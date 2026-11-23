"""KKTools WebView2 桌面入口。"""
import ctypes
import logging
import sys

from core import diagnostics


def main() -> int:
    path = diagnostics.initialize()
    try:
        from launch_web import launch_desktop
        return launch_desktop()
    except Exception:
        logging.getLogger("kktools").exception("桌面启动失败")
        location = str(path) if path else "日志文件不可用"
        message = f"KKTools 启动失败。请确认系统已安装 Microsoft Edge WebView2 Runtime。\n\n错误详情：{location}"
        if sys.platform == "win32":
            ctypes.windll.user32.MessageBoxW(0, message, "KKTools 启动失败", 0x10)
        else:
            print(message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
