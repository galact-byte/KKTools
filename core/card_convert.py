"""Koikatu (KK / 1代) 与 Koikatu Sunshine (KKS / 2代) 卡片结构化互转。

原则：
- 对角色卡按块精准转换（Header / About / Parameter / Custom / Status），
  不触碰 Coordinate、KKEx（Mod 扩展数据）、封面 PNG 与脸图 PNG；
- Custom / Parameter / Status 重编码统一使用单精度 float32（use_single_float=True），
  避免 Python msgpack 默认写出 float64 导致游戏反序列化失败；
- 产出字节前自动重新解析校验，校验通过才落盘；默认另存新文件不覆写原卡。
"""

from __future__ import annotations

import io
import struct
import uuid
from pathlib import Path
from typing import Callable, Iterable, Literal

import msgpack

from core import card_scan, catalog, kk_card

TargetGame = Literal["KK", "KKS"]

KK_ATTRIBUTE_KEYS = (
    "hinnyo",
    "harapeko",
    "donkan",
    "choroi",
    "bitch",
    "mutturi",
    "dokusyo",
    "ongaku",
    "kappatu",
    "ukemi",
    "friendly",
    "kireizuki",
    "taida",
    "sinsyutu",
    "hitori",
    "undo",
    "majime",
    "likeGirls",
)

KKS_ATTRIBUTE_KEYS = (
    "harapeko",
    "choroi",
    "dokusyo",
    "ongaku",
    "okute",
    "friendly",
    "kireizuki",
    "sinsyutu",
    "hitori",
    "active",
    "majime",
    "info",
    "love",
    "talk",
    "nakama",
    "nonbiri",
    "hinnyo",
    "likeGirls",
    "bitch",
    "mutturi",
    "lonely",
    "ukemi",
    "undo",
)

_KKS_HAIR_GLOSS_COLOR = [0.8509804010391235, 0.8509804010391235, 0.8509804010391235, 1.0]


class CardConvertError(kk_card.KKCardError):
    """卡片版本互转失败异常。"""


def _pack_mp(value) -> bytes:
    """使用单精度 float32 + bin 类型编码 MessagePack，匹配 C# MessagePack 布局。"""
    return msgpack.packb(value, use_bin_type=True, use_single_float=True)


def _map_attributes(attrs: dict | None, target: TargetGame) -> dict[str, bool]:
    src = attrs if isinstance(attrs, dict) else {}
    if target == "KKS":
        shared = set(KK_ATTRIBUTE_KEYS)
        out = {k: (bool(src.get(k, False)) if k in shared else False) for k in KKS_ATTRIBUTE_KEYS}
        out["active"] = bool(src.get("kappatu", False))
        out["nonbiri"] = bool(src.get("taida", False))
        return out
    shared = set(KKS_ATTRIBUTE_KEYS)
    out = {k: (bool(src.get(k, False)) if k in shared else False) for k in KK_ATTRIBUTE_KEYS}
    out["kappatu"] = bool(src.get("active", False))
    out["taida"] = bool(src.get("nonbiri", False))
    return out


def _unpack_custom_segments(raw: bytes) -> list[dict]:
    stream = io.BytesIO(raw)
    segs: list[dict] = []
    for seg_name in ("face", "body", "hair"):
        hdr = stream.read(4)
        if len(hdr) < 4:
            raise CardConvertError(f"Custom.{seg_name} 段长度头缺失")
        seg_len = struct.unpack("<i", hdr)[0]
        if seg_len < 0:
            raise CardConvertError(f"Custom.{seg_name} 段长度异常")
        seg_bytes = stream.read(seg_len)
        if len(seg_bytes) < seg_len:
            raise CardConvertError(f"Custom.{seg_name} 段数据不完整")
        obj = msgpack.unpackb(seg_bytes, raw=False, strict_map_key=False)
        if not isinstance(obj, dict):
            raise CardConvertError(f"Custom.{seg_name} 不是合法字典结构")
        segs.append(obj)
    if stream.read(1):
        raise CardConvertError("Custom 存在未识别的尾部数据，不能安全转换")
    return segs


