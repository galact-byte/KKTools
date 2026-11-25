"""应用图标资产、PyInstaller 打包配置与桌面窗口图标解析回归测试。"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import IcoImagePlugin, Image

import launch_web

ROOT = Path(__file__).resolve().parent.parent


def test_app_icon_ico_has_multiresolution_transparent_frames():
    svg_path = ROOT / "assets" / "kktools.svg"
    ico_path = ROOT / "assets" / "kktools.ico"
    assert svg_path.is_file()
    assert ico_path.is_file()

    with ico_path.open("rb") as fh:
        ico = IcoImagePlugin.IcoFile(fh)
        sizes = set(ico.sizes())
        for expected in ((16, 16), (32, 32), (48, 48), (256, 256)):
            assert expected in sizes, f"missing ICO size {expected}"
        frame_256 = ico.getimage((256, 256)).convert("RGBA")
        # 圆角矩形图标四角必须透明，不能出现白色方底
        assert frame_256.getpixel((0, 0))[3] == 0
        assert frame_256.getpixel((255, 255))[3] == 0


def test_web_logo_and_favicon_assets_exist():
    logo_path = ROOT / "web" / "public" / "logo.png"
    fav_path = ROOT / "web" / "public" / "favicon.ico"
    assert logo_path.is_file()
    assert fav_path.is_file()

    with Image.open(logo_path) as img:
        assert img.size == (256, 256)
        assert img.mode == "RGBA"
    with Image.open(fav_path) as fav:
        assert (32, 32) in fav.info.get("sizes", set())


def test_pyinstaller_spec_configures_custom_icon_and_bundles_it():
    spec_text = (ROOT / "KKTools.spec").read_text(encoding="utf-8")
    assert "icon='assets/kktools.ico'" in spec_text or 'icon="assets/kktools.ico"' in spec_text
    assert "('assets/kktools.ico', 'assets')" in spec_text or '("assets/kktools.ico", "assets")' in spec_text


def test_launch_web_resolves_icon_in_dev_and_frozen_modes(tmp_path, monkeypatch):
    dev_icon = launch_web.resolve_icon_path()
    assert dev_icon is not None
    assert dev_icon.is_file()
    assert dev_icon.name == "kktools.ico"

    fake_meipass = tmp_path / "meipass"
    fake_icon = fake_meipass / "assets" / "kktools.ico"
    fake_icon.parent.mkdir(parents=True)
    fake_icon.write_bytes((ROOT / "assets" / "kktools.ico").read_bytes())

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(fake_meipass), raising=False)

    frozen_icon = launch_web.resolve_icon_path()
    assert frozen_icon == fake_icon


def test_web_index_html_links_favicon_and_logo():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert "favicon.ico" in html
    assert "logo.png" in html
