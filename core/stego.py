"""解包 / 打包 / 隐写伪装 / 分卷。

伪装原理（经典手法）：把 zip 压缩包**追加在一个真实载体文件（视频/图片）之后**。
得到的文件既能被播放器/看图器当作正常媒体打开，又能被解压软件识别为 zip——因为
zip 的目录信息在文件末尾，解压器从尾部定位，能容忍前面的"垃圾"前缀。

Python 的 zipfile 本身就支持带前缀的 zip（自解压 exe 同理），故解包时直接用
zipfile 打开伪装文件即可，无需手动剥离载体。
"""

from __future__ import annotations

import hashlib
import json
import random
import tempfile
import zlib
import zipfile
from pathlib import Path
from typing import Callable, Iterable

try:
    import pyzipper
    HAVE_PYZIPPER = True
except ImportError:  # 未装则仅支持不加密打包/解包
    HAVE_PYZIPPER = False

ProgressCb = Callable[[int, int, str], None]  # (当前, 总数, 描述)


def pack_folder(
    folder: str | Path,
    out_zip: str | Path,
    *,
    compress: bool = True,
    password: str | None = None,
    progress: ProgressCb | None = None,
) -> str:
    """把文件夹打包成 zip。给 password 则用 AES-256 加密（需 pyzipper）。返回输出路径。"""
    folder = Path(folder)
    out_zip = Path(out_zip)
    files = [p for p in folder.rglob("*") if p.is_file()]
    total = len(files)
    if password:
        if not HAVE_PYZIPPER:
            raise RuntimeError("加密打包需要 pyzipper，请先安装：pip install pyzipper")
        with pyzipper.AESZipFile(
            out_zip, "w", compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES
        ) as zf:
            zf.setpassword(password.encode("utf-8"))
            for i, p in enumerate(files, 1):
                zf.write(p, p.relative_to(folder).as_posix())
                if progress:
                    progress(i, total, p.name)
    else:
        mode = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
        with zipfile.ZipFile(out_zip, "w", mode) as zf:
            for i, p in enumerate(files, 1):
                zf.write(p, p.relative_to(folder).as_posix())
                if progress:
                    progress(i, total, p.name)
    return str(out_zip)


_CARRIER_SUFFIXES = (".mp4", ".mkv", ".mov", ".avi", ".webm", ".jpg", ".jpeg", ".png", ".webp", ".gif")


def pick_carrier_from_pool(pool_dir: str | Path) -> str:
    """从素材池目录里随机挑一个可用作载体的图片/视频文件。

    比固定单一载体更隐蔽（每次伪装的"外壳"都不同）。目录空或无合适文件则报错。
    """
    pool = Path(pool_dir)
    if not pool.is_dir():
        raise FileNotFoundError(f"素材池目录无效: {pool_dir}")
    files = [p for p in pool.iterdir()
             if p.is_file() and p.suffix.lower() in _CARRIER_SUFFIXES]
    if not files:
        files = [p for p in pool.iterdir() if p.is_file()]  # 兜底：池里任意文件
    if not files:
        raise FileNotFoundError("素材池目录为空，没有可用的载体文件")
    return str(random.choice(files))


def disguise(carrier: str | Path, payload_zip: str | Path, out_path: str | Path) -> str:
    """把 payload_zip 追加到 carrier 之后，生成伪装文件。"""
    carrier = Path(carrier)
    payload_zip = Path(payload_zip)
    out_path = Path(out_path)
    with open(out_path, "wb") as out:
        out.write(carrier.read_bytes())
        out.write(payload_zip.read_bytes())
    return str(out_path)


def pack_and_disguise(
    folder: str | Path,
    carrier: str | Path,
    out_path: str | Path,
    *,
    password: str | None = None,
    progress: ProgressCb | None = None,
) -> str:
    """打包文件夹并伪装成载体文件，一步到位。给 password 则 AES 加密。"""
    out_path = Path(out_path)
    tmp_zip = out_path.with_suffix(out_path.suffix + ".tmp.zip")
    try:
        pack_folder(folder, tmp_zip, password=password, progress=progress)
        disguise(carrier, tmp_zip, out_path)
    finally:
        if tmp_zip.exists():
            tmp_zip.unlink()
    return str(out_path)