def _require_map(raw: bytes, name: str) -> dict:
    try:
        value = msgpack.unpackb(raw, raw=False, strict_map_key=False)
    except (ValueError, TypeError) as exc:
        raise CardConvertError(f"{name} 数据无法解析：{exc}") from exc
    if not isinstance(value, dict):
        raise CardConvertError(f"{name} 必须为字典结构")
    return value


def _validate_character(card: kk_card.KoikatuCard) -> None:
    """在输入和输出两端检查必需块与已知二进制段，不代替游戏内加载验证。"""
    for name in ("Custom", "Coordinate", "Parameter", "Status"):
        if not card.blocks.get(name):
            raise CardConvertError(f"缺少必需的 {name} 块")
    if len(card.block_order) != len(card.blocks):
        raise CardConvertError("块索引包含重复名称或与数据块不一致")
    end = 0
    for info in sorted(card.block_order, key=lambda entry: entry.pos):
        if info.pos < end or info.size < 0 or info.pos + info.size > len(card._data_blob):
            raise CardConvertError(f"{info.name} 块索引越界或重叠")
        if info.name not in card.blocks or len(card.blocks[info.name]) != info.size:
            raise CardConvertError(f"{info.name} 块长度与索引不一致")
        end = info.pos + info.size
    versions = {i.name: i.version for i in card.block_order}
    parameter = _require_map(card.blocks["Parameter"], "Parameter")
    expected = "0.0.6" if card.game == "KKS" else "0.0.5"
    if parameter.get("version") != expected or versions["Parameter"] != expected:
        raise CardConvertError(f"Parameter 版本不受支持或索引不一致，{card.game} 需要 {expected}")
    if type(parameter.get("sex")) is not int or parameter["sex"] not in (0, 1):
        raise CardConvertError("Parameter.sex 缺失或无效")
    if not isinstance(parameter.get("attribute"), dict):
        raise CardConvertError("Parameter.attribute 缺失或无效")
    status = _require_map(card.blocks["Status"], "Status")
    if status.get("version") != "0.0.0" or versions["Status"] != "0.0.0":
        raise CardConvertError("Status 版本不受支持")
    face, body, hair = _unpack_custom_segments(card.blocks["Custom"])
    if versions["Custom"] != "0.0.0":
        raise CardConvertError("Custom 块版本不受支持")
    if not isinstance(face.get("shapeValueFace"), list) or not isinstance(body.get("shapeValueBody"), list):
        raise CardConvertError("Custom 缺少面部或身体参数")
    if face.get("version") != ("0.0.3" if card.game == "KKS" else "0.0.2"):
        raise CardConvertError("Custom.face 版本不受支持")
    if hair.get("version") != ("0.0.5" if card.game == "KKS" else "0.0.4"):
        raise CardConvertError("Custom.hair 版本不受支持")
    if not isinstance(hair.get("parts"), list) or any(not isinstance(part, dict) for part in hair["parts"]):
        raise CardConvertError("Custom.hair.parts 必须为字典数组")
    try:
        coordinates = msgpack.unpackb(card.blocks["Coordinate"], raw=False, strict_map_key=False)
        if not isinstance(coordinates, list) or not coordinates:
            raise CardConvertError("Coordinate 必须包含至少一套服装数据")
        if versions["Coordinate"] != "0.0.0":
            raise CardConvertError("Coordinate 块版本不受支持")
        for slot in coordinates:
            if not isinstance(slot, bytes):
                raise CardConvertError("Coordinate 服装数据必须为二进制段")
            stream = io.BytesIO(slot)
            for part in ("clothes", "accessory", "makeup"):
                if part == "makeup" and stream.read(1) not in (b"\x00", b"\x01"):
                    raise CardConvertError("Coordinate.enableMakeup 缺失或无效")
                header = stream.read(4)
                if len(header) != 4:
                    raise CardConvertError(f"Coordinate.{part} 长度头缺失")
                size = struct.unpack("<i", header)[0]
                if size <= 0 or size > len(slot) - stream.tell():
                    raise CardConvertError(f"Coordinate.{part} 数据长度异常")
                _require_map(stream.read(size), f"Coordinate.{part}")
    except (ValueError, TypeError) as exc:
        raise CardConvertError(f"Coordinate 数据无法解析：{exc}") from exc
    if card.game == "KKS" or "About" in card.blocks:
        about = _require_map(card.blocks.get("About", b""), "About")
        if about.get("version") != "0.0.0" or versions.get("About") != "0.0.0":
            raise CardConvertError("About 版本不受支持")
        if not isinstance(about.get("userID"), str) or not isinstance(about.get("dataID"), str):
            raise CardConvertError("About 身份字段缺失或无效")


