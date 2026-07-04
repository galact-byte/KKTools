"""SVG 图标按主题色着色。

方案：把 SVG 渲染到透明 pixmap，再用 SourceIn 合成填充目标颜色——
这样图标文件本身用什么颜色都无所谓（只取其形状/alpha），着色完全由主题驱动。
找不到文件或渲染失败时返回空 QIcon（调用方据此回退纯文字），绝不抛错。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

ICON_DIR = Path(__file__).resolve().parent / "icons"


@lru_cache(maxsize=256)
def _tinted_pixmap(path_str: str, color: str, w: int, h: int) -> QPixmap:
    pm = QPixmap(w, h)
    pm.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(path_str)
    if not renderer.isValid():
        return pm  # 空（全透明），上层据此回退
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(p)
    # 用目标色按 SourceIn 覆盖：只在原图不透明处着色
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(pm.rect(), QColor(color))
    p.end()
    return pm


def tint_icon(name: str, color: str, size: int = 18) -> QIcon:
    """按主题色生成图标。name 是 icons/ 下不带扩展名的文件名。"""
    path = ICON_DIR / f"{name}.svg"
    if not path.is_file():
        return QIcon()
    pm = _tinted_pixmap(str(path), color, size, size)
    if pm.isNull():
        return QIcon()
    return QIcon(pm)


def tint_pixmap(name: str, color: str, size: int = 16) -> QPixmap:
    path = ICON_DIR / f"{name}.svg"
    if not path.is_file():
        return QPixmap()
    return _tinted_pixmap(str(path), color, size, size)


def icon_size(size: int) -> QSize:
    return QSize(size, size)
