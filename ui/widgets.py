"""可复用的小部件与辅助函数，避免各页面重复造轮子。"""

from __future__ import annotations

from PyQt6 import sip
from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtGui import QColor, QDragEnterEvent, QDropEvent, QPainter, QPalette
from PyQt6.QtWidgets import (
    QAbstractItemView,
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


# 表单字段名列宽：同一区块的输入框都从这一列开始
FORM_LABEL_W = 90


def indent_row(*widgets: QWidget, width: int = FORM_LABEL_W) -> QHBoxLayout:
    """复选框等无字段名的控件，缩进到输入框那一列。"""
    row = QHBoxLayout()
    row.addWidget(field_label("", width))
    for w in widgets:
        row.addWidget(w)
    row.addStretch(1)
    return row


def field_label(text: str, width: int | None = None) -> QLabel:
    """表单左侧字段名；给定 width 时固定宽度，让同一区块的输入框从同一列开始。"""
    label = QLabel(text)
    label.setObjectName("FieldLabel")
    if width:
        label.setFixedWidth(width)
    return label


class _EmptyHint(QObject):
    """列表为空时在视口中央画一行浅色提示，有内容后自动消失。"""

    def __init__(self, view: QAbstractItemView, text: str):
        super().__init__(view)
        self._view = view
        self._text = text

    def refresh(self, *_args) -> None:
        if not sip.isdeleted(self._view):
            self._view.viewport().update()

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt 接口名)
        if event.type() != QEvent.Type.Paint or sip.isdeleted(self._view):
            return False
        model = self._view.model()
        if model is not None and model.rowCount() > 0:
            return False
        self._view.viewportEvent(event)  # 先画背景，再叠提示
        painter = QPainter(obj)
        painter.setPen(self._view.palette().color(QPalette.ColorRole.PlaceholderText))
        rect = obj.rect().adjusted(16, 0, -16, 0)
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap), self._text)
        painter.end()
        return True


def install_empty_hint(view: QAbstractItemView, text: str) -> None:
    """给列表/树加空状态提示，告诉用户这里可以拖入或添加什么。"""
    view.setProperty("emptyHint", text)
    hint_filter = _EmptyHint(view, text)
    view.viewport().installEventFilter(hint_filter)
    model = view.model()
    if model is not None:
        for sig in (model.rowsInserted, model.rowsRemoved, model.modelReset):
            sig.connect(hint_filter.refresh)


def make_dir_row(label: str, default: str = "", parent: QWidget | None = None,
                 label_width: int = FORM_LABEL_W) -> tuple[QHBoxLayout, QLineEdit]:
    """目录选择行：标签 + 输入框 + 「…」按钮，返回 (row_layout, line_edit)。"""
    row = QHBoxLayout()
    edit = QLineEdit(default)
    btn = QPushButton("…"); btn.setObjectName("MiniBtn"); btn.setFixedWidth(34)

    def pick():
        d = QFileDialog.getExistingDirectory(parent, label, edit.text() or "")
        if d:
            edit.setText(d)

    btn.clicked.connect(pick)
    row.addWidget(field_label(label, label_width))
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
