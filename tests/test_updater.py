"""更新行为：版本、可信下载、失败清理，以及独立程序副本的替换与回滚。"""

import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest


def test_update_service_is_available():
    assert importlib.util.find_spec("core.updater") is not None, "缺少更新服务：尚不能检查、下载和安装新版本"


@pytest.fixture
def updater():
    if importlib.util.find_spec("core.updater") is None:
        pytest.skip("更新服务尚未实现")
    return importlib.import_module("core.updater")


def release_data(payload=b"MZnew-program", version="v0.7.0"):
    return {
        "tag_name": version,
        "html_url": f"https://github.com/galact-byte/KKTools/releases/tag/{version}",
        "body": "新增测试功能。",
        "draft": False,
        "prerelease": False,
        "assets": [{
            "name": "KKTools.exe", "state": "uploaded", "size": len(payload),
            "digest": "sha256:" + hashlib.sha256(payload).hexdigest(),
            "browser_download_url": f"https://github.com/galact-byte/KKTools/releases/download/{version}/KKTools.exe",
        }],
    }


class Response(io.BytesIO):
    def __init__(self, data, url):
        super().__init__(data)
        self.url = url

    def geturl(self):
        return self.url


@pytest.mark.parametrize(("current", "remote", "available"), [
    ("v0.9.0", "v0.10.0", True),
    ("0.6.0", "v0.6.0", False),
    ("v0.8.0", "v0.7.0", False),
])
def test_update_is_offered_only_for_newer_numeric_versions(updater, current, remote, available):
    result = updater.parse_release(release_data(version=remote), current)
    assert bool(result) is available


@pytest.mark.parametrize("field", ["draft", "prerelease"])
def test_drafts_and_prereleases_are_not_installed(updater, field):
    data = release_data()
    data[field] = True
    assert updater.parse_release(data, "0.6.0") is None


@pytest.mark.parametrize("alter", [
    lambda d: d.update(tag_name="v0.7.0-beta.1"),
    lambda d: d.update(assets=[]),
    lambda d: d["assets"][0].update(digest=None),
    lambda d: d["assets"][0].update(size=-1),
    lambda d: d["assets"][0].update(browser_download_url="https://example.com/KKTools.exe"),
    lambda d: d["assets"][0].update(browser_download_url="http://github.com/galact-byte/KKTools/releases/download/v0.7.0/KKTools.exe"),
])
def test_unverifiable_releases_are_rejected(updater, alter):
    data = release_data()
    alter(data)
    with pytest.raises(updater.UpdateError):
        updater.parse_release(data, "0.6.0")


def test_live_api_boundary_parses_release_and_reports_rate_limit(updater, monkeypatch):
    monkeypatch.setattr(updater, "_open_url", lambda request: Response(json.dumps(release_data()).encode(), request.full_url))
    result = updater.check_for_update("0.6.0")
    assert result.version == "v0.7.0"
    from urllib.error import HTTPError
    def limited(request):
        raise HTTPError(request.full_url, 403, "Forbidden", {}, None)
    monkeypatch.setattr(updater, "_open_url", limited)
    with pytest.raises(updater.UpdateError, match="频繁|限流"):
        updater.check_for_update("0.6.0")


def test_download_verifies_bytes_and_preserves_local_files(updater, tmp_path, monkeypatch):
    payload = b"MZverified-program"
    release = updater.parse_release(release_data(payload), "0.6.0")
    (tmp_path / "config.json").write_text('{"identity":"keep"}', encoding="utf-8")
    monkeypatch.setattr(updater, "_open_url", lambda request: Response(payload, request.full_url))
    events = []
    artifact = updater.download_update(release, tmp_path, progress=lambda *args: events.append(args))
    assert artifact.read_bytes() == payload
    assert (tmp_path / "config.json").read_text(encoding="utf-8") == '{"identity":"keep"}'
    assert events[-1][0:2] == (len(payload), len(payload))
    assert any("校验" in event[2] for event in events), "下载后的校验阶段必须可见"


@pytest.mark.parametrize("payload", [b"MZtruncated", b"MZtampered-program", b"<html>server error</html>"])
def test_bad_downloads_never_replace_program_and_leave_no_partial_file(updater, tmp_path, monkeypatch, payload):
    original = tmp_path / "KKTools.exe"
    original.write_bytes(b"MZoriginal")
    release = updater.parse_release(release_data(b"MZexpected-program"), "0.6.0")
    monkeypatch.setattr(updater, "_open_url", lambda request: Response(payload, request.full_url))
    with pytest.raises(updater.UpdateError):
        updater.download_update(release, tmp_path)
    assert original.read_bytes() == b"MZoriginal"
    assert not list(tmp_path.rglob("*.part"))
    assert not list((tmp_path / ".kktools-update").glob("*/KKTools.exe"))


