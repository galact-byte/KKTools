"""诊断日志应跨窗口关闭保留，并记录真正的失败堆栈。"""

import logging
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from core import diagnostics


@pytest.fixture
def log_path(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    old_sys, old_thread = sys.excepthook, threading.excepthook
    path = diagnostics.initialize()
    yield path
    sys.excepthook, threading.excepthook = old_sys, old_thread
    logger = logging.getLogger("kktools")
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)


def test_operation_log_persists_as_utf8(log_path):
    from web_bridge import KKToolsBridge
    KKToolsBridge().record_log('info', 'PACK', '打包操作完成：中文.zipmod')
    text = log_path.read_text(encoding="utf-8")
    assert "打包操作完成：中文.zipmod" in text
    assert "Python" in text
    assert "KKTools" in text


def test_worker_failure_records_traceback_before_ui_callback(log_path):
    import time
    from web_bridge import _TaskManager

    def failing_job(report):
        raise ValueError("worker-test-error")

    tasks = _TaskManager()
    task_id = tasks.start(failing_job)
    deadline = time.monotonic() + 5
    while tasks.get(task_id)['status'] == 'running':
        assert time.monotonic() < deadline
        time.sleep(0.01)
    text = log_path.read_text(encoding="utf-8")
    assert "Traceback" in text
    assert "failing_job" in text
    assert "ValueError: worker-test-error" in text


def test_uncaught_startup_and_thread_errors_survive_process_exit(tmp_path):
    code = '''
from core import diagnostics
import threading
diagnostics.initialize()
def fail():
    raise RuntimeError("thread-test-error")
t = threading.Thread(target=fail)
t.start()
t.join()
raise ValueError("startup-test-error")
'''
    env = dict(os.environ, LOCALAPPDATA=str(tmp_path))
    result = subprocess.run([sys.executable, "-c", code], env=env,
                            cwd=Path(__file__).resolve().parents[1], capture_output=True, timeout=15)
    assert result.returncode != 0
    text = "\n".join(p.read_text(encoding="utf-8") for p in tmp_path.rglob("*.log"))
    assert "RuntimeError: thread-test-error" in text
    assert "ValueError: startup-test-error" in text
    assert "Traceback" in text


def test_log_directory_opens_without_removing_log(log_path, monkeypatch):
    import web_bridge
    bridge = web_bridge.KKToolsBridge()
    bridge.record_log('info', 'TEST', '保留此条操作记录')
    opened = []
    monkeypatch.setattr(web_bridge.os, 'startfile', lambda path: opened.append(path))
    assert bridge.open_log_directory()['ok']
    assert Path(opened[0]) == log_path.parent
    assert "保留此条操作记录" in log_path.read_text(encoding="utf-8")


def test_handled_card_error_also_records_diagnostics(log_path, tmp_path, monkeypatch):
    from web_bridge import KKToolsBridge
    invalid = tmp_path / "broken.png"
    invalid.write_bytes(b"not a PNG card")
    assert not KKToolsBridge().load_card(str(invalid))['ok']
    text = log_path.read_text(encoding="utf-8")
    assert "Traceback" in text
    assert "KKCardError" in text


def test_windowed_process_without_standard_streams_still_logs(tmp_path):
    code = '''
from core import diagnostics
import sys
sys.stdout = sys.stderr = None
diagnostics.initialize()
raise RuntimeError("windowed-test-error")
'''
    result = subprocess.run([sys.executable, "-c", code],
                            env=dict(os.environ, LOCALAPPDATA=str(tmp_path)),
                            cwd=Path(__file__).resolve().parents[1], capture_output=True, timeout=15)
    assert result.returncode != 0
    logs = list(tmp_path.rglob("*.log"))
    assert len(logs) == 1
    assert "RuntimeError: windowed-test-error" in logs[0].read_text(encoding="utf-8")


def test_rotation_keeps_recent_records(log_path):
    handler = logging.getLogger("kktools").handlers[0]
    handler.maxBytes = 256
    for i in range(30):
        logging.getLogger("kktools").info("record-%s %s", i, "x" * 80)
    assert "record-29" in log_path.read_text(encoding="utf-8")
    assert Path(str(log_path) + ".1").exists()
    assert len(list(log_path.parent.glob(log_path.name + "*"))) == 3


def test_unwritable_primary_log_directory_falls_back(tmp_path, monkeypatch):
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("blocked")
    fallback = tmp_path / "fallback"
    fallback.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(blocked))
    monkeypatch.setattr(diagnostics.tempfile, "gettempdir", lambda: str(fallback))
    old_sys, old_thread = sys.excepthook, threading.excepthook
    try:
        path = diagnostics.initialize()
        assert path.is_relative_to(fallback)
        assert "KKTools" in path.read_text(encoding="utf-8")
    finally:
        sys.excepthook, threading.excepthook = old_sys, old_thread
        for handler in logging.getLogger("kktools").handlers[:]:
            handler.close()
            logging.getLogger("kktools").removeHandler(handler)
