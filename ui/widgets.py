"""可复用的小部件与辅助函数，避免各页面重复造轮子。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def make_card(parent: QWidget | None = None) -> QFrame:
    """内容分区容器：微妙底色 + 细线框 + 极轻投影。

    提供清晰的视觉分组。投影克制（blur6/offset0,1/alpha24），
    只在亮色主题下产生必要的层次区分，不是重阴影卡片堆叠。
    """
    frame = QFrame(parent)
    frame.setProperty("card", True)
    shadow = QGraphicsDropShadowEffect(frame)
    shadow.setBlurRadius(6)
    shadow.setColor(QColor(0, 0, 0, 24))
    shadow.setOffset(0, 1)
    frame.setGraphicsEffect(shadow)
    return frame


def section_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("SectionTitle")
    return label


def hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("HintLabel")
    label.setWordWrap(True)
    return label


def field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("FieldLabel")
    return label


def make_dir_row(label: str, default: str = "", parent: QWidget | None = None,
                 label_width: int | None = None) -> tuple[QHBoxLayout, QLineEdit]:
    """目录选择行：标签 + 输入框 + 「…」按钮，返回 (row_layout, line_edit)。"""
    row = QHBoxLayout()
    edit = QLineEdit(default)
    btn = QPushButton("…"); btn.setObjectName("MiniBtn"); btn.setFixedWidth(34)

    def pick():
        d = QFileDialog.getExistingDirectory(parent, label, edit.text() or "")
        if d:
            edit.setText(d)

    btn.clicked.connect(pick)
    lbl = QLabel(label)
    if label_width:
        lbl.setMinimumWidth(label_width)
    row.addWidget(lbl)
    row.addWidget(edit, 1)
    row.addWidget(btn)
    return row, edit


class CardDropList(QListWidget):
    """接受拖放 PNG（角色卡）的列表控件。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e: QDragEnterEvent) -> None:
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent) -> None:
        for url in e.mimeData().urls():
            p = url.toLocalFile()
            if p.lower().endswith(".png"):
                self.addItem(p)


class PageBase(QWidget):
    """所有页面的基类：统一提供页头(标题+副标题) + 内容区。"""

    def __init__(self, title: str, subtitle: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._title = title
        self._subtitle = subtitle
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(0)

        header = QFrame()
        header.setObjectName("PageHeader")
        hl = QVBoxLayout(header)
        hl.setContentsMargins(28, 20, 28, 18)
        hl.setSpacing(4)
        t = QLabel(title)
        t.setObjectName("PageTitle")
        hl.addWidget(t)
        if subtitle:
            s = QLabel(subtitle)
            s.setObjectName("PageSubtitle")
            hl.addWidget(s)
        self._outer.addWidget(header)

        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(28, 22, 28, 24)
        self.body_layout.setSpacing(18)
        self._outer.addWidget(self.body, 1)
