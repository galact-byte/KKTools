"""目录卡片扫描：遍历目录下的 PNG，识别类型并提取缩略图与基本信息。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from core.kk_card import read_card_light

TYPE_LABELS = {
    "character": "角色卡",
    "coordinate": "服装卡",
    "scene": "场景卡",
    "other": "其它",
}


@dataclass
class CardItem:
    path: str
    type: str            # character / coordinate / scene / other
    game: str            # KK / KKS / ?
    name: str            # 角色名（仅角色卡）
    thumbnail: bytes     # 缩略图字节（PNG）


def scan_item(path: Path) -> CardItem | None:
    """轻量识别单个 PNG：只读缩略图+头部，不整文件读取（见 read_card_light）。"""
    try:
        info = read_card_light(path)
    except OSError:
        return None
    return CardItem(
        path=str(path), type=info.type, game=info.game,
        name=info.name, thumbnail=info.thumbnail,
    )


def scan_dir(
    directory: str | Path,
    *,
    recursive: bool = False,
    progress: Callable[[int, int, str], None] | None = None,
) -> list[CardItem]:
    """扫描目录下的 PNG（默认不递归）。"""
    directory = Path(directory)
    if not directory.is_dir():
        return []
    if recursive:
        files = [p for p in directory.rglob("*.png") if p.is_file()]
    else:
        files = [p for p in directory.glob("*.png") if p.is_file()]
    total = len(files)
    items: list[CardItem] = []
    for i, p in enumerate(files, 1):
        item = scan_item(p)
        if item is not None:
            items.append(item)
        if progress and (i % 10 == 0 or i == total):
            progress(i, total, p.name)
    return items
