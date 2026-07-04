"""多重封缄 + 恢复校验单测。

需要 pyzipper（封缄依赖）。可直接 python 运行，或用 pytest。
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import stego  # noqa: E402


def _make_tree(root: Path) -> None:
    (root / "sub").mkdir(parents=True, exist_ok=True)
    (root / "a.txt").write_text("hello 恋活", encoding="utf-8")
    (root / "sub" / "b.bin").write_bytes(bytes(range(256)) * 8)


def test_layered_roundtrip_two_layers():
    if not stego.HAVE_PYZIPPER:
        print("[SKIP] pyzipper 未安装，跳过封缄测试")
        return
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        src = d / "src"
        _make_tree(src)
        out = d / "sealed.dat"
        stego.pack_layered(src, out, ["pw1", "pw2"])
        assert out.is_file()
        assert stego.read_seal_layers(out) == 2

        restored = d / "restored"
        stego.extract_layered(out, restored, ["pw1", "pw2"])
        assert (restored / "a.txt").read_text(encoding="utf-8") == "hello 恋活"
        assert (restored / "sub" / "b.bin").read_bytes() == bytes(range(256)) * 8


def test_layered_three_layers_and_sidecar_layers():
    if not stego.HAVE_PYZIPPER:
        print("[SKIP] pyzipper 未安装")
        return
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        src = d / "src"; _make_tree(src)
        out = d / "deep.dat"
        stego.pack_layered(src, out, ["x", "y", "z"])
        # 不显式传 layers，靠伴随文件还原层数
        restored = d / "r3"
        stego.extract_layered(out, restored, ["x", "y", "z"])
        assert (restored / "a.txt").is_file()


def test_recovery_detects_corruption():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        src = d / "src"; _make_tree(src)
        zip_path = d / "plain.zip"
        stego.pack_folder(src, zip_path)
        sc = stego.write_recovery_sidecar(zip_path, redundancy=True)
        assert Path(sc).is_file()

        # 未损坏 → ok
        res = stego.verify_recovery(zip_path)
        assert res["ok"], res

        # 篡改 1 字节 → 报损
        data = bytearray(zip_path.read_bytes())
        data[len(data) // 2] ^= 0xFF
        zip_path.write_bytes(bytes(data))
        res2 = stego.verify_recovery(zip_path)
        assert not res2["ok"]
        assert res2["can_repair_tail"] is True


def test_recovery_missing_sidecar():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        f = Path(d) / "x.bin"; f.write_bytes(b"abc")
        res = stego.verify_recovery(f)
        assert not res["ok"]
        assert "缺少" in res["reason"]


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for t in tests:
        try:
            t(); print(f"[OK] {t.__name__}"); passed += 1
        except AssertionError as e:
            print(f"[FAIL] {t.__name__}: {e}"); failed += 1
        except Exception as e:  # noqa: BLE001
            import traceback; traceback.print_exc()
            print(f"[ERR] {t.__name__}: {e}"); failed += 1
    print(f"\n结果: {passed} 通过, {failed} 失败")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run())
