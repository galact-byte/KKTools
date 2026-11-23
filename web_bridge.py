"""KKTools WebView2 前端与纯 Python core/ 之间的完整业务桥接层。

覆盖能力：
- 配置、主题与壁纸预览（兼容旧版 PyQt6 主题 ID）
- 后台任务队列（打包/解包、分享导出/导入、Mod 索引/归档/整理、自更新检查与下载）
- 卡片浏览扫描、角色卡读取/编辑/换封面/安全写回、拖放类型识别
- 场景卡解析与一键提取内嵌角色
- 软件自更新（阶段提示、下载进度、校验、安全清理旧包、便携 EXE 辅助替换重启）
"""

from __future__ import annotations

import os
import logging
import base64
import mimetypes
import subprocess
import sys
import tempfile
import threading
import uuid
import webbrowser
from pathlib import Path
from typing import Any, Callable

from core import (
    card_scan,
    kk_card,
    kk_fields,
    mod_index,
    scene_card,
    settings,
    share,
    stego,
    updater,
)

_WEB_TO_LEGACY_THEME = {
    "sora_light": "cloud_light",
    "washi_light": "paper_light",
    "tsukiyo_dark": "graphite_dark",
    "yorha_light": "yorha_light",
}

_LEGACY_TO_WEB_THEME = {
    "cloud_light": "sora_light",
    "paper_light": "washi_light",
    "graphite_dark": "tsukiyo_dark",
    "yorha_light": "yorha_light",
}


def _ok(data: Any = None) -> dict[str, Any]:
    return {"ok": True, "data": data}


def _err(message: str) -> dict[str, Any]:
    logging.getLogger("kktools").error(message, exc_info=sys.exc_info()[0] is not None)
    return {"ok": False, "error": message}


def _bytes_to_data_url(raw: bytes | None, mime: str = "image/png") -> str:
    if not raw:
        return ""
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def _file_to_data_url(path_str: str, max_bytes: int = 16 * 1024 * 1024) -> str:
    if not path_str:
        return ""
    p = Path(path_str)
    if not p.is_file():
        return ""
    try:
        if p.stat().st_size > max_bytes:
            return ""
        mime, _ = mimetypes.guess_type(str(p))
        return _bytes_to_data_url(p.read_bytes(), mime or "image/png")
    except OSError:
        return ""


def _pick_via_tk(kind: str, title: str, initial_dir: str = "", multiple: bool = False) -> Any:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        if kind == "dir":
            return filedialog.askdirectory(title=title, initialdir=initial_dir or None) or ""
        if kind == "save_txt":
            return (
                filedialog.asksaveasfilename(
                    title=title,
                    defaultextension=".txt",
                    filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
                )
                or ""
            )
        if kind == "image":
            return (
                filedialog.askopenfilename(
                    title=title,
                    filetypes=[("图片文件", "*.png *.jpg *.jpeg *.webp *.bmp"), ("所有文件", "*.*")],
                )
                or ""
            )
        if kind == "card":
            if multiple:
                return list(
                    filedialog.askopenfilenames(
                        title=title,
                        filetypes=[("恋活卡片 PNG", "*.png"), ("所有文件", "*.*")],
                    )
                    or []
                )
            return (
                filedialog.askopenfilename(
                    title=title,
                    filetypes=[("恋活卡片 PNG", "*.png"), ("所有文件", "*.*")],
                )
                or ""
            )
        if multiple:
            return list(
                filedialog.askopenfilenames(title=title, filetypes=[("所有文件", "*.*")]) or []
            )
        return filedialog.askopenfilename(title=title, filetypes=[("所有文件", "*.*")]) or ""
    finally:
        root.destroy()


def _mod_cache_path() -> Path:
    return settings.app_dir() / "mod_index.json"


