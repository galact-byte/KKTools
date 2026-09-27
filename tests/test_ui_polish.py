"""界面细节：控件状态可辨认、表单对齐、空列表有提示、工具栏不过载。"""

import os
import re
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint  # noqa: E402
from PyQt6.QtWidgets import QApplication, QLineEdit, QListWidget, QPushButton  # noqa: E402

import pytest  # noqa: E402

from core import settings  # noqa: E402
from core import theme as T  # noqa: E402
from ui import theme_qss  # noqa: E402


_APP = None


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path, monkeypatch):
    """页面构造会读写配置（如库身份），测试里不能碰真实 config.json。"""
    monkeypatch.setattr(settings, "_CONFIG_PATH", tmp_path / "config.json")


def _app():
    # 保持模块级引用：QApplication 被回收后再建新实例会让 Qt 直接崩溃
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def _rule(qss: str, selector: str) -> str:
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", qss)
    assert m, f"缺少样式规则: {selector}"
    return m.group(1)


def test_checked_checkbox_draws_a_checkmark_in_every_theme():
    for th in T.list_themes():
        body = _rule(theme_qss.build_qss(th), "QCheckBox::indicator:checked")
        m = re.search(r"image:\s*url\(([^)]+)\)", body)
        assert m, f"{th.id}: 选中态只有底色，没有对勾"
        svg = Path(m.group(1))
        assert svg.exists() and "<path" in svg.read_text(encoding="utf-8")


def test_disabled_danger_button_drops_its_red_outline():
    qss = theme_qss.build_qss(T.find_theme("ink_light"))
    body = _rule(qss, 'QPushButton[accent="danger"]:disabled')
    assert "border" in body and "color" in body


def test_empty_list_shows_hint_and_hides_it_once_filled():
    from ui.widgets import install_empty_hint

    app = _app()
    view = QListWidget(); view.resize(300, 160)
    install_empty_hint(view, "拖入文件到这里")
    view.show(); app.processEvents()
    empty = view.viewport().grab().toImage()
    bare = QListWidget(); bare.resize(300, 160); bare.show(); app.processEvents()
    assert empty != bare.viewport().grab().toImage(), "空列表没有画出提示"
    view.addItem("a.zipmod"); bare.addItem("a.zipmod"); app.processEvents()
    assert view.viewport().grab().toImage() == bare.viewport().grab().toImage(), "有内容时仍在画提示"


def test_pack_form_fields_start_at_one_column():
    from ui.pages.pack_page import PackPage

    app = _app()
    page = PackPage(); page.apply_ui_mode("advanced"); page.resize(1200, 900); page.show()
    app.processEvents()
    fields = [page.pack_folder, page.pack_carrier, page.pool_dir, page.pack_out,
              page.split_size, page.enc_pwd, page.seal_layers, page.seal_pwds]
    xs = {f.mapTo(page, QPoint(0, 0)).x() for f in fields}
    assert len(xs) == 1, f"打包表单输入框起点不一致: {sorted(xs)}"
    unpack = {f.mapTo(page, QPoint(0, 0)).x() for f in (page.unpack_out, page.unpack_pwds)}
    assert len(unpack) == 1, f"解包表单输入框起点不一致: {sorted(unpack)}"


def test_pack_page_lists_have_empty_hints():
    from ui.pages.pack_page import PackPage

    _app()
    page = PackPage()
    for view in (page.unpack_list, page.pack_file_list):
        assert view.property("emptyHint"), "空列表缺少操作提示"


def test_editor_toolbar_keeps_core_actions_and_moves_rest_to_menu():
    from ui.pages.editor_page import EditorPage

    app = _app()
    page = EditorPage(); page.apply_ui_mode("advanced"); page.resize(1280, 800); page.show()
    app.processEvents()
    top = [b for b in page.findChildren(QPushButton)
           if b.isVisible() and b.mapTo(page, QPoint(0, 0)).y() < page.btn_open.mapTo(page, QPoint(0, 0)).y() + 5]
    assert len(top) <= 6, [b.text() for b in top]
    texts = [a.text() for a in page.more_menu.actions()]
    for name in ("更换预览图", "导出 JSON", "切换 KK/KKS 标识(实验)"):
        assert name in texts
    assert not page.btn_more.isEnabled()


def test_editor_birthday_label_lines_up_with_its_fields():
    from ui.pages.editor_page import EditorPage
    from PyQt6.QtWidgets import QLabel

    app = _app()
    page = EditorPage(); page.resize(1280, 800); page.show(); app.processEvents()
    label = next(l for l in page.findChildren(QLabel) if l.text() == "生日")
    ly = label.mapTo(page, QPoint(0, label.height() // 2)).y()
    fy = page.sp_month.mapTo(page, QPoint(0, page.sp_month.height() // 2)).y()
    assert abs(ly - fy) <= 3, (ly, fy)


def test_other_pages_mark_empty_areas():
    from ui.pages.mod_page import ModPage
    from ui.pages.scene_page import ScenePage
    from ui.pages.share_page import SharePage

    _app()
    mod, scene, share = ModPage(), ScenePage(), SharePage()
    assert mod.queue.property("emptyHint") and mod.result.placeholderText()
    assert scene.analysis.placeholderText()
    assert share.queue.property("emptyHint") and share.result.placeholderText()


def test_share_form_fields_align():
    from ui.pages.share_page import SharePage

    app = _app()
    page = SharePage(); page.resize(1200, 900); page.show(); app.processEvents()
    edits = [e for e in page.findChildren(QLineEdit) if e.isVisible()]
    assert page.exclude_edit in edits
    xs = {e.mapTo(page, QPoint(0, 0)).x() for e in edits}
    assert len(xs) == 1, sorted(xs)
