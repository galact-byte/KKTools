"""Mod 仓库索引与缺失检测。

- 扫描目录下的 .zipmod / .zip，读取内部 manifest.xml，建立 {guid: 信息} 索引。
- 从角色卡提取依赖 ModID（见 kk_card.extract_mod_ids）。
- 比对卡片依赖与本地索引，给出缺失清单。

索引可缓存为 JSON，避免每次重扫海量 mod 目录。
"""

from __future__ import annotations

import inspect
import json
import shutil
import xml.etree.ElementTree as ET
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
from typing import Callable, Iterable

from core.kk_card import KoikatuCard, extract_mod_ids

MOD_SUFFIXES = (".zipmod", ".zip")


@dataclass
class ModEntry:
    guid: str
    name: str = ""
    version: str = ""
    author: str = ""
    path: str = ""


def read_manifest(zip_path: Path) -> ModEntry | None:
    """读取单个 zipmod 的 manifest.xml，返回 ModEntry；无 manifest 或无 guid 则 None。"""
    try:
        with zipfile.ZipFile(zip_path) as zf:
            if "manifest.xml" not in zf.namelist():
                return None
            raw = zf.read("manifest.xml")
    except (zipfile.BadZipFile, OSError):
        return None
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return None

    def text(tag: str) -> str:
        el = root.find(tag)
        return (el.text or "").strip() if el is not None else ""

    guid = text("guid")
    if not guid:
        return None
    return ModEntry(
        guid=guid,
        name=text("name"),
        version=text("version"),
        author=text("author"),
        path=str(zip_path),
    )


def iter_mod_files(dirs: Iterable[str]) -> Iterable[Path]:
    for d in dirs:
        base = Path(d)
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if p.suffix.lower() in MOD_SUFFIXES and p.is_file():
                yield p


@dataclass
class ModIndex:
    """guid -> ModEntry 的全局索引，附带文件指纹用于增量重建。"""

    entries: dict[str, ModEntry] = field(default_factory=dict)
    # 文件指纹：abspath -> (mtime_int, size, guid|None)。guid=None 表示该文件无有效
    # manifest（负缓存，避免重复打开坏包）。用于增量重建时跳过未变动文件。
    files: dict[str, tuple] = field(default_factory=dict)

    def __contains__(self, guid: str) -> bool:
        return guid in self.entries

    def get(self, guid: str) -> ModEntry | None:
        return self.entries.get(guid)

    @property
    def count(self) -> int:
        return len(self.entries)

    def build(
        self,
        dirs: Iterable[str],
        progress: Callable[..., None] | None = None,
        workers: int = 16,
        previous: "ModIndex | None" = None,
    ) -> "ModIndex":
        """扫描目录建立索引。

        增量：传入 previous（通常是已加载的缓存），未变动的 zipmod（路径+mtime+大小
        一致）直接复用，不再打开文件——整合版加几个 mod 后重建可从数分钟降到秒级。
        首次构建（previous 为空）则全量扫描。

        progress 支持 2 参数 (done, path) 或 3 参数 (done, total, path) 回调。
        """
        old_files = previous.files if previous else {}
        old_entries = previous.entries if previous else {}

        new_entries: dict[str, ModEntry] = {}
        new_files: dict[str, tuple] = {}
        files = list(iter_mod_files(dirs))
        total = len(files)
        done = 0
        to_read: list[Path] = []

        # 兼容 2 参数 (done, path) 与 3 参数 (done, total, path) 进度回调
        takes_total = False
        if progress is not None:
            try:
                sig = inspect.signature(progress)
                pos_params = [
                    p
                    for p in sig.parameters.values()
                    if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                ]
                has_varargs = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in sig.parameters.values())
                takes_total = has_varargs or len(pos_params) >= 3
            except (TypeError, ValueError):
                takes_total = False

        def _emit(cur: int, name: str) -> None:
            if progress is None:
                return
            if takes_total:
                progress(cur, total, name)
            else:
                progress(cur, name)

        # 第一遍：复用未变动文件
        for p in files:
            sp = str(p)
            try:
                st = p.stat()
            except OSError:
                continue
            fp = (int(st.st_mtime), st.st_size)
            old = old_files.get(sp)
            if old is not None and (old[0], old[1]) == fp:
                guid = old[2]
                new_files[sp] = old
                if guid and guid in old_entries:
                    new_entries[old_entries[guid].guid] = old_entries[guid]
                done += 1
            else:
                to_read.append(p)
        if done > 0:
            _emit(done, "")

        # 第二遍：并行读取新增/变动文件的 manifest
        if to_read:
            with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
                for p, entry in zip(to_read, ex.map(read_manifest, to_read)):
                    sp = str(p)
                    try:
                        st = p.stat()
                        fp = (int(st.st_mtime), st.st_size)
                    except OSError:
                        fp = (0, 0)
                    guid = entry.guid if entry else None
                    new_files[sp] = (fp[0], fp[1], guid)
                    if entry:
                        new_entries[entry.guid] = entry
                    done += 1
                    if done % 100 == 0 or done == total:
                        _emit(done, str(p))
        _emit(total, "")

        self.entries = new_entries
        self.files = new_files
        return self

    def save(self, path: str | Path) -> None:
        data = {
            "entries": {
                g: {"name": e.name, "version": e.version, "author": e.author, "path": e.path}
                for g, e in self.entries.items()
            },
            "files": {sp: list(fp) for sp, fp in self.files.items()},
        }
        Path(path).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "ModIndex":
        idx = cls()
        p = Path(path)
        if not p.exists():
            return idx
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return idx
        for guid, info in data.get("entries", {}).items():
            idx.entries[guid] = ModEntry(
                guid=guid,
                name=info.get("name", ""),
                version=info.get("version", ""),
                author=info.get("author", ""),
                path=info.get("path", ""),
            )
        for sp, fp in data.get("files", {}).items():
            if isinstance(fp, list) and len(fp) == 3:
                idx.files[sp] = (fp[0], fp[1], fp[2])
        return idx