def test_prepare_rechecks_download_and_rejects_modified_file(updater, tmp_path, monkeypatch):
    payload = b"MZverified-program"
    release = updater.parse_release(release_data(payload), "0.6.0")
    monkeypatch.setattr(updater, "_open_url", lambda request: Response(payload, request.full_url))
    artifact = updater.download_update(release, tmp_path)
    target = tmp_path / "renamed tool.exe"
    target.write_bytes(b"MZold")
    artifact.write_bytes(b"MZchanged-after-download")
    with pytest.raises(updater.UpdateError):
        updater.prepare_update(artifact, release, executable=target)
    assert target.read_bytes() == b"MZold"


def test_discard_download_removes_only_its_own_stage(updater, tmp_path, monkeypatch):
    payload = b"MZverified-program"
    release = updater.parse_release(release_data(payload), "0.6.0")
    monkeypatch.setattr(updater, "_open_url", lambda request: Response(payload, request.full_url))
    artifact = updater.download_update(release, tmp_path)
    config = tmp_path / "config.json"
    config.write_bytes(b"keep")
    updater.discard_download(artifact, app_dir=tmp_path)
    assert not artifact.parent.exists()
    with pytest.raises(updater.UpdateError):
        updater.discard_download(config, app_dir=tmp_path)
    assert config.read_bytes() == b"keep"


@pytest.fixture(scope="module")
def tiny_programs(tmp_path_factory):
    if sys.platform != "win32":
        pytest.skip("Windows 原生更新助手的进程与文件替换测试")
    root = tmp_path_factory.mktemp("updater-native-programs")
    compiler = Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
    if not compiler.is_file():
        pytest.skip("本机没有可用于测试的 .NET 编译器")
    binaries = {}
    for version in ("old", "new"):
        source = root / f"{version}.cs"
        source.write_text('using System; using System.IO; using System.Threading; class Program { static void Main() { File.WriteAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "started-' + version + '.txt"), "' + version + '"); Thread.Sleep(4000); } }', encoding="utf-8")
        exe = root / f"{version}.exe"
        subprocess.run([str(compiler), "/nologo", "/target:winexe", f"/out:{exe}", str(source)], check=True, capture_output=True)
        binaries[version] = exe.read_bytes()
    return binaries


@pytest.mark.parametrize(('broken', 'hash_cmdlet_available'), [(False, True), (True, True), (False, False)], ids=['install', 'rollback', 'install_without_hash_cmdlet'])
def test_windows_helper_waits_restarts_and_rolls_back_in_separate_copy(updater, tmp_path, monkeypatch, tiny_programs, broken, hash_cmdlet_available):
    root = tmp_path / "升级副本 & 空格"
    root.mkdir()
    target = root / "renamed tool.exe"
    target.write_bytes(tiny_programs["old"])
    (root / "config.json").write_bytes(b'{"keep":true}')
    (root / "my-cards").mkdir()
    (root / "my-cards" / "card.png").write_bytes(b"original-card")
    payload = b"MZthis-is-not-a-runnable-program" if broken else tiny_programs["new"]
    release = updater.parse_release(release_data(payload), "0.6.0")
    monkeypatch.setattr(updater, "_open_url", lambda request: Response(payload, request.full_url))
    artifact = updater.download_update(release, root)
    plan = updater.prepare_update(artifact, release, executable=target)
    if not hash_cmdlet_available:
        helper_path = plan.with_name('install.ps1')
        missing_hash_setup = "Import-Module (Join-Path $PSHOME 'Modules\\Microsoft.PowerShell.Management')\nImport-Module (Join-Path $PSHOME 'Modules\\Microsoft.PowerShell.Utility')\nRemove-Item Function:\\Get-FileHash -ErrorAction SilentlyContinue\n$PSModuleAutoLoadingPreference = 'None'\n"
        helper_path.write_text(missing_hash_setup + helper_path.read_text(encoding='utf-8'), encoding='utf-8')
    parent = subprocess.Popen([str(target)], cwd=root)
    data = json.loads(plan.read_text(encoding="utf-8"))
    data["parent_pid"] = parent.pid
    plan.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    helper = updater.launch_update(plan)
    try:
        time.sleep(0.4)
        assert target.read_bytes() == tiny_programs["old"], "原程序未退出时不能替换"
        helper.wait(timeout=30)
        result = json.loads((root / ".kktools-update-result.json").read_text(encoding="utf-8-sig"))
        assert result["ok"] is (not broken), result
        assert target.read_bytes() == (tiny_programs["old"] if broken else tiny_programs["new"])
        marker = root / ("started-old.txt" if broken else "started-new.txt")
        assert marker.is_file()
        assert (root / "config.json").read_bytes() == b'{"keep":true}'
        assert (root / "my-cards" / "card.png").read_bytes() == b"original-card"
        assert not list((root / ".kktools-update").glob("*"))
    finally:
        parent.wait(timeout=10)
        time.sleep(4)
