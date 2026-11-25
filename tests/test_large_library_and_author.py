"""大库性能优化与卡片作者提取的 TDD 回归测试。"""

from __future__ import annotations

import io
import struct
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import msgpack
import pytest
from PIL import Image

from core import card_scan, catalog, kk_card, mod_index, settings
from launch_web import start_local_server
from web_bridge import KKToolsBridge


def _make_png(width: int = 240, height: int = 336, color=(120, 180, 240)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="PNG")
    return buf.getvalue()


def _lz4_store_block(raw: bytes) -> bytes:
    """构造标准无匹配字面量 LZ4 raw block，用于测试 MessagePack-CSharp ExtType(99) 解压。"""
    out = bytearray()
    n = len(raw)
    if n < 15:
        out.append(n << 4)
    else:
        out.append(0xF0)
        rem = n - 15
        while rem >= 255:
            out.append(255)
            rem -= 255
        out.append(rem)
    out.extend(raw)
    return bytes(out)


def _make_card_bytes(
    *,
    marker: str = "【KoiKatuChara】",
    lastname: str = "白峰",
    firstname: str = "一乃",
    about: dict | None = None,
    kkex: dict | None = None,
    thumb_size: tuple[int, int] = (240, 336),
) -> bytes:
    thumb = _make_png(thumb_size[0], thumb_size[1])
    face = _make_png(64, 64, (200, 160, 220))
    param_ver = "0.0.6" if marker == "【KoiKatuCharaSun】" else "0.0.5"
    param = {
        "version": param_ver,
        "sex": 1,
        "lastname": lastname,
        "firstname": firstname,
        "nickname": firstname,
        "personality": 0,
        "bloodType": 0,
        "birthMonth": 5,
        "birthDay": 12,
        "clubActivities": 0,
        "voiceRate": 0.5,
        "awnser": {},
        "denial": {},
        "attribute": {},
    }
    blocks_list: list[tuple[str, str, bytes]] = [
        ("Custom", "0.0.0", msgpack.packb({"dummy": 1}, use_bin_type=True)),
        ("Coordinate", "0.0.0", msgpack.packb([], use_bin_type=True)),
        ("Parameter", param_ver, msgpack.packb(param, use_bin_type=True, use_single_float=True)),
        ("Status", "0.0.0", msgpack.packb({"version": "0.0.0"}, use_bin_type=True)),
    ]
    if about is not None:
        blocks_list.append(("About", "0.0.0", msgpack.packb(about, use_bin_type=True)))
    if kkex is not None:
        blocks_list.append(("KKEx", "3", msgpack.packb(kkex, use_bin_type=True)))

    blob = bytearray()
    lst = []
    for name, ver, payload in blocks_list:
        pos = len(blob)
        blob.extend(payload)
        lst.append({"name": name, "version": ver, "pos": pos, "size": len(payload)})

    lst_raw = msgpack.packb({"lstInfo": lst}, use_bin_type=True)
    out = io.BytesIO()
    out.write(thumb)
    out.write(struct.pack("<i", 100))
    out.write(kk_card.write_cs_string(marker))
    out.write(kk_card.write_cs_string("0.0.0"))
    out.write(struct.pack("<i", len(face)))
    out.write(face)
    out.write(struct.pack("<i", len(lst_raw)))
    out.write(lst_raw)
    out.write(struct.pack("<q", len(blob)))
    out.write(blob)
    return out.getvalue()