class _TaskManager:
    """线程安全的轻量后台任务跟踪器。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: dict[str, dict[str, Any]] = {}

    def start(self, fn: Callable[[Callable[[int, int, str], None]], Any]) -> str:
        task_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._tasks[task_id] = {
                "id": task_id,
                "status": "running",
                "current": 0,
                "total": 0,
                "percent": 0,
                "message": "准备中…",
                "result": None,
                "error": "",
            }

        def report(current: int, total: int, message: str = "") -> None:
            pct = int((current / total) * 100) if total > 0 else 0
            with self._lock:
                t = self._tasks.get(task_id)
                if t:
                    t["current"] = int(current)
                    t["total"] = int(total)
                    t["percent"] = max(0, min(100, pct))
                    if message:
                        t["message"] = str(message)

        def runner() -> None:
            try:
                res = fn(report)
                with self._lock:
                    t = self._tasks[task_id]
                    t["status"] = "done"
                    t["percent"] = 100
                    t["result"] = res
            except Exception as exc:  # noqa: BLE001
                logging.getLogger("kktools").exception("后台任务失败")
                with self._lock:
                    t = self._tasks[task_id]
                    t["status"] = "error"
                    t["error"] = str(exc)

        threading.Thread(target=runner, daemon=True).start()
        return task_id

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            t = self._tasks.get(task_id)
            return dict(t) if t else None

    def has_running(self) -> bool:
        with self._lock:
            return any(t["status"] == "running" for t in self._tasks.values())


class KKToolsBridge:
    """暴露给前端（pywebview.api / HTTP /api/<method>）的业务接口。"""

    def __init__(self) -> None:
        self._active_saves = 0
        self._save_lock = threading.Lock()
        self._window = None
        self._tasks = _TaskManager()
        self._mod_index: mod_index.ModIndex | None = None
        self._latest_release: updater.Release | None = None
        self._pending_update_artifact: Path | None = None
        self._installing_update: bool = False
        self._has_unsaved_edits: bool = False

    def bind_window(self, window: Any) -> None:
        self._window = window

    # ---- 生命周期与任务轮询 ----

    def set_dirty_state(self, dirty: bool) -> dict[str, Any]:
        self._has_unsaved_edits = bool(dirty)
        return _ok(self._has_unsaved_edits)

    def has_unsaved_edits(self) -> bool:
        return self._has_unsaved_edits

    def has_running_tasks(self) -> bool:
        return self._active_saves > 0 or self._tasks.has_running()

    def record_log(self, level: str, source: str, message: str) -> dict[str, Any]:
        severity = {"error": logging.ERROR, "warn": logging.WARNING}.get(level, logging.INFO)
        logging.getLogger("kktools").log(severity, "[%s] %s", str(source)[:40], str(message)[:4000])
        return _ok()

    def open_log_directory(self) -> dict[str, Any]:
        from core import diagnostics
        path = diagnostics.log_path()
        if path is None:
            return _err("当前日志文件不可用")
        try:
            os.startfile(str(path.parent))
            return _ok(str(path.parent))
        except OSError as exc:
            return _err(f"打开日志目录失败：{exc}")

    def poll_task(self, task_id: str) -> dict[str, Any]:
        info = self._tasks.get(task_id)
        if info is None:
            return _err("任务不存在或已过期")
        return _ok(info)

    def cleanup_pending_update(self) -> dict[str, Any]:
        """普通退出或重新检查更新前，清理未安装的更新临时文件。"""
        if self._pending_update_artifact is not None and not self._installing_update:
            try:
                updater.discard_download(self._pending_update_artifact)
            except Exception:  # noqa: BLE001
                pass
            self._pending_update_artifact = None
        return _ok(True)

    # ---- 配置与壁纸 ----

    def get_config(self) -> dict[str, Any]:
        try:
            cfg = settings.load()
            wp_path = str(cfg.get("wallpaper_path") or "")
            wp_url = _file_to_data_url(wp_path) if wp_path else ""
            raw_theme = str(cfg.get("theme") or "cloud_light")
            quick_dirs: list[dict[str, str]] = []
            for key, game_tag, label in (
                ("kk_game_dir", "KK", "KK 角色目录"),
                ("kks_game_dir", "KKS", "KKS 角色目录"),
            ):
                base_str = str(cfg.get(key) or "").strip()
                if not base_str:
                    continue
                base = Path(base_str)
                chara = base / "UserData" / "chara"
                if chara.is_dir():
                    quick_dirs.append({"game": game_tag, "label": label, "path": str(chara)})
                elif base.is_dir():
                    quick_dirs.append({"game": game_tag, "label": f"{game_tag} 目录", "path": str(base)})

            data = {
                "kk_game_dir": cfg.get("kk_game_dir", ""),
                "kks_game_dir": cfg.get("kks_game_dir", ""),
                "mod_dirs": list(cfg.get("mod_dirs") or []),
                "output_dir": cfg.get("output_dir", ""),
                "last_browse_dir": cfg.get("last_browse_dir", ""),
                "carrier_dir": cfg.get("carrier_dir", ""),
                "pack_out_dir": cfg.get("pack_out_dir", ""),
                "quick_dirs": quick_dirs,
                "theme": _LEGACY_TO_WEB_THEME.get(raw_theme, "sora_light"),
                "wallpaper_path": wp_path,
                "wallpaper_url": wp_url,
                "wallpaper_enabled": bool(wp_url) and bool(cfg.get("wallpaper_enabled", True)),
                "wallpaper_overlay": int(cfg.get("wallpaper_overlay", 55)),
                "wallpaper_panel_alpha": int(cfg.get("wallpaper_panel_alpha", 82)),
                "wallpaper_blur": int(cfg.get("wallpaper_blur", 18)),
                "ui_mode": cfg.get("ui_mode", "normal"),
                "start_page": int(cfg.get("start_page", 1)),
                "recent_cards": list(cfg.get("recent_cards") or []),
                "app_version": updater.current_version(),
                "is_frozen": bool(getattr(sys, "frozen", False)),
            }
            return _ok(data)
        except Exception as exc:  # noqa: BLE001
            return _err(f"读取配置失败：{exc}")

    def save_config(self, patch: dict[str, Any]) -> dict[str, Any]:
        try:
            cfg = settings.load()
            for k in (
                "kk_game_dir",
                "kks_game_dir",
                "mod_dirs",
                "output_dir",
                "last_browse_dir",
                "carrier_dir",
                "pack_out_dir",
                "ui_mode",
                "start_page",
            ):
                if k in patch:
                    cfg[k] = patch[k]

            if "theme" in patch:
                t = str(patch["theme"])
                cfg["theme"] = _WEB_TO_LEGACY_THEME.get(t, t)

            if "wallpaper_enabled" in patch:
                cfg["wallpaper_enabled"] = bool(patch["wallpaper_enabled"])
            if "wallpaper_path" in patch:
                cfg["wallpaper_path"] = str(patch["wallpaper_path"] or "")
            if "wallpaper_blur" in patch:
                cfg["wallpaper_blur"] = max(0, min(40, int(patch["wallpaper_blur"])))

            if "wallpaper_overlay" in patch:
                cfg["wallpaper_overlay"] = max(0, min(90, int(patch["wallpaper_overlay"])))
            if "wallpaper_panel_alpha" in patch:
                cfg["wallpaper_panel_alpha"] = max(45, min(100, int(patch["wallpaper_panel_alpha"])))

            settings.save(cfg)
            return self.get_config()
        except Exception as exc:  # noqa: BLE001
            return _err(f"保存配置失败：{exc}")

    def get_wallpaper_data_url(self, path: str) -> dict[str, Any]:
        url = _file_to_data_url(path)
        if not url:
            return _err("无法读取所选图片文件（文件不存在或超过 16MB 限制）")
        return _ok(url)

    # ---- 系统文件选择器 ----

    def pick_directory(self, title: str = "选择目录", initial_dir: str = "") -> dict[str, Any]:
        try:
            if self._window is not None:
                import webview

                res = self._window.create_file_dialog(
                    webview.FileDialog.FOLDER,
                    directory=initial_dir or "",
                )
                return _ok(res[0] if res else "")
            return _ok(_pick_via_tk("dir", title, initial_dir))
        except Exception as exc:  # noqa: BLE001
            return _err(f"打开目录选择器失败：{exc}")

    def pick_image_file(self, title: str = "选择图片") -> dict[str, Any]:
        try:
            if self._window is not None:
                import webview

                res = self._window.create_file_dialog(
                    webview.FileDialog.OPEN,
                    file_types=("图片文件 (*.png;*.jpg;*.jpeg;*.webp;*.bmp)", "所有文件 (*.*)"),
                )
                return _ok(res[0] if res else "")
            return _ok(_pick_via_tk("image", title))
        except Exception as exc:  # noqa: BLE001
            return _err(f"打开图片选择器失败：{exc}")

    def pick_card_file(self, title: str = "选择恋活卡片 PNG") -> dict[str, Any]:
        try:
            if self._window is not None:
                import webview

                res = self._window.create_file_dialog(
                    webview.FileDialog.OPEN,
                    file_types=("PNG 卡片 (*.png)", "所有文件 (*.*)"),
                )
                return _ok(res[0] if res else "")
            return _ok(_pick_via_tk("card", title))
        except Exception as exc:  # noqa: BLE001
            return _err(f"打开文件选择器失败：{exc}")

    def pick_card_files(self, title: str = "批量选择角色卡 PNG") -> dict[str, Any]:
        try:
            if self._window is not None:
                import webview

                res = self._window.create_file_dialog(
                    webview.FileDialog.OPEN,
                    allow_multiple=True,
                    file_types=("PNG 卡片 (*.png)", "所有文件 (*.*)"),
                )
                return _ok(list(res) if res else [])
            return _ok(_pick_via_tk("card", title, multiple=True))
        except Exception as exc:  # noqa: BLE001
            return _err(f"打开多选对话框失败：{exc}")

    def pick_any_files(self, title: str = "选择文件", multiple: bool = True) -> dict[str, Any]:
        try:
            if self._window is not None:
                import webview

                res = self._window.create_file_dialog(
                    webview.FileDialog.OPEN,
                    allow_multiple=bool(multiple),
                    file_types=("所有文件 (*.*)",),
                )
                if multiple:
                    return _ok(list(res) if res else [])
                return _ok(res[0] if res else "")
            return _ok(_pick_via_tk("any", title, multiple=bool(multiple)))
        except Exception as exc:  # noqa: BLE001
            return _err(f"打开文件选择器失败：{exc}")

    def pick_save_txt(self, title: str = "导出文本文件") -> dict[str, Any]:
        try:
            if self._window is not None:
                import webview

                res = self._window.create_file_dialog(
                    webview.FileDialog.SAVE,
                    save_filename="mod_guids.txt",
                    file_types=("文本文件 (*.txt)", "所有文件 (*.*)"),
                )
                if isinstance(res, (list, tuple)):
                    return _ok(res[0] if res else "")
                return _ok(res or "")
            return _ok(_pick_via_tk("save_txt", title))
        except Exception as exc:  # noqa: BLE001
            return _err(f"打开保存对话框失败：{exc}")

    def reveal_in_explorer(self, path: str) -> dict[str, Any]:
        try:
            p = Path(path)
            if sys.platform == "win32" and p.exists():
                if p.is_dir():
                    subprocess.Popen(["explorer", str(p)])
                else:
                    subprocess.Popen(["explorer", "/select,", str(p)])
                return _ok(True)
            return _err("目标路径不存在")
        except Exception as exc:  # noqa: BLE001
            return _err(str(exc))

    def open_external_url(self, url: str) -> dict[str, Any]:
        try:
            if not str(url).startswith(("https://", "http://")):
                return _err("仅允许打开 HTTP/HTTPS 链接")
            webbrowser.open(str(url))
            return _ok(True)
        except Exception as exc:  # noqa: BLE001
            return _err(str(exc))

    # ---- 目录卡片扫描与类型识别 ----

    def scan_directory(self, directory: str, recursive: bool = False) -> dict[str, Any]:
        try:
            d = Path(directory)
            if not d.is_dir():
                return _err(f"目录不存在：{directory}")
            items = card_scan.scan_dir(d, recursive=bool(recursive))
            out: list[dict[str, Any]] = []
            for idx, item in enumerate(items):
                p = Path(item.path)
                out.append(
                    {
                        "id": f"local-{idx}-{p.name}",
                        "path": item.path,
                        "fileName": p.name,
                        "type": item.type,
                        "game": item.game,
                        "name": item.name,
                        "thumbnailUrl": _bytes_to_data_url(item.thumbnail, "image/png"),
                        "isDemo": False,
                    }
                )
            settings.set_value("last_browse_dir", str(d))
            return _ok(out)
        except Exception as exc:  # noqa: BLE001
            return _err(f"扫描目录失败：{exc}")

    def inspect_file(self, path: str) -> dict[str, Any]:
        try:
            p = Path(path)
            if not p.is_file():
                return _err("文件不存在")
            info = kk_card.read_card_light(p)
            return _ok({"path": str(p), "type": info.type, "game": info.game, "name": info.name})
        except Exception as exc:  # noqa: BLE001
            return _err(str(exc))

    # ---- 角色卡读取、换封面与安全写回 ----

    def load_card(self, path: str) -> dict[str, Any]:
        try:
            p = Path(path)
            card = kk_card.KoikatuCard.load(p)
            param = card.parameter or {}

            def _bool_dict(raw_val: Any) -> dict[str, bool]:
                return {k: v for k, v in kk_fields.editable_items(raw_val)}

            raw_scalars: dict[str, Any] = {}
            for k, v in param.items():
                if isinstance(v, (str, int, float, bool)):
                    raw_scalars[str(k)] = v

            mods = sorted(kk_card.extract_mod_ids(card).keys())
            # 维护最近打开列表
            cfg = settings.load()
            recent = [x for x in cfg.get("recent_cards", []) if x != str(p)]
            recent.insert(0, str(p))
            settings.set_value("recent_cards", recent[:12])

            return _ok(
                {
                    "path": str(p),
                    "fileName": p.name,
                    "game": card.game,
                    "gameName": card.game_name,
                    "marker": card.marker,
                    "version": card.version,
                    "thumbnailUrl": _bytes_to_data_url(card.thumbnail, "image/png"),
                    "faceUrl": _bytes_to_data_url(card.face, "image/png") if card.face else "",
                    "isDemo": False,
                    "parameter": {
                        "lastname": str(param.get("lastname", "")),
                        "firstname": str(param.get("firstname", "")),
                        "nickname": str(param.get("nickname", "")),
                        "sex": int(param.get("sex", 1)) if isinstance(param.get("sex"), int) else 1,
                        "personality": param.get("personality", 0),
                        "bloodType": param.get("bloodType", 0),
                        "birthMonth": int(param.get("birthMonth", 1))
                        if isinstance(param.get("birthMonth"), int)
                        else 1,
                        "birthDay": int(param.get("birthDay", 1))
                        if isinstance(param.get("birthDay"), int)
                        else 1,
                        "clubActivities": param.get("clubActivities", ""),
                        "voiceRate": param.get("voiceRate", 0.5),
                        "awnser": _bool_dict(param.get("awnser")),
                        "attribute": _bool_dict(param.get("attribute")),
                        "denial": _bool_dict(param.get("denial")),
                        "rawScalars": raw_scalars,
                    },
                    "modIds": mods,
                    "blockNames": list(card.block_names),
                }
            )
        except Exception as exc:  # noqa: BLE001
            return _err(f"读取角色卡失败：{exc}")

    def save_card(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._save_lock:
            self._active_saves += 1
        try:
            src = Path(payload["path"])
            overwrite = bool(payload.get("overwrite", False))
            new_param = payload.get("parameter") or {}
            cover_path = str(payload.get("coverPath") or "").strip()

            card = kk_card.KoikatuCard.load(src)

            if cover_path:
                cp = Path(cover_path)
                if not cp.is_file():
                    return _err(f"封面图片不存在：{cover_path}")
                from io import BytesIO
                from PIL import Image

                with Image.open(cp) as image:
                    buf = BytesIO()
                    image.convert("RGBA").save(buf, format="PNG")
                card.set_thumbnail_from_png(buf.getvalue())

            updates: dict[str, Any] = {}
            for key in (
                "lastname",
                "firstname",
                "nickname",
                "sex",
                "personality",
                "bloodType",
                "birthMonth",
                "birthDay",
            ):
                if key in new_param:
                    updates[key] = new_param[key]
            if "clubActivities" in new_param:
                val = new_param["clubActivities"]
                updates["clubActivities"] = int(val) if isinstance(val, str) and val.isdigit() else val

            orig_param = card.parameter or {}
            for bucket in ("awnser", "attribute", "denial"):
                if isinstance(new_param.get(bucket), dict):
                    merged = dict(orig_param.get(bucket) or {})
                    for k, v in new_param[bucket].items():
                        merged[k] = bool(v)
                    updates[bucket] = merged

            card.update_parameter(updates)

            if overwrite:
                out_path = src
                saved = card.save(out_path, backup=True)
            else:
                out_path = src.with_name(f"{src.stem}_edited{src.suffix}")
                idx = 2
                while out_path.exists():
                    out_path = src.with_name(f"{src.stem}_edited_{idx}{src.suffix}")
                    idx += 1
                saved = card.save(out_path, backup=False)

            return _ok({"savedPath": str(saved)})
        except Exception as exc:  # noqa: BLE001
            return _err(f"保存角色卡失败：{exc}")
        finally:
            with self._save_lock:
                self._active_saves -= 1

    # ---- 解包与打包（core.stego） ----

    def start_pack(self, opts: dict[str, Any]) -> dict[str, Any]:
        sources = [Path(p) for p in (opts.get("sources") or []) if p]
        out_dir = Path(str(opts.get("outDir") or "").strip())
        archive_name = str(opts.get("archiveName") or "KKTools_Pack").strip() or "KKTools_Pack"
        stego_mode = str(opts.get("stegoMode") or "none")  # none | image | video
        carrier_path = str(opts.get("carrierPath") or "").strip()
        passwords = [str(p) for p in (opts.get("passwords") or []) if str(p)]
        split_mb = float(opts.get("splitMB") or 0)
        write_recovery = bool(opts.get("writeRecovery", False))

        if not sources:
            return _err("请先添加要打包的文件或目录")
        if not str(opts.get("outDir") or "").strip():
            return _err("请选择输出目录")

        def job(report: Callable[[int, int, str], None]) -> dict[str, Any]:
            out_dir.mkdir(parents=True, exist_ok=True)
            settings.set_value("pack_out_dir", str(out_dir))

            carrier: Path | None = None
            if stego_mode in ("image", "video"):
                if carrier_path and Path(carrier_path).is_file():
                    carrier = Path(carrier_path)
                else:
                    pool = settings.get("carrier_dir", "")
                    if pool and Path(pool).is_dir():
                        carrier = Path(stego.pick_carrier_from_pool(pool))
                    else:
                        raise ValueError("启用伪装模式时请先选择载体文件，或在设置中配置载体目录")

            ext = carrier.suffix if carrier is not None else ".zip"
            out_file = out_dir / (archive_name if archive_name.endswith(ext) else f"{archive_name}{ext}")
            pack_source: Any = sources[0] if (len(sources) == 1 and sources[0].is_dir()) else sources

            def _prog(cur: int, tot: int, name: str = "") -> None:
                report(cur, tot, f"正在打包：{name}" if name else "正在打包…")

            if len(passwords) >= 2:
                produced = Path(
                    stego.pack_layered(
                        pack_source,
                        out_file,
                        passwords,
                        carrier=carrier,
                        progress=_prog,
                    )
                )
            elif carrier is not None:
                produced = Path(
                    stego.pack_and_disguise(
                        pack_source,
                        carrier,
                        out_file,
                        password=passwords[0] if passwords else None,
                        progress=_prog,
                    )
                )
            else:
                produced = Path(
                    stego.pack_folder(
                        pack_source,
                        out_file,
                        password=passwords[0] if passwords else None,
                        progress=_prog,
                    )
                )

            outputs = [str(produced)]
            if split_mb > 0:
                report(85, 100, f"正在按 {split_mb:g} MB 分卷…")
                parts = stego.split_file(produced, split_mb, out_dir=out_dir)
                if parts:
                    outputs = [str(x) for x in parts]

            recovery_file = ""
            if write_recovery:
                report(94, 100, "正在生成恢复校验 sidecar…")
                recovery_file = str(stego.write_recovery_sidecar(produced))

            return {
                "outputs": outputs,
                "outDir": str(out_dir),
                "recoveryFile": recovery_file,
            }

        return _ok({"taskId": self._tasks.start(job)})

    def start_unpack(self, opts: dict[str, Any]) -> dict[str, Any]:
        input_path = Path(str(opts.get("inputPath") or "").strip())
        out_dir = Path(str(opts.get("outDir") or "").strip())
        passwords = [str(p) for p in (opts.get("passwords") or []) if str(p)]

        if not input_path.is_file():
            return _err("请选择要解包的文件（ZIP / 图种 / 视频载体 / 首分卷）")
        if not str(opts.get("outDir") or "").strip():
            return _err("请选择解压目标目录")

        def job(report: Callable[[int, int, str], None]) -> dict[str, Any]:
            out_dir.mkdir(parents=True, exist_ok=True)
            target = input_path
            temp_joined: Path | None = None

            # 检测是否为分卷文件（如 .part1 / .001 / .z01 等）
            name_lower = input_path.name.lower()
            is_part = any(
                token in name_lower for token in (".part", ".001", ".002", ".003")
            ) or (input_path.suffix.startswith(".") and input_path.suffix[1:].isdigit())

            try:
                if is_part:
                    report(15, 100, "正在校验分卷连续性并合并…")
                    tmp_dir = Path(tempfile.mkdtemp(prefix="kktools_join_"))
                    temp_joined = tmp_dir / "joined.bin"
                    # join_parts 内置严格卷号连续校验，缺卷直接抛异常中止
                    target = Path(stego.join_parts(input_path, temp_joined))

                layers = stego.read_seal_layers(target)
                report(35, 100, "正在解包提取文件…")

                def _prog(cur: int, tot: int, name: str = "") -> None:
                    report(cur, tot, f"正在解压：{name}" if name else "正在解压…")

                if layers and layers >= 2:
                    files = stego.extract_layered(target, out_dir, passwords, layers=layers, progress=_prog)
                else:
                    files = stego.extract_archive(
                        target,
                        out_dir,
                        passwords=passwords or None,
                        progress=_prog,
                    )
                return {
                    "count": len(files),
                    "outDir": str(out_dir),
                    "files": [str(f) for f in files[:60]],
                }
            finally:
                if temp_joined is not None:
                    try:
                        temp_joined.unlink(missing_ok=True)
                        temp_joined.parent.rmdir()
                    except OSError:
                        pass

        return _ok({"taskId": self._tasks.start(job)})

    # ---- 分享与整理（core.share） ----

    def _ensure_mod_index(self) -> mod_index.ModIndex:
        if self._mod_index is not None:
            return self._mod_index
        cache = _mod_cache_path()
        if cache.is_file():
            self._mod_index = mod_index.ModIndex.load(cache)
            return self._mod_index
        self._mod_index = mod_index.ModIndex()
        return self._mod_index

    def start_share_export(self, opts: dict[str, Any]) -> dict[str, Any]:
        card_paths = [str(p) for p in (opts.get("cardPaths") or []) if p and Path(p).is_file()]
        out_dir = Path(str(opts.get("outDir") or "").strip())
        group_by_char = bool(opts.get("groupByChar", True))
        exclude_raw = str(opts.get("excludeGuids") or "")
        exclude_set = {line.strip() for line in exclude_raw.splitlines() if line.strip()} or None

        if not card_paths:
            return _err("请先添加至少一张角色卡")
        if not str(opts.get("outDir") or "").strip():
            return _err("请选择分享包输出目录")

        def job(report: Callable[[int, int, str], None]) -> dict[str, Any]:
            idx = self._ensure_mod_index()
            if not idx.entries:
                dirs = [d for d in settings.guess_mod_dirs() if Path(d).is_dir()]
                if dirs:
                    report(10, 100, "首次构建 Mod 索引以匹配依赖…")
                    idx.build(dirs)
                    idx.save(_mod_cache_path())
                    self._mod_index = idx
            res = share.build_share_package(
                card_paths,
                idx,
                out_dir,
                group_by_char=group_by_char,
                exclude_guids=exclude_set,
                progress=lambda cur, tot, msg: report(cur, tot, msg),
            )
            return {"report": res, "outDir": str(out_dir)}

        return _ok({"taskId": self._tasks.start(job)})

    def start_share_import(self, opts: dict[str, Any]) -> dict[str, Any]:
        pkg_dir = Path(str(opts.get("pkgDir") or "").strip())
        card_target = Path(str(opts.get("cardTarget") or "").strip())
        mod_target_str = str(opts.get("modTarget") or "").strip()
        mod_target = Path(mod_target_str) if mod_target_str else None

        if not pkg_dir.is_dir():
            return _err("请选择有效的分享包目录")
        if not str(opts.get("cardTarget") or "").strip():
            return _err("请选择角色卡导入目标目录")

        def job(report: Callable[[int, int, str], None]) -> dict[str, Any]:
            res = share.restore_package(
                pkg_dir,
                card_target,
                mod_target=mod_target,
                progress=lambda cur, tot, msg: report(cur, tot, msg),
            )
            return {"report": res, "cardTarget": str(card_target)}

        return _ok({"taskId": self._tasks.start(job)})

    def start_organize_cards(self, opts: dict[str, Any]) -> dict[str, Any]:
        src_dir = Path(str(opts.get("srcDir") or "").strip())
        out_dir = Path(str(opts.get("outDir") or "").strip())
        by = str(opts.get("by") or "type")
        move = bool(opts.get("move", False))

        if not str(opts.get("srcDir") or "").strip() or not src_dir.is_dir():
            return _err("请选择有效的待整理卡片目录")
        if not str(opts.get("outDir") or "").strip():
            return _err("请选择整理后的输出目录")

        def job(report: Callable[[int, int, str], None]) -> dict[str, Any]:
            res = share.organize_cards(
                src_dir,
                out_dir,
                by=by,
                move=move,
                progress=lambda cur, tot, msg: report(cur, tot, msg),
            )
            return {"report": res, "outDir": str(out_dir)}

        return _ok({"taskId": self._tasks.start(job)})

    # ---- Mod 仓库（core.mod_index） ----

    def _serialize_mods(self, idx: mod_index.ModIndex) -> list[dict[str, Any]]:
        items = []
        for entry in idx.entries.values():
            p = Path(entry.path)
            size_mb = (p.stat().st_size / (1024 * 1024)) if p.is_file() else 0.0
            items.append(
                {
                    "guid": entry.guid,
                    "name": entry.name,
                    "version": entry.version,
                    "author": entry.author,
                    "fileName": p.name,
                    "path": entry.path,
                    "sizeMB": round(size_mb, 2),
                }
            )
        items.sort(key=lambda x: (x["name"] or x["fileName"]).lower())
        return items

    def get_cached_mods(self) -> dict[str, Any]:
        idx = self._ensure_mod_index()
        items = self._serialize_mods(idx)
        return _ok({"total": len(items), "items": items})

    def start_scan_mods(self, dirs: list[str] | None = None) -> dict[str, Any]:
        target_dirs = [d for d in (dirs or settings.guess_mod_dirs()) if d and Path(d).is_dir()]
        if not target_dirs:
            return _err("尚未配置有效的 Mod 目录，请先在「外观与设置」中填写游戏目录")

        def job(report: Callable[[int, int, str], None]) -> dict[str, Any]:
            prev = self._ensure_mod_index()
            idx = mod_index.ModIndex().build(
                target_dirs,
                previous=prev if prev.files else None,
                progress=lambda cur, name: report(cur, max(cur, 1), f"索引：{Path(name).name}" if name else "整理索引…"),
            )
            idx.save(_mod_cache_path())
            self._mod_index = idx
            items = self._serialize_mods(idx)
            return {"total": len(items), "items": items}

        return _ok({"taskId": self._tasks.start(job)})

    def scan_mods(self, dirs: list[str] | None = None) -> dict[str, Any]:
        """同步轻量兼容接口。"""
        try:
            target_dirs = [d for d in (dirs or settings.guess_mod_dirs()) if d and Path(d).is_dir()]
            if not target_dirs:
                return _err("尚未配置有效的 Mod 目录")
            prev = self._ensure_mod_index()
            idx = mod_index.ModIndex().build(target_dirs, previous=prev if prev.files else None)
            idx.save(_mod_cache_path())
            self._mod_index = idx
            items = self._serialize_mods(idx)
            return _ok({"total": len(items), "items": items})
        except Exception as exc:  # noqa: BLE001
            return _err(f"Mod 索引失败：{exc}")

    def check_card_mods(self, card_path: str) -> dict[str, Any]:
        try:
            idx = self._ensure_mod_index()
            rep = mod_index.check_card(card_path, idx, strict=True)
            return _ok(
                {
                    "cardPath": str(card_path),
                    "total": len(rep.present) + len(rep.missing),
                    "present": sorted(rep.present),
                    "missing": sorted(rep.missing),
                }
            )
        except Exception as exc:  # noqa: BLE001
            return _err(f"缺失检测失败：{exc}")

    def export_manifest(self, out_path: str) -> dict[str, Any]:
        from core import manifest, identity
        try:
            count = manifest.export_manifest(self._ensure_mod_index(), out_path, identity.get_identity())
            return _ok({"count": count})
        except Exception as exc:
            return _err(f"导出清单失败：{exc}")

    def compare_manifest(self, path: str) -> dict[str, Any]:
        from core import manifest
        try:
            mine = manifest.build_manifest(self._ensure_mod_index(), {})
            theirs = manifest.load_manifest(path)
            return _ok(manifest.reconcile_manifests(mine, theirs))
        except Exception as exc:
            return _err(f"清单对账失败：{exc}")

    def start_export_mod_list(self, path: str, out_dir: str) -> dict[str, Any]:
        from core import manifest
        try:
            guids = manifest.load_manifest(path)["guids"]
            if not guids or not out_dir.strip():
                return _err("清单为空或未选择输出目录")
            index = self._ensure_mod_index()
            target = Path(out_dir) / "mods.zip"
            number = 2
            while target.exists():
                target = Path(out_dir) / f"mods ({number}).zip"
                number += 1
        except Exception as exc:
            return _err(f"读取清单失败：{exc}")

        def job(report):
            count, skipped = mod_index.export_as_zip(guids, index, target, progress=report)
            return {"count": count, "skipped": skipped, "path": str(target)}
        return _ok({"taskId": self._tasks.start(job)})

    def export_mod_guids(self, out_path: str) -> dict[str, Any]:
        try:
            idx = self._ensure_mod_index()
            if not idx.entries:
                return _err("请先扫描本地 Mod 仓库")
            count = mod_index.export_guid_list(idx, out_path)
            return _ok({"count": count, "path": str(out_path)})
        except Exception as exc:  # noqa: BLE001
            return _err(f"导出 GUID 列表失败：{exc}")

    def start_archive_unreferenced(self, opts: dict[str, Any]) -> dict[str, Any]:
        card_dir = Path(str(opts.get("cardDir") or "").strip())
        archive_dir = Path(str(opts.get("archiveDir") or "").strip())
        move = bool(opts.get("move", False))

        if not str(opts.get("cardDir") or "").strip() or not card_dir.is_dir():
            return _err("请选择角色卡目录用于分析引用")
        if not str(opts.get("archiveDir") or "").strip():
            return _err("请选择归档目标目录")

        def job(report: Callable[[int, int, str], None]) -> dict[str, Any]:
            idx = self._ensure_mod_index()
            if not idx.entries:
                raise ValueError("请先扫描本地 Mod 仓库")
            card_paths = [str(p) for p in card_dir.rglob("*.png") if p.is_file()]
            if not card_paths:
                raise ValueError("所选角色卡目录下未找到 PNG 文件")
            res = mod_index.archive_unreferenced(
                idx,
                card_paths,
                archive_dir,
                move=move,
                progress=lambda cur, tot, msg: report(cur, tot, msg),
            )
            return {"report": res, "archiveDir": str(archive_dir)}

        return _ok({"taskId": self._tasks.start(job)})

    def start_organize_mods(self, opts: dict[str, Any]) -> dict[str, Any]:
        target_dir = Path(str(opts.get("targetDir") or "").strip())
        move = bool(opts.get("move", False))
        if not str(opts.get("targetDir") or "").strip():
            return _err("请选择按作者整理的输出目录")

        def job(report: Callable[[int, int, str], None]) -> dict[str, Any]:
            idx = self._ensure_mod_index()
            if not idx.entries:
                raise ValueError("请先扫描本地 Mod 仓库")
            res = mod_index.organize_by_author(
                idx,
                target_dir,
                move=move,
                progress=lambda cur, tot, msg: report(cur, tot, msg),
            )
            return {"report": res, "targetDir": str(target_dir)}

        return _ok({"taskId": self._tasks.start(job)})

    # ---- 场景卡分析与角色提取（core.scene_card） ----

    def analyze_scene(self, path: str) -> dict[str, Any]:
        try:
            p = Path(path)
            raw = p.read_bytes()
            info = scene_card.analyze_scene(p)
            preview = scene_card.get_scene_preview(raw)
            embedded = scene_card.find_embedded_characters(raw)
            chars = []
            for idx, ch in enumerate(info.get("characters") or []):
                thumb = embedded[idx].thumbnail if idx < len(embedded) else b""
                chars.append(
                    {
                        "index": idx,
                        "name": ch.get("name", ""),
                        "game": ch.get("game", ""),
                        "previewUrl": _bytes_to_data_url(thumb, "image/png"),
                    }
                )
            return _ok(
                {
                    "path": str(p),
                    "fileName": p.name,
                    "previewUrl": _bytes_to_data_url(preview, "image/png"),
                    "characterCount": int(info.get("character_count", len(chars))),
                    "characters": chars,
                    "modIds": sorted((info.get("mod_ids") or {}).keys()),
                }
            )
        except Exception as exc:  # noqa: BLE001
            return _err(f"场景卡解析失败：{exc}")

    def extract_scene_characters(self, scene_path: str, out_dir: str) -> dict[str, Any]:
        try:
            saved = scene_card.extract_characters_to(scene_path, out_dir)
            return _ok({"count": len(saved), "saved": saved, "outDir": str(out_dir)})
        except Exception as exc:  # noqa: BLE001
            return _err(f"提取角色卡失败：{exc}")

    # ---- 软件自更新（core.updater） ----

    def get_update_info(self) -> dict[str, Any]:
        try:
            last = updater.last_update_result()
            return _ok(
                {
                    "currentVersion": updater.current_version(),
                    "isFrozen": bool(getattr(sys, "frozen", False)),
                    "releasesUrl": updater.RELEASES_URL,
                    "lastResult": last,
                    "hasPendingArtifact": self._pending_update_artifact is not None,
                }
            )
        except Exception as exc:  # noqa: BLE001
            return _err(str(exc))

    def start_check_update(self) -> dict[str, Any]:
        # 重新检查版本时先清理上一次旧下载（规则 #10914）
        self.cleanup_pending_update()
        self._latest_release = None

        def job(report: Callable[[int, int, str], None]) -> dict[str, Any]:
            report(10, 100, "正在连接 GitHub 检查最新版本…")
            rel = updater.check_for_update(
                progress=lambda cur, tot, msg: report(cur, tot or 100, msg or "正在检查版本…")
            )
            self._latest_release = rel
            if rel is None:
                return {
                    "hasUpdate": False,
                    "currentVersion": updater.current_version(),
                }
            return {
                "hasUpdate": True,
                "currentVersion": updater.current_version(),
                "release": {
                    "version": rel.version,
                    "notes": rel.notes,
                    "pageUrl": rel.page_url,
                    "size": rel.size,
                    "hasSha256": bool(rel.sha256),
                },
            }

        return _ok({"taskId": self._tasks.start(job)})

    def start_download_update(self) -> dict[str, Any]:
        rel = self._latest_release
        if rel is None:
            return _err("请先检查新版本")

        self.cleanup_pending_update()

        def job(report: Callable[[int, int, str], None]) -> dict[str, Any]:
            artifact = updater.download_update(
                rel,
                progress=lambda cur, tot, msg: report(cur, tot, msg),
            )
            self._pending_update_artifact = artifact
            return {
                "version": rel.version,
                "artifactPath": str(artifact),
                "isFrozen": bool(getattr(sys, "frozen", False)),
            }

        return _ok({"taskId": self._tasks.start(job)})

    def apply_update_and_restart(self) -> dict[str, Any]:
        if not getattr(sys, "frozen", False):
            return _err("当前为源码运行模式，不自动覆盖开发目录；请直接打开下载目录或发布页。")
        if self._pending_update_artifact is None or self._latest_release is None:
            return _err("尚未下载并校验新版本文件")
        try:
            plan = updater.prepare_update(self._pending_update_artifact, self._latest_release)
            self._installing_update = True
            updater.launch_update(plan)
            if self._window is not None:
                threading.Timer(0.25, self._window.destroy).start()
            return _ok({"restarting": True, "plan": str(plan)})
        except Exception as exc:  # noqa: BLE001
            self._installing_update = False
            return _err(f"启动更新替换失败：{exc}")
