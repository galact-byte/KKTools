"""目录卡片扫描：遍历目录下的 PNG，识别类型并提取元数据（支持 SQLite 增量缓存与多线程）。"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from core import catalog, settings
from core.kk_card import read_card_light

TYPE_LABELS = {
    "character": "角色卡",
    "coordinate": "服装卡",
    "scene": "场景卡",
    "other": "其它",
}

# 递归扫描整个游戏目录时自动跳过的非卡片巨目录（小写比对）
IGNORED_RECURSIVE_DIRS = frozenset(
    {
        "abdata",
        "mods",
        "bepinex",
        "mono",
        "monobleedingedge",
        "koikatu_data",
        "koikatsusunshine_data",
        "koikatsuparty_data",
        "cap",
        "bg",
        "frame",
        "material",
        "overlays",
        "thumb_cache",
        ".git",
    }
)


_SCAN_WRITE_LOCK = threading.Lock()
_INDEX_REVISION = 1


class ScanCancelled(Exception):
    """用户主动取消卡片目录扫描。"""


@dataclass
class CardItem:
    path: str
    type: str            # character / coordinate / scene / other
    game: str            # KK / KKS / ?
    name: str            # 角色名（仅角色卡）
    thumbnail: bytes     # 缩略图字节（PNG；快速扫描模式可为空，由 HTTP 按需加载）
    author: str = ""
    author_history: tuple[str, ...] = ()
    author_source: str = ""
    user_id: str = ""
    mtime_ns: int = 0
    size: int = 0


def _norm_key(path: str | Path) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def _index_db_path(cache_path: Path | None = None) -> Path:
    return cache_path if cache_path is not None else (settings.app_dir() / "card_index.sqlite3")


def _open_index_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=15)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS card_index (
            norm_path TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            mtime_ns INTEGER NOT NULL,
            size INTEGER NOT NULL,
            type TEXT NOT NULL,
            game TEXT NOT NULL,
            name TEXT NOT NULL,
            author TEXT NOT NULL,
            author_history TEXT NOT NULL,
            author_source TEXT NOT NULL,
            user_id TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS card_scan_members (
            root TEXT NOT NULL, recursive INTEGER NOT NULL,
            norm_path TEXT NOT NULL, generation TEXT NOT NULL,
            PRIMARY KEY (root, recursive, norm_path)
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS card_scan_state (
            root TEXT NOT NULL, recursive INTEGER NOT NULL, complete INTEGER NOT NULL,
            PRIMARY KEY (root, recursive)
        )"""
    )
    # 这里只包含可重建的扫描缓存，不涉及 card_tags 中的用户标签与作者记录。
    if conn.execute("PRAGMA user_version").fetchone()[0] < _INDEX_REVISION:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("PRAGMA user_version").fetchone()[0] < _INDEX_REVISION:
                conn.execute("DELETE FROM card_scan_members")
                conn.execute("DELETE FROM card_scan_state")
                conn.execute("DELETE FROM card_index")
                conn.execute(f"PRAGMA user_version={_INDEX_REVISION}")
    return conn


@contextmanager
def _scan_writer(cancel_event: threading.Event | None):
    # 成员清单以一次完整扫描为单位更新，避免重叠扫描互相清除新发现的成员。
    while not _SCAN_WRITE_LOCK.acquire(timeout=.1):
        if cancel_event is not None and cancel_event.is_set():
            raise ScanCancelled("扫描已取消")
    try:
        if cancel_event is not None and cancel_event.is_set():
            raise ScanCancelled("扫描已取消")
        yield
    finally:
        _SCAN_WRITE_LOCK.release()