def _wait_task(bridge: KKToolsBridge, task_id: str, timeout: float = 10.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        res = bridge.poll_task(task_id)
        assert res["ok"] is True
        st = res["data"]
        if st["status"] in ("done", "error", "cancelled"):
            return st
        time.sleep(0.03)
    raise AssertionError(f"任务 {task_id} 超时")


def test_read_card_light_extracts_plain_and_lz4_author_and_about_userid(tmp_path: Path):
    # 1. 普通未压缩 marco.authordata（含 Anonymous / [Unknown] 过滤）
    plain_authors = msgpack.packb(["[Unknown]", "AliceMaker", "BobEdit", "Anonymous"], use_bin_type=True)
    p1 = tmp_path / "plain_author.png"
    p1.write_bytes(_make_card_bytes(kkex={"marco.authordata": [1, {"Authors": plain_authors}]}))
    info1 = kk_card.read_card_light(p1, include_thumbnail=False)
    assert info1.thumbnail == b""
    assert info1.author == "AliceMaker"
    assert list(info1.author_history) == ["AliceMaker", "BobEdit"]
    assert info1.author_source == "card"

    # 2. MessagePack-CSharp ExtType(99) LZ4 压缩 marco.authordata
    raw_authors_mp = msgpack.packb(["KuroCreator", "SecondAuthor"], use_bin_type=True)
    lz4_payload = b"\xd2" + struct.pack(">i", len(raw_authors_mp)) + _lz4_store_block(raw_authors_mp)
    ext_bytes = msgpack.packb(msgpack.ExtType(99, lz4_payload), use_bin_type=True)
    p2 = tmp_path / "lz4_author.png"
    p2.write_bytes(_make_card_bytes(kkex={"marco.authordata": [1, {"Authors": ext_bytes}]}))
    info2 = kk_card.read_card_light(p2, include_thumbnail=False)
    assert info2.author == "KuroCreator"
    assert list(info2.author_history) == ["KuroCreator", "SecondAuthor"]
    assert info2.author_source == "card"

    # 3. KKS 无 marco.authordata 但有 About.userID
    p3 = tmp_path / "kks_userid.png"
    p3.write_bytes(
        _make_card_bytes(
            marker="【KoiKatuCharaSun】",
            about={"version": "0.0.0", "language": 0, "userID": "b7e93219-a86d-4526-88bc-df7af5097f48", "dataID": "1111"},
        )
    )
    info3 = kk_card.read_card_light(p3, include_thumbnail=False)
    assert info3.user_id == "b7e93219-a86d-4526-88bc-df7af5097f48"
    assert info3.author == "KKSID:b7e93219"
    assert info3.author_source == "userid"

    # 4. 放在乱七八糟子目录里的无作者老 1 代卡：不得用父目录名推测作者
    messy_dir = tmp_path / "随机下载文件夹_999"
    messy_dir.mkdir()
    p4 = messy_dir / "old_kk.png"
    p4.write_bytes(_make_card_bytes())
    info4 = kk_card.read_card_light(p4, include_thumbnail=False)
    assert info4.author == ""
    assert info4.author_source == ""


def test_catalog_author_override_and_csv_export(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "app_dir", lambda: tmp_path)
    card_path = tmp_path / "chara.png"
    card_path.write_bytes(_make_card_bytes())

    assert catalog.get_author_override(card_path) == ""
    assert catalog.set_author_override(card_path, "千夏社") == "千夏社"
    assert catalog.get_author_override(card_path) == "千夏社"

    out_dir = tmp_path / "export"
    csv_file = catalog.export_data("list", [str(card_path)], out_dir, "csv")
    csv_text = csv_file.read_text(encoding="utf-8-sig")
    assert "作者" in csv_text.splitlines()[0]
    assert "千夏社" in csv_text

    # 清空覆盖后恢复为空
    assert catalog.set_author_override(card_path, "   ") == ""
    assert catalog.get_author_override(card_path) == ""


def test_scan_dir_fast_sqlite_cache_ignores_non_card_dirs_and_supports_cancel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "app_dir", lambda: tmp_path / "appdata")
    root = tmp_path / "game_root"
    (root / "UserData" / "chara" / "female").mkdir(parents=True)
    (root / "mods").mkdir(parents=True)
    (root / "abdata").mkdir(parents=True)
    (root / "BepInEx").mkdir(parents=True)

    c1 = root / "UserData" / "chara" / "female" / "a.png"
    c1.write_bytes(_make_card_bytes(lastname="星野", firstname="美咲"))
    # 这些非卡片巨目录内的 PNG 在递归扫描时必须跳过
    (root / "mods" / "noise.png").write_bytes(_make_png(16, 16))
    (root / "abdata" / "noise.png").write_bytes(_make_png(16, 16))
    (root / "BepInEx" / "noise.png").write_bytes(_make_png(16, 16))

    calls = 0
    real_light = kk_card.read_card_light

    def spy_light(path, *args, **kwargs):
        nonlocal calls
        calls += 1
        return real_light(path, *args, **kwargs)

    monkeypatch.setattr(card_scan, "read_card_light", spy_light)

    # 首次冷扫：只扫到 UserData 里的卡，跳过 mods/abdata/BepInEx
    items1 = card_scan.scan_dir_fast(root, recursive=True, workers=4)
    assert len(items1) == 1
    assert items1[0].name == "星野美咲"
    assert calls == 1

    # 二次热扫：全部命中 SQLite 缓存，0 次打开 PNG
    calls = 0
    items2 = card_scan.scan_dir_fast(root, recursive=True, workers=4)
    assert len(items2) == 1
    assert items2[0].name == "星野美咲"
    assert calls == 0

    # 修改文件内容后：自动失效缓存并重新解析
    c1.write_bytes(_make_card_bytes(lastname="新名字", firstname="测试"))
    items3 = card_scan.scan_dir_fast(root, recursive=True, workers=4)
    assert calls == 1
    assert items3[0].name == "新名字测试"

    # 取消事件生效
    ev = threading.Event()
    ev.set()
    with pytest.raises(card_scan.ScanCancelled):
        card_scan.scan_dir_fast(root, recursive=True, cancel_event=ev)


