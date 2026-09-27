"""只读游戏目录的手工集成验收：python tests/manual_pack_smoke.py <游戏目录> [mods子目录]。"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt6.QtWidgets import QApplication, QFileDialog  # noqa: E402
from PIL import Image  # noqa: E402

from core import settings, stego  # noqa: E402
from ui.pages.pack_page import PackPage  # noqa: E402


def fingerprint(path: Path) -> tuple[int, int, str]:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, digest.hexdigest()


def pick_mods(mods_dir: Path) -> list[Path]:
    if not mods_dir.is_dir():
        raise FileNotFoundError(f"未找到 mods 目录: {mods_dir}")
    chosen: list[Path] = []
    names: set[str] = set()
    for path in mods_dir.rglob("*.zipmod"):
        if (path.is_file() and 4096 <= path.stat().st_size <= 2 * 1024 * 1024
                and path.name.casefold() not in names and zipfile.is_zipfile(path)):
            chosen.append(path)
            names.add(path.name.casefold())
            if len(chosen) == 3:
                return chosen
    raise RuntimeError("未找到三份不同名、2MB 以下的有效 zipmod")


def pack_from_page(page: PackPage) -> None:
    done: list[list[str]] = []
    failed: list[str] = []
    page._on_done = lambda _label, results: done.append(results)
    page._on_failed = failed.append
    with patch.object(settings, "set_value", lambda *_: None):
        page._do_pack()
        if not page._worker or not page._worker.wait(60000):
            raise TimeoutError("打包后台任务未在 60 秒内结束")
        QApplication.processEvents()
    if failed or len(done) != 1:
        raise AssertionError(f"打包失败: {failed}, 成功回调: {done}")


def verify_files(root: Path, selected: list[Path], excluded: Path) -> None:
    page = PackPage()
    page.show()
    page.pack_by_files.setChecked(True)
    with patch.object(QFileDialog, "getOpenFileNames", return_value=([str(p) for p in selected], "")):
        page._add_pack_files()
    page.pack_carrier.setText(str(root / "carrier.png"))
    for password in ([None, "smoke-password"] if stego.HAVE_PYZIPPER else [None]):
        name = "encrypted" if password else "plain"
        output = root / f"selected_{name}.png"
        page.pack_out.setText(str(output))
        page.enc_enable.setChecked(bool(password))
        page.enc_pwd.setText(password or "")
        pack_from_page(page)

        with Image.open(output) as image:
            image.verify()
        with zipfile.ZipFile(output) as archive:
            assert set(archive.namelist()) == {p.name for p in selected}
            assert excluded.name not in archive.namelist()
        restored = root / f"restored_{name}"
        stego.extract_archive(output, restored, passwords=[password] if password else None)
        for path in selected:
            assert (restored / path.name).read_bytes() == path.read_bytes()
        print(f"指定文件+{'AES' if password else '普通'}：图片可读；{len(selected)} 个 mod 往返一致；未选文件不在包内")

    if stego.HAVE_PYZIPPER:
        page.apply_ui_mode("advanced")
        page.seal_layers.setValue(2)
        page.seal_pwds.setText("inner-pass,outer-pass")
        page.pack_out.setText(str(root / "layered.png"))
        pack_from_page(page)
        with Image.open(root / "layered.png") as image:
            image.verify()
        restored = root / "restored_layered"
        stego.extract_layered(root / "layered.png", restored, ["inner-pass", "outer-pass"])
        for path in selected:
            assert (restored / path.name).read_bytes() == path.read_bytes()
        print("指定文件+双层封缄：往返一致")

    stage = root / "folder_source"
    (stage / "sub").mkdir(parents=True)
    shutil.copy2(selected[0], stage / selected[0].name)
    shutil.copy2(selected[1], stage / "sub" / selected[1].name)
    page.apply_ui_mode("normal")
    page.pack_by_folder.setChecked(True)
    page.pack_folder.setText(str(stage))
    page.enc_enable.setChecked(False)
    page.pack_out.setText(str(root / "folder.png"))
    pack_from_page(page)
    with zipfile.ZipFile(root / "folder.png") as archive:
        assert set(archive.namelist()) == {selected[0].name, f"sub/{selected[1].name}"}
    print("原文件夹模式：嵌套目录结构保持")
    page.close()


def main() -> None:
    if len(sys.argv) not in (2, 3):
        raise SystemExit("用法: python tests/manual_pack_smoke.py <游戏目录> [mods子目录]")
    game = Path(sys.argv[1]).resolve(strict=True)
    mods_dir = (game / "mods").resolve(strict=True)
    sample_dir = (mods_dir / sys.argv[2]).resolve(strict=True) if len(sys.argv) == 3 else mods_dir
    if not sample_dir.is_relative_to(mods_dir):
        raise ValueError("样本目录必须位于游戏 mods 内")
    samples = pick_mods(sample_dir)
    before = {p: fingerprint(p) for p in samples}
    selected = [samples[0], samples[2]]
    excluded = samples[1]
    print(f"游戏目录（只读）: {game}")
    for path in samples:
        size, _, digest = before[path]
        print(f"{'选择' if path in selected else '排除'}: {path.relative_to(game)} | {size} bytes | SHA-256 {digest}")

    temp_root = Path(tempfile.gettempdir()).resolve()
    if temp_root.drive.casefold() == game.drive.casefold():
        raise RuntimeError(f"系统临时目录与游戏同盘，拒绝写入: {temp_root}")
    print(f"临时输出目录所在盘: {temp_root.drive}")
    app = QApplication([])
    with tempfile.TemporaryDirectory(prefix="kktools_real_mod_", dir=temp_root) as tmp:
        temp = Path(tmp)
        Image.new("RGB", (32, 32), "#2c594e").save(temp / "carrier.png")
        verify_files(temp, selected, excluded)
    app.processEvents()
    assert {p: fingerprint(p) for p in samples} == before, "游戏目录的样本文件发生变化"
    print("源 mod 哈希/大小/修改时间未变；临时打包目录已自动清理。")


if __name__ == "__main__":
    main()
