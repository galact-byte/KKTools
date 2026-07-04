"""全局日志总线：各页面调用 log() 写日志，运行日志页订阅显示。"""

from __future__ import annotations

import time

from PyQt6.QtCore import QObject, pyqtSignal


class _LogBus(QObject):
    message = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.history: list[str] = []

    def log(self, text: str) -> None:
        line = f"[{time.strftime('%H:%M:%S')}] {text}"
        self.history.append(line)
        if len(self.history) > 2000:
            self.history = self.history[-1500:]
        self.message.emit(line)


bus = _LogBus()


def log(text: str) -> None:
    bus.log(text)
