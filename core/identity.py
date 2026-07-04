"""本机库身份：给这台机器的 Mod 库分配稳定标识，用于跨机清单对账。

holder_id：持有人标识（一个人可能换机器）。
library_id：库标识（这台机器的这份 mod 库）。
display_name：展示名，默认取系统用户名，可在设置里改。

首次访问时用 uuid 生成并写入 config.json，之后保持不变——这样别人拿到你导出的清单，
能稳定地把它归属到“你的库”，而不是靠文件名猜。
"""

from __future__ import annotations

import os
import uuid

from core import settings


def _default_display_name() -> str:
    return os.environ.get("USERNAME") or os.environ.get("USER") or "用户"


def get_identity() -> dict:
    """读取本机身份；缺失字段自动补全并持久化。返回 {holder_id, library_id, display_name}。"""
    cfg = settings.load()
    ident = dict(cfg.get("identity") or {})
    changed = False
    if not ident.get("holder_id"):
        ident["holder_id"] = "hld_" + uuid.uuid4().hex[:16]
        changed = True
    if not ident.get("library_id"):
        ident["library_id"] = "lib_" + uuid.uuid4().hex[:16]
        changed = True
    if not ident.get("display_name"):
        ident["display_name"] = _default_display_name()
        changed = True
    if changed:
        settings.set_value("identity", ident)
    return ident


def set_display_name(name: str) -> dict:
    """更新展示名（空值忽略），返回更新后的身份。"""
    ident = get_identity()
    name = (name or "").strip()
    if name:
        ident["display_name"] = name
        settings.set_value("identity", ident)
    return ident
