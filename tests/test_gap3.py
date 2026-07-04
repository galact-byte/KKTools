"""Gap3 单测：载体素材池随机抽取 + Mod 清单导出 zip。"""

import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import stego  # noqa: E402
from core.mod_index import ModIndex, ModEntry  # noqa: E402


def test_pick_carrier_from_pool():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "a.mp4").write_bytes(b"v1")
        (d / "b.jpg").write_bytes(b"v2")
        (d / "note.txt").write_text("x")  # 非载体后缀，优先不选
        picked = stego.pick_carrier_from_pool(d)
        assert Path(picked).suffix.lower() in (".mp4", ".jpg")
        assert Path(picked).is_file()


def test_pick_carrier_empty_pool_raises():
    with tempfile.TemporaryDirectory() as d:
        try:
            stego.pick_carrier_from_pool(d)
            assert False, "空池应报错"
        except FileNotFoundError:
            pass


def test_export_as_zip():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        m1 = d / "g1.zipmod"; m1.write_bytes(b"mod1")
        m2 = d / "g2.zipmod"; m2.write_bytes(b"mod2")
        index = ModIndex()
        index.entries["g1"] = ModEntry(guid="g1", path=str(m1))
        index.entries["g2"] = ModEntry(guid="g2", path=str(m2))
        out = d / "export.zip"
        # 清单含 g1/g2/g3，g3 仓库没有
        from core import mod_index as MI
        added, skipped = MI.export_as_zip(["g1", "g2", "g3"], index, out)
        assert added == 2 and skipped == 1, (added, skipped)
        with zipfile.ZipFile(out) as zf:
            names = set(zf.namelist())
        assert names == {"g1.zipmod", "g2.zipmod"}, names


def _run() -> int:
    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print(f"[OK] {name}"); passed += 1
            except AssertionError as e:
                print(f"[FAIL] {name}: {e}"); failed += 1
            except Exception as e:  # noqa: BLE001
                import traceback; traceback.print_exc(); print(f"[ERR] {name}: {e}"); failed += 1
    print(f"\n结果: {passed} 通过, {failed} 失败")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run())