def looks_like_zip(path: str | Path) -> bool:
    """文件能否被当作 zip 打开（含伪装在载体之后的 zip）。

    只校验目录结构是否可读（轻量），不做 testzip 全量 CRC 校验——后者会读完
    整个文件，伪装视频可能上 GB，会非常慢。
    """
    try:
        with zipfile.ZipFile(path) as zf:
            zf.namelist()
        return True
    except (zipfile.BadZipFile, OSError):
        return False


def extract_archive(
    path: str | Path,
    out_dir: str | Path,
    *,
    passwords: list[str] | None = None,
    progress: ProgressCb | None = None,
) -> list[str]:
    """解包 zip（含伪装在载体后的 zip，含 AES 加密）。

    passwords 给定时依次尝试解密（先尝试无密码=未加密包）。返回解出的文件相对路径列表。
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    zf_cls = pyzipper.AESZipFile if HAVE_PYZIPPER else zipfile.ZipFile
    candidates: list[str | None] = [None] + [p for p in (passwords or []) if p]
    last_err: Exception | None = None
    for pw in candidates:
        try:
            with zf_cls(path) as zf:
                names = [n for n in zf.namelist() if not n.endswith("/")]
                if pw:
                    zf.setpassword(pw.encode("utf-8"))
                # 先试读第一个文件验证密码，避免错误密码下产生半套文件
                if names:
                    with zf.open(names[0]) as f:
                        f.read(1)
                extracted: list[str] = []
                total = len(names)
                for i, name in enumerate(names, 1):
                    zf.extract(name, out_dir)
                    extracted.append(name)
                    if progress:
                        progress(i, total, name)
                return extracted
        except (RuntimeError, zipfile.BadZipFile, OSError) as exc:
            last_err = exc
            continue
    raise last_err or RuntimeError("解压失败：可能需要正确的密码")



def split_file(
    path: str | Path,
    chunk_size_mb: float,
    out_dir: str | Path | None = None,
) -> list[str]:
    """把文件分卷为 name.001 / name.002 ...，返回分卷路径列表。"""
    path = Path(path)
    out_dir = Path(out_dir) if out_dir else path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    chunk = int(chunk_size_mb * 1024 * 1024)
    if chunk <= 0:
        raise ValueError("分卷大小必须大于 0")
    parts: list[str] = []
    with open(path, "rb") as f:
        idx = 1
        while True:
            data = f.read(chunk)
            if not data:
                break
            part = out_dir / f"{path.name}.{idx:03d}"
            part.write_bytes(data)
            parts.append(str(part))
            idx += 1
    return parts


def join_parts(first_part: str | Path, out_path: str | Path) -> str:
    """把 name.001 / name.002 ... 合并回原文件。传入 .001 分卷路径。"""
    first_part = Path(first_part)
    stem = first_part.with_suffix("")  # 去掉 .001
    out_path = Path(out_path)
    parts = sorted(stem.parent.glob(stem.name + ".[0-9][0-9][0-9]"))
    if not parts:
        raise FileNotFoundError("未找到分卷文件")
    with open(out_path, "wb") as out:
        for p in parts:
            out.write(p.read_bytes())
    return str(out_path)


# ============================================================================
# 多重封缄（多层嵌套加密）+ 恢复校验记录
#
# “封缄”= 把内容逐层用不同密码 AES 加密：第 1 层把文件夹打成加密 zip，
# 第 2 层再把上一层的 zip 当作唯一成员打成加密 zip……如此 N 层。
# 解封时按相反顺序、用对应密码逐层剥离。最外层旁写一个明文伴随文件
# <out>.kkseal.json 记录层数（不含任何密码），解封时无需用户猜层数。
# ============================================================================

_SEAL_INNER_NAME = "payload.kkz"   # 每层内部封装的固定成员名
_SEAL_SIDECAR_SUFFIX = ".kkseal.json"


def seal_sidecar_path(out_path: str | Path) -> Path:
    return Path(str(out_path) + _SEAL_SIDECAR_SUFFIX)


def _aes_zip_single(src_file: Path, out_zip: Path, password: str, arcname: str) -> None:
    """把单个文件以 AES-256 加密写入一个新 zip（一层封缄）。"""
    if not HAVE_PYZIPPER:
        raise RuntimeError("多重封缄需要 pyzipper，请先安装：pip install pyzipper")
    with pyzipper.AESZipFile(
        out_zip, "w", compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES
    ) as zf:
        zf.setpassword(password.encode("utf-8"))
        zf.write(src_file, arcname)


def pack_layered(
    folder: str | Path,
    out_path: str | Path,
    passwords: list[str],
    *,
    carrier: str | Path | None = None,
    progress: ProgressCb | None = None,
) -> str:
    """把文件夹多重封缄为 N 层加密文件（N=len(passwords)）。

    passwords[0] 是最内层（最先施加）、passwords[-1] 是最外层。
    给 carrier 则把最外层结果伪装追加到载体之后。
    旁写 <out>.kkseal.json 明文记录层数（不含密码）。返回最终输出路径。
    """
    folder = Path(folder)
    out_path = Path(out_path)
    if not passwords:
        raise ValueError("多重封缄至少需要一个密码")
    if not HAVE_PYZIPPER:
        raise RuntimeError("多重封缄需要 pyzipper，请先安装：pip install pyzipper")

    n = len(passwords)
    tmpdir = Path(tempfile.mkdtemp(prefix="kkseal_"))
    try:
        # 第 1 层：把文件夹打成加密 zip
        layer = tmpdir / "layer_1.kkz"
        pack_folder(folder, layer, password=passwords[0], progress=progress)
        if progress:
            progress(1, n, f"封缄第 1/{n} 层")
        # 第 2..N 层：把上一层 zip 当作唯一成员再加密
        for i in range(1, n):
            nxt = tmpdir / f"layer_{i + 1}.kkz"
            _aes_zip_single(layer, nxt, passwords[i], _SEAL_INNER_NAME)
            layer = nxt
            if progress:
                progress(i + 1, n, f"封缄第 {i + 1}/{n} 层")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        if carrier:
            disguise(carrier, layer, out_path)
        else:
            out_path.write_bytes(layer.read_bytes())
    finally:
        for f in tmpdir.glob("*"):
            try:
                f.unlink()
            except OSError:
                pass
        try:
            tmpdir.rmdir()
        except OSError:
            pass

    # 明文伴随：只记层数，绝不含密码
    seal_sidecar_path(out_path).write_text(
        json.dumps({"format": "kkseal", "version": 1, "layers": n}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(out_path)


def read_seal_layers(path: str | Path) -> int | None:
    """读取伴随文件里的封缄层数；没有伴随文件则返回 None（需用户自报层数）。"""
    sc = seal_sidecar_path(path)
    if not sc.is_file():
        return None
    try:
        data = json.loads(sc.read_text(encoding="utf-8"))
        n = int(data.get("layers", 0))
        return n if n > 0 else None
    except (json.JSONDecodeError, OSError, ValueError, TypeError):
        return None


def extract_layered(
    path: str | Path,
    out_dir: str | Path,
    passwords: list[str],
    *,
    layers: int | None = None,
    progress: ProgressCb | None = None,
) -> list[str]:
    """逐层解封多重封缄文件（也兼容伪装在载体之后的封缄包）。

    passwords 顺序须与封缄时一致（[最内, ..., 最外]）；本函数按相反顺序逐层剥离。
    layers 为空时优先读伴随文件，再回退为 len(passwords)。返回最终解出的文件列表。
    """
    path = Path(path)
    out_dir = Path(out_dir)
    n = layers or read_seal_layers(path) or len(passwords)
    if len(passwords) < n:
        raise ValueError(f"需要 {n} 个密码，仅提供了 {len(passwords)} 个")

    tmpdir = Path(tempfile.mkdtemp(prefix="kkunseal_"))
    try:
        current = path
        # 从最外层(passwords[n-1])往内剥到第 2 层
        for depth in range(n, 1, -1):
            pw = passwords[depth - 1]
            stage = tmpdir / f"unseal_{depth}"
            names = extract_archive(current, stage, passwords=[pw])
            inner = stage / _SEAL_INNER_NAME
            if not inner.is_file():
                # 兼容：取解出的第一个文件作为内层
                cand = [stage / x for x in names if (stage / x).is_file()]
                if not cand:
                    raise RuntimeError(f"第 {depth} 层解封后未找到内层封包")
                inner = cand[0]
            current = inner
            if progress:
                progress(n - depth + 1, n, f"解封第 {depth}/{n} 层")
        # 第 1 层：解到目标目录
        result = extract_archive(current, out_dir, passwords=[passwords[0]])
        if progress:
            progress(n, n, "解封第 1 层")
        return result
    finally:
        for f in sorted(tmpdir.rglob("*"), reverse=True):
            try:
                f.unlink() if f.is_file() else f.rmdir()
            except OSError:
                pass
        try:
            tmpdir.rmdir()
        except OSError:
            pass


# ---- 恢复校验记录（完整性 + 可选轻冗余） ----
#
# 诚实说明：这是“校验 + 轻冗余”，不是 WinRAR 那种 Reed-Solomon 奇偶纠错。
# 能可靠地“检测”文件是否损坏、定位是哪个内部文件坏了；冗余副本仅对
# zip 末尾的中央目录这类“小而关键、坏了就整包打不开”的段落做备份。

_RECOVERY_SUFFIX = ".kkrec.json"


def recovery_sidecar_path(path: str | Path) -> Path:
    return Path(str(path) + _RECOVERY_SUFFIX)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def write_recovery_sidecar(
    path: str | Path,
    *,
    redundancy: bool = False,
    progress: ProgressCb | None = None,
) -> str:
    """为文件生成恢复校验清单 <name>.kkrec.json。

    包含：整文件大小 + SHA256；若是 zip，则逐内部文件 SHA256（便于定位损坏）。
    redundancy=True 时额外保存文件末尾一小段（含 zip 中央目录）的十六进制副本，
    便于尾部损坏时人工修补。返回清单路径。
    """
    path = Path(path)
    rec: dict = {
        "format": "kkrec",
        "version": 1,
        "name": path.name,
        "size": path.stat().st_size,
        "sha256": _sha256_file(path),
        "members": [],
    }
    if looks_like_zip(path):
        try:
            with zipfile.ZipFile(path) as zf:
                infos = [n for n in zf.infolist() if not n.is_dir()]
                total = len(infos)
                for i, info in enumerate(infos, 1):
                    with zf.open(info) as f:
                        digest = _sha256_bytes(f.read())
                    rec["members"].append({"name": info.filename, "sha256": digest, "size": info.file_size})
                    if progress:
                        progress(i, total, info.filename)
        except (zipfile.BadZipFile, OSError):
            pass  # 非标准 zip 就只保留整文件校验

    if redundancy:
        tail = min(64 * 1024, rec["size"])  # 末尾 64KB，覆盖中央目录
        with open(path, "rb") as f:
            f.seek(-tail, 2)
            rec["tail_redundancy"] = {"bytes": tail, "hex": f.read().hex()}

    sc = recovery_sidecar_path(path)
    sc.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(sc)


def verify_recovery(
    path: str | Path,
    sidecar: str | Path | None = None,
    *,
    progress: ProgressCb | None = None,
) -> dict:
    """对照恢复清单校验文件完整性。

    返回 {ok, reason, bad_members, can_repair_tail}。ok=True 表示整文件 SHA256 匹配。
    """
    path = Path(path)
    sc = Path(sidecar) if sidecar else recovery_sidecar_path(path)
    if not sc.is_file():
        return {"ok": False, "reason": "缺少恢复清单文件", "bad_members": [], "can_repair_tail": False}
    try:
        rec = json.loads(sc.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {"ok": False, "reason": f"恢复清单损坏: {exc}", "bad_members": [], "can_repair_tail": False}

    if not path.is_file():
        return {"ok": False, "reason": "目标文件不存在", "bad_members": [], "can_repair_tail": False}

    actual = _sha256_file(path)
    can_repair = "tail_redundancy" in rec
    if actual == rec.get("sha256"):
        return {"ok": True, "reason": "整文件校验通过", "bad_members": [], "can_repair_tail": can_repair}

    # 整体不符：尽量定位是哪些内部文件坏了
    bad: list[str] = []
    if rec.get("members") and looks_like_zip(path):
        want = {m["name"]: m["sha256"] for m in rec["members"]}
        try:
            with zipfile.ZipFile(path) as zf:
                names = [n for n in zf.namelist() if not n.endswith("/")]
                total = len(names)
                for i, name in enumerate(names, 1):
                    if name in want:
                        try:
                            with zf.open(name) as f:
                                if _sha256_bytes(f.read()) != want[name]:
                                    bad.append(name)
                        except (zipfile.BadZipFile, OSError, zlib.error):
                            bad.append(name)  # 解压失败 = 该成员已损坏
                    if progress:
                        progress(i, total, name)
                missing = set(want) - set(names)
                bad.extend(sorted(missing))
        except (zipfile.BadZipFile, OSError):
            bad.append("(整个压缩包无法打开)")
    return {
        "ok": False,
        "reason": "整文件校验不通过，文件可能已损坏",
        "bad_members": bad,
        "can_repair_tail": can_repair,
    }