def query_index_page(
    directory: str | Path, *, recursive: bool = False, offset: int = 0,
    limit: int = 120, card_type: str = "", game: str = "", author: str | None = None,
    search: str = "", cache_path: Path | None = None,
) -> dict:
    """查询指定扫描范围的索引页；不遍历目录，也不重新解析卡片。"""
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError("offset 必须为非负整数，limit 必须为 1 至 500 的整数")
    if not isinstance(recursive, bool):
        raise ValueError("recursive 必须为布尔值")
    if card_type not in ("", *TYPE_LABELS) or game not in ("", "KK", "KKS", "EC", "?"):
        raise ValueError("不支持的卡片类型或游戏筛选")
    if not isinstance(search, str) or (author is not None and not isinstance(author, str)):
        raise ValueError("搜索和作者筛选必须为字符串")
    root = _norm_key(Path(directory).resolve())
    with closing(catalog._tags_connection()):
        pass
    with closing(_open_index_db(_index_db_path(cache_path))) as conn:
        conn.execute("ATTACH DATABASE ? AS local_catalog", (str(settings.app_dir() / "card_tags.sqlite3"),))
        effective_author = "COALESCE(NULLIF(a.author, ''), c.author)"
        conditions = ["m.root=?", "m.recursive=?"]
        params: list = [root, int(recursive)]
        for column, value in (("c.type", card_type), ("c.game", game)):
            if value:
                conditions.append(f"{column}=?")
                params.append(value)
        if author is not None:
            conditions.append(f"{effective_author}=?")
            params.append(author)
        if search:
            conditions.append(
                f"(instr(lower(c.path), lower(?))>0 OR instr(lower(c.name), lower(?))>0 "
                f"OR instr(lower({effective_author}), lower(?))>0 OR EXISTS "
                "(SELECT 1 FROM local_catalog.tags t WHERE t.path=c.norm_path "
                "AND instr(lower(t.tag), lower(?))>0))"
            )
            params.extend([search] * 4)
        source = (
            "FROM card_scan_members m JOIN card_index c ON c.norm_path=m.norm_path "
            "LEFT JOIN local_catalog.authors a ON a.path=c.norm_path WHERE " + " AND ".join(conditions)
        )
        conn.execute("BEGIN")
        total = conn.execute("SELECT COUNT(*) " + source, params).fetchone()[0]
        rows = conn.execute(
            "SELECT c.path,c.type,c.game,c.name,c.author,c.author_history,c.author_source,"
            "c.user_id,c.mtime_ns,c.size " + source + " ORDER BY c.norm_path LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        state = conn.execute(
            "SELECT complete FROM card_scan_state WHERE root=? AND recursive=?", (root, int(recursive)),
        ).fetchone()
    items = [CardItem(
        path=r[0], type=r[1], game=r[2], name=r[3], thumbnail=b"", author=r[4],
        author_history=tuple(json.loads(r[5])), author_source=r[6], user_id=r[7],
        mtime_ns=r[8], size=r[9],
    ) for r in rows]
    return {"directory": str(Path(directory).resolve()), "recursive": recursive, "total": total,
            "offset": offset, "limit": limit, "hasMore": offset + len(items) < total,
            "indexed": state is not None, "complete": bool(state and state[0]), "items": items}


def _collect_png_entries(
    directory: Path,
    *,
    recursive: bool,
    cancel_event: threading.Event | None = None,
    on_discover: Callable[[int], None] | None = None,
) -> list[tuple[Path, int, int]]:
    """使用 os.scandir 高速遍历 PNG 文件，并在递归模式下剪枝跳过非卡片巨目录。"""
    results: list[tuple[Path, int, int]] = []
    stack: list[tuple[Path, bool]] = [(directory, True)]
    while stack:
        if cancel_event is not None and cancel_event.is_set():
            raise ScanCancelled("扫描已取消")
        current, is_root = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    if cancel_event is not None and cancel_event.is_set():
                        raise ScanCancelled("扫描已取消")
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if recursive:
                                if entry.name.lower() in IGNORED_RECURSIVE_DIRS:
                                    continue
                                stack.append((Path(entry.path), False))
                            continue
                        if not entry.name.lower().endswith(".png"):
                            continue
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        st = entry.stat(follow_symlinks=False)
                        results.append((Path(entry.path), int(st.st_mtime_ns), int(st.st_size)))
                        if on_discover and len(results) % 500 == 0:
                            on_discover(len(results))
                    except OSError:
                        continue
        except OSError:
            continue
    results.sort(key=lambda item: item[0].as_posix().lower())
    return results


def scan_item(path: Path, *, include_thumbnail: bool = True) -> CardItem | None:
    """轻量识别单个 PNG：只读头部与所需元数据，不整文件读取（见 read_card_light）。"""
    try:
        st = path.stat()
        info = read_card_light(path, include_thumbnail=include_thumbnail)
    except OSError:
        return None
    return CardItem(
        path=str(path),
        type=info.type,
        game=info.game,
        name=info.name,
        thumbnail=info.thumbnail,
        author=info.author,
        author_history=info.author_history,
        author_source=info.author_source,
        user_id=info.user_id,
        mtime_ns=int(st.st_mtime_ns),
        size=int(st.st_size),
    )


def scan_dir(
    directory: str | Path,
    *,
    recursive: bool = False,
    progress: Callable[[int, int, str], None] | None = None,
) -> list[CardItem]:
    """扫描目录下的 PNG（默认不递归，兼容原有返回缩略图字节的行为）。"""
    directory = Path(directory)
    if not directory.is_dir():
        return []
    entries = _collect_png_entries(directory, recursive=recursive)
    total = len(entries)
    items: list[CardItem] = []
    for i, (p, _, _) in enumerate(entries, 1):
        item = scan_item(p, include_thumbnail=True)
        if item is not None:
            items.append(item)
        if progress and (i % 10 == 0 or i == total):
            progress(i, total, p.name)
    return items