@dataclass
class MissingReport:
    card_path: str
    required: dict[str, int]            # ModID -> 次数
    present: list[str]                  # 仓库里有的
    missing: list[str]                  # 仓库里没有的

    @property
    def required_count(self) -> int:
        return len(self.required)

    @property
    def missing_count(self) -> int:
        return len(self.missing)


def check_card(card_path: str | Path, index: ModIndex, *, strict: bool = False) -> MissingReport:
    """检查一张卡的 mod 依赖在索引中的缺失情况。

    角色卡：直接读 Sideloader UAR。场景卡：聚合内嵌角色依赖 + 场景级 studio 道具依赖。
    """
    from core.kk_card import KoikatuCard as _KC, KKCardError, classify, is_character_card

    data = Path(card_path).read_bytes()
    kind = classify(data)[0] if strict else None
    if is_character_card(data) or kind == "coordinate":
        required = extract_mod_ids(_KC.from_bytes(data), strict=strict)
    else:
        if strict and kind != "scene":
            raise KKCardError("无法识别为可完整分析的角色卡、服装卡或场景卡")
        from core import scene_card
        if strict and scene_card.get_scene_preview(data) is None:
            raise KKCardError("场景卡封面损坏，无法完整分析")
        required = {}
        for c in scene_card.find_embedded_characters(data, strict=strict):
            for g, n in extract_mod_ids(c, strict=strict).items():
                required[g] = required.get(g, 0) + n
        for g, n in scene_card.extract_scene_mod_ids(data, strict=strict).items():
            required[g] = required.get(g, 0) + n

    present = [g for g in required if g in index]
    missing = [g for g in required if g not in index]
    return MissingReport(
        card_path=str(card_path),
        required=required,
        present=sorted(present),
        missing=sorted(missing),
    )


def _safe_name(s: str) -> str:
    name = "".join(c for c in (s or "") if c not in r'\/:*?"<>|' and ord(c) >= 32).strip().rstrip('. ')
    return '' if not name or PureWindowsPath(name).is_reserved() else name


def export_guid_list(index: ModIndex, path: str | Path) -> int:
    """导出本机索引里所有 mod 的 guid（每行一个），供他人比对。返回条数。"""
    guids = sorted(index.entries)
    Path(path).write_text("\n".join(guids), encoding="utf-8")
    return len(guids)


def parse_guid_list(path: str | Path) -> list[str]:
    """解析 guid 清单文件：忽略空行与 # 注释/标题行（兼容缺失清单导出格式）。"""
    out: list[str] = []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            out.append(s.split("|")[0].strip().lstrip("- ").strip())
    return list(dict.fromkeys(g for g in out if g))


def compare_guid_list(guids: list[str], index: ModIndex) -> dict:
    """把一份 guid 清单与本机索引比对：本机已有(可补给对方) vs 本机也缺。"""
    have = [g for g in guids if g in index]
    lack = [g for g in guids if g not in index]
    return {"total": len(guids), "have": sorted(have), "lack": sorted(lack)}


