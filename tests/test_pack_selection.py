"""选择文件打包的行为回归。"""

import tempfile
import zipfile
from pathlib import Path

import pytest

from core import stego


def test_pack_selected_files_only_and_keep_originals():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        mods = root / "mods"
        mods.mkdir()
        selected = mods / "keep-out-of-game.zipmod"
        excluded = mods / "leave-alone.zipmod"
        selected.write_bytes(b"chosen")
        excluded.write_bytes(b"other")
        output = root / "selected.zip"

        stego.pack_folder([selected], output)

        with zipfile.ZipFile(output) as zf:
            assert zf.namelist() == ["keep-out-of-game.zipmod"]
            assert zf.read("keep-out-of-game.zipmod") == b"chosen"
        assert selected.read_bytes() == b"chosen"
        assert excluded.read_bytes() == b"other"


def test_selected_files_roundtrip_disguised_and_encrypted():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        chosen = root / "one.zipmod"
        chosen.write_bytes(b"mod content")
        carrier = root / "cover.png"
        carrier.write_bytes(b"image-prefix")
        out = root / "shared.png"
        password = "secret" if stego.HAVE_PYZIPPER else None

        stego.pack_and_disguise([chosen], carrier, out, password=password)
        restored = root / "restored"
        stego.extract_archive(out, restored, passwords=[password] if password else None)

        assert out.read_bytes().startswith(b"image-prefix")
        assert (restored / chosen.name).read_bytes() == b"mod content"


def test_selected_files_roundtrip_layered():
    if not stego.HAVE_PYZIPPER:
        pytest.skip("pyzipper not installed")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        chosen = root / "one.zipmod"
        chosen.write_bytes(b"mod content")
        out = root / "layered.dat"

        stego.pack_layered([chosen], out, ["inner", "outer"])
        restored = root / "restored"
        stego.extract_layered(out, restored, ["inner", "outer"])

        assert (restored / chosen.name).read_bytes() == b"mod content"
        assert chosen.read_bytes() == b"mod content"


def test_missing_file_fails_before_writing_output():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        existing = root / "ok.zipmod"
        existing.write_bytes(b"ok")
        output = root / "out.zip"

        with pytest.raises(FileNotFoundError):
            stego.pack_folder([existing, root / "gone.zipmod"], output)

        assert not output.exists()


def test_duplicate_archive_names_fail_before_writing_output():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for dirname in ("a", "b"):
            folder = root / dirname
            folder.mkdir()
            (folder / "same.zipmod").write_bytes(dirname.encode())
        output = root / "out.zip"

        with pytest.raises(ValueError, match="同名"):
            stego.pack_folder([root / "a" / "same.zipmod", root / "b" / "same.zipmod"], output)

        assert not output.exists()


def test_folder_pack_keeps_relative_directories():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        mods = root / "mods"
        (mods / "sub").mkdir(parents=True)
        (mods / "sub" / "a.zipmod").write_bytes(b"a")
        output = root / "all.zip"

        stego.pack_folder(mods, output)

        with zipfile.ZipFile(output) as zf:
            assert zf.namelist() == ["sub/a.zipmod"]


def test_layered_sidecar_cannot_overwrite_input(tmp_path):
    if not stego.HAVE_PYZIPPER:
        pytest.skip("pyzipper not installed")
    output = tmp_path / "shared.png"
    chosen = tmp_path / "shared.png.kkseal.json"
    chosen.write_bytes(b"original selected file")
    with pytest.raises(ValueError, match="覆盖"):
        stego.pack_layered([chosen], output, ["inner", "outer"])
    assert chosen.read_bytes() == b"original selected file"
    assert not output.exists()


def test_missing_carrier_does_not_truncate_output(tmp_path):
    source = tmp_path / "one.zipmod"
    source.write_bytes(b"source")
    output = tmp_path / "existing.png"
    output.write_bytes(b"existing result")
    with pytest.raises(FileNotFoundError):
        stego.pack_and_disguise([source], tmp_path / "missing.png", output)
    assert output.read_bytes() == b"existing result"


def test_refuse_to_overwrite_selected_file_or_carrier():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        chosen = root / "mod.zipmod"
        chosen.write_bytes(b"original mod")
        carrier = root / "cover.png"
        carrier.write_bytes(b"original cover")

        with pytest.raises(ValueError):
            stego.pack_folder([chosen], chosen)
        with pytest.raises(ValueError):
            stego.pack_and_disguise([chosen], carrier, carrier)
        if stego.HAVE_PYZIPPER:
            with pytest.raises(ValueError):
                stego.pack_layered([chosen], chosen, ["inner", "outer"])

        assert chosen.read_bytes() == b"original mod"
        assert carrier.read_bytes() == b"original cover"