def _pack_custom_segments(segs: list[dict]) -> bytes:
    out = bytearray()
    for seg in segs:
        raw = _pack_mp(seg)
        out.extend(struct.pack("<i", len(raw)))
        out.extend(raw)
    return bytes(out)


def _set_block_version(card: kk_card.KoikatuCard, name: str, version: str) -> None:
    for bi in card.block_order:
        if bi.name == name:
            bi.version = version
            return


def _add_block_before_kkex(card: kk_card.KoikatuCard, name: str, version: str, payload: bytes) -> None:
    if name in card.blocks:
        card.blocks[name] = payload
        _set_block_version(card, name, version)
        return
    # pos 设为当前最大 pos+1 保证序列化顺序落在新段尾部，逻辑索引插在 KKEx 前
    next_pos = max((b.pos + b.size for b in card.block_order), default=0)
    info = kk_card.BlockInfo(name=name, version=version, pos=next_pos, size=len(payload))
    kkex_idx = next((i for i, b in enumerate(card.block_order) if b.name == "KKEx"), -1)
    if kkex_idx >= 0:
        card.block_order.insert(kkex_idx, info)
    else:
        card.block_order.append(info)
    card.blocks[name] = payload


def _remove_block(card: kk_card.KoikatuCard, name: str) -> None:
    card.block_order = [b for b in card.block_order if b.name != name]
    card.blocks.pop(name, None)


