"""打包页在两种输入模式之间的实际行为。"""

import os
import tempfile
import zipfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox, QPushButton  # noqa: E402

from core import settings, stego  # noqa: E402
from ui.pages.pack_page import PackPage  # noqa: E402


def test_selected_mode_packs_only_chosen_files_and_folder_mode_remains_default(monkeypatch):
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        folder = root / "mods"
        folder.mkdir()
        selected = folder / "yes.zipmod"
        excluded = folder / "no.zipmod"
        selected.write_bytes(b"yes")
        excluded.write_bytes(b"no")
        carrier = root / "image.png"
        carrier.write_bytes(b"cover")
        out = root / "shared.png"
        page = PackPage()
        page.show()
        monkeypatch.setattr(settings, "set_value", lambda *args: None)
        monkeypatch.setattr(page, "_run", lambda job, label: job())
        monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *args: ([str(selected)], ""))

        assert page.pack_by_folder.isChecked()
        page.pack_by_files.setChecked(True)
        assert not page.pack_folder.isVisible()
        assert page.pack_file_list.isVisible()
        page._add_pack_files()
        page.pack_carrier.setText(str(carrier))
        page.pack_out.setText(str(out))
        page._do_pack()

        with zipfile.ZipFile(out) as zf:
            assert zf.namelist() == ["yes.zipmod"]
        assert excluded.read_bytes() == b"no"

        page.pack_file_list.setCurrentRow(0)
        page._remove_pack_files()
        assert page.pack_file_list.count() == 0
        page.pack_by_folder.setChecked(True)
        assert page.pack_folder.isVisible()
        page.pack_folder.setText(str(folder))
        page.pack_out.setText(str(root / "all.png"))
        page._do_pack()
        with zipfile.ZipFile(root / "all.png") as zf:
            assert set(zf.namelist()) == {"yes.zipmod", "no.zipmod"}
        page.close()
    app.processEvents()


def test_selected_mode_requires_files_even_when_folder_path_is_set(monkeypatch):
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        page = PackPage()
        page.pack_folder.setText(str(root))
        page.pack_by_files.setChecked(True)
        warnings = []
        monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))
        page._do_pack()
        assert warnings and "文件" in warnings[0]
    app.processEvents()


def test_advanced_file_mode_can_scroll_to_pack_button():
    app = QApplication.instance() or QApplication([])
    page = PackPage()
    page.apply_ui_mode("advanced")
    page.pack_by_files.setChecked(True)
    page.resize(1040, 530)
    page.show()
    app.processEvents()

    assert page.height() == 530
    scroll = page.pack_scroll
    assert scroll.verticalScrollBar().maximum() > 0
    scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
    app.processEvents()
    button = next(b for b in page.findChildren(QPushButton) if b.text() == "开始打包伪装")
    y = button.mapTo(scroll.viewport(), button.rect().bottomLeft()).y()
    assert 0 <= y < scroll.viewport().height()
    page.close()


def test_selected_mode_flows_through_layered_pack(monkeypatch):
    if not stego.HAVE_PYZIPPER:
        return
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        chosen = root / "chosen.zipmod"
        chosen.write_bytes(b"chosen")
        carrier = root / "cover.png"
        carrier.write_bytes(b"cover")
        output = root / "layered.png"
        page = PackPage()
        page.apply_ui_mode("advanced")
        page.pack_by_files.setChecked(True)
        page.pack_file_list.addItem(str(chosen))
        page.pack_carrier.setText(str(carrier))
        page.pack_out.setText(str(output))
        page.seal_layers.setValue(2)
        page.seal_pwds.setText("inner,outer")
        monkeypatch.setattr(settings, "set_value", lambda *args: None)
        monkeypatch.setattr(page, "_run", lambda job, label: job())

        page._do_pack()

        restored = root / "restored"
        stego.extract_layered(output, restored, ["inner", "outer"])
        assert (restored / "chosen.zipmod").read_bytes() == b"chosen"
        assert chosen.read_bytes() == b"chosen"
    app.processEvents()
