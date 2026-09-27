"""本地诊断日志：在 Qt 导入前启动，保留操作记录和异常堆栈。"""

from __future__ import annotations

import json
import logging
import os
import platform
import sys
import tempfile
import threading
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

logger = logging.getLogger("kktools")
_log_path: Path | None = None


def log_path() -> Path | None:
    return _log_path


def record_exception(exc_type, value, tb) -> None:
    logger.critical("未处理异常", exc_info=(exc_type, value, tb))
    if sys.stderr is not None:
        sys.__excepthook__(exc_type, value, tb)


def _thread_exception(args) -> None:
    record_exception(args.exc_type, args.exc_value, args.exc_traceback)


def initialize() -> Path | None:
    """首选用户本地目录；不可写时回退系统临时目录，不写 EXE 或游戏盘。"""
    global _log_path
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    _log_path = None
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    filename = f"kktools-{datetime.now():%Y%m%d-%H%M%S-%f}-{os.getpid()}.log"
    for folder in (base / "KKTools" / "logs", Path(tempfile.gettempdir()) / "KKTools" / "logs"):
        try:
            folder.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(folder / filename, maxBytes=2 * 1024 * 1024,
                                          backupCount=2, encoding="utf-8")
        except OSError:
            continue
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(handler)
        _log_path = folder / filename
        # 每次运行单独写文件，避免多开时争抢轮转；保留最近十次运行。
        sessions = sorted(folder.glob("kktools-*.log"), key=lambda p: p.name, reverse=True)
        for old in sessions[10:]:
            for path in (old, Path(str(old) + ".1"), Path(str(old) + ".2")):
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass  # 另一实例仍持有文件时留待下次清理。
        break
    if _log_path is None:
        logger.addHandler(logging.NullHandler())
    sys.excepthook = record_exception
    threading.excepthook = _thread_exception
    try:
        info = json.loads((Path(__file__).resolve().parent / "build_info.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        info = {"version": "development", "commit": "local"}
    logger.info("KKTools 启动 | 版本 %s | 提交 %s | Python %s | %s | frozen=%s",
                info.get("version"), info.get("commit"), platform.python_version(),
                platform.platform(), bool(getattr(sys, "frozen", False)))
    return _log_path
