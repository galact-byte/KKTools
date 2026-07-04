"""分享包"排除参考清单 mod"逻辑单测（monkeypatch 读卡，专测排除分支）。"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import share  # noqa: E402
from core.mod_index import ModIndex, ModEntry  # noqa: E402


def test_exclude_guids_skips_mods():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        # 造一张假卡文件（只需存在以便复制）
        card = d / "chara.png"; card.write_bytes(b"\x89PNG fake")
        # 造两个本地存在的 zipmod（g1/g2），g3 仓库没有
        modg1 = d / "g1.zipmod"; modg1.write_bytes(b"zip1")
        modg2 = d / "g2.zipmod"; modg2.write_bytes(b"zip2")
        index = ModIndex()
        index.entries["g1"] = ModEntry(guid="g1", path=str(modg1))
        index.entries["g2"] = ModEntry(guid="g2", path=str(modg2))

        # monkeypatch：让这张卡“依赖” g1/g2/g3
        orig_extract = share.extract_mod_ids
        orig_load = share.KoikatuCard.load
        share.extract_mod_ids = lambda c: {"g1": 1, "g2": 1, "g3": 1}
        share.KoikatuCard.load = classmethod(lambda cls, p: None)
        try:
            out = d / "pkg"
            report = share.build_share_package(
                [str(card)], index, out, group_by_char=False, exclude_guids={"g2"})
        finally:
            share.extract_mod_ids = orig_extract
            share.KoikatuCard.load = orig_load

        c = report["cards"][0]
        assert c["copied"] == 1, c          # g1 打入
        assert c["excluded"] == 1, c        # g2 被排除
        assert c["missing"] == ["g3"], c    # g3 仓库没有
        assert report["excluded_mods"] == ["g2"]
        # g2 的文件不应出现在分享包里
        assert not (out / "mods" / "g2.zipmod").exists()
        assert (out / "mods" / "g1.zipmod").exists()


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
