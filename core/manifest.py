"""带身份戳的 Mod 清单：导出本机拥有的 mod GUID，跨机对账互助。

相比单纯的 GUID 文本清单（mod_index.export_guid_list），清单额外携带“是谁、哪份库、
何时导出”的身份信息，对方导入后能稳定归属，也便于多份清单混在一起时区分来源。
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

from core.mod_index import ModIndex

_FORMAT = "kkmanifest"
_VERSION = 1


def build_manifest(index: ModIndex, identity: dict, *, include_names: bool = False) -> dict:
    """从索引构建清单 dict。include_names=True 时附带 guid->名称（体积更大，便于人读）。"""
    guids = sorted(index.entries)
    data: dict = {
        "format": _FORMAT,
        "version": _VERSION,
        "identity": {
            "holder_id": identity.get("holder_id", ""),
            "library_id": identity.get("library_id", ""),
            "display_name": identity.get("display_name", ""),
        },
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "count": len(guids),
        "guids": guids,
    }
    if include_names:
        data["names"] = {g: index.entries[g].name for g in guids if index.entries[g].name}
    return data


def export_manifest(index: ModIndex, out_path: str | Path, identity: dict,
                    *, include_names: bool = False) -> int:
    """导出清单到 JSON 文件，返回 mod 条数。"""
    data = build_manifest(index, identity, include_names=include_names)
    Path(out_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data["count"]


def load_manifest(path: str | Path) -> dict:
    """加载清单文件。兼容两种来源：本格式 JSON；或退而求其次的纯 GUID 文本清单。"""
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")
    try:
        data = json.loads(text)
        if isinstance(data, dict) and data.get("format") == _FORMAT:
            data.setdefault("guids", [])
            data.setdefault("identity", {})
            return data
    except json.JSONDecodeError:
        pass
    # 回退：把它当作每行一个 guid 的纯文本清单（兼容 export_guid_list/缺失清单）
    from core.mod_index import parse_guid_list
    guids = parse_guid_list(p)
    return {"format": _FORMAT, "version": _VERSION, "identity": {}, "guids": guids,
            "count": len(guids), "generated": ""}


def reconcile_manifests(mine: dict, theirs: dict) -> dict:
    """对账两份清单。

    返回：
      - mine_only: 我有、对方没有的 guid（我可补给对方）
      - theirs_only: 对方有、我没有的 guid（可向对方索取）
      - both: 双方都有的数量
      - theirs_identity: 对方身份信息
    """
    a = set(mine.get("guids", []))
    b = set(theirs.get("guids", []))
    return {
        "mine_only": sorted(a - b),
        "theirs_only": sorted(b - a),
        "both": len(a & b),
        "mine_count": len(a),
        "theirs_count": len(b),
        "theirs_identity": theirs.get("identity", {}),
        "mine_identity": mine.get("identity", {}),
    }
