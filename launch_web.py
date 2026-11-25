"""KKTools WebView2 日系清爽工作台启动器。

用法：
- 直接启动桌面窗口（使用 Windows 原生 Edge WebView2）：
    python launch_web.py
- 仅启动本地 HTTP 预览服务（供浏览器查看或自动化视觉巡检）：
    python launch_web.py --server --port 18421
"""

from __future__ import annotations

import argparse
import ctypes
import json
import mimetypes
import socket
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from web_bridge import KKToolsBridge  # noqa: E402


def resolve_dist_dir() -> Path:
    """定位前端构建产物目录（兼容 PyInstaller --onefile 与源码运行）。"""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            cand = Path(meipass) / "web" / "dist"
            if (cand / "index.html").is_file():
                return cand
    return ROOT / "web" / "dist"


def resolve_icon_path() -> Path | None:
    """定位桌面窗口图标（兼容 PyInstaller --onefile 与源码运行）。"""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            cand = Path(meipass) / "assets" / "kktools.ico"
            if cand.is_file():
                return cand
    cand = ROOT / "assets" / "kktools.ico"
    return cand if cand.is_file() else None


def _set_windows_app_id() -> None:
    """设置独立 AppUserModelID，确保任务栏显示 KKTools 图标而非宿主 python.exe。"""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("KKTools.Studio.App")
    except Exception:
        pass


def _confirm_windows(title: str, message: str) -> bool:
    """使用系统原生弹窗做关窗前二次确认（返回 True 表示允许关闭）。"""
    if sys.platform != "win32":
        return True
    MB_YESNO = 0x00000004
    MB_ICONWARNING = 0x00000030
    MB_DEFBUTTON2 = 0x00000100
    IDYES = 6
    res = ctypes.windll.user32.MessageBoxW(
        0,
        message,
        title,
        MB_YESNO | MB_ICONWARNING | MB_DEFBUTTON2,
    )
    return res == IDYES


def _make_handler(bridge: KKToolsBridge, dist_dir: Path):
    class _Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(dist_dir), **kwargs)

        def log_message(self, format: str, *args) -> None:  # noqa: A002
            return

        def do_GET(self) -> None:  # noqa: N802
            if self.path.startswith("/thumb/"):
                host = self.headers.get("Host", "")
                if host != f"127.0.0.1:{self.server.server_port}":
                    self.send_error(403)
                    return
                token = self.path[len("/thumb/") :].split("?", 1)[0].strip("/")
                res = bridge.get_thumbnail_bytes(token)
                if res is None:
                    self.send_error(404)
                    return
                payload, mime = res
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "private, max-age=86400")
                self.end_headers()
                self.wfile.write(payload)
                return
            super().do_GET()

        def do_POST(self) -> None:  # noqa: N802
            if not self.path.startswith("/api/"):
                self.send_error(404)
                return
            host = self.headers.get("Host", "")
            origin = self.headers.get("Origin")
            if host != f"127.0.0.1:{self.server.server_port}" or (
                origin is not None and origin != f"http://{host}"
            ):
                self._send_json({"ok": False, "error": "拒绝跨来源调用"}, 403)
                return
            if self.headers.get_content_type() != "application/json":
                self._send_json({"ok": False, "error": "仅接受 JSON 请求"}, 415)
                return
            method_name = self.path[len("/api/") :].strip("/")
            if (
                method_name.startswith("_")
                or method_name in ("bind_window", "get_thumbnail_bytes")
                or not callable(getattr(bridge, method_name, None))
            ):
                self._send_json({"ok": False, "error": f"未知接口：{method_name}"}, 404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0") or "0")
                if not 0 <= length <= 1024 * 1024:
                    self._send_json({"ok": False, "error": "请求过大"}, 413)
                    return
                raw = self.rfile.read(length) if length > 0 else b"{}"
                body = json.loads(raw.decode("utf-8"))
                call_args = body.get("args", [])
                if not isinstance(call_args, list):
                    raise ValueError("args 必须是数组")
                fn = getattr(bridge, method_name)
                result = fn(*call_args)
            except Exception as exc:  # noqa: BLE001
                result = {"ok": False, "error": str(exc)}
            self._send_json(result, 200)

        def _send_json(self, payload: dict, status: int) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return _Handler


def _pick_free_port(preferred: int = 0) -> int:
    if preferred:
        return preferred
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def start_local_server(bridge: KKToolsBridge, port: int = 0) -> tuple[ThreadingHTTPServer, int]:
    dist_dir = resolve_dist_dir()
    if not (dist_dir / "index.html").is_file():
        raise FileNotFoundError(
            f"未找到前端构建产物 {dist_dir / 'index.html'}，请先在 web/ 目录执行 bun run build"
        )
    mimetypes.add_type("application/javascript", ".js")
    mimetypes.add_type("text/css", ".css")
    actual_port = _pick_free_port(port)
    handler = _make_handler(bridge, dist_dir)
    server = ThreadingHTTPServer(("127.0.0.1", actual_port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, actual_port


def can_close(bridge: KKToolsBridge, confirm=_confirm_windows) -> bool:
    if bridge.has_running_tasks():
        return False
    if bridge.has_unsaved_edits():
        return confirm("存在未保存的角色卡改动", "角色编辑器中还有未保存的修改。\n确定放弃修改并退出 KKTools 吗？")
    return True


def launch_desktop() -> int:
    """启动 Edge WebView2 原生桌面窗口，内建未保存改动与后台任务关窗保护。"""
    import webview

    _set_windows_app_id()
    icon_path = resolve_icon_path()

    bridge = KKToolsBridge()
    server, port = start_local_server(bridge, port=0)
    url = f"http://127.0.0.1:{port}/"

    window = webview.create_window(
        title="KKTools · 恋活角色卡画室",
        url=url,
        js_api=bridge,
        width=1340,
        height=860,
        min_size=(1060, 680),
        background_color="#EEF4FC",
    )
    bridge.bind_window(window)

    def _on_closing() -> bool:
        if bridge.has_running_tasks():
            window.evaluate_js("window.dispatchEvent(new CustomEvent('kk-close-blocked'))")
        return can_close(bridge)

    window.events.closing += _on_closing

    try:
        webview.start(gui="edgechromium", icon=str(icon_path) if icon_path else None)
    finally:
        bridge.cleanup_pending_update()
        server.shutdown()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="KKTools WebView2 日系清爽工作台")
    parser.add_argument("--server", action="store_true", help="仅启动本地 HTTP 服务，不弹出桌面窗口")
    parser.add_argument("--port", type=int, default=0, help="指定本地端口（默认自动分配）")
    args = parser.parse_args()

    if args.server:
        bridge = KKToolsBridge()
        server, port = start_local_server(bridge, port=args.port)
        url = f"http://127.0.0.1:{port}/"
        print(f"KKTools Web Preview running at {url}", flush=True)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
        finally:
            bridge.cleanup_pending_update()
            server.shutdown()
        return 0

    return launch_desktop()


if __name__ == "__main__":
    raise SystemExit(main())
