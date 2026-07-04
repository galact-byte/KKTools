"""软件设置页：配置游戏目录、Mod 目录、输出目录等。"""

from __future__ import annotations

import os
import subprocess
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core import identity, settings, theme as theme_mod
from ui.applog import log
from ui.widgets import PageBase, hint, make_dir_row, section_title


class SettingsPage(PageBase):
    def __init__(self):
        super().__init__("软件设置", "配置游戏目录、Mod 仓库与输出目录")
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        col = QVBoxLayout(inner)
        col.setContentsMargins(0, 0, 8, 0)
        col.setSpacing(28)
        col.addWidget(self._build_appearance())
        col.addWidget(self._build_identity())

        # 路径配置——不用卡片包裹，靠分区标题 + 间距分隔
        path_section = QWidget()
        pv = QVBoxLayout(path_section)
        pv.setContentsMargins(0, 0, 0, 0)
        pv.setSpacing(10)
        pv.addWidget(section_title("路径配置"))

        _d, self.kk = make_dir_row("恋活(KK)游戏根目录", parent=self, label_width=190); pv.addLayout(_d)
        _d, self.kks = make_dir_row("恋活日光浴(KKS)游戏根目录", parent=self, label_width=190); pv.addLayout(_d)
        _d, self.output = make_dir_row("通用输出目录", parent=self, label_width=190); pv.addLayout(_d)
        _d, self.carrier = make_dir_row("伪装载体目录", parent=self, label_width=190); pv.addLayout(_d)

        pv.addWidget(section_title("额外 Mod 目录"))
        pv.addWidget(hint("游戏目录下的 mods 会自动纳入；这里可补充其它存放 zipmod 的目录。"))
        self.mod_list = QListWidget()
        self.mod_list.setMaximumHeight(120)
        pv.addWidget(self.mod_list)
        mrow = QHBoxLayout()
        b_add = QPushButton("添加目录"); b_add.clicked.connect(self._add_mod_dir)
        b_del = QPushButton("移除选中"); b_del.clicked.connect(self._del_mod_dir)
        mrow.addWidget(b_add); mrow.addWidget(b_del); mrow.addStretch(1)
        pv.addLayout(mrow)

        save = QPushButton("保存设置"); save.setProperty("accent", "primary")
        save.clicked.connect(self._save)
        pv.addWidget(save)
        col.addWidget(path_section)
        col.addStretch(1)
        scroll.setWidget(inner)
        self.body_layout.addWidget(scroll, 1)

    def _build_appearance(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)
        v.addWidget(section_title("外观"))
        v.addWidget(hint("切换界面主题（即时生效）。把自定义主题 JSON 放进用户主题目录即可被加载。"))

        cfg = settings.load()

        row = QHBoxLayout()
        lbl = QLabel("界面主题"); lbl.setMinimumWidth(190)
        self.theme_combo = QComboBox()
        self._reload_theme_list(cfg.get("user_theme_dir", ""), cfg.get("theme", "bone_light"))
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        row.addWidget(lbl); row.addWidget(self.theme_combo, 1)
        v.addLayout(row)

        mode_row = QHBoxLayout()
        m_lbl = QLabel("界面模式"); m_lbl.setMinimumWidth(190)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("精简（普通）— 只显示常用功能", "normal")
        self.mode_combo.addItem("完整（高级）— 展开封缄/分卷/标识切换等", "advanced")
        cur_mode = cfg.get("ui_mode", "normal")
        self.mode_combo.setCurrentIndex(1 if cur_mode == "advanced" else 0)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_row.addWidget(m_lbl); mode_row.addWidget(self.mode_combo, 1)
        v.addLayout(mode_row)

        ud = QHBoxLayout()
        ud_lbl = QLabel("用户主题目录"); ud_lbl.setMinimumWidth(190)
        self.user_theme_dir = QLineEdit(cfg.get("user_theme_dir", ""))
        self.user_theme_dir.setPlaceholderText("可空；放自定义主题 JSON 的目录")
        b_pick = QPushButton("…"); b_pick.setObjectName("MiniBtn"); b_pick.setFixedWidth(34)
        b_pick.clicked.connect(self._pick_user_theme_dir)
        b_open = QPushButton("打开"); b_open.clicked.connect(self._open_user_theme_dir)
        ud.addWidget(ud_lbl); ud.addWidget(self.user_theme_dir, 1)
        ud.addWidget(b_pick); ud.addWidget(b_open)
        v.addLayout(ud)

        fl_row = QHBoxLayout()
        fl_lbl = QLabel("标题栏样式"); fl_lbl.setMinimumWidth(190)
        self.frameless_check = QCheckBox("使用无边框自绘标题栏（默认系统原生，重启后生效）")
        self.frameless_check.setChecked(bool(cfg.get("frameless", False)))
        self.frameless_check.toggled.connect(lambda on: settings.set_value("frameless", on))
        fl_row.addWidget(fl_lbl); fl_row.addWidget(self.frameless_check, 1)
        v.addLayout(fl_row)
        return w

    def _build_identity(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)
        v.addWidget(section_title("库身份（用于清单对账）"))
        v.addWidget(hint("导出 Mod 清单时会盖上这个身份，方便朋友区分来源。ID 首次运行自动生成、保持不变。"))

        ident = identity.get_identity()
        row = QHBoxLayout()
        lbl = QLabel("展示名"); lbl.setMinimumWidth(190)
        self.display_name = QLineEdit(ident.get("display_name", ""))
        self.display_name.setPlaceholderText("给自己起个名字，例如：阿白")
        b_save = QPushButton("保存展示名"); b_save.clicked.connect(self._save_display_name)
        row.addWidget(lbl); row.addWidget(self.display_name, 1); row.addWidget(b_save)
        v.addLayout(row)

        ids = QLabel(f"holder: {ident.get('holder_id','')}    library: {ident.get('library_id','')}")
        ids.setObjectName("HintLabel")
        v.addWidget(ids)
        return w

    def _save_display_name(self) -> None:
        identity.set_display_name(self.display_name.text())
        log("展示名已保存")
        QMessageBox.information(self, "已保存", "展示名已保存。")

    def _reload_theme_list(self, user_dir: str, current_id: str) -> None:
        """重建主题下拉。用 itemData 存 id，避免 currentText 与显示名耦合。"""
        self.theme_combo.blockSignals(True)
        self.theme_combo.clear()
        extra = [user_dir] if user_dir else None
        sel = 0
        for i, th in enumerate(theme_mod.list_themes(extra)):
            label = f"{th.name}  ·  {'浅色' if th.variant == 'light' else '深色'}"
            self.theme_combo.addItem(label, th.id)
            if th.id == current_id:
                sel = i
        self.theme_combo.setCurrentIndex(sel)
        self.theme_combo.blockSignals(False)

    def _on_theme_changed(self, _index: int) -> None:
        tid = self.theme_combo.currentData()
        if tid is None:
            return
        settings.set_value("theme", tid)
        app = QApplication.instance()
        if app is not None:
            from main import apply_theme  # 延迟导入避免循环依赖
            apply_theme(app, tid)
        # 主题切换后重新着色图标（标题栏窗控 + 侧栏导航）
        win = self.window()
        if hasattr(win, "refresh_theme_dependent"):
            win.refresh_theme_dependent()
        log(f"已切换主题: {tid}")

    def _on_mode_changed(self, _index: int) -> None:
        mode = self.mode_combo.currentData() or "normal"
        settings.set_value("ui_mode", mode)
        win = self.window()
        if hasattr(win, "apply_ui_mode"):
            win.apply_ui_mode(mode)
        log(f"已切换界面模式: {'高级' if mode == 'advanced' else '普通'}")

    def _pick_user_theme_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择用户主题目录", self.user_theme_dir.text() or "")
        if d:
            self.user_theme_dir.setText(d)
            settings.set_value("user_theme_dir", d)
            self._reload_theme_list(d, settings.get("theme", "bone_light"))
            log(f"用户主题目录已设为: {d}")

    def _open_user_theme_dir(self) -> None:
        d = self.user_theme_dir.text().strip() or str(theme_mod.builtin_dir())
        try:
            if sys.platform.startswith("win"):
                os.startfile(d)  # noqa: S606 - 打开本机目录，路径来自用户配置
            elif sys.platform == "darwin":
                subprocess.run(["open", d], check=False)
            else:
                subprocess.run(["xdg-open", d], check=False)
        except OSError as exc:
            QMessageBox.warning(self, "无法打开", f"打开目录失败: {exc}")

    def _add_mod_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择 Mod 目录")
        if d:
            self.mod_list.addItem(d)

    def _del_mod_dir(self) -> None:
        for it in self.mod_list.selectedItems():
            self.mod_list.takeItem(self.mod_list.row(it))

    def _load(self) -> None:
        cfg = settings.load()
        self.kk.setText(cfg.get("kk_game_dir", ""))
        self.kks.setText(cfg.get("kks_game_dir", ""))
        self.output.setText(cfg.get("output_dir", ""))
        self.carrier.setText(cfg.get("carrier_dir", ""))
        self.mod_list.clear()
        for d in cfg.get("mod_dirs", []):
            self.mod_list.addItem(d)

    def _save(self) -> None:
        cfg = settings.load()
        cfg["kk_game_dir"] = self.kk.text().strip()
        cfg["kks_game_dir"] = self.kks.text().strip()
        cfg["output_dir"] = self.output.text().strip()
        cfg["carrier_dir"] = self.carrier.text().strip()
        cfg["mod_dirs"] = [self.mod_list.item(i).text() for i in range(self.mod_list.count())]
        new_user_dir = self.user_theme_dir.text().strip()
        if new_user_dir != cfg.get("user_theme_dir", ""):
            cfg["user_theme_dir"] = new_user_dir
            self._reload_theme_list(new_user_dir, cfg.get("theme", "bone_light"))
        settings.save(cfg)
        log("设置已保存")
        QMessageBox.information(self, "已保存", "设置已保存。")
