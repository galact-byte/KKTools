"""卡片浏览器：选目录 -> 扫描识别 -> 缩略图墙预览，支持类型筛选 / 搜索 /
双击进编辑器 / 导出目录卡片信息 CSV。"""

from __future__ import annotations

import csv
import os
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from core import card_scan, settings
from core.card_scan import TYPE_LABELS, CardItem
from ui.applog import log
from ui.widgets import PageBase, make_card
from ui.worker import Worker

ROLE_ITEM = Qt.ItemDataRole.UserRole

# 克制的类型色标（功能型状态色，非装饰）
TYPE_COLORS = {
    "character": "#58a6ff",   # 角色卡 蓝
    "coordinate": "#3fb950",  # 服装卡 绿
    "scene": "#d29922",       # 场景卡 琥珀
    "other": "#8b949e",       # 其它 灰
}

# 单次最多在网格里渲染的卡片数（整合版场景卡上万，全渲染会拖垮 UI 与内存）
MAX_DISPLAY = 3000


class BrowserPage(PageBase):
    def __init__(self, on_open_card: Callable[[str], None] | None = None):
        super().__init__("卡片浏览器", "扫描目录，识别角色卡 / 服装卡 / 场景卡，缩略图墙预览")
        self.on_open_card = on_open_card
        self._items: list[CardItem] = []
        self._icon_cache: dict[str, QIcon] = {}
        self._worker: Worker | None = None
        self._root_dir: str = ""
        self._folder_filter: str | None = None  # 选中的目录（含子目录）筛选，None=全部
        self._build_ui()

    def _build_ui(self) -> None:
        bar = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("选择或输入要浏览的目录")
        self.path_edit.setText(settings.get("last_browse_dir", "") or "")
        btn_browse = QPushButton("选择目录")
        btn_browse.clicked.connect(self._choose_dir)
        self.chk_recursive = QCheckBox("递归子目录")
        btn_scan = QPushButton("扫描")
        btn_scan.setProperty("accent", "primary")
        btn_scan.clicked.connect(self._start_scan)
        bar.addWidget(QLabel("目录"))
        bar.addWidget(self.path_edit, 1)
        bar.addWidget(btn_browse)
        bar.addWidget(self.chk_recursive)
        bar.addWidget(btn_scan)
        self.body_layout.addLayout(bar)

        filt = QHBoxLayout()
        self.cb_type = QComboBox()
        self.cb_type.addItem("全部类型", "all")
        for key, lbl in TYPE_LABELS.items():
            self.cb_type.addItem(lbl, key)
        self.cb_type.currentIndexChanged.connect(self._apply_filter)
        self.search = QLineEdit()
        self.search.setPlaceholderText("按名称 / 文件名搜索")
        self.search.textChanged.connect(self._apply_filter)
        self.btn_csv = QPushButton("导出CSV")
        self.btn_csv.clicked.connect(self._export_csv)
        self.btn_csv.setEnabled(False)
        filt.addWidget(QLabel("筛选"))
        filt.addWidget(self.cb_type)
        filt.addWidget(self.search, 1)
        filt.addWidget(self.btn_csv)
        self.body_layout.addLayout(filt)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.body_layout.addWidget(self.progress)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(self._build_left_panel())

        card = make_card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(8, 8, 8, 8)
        self.grid = QListWidget()
        self.grid.setViewMode(QListWidget.ViewMode.IconMode)
        self.grid.setIconSize(QSize(120, 135))
        self.grid.setGridSize(QSize(146, 188))
        self.grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.grid.setMovement(QListWidget.Movement.Static)
        self.grid.setSpacing(6)
        self.grid.setWordWrap(True)
        self.grid.itemDoubleClicked.connect(self._on_double)
        self.grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.grid.customContextMenuRequested.connect(self._menu)
        cl.addWidget(self.grid)
        self.status = QLabel("选择一个目录开始扫描")
        self.status.setObjectName("HintLabel")
        cl.addWidget(self.status)
        split.addWidget(card)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([260, 940])
        self.body_layout.addWidget(split, 1)

    def _build_left_panel(self) -> QFrame:
        panel = make_card()
        panel.setMinimumWidth(220)
        panel.setMaximumWidth(360)
        v = QVBoxLayout(panel)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)

        head = QLabel("库统计")
        head.setObjectName("SectionTitle")
        v.addWidget(head)
        self.stats_label = QLabel("尚未扫描")
        self.stats_label.setWordWrap(True)
        self.stats_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        v.addWidget(self.stats_label)

        tree_head = QLabel("文件夹")
        tree_head.setObjectName("SectionTitle")
        v.addWidget(tree_head)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemSelectionChanged.connect(self._on_tree_select)
        v.addWidget(self.tree, 1)

        btn_all = QPushButton("显示全部目录")
        btn_all.clicked.connect(self._clear_folder_filter)
        v.addWidget(btn_all)
        return panel

    # ---- 扫描 ----

    def _choose_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择目录", self.path_edit.text() or "")
        if d:
            self.path_edit.setText(d)

    def _start_scan(self) -> None:
        directory = self.path_edit.text().strip()
        if not directory or not Path(directory).is_dir():
            QMessageBox.warning(self, "目录无效", "请选择一个有效目录。")
            return
        settings.set_value("last_browse_dir", directory)
        if self._worker and self._worker.isRunning():
            return
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.status.setText("扫描中…")
        log(f"开始扫描目录: {directory} (递归={self.chk_recursive.isChecked()})")
        self._worker = Worker(
            card_scan.scan_dir, directory, recursive=self.chk_recursive.isChecked()
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_scanned)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_progress(self, cur: int, total: int, desc: str) -> None:
        if total:
            self.progress.setRange(0, total)
            self.progress.setValue(cur)
        self.status.setText(f"扫描中… {cur}/{total}  {desc}")

    def _on_scanned(self, items: list[CardItem]) -> None:
        self.progress.setVisible(False)
        self._items = items
        self._icon_cache.clear()   # 新一批卡片，旧图标缓存作废
        self._root_dir = self.path_edit.text().strip()
        self._folder_filter = None
        self.btn_csv.setEnabled(bool(items))
        log(f"扫描完成，共 {len(items)} 张卡片")
        self._update_stats()
        self._rebuild_tree()
        self._apply_filter()

    # ---- 库统计 + 目录树 ----

    def _update_stats(self) -> None:
        total = len(self._items)
        by_type: dict[str, int] = defaultdict(int)
        by_game: dict[str, int] = defaultdict(int)
        for it in self._items:
            by_type[it.type] += 1
            by_game[it.game] += 1
        lines = [f"全库：{total} 张"]
        if by_game.get("KK"):
            lines.append(f"KK：{by_game['KK']}")
        if by_game.get("KKS"):
            lines.append(f"KKS：{by_game['KKS']}")
        for key, lbl in TYPE_LABELS.items():
            if by_type.get(key):
                lines.append(f"{lbl}：{by_type[key]}")
        self.stats_label.setText("    ".join(lines) if total else "尚未扫描")

    def _rebuild_tree(self) -> None:
        self.tree.blockSignals(True)
        self.tree.clear()
        if not self._items or not self._root_dir:
            self.tree.blockSignals(False)
            return
        root = Path(self._root_dir).resolve()
        # 统计每个目录（含子目录）下的卡片数：每张卡为其所在目录及各级祖先（到 root 为止）+1
        counts: dict[str, int] = defaultdict(int)
        for it in self._items:
            p = Path(it.path).resolve().parent
            for d in [p, *p.parents]:
                counts[str(d)] += 1
                if d == root:
                    break
        root_node = QTreeWidgetItem([f"{root.name or str(root)}  ({counts.get(str(root), 0)})"])
        root_node.setData(0, ROLE_ITEM, str(root))
        self.tree.addTopLevelItem(root_node)
        node_map = {str(root): root_node}
        # 按路径深度排序，确保父节点先于子节点创建
        for d in sorted((k for k in counts if k != str(root)), key=lambda s: s.count(os.sep)):
            parent_node = node_map.get(str(Path(d).parent), root_node)
            node = QTreeWidgetItem([f"{Path(d).name}  ({counts[d]})"])
            node.setData(0, ROLE_ITEM, d)
            parent_node.addChild(node)
            node_map[d] = node
        root_node.setExpanded(True)
        self.tree.blockSignals(False)

    def _on_tree_select(self) -> None:
        items = self.tree.selectedItems()
        if not items:
            return
        self._folder_filter = items[0].data(0, ROLE_ITEM)
        self._apply_filter()

    def _clear_folder_filter(self) -> None:
        self.tree.clearSelection()
        self._folder_filter = None
        self._apply_filter()

    def _on_failed(self, msg: str) -> None:
        self.progress.setVisible(False)
        self.status.setText("扫描失败")
        QMessageBox.critical(self, "扫描失败", msg.splitlines()[0])

    # ---- 展示与筛选 ----

    def _folder_match(self, path: str) -> bool:
        if not self._folder_filter:
            return True
        ip = os.path.normcase(os.path.normpath(path))
        fp = os.path.normcase(os.path.normpath(self._folder_filter))
        return ip == fp or ip.startswith(fp + os.sep)

    def _apply_filter(self) -> None:
        type_key = self.cb_type.currentData()
        kw = self.search.text().strip().lower()
        self.grid.clear()
        shown = 0
        capped = False
        for it in self._items:
            if type_key != "all" and it.type != type_key:
                continue
            if not self._folder_match(it.path):
                continue
            hay = f"{it.name} {Path(it.path).name}".lower()
            if kw and kw not in hay:
                continue
            if shown >= MAX_DISPLAY:
                capped = True
                break
            self._add_item(it)
            shown += 1
        counts = {}
        for it in self._items:
            counts[it.type] = counts.get(it.type, 0) + 1
        summary = "  ".join(f"{TYPE_LABELS.get(k,k)}:{v}" for k, v in counts.items())
        tail = f"（已达显示上限 {MAX_DISPLAY}，请用筛选/搜索缩小或扫描子目录）" if capped else ""
        self.status.setText(f"显示 {shown} / {len(self._items)} 张    [{summary}]{tail}")

    def _add_item(self, it: CardItem) -> None:
        # 图标缓存：按路径缓存降采样后的小 QPixmap，原始缩略图字节用完即释放。
        # 这样重新筛选/搜索时能复用，且不会让上千张全尺寸 PNG 常驻内存。
        icon = self._icon_cache.get(it.path)
        if icon is None:
            pix = QPixmap()
            if it.thumbnail:
                pix.loadFromData(it.thumbnail)
            if not pix.isNull():
                pix = pix.scaled(self.grid.iconSize(), Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
                icon = QIcon(pix)
            else:
                icon = QIcon()
            self._icon_cache[it.path] = icon
            it.thumbnail = b""   # 已转成小图标，释放原始字节
        label = it.name or Path(it.path).stem
        tag = TYPE_LABELS.get(it.type, it.type)
        if it.game in ("KK", "KKS"):
            tag = f"{it.game}·{tag}"
        wi = QListWidgetItem(icon, f"{label}\n[{tag}]")
        wi.setData(ROLE_ITEM, it)
        wi.setToolTip(it.path)
        wi.setForeground(QColor(TYPE_COLORS.get(it.type, "#c9d1d9")))
        wi.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.grid.addItem(wi)

    # ---- 交互 ----

    def _on_double(self, wi: QListWidgetItem) -> None:
        it: CardItem = wi.data(ROLE_ITEM)
        if it.type == "character" and self.on_open_card:
            self.on_open_card(it.path)
        else:
            self._open_in_explorer(it.path)

    def focus_search(self) -> None:
        """供全局快捷键 Ctrl+F 调用：聚焦搜索框并全选。"""
        self.search.setFocus()
        self.search.selectAll()

    def _menu(self, pos) -> None:
        wi = self.grid.itemAt(pos)
        if not wi:
            return
        it: CardItem = wi.data(ROLE_ITEM)
        menu = QMenu(self)
        if it.type == "character":
            menu.addAction("在编辑器打开", lambda: self.on_open_card and self.on_open_card(it.path))
        menu.addAction("打开所在文件夹", lambda: self._open_in_explorer(it.path))
        menu.addAction("复制文件路径", lambda: self._copy_path(it.path))
        menu.addSeparator()
        menu.addAction("删除此卡…", lambda: self._delete_card(it, wi))
        menu.exec(self.grid.mapToGlobal(pos))

    def _copy_path(self, path: str) -> None:
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(path)
        log(f"已复制路径: {path}")

    def _delete_card(self, it: CardItem, wi: QListWidgetItem) -> None:
        """删除单张卡片：二次确认，优先移入系统回收站（装了 send2trash 时可还原）。"""
        ret = QMessageBox.question(
            self, "删除卡片",
            f"将删除这张卡片：\n{Path(it.path).name}\n\n"
            "会优先移入系统回收站（装了 send2trash 时可还原），否则永久删除。继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if ret != QMessageBox.StandardButton.Yes:
            return
        try:
            try:
                from send2trash import send2trash
                send2trash(os.path.normpath(it.path)); where = "已移入回收站"
            except ImportError:
                Path(it.path).unlink(); where = "已永久删除（未装 send2trash）"
        except OSError as exc:
            QMessageBox.warning(self, "删除失败", str(exc)); return
        self._items = [x for x in self._items if x.path != it.path]
        self.grid.takeItem(self.grid.row(wi))
        self._update_stats()
        self.btn_csv.setEnabled(bool(self._items))
        log(f"{where}: {it.path}")

    def _open_in_explorer(self, path: str) -> None:
        try:
            if os.name == "nt":
                subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
            else:
                subprocess.Popen(["xdg-open", str(Path(path).parent)])
        except OSError as exc:
            QMessageBox.warning(self, "打开失败", str(exc))

    def _export_csv(self) -> None:
        if not self._items:
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出卡片信息 CSV", "cards.csv", "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["文件名", "类型", "游戏", "角色名", "路径"])
            for it in self._items:
                w.writerow([Path(it.path).name, TYPE_LABELS.get(it.type, it.type),
                            it.game, it.name, it.path])
        log(f"导出 CSV: {path}")
        QMessageBox.information(self, "已导出", f"已导出 {len(self._items)} 条到:\n{path}")
