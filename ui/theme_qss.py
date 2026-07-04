"""把 Theme 渲染成 Qt 样式表（QSS）。

读取 ui/style.qss.tmpl（${令牌} 占位），用 string.Template 注入 theme.flat()。
之所以不用 str.format：QSS 大量使用 {} 作规则块，会与 format 冲突；${} 则安全。

下拉/菜单箭头：QSS 的 CSS 三角(border trick)在部分平台会渲染成黑方块，
故改为按主题色生成一个 SVG 箭头落盘，再用 image: url() 引用——稳定且随主题着色。
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from string import Template

from core.theme import Theme

_TEMPLATE_PATH = Path(__file__).resolve().parent / "style.qss.tmpl"
_CACHE_DIR = Path(tempfile.gettempdir()) / "kktools_ui"

_CHEVRON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12">'
    '<path d="M2.5 4.5 L6 8 L9.5 4.5" fill="none" stroke="{color}" '
    'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'
)


def template_text() -> str:
    return _TEMPLATE_PATH.read_text(encoding="utf-8")


def _chevron_url(color: str) -> str:
    """按颜色生成（缓存）一个向下箭头 SVG，返回 QSS url() 用的正斜杠绝对路径。"""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _CACHE_DIR / f"chevron_{color.lstrip('#')}.svg"
    if not path.exists():
        path.write_text(_CHEVRON_SVG.format(color=color), encoding="utf-8")
    return path.as_posix()


def build_qss(theme: Theme) -> str:
    """渲染主题为完整 QSS 字符串。

    使用 substitute（而非 safe_substitute）：缺占位符会抛 KeyError，
    便于在测试中第一时间发现主题/模板不匹配，而不是悄悄留下 ${xxx}。
    """
    values = theme.flat()
    values["arrow_icon"] = _chevron_url(values["text_muted"])
    return Template(template_text()).substitute(values)
