"""库身份 + 清单对账单测。隔离 config 路径，避免污染真实配置。"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import settings  # noqa: E402


def _isolate_config(tmp: Path) -> None:
    """把 settings 的配置路径指到临时文件。"""
    settings._CONFIG_PATH = tmp / "config.json"


def test_identity_stable_and_generated():
    with tempfile.TemporaryDirectory() as d:
        _isolate_config(Path(d))
        from core import identity
        a = identity.get_identity()
        assert a["holder_id"].startswith("hld_")
        assert a["library_id"].startswith("lib_")
        assert a["display_name"]
        # 再次取应完全一致（持久化、稳定）
        b = identity.get_identity()
        assert a == b
        # 改展示名后 id 不变
        c = identity.set_display_name("阿白")
        assert c["display_name"] == "阿白"
        assert c["holder_id"] == a["holder_id"]


def test_manifest_export_and_reconcile():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        _isolate_config(d)
        from core import manifest
        from core.mod_index import ModIndex, ModEntry

        idx_mine = ModIndex()
        for g in ["aaa", "bbb", "ccc"]:
            idx_mine.entries[g] = ModEntry(guid=g, name=g.upper())
        ident = {"holder_id": "hld_x", "library_id": "lib_x", "display_name": "我"}
        out = d / "mine.kkmanifest.json"
        n = manifest.export_manifest(idx_mine, out, ident)
        assert n == 3

        mine = manifest.load_manifest(out)
        assert mine["identity"]["holder_id"] == "hld_x"
        assert mine["guids"] == ["aaa", "bbb", "ccc"]

        theirs = {"identity": {"display_name": "对方"}, "guids": ["bbb", "ccc", "ddd", "eee"]}
        rec = manifest.reconcile_manifests(mine, theirs)
        assert rec["mine_only"] == ["aaa"]            # 我有他没有 → 可补给对方
        assert rec["theirs_only"] == ["ddd", "eee"]   # 他有我没有 → 可索取
        assert rec["both"] == 2
        assert rec["theirs_identity"]["display_name"] == "对方"


def test_load_manifest_falls_back_to_plain_guid_list():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        f = d / "plain.txt"
        f.write_text("# 标题\naaa\nbbb | 名字\n- ccc\n\n", encoding="utf-8")
        from core import manifest
        m = manifest.load_manifest(f)
        assert set(m["guids"]) == {"aaa", "bbb", "ccc"}


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
