"""六项审查缺陷的回归验证；所有卡片、Mod 和写回目标均位于 tmp_path。"""

from pathlib import Path
import zipfile

import msgpack
import pytest

from core import mod_index, settings, share, stego
from core.kk_card import BlockInfo, KoikatuCard, KKCardError, png_data_length
from test_kk_card import _build_synthetic_card, _make_png
from web_bridge import KKToolsBridge


def make_card(path, *, name="Same", guids=()):
    raw, _ = _build_synthetic_card()
    card = KoikatuCard.from_bytes(raw)
    card.update_parameter({"firstname": name})
    if guids:
        card.block_order.append(BlockInfo("KKEx", "1.0.0", 0, 0))
        card.blocks["KKEx"] = msgpack.packb({
            "com.bepis.sideloader.universalautoresolver": [1, {
                "info": [msgpack.packb({"ModID": guid}) for guid in guids],
            }],
        }, use_bin_type=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    card.save(path, backup=False)
    return path


def make_mod(path, guid):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("manifest.xml", f"<manifest><guid>{guid}</guid></manifest>")
    return mod_index.read_manifest(path)


@pytest.fixture
def bridge(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "_CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr(settings, "app_dir", lambda: tmp_path)
    return KKToolsBridge()


@pytest.mark.parametrize("extra_edits", [False, True], ids=["fields-only", "fields-and-preview"])
@pytest.mark.parametrize("overwrite", [False, True], ids=["save-as", "overwrite"])
def test_failed_save_keeps_edits_and_close_prompt_until_success(bridge, tmp_path, monkeypatch, overwrite, extra_edits):
    source = make_card(tmp_path / "source.png", name="Original")
    original = source.read_bytes()
    output = source if overwrite else tmp_path / "source_edited.png"
    cover = tmp_path / "cover.png"
    cover.write_bytes(_make_png((1, 2, 3), (10, 12)))
    payload = {"path": str(source), "outPath": str(output), "overwrite": overwrite,
               "parameter": {"firstname": "Edited"},
               "coverPath": str(cover) if extra_edits else ""}
    bridge.set_dirty_state(True)
    real_write = Path.write_bytes

    def fail_target(path, data):
        if path == output:
            raise PermissionError("测试写入失败")
        return real_write(path, data)

    monkeypatch.setattr(Path, "write_bytes", fail_target)
    result = bridge.save_card(payload)
    assert not result["ok"] and "测试写入失败" in result["error"]
    assert source.read_bytes() == original
    assert bridge.has_unsaved_edits()
    monkeypatch.setattr(Path, "write_bytes", real_write)
    result = bridge.save_card(payload)
    assert result["ok"], result
    saved = KoikatuCard.load(output)
    assert saved.parameter["firstname"] == "Edited"
    if extra_edits:
        from io import BytesIO
        from PIL import Image
        assert Image.open(BytesIO(saved.thumbnail)).convert('RGBA').tobytes() == Image.open(cover).convert('RGBA').tobytes()
    if overwrite:
        assert source.with_suffix(".png.bak").read_bytes() == original
    else:
        assert source.read_bytes() == original


@pytest.mark.parametrize("group", [False, True], ids=["shared-folder", "character-folder"])
def test_share_preserves_same_named_cards_and_existing_files(tmp_path, group):
    first = make_card(tmp_path / "a" / "same.png")
    second = make_card(tmp_path / "b" / "same.png")
    card = KoikatuCard.load(second)
    card.update_parameter({"nickname": "Different"})
    card.save(second, backup=False)
    output = tmp_path / "package"
    folder = output / ("Same" if group else "cards")
    folder.mkdir(parents=True)
    existing = folder / "same.png"
    existing.write_bytes(b"existing-user-file")

    report = share.build_share_package([str(first), str(second)], mod_index.ModIndex(), output, group_by_char=group)

    files = list(folder.glob("*.png"))
    assert existing.read_bytes() == b"existing-user-file"
    assert len(files) == 3
    assert {p.read_bytes() for p in files} == {b"existing-user-file", first.read_bytes(), second.read_bytes()}
    assert len(report["cards"]) == 2
    assert len({c["card"] for c in report["cards"]}) == 2
    readme = (output / "README.txt").read_text(encoding="utf-8")
    for entry in report["cards"]:
        assert (folder / entry["card"]).is_file()
        assert entry["card"] in readme


@pytest.mark.parametrize("group", [False, True], ids=["shared-folder", "character-folder"])
def test_share_includes_same_named_mods_and_deduplicates_reused_dependencies(tmp_path, group):
    index = mod_index.ModIndex()
    for number in (1, 2):
        entry = make_mod(tmp_path / f"mod-{number}" / "same.zipmod", f"guid.{number}")
        index.entries[entry.guid] = entry
    cards = [make_card(tmp_path / f"card-{number}.png", guids=index.entries) for number in (1, 2)]
    output = tmp_path / "package"
    folder = output / ("Same/mods" if group else "mods")
    folder.mkdir(parents=True)
    existing = folder / "same.zipmod"
    existing.write_bytes(b"existing-mod")

    report = share.build_share_package([str(p) for p in cards], index, output, group_by_char=group)

    assert existing.read_bytes() == b"existing-mod"
    copied = [p for p in folder.glob("*.zipmod") if p != existing]
    assert len(copied) == 2, "同一包内共用依赖只复制一次，但不同内容的同名 Mod 都须保留"
    assert {mod_index.read_manifest(p).guid for p in copied} == set(index.entries)
    assert set(report["copied_mods"]) == set(index.entries)
    assert report["total_missing"] == []
    assert all(c["copied"] == 2 for c in report["cards"])


@pytest.mark.parametrize("name", ["..", ".", "... ", "../..", "CON", "NUL.txt"])
def test_share_character_directories_stay_inside_selected_output(tmp_path, name):
    source = make_card(tmp_path / "source" / "card.png", name=name)
    output = tmp_path / "package"
    share.build_share_package([str(source)], mod_index.ModIndex(), output)
    files = list(output.rglob("*.png"))
    assert len(files) == 1
    assert files[0].read_bytes() == source.read_bytes()
    assert files[0].resolve().is_relative_to(output.resolve())
    assert files[0].parent != output, "特殊目录名应回退到正常子目录"
    assert not (tmp_path / "card.png").exists()


def test_join_rejects_missing_middle_part_before_touching_output(tmp_path):
    first = tmp_path / "data.bin.001"
    first.write_bytes(b"first")
    (tmp_path / "data.bin.003").write_bytes(b"third")
    output = tmp_path / "joined.bin"
    with pytest.raises(ValueError, match="002"):
        stego.join_parts(first, output)
    assert not output.exists()
    output.write_bytes(b"previous-output")
    with pytest.raises(ValueError, match="002"):
        stego.join_parts(first, output)
    assert output.read_bytes() == b"previous-output"
    assert first.read_bytes() == b"first"


def test_join_requires_existing_first_part_and_cannot_overwrite_parts(tmp_path):
    first = tmp_path / "data.bin.001"
    second = tmp_path / "data.bin.002"
    second.write_bytes(b"second")
    with pytest.raises((FileNotFoundError, ValueError)):
        stego.join_parts(first, tmp_path / "missing.bin")
    first.write_bytes(b"first")
    with pytest.raises(ValueError, match="001"):
        stego.join_parts(second, tmp_path / "wrong-start.bin")
    with pytest.raises(ValueError, match="覆盖"):
        stego.join_parts(first, second)
    assert first.read_bytes() == b"first"
    assert second.read_bytes() == b"second"


def test_split_join_roundtrip_in_numeric_order_past_999(tmp_path):
    source = tmp_path / "data.bin"
    payload = bytes(range(251)) * 4
    source.write_bytes(payload)
    parts = stego.split_file(source, 1 / (1024 * 1024), tmp_path / "parts")
    output = tmp_path / "joined.bin"
    assert len(parts) == 1004
    assert stego.join_parts(parts[0], output) == str(output)
    assert output.read_bytes() == payload
    assert source.read_bytes() == payload


@pytest.mark.parametrize("move", [False, True], ids=["copy", "move"])
@pytest.mark.parametrize("broken_kind", ["garbage", "plain-png", "truncated-card", "bad-kkex", "bad-kkex-tail", "bad-kkex-utf8", "bad-uar"])
def test_archive_aborts_before_any_file_operation_if_card_analysis_is_incomplete(tmp_path, move, broken_kind):
    entry = make_mod(tmp_path / "mods" / "one.zipmod", "guid.used")
    index = mod_index.ModIndex(entries={entry.guid: entry})
    valid = make_card(tmp_path / "valid.png")
    broken = tmp_path / "broken.png"
    if broken_kind == "garbage":
        broken.write_bytes(b"not-a-card")
    elif broken_kind == "plain-png":
        broken.write_bytes(_make_png((0, 0, 0), (4, 4)))
    elif broken_kind == "truncated-card":
        raw, _ = _build_synthetic_card()
        broken.write_bytes(raw[:-20])
    else:
        make_card(broken, guids=[entry.guid])
        card = KoikatuCard.load(broken)
        if broken_kind.startswith("bad-kkex"):
            card.blocks["KKEx"] = {
                "bad-kkex": b"\xc1",
                "bad-kkex-tail": msgpack.packb({}) + b"\xc1",
                "bad-kkex-utf8": b"\x81\xa1\xff\xc0",
            }[broken_kind]
            card._dirty = True
        else:
            card.set_block_dict("KKEx", {"com.bepis.sideloader.universalautoresolver": [1, {"info": [b"\xc1"]}]})
        card.save(broken, backup=False)
    original = Path(entry.path).read_bytes()
    archive = tmp_path / "archive"
    with pytest.raises((ValueError, KKCardError), match="broken.png"):
        mod_index.archive_unreferenced(index, [str(valid), str(broken)], archive, move=move)
    assert not archive.exists(), "全部分析成功前不得归档，包括前面已经成功分析的卡片"
    assert Path(entry.path).read_bytes() == original


@pytest.mark.parametrize("broken", [False, True], ids=["valid-scene", "broken-embedded-card"])
def test_archive_analyzes_scene_dependencies_or_stops_if_embedded_card_is_broken(tmp_path, broken):
    entry = make_mod(tmp_path / "mods" / "used.zipmod", "guid.used")
    index = mod_index.ModIndex(entries={entry.guid: entry})
    card = make_card(tmp_path / "character.png", guids=[entry.guid])
    raw = card.read_bytes()
    preview_size = png_data_length(raw)
    scene = tmp_path / "scene.png"
    embedded = raw[preview_size:]
    scene.write_bytes(raw[:preview_size] + b"KStudio" + (embedded[:-50] if broken else embedded))
    archive = tmp_path / "archive"
    if broken:
        with pytest.raises((ValueError, KKCardError), match="scene.png"):
            mod_index.archive_unreferenced(index, [str(scene)], archive, move=True)
    else:
        report = mod_index.archive_unreferenced(index, [str(scene)], archive, move=True)
        assert report["used"] == 1 and report["archived"] == 0
    assert Path(entry.path).is_file()
    assert not archive.exists()


@pytest.mark.parametrize("valid_first", [False, True], ids=["broken-first", "broken-after-valid"])
def test_archive_stops_when_scene_level_dependencies_cannot_be_decoded(tmp_path, valid_first):
    entry = make_mod(tmp_path / "mods" / "used.zipmod", "guid.used")
    index = mod_index.ModIndex(entries={entry.guid: entry})
    scene = tmp_path / "scene.png"
    signature = b"com.bepis.sideloader.universalautoresolver"
    valid = signature + msgpack.packb([1, {"info": []}]) if valid_first else b""
    scene.write_bytes(_make_png((0, 0, 0), (4, 4)) + b"KStudio" + valid + signature + b"\xc1")
    archive = tmp_path / "archive"
    with pytest.raises((ValueError, KKCardError), match="scene.png"):
        mod_index.archive_unreferenced(index, [str(scene)], archive, move=True)
    assert Path(entry.path).is_file()
    assert not archive.exists()


def test_archive_rejects_empty_selection(tmp_path):
    entry = make_mod(tmp_path / "mods" / "one.zipmod", "guid.used")
    index = mod_index.ModIndex(entries={entry.guid: entry})
    with pytest.raises(ValueError, match="卡片"):
        mod_index.archive_unreferenced(index, [], tmp_path / "archive", move=True)
    assert Path(entry.path).exists()


@pytest.mark.parametrize("move", [False, True], ids=["copy", "move"])
def test_archive_preserves_used_mods_and_archives_only_unused_after_full_analysis(tmp_path, move):
    entries = [make_mod(tmp_path / "mods" / f"{name}.zipmod", f"guid.{name}") for name in ("used", "unused")]
    index = mod_index.ModIndex(entries={e.guid: e for e in entries})
    card = make_card(tmp_path / "card.png", guids=["guid.used"])
    archive = tmp_path / "archive"
    report = mod_index.archive_unreferenced(index, [str(card)], archive, move=move)
    assert report["used"] == 1 and report["archived"] == 1
    assert Path(entries[0].path).is_file()
    assert (archive / "unused.zipmod").is_file()
    assert not (archive / "used.zipmod").exists()
    assert Path(entries[1].path).exists() is (not move)