def test_async_scan_and_http_thumbnail_whitelist_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "app_dir", lambda: tmp_path / "appdata")
    monkeypatch.setattr(settings, "_CONFIG_PATH", tmp_path / "appdata" / "config.json")
    (tmp_path / "appdata").mkdir(parents=True, exist_ok=True)

    cards_dir = tmp_path / "cards"
    cards_dir.mkdir()
    plain_authors = msgpack.packb(["SenseiAuthor"], use_bin_type=True)
    card_file = cards_dir / "heroine.png"
    card_file.write_bytes(
        _make_card_bytes(
            thumb_size=(600, 840),
            kkex={"marco.authordata": [1, {"Authors": plain_authors}]},
        )
    )

    bridge = KKToolsBridge()
    start_res = bridge.start_scan_directory(str(cards_dir), recursive=False)
    assert start_res["ok"] is True
    st = _wait_task(bridge, start_res["data"]["taskId"])
    assert st["status"] == "done", st
    items = st["result"]["items"]
    assert len(items) == 1
    item = items[0]
    assert item["author"] == "SenseiAuthor"
    assert item["authorSource"] == "card"
    # 关键：不把 base64 缩略图塞进 JSON，而是返回按需 HTTP 缩略图路径
    assert item["thumbnailUrl"].startswith("/thumb/")
    assert "data:image" not in item["thumbnailUrl"]

    server, port = start_local_server(bridge)
    try:
        # 合法白名单缩略图请求返回 200 且经过缩放缓存
        url = f"http://127.0.0.1:{port}{item['thumbnailUrl']}"
        with urllib.request.urlopen(url, timeout=5) as resp:
            assert resp.status == 200
            ctype = resp.headers.get("Content-Type", "")
            assert ctype in ("image/webp", "image/png")
            assert "max-age" in resp.headers.get("Cache-Control", "")
            body = resp.read()
        with Image.open(io.BytesIO(body)) as im:
            assert im.width <= 360

        # 未授权/非法 token 拒绝返回 404
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/thumb/not_registered_token", timeout=5)
        assert exc_info.value.code == 404
    finally:
        server.shutdown()
        server.server_close()


def test_mod_index_reports_real_total_and_serialize_uses_cached_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import zipfile

    monkeypatch.setattr(settings, "app_dir", lambda: tmp_path / "appdata")
    (tmp_path / "appdata").mkdir(parents=True, exist_ok=True)
    mods_dir = tmp_path / "mods"
    mods_dir.mkdir()
    for i in range(3):
        zp = mods_dir / f"m{i}.zipmod"
        with zipfile.ZipFile(zp, "w") as zf:
            zf.writestr(
                "manifest.xml",
                f"<manifest><guid>g.{i}</guid><name>Mod {i}</name><version>1.0</version><author>Auth</author></manifest>",
            )

    seen_progress: list[tuple[int, int, str]] = []
    idx = mod_index.ModIndex().build(
        [str(mods_dir)],
        progress=lambda cur, total, name: seen_progress.append((cur, total, name)),
    )
    assert idx.count == 3
    assert any(tot == 3 for _, tot, _ in seen_progress)

    # _serialize_mods 直接复用 idx.files 里的 size，不再对每个文件重新 stat
    bridge = KKToolsBridge()
    bridge._mod_index = idx
    orig_stat = Path.stat
    stat_calls = 0

    def spy_stat(self, *args, **kwargs):
        nonlocal stat_calls
        if self.suffix == ".zipmod":
            stat_calls += 1
        return orig_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", spy_stat)
    res = bridge.get_cached_mods()
    assert res["ok"] is True
    assert res["data"]["total"] == 3
    assert stat_calls == 0
