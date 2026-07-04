"""场景卡工具：从 Studio 场景卡中提取内嵌的角色卡，并分析其 mod 依赖。

场景卡里的角色以 `productNo + marker + version + 脸图PNG + lstInfo + data` 的形式
内嵌（**没有前导缩略图**）。提取时以脸图作为封面，重建为可独立读取的标准角色卡。
"""

from __future__ import annotations

from pathlib import Path

import msgpack

from core.kk_card import (
    PNG_SIGNATURE,
    BlockInfo,
    KoikatuCard,
    _Reader,
    extract_mod_ids,
    png_data_length,
)

# 【 的 UTF-8 字节是 e3 80 90；拼上角色 marker 主体用于定位内嵌角色
_FULLWIDTH_OPEN = b"\xe3\x80\x90"
CHARA_MARKER_PATTERNS = [
    _FULLWIDTH_OPEN + b"KoiKatuCharaSun",
    _FULLWIDTH_OPEN + b"KoiKatuCharaSP",
    _FULLWIDTH_OPEN + b"KoiKatuChara",
]


def _parse_embedded(data: bytes, marker_full_start: int) -> KoikatuCard | None:
    """从内嵌角色的 marker 起点解析出一张可独立保存的角色卡（脸图作封面）。"""
    # 布局：[productNo:int32][marker长度前缀:1B][marker...]
    chara_start = marker_full_start - 5
    if chara_start < 0:
        return None
    r = _Reader(data)
    r.pos = chara_start
    try:
        product_no = r.read_int32()
        marker = r.read_cs_string()
        version = r.read_cs_string()
        face_len = r.read_int32()
        if face_len <= 0 or r.pos + face_len > len(data):
            return None
        face = r.read(face_len)
        if face[:8] != PNG_SIGNATURE:
            return None
        lst_len = r.read_int32()
        if lst_len <= 0 or r.pos + lst_len > len(data):
            return None
        lst_raw = r.read(lst_len)
        lstinfo = msgpack.unpackb(lst_raw, raw=False, strict_map_key=False)
        data_len = r.read_int64()
        if data_len < 0 or r.pos + data_len > len(data):
            return None
        blob = r.read(data_len)
    except Exception:  # noqa: BLE001 - 解析失败即视为不是有效内嵌角色
        return None

    block_order: list[BlockInfo] = []
    blocks: dict[str, bytes] = {}
    info_list = lstinfo.get("lstInfo")
    if not isinstance(info_list, list):
        return None
    for info in info_list:
        try:
            bi = BlockInfo(info["name"], info.get("version", "0.0.0"),
                           int(info["pos"]), int(info["size"]))
        except (KeyError, TypeError, ValueError):
            return None
        block_order.append(bi)
        blocks[bi.name] = blob[bi.pos : bi.pos + bi.size]

    return KoikatuCard(
        thumbnail=face,          # 用脸图当封面缩略图
        face=face,
        product_no=product_no,
        marker=marker,
        version=version,
        blocks=blocks,
        block_order=block_order,
        _lstinfo_raw=lst_raw,
        _data_blob=blob,
        _dirty=False,
    )


def find_embedded_characters(data: bytes) -> list[KoikatuCard]:
    """扫描场景卡字节，返回所有成功解析的内嵌角色卡。"""
    seen_starts: set[int] = set()
    cards: list[KoikatuCard] = []
    for pat in CHARA_MARKER_PATTERNS:
        start = -1
        while True:
            start = data.find(pat, start + 1)
            if start < 0:
                break
            if start in seen_starts:
                continue
            seen_starts.add(start)
            card = _parse_embedded(data, start)
            if card is not None:
                cards.append(card)
    return cards


def get_scene_preview(data: bytes) -> bytes | None:
    """场景卡封面 = 文件开头那张 PNG。"""
    if data[:8] != PNG_SIGNATURE:
        return None
    try:
        n = png_data_length(data, 0)
    except Exception:  # noqa: BLE001
        return None
    return data[:n]


def _chara_name(card: KoikatuCard) -> str:
    try:
        p = card.parameter or {}
        name = f"{p.get('lastname','')}{p.get('firstname','')}".strip()
        return name or p.get("nickname", "") or "(无名)"
    except Exception:  # noqa: BLE001
        return "(解析失败)"


def extract_characters_to(scene_path: str | Path, out_dir: str | Path) -> list[str]:
    """从场景卡提取所有内嵌角色，保存到 out_dir，返回保存路径列表。"""
    scene_path = Path(scene_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    data = scene_path.read_bytes()
    cards = find_embedded_characters(data)
    saved: list[str] = []
    for i, card in enumerate(cards, 1):
        name = _chara_name(card)
        safe = "".join(c for c in name if c not in r'\/:*?"<>|').strip() or f"chara{i}"
        out = out_dir / f"{scene_path.stem}_{i:02d}_{safe}.png"
        card.save(out, backup=False)
        saved.append(str(out))
    return saved


_UAR_SIG = b"com.bepis.sideloader.universalautoresolver"


def extract_scene_mod_ids(data: bytes) -> dict[str, int]:
    """提取场景级 Sideloader 依赖（studio 道具/姿势/地图等的 ModID）。

    场景里也存了 UAR：紧跟签名的是 [版本, {"info": [blob...]}]，每个 blob 再 msgpack
    解出 ModID（与角色卡同构）。无 studio mod 依赖的场景该 info 为空，返回空字典。
    """
    out: dict[str, int] = {}
    pos = data.find(_UAR_SIG)
    if pos < 0:
        return out
    up = msgpack.Unpacker(raw=False, strict_map_key=False)
    up.feed(data[pos + len(_UAR_SIG):])
    try:
        val = next(iter(up))
    except Exception:  # noqa: BLE001
        return out
    if isinstance(val, (list, tuple)) and len(val) >= 2 and isinstance(val[1], dict):
        for blob in val[1].get("info") or []:
            if isinstance(blob, (bytes, bytearray)):
                try:
                    d = msgpack.unpackb(blob, raw=False, strict_map_key=False)
                except Exception:  # noqa: BLE001
                    continue
                if isinstance(d, dict):
                    mid = d.get("ModID")
                    if isinstance(mid, str) and mid:
                        out[mid] = out.get(mid, 0) + 1
    return out


def analyze_scene(scene_path: str | Path) -> dict:
    """分析场景卡：内嵌角色名单 + 聚合的 mod 依赖（内嵌角色 + 场景级 studio 道具）。"""
    data = Path(scene_path).read_bytes()
    cards = find_embedded_characters(data)
    characters = []
    all_mods: dict[str, int] = {}
    for card in cards:
        mods = extract_mod_ids(card)
        for g, n in mods.items():
            all_mods[g] = all_mods.get(g, 0) + n
        characters.append({"name": _chara_name(card), "game": card.game, "mods": len(mods)})
    # 场景级 studio 道具依赖
    scene_mods = extract_scene_mod_ids(data)
    for g, n in scene_mods.items():
        all_mods[g] = all_mods.get(g, 0) + n
    return {
        "path": str(scene_path),
        "size": len(data),
        "character_count": len(cards),
        "characters": characters,
        "mod_ids": all_mods,
        "scene_mod_count": len(scene_mods),
    }
