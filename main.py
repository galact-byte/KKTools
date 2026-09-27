"""KKTools 主程序入口。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import diagnostics  # noqa: E402


def apply_theme(app, theme_id: str | None = None) -> str:
    """加载并应用主题，返回最终生效的主题 id。

    theme_id 为空时读配置；找不到指定主题则回退到内置 bone_light；
    再不行就回退到代码内默认令牌——保证界面永远有样式可用。
    """
    from core import settings, theme as theme_mod
    from ui import theme_qss

    cfg = settings.load()
    tid = theme_id or cfg.get("theme", "bone_light")
    user_dir = cfg.get("user_theme_dir", "") or None
    extra = [user_dir] if user_dir else None

    th = theme_mod.find_theme(tid, extra) or theme_mod.find_theme("bone_light", extra)
    if th is None:
        th = theme_mod.from_dict({"id": "bone_light", "name": "骨白·昼"})  # 纯默认令牌兜底
    app.setStyleSheet(theme_qss.build_qss(th))
    return th.id


def main() -> int:
    path = diagnostics.initialize()
    from PyQt6.QtWidgets import QApplication, QMessageBox
    from ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("KKTools")
    if path is None:
        QMessageBox.warning(None, "日志不可用", "无法写入本地日志目录。若遇到错误，请保留报错截图。")

    def report_exception(exc_type, value, tb):
        diagnostics.record_exception(exc_type, value, tb)
        location = f"日志已保存到：{path}" if path else "日志不可用，请保留此报错截图。"
        QMessageBox.critical(None, "程序异常", f"{value}\n\n{location}")

    sys.excepthook = report_exception
    apply_theme(app)

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
