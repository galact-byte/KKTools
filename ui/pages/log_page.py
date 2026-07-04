"""运行日志页：显示各模块通过日志总线发出的操作记录。"""

from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QPlainTextEdit, QPushButton, QVBoxLayout

from ui.applog import bus
from ui.widgets import PageBase, make_card, section_title


class LogPage(PageBase):
    def __init__(self):
        super().__init__("运行日志", "各模块操作记录")
        card = make_card()
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 14, 14, 14)
        v.addWidget(section_title("日志"))
        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setPlainText("\n".join(bus.history))
        v.addWidget(self.view, 1)
        row = QHBoxLayout()
        b_clear = QPushButton("清空显示")
        b_clear.clicked.connect(self.view.clear)
        row.addStretch(1)
        row.addWidget(b_clear)
        v.addLayout(row)
        self.body_layout.addWidget(card, 1)

        bus.message.connect(self._append)

    def _append(self, line: str) -> None:
        self.view.appendPlainText(line)
