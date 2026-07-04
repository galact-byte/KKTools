"""占位页面：尚未实现的模块统一用它，保证应用可整体运行。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout

from ui.widgets import PageBase, make_card


class PlaceholderPage(PageBase):
    def __init__(self, title: str, subtitle: str = "", todo: str = ""):
        super().__init__(title, subtitle)
        card = make_card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(24, 40, 24, 40)
        cl.setSpacing(8)
        cl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        head = QLabel("本模块开发中")
        head.setObjectName("PageTitle")
        head.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(head)

        if todo:
            desc = QLabel(todo)
            desc.setObjectName("HintLabel")
            desc.setWordWrap(True)
            desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(desc)

        self.body_layout.addWidget(card)
        self.body_layout.addStretch(1)
