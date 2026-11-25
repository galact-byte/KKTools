"""卡片标签与可读资料导出；元数据独立于游戏卡片存储。"""
from __future__ import annotations

import base64
import csv
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

import msgpack

from core import kk_card, scene_card, settings


def unique_path(folder: Path, name: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / name
    n = 2
    while target.exists() or target.is_symlink():
        target = folder / f'{Path(name).stem} ({n}){Path(name).suffix}'
        n += 1
    return target


def _key(path: str | Path) -> str:
    return os.path.normcase(str(Path(path).resolve()))


def _tags_connection():
    db_path = settings.app_dir() / 'card_tags.sqlite3'
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10)
    conn.execute('CREATE TABLE IF NOT EXISTS tags (path TEXT NOT NULL, tag TEXT NOT NULL, PRIMARY KEY(path, tag))')
    conn.execute('CREATE TABLE IF NOT EXISTS authors (path TEXT PRIMARY KEY, author TEXT NOT NULL)')
    return conn


def get_author_override(path: str | Path) -> str:
    with closing(_tags_connection()) as conn:
        row = conn.execute('SELECT author FROM authors WHERE path=?', (_key(path),)).fetchone()
        return str(row[0]) if row else ''


def all_author_overrides() -> dict[str, str]:
    with closing(_tags_connection()) as conn:
        return {str(r[0]): str(r[1]) for r in conn.execute('SELECT path, author FROM authors')}


def metadata_for_paths(paths: list[str | Path]) -> tuple[dict[str, list[str]], dict[str, str]]:
    """仅读取当前结果页的本地标签和作者覆盖，不载入整个本地资料库。"""
    keys = list(dict.fromkeys(_key(path) for path in paths))
    tags: dict[str, list[str]] = {}
    authors: dict[str, str] = {}
    with closing(_tags_connection()) as conn:
        for start in range(0, len(keys), 500):
            batch = keys[start:start + 500]
            placeholders = ",".join("?" for _ in batch)
            for path, tag in conn.execute(
                f"SELECT path,tag FROM tags WHERE path IN ({placeholders}) ORDER BY rowid", batch,
            ):
                tags.setdefault(path, []).append(tag)
            authors.update(conn.execute(
                f"SELECT path,author FROM authors WHERE path IN ({placeholders})", batch,
            ))
    return tags, authors


def set_author_override(path: str | Path, author: str) -> str:
    if not Path(path).is_file():
        raise ValueError('卡片文件不存在')
    cleaned = str(author or '').strip()
    if len(cleaned) > 80:
        raise ValueError('作者名称不超过 80 个字符')
    with closing(_tags_connection()) as conn, conn:
        if not cleaned:
            conn.execute('DELETE FROM authors WHERE path=?', (_key(path),))
            return ''
        conn.execute('INSERT OR REPLACE INTO authors (path, author) VALUES (?, ?)', (_key(path), cleaned))
    return cleaned


def get_tags(path: str | Path) -> list[str]:
    with closing(_tags_connection()) as conn:
        return [r[0] for r in conn.execute('SELECT tag FROM tags WHERE path=? ORDER BY rowid', (_key(path),))]


def all_tags() -> dict[str, list[str]]:
    with closing(_tags_connection()) as conn:
        result: dict[str, list[str]] = {}
        for path, tag in conn.execute('SELECT path, tag FROM tags ORDER BY rowid'):
            result.setdefault(path, []).append(tag)
        return result


def set_tags(path: str | Path, tags: list[str]) -> list[str]:
    if not Path(path).is_file():
        raise ValueError('卡片文件不存在')
    if not isinstance(tags, list) or len(tags) > 50 or any(not isinstance(t, str) or len(t) > 40 for t in tags):
        raise ValueError('最多 50 个标签，每个标签不超过 40 字符')
    tags = list(dict.fromkeys(t.strip() for t in tags if t.strip()))
    with closing(_tags_connection()) as conn, conn:
        conn.execute('DELETE FROM tags WHERE path=?', (_key(path),))
        conn.executemany('INSERT INTO tags VALUES (?,?)', [(_key(path), t) for t in tags])
    return tags


def _json_value(value):
    if isinstance(value, bytes):
        return {'encoding': 'base64', 'data': base64.b64encode(value).decode('ascii')}
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(v) for v in value]
    return value


def _cell(value) -> str:
    text = str(value)
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else text


def export_data(kind: str, paths: list[str], folder: Path, fmt: str = 'json') -> Path:
    if not paths or any(not Path(p).is_file() for p in paths):
        raise ValueError('请选择存在的本地卡片')
    if (kind, fmt) not in {('list', 'csv'), ('character', 'json'), ('scene', 'json'), ('scene', 'txt')}:
        raise ValueError('不支持的导出类型或格式')
    if kind != 'list' and len(paths) != 1:
        raise ValueError('档案导出每次请选择一张卡片')
    if kind == 'list':
        rows = []
        overrides = all_author_overrides()
        for p in paths:
            info = kk_card.read_card_light(p, include_thumbnail=False)
            author = overrides.get(_key(p), '') or info.author
            rows.append([info.name, author, Path(p).name, info.type, info.game, '; '.join(get_tags(p)), str(Path(p).resolve())])
        target = unique_path(folder, '卡片列表.csv')
        with target.open('x', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['名称', '作者', '文件名', '类型', '游戏', '标签', '路径'])
            writer.writerows([[_cell(c) for c in row] for row in rows])
        return target
    source = Path(paths[0])
    if kind == 'character':
        card = kk_card.KoikatuCard.load(source)
        blocks = {}
        for name in card.block_names:
            try:
                # 必须解码完整块；多段流或不完整尾部按原始字节保留。
                value = msgpack.unpackb(card.blocks[name], raw=False, strict_map_key=False)
            except Exception:
                value = None
            blocks[name] = _json_value(value if value is not None else card.blocks[name])
        doc = {'path': str(source), 'game': card.game, 'marker': card.marker, 'version': card.version,
               'parameter': _json_value(card.parameter), 'blocks': blocks,
               'mod_ids': kk_card.extract_mod_ids(card, strict=True), 'tags': get_tags(source)}
    else:
        if kk_card.classify(source.read_bytes())[0] != 'scene':
            raise ValueError('请选择场景卡')
        doc = scene_card.analyze_scene(source, strict=True)
    target = unique_path(folder, source.stem + ('_档案.json' if kind == 'character' else f'_场景分析.{fmt}'))
    if fmt == 'txt':
        lines = [f'场景：{source.name}', f"内嵌角色：{doc['character_count']}", '']
        lines += [f"{c['name']} | {c['game']} | Mod {c['mods']}" for c in doc['characters']]
        lines += ['', 'Mod 依赖：'] + [f'{k}: {v}' for k, v in doc['mod_ids'].items()]
        content = '\n'.join(lines)
    else:
        content = json.dumps(doc, ensure_ascii=False, indent=2)
    with target.open('x', encoding='utf-8') as f:
        f.write(content)
    return target
