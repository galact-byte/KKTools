"""后端大库扫描、分页和任务生命周期的行为回归。"""
from __future__ import annotations

import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path

import pytest

from core import card_scan, catalog, settings
from test_large_library_and_author import _make_card_bytes, _wait_task
from web_bridge import KKToolsBridge, _TaskManager


@pytest.fixture
def library(tmp_path, monkeypatch):
    app = tmp_path / 'app'
    app.mkdir()
    monkeypatch.setattr(settings, 'app_dir', lambda: app)
    monkeypatch.setattr(settings, '_CONFIG_PATH', app / 'config.json')
    root = tmp_path / 'cards'
    root.mkdir()
    return root


def _cards(root, count):
    data = _make_card_bytes()
    for i in range(count):
        (root / f'{i:04}.png').write_bytes(data)


def test_preexisting_index_refreshes_metadata_after_parser_revision(library, monkeypatch):
    _cards(library, 1)
    card_scan.scan_dir_fast(library)
    db = settings.app_dir() / 'card_index.sqlite3'
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE card_index SET game='STALE'")
        conn.execute('PRAGMA user_version=0')
    calls = []
    read = card_scan.read_card_light
    def track(*args, **kwargs):
        calls.append(args[0])
        return read(*args, **kwargs)
    monkeypatch.setattr(card_scan, 'read_card_light', track)
    assert card_scan.scan_dir_fast(library)[0].game == 'KK'
    assert len(calls) == 1


def test_overlapping_scans_cannot_erase_newer_directory_members(library, monkeypatch):
    _cards(library, 1)
    entered = threading.Event()
    release = threading.Event()
    read = card_scan.read_card_light
    call_lock = threading.Lock()
    calls = 0
    def delayed_first(*args, **kwargs):
        nonlocal calls
        with call_lock:
            calls += 1
            first = calls == 1
        if first:
            entered.set()
            assert release.wait(5)
        return read(*args, **kwargs)
    monkeypatch.setattr(card_scan, 'read_card_light', delayed_first)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(card_scan.scan_dir_fast, library)
        try:
            assert entered.wait(3)
            _cards(library, 2)
            second = pool.submit(card_scan.scan_dir_fast, library)
            try:
                second.result(timeout=.2)
            except TimeoutError:
                pass
        finally:
            release.set()
        first.result(timeout=5)
        second.result(timeout=5)
    assert card_scan.query_index_page(library)['total'] == 2


def test_deleted_file_at_progress_boundary_does_not_abort_scan(library, monkeypatch):
    _cards(library, 2)
    collect = card_scan._collect_png_entries

    def discover_then_remove(*args, **kwargs):
        entries = collect(*args, **kwargs)
        entries[-1][0].unlink()
        return entries

    monkeypatch.setattr(card_scan, '_collect_png_entries', discover_then_remove)
    progress = []
    items = card_scan.scan_dir_fast(library, workers=1, progress=lambda *v: progress.append(v))
    assert [Path(i.path).name for i in items] == ['0000.png']
    assert progress[-1][0:2] == (2, 2)


def test_cancelled_scan_commits_completed_work_for_resume(library, monkeypatch):
    _cards(library, 45)
    cancelled = threading.Event()

    def cancel_after_work(current, total, message):
        if current >= 25:
            cancelled.set()

    with pytest.raises(card_scan.ScanCancelled):
        card_scan.scan_dir_fast(library, workers=1, progress=cancel_after_work, cancel_event=cancelled)
    parsed = []
    read = card_scan.read_card_light

    def track(path, **kwargs):
        parsed.append(path)
        return read(path, **kwargs)

    monkeypatch.setattr(card_scan, 'read_card_light', track)
    assert len(card_scan.scan_dir_fast(library, workers=1)) == 45
    assert len(parsed) <= 20


def test_scan_limits_waiting_parse_jobs(library, monkeypatch):
    _cards(library, 60)

    class BudgetExecutor(ThreadPoolExecutor):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.outstanding = 0
            self.guard = threading.Lock()

        def submit(self, fn, *args, **kwargs):
            with self.guard:
                self.outstanding += 1
                if self.outstanding > 8:
                    raise RuntimeError('解析等待队列超过测试预算')
            future = super().submit(fn, *args, **kwargs)
            def completed(_):
                with self.guard:
                    self.outstanding -= 1
            future.add_done_callback(completed)
            return future

    monkeypatch.setattr(card_scan, 'ThreadPoolExecutor', BudgetExecutor)
    assert len(card_scan.scan_dir_fast(library, workers=2)) == 60