def _convert_character_bytes(data: bytes, target: TargetGame) -> tuple[bytes, dict]:
    card = kk_card.KoikatuCard.from_bytes(data)
    src_game = card.game
    if src_game not in ("KK", "KKS"):
        raise CardConvertError(f"暂不支持转换该游戏版本的角色卡：{card.game_name}（{card.marker}）")
    if src_game == target:
        raise CardConvertError(f"该角色卡已经是 {target} 版本，无需转换")

    _validate_character(card)
    original_thumbnail, original_face = card.thumbnail, card.face
    preserved = {name: raw for name, raw in card.blocks.items()
                 if name not in {"About", "Custom", "Parameter", "Status"}}

    # 1. Header & About
    if target == "KKS":
        card.marker = "【KoiKatuCharaSun】"
        card.version = "0.0.0"
        if "About" not in card.blocks:
            about_payload = _pack_mp(
                {
                    "version": "0.0.0",
                    "language": 0,
                    # Guid.Empty 表示未知原作者，dataID 仍标识本次生成的卡片。
                    "userID": str(uuid.UUID(int=0)),
                    "dataID": str(uuid.uuid4()),
                }
            )
            _add_block_before_kkex(card, "About", "0.0.0", about_payload)
    else:
        card.marker = "【KoiKatuChara】"
        card.version = "0.0.0"
        _remove_block(card, "About")

    # 2. Parameter
    if "Parameter" in card.blocks:
        param = msgpack.unpackb(card.blocks["Parameter"], raw=False, strict_map_key=False)
        if not isinstance(param, dict):
            raise CardConvertError("Parameter 块格式异常，无法转换")
        if target == "KKS":
            param["version"] = "0.0.6"
            param.setdefault("interest", {"answer": [-1, -1]})
            param.setdefault("exType", 0)
            if "attribute" in param:
                param["attribute"] = _map_attributes(param.get("attribute"), "KKS")
            _set_block_version(card, "Parameter", "0.0.6")
        else:
            param["version"] = "0.0.5"
            param.pop("interest", None)
            param.pop("exType", None)
            if "attribute" in param:
                param["attribute"] = _map_attributes(param.get("attribute"), "KK")
            _set_block_version(card, "Parameter", "0.0.5")
        card.blocks["Parameter"] = _pack_mp(param)

    # 3. Custom (face / body / hair 三段)
    if "Custom" in card.blocks:
        face, body, hair = _unpack_custom_segments(card.blocks["Custom"])
        if target == "KKS":
            face["version"] = "0.0.3"
            face.setdefault("hlUpX", 0.5)
            face.setdefault("hlDownX", 0.5)
            body.setdefault("typeBone", 0)
            hair["version"] = "0.0.5"
            for part in hair.get("parts") or []:
                if isinstance(part, dict):
                    part.setdefault("glossColor", list(_KKS_HAIR_GLOSS_COLOR))
                    part.setdefault("noShake", False)
        else:
            face["version"] = "0.0.2"
            face.pop("hlUpX", None)
            face.pop("hlDownX", None)
            body.pop("typeBone", None)
            hair["version"] = "0.0.4"
            for part in hair.get("parts") or []:
                if isinstance(part, dict):
                    part.pop("glossColor", None)
                    part.pop("noShake", None)
        _set_block_version(card, "Custom", "0.0.0")
        card.blocks["Custom"] = _pack_custom_segments([face, body, hair])

    # 4. Status
    if "Status" in card.blocks:
        status = msgpack.unpackb(card.blocks["Status"], raw=False, strict_map_key=False)
        if isinstance(status, dict):
            if target == "KKS":
                status["eyesBlink"] = True
                status["eyesLookPtn"] = 0
                status["mouthFixed"] = False
                status["mouthOpenMax"] = 1.0
                status["mouthPtn"] = 0
                status["neckLookPtn"] = 0
                status["visibleSonAlways"] = True
            else:
                status.pop("enableShapeHand", None)
                status.pop("shapeHandBlendValue", None)
                status.pop("shapeHandPtn", None)
                status["eyesBlink"] = False
                status["eyesLookPtn"] = 1
                status["mouthFixed"] = True
                status["mouthOpenMax"] = 0.0
                status["mouthPtn"] = 1
                status["neckLookPtn"] = 3
                status["visibleSonAlways"] = False
            card.blocks["Status"] = _pack_mp(status)

    card._dirty = True
    out_bytes = card.to_bytes()

    # 5. 写回后强制自检
    check = kk_card.KoikatuCard.from_bytes(out_bytes)
    if check.game != target:
        raise CardConvertError("转换自检失败：目标游戏标识不匹配")
    if target == "KKS" and "About" not in check.blocks:
        raise CardConvertError("转换自检失败：缺少 KKS About 块")
    if target == "KK" and "About" in check.blocks:
        raise CardConvertError("转换自检失败：未移除 About 块")
    _validate_character(check)
    if check.thumbnail != original_thumbnail or check.face != original_face:
        raise CardConvertError("转换自检失败：封面或脸图发生变化")
    for name, raw in preserved.items():
        if check.blocks.get(name) != raw:
            raise CardConvertError(f"转换自检失败：{name} 块未原样保留")

    return out_bytes, {
        "type": "character",
        "sourceGame": src_game,
        "targetGame": target,
    }


def convert_card_bytes(data: bytes, target: TargetGame) -> tuple[bytes, dict]:
    """将单张 KK / KKS 角色卡转换为目标代；独立服装卡和场景卡明确拒绝。"""
    if target not in ("KK", "KKS"):
        raise CardConvertError(f"不支持的目标版本：{target!r}（仅支持 KK / KKS）")
    kind, _, _ = kk_card.classify(data)
    if kind == "character":
        return _convert_character_bytes(data, target)
    if kind == "coordinate":
        raise CardConvertError("暂不支持可靠转换独立服装卡：KK/KKS 共用文件标记，不能通过更换标记判定或转换代数")
    if kind == "scene":
        raise CardConvertError("暂不支持转换场景卡（KK 与 KKS 场景对象和地图结构不兼容）")
    raise CardConvertError("该文件不是可转换的 KK / KKS 角色卡")


