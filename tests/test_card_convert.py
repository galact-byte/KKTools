"""KK (1代) ↔ KKS (2代) 卡片互转的 TDD 回归测试。"""

from __future__ import annotations

import io
import struct
import time
from pathlib import Path

import msgpack
import pytest
from PIL import Image

from core import card_convert, catalog, kk_card, settings
from web_bridge import KKToolsBridge


def _make_png(color=(100, 150, 220)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 88), color).save(buf, format="PNG")
    return buf.getvalue()


def _pack_custom(face: dict, body: dict, hair: dict) -> bytes:
    out = bytearray()
    for seg in (face, body, hair):
        raw = msgpack.packb(seg, use_bin_type=True, use_single_float=True)
        out.extend(struct.pack("<i", len(raw)))
        out.extend(raw)
    return bytes(out)


def _unpack_custom(raw: bytes) -> tuple[dict, dict, dict, list[bytes]]:
    s = io.BytesIO(raw)
    segs = []
    raws = []
    for _ in range(3):
        n = struct.unpack("<i", s.read(4))[0]
        b = s.read(n)
        raws.append(b)
        segs.append(msgpack.unpackb(b, raw=False, strict_map_key=False))
    return segs[0], segs[1], segs[2], raws


def _make_full_kk_card(*, with_kkex: bool = True) -> bytes:
    thumb = _make_png((80, 140, 220))
    face_png = _make_png((220, 140, 160))
    custom_raw = _pack_custom(
        face={"version": "0.0.2", "shapeValueFace": [0.5, 0.25], "headId": 0},
        body={"version": "0.0.2", "shapeValueBody": [0.4, 0.6], "bustSoftness": 0.5},
        hair={"version": "0.0.4", "parts": [{"id": 1, "baseColor": [0.2, 0.3, 0.4, 1.0]}]},
    )
    coord_slot = bytearray()
    for part in ({"version": "0.0.1", "parts": []}, {"version": "0.0.0", "parts": []}):
        raw = msgpack.packb(part, use_bin_type=True)
        coord_slot.extend(struct.pack("<i", len(raw)))
        coord_slot.extend(raw)
    coord_slot.append(0)
    makeup = msgpack.packb({"version": "0.0.0"}, use_bin_type=True)
    coord_slot.extend(struct.pack("<i", len(makeup)))
    coord_slot.extend(makeup)
    coord_raw = msgpack.packb([bytes(coord_slot)], use_bin_type=True)
    param = {
        "version": "0.0.5",
        "sex": 1,
        "lastname": "天童",
        "firstname": "凯伊",
        "nickname": "Kei",
        "personality": 8,
        "bloodType": 1,
        "birthMonth": 3,
        "birthDay": 25,
        "clubActivities": 3,
        "voiceRate": 0.5,
        "awnser": {"animal": True},
        "denial": {"kiss": False},
        "attribute": {
            "hinnyo": False,
            "harapeko": False,
            "donkan": True,
            "choroi": False,
            "bitch": False,
            "mutturi": False,
            "dokusyo": True,
            "ongaku": False,
            "kappatu": True,
            "ukemi": False,
            "friendly": False,
            "kireizuki": True,
            "taida": True,
            "sinsyutu": False,
            "hitori": False,
            "undo": False,
            "majime": True,
            "likeGirls": False,
        },
    }
    status = {
        "version": "0.0.0",
        "coordinateType": 0,
        "eyesBlink": False,
        "eyesLookPtn": 1,
        "mouthFixed": True,
        "mouthOpenMax": 0.0,
        "mouthPtn": 1,
        "neckLookPtn": 3,
        "visibleSonAlways": False,
    }
    blocks: list[tuple[str, str, bytes]] = [
        ("Custom", "0.0.0", custom_raw),
        ("Coordinate", "0.0.0", coord_raw),
        ("Parameter", "0.0.5", msgpack.packb(param, use_bin_type=True, use_single_float=True)),
        ("Status", "0.0.0", msgpack.packb(status, use_bin_type=True, use_single_float=True)),
    ]
    if with_kkex:
        kkex = {
            "com.bepis.sideloader.universalautoresolver": [
                1,
                {"info": [msgpack.packb({"ModID": "demo.mod.pack"}, use_bin_type=True)]},
            ],
            "marco.authordata": [1, {"Authors": msgpack.packb(["MillenniumMaker"], use_bin_type=True)}],
        }
        blocks.append(("KKEx", "3", msgpack.packb(kkex, use_bin_type=True)))

    blob = bytearray()
    lst = []
    for name, ver, raw in blocks:
        pos = len(blob)
        blob.extend(raw)
        lst.append({"name": name, "version": ver, "pos": pos, "size": len(raw)})

    lst_raw = msgpack.packb({"lstInfo": lst}, use_bin_type=True)
    out = io.BytesIO()
    out.write(thumb)
    out.write(struct.pack("<i", 100))
    out.write(kk_card.write_cs_string("【KoiKatuChara】"))
    out.write(kk_card.write_cs_string("0.0.0"))
    out.write(struct.pack("<i", len(face_png)))
    out.write(face_png)
    out.write(struct.pack("<i", len(lst_raw)))
    out.write(lst_raw)
    out.write(struct.pack("<q", len(blob)))
    out.write(blob)
    return out.getvalue()


