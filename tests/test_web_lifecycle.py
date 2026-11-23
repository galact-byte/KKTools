"""新版桌面退出与任务生命周期回归。"""
import threading
from launch_web import can_close
from web_bridge import KKToolsBridge


def test_close_waits_for_tasks_without_discarding_edits():
    bridge = KKToolsBridge()
    stop = threading.Event()
    bridge._tasks.start(lambda report: stop.wait(5))
    bridge.set_dirty_state(True)
    confirmations = []
    try:
        assert not can_close(bridge, lambda *args: confirmations.append(args) or True)
        assert not confirmations
        assert bridge.has_unsaved_edits()
    finally:
        stop.set()


def test_close_asks_before_discarding_edits():
    bridge = KKToolsBridge()
    bridge.set_dirty_state(True)
    assert not can_close(bridge, lambda *args: False)
    assert can_close(bridge, lambda *args: True)


def test_close_without_edits_needs_no_prompt():
    assert can_close(KKToolsBridge(), lambda *args: False)
