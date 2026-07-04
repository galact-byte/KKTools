"""主窗口：顶部横向导航（品牌 + 标签 + 窗控合为一条顶栏）+ 下方全宽页面堆叠。

刻意采用顶部导航而非左侧栏——剪影与常见左栏工具截然不同。
默认无边框（顶栏自绘、可拖动/边缘缩放）；config 里 frameless=False 退回系统原生窗口。
功能型布局，克制无装饰；间距遵循 8px 节奏、字号用统一阶梯。
"""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core import settings, theme as theme_mod
from ui.iconutil import tint_icon
from ui.pages.browser_page import BrowserPage
from ui.pages.editor_page import EditorPage
from ui.pages.log_page import LogPage
from ui.pages.mod_page import ModPage
from ui.pages.pack_page import PackPage
from ui.pages.scene_page import ScenePage
from ui.pages.settings_page import SettingsPage
from ui.pages.share_page import SharePage

APP_VERSION = "v0.5.0"

# 导航：(短标签, 完整名/tooltip, 图标名)
NAV = [
    ("编辑", "角色卡编辑", "nav_editor"),
    ("浏览", "卡片浏览器", "nav_browser"),
    ("打包", "解包 / 打包", "nav_pack"),
    ("分享", "分享整理导入", "nav_share"),
    ("Mod", "Mod 仓库", "nav_mod"),
    ("场景", "场景卡工具", "nav_scene"),
    ("日志", "运行日志", "nav_log"),
    ("设置", "软件设置", "nav_settings"),
]
EDITOR_ROW = 0

_RESIZE_MARGIN = 7  # 边缘缩放命中区宽度（px）