def scan_dir_fast(
    directory: str | Path,
    *,
    recursive: bool = False,
    workers: int = 8,
    cache_path: Path | None = None,
    progress: Callable[[int, int, str], None] | None = None,
    cancel_event: threading.Event | None = None,
    include_thumbnail: bool = False,
    collect_results: bool = True,
) -> list[CardItem]:
    """增量扫描并分批写入索引；分页模式不在内存中收集整库元数据。

    缓存命中仍需遍历目录和读取文件属性，但不会重新打开卡片解析。
    未完成扫描的已解析内容也会提交；只有完整扫描才清除范围内的过期成员。
    """
    directory = Path(directory).resolve()
    if not directory.is_dir():
        return []
    if type(workers) is not int or not 1 <= workers <= 32:
        raise ValueError("workers 必须为 1 至 32 的整数")

    def check_cancel() -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise ScanCancelled("扫描已取消")

    check_cancel()
    if progress:
        progress(0, 0, "正在遍历目录文件…")
    entries = _collect_png_entries(
        directory, recursive=recursive, cancel_event=cancel_event,
        on_discover=(lambda n: progress(0, n, f"已发现 {n} 个 PNG 文件…")) if progress else None,
    )
    total = len(entries)
    results: list[CardItem | None] = [None] * total if collect_results else []
    root = _norm_key(directory)
    generation = uuid.uuid4().hex
    done = 0
    found = 0
    rows: list[tuple] = []
    members: list[tuple] = []

    def parse(job):
        idx, p, mtime_ns, size, nk = job
        check_cancel()
        try:
            info = read_card_light(p, include_thumbnail=include_thumbnail)
        except OSError:
            return idx, None, None
        item = CardItem(
            path=str(p), type=info.type, game=info.game, name=info.name,
            thumbnail=info.thumbnail, author=info.author, author_history=info.author_history,
            author_source=info.author_source, user_id=info.user_id, mtime_ns=mtime_ns, size=size,
        )
        row = (nk, str(p), mtime_ns, size, info.type, info.game, info.name, info.author,
               json.dumps(list(info.author_history), ensure_ascii=False), info.author_source, info.user_id)
        return idx, item, row

    with _scan_writer(cancel_event), closing(_open_index_db(_index_db_path(cache_path))) as conn:
        conn.execute("INSERT OR REPLACE INTO card_scan_state VALUES (?,?,0)", (root, int(recursive)))
        conn.commit()

        def flush() -> None:
            with conn:
                if rows:
                    conn.executemany(
                        "INSERT OR REPLACE INTO card_index "
                        "(norm_path,path,mtime_ns,size,type,game,name,author,author_history,author_source,user_id) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows,
                    )
                if members:
                    conn.executemany("INSERT OR REPLACE INTO card_scan_members VALUES (?,?,?,?)", members)
            rows.clear()
            members.clear()

        def accept(idx, item, row=None) -> None:
            nonlocal done, found
            if item is not None:
                found += 1
                if collect_results:
                    results[idx] = item
                members.append((root, int(recursive), _norm_key(item.path), generation))
            if row is not None:
                rows.append(row)
            done += 1
            if len(members) >= 128:
                flush()
            if progress and (done % 25 == 0 or done == total):
                progress(done, total, entries[idx][0].name)

        pool = ThreadPoolExecutor(max_workers=workers)
        pending = {}
        try:
            for start in range(0, total, 500):
                check_cancel()
                batch = entries[start:start + 500]
                keys = [_norm_key(p) for p, _, _ in batch]
                sql = ("SELECT norm_path,mtime_ns,size,type,game,name,author,author_history,author_source,user_id "
                       f"FROM card_index WHERE norm_path IN ({','.join('?' for _ in keys)})")
                cached = {r[0]: r[1:] for r in conn.execute(sql, keys)}
                jobs = []
                for idx, (p, mtime_ns, size) in enumerate(batch, start):
                    check_cancel()
                    nk = _norm_key(p)
                    hit = cached.get(nk)
                    if hit and hit[0] == mtime_ns and hit[1] == size and not include_thumbnail:
                        try:
                            history = tuple(json.loads(hit[6]))
                        except (ValueError, TypeError):
                            jobs.append((idx, p, mtime_ns, size, nk))
                            continue
                        accept(idx, CardItem(
                            path=str(p), type=hit[2], game=hit[3], name=hit[4], thumbnail=b"",
                            author=hit[5], author_history=history, author_source=hit[7], user_id=hit[8],
                            mtime_ns=mtime_ns, size=size,
                        ))
                    else:
                        jobs.append((idx, p, mtime_ns, size, nk))
                todo = iter(jobs)
                while True:
                    check_cancel()
                    while len(pending) < workers * 2:
                        job = next(todo, None)
                        if job is None:
                            break
                        pending[pool.submit(parse, job)] = job
                    if not pending:
                        break
                    finished, _ = wait(pending, return_when=FIRST_COMPLETED)
                    for future in finished:
                        check_cancel()
                        pending.pop(future)
                        accept(*future.result())
                flush()
            check_cancel()
            with conn:
                conn.execute(
                    "DELETE FROM card_scan_members WHERE root=? AND recursive=? AND generation<>?",
                    (root, int(recursive), generation),
                )
                conn.execute("INSERT OR REPLACE INTO card_scan_state VALUES (?,?,1)", (root, int(recursive)))
        finally:
            for future in pending:
                future.cancel()
            pool.shutdown(wait=True, cancel_futures=True)
            flush()
    if progress:
        progress(total, total, f"扫描完成，共 {found} 张")
    return [item for item in results if item is not None]
