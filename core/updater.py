"""从本项目 GitHub Release 检查更新，校验下载并准备 Windows 原位替换。"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
import uuid

from core import settings

APP_VERSION = "v0.8.0"
REPOSITORY = "galact-byte/KKTools"
RELEASES_URL = f"https://github.com/{REPOSITORY}/releases/latest"
_API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
_BUILD_INFO = Path(__file__).with_name("build_info.json")
_MAX_DOWNLOAD = 512 * 1024 * 1024
_ALLOWED_HOSTS = {"api.github.com", "github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"}
Progress = Callable[[int, int, str], None]


class UpdateError(RuntimeError):
    """可以直接展示给用户的检查、下载或安装准备错误。"""


@dataclass(frozen=True)
class Release:
    version: str
    notes: str
    page_url: str
    download_url: str
    size: int
    sha256: str


def _version(text: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", str(text))
    if not match:
        raise UpdateError(f"无法识别稳定版版本号：{text}")
    return tuple(int(x) for x in match.groups())


def current_version() -> str:
    try:
        value = json.loads(_BUILD_INFO.read_text(encoding="utf-8"))["version"]
        _version(value)
        return str(value)
    except (OSError, ValueError, KeyError, TypeError, UpdateError):
        return APP_VERSION


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.hostname not in _ALLOWED_HOSTS
            or parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise UpdateError("更新地址不是受支持的 GitHub HTTPS 地址")


class _ReleaseRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open_url(request: Request):
    _validate_url(request.full_url)
    return build_opener(_ReleaseRedirect()).open(request, timeout=20)


def _request(url: str) -> Request:
    return Request(url, headers={"User-Agent": f"KKTools/{current_version()}",
                                 "Accept": "application/vnd.github+json" if url == _API_URL else "application/octet-stream"})


def parse_release(data: dict, installed_version: str) -> Release | None:
    if not isinstance(data, dict):
        raise UpdateError("服务器返回的版本信息格式不正确")
    if data.get("draft") or data.get("prerelease"):
        return None
    tag = str(data.get("tag_name", ""))
    if _version(tag) <= _version(installed_version):
        return None
    assets = data.get("assets")
    if not isinstance(assets, list):
        raise UpdateError("新版本未提供 Windows 程序")
    asset = next((x for x in assets if isinstance(x, dict) and x.get("name") == "KKTools.exe"), None)
    if not asset or asset.get("state", "uploaded") != "uploaded":
        raise UpdateError("新版本未提供完整的 KKTools.exe，请稍后再试")
    url = str(asset.get("browser_download_url", ""))
    page = str(data.get("html_url", ""))
    expected = f"https://github.com/{REPOSITORY}/releases/"
    if url != f"{expected}download/{tag}/KKTools.exe" or page != f"{expected}tag/{tag}":
        raise UpdateError("发布包不属于本项目的正式发布地址")
    size = asset.get("size")
    digest = str(asset.get("digest", ""))
    if type(size) is not int or not 0 < size <= _MAX_DOWNLOAD:
        raise UpdateError("发布包大小异常，已停止更新")
    if not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest):
        raise UpdateError("发布包缺少 SHA-256 校验信息，请前往发布页检查")
    return Release(tag, str(data.get("body") or "本次发布未提供更新说明。"), page, url, size, digest[7:].lower())


def check_for_update(installed_version: str | None = None, progress: Progress | None = None) -> Release | None:
    if progress:
        progress(0, 0, "正在检查新版本…")
    try:
        with _open_url(_request(_API_URL)) as response:
            _validate_url(response.geturl())
            raw = response.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise UpdateError("服务器返回的版本信息过大")
            data = json.loads(raw)
        return parse_release(data, installed_version or current_version())
    except HTTPError as exc:
        if exc.code in (403, 429):
            raise UpdateError("GitHub 请求过于频繁或被限流，请稍后重试，也可打开发布页。") from exc
        raise UpdateError(f"检查更新失败（HTTP {exc.code}），请稍后重试或打开发布页。") from exc
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        raise UpdateError(f"无法获取更新信息，请检查网络或稍后重试：{exc}") from exc


def _verify(path: Path, release: Release) -> None:
    if path.stat().st_size != release.size:
        raise UpdateError("下载的文件大小不完整，已停止安装，请重试")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise UpdateError("下载内容不是 Windows 程序，已停止安装")
        stream.seek(0)
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != release.sha256:
        raise UpdateError("下载文件的 SHA-256 校验失败，已停止安装，请重试")


def download_update(release: Release, app_dir: str | Path | None = None, progress: Progress | None = None) -> Path:
    root = Path(app_dir) if app_dir is not None else settings.app_dir()
    stage = root / ".kktools-update" / uuid.uuid4().hex
    try:
        stage.mkdir(parents=True)
        part = stage / "KKTools.exe.part"
        received = 0
        with _open_url(_request(release.download_url)) as response, part.open("xb") as output:
            _validate_url(response.geturl())
            while block := response.read(256 * 1024):
                received += len(block)
                if received > release.size:
                    raise UpdateError("下载内容超过发布包声明的大小，已停止更新")
                output.write(block)
                if progress:
                    progress(received, release.size, "正在下载更新…")
        if progress:
            progress(received, release.size, "正在校验下载文件…")
        _verify(part, release)
        artifact = part.with_suffix("")
        part.rename(artifact)
        return artifact
    except Exception as exc:
        if stage.is_dir():
            shutil.rmtree(stage, ignore_errors=True)
        if isinstance(exc, UpdateError):
            raise
        raise UpdateError(f"下载更新失败，请检查网络及程序目录写入权限：{exc}") from exc


def discard_download(artifact: str | Path, *, app_dir: str | Path | None = None) -> None:
    """仅清理本次下载拥有的暂存目录，拒绝删除程序或用户资料。"""
    root = Path(app_dir) if app_dir is not None else settings.app_dir()
    artifact = Path(artifact).resolve()
    if artifact.name != "KKTools.exe" or artifact.parent.parent != root.resolve() / ".kktools-update":
        raise UpdateError("拒绝清理不属于本次更新的文件")
    shutil.rmtree(artifact.parent, ignore_errors=True)


def prepare_update(artifact: str | Path, release: Release, *, executable: str | Path | None = None) -> Path:
    target = Path(executable or sys.executable).resolve()
    artifact = Path(artifact).resolve()
    stage = artifact.parent
    if (target.suffix.lower() != ".exe" or not target.is_file()
            or stage.parent != target.parent / ".kktools-update"
            or artifact.name != "KKTools.exe"):
        raise UpdateError("更新文件或程序位置不正确，请重新下载")
    _verify(artifact, release)
    helper = stage / "install.ps1"
    shutil.copyfile(Path(__file__).with_name("update_helper.ps1"), helper)
    plan = stage / "plan.json"
    plan.write_text(json.dumps({
        "parent_pid": os.getpid(), "target": str(target), "source": str(artifact),
        "sha256": release.sha256, "size": release.size, "version": release.version,
    }, ensure_ascii=False), encoding="utf-8")
    return plan


def launch_update(plan: str | Path) -> subprocess.Popen:
    if sys.platform != "win32":
        raise UpdateError("自动替换目前仅支持 Windows 便携版")
    plan = Path(plan).resolve()
    helper = plan.with_name("install.ps1")
    if not plan.is_file() or not helper.is_file():
        raise UpdateError("更新准备文件缺失，请重新下载")
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    try:
        return subprocess.Popen(
            [str(powershell), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(helper)],
            cwd=str(plan.parent), creationflags=subprocess.CREATE_NO_WINDOW,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        raise UpdateError(f"无法启动更新助手，程序尚未退出：{exc}") from exc


def last_update_result(app_dir: str | Path | None = None) -> dict | None:
    root = Path(app_dir) if app_dir is not None else settings.app_dir()
    try:
        data = json.loads((root / ".kktools-update-result.json").read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None
