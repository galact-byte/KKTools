"""恢复记录辅助操作：只在新副本上修复，哈希不一致不交付。"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from core import stego
from core.catalog import unique_path


def repair_tail(path: Path, sidecar: Path, out_dir: Path) -> Path:
    if not path.is_file() or not sidecar.is_file():
        raise ValueError('请选择待修复文件及其恢复记录')
    if sidecar.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('恢复记录过大')
    rec = json.loads(sidecar.read_text(encoding='utf-8'))
    if not isinstance(rec, dict) or rec.get('format') != 'kkrec' or rec.get('version') != 1:
        raise ValueError('恢复记录格式不支持')
    size, digest, tail = rec.get('size'), rec.get('sha256'), rec.get('tail_redundancy')
    if type(size) is not int or size <= 0 or not isinstance(digest, str) or len(digest) != 64:
        raise ValueError('恢复记录的文件信息无效')
    if not isinstance(tail, dict) or type(tail.get('bytes')) is not int:
        raise ValueError('该恢复记录只有校验信息，没有尾部备份，无法修复')
    count, text = tail['bytes'], tail.get('hex')
    if not 0 < count <= min(size, 65536) or not isinstance(text, str) or len(text) != count * 2:
        raise ValueError('尾部备份无效')
    backup = bytes.fromhex(text)
    if path.stat().st_size < size - count:
        raise ValueError('截断超出尾部备份范围，无法修复')
    target = unique_path(out_dir, f'{path.stem}_repaired{path.suffix}')
    created = False
    try:
        with target.open('xb') as output, path.open('rb') as source:
            created = True
            shutil.copyfileobj(source, output)
            output.seek(size-count)
            output.write(backup)
            output.truncate(size)
        if stego._sha256_file(target) != digest:
            raise ValueError('修复后整文件校验仍不一致：损坏超出尾部备份范围，或恢复记录不匹配')
        return target
    except Exception:
        if created:
            target.unlink(missing_ok=True)
        raise
