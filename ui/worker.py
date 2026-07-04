"""通用后台任务线程：把耗时操作（扫描、建索引、打包）放到子线程，避免界面卡死。"""

from __future__ import annotations

from typing import Any, Callable

from PyQt6.QtCore import QThread, pyqtSignal


class Worker(QThread):
    """运行一个返回值的可调用对象；通过信号回报进度/结果/异常。

    传入的 fn 可接受一个可选的 progress 回调（若签名里含 'progress' 形参，
    会自动注入，用于发射 progress 信号）。
    """

    progress = pyqtSignal(int, int, str)   # (当前, 总数, 描述)
    finished_ok = pyqtSignal(object)       # 结果
    failed = pyqtSignal(str)               # 错误信息

    def __init__(self, fn: Callable[..., Any], *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def _emit_progress(self, cur: int, total: int, desc: str = "") -> None:
        self.progress.emit(cur, total, desc)

    def run(self) -> None:  # noqa: D401
        try:
            import inspect

            kwargs = dict(self._kwargs)
            try:
                params = inspect.signature(self._fn).parameters
                if "progress" in params and "progress" not in kwargs:
                    kwargs["progress"] = self._emit_progress
            except (ValueError, TypeError):
                pass
            result = self._fn(*self._args, **kwargs)
            self.finished_ok.emit(result)
        except Exception as exc:  # noqa: BLE001 - 统一上报，避免线程内崩溃无声
            import traceback
            self.failed.emit(f"{exc}\n{traceback.format_exc()}")