def _make_coordinate_bytes(marker: str = "【KoiKatuClothes】") -> bytes:
    out = io.BytesIO()
    out.write(_make_png((180, 120, 200)))
    out.write(struct.pack("<i", 100))
    out.write(kk_card.write_cs_string(marker))
    out.write(kk_card.write_cs_string("0.0.0"))
    out.write(kk_card.write_cs_string("uniform"))
    payload = b"\x01\x02\x03\x04payload-bytes"
    out.write(struct.pack("<i", len(payload)))
    out.write(payload)
    return out.getvalue()


def _wait_task(bridge: KKToolsBridge, task_id: str, timeout: float = 10.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        st = bridge.poll_task(task_id)["data"]
        if st["status"] in ("done", "error", "cancelled"):
            return st
        time.sleep(0.03)
    raise AssertionError("任务超时")


def test_kk_to_kks_and_roundtrip_back_to_kk_preserves_float32_and_blocks():
    kk_raw = _make_full_kk_card(with_kkex=True)
    orig = kk_card.KoikatuCard.from_bytes(kk_raw)

    # 1. KK -> KKS
    kks_raw, meta = card_convert.convert_card_bytes(kk_raw, "KKS")
    assert meta["sourceGame"] == "KK"
    assert meta["targetGame"] == "KKS"

    kks = kk_card.KoikatuCard.from_bytes(kks_raw)
    assert kks.marker == "【KoiKatuCharaSun】"
    assert kks.game == "KKS"
    assert kks.thumbnail == orig.thumbnail
    assert kks.face == orig.face
    # Coordinate 与 KKEx 字节级原样保留
    assert kks.blocks["Coordinate"] == orig.blocks["Coordinate"]
    assert kks.blocks["KKEx"] == orig.blocks["KKEx"]
    assert kk_card.extract_mod_ids(kks, strict=True) == {"demo.mod.pack": 1}
    # About 插入在 KKEx 之前
    assert "About" in kks.blocks
    assert kks.block_names.index("About") < kks.block_names.index("KKEx")
    about = kks.get_block_dict("About")
    assert about["version"] == "0.0.0"
    assert about["userID"] and about["dataID"]
    # Parameter 升级与 attribute 映射
    param_info = next(b for b in kks.block_order if b.name == "Parameter")
    assert param_info.version == "0.0.6"
    kks_param = kks.parameter
    assert kks_param["version"] == "0.0.6"
    assert kks_param["interest"] == {"answer": [-1, -1]}
    assert kks_param["attribute"]["active"] is True
    assert kks_param["attribute"]["nonbiri"] is True
    assert kks_param["attribute"]["dokusyo"] is True
    assert "kappatu" not in kks_param["attribute"]
    # Custom 升级且浮点必须保持 float32 (0xCA)，不得出现 float64 (0xCB)
    face, body, hair, custom_raws = _unpack_custom(kks.blocks["Custom"])
    assert face["version"] == "0.0.3"
    assert face["hlUpX"] == pytest.approx(0.5)
    assert face["hlDownX"] == pytest.approx(0.5)
    assert "typeBone" in body
    assert hair["version"] == "0.0.5"
    assert len(hair["parts"][0]["glossColor"]) == 4
    assert all(b"\xcb" not in seg for seg in custom_raws)
    assert b"\xca" in custom_raws[0]

    # 2. KKS -> KK 逆转
    back_raw, meta2 = card_convert.convert_card_bytes(kks_raw, "KK")
    assert meta2["sourceGame"] == "KKS"
    assert meta2["targetGame"] == "KK"
    back = kk_card.KoikatuCard.from_bytes(back_raw)
    assert back.marker == "【KoiKatuChara】"
    assert back.game == "KK"
    assert "About" not in back.blocks
    back_param_info = next(b for b in back.block_order if b.name == "Parameter")
    assert back_param_info.version == "0.0.5"
    back_param = back.parameter
    assert back_param["version"] == "0.0.5"
    assert "interest" not in back_param
    assert "exType" not in back_param
    assert back_param["attribute"]["kappatu"] is True
    assert back_param["attribute"]["taida"] is True
    assert back_param["attribute"]["dokusyo"] is True
    b_face, b_body, b_hair, b_raws = _unpack_custom(back.blocks["Custom"])
    assert b_face["version"] == "0.0.2"
    assert "hlUpX" not in b_face
    assert "typeBone" not in b_body
    assert b_hair["version"] == "0.0.4"
    assert "glossColor" not in b_hair["parts"][0]
    assert all(b"\xcb" not in seg for seg in b_raws)
    assert back.blocks["Coordinate"] == orig.blocks["Coordinate"]
    assert back.blocks["KKEx"] == orig.blocks["KKEx"]


def test_coordinate_header_conversion_and_error_guards():
    # KK 与 KKS 的真实独立服装卡共用此头，不能凭改 marker 宣称完成转换。
    shared_coordinate = _make_coordinate_bytes("【KoiKatuClothes】")
    assert kk_card.classify(shared_coordinate)[:2] == ("coordinate", "?")
    for target in ("KK", "KKS"):
        with pytest.raises(card_convert.CardConvertError, match="服装卡"):
            card_convert.convert_card_bytes(shared_coordinate, target)

    # 已是目标版本报错
    with pytest.raises(card_convert.CardConvertError):
        card_convert.convert_card_bytes(_make_full_kk_card(), "KK")

    # 非卡片 PNG 拒绝转换
    with pytest.raises(card_convert.CardConvertError):
        card_convert.convert_card_bytes(_make_png(), "KKS")

    # 场景卡拒绝转换
    scene_bytes = _make_png() + b"KStudio\x00dummy"
    with pytest.raises(card_convert.CardConvertError):
        card_convert.convert_card_bytes(scene_bytes, "KKS")


def test_convert_file_copies_metadata_and_bridge_single_and_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "app_dir", lambda: tmp_path / "appdata")
    monkeypatch.setattr(settings, "_CONFIG_PATH", tmp_path / "appdata" / "config.json")
    (tmp_path / "appdata").mkdir(parents=True, exist_ok=True)

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    c1 = src_dir / "kei_kk.png"
    c1.write_bytes(_make_full_kk_card())
    catalog.set_tags(c1, ["千年", "女仆"])
    catalog.set_author_override(c1, "千夏社")

    bridge = KKToolsBridge()
    # 单张转换：默认另存新文件，原卡不动，且复制标签与手动作者
    res = bridge.convert_card(str(c1), "KKS")
    assert res["ok"] is True, res
    out_single = Path(res["data"]["savedPath"])
    assert out_single.is_file()
    assert out_single != c1
    assert kk_card.KoikatuCard.load(out_single).game == "KKS"
    assert kk_card.KoikatuCard.load(c1).game == "KK"
    assert catalog.get_tags(out_single) == ["千年", "女仆"]
    assert catalog.get_author_override(out_single) == "千夏社"

    # 批量目录转换（含已是目标版本跳过与坏文件失败计数）
    (src_dir / "plain.png").write_bytes(_make_png())
    out_batch = tmp_path / "batch_out"
    start = bridge.start_batch_convert_cards(
        {"sources": [str(src_dir)], "target": "KKS", "outDir": str(out_batch), "recursive": False}
    )
    assert start["ok"] is True
    st = _wait_task(bridge, start["data"]["taskId"])
    assert st["status"] == "done", st
    rep = st["result"]
    assert rep["converted"] == 1
    assert rep["skipped"] == 1  # out_single 已经是 KKS
    assert rep["failed"] == 1   # plain.png 非角色/服装卡
    assert len(rep["outputs"]) == 1
    assert kk_card.KoikatuCard.load(rep["outputs"][0]).game == "KKS"
