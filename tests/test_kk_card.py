"""卡片解析内核的往返测试。

关键点：合成卡片时**手工按格式规范拼字节**（而不是用 KoikatuCard.to_bytes），
这样才能真正验证解析逻辑符合恋活卡片的二进制布局，而不是自己跟自己对账。
"""

import io
import struct
import sys
from pathlib import Path

import msgpack

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.kk_card import (  # noqa: E402
    KoikatuCard,
    is_character_card,
    png_data_length,
    write_cs_string,
)


def _make_png(color: tuple[int, int, int], size: tuple[int, int]) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _build_synthetic_card() -> tuple[bytes, dict]:
    """手工拼一张最小但合法的 KK 角色卡，返回 (字节, 期望的 Parameter 字典)。"""
    thumbnail = _make_png((180, 80, 160), (10, 12))   # 缩略图
    face = _make_png((40, 40, 60), (16, 16))          # 脸图

    parameter = {
        "lastname": "",
        "firstname": "Ishtar",
        "nickname": "天の女神",
        "sex": 1,
        "personality": 2,
        "bloodType": 2,
        "birthMonth": 2,
        "birthDay": 3,
        "clubActivities": "游泳部",
    }
    custom = {"some": "blob", "n": 123}

    blk_param = msgpack.packb(parameter, use_bin_type=True)
    blk_custom = msgpack.packb(custom, use_bin_type=True)

    # 数据区：两个块拼接，记录各自 pos/size
    data = blk_custom + blk_param
    lstinfo = {
        "lstInfo": [
            {"name": "Custom", "version": "0.0.0", "pos": 0, "size": len(blk_custom)},
            {
                "name": "Parameter",
                "version": "0.0.0",
                "pos": len(blk_custom),
                "size": len(blk_param),
            },
        ]
    }
    lstinfo_raw = msgpack.packb(lstinfo, use_bin_type=True)

    out = io.BytesIO()
    out.write(thumbnail)
    out.write(struct.pack("<i", 100))                 # productNo
    out.write(write_cs_string("【KoiKatuChara】"))     # marker
    out.write(write_cs_string("0.0.0"))               # version
    out.write(struct.pack("<i", len(face)))
    out.write(face)
    out.write(struct.pack("<i", len(lstinfo_raw)))
    out.write(lstinfo_raw)
    out.write(struct.pack("<q", len(data)))
    out.write(data)
    return out.getvalue(), parameter


def test_png_length_walks_chunks():
    png = _make_png((1, 2, 3), (8, 8))
    # 后面接一坨垃圾，应当只返回 PNG 本体长度
    assert png_data_length(png + b"GARBAGE", 0) == len(png)


def test_parse_synthetic_card():
    raw, expected_param = _build_synthetic_card()
    assert is_character_card(raw)

    card = KoikatuCard.from_bytes(raw)
    assert card.marker == "【KoiKatuChara】"
    assert card.game == "KK"
    assert card.product_no == 100
    assert card.block_names == ["Custom", "Parameter"]

    param = card.parameter
    assert param["firstname"] == "Ishtar"
    assert param["nickname"] == "天の女神"
    assert param["clubActivities"] == "游泳部"
    assert param == expected_param


def test_roundtrip_byte_exact_when_untouched():
    """没改任何东西时，重建的字节应与原始完全一致。"""
    raw, _ = _build_synthetic_card()
    card = KoikatuCard.from_bytes(raw)
    assert card.to_bytes() == raw


def test_edit_parameter_persists_and_preserves_others(tmp_path):
    raw, _ = _build_synthetic_card()
    card = KoikatuCard.from_bytes(raw)
    original_custom = card.blocks["Custom"]

    card.update_parameter({"firstname": "Saber", "nickname": "剑之骑士"})
    out = tmp_path / "edited.png"
    card.save(out, backup=False)

    reloaded = KoikatuCard.load(out)
    assert reloaded.parameter["firstname"] == "Saber"
    assert reloaded.parameter["nickname"] == "剑之骑士"
    # 其它字段保持
    assert reloaded.parameter["clubActivities"] == "游泳部"
    # Custom 块字节级未变
    assert reloaded.blocks["Custom"] == original_custom


def test_update_parameter_ignores_unknown_keys():
    raw, _ = _build_synthetic_card()
    card = KoikatuCard.from_bytes(raw)
    card.update_parameter({"firstname": "X", "this_key_does_not_exist": 999})
    assert "this_key_does_not_exist" not in card.parameter
    assert card.parameter["firstname"] == "X"


def test_save_creates_backup(tmp_path):
    raw, _ = _build_synthetic_card()
    target = tmp_path / "card.png"
    target.write_bytes(raw)

    card = KoikatuCard.from_bytes(raw)
    card.update_parameter({"firstname": "Backup"})
    card.save(target, backup=True)

    assert (tmp_path / "card.png.bak").exists()
    assert KoikatuCard.load(tmp_path / "card.png.bak").parameter["firstname"] == "Ishtar"
    assert KoikatuCard.load(target).parameter["firstname"] == "Backup"


def test_rejects_non_card():
    assert not is_character_card(b"not a png at all")
    assert not is_character_card(_make_png((0, 0, 0), (4, 4)))  # 纯 PNG 不是卡片


if __name__ == "__main__":
    import traceback

    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    failed = 0
    import tempfile

    for fn in funcs:
        try:
            if "tmp_path" in fn.__code__.co_varnames[: fn.__code__.co_argcount]:
                with tempfile.TemporaryDirectory() as d:
                    fn(Path(d))
            else:
                fn()
            print(f"[OK] {fn.__name__}")
            passed += 1
        except Exception:  # noqa: BLE001
            print(f"[X]  {fn.__name__}")
            traceback.print_exc()
            failed += 1
    print(f"\n结果: {passed} 通过, {failed} 失败")
    sys.exit(1 if failed else 0)
