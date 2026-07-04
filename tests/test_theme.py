"""主题引擎单测：加载内置主题、QSS 生成无遗漏占位符、缺字段回退、色彩运算。

可直接 `python tests/test_theme.py` 运行，或用 pytest。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import theme as T  # noqa: E402
from ui import theme_qss  # noqa: E402


def test_builtin_themes_load():
    themes = T.list_themes()
    ids = {t.id for t in themes}
    assert {"ink_dark", "ink_light", "indigo_dark", "pine_dark",
            "sakura_dark", "amber_dark", "seiji_dark", "snow_light"} <= ids, ids
    assert T.find_theme("ink_dark") is not None


def _relative_luminance(hex_color: str) -> float:
    def chan(c: int) -> float:
        x = c / 255
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    r, g, b = T._hex_to_rgb(hex_color)
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def _contrast(fg: str, bg: str) -> float:
    a, b = _relative_luminance(fg), _relative_luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def test_all_themes_meet_wcag_contrast():
    """所有内置主题：正文/提示/主按钮文字对比 ≥4.5:1（WCAG AA），强调元素 ≥3:1。"""
    text_pairs = [("text", "bg"), ("text", "surface"),
                  ("text_muted", "bg"), ("text_muted", "surface"),
                  ("text_dim", "bg"), ("text_dim", "surface"),
                  ("on_primary", "primary")]
    ui_pairs = [("accent", "bg"), ("accent", "surface"), ("danger", "surface")]
    for th in T.list_themes():
        f = th.flat()
        for fg, bg in text_pairs:
            r = _contrast(f[fg], f[bg])
            assert r >= 4.5, f"{th.id}: {fg}/{bg} 仅 {r:.2f}:1 (<4.5)"
        for fg, bg in ui_pairs:
            r = _contrast(f[fg], f[bg])
            assert r >= 3.0, f"{th.id}: {fg}/{bg} 仅 {r:.2f}:1 (<3.0)"


def test_qss_has_no_unsubstituted_placeholder():
    for th in T.list_themes():
        qss = theme_qss.build_qss(th)
        assert "${" not in qss, f"{th.id} 残留未替换占位符"
        # 基本健全性：包含若干关键选择器与注入后的颜色
        assert "QPushButton" in qss
        assert th.flat()["bg"] in qss


def test_partial_theme_falls_back():
    # 只给极少量令牌，其余应回退默认且仍能渲染
    th = T.from_dict({"id": "tiny", "name": "tiny", "tokens": {"accent": "#123456"}})
    flat = th.flat()
    assert flat["accent"] == "#123456"
    assert flat["bg"] == T.DEFAULT_TOKENS["bg"]  # 回退
    qss = theme_qss.build_qss(th)
    assert "${" not in qss


def test_color_math():
    assert T.lighten("#000000", 0.5) == "#808080"
    assert T.darken("#ffffff", 0.5) == "#808080"
    assert T.mix("#000000", "#ffffff", 0.5) == "#808080"
    # 3 位简写
    assert T.lighten("#000", 0.0) == "#000000"


def test_light_variant_hover_direction():
    # 亮色变体下，按钮 hover 应比底色更深（调暗）
    th = T.from_dict({"id": "lt", "name": "lt", "variant": "light",
                      "tokens": {"surface_alt": "#cccccc"}})
    flat = th.flat()
    base = T._hex_to_rgb(flat["button_bg"])[0]
    hov = T._hex_to_rgb(flat["button_bg_hover"])[0]
    assert hov < base, "亮色主题 hover 应更深"


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"[OK] {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {t.__name__}: {e}")
            failed += 1
        except Exception as e:  # noqa: BLE001
            print(f"[ERR] {t.__name__}: {e}")
            failed += 1
    print(f"\n结果: {passed} 通过, {failed} 失败")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run())