def convert_card_file(
    src: str | Path,
    target: TargetGame,
    *,
    out_dir: str | Path | None = None,
    overwrite: bool = False,
) -> dict:
    """转换单个卡片文件，默认另存新文件不覆盖原卡，并复制标签与手动作者记录。"""
    src_path = Path(src)
    if not src_path.is_file():
        raise CardConvertError(f"卡片文件不存在：{src}")
    raw = src_path.read_bytes()
    out_bytes, meta = convert_card_bytes(raw, target)

    if overwrite:
        bak = src_path.with_suffix(src_path.suffix + ".bak")
        idx = 1
        while bak.exists():
            bak = src_path.with_suffix(src_path.suffix + f".bak{idx}")
            idx += 1
        bak.write_bytes(raw)
        dst_path = src_path
        dst_path.write_bytes(out_bytes)
    else:
        folder = Path(out_dir) if out_dir else src_path.parent
        dst_name = f"{src_path.stem}_{target}{src_path.suffix}"
        dst_path = catalog.unique_path(folder, dst_name)
        dst_path.write_bytes(out_bytes)

        # 复制本地标签与手动作者覆盖（非致命）
        try:
            tags = catalog.get_tags(src_path)
            if tags:
                catalog.set_tags(dst_path, tags)
            manual_author = catalog.get_author_override(src_path)
            if manual_author:
                catalog.set_author_override(dst_path, manual_author)
        except Exception:  # noqa: BLE001
            pass

    return {
        "sourcePath": str(src_path),
        "savedPath": str(dst_path),
        **meta,
    }


def batch_convert_cards(
    sources: Iterable[str | Path],
    target: TargetGame,
    out_dir: str | Path,
    *,
    recursive: bool = False,
    progress: Callable[[int, int, str], None] | None = None,
) -> dict:
    """批量转换多个卡片文件或目录到 out_dir（不改动原文件）。"""
    if target not in ("KK", "KKS"):
        raise CardConvertError(f"不支持的目标版本：{target!r}")
    out_folder = Path(out_dir)
    out_folder.mkdir(parents=True, exist_ok=True)

    files: list[Path] = []
    seen: set[str] = set()
    for item in sources:
        p = Path(item)
        if p.is_file():
            key = str(p.resolve()).lower()
            if key not in seen:
                seen.add(key)
                files.append(p)
        elif p.is_dir():
            for png, _, _ in card_scan._collect_png_entries(p, recursive=recursive):
                key = str(png.resolve()).lower()
                if key not in seen:
                    seen.add(key)
                    files.append(png)

    total = len(files)
    converted = 0
    skipped = 0
    failed = 0
    outputs: list[str] = []
    errors: list[dict[str, str]] = []

    for i, fp in enumerate(files, 1):
        try:
            res = convert_card_file(fp, target, out_dir=out_folder, overwrite=False)
            converted += 1
            outputs.append(res["savedPath"])
        except CardConvertError as exc:
            msg = str(exc)
            if "已经是" in msg and "无需转换" in msg:
                skipped += 1
            else:
                failed += 1
                errors.append({"path": str(fp), "reason": msg})
        except Exception as exc:  # noqa: BLE001
            failed += 1
            errors.append({"path": str(fp), "reason": str(exc)})
        if progress and (i % 5 == 0 or i == total):
            progress(i, total, fp.name)

    return {
        "total": total,
        "converted": converted,
        "skipped": skipped,
        "failed": failed,
        "target": target,
        "outDir": str(out_folder),
        "outputs": outputs,
        "errors": errors[:50],
    }
