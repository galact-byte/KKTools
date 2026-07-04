"""场景卡工具页：提取场景卡内嵌角色（带封面）、分析 mod 依赖。"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core import scene_card
from core.scene_card import get_scene_preview
from ui.applog import log
from ui.widgets import PageBase, hint, make_card, section_title


class ScenePage(PageBase):
    def __init__(self):
        super().__init__("场景卡工具", "从 Studio 场景卡提取内嵌角色（带封面），分析依赖")
        self._scene_path: str | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        bar = QHBoxLayout()
        b_pick = QPushButton("选择场景卡"); b_pick.setProperty("accent", "primary")
        b_pick.clicked.connect(self._pick)
        self.path_label = QLabel("未选择")
        self.path_label.setObjectName("HintLabel")
        bar.addWidget(b_pick); bar.addWidget(self.path_label, 1)
        self.body_layout.addLayout(bar)

        body = QHBoxLayout(); body.setSpacing(14)
        # 左：封面
        left = make_card(); lv = QVBoxLayout(left); lv.setContentsMargins(14, 14, 14, 14)
        lv.addWidget(section_title("场景封面"))
        self.preview = QLabel("—"); self.preview.setObjectName("ThumbPreview")
        self.preview.setFixedSize(240, 200); self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lv.addWidget(self.preview); lv.addStretch(1)
        left.setFixedWidth(272)
        body.addWidget(left)
        # 右：分析与操作
        right = make_card(); rv = QVBoxLayout(right); rv.setContentsMargins(14, 14, 14, 14)
        rv.addWidget(section_title("分析结果"))
        rv.addWidget(hint("提取的角色以脸图作封面，重建为可独立读取的标准角色卡。"))
        self.analysis = QPlainTextEdit(); self.analysis.setReadOnly(True)
        rv.addWidget(self.analysis, 1)
        row = QHBoxLayout()
        self.b_analyze = QPushButton("分析"); self.b_analyze.clicked.connect(self._analyze); self.b_analyze.setEnabled(False)
        self.b_extract = QPushButton("提取角色到目录"); self.b_extract.setProperty("accent", "primary")
        self.b_extract.clicked.connect(self._extract); self.b_extract.setEnabled(False)
        row.addStretch(1); row.addWidget(self.b_analyze); row.addWidget(self.b_extract)
        rv.addLayout(row)
        body.addWidget(right, 1)
        self.body_layout.addLayout(body, 1)

    def _pick(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择场景卡", "", "场景卡 PNG (*.png)")
        if not path:
            return
        self._scene_path = path
        self.path_label.setText(path)
        self.b_analyze.setEnabled(True); self.b_extract.setEnabled(True)
        data = Path(path).read_bytes()
        prev = get_scene_preview(data)
        if prev:
            pix = QPixmap(); pix.loadFromData(prev)
            self.preview.setPixmap(pix.scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation))
        else:
            self.preview.setText("无封面")
        self._analyze()

    def _analyze(self) -> None:
        if not self._scene_path:
            return
        try:
            info = scene_card.analyze_scene(self._scene_path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "分析失败", str(exc)); return
        lines = [
            f"文件: {Path(info['path']).name}",
            f"大小: {info['size']} 字节",
            f"内嵌角色数: {info['character_count']}",
            f"聚合 mod 依赖数: {len(info['mod_ids'])}  (其中场景级 studio 道具 {info.get('scene_mod_count', 0)} 个)",
            "",
            "内嵌角色:",
        ]
        for i, c in enumerate(info["characters"], 1):
            lines.append(f"  {i}. {c['name']}  [{c['game']}]  依赖 mod {c['mods']} 个")
        if info["mod_ids"]:
            lines.append("")
            lines.append("依赖 mod (ModID x 次数):")
            for g, n in sorted(info["mod_ids"].items()):
                lines.append(f"  {g} x{n}")
        self.analysis.setPlainText("\n".join(lines))

    def _extract(self) -> None:
        if not self._scene_path:
            return
        out = QFileDialog.getExistingDirectory(self, "选择提取输出目录")
        if not out:
            return
        try:
            saved = scene_card.extract_characters_to(self._scene_path, out)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "提取失败", str(exc)); return
        log(f"从场景卡提取 {len(saved)} 个角色到 {out}")
        if saved:
            QMessageBox.information(self, "提取完成",
                                    f"已提取 {len(saved)} 个角色到:\n{out}")
        else:
            QMessageBox.information(self, "无角色", "未在该场景卡中找到可提取的内嵌角色。")
