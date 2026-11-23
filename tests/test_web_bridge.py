"""WebView2 桥接层（web_bridge.py）与启动器（launch_web.py）的自动化回归测试。"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from core import settings, stego, updater
from launch_web import resolve_dist_dir
from web_bridge import KKToolsBridge


def _wait_task(bridge: KKToolsBridge, task_id: str, timeout: float = 10.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        res = bridge.poll_task(task_id)
        assert res["ok"] is True
        st = res["data"]
        if st["status"] in ("done", "error"):
            return st
        time.sleep(0.05)
    raise AssertionError(f"任务 {task_id} 超时未完成")


def test_config_roundtrip_preserves_legacy_theme_ids(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cfg_file = tmp_path / "config.json"
    monkeypatch.setattr(settings, "_CONFIG_PATH", cfg_file)
    bridge = KKToolsBridge()

    res = bridge.save_config({"theme": "tsukiyo_dark", "wallpaper_overlay": 42, "wallpaper_panel_alpha": 88})
    assert res["ok"] is True
    assert res["data"]["theme"] == "tsukiyo_dark"
    # 写回磁盘的是兼容旧版 PyQt6 的主题 ID
    raw_cfg = settings.load()
    assert raw_cfg["theme"] == "graphite_dark"
    assert raw_cfg["wallpaper_overlay"] == 42
    assert raw_cfg["wallpaper_panel_alpha"] == 88


def test_pack_and_unpack_roundtrip_via_bridge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "_CONFIG_PATH", tmp_path / "config.json")
    src = tmp_path / "src"
    src.mkdir()
    (src / "hello.txt").write_text("kktools-web-bridge", encoding="utf-8")

    out_pack = tmp_path / "packed"
    out_unpack = tmp_path / "unpacked"
    bridge = KKToolsBridge()

    start_pack = bridge.start_pack(
        {
            "sources": [str(src)],
            "outDir": str(out_pack),
            "archiveName": "demo_pkg",
            "stegoMode": "none",
            "passwords": ["secret123"],
            "splitMB": 0,
        }
    )
    assert start_pack["ok"] is True
    st_pack = _wait_task(bridge, start_pack["data"]["taskId"])
    assert st_pack["status"] == "done", st_pack
    archive_path = Path(st_pack["result"]["outputs"][0])
    assert archive_path.is_file()

    start_unpack = bridge.start_unpack(
        {
            "inputPath": str(archive_path),
            "outDir": str(out_unpack),
            "passwords": ["secret123"],
        }
    )
    assert start_unpack["ok"] is True
    st_unpack = _wait_task(bridge, start_unpack["data"]["taskId"])
    assert st_unpack["status"] == "done", st_unpack
    assert st_unpack["result"]["count"] >= 1
    assert any(p.name == "hello.txt" for p in out_unpack.rglob("*.txt"))


def test_unpack_missing_split_part_fails_strictly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "_CONFIG_PATH", tmp_path / "config.json")
    # 构造 3 卷分卷并故意删掉第 2 卷
    raw = tmp_path / "payload.zip"
    raw.write_bytes(b"A" * (3 * 1024 * 1024))
    parts = [Path(p) for p in stego.split_file(raw, 1.0, out_dir=tmp_path / "parts")]
    assert len(parts) >= 3
    parts[1].unlink()

    bridge = KKToolsBridge()
    res = bridge.start_unpack(
        {"inputPath": str(parts[0]), "outDir": str(tmp_path / "out"), "passwords": []}
    )
    assert res["ok"] is True
    st = _wait_task(bridge, res["data"]["taskId"])
    assert st["status"] == "error"
    assert st["error"]


def test_update_source_mode_guard_and_cleanup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    bridge = KKToolsBridge()
    # 源码模式不允许覆盖开发目录
    res = bridge.apply_update_and_restart()
    assert res["ok"] is False
    assert "源码运行模式" in res["error"]

    # 未安装临时下载在 cleanup_pending_update 时会被清理
    fake_file = tmp_path / "KKTools_new.exe"
    fake_file.write_bytes(b"binary")
    called: list[Path] = []
    monkeypatch.setattr(updater, "discard_download", lambda p, **kw: called.append(Path(p)))
    bridge._pending_update_artifact = fake_file
    bridge.cleanup_pending_update()
    assert called == [fake_file]
    assert bridge._pending_update_artifact is None


def test_dirty_state_and_dist_dir():
    bridge = KKToolsBridge()
    assert bridge.has_unsaved_edits() is False
    bridge.set_dirty_state(True)
    assert bridge.has_unsaved_edits() is True
    bridge.set_dirty_state(False)
    assert bridge.has_unsaved_edits() is False
    assert (resolve_dist_dir() / "index.html").is_file()