class _TopBar(QFrame):
    """顶栏：空白区可拖动窗口、双击最大化（仅无边框时生效）。"""

    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.setObjectName("TopBar")
        self._win = win
        self._press = None
        self._origin = None

    def mousePressEvent(self, event) -> None:
        if self._win._frameless and event.button() == Qt.MouseButton.LeftButton:
            self._press = event.globalPosition().toPoint()
            self._origin = self._win.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._press is not None and not self._win.isMaximized():
            delta = event.globalPosition().toPoint() - self._press
            self._win.move(self._origin + delta)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._press = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if self._win._frameless and event.button() == Qt.MouseButton.LeftButton:
            self._win._toggle_max()
        super().mouseDoubleClickEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("KKTools - 恋活角色卡工具箱")
        self.resize(1240, 800)
        self.setMinimumSize(1040, 660)
        self.setAcceptDrops(True)

        self._frameless = bool(settings.get("frameless", True))
        self._resize_edge: str | None = None
        self._resize_start = None
        if self._frameless:
            self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
            self.setMouseTracking(True)

        central = QWidget()
        central.setMouseTracking(True)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(central)

        root.addWidget(self._build_topbar())

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        # 实例化页面
        self.editor = EditorPage()
        self.browser = BrowserPage(on_open_card=self._open_in_editor)
        self.pages = [
            self.editor,
            self.browser,
            PackPage(),
            SharePage(),
            ModPage(),
            ScenePage(),
            LogPage(),
            SettingsPage(),
        ]
        for p in self.pages:
            self.stack.addWidget(p)

        self.apply_ui_mode(settings.get("ui_mode", "normal"))
        start = settings.get("start_page", 1)
        self._select_page(start if 0 <= start < len(self.pages) else 0)
        self._build_shortcuts()
        self.statusBar().showMessage("就绪 — 可把角色卡拖到窗口直接编辑")

        # 初始化图标着色（Logo + 导航 + 窗控）
        self._refresh_logo()
        self._refresh_nav_icons()

    # ---- 全局快捷键 ----

    def _build_shortcuts(self) -> None:
        """Ctrl+O 读卡 / Ctrl+S 另存 / Ctrl+F 聚焦搜索 / Ctrl+1~8 切页。
        用 Ctrl 组合而非裸数字键，避免抢走输入框里的数字输入。"""
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self._sc_open)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self._sc_save)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self._sc_find)
        for i in range(len(self.pages)):
            QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self,
                      activated=lambda idx=i: self._select_page(idx))

    def _sc_open(self) -> None:
        self._select_page(EDITOR_ROW)
        self.editor._open_card()

    def _sc_save(self) -> None:
        if self.stack.currentWidget() is self.editor:
            self.editor._save_as_new()

    def _sc_find(self) -> None:
        fn = getattr(self.stack.currentWidget(), "focus_search", None)
        if callable(fn):
            fn()

    # ---- 顶栏（品牌 + 横向导航 + 窗控） ----

    def _build_topbar(self) -> QWidget:
        bar = _TopBar(self)
        bar.setFixedHeight(54)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(18, 0, 10, 0)
        lay.setSpacing(16)

        brand_icon = QLabel()
        brand_icon.setObjectName("BrandLogo")
        brand_icon.setFixedSize(24, 24)
        lay.addWidget(brand_icon)

        brand = QLabel("KKTools")
        brand.setObjectName("TitleBrand")
        lay.addWidget(brand)

        # 横向导航标签
        nav_wrap = QWidget()
        nav_wrap.setObjectName("NavWrap")
        nl = QHBoxLayout(nav_wrap)
        nl.setContentsMargins(0, 0, 0, 0)
        nl.setSpacing(4)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: list[QPushButton] = []
        self.nav_icons: list[str] = []
        for idx, (short, full, icon) in enumerate(NAV):
            b = QPushButton(short)
            b.setObjectName("NavTab")
            b.setCheckable(True)
            b.setToolTip(full)
            b.setIconSize(QSize(16, 16))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _checked, i=idx: self._select_page(i))
            self.nav_group.addButton(b, idx)
            self.nav_buttons.append(b)
            self.nav_icons.append(icon)
            nl.addWidget(b)
        lay.addWidget(nav_wrap)

        lay.addStretch(1)

        if self._frameless:
            self.btn_min = self._win_button("WinBtn")
            self.btn_max = self._win_button("WinBtn")
            self.btn_close = self._win_button("WinCloseBtn")
            self.btn_min.clicked.connect(self.showMinimized)
            self.btn_max.clicked.connect(self._toggle_max)
            self.btn_close.clicked.connect(self.close)
            lay.addWidget(self.btn_min)
            lay.addWidget(self.btn_max)
            lay.addWidget(self.btn_close)
            self._refresh_win_icons()
        return bar

    def _win_button(self, obj_name: str) -> QPushButton:
        b = QPushButton()
        b.setObjectName(obj_name)
        b.setFixedSize(36, 30)
        return b

    def _refresh_win_icons(self) -> None:
        if not self._frameless:
            return
        color = self._theme_token("text_muted")
        self.btn_min.setIcon(tint_icon("win_min", color, 16))
        self.btn_max.setIcon(tint_icon("win_restore" if self.isMaximized() else "win_max", color, 14))
        self.btn_close.setIcon(tint_icon("win_close", color, 16))

    def _theme_token(self, key: str) -> str:
        cfg = settings.load()
        user_dir = cfg.get("user_theme_dir", "") or None
        extra = [user_dir] if user_dir else None
        th = theme_mod.find_theme(cfg.get("theme", "bone_light"), extra) \
            or theme_mod.from_dict({"id": "bone_light", "name": "骨白·昼"})
        return th.flat()[key]

    def refresh_theme_dependent(self) -> None:
        """主题切换后重新着色窗控图标 + 导航图标 + 品牌 Logo。"""
        self._refresh_win_icons()
        self._refresh_nav_icons()
        self._refresh_logo()

    # ---- 导航 / 窗口 ----

    def _select_page(self, index: int) -> None:
        if not (0 <= index < self.stack.count()):
            return
        self.stack.setCurrentIndex(index)
        btn = self.nav_buttons[index]
        if not btn.isChecked():
            btn.setChecked(True)
        self._refresh_nav_icons()

    def _refresh_nav_icons(self) -> None:
        """按选中态给导航图标着色：当前项用 on_primary（衬朱红底），其余 text_muted。"""
        cur = self.stack.currentIndex()
        active = self._theme_token("on_primary")
        rest = self._theme_token("text_muted")
        for i, b in enumerate(self.nav_buttons):
            b.setIcon(tint_icon(self.nav_icons[i], active if i == cur else rest, 16))

    def _refresh_logo(self) -> None:
        """品牌 Logo 着 accent 色。"""
        logo = self.findChild(QLabel, "BrandLogo")
        if logo:
            logo.setPixmap(tint_icon("logo", self._theme_token("accent"), 24).pixmap(24, 24))

    def apply_ui_mode(self, mode: str) -> None:
        """把界面模式广播给各页面；实现了 apply_ui_mode 的页面据此收放高级选项。"""
        for p in self.pages:
            fn = getattr(p, "apply_ui_mode", None)
            if callable(fn):
                fn(mode)

    def _toggle_max(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        self._refresh_win_icons()

    def _open_in_editor(self, path: str) -> None:
        self._select_page(EDITOR_ROW)
        self.editor.load_card(path)

    # ---- 边缘缩放（无边框窗口手动实现） ----

    def _edge_at(self, pos) -> str | None:
        if not self._frameless or self.isMaximized():
            return None
        m = _RESIZE_MARGIN
        x, y, w, h = pos.x(), pos.y(), self.width(), self.height()
        left, right = x <= m, x >= w - m
        top, bottom = y <= m, y >= h - m
        if top and left:
            return "tl"
        if top and right:
            return "tr"
        if bottom and left:
            return "bl"
        if bottom and right:
            return "br"
        if left:
            return "l"
        if right:
            return "r"
        if top:
            return "t"
        if bottom:
            return "b"
        return None

    _CURSORS = {
        "l": Qt.CursorShape.SizeHorCursor, "r": Qt.CursorShape.SizeHorCursor,
        "t": Qt.CursorShape.SizeVerCursor, "b": Qt.CursorShape.SizeVerCursor,
        "tl": Qt.CursorShape.SizeFDiagCursor, "br": Qt.CursorShape.SizeFDiagCursor,
        "tr": Qt.CursorShape.SizeBDiagCursor, "bl": Qt.CursorShape.SizeBDiagCursor,
    }

    def mousePressEvent(self, event) -> None:
        if self._frameless and event.button() == Qt.MouseButton.LeftButton:
            edge = self._edge_at(event.position().toPoint())
            if edge:
                self._resize_edge = edge
                self._resize_start = (event.globalPosition().toPoint(), self.geometry())
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._frameless:
            if self._resize_edge and self._resize_start:
                self._do_resize(event.globalPosition().toPoint())
                return
            edge = self._edge_at(event.position().toPoint())
            self.setCursor(self._CURSORS.get(edge, Qt.CursorShape.ArrowCursor))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._resize_edge = None
        self._resize_start = None
        super().mouseReleaseEvent(event)

    def _do_resize(self, gpos) -> None:
        start_pos, start_geo = self._resize_start
        dx = gpos.x() - start_pos.x()
        dy = gpos.y() - start_pos.y()
        g = start_geo.adjusted(0, 0, 0, 0)
        minw, minh = self.minimumWidth(), self.minimumHeight()
        edge = self._resize_edge
        left, top = g.left(), g.top()
        right, bottom = g.right(), g.bottom()
        if "l" in edge:
            left = min(g.left() + dx, right - minw)
        if "r" in edge:
            right = max(g.right() + dx, left + minw)
        if "t" in edge:
            top = min(g.top() + dy, bottom - minh)
        if "b" in edge:
            bottom = max(g.bottom() + dy, top + minh)
        g.setCoords(left, top, right, bottom)
        self.setGeometry(g)

    # ---- 拖拽角色卡直接编辑 ----

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".png"):
                self._open_in_editor(path)
                break