def test_index_pages_are_scoped_filterable_and_remove_stale_members(library):
    _cards(library, 5)
    sub = library / 'sub'
    sub.mkdir()
    _cards(sub, 2)
    other = library.parent / 'other'
    other.mkdir()
    _cards(other, 1)
    card_scan.scan_dir_fast(other)
    card_scan.scan_dir_fast(library)
    card_scan.scan_dir_fast(library, recursive=True)
    page = card_scan.query_index_page(library, offset=1, limit=2)
    assert page['total'] == 5
    assert [Path(i.path).name for i in page['items']] == ['0001.png', '0002.png']
    assert page['hasMore'] is True
    assert card_scan.query_index_page(library, recursive=True)['total'] == 7
    catalog.set_author_override(library / '0002.png', 'ManualMaker')
    catalog.set_tags(library / '0002.png', ['检索标签'])
    assert card_scan.query_index_page(library, author='ManualMaker')['total'] == 1
    assert card_scan.query_index_page(library, search='检索标签')['total'] == 1
    assert card_scan.query_index_page(library, card_type='scene')['total'] == 0
    (library / '0001.png').unlink()
    card_scan.scan_dir_fast(library)
    assert card_scan.query_index_page(library)['total'] == 4
    with pytest.raises(ValueError):
        card_scan.query_index_page(library, offset=-1)
    with pytest.raises(ValueError):
        card_scan.query_index_page(library, limit=501)


def test_paged_scan_returns_summary_and_pages_keep_stable_ids(library):
    _cards(library, 6)
    bridge = KKToolsBridge()
    started = bridge.start_scan_directory(str(library), paged=True)
    state = _wait_task(bridge, started['data']['taskId'])
    assert state['status'] == 'done', state
    assert state['result']['total'] == 6
    assert 'items' not in state['result']
    page1 = bridge.query_card_page(str(library), {'offset': 0, 'limit': 3})
    page2 = bridge.query_card_page(str(library), {'offset': 1, 'limit': 1})
    assert page1['ok'] and page2['ok']
    assert page1['data']['items'][1]['id'] == page2['data']['items'][0]['id']
    assert len(page1['data']['items']) == 3
    assert page1['data']['total'] == 6
    for options in ({'limit': 0}, {'offset': -1}, {'limit': 'many'}, {'limit': True}):
        assert bridge.query_card_page(str(library), options)['ok'] is False


def test_pages_use_only_requested_local_metadata(library, monkeypatch):
    _cards(library, 4)
    bridge = KKToolsBridge()
    bridge.scan_directory(str(library))
    catalog.set_tags(library / '0001.png', ['本地'])
    catalog.set_author_override(library / '0001.png', 'LocalAuthor')
    def reject_full_table():
        raise AssertionError('分页不能全量加载本地标签或作者表')
    monkeypatch.setattr(catalog, 'all_tags', reject_full_table)
    monkeypatch.setattr(catalog, 'all_author_overrides', reject_full_table)
    page = bridge.query_card_page(str(library), {'offset': 1, 'limit': 1})
    assert page['ok'], page
    assert page['data']['items'][0]['author'] == 'LocalAuthor'
    assert page['data']['items'][0]['tags'] == ['本地']


def test_legacy_scans_release_previous_large_result(library):
    _cards(library, 3)
    bridge = KKToolsBridge()
    ids = []
    for _ in range(3):
        task = bridge.start_scan_directory(str(library))['data']['taskId']
        ids.append(task)
        assert len(_wait_task(bridge, task)['result']['items']) == 3
    assert bridge.poll_task(ids[0])['data']['result'] is None
    assert bridge.poll_task(ids[0])['data']['resultExpired'] is True
    assert len(bridge.poll_task(ids[-1])['data']['result']['items']) == 3
    assert bridge.release_task(ids[-1])['ok'] is True
    assert bridge.poll_task(ids[-1])['ok'] is False


def test_task_release_never_discards_a_running_task():
    bridge = KKToolsBridge()
    stop = threading.Event()
    task = bridge._tasks.start(lambda report: stop.wait(5))
    try:
        assert bridge.release_task(task)['ok'] is False
        assert bridge.has_running_tasks()
    finally:
        stop.set()
    _wait_task(bridge, task)
    assert bridge.cancel_task(task)['ok'] is False
    assert bridge.release_task(task)['ok'] is True


def test_completed_task_records_are_bounded_and_expire(monkeypatch):
    manager = _TaskManager(max_completed=2, retention_seconds=10)
    ids = []
    for _ in range(4):
        task = manager.start(lambda report: 'small-result')
        ids.append(task)
        deadline = time.monotonic() + 3
        while manager.get(task)['status'] == 'running':
            assert time.monotonic() < deadline
            time.sleep(.005)
    assert manager.get(ids[0]) is None
    assert manager.get(ids[-1])['result'] == 'small-result'
    clock = time.monotonic()
    monkeypatch.setattr('web_bridge.time.monotonic', lambda: clock + 11)
    assert manager.get(ids[-1]) is None