def export_as_zip(
    guids: Iterable[str],
    index: ModIndex,
    out_zip: str | Path,
    *,
    progress: Callable[[int, int, str], None] | None = None,
) -> tuple[int, int]:
    """把 guids 中索引里存在的 zipmod 直接打进一个 zip 压缩包。返回(打入数, 跳过数)。

    用 ZIP_STORED（不再二次压缩）——zipmod 本身已是压缩包，重压既慢又几乎不省体积。
    相比"复制到目录"，导出单个 zip 更便于直接发给别人。
    """
    guids = list(dict.fromkeys(guids))  # 去重保序
    out = Path(out_zip)
    out.parent.mkdir(parents=True, exist_ok=True)
    added = skipped = 0
    total = len(guids)
    seen_names: set[str] = set()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as zf:
        for i, g in enumerate(guids, 1):
            e = index.get(g)
            if e and e.path and Path(e.path).exists():
                arc = Path(e.path).name
                # 同名文件避免覆盖：加 guid 前缀
                if arc in seen_names:
                    arc = f"{g}__{arc}"
                seen_names.add(arc)
                zf.write(e.path, arc)
                added += 1
            else:
                skipped += 1
            if progress:
                progress(i, total, g)
    return added, skipped


def copy_fillable(guids: Iterable[str], index: ModIndex, target_dir: str | Path) -> tuple[int, int]:
    """把指定 guid 中索引里存在的 zipmod 复制到 target_dir。返回(复制数, 跳过数)。"""
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    copied = skipped = 0
    for g in dict.fromkeys(guids):           # 去重保序
        e = index.get(g)
        if e and e.path and Path(e.path).exists():
            dst = target / Path(e.path).name
            if dst.exists():
                skipped += 1
                continue
            shutil.copy2(e.path, dst)
            copied += 1
        else:
            skipped += 1
    return copied, skipped


def organize_by_author(
    index: ModIndex,
    target_dir: str | Path,
    *,
    move: bool = False,
    progress: Callable[[int, int, str], None] | None = None,
) -> dict:
    """把索引里的 zipmod 按 manifest 作者整理到 target_dir/<作者>/ 下。

    move=False(默认) 为复制(安全、不动原库)；move=True 为移动(就地整理，省空间但改原库)。
    移动后索引路径会失效，调用方应提示重建索引。
    """
    target = Path(target_dir)
    entries = list(index.entries.values())
    total = len(entries)
    done = moved = skipped = 0
    for e in entries:
        done += 1
        src = Path(e.path) if e.path else None
        if not src or not src.exists():
            skipped += 1
        else:
            author = _safe_name(e.author) or "未知作者"
            dst_dir = target / author
            if not dst_dir.resolve().is_relative_to(target.resolve()):
                raise ValueError(f"整理目标超出所选输出目录：{dst_dir}")
            dst = dst_dir / src.name
            try:
                if src.resolve() == dst.resolve():
                    skipped += 1
                elif dst.exists():
                    skipped += 1
                else:
                    dst_dir.mkdir(parents=True, exist_ok=True)
                    if move:
                        shutil.move(str(src), str(dst))
                    else:
                        shutil.copy2(src, dst)
                    moved += 1
            except OSError:
                skipped += 1
        if progress and (done % 50 == 0 or done == total):
            progress(done, total, e.name)
    return {"processed": done, "done": moved, "skipped": skipped, "move": move}


def archive_unreferenced(
    index: ModIndex,
    card_paths: list[str],
    archive_dir: str | Path,
    *,
    move: bool = False,
    progress: Callable[[int, int, str], None] | None = None,
) -> dict:
    """把"没有被任一给定卡片引用"的 mod 归档到 archive_dir。

    先求所有卡片依赖 guid 的并集，索引中不在并集里的即未引用。
    注意：未引用是相对于**所选卡片**而言，请谨慎选卡。move=False 默认复制。
    """
    if not card_paths:
        raise ValueError("请先选择需要分析的卡片，不能用空选择判断未引用 Mod")
    used: set[str] = set()
    for cp in card_paths:
        try:
            used.update(check_card(cp, index, strict=True).required)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"卡片依赖分析不完整，已停止归档：{cp}\n{exc}") from exc
    archive = Path(archive_dir)
    entries = list(index.entries.items())
    total = len(entries)
    done = archived = 0
    for guid, e in entries:
        done += 1
        if guid in used:
            continue
        src = Path(e.path) if e.path else None
        if not src or not src.exists():
            continue
        dst = archive / src.name
        try:
            if not dst.exists():
                archive.mkdir(parents=True, exist_ok=True)
                if move:
                    shutil.move(str(src), str(dst))
                else:
                    shutil.copy2(src, dst)
                archived += 1
        except OSError:
            pass
        if progress and (done % 50 == 0 or done == total):
            progress(done, total, e.name)
    return {"used": len(used), "archived": archived, "total": index.count, "move": move}
