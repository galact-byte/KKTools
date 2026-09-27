"""运行日志页：显示各模块通过日志总线发出的操作记录。"""

from __future__ import annotations

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QHBoxLayout, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout

from core import diagnostics

from ui.applog import bus
from ui.widgets import PageBase, make_card, section_title


class LogPage(PageBase):
    def __init__(self):
        super().__init__("运行日志", "操作记录自动保存；反馈 Bug 时请附上对应日志")
        card = make_card()
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 14, 14, 14)
        v.addWidget(section_title("日志"))
        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(3000)
        self.view.setPlaceholderText("暂无记录，操作过程会显示在这里")
        self.view.setPlainText("\n".join(bus.history))
        v.addWidget(self.view, 1)
        row = QHBoxLayout()
        b_open = QPushButton("打开日志目录")
        b_open.clicked.connect(self._open_logs)
        row.addWidget(b_open)
        b_clear = QPushButton("清空显示")
        b_clear.clicked.connect(self.view.clear)
        row.addStretch(1)
        row.addWidget(b_clear)
        v.addLayout(row)
        self.body_layout.addWidget(card, 1)

        bus.message.connect(self._append)

    def _open_logs(self) -> None:
        path = diagnostics.log_path()
        if path is None:
            QMessageBox.warning(self, "日志不可用", "本次运行未能创建日志文件，请保留报错截图。")
        elif not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent))):
            QMessageBox.warning(self, "无法打开目录", f"请手动打开日志目录：\n{path.parent}")

    def _append(self, line: str) -> None:
        self.view.appendPlainText(line)
