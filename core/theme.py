"""主题（皮肤）数据模型与加载。

与界面无关的纯逻辑：把一个精简的 JSON 主题（约 15 个角色令牌 + 形状 + 字体）
解析为 Theme，并派生出 QSS 模板所需的全部占位值。

设计取舍：只定义"角色化"令牌（bg / surface / text / accent ...），
而非给每个控件单独写一个颜色——派生色（hover / pressed / disabled）由色彩运算
自动算出，主题文件因此可以很短。缺失的令牌回退到 DEFAULT_TOKENS，半成品主题也能加载。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# ---- 色彩运算（纯函数，便于派生 hover/pressed/disabled） ----


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb_to_hex(rgb: tuple[float, float, float]) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(c)))) for c in rgb)


def lighten(hex_color: str, amount: float) -> str:
    """向白色靠拢 amount（0~1）。"""
    r, g, b = _hex_to_rgb(hex_color)
    return _rgb_to_hex((r + (255 - r) * amount, g + (255 - g) * amount, b + (255 - b) * amount))


def darken(hex_color: str, amount: float) -> str:
    """向黑色靠拢 amount（0~1）。"""
    r, g, b = _hex_to_rgb(hex_color)
    return _rgb_to_hex((r * (1 - amount), g * (1 - amount), b * (1 - amount)))


def mix(a: str, b: str, t: float) -> str:
    """在 a、b 之间线性插值，t=0 取 a，t=1 取 b。"""
    ar, ag, ab = _hex_to_rgb(a)
    br, bg_, bb = _hex_to_rgb(b)
    return _rgb_to_hex((ar + (br - ar) * t, ag + (bg_ - ag) * t, ab + (bb - ab) * t))


# 默认令牌 = 内置「朱红·墨」配色，作为缺失字段的兜底，保证任何主题都能补全。
# 暖墨底 + 朱红 accent —— 和风工具台，与冷紫蓝暗色调工具刻意拉开距离。
DEFAULT_TOKENS: dict[str, str] = {
    "bg": "#1a1817",          # 主背景（暖墨色）
    "bg_deep": "#121110",     # 更深底（顶栏/状态栏）
    "surface": "#24211f",     # 卡片 / 悬浮面（暖灰）
    "surface_alt": "#2c2826", # 按钮底 / 次级面
    "border": "#3d3734",      # 主描边
    "border_soft": "#2e2a27", # 弱描边
    "text": "#e6e3e0",        # 正文
    "text_strong": "#f5f2ef", # 强调文字 / 标题
    "text_muted": "#a39d97",  # 次要文字
    "text_dim": "#938d86",    # 暗淡提示
    "accent": "#c44b4b",      # 强调色（朱红）
    "selection": "#4a2020",   # 文本选区底
    "primary": "#a83a3a",     # 主操作按钮（深朱红）
    "on_primary": "#faf4f0",  # 主按钮上的文字
    "danger": "#cf5a4a",      # 危险操作（暖红）
    "success": "#5a9e6f",     # 成功 / 完成（草绿，与朱红形成冷暖反差）
}

DEFAULT_SHAPE = {"radius": 6, "radius_sm": 4, "radius_lg": 10}
DEFAULT_FONT = {
    "ui": "Microsoft YaHei UI, Microsoft YaHei, Segoe UI, sans-serif",
    "serif": "Noto Serif SC, Source Han Serif SC, Noto Serif CJK SC, SimSun, serif",
    "mono": "Consolas, JetBrains Mono, Cascadia Mono, monospace",
}


@dataclass
class Theme:
    id: str
    name: str
    variant: str = "dark"  # "dark" | "light"
    author: str = ""
    tokens: dict = field(default_factory=dict)
    shape: dict = field(default_factory=dict)
    font: dict = field(default_factory=dict)

    def flat(self) -> dict[str, str]:
        """展开为 QSS 模板所需的全部占位值（颜色派生 + 形状 + 字体）。

        模板用 string.Template 的 ${name} 语法替换——因为 QSS 自身大量使用 {} 规则块，
        无法用 str.format()。
        """
        t = dict(DEFAULT_TOKENS)
        t.update({k: v for k, v in self.tokens.items() if v})
        shape = {**DEFAULT_SHAPE, **self.shape}
        font = {**DEFAULT_FONT, **self.font}

        light = self.variant == "light"
        # 强调（hover）与减弱（pressed）随明暗变体反向：暗色调亮、亮色调暗。
        emph = (lambda c, a: darken(c, a)) if light else (lambda c, a: lighten(c, a))
        deemph = (lambda c, a: lighten(c, a)) if light else (lambda c, a: darken(c, a))

        bg = t["bg"]
        surface = t["surface"]
        surface_alt = t.get("surface_alt") or mix(bg, surface, 0.6)
        button_bg = t.get("button_bg") or surface_alt
        accent = t["accent"]
        primary = t["primary"]
        on_primary = t.get("on_primary", "#ffffff")
        danger = t["danger"]

        return {
            # 字体
            "font_ui": font["ui"],
            "font_serif": font["serif"],
            "font_mono": font["mono"],
            # 形状
            "radius": str(shape["radius"]),
            "radius_sm": str(shape["radius_sm"]),
            "radius_lg": str(shape["radius_lg"]),
            # 面
            "bg": bg,
            "bg_deep": t["bg_deep"],
            "surface": surface,
            "surface_alt": surface_alt,
            # 输入框底：要在卡片(surface)里干净可辨，而非沿用页面底色。
            # 浅色=比白卡略沉的灰白；深色=比卡片更暗的内凹底。
            "input_bg": t.get("input_bg") or (darken(surface, 0.05) if light else darken(bg, 0.10)),
            # 悬浮/选中面：比卡片略亮(深色)或略沉(浅色)
            "surface_hover": t.get("surface_hover") or (darken(surface, 0.04) if light else lighten(surface, 0.05)),
            # 描边
            "border": t["border"],
            "border_soft": t["border_soft"],
            # 卡片描边：取主描边与弱描边之间，让卡片轮廓清晰但不抢戏（浮起感关键）
            "card_border": t.get("card_border") or mix(t["border_soft"], t["border"], 0.65),
            "border_focus": accent,
            # 文字
            "text": t["text"],
            "text_strong": t["text_strong"],
            "text_muted": t["text_muted"],
            "text_dim": t["text_dim"],
            "text_disabled": t.get("text_disabled") or mix(t["text_dim"], bg, 0.5),
            # 普通按钮
            "button_bg": button_bg,
            "button_bg_hover": emph(button_bg, 0.07),
            "button_bg_press": deemph(button_bg, 0.05),
            # 强调
            "accent": accent,
            "accent_hover": t.get("accent_hover") or emph(accent, 0.10),
            "selection": t["selection"],
            "selection_soft": mix(t["selection"], bg, 0.45),
            # 主操作按钮
            "primary": primary,
            "primary_hover": emph(primary, 0.08),
            "primary_press": deemph(primary, 0.08),
            "on_primary": on_primary,
            "primary_disabled_bg": mix(primary, bg, 0.72),
            "primary_disabled_text": mix(on_primary, bg, 0.55),
            # 危险
            "danger": danger,
            "danger_bg_hover": mix(danger, bg, 0.82),
            # 进度 / 勾选（沿用主色，贯彻"单一强调"理念）
            "success": t["success"],
        }


def from_dict(data: dict) -> Theme:
    """从已解析的 dict 构造 Theme，对脏数据宽容（缺字段走默认）。"""
    return Theme(
        id=str(data.get("id") or "unnamed"),
        name=str(data.get("name") or data.get("id") or "未命名"),
        variant="light" if str(data.get("variant", "dark")).lower() == "light" else "dark",
        author=str(data.get("author", "")),
        tokens=dict(data.get("tokens", {})),
        shape=dict(data.get("shape", {})),
        font=dict(data.get("font", {})),
    )


def load_theme(path: str | Path) -> Theme:
    """从 JSON 文件加载一个主题。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("主题文件必须是 JSON 对象")
    return from_dict(data)


def builtin_dir() -> Path:
    """内置主题目录：<project>/ui/themes。"""
    return Path(__file__).resolve().parent.parent / "ui" / "themes"


def list_themes(extra_dirs: list[str | Path] | None = None) -> list[Theme]:
    """扫描内置 + 额外目录下的 *.json 主题。同 id 时后扫描到的覆盖（用户可覆盖内置）。

    损坏的单个主题文件被跳过，不影响其它主题加载。
    """
    by_id: dict[str, Theme] = {}
    dirs: list[Path] = [builtin_dir()]
    for d in extra_dirs or []:
        if d:
            dirs.append(Path(d))
    for d in dirs:
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.json")):
            try:
                th = load_theme(f)
            except (json.JSONDecodeError, OSError, ValueError):
                continue  # 坏主题跳过，绝不让一个文件拖垮整个列表
            by_id[th.id] = th
    return list(by_id.values())


def find_theme(theme_id: str, extra_dirs: list[str | Path] | None = None) -> Theme | None:
    for th in list_themes(extra_dirs):
        if th.id == theme_id:
            return th
    return None
