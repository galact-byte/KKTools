"""分享包生成：把角色卡与其依赖的 mod 一起整理输出，方便分享给别人。"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

from core.kk_card import KoikatuCard, extract_mod_ids
from core.mod_index import ModIndex


def _card_name(path: Path) -> str:
    try:
        card = KoikatuCard.load(path)
        p = card.parameter or {}
        name = f"{p.get('lastname','')}{p.get('firstname','')}".strip() or p.get("nickname", "")
        return name or path.stem
    except Exception:  # noqa: BLE001
        return path.stem


def build_share_package(
    card_paths: list[str],
    index: ModIndex,
    out_dir: str | Path,
    *,
    group_by_char: bool = True,
    exclude_guids: set[str] | None = None,
    progress: Callable[[int, int, str], None] | None = None,
) -> dict:
    """为若干角色卡生成分享包。

    每张卡：复制卡片本身 + 从索引中复制其依赖且本地存在的 zipmod；记录缺失的 mod。
    group_by_char=True 时每张卡一个子目录，否则集中放到 cards/ 与 mods/。
    exclude_guids 给定时，这些 GUID（如某个大整合包里已有的 mod）不打进分享包，
    避免分享包塞入对方大概率已经有的 mod、徒增体积。
    返回汇总报告 dict。
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    exclude = exclude_guids or set()

    report = {"cards": [], "total_missing": set(), "copied_mods": set(), "excluded_mods": set()}
    total = len(card_paths)
    for i, cp in enumerate(card_paths, 1):
        cp = Path(cp)
        name = _card_name(cp)
        safe = "".join(c for c in name if c not in r'\/:*?"<>|').strip() or cp.stem

        if group_by_char:
            base = out_dir / safe
            card_dst_dir = base
            mods_dst_dir = base / "mods"
        else:
            card_dst_dir = out_dir / "cards"
            mods_dst_dir = out_dir / "mods"
        card_dst_dir.mkdir(parents=True, exist_ok=True)
        mods_dst_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy2(cp, card_dst_dir / cp.name)

        try:
            card = KoikatuCard.load(cp)
            required = extract_mod_ids(card)
        except Exception:  # noqa: BLE001
            required = {}

        present, missing, excluded = [], [], []
        for guid in required:
            if guid in exclude:
                excluded.append(guid)
                report["excluded_mods"].add(guid)
                continue
            entry = index.get(guid)
            if entry and entry.path and Path(entry.path).exists():
                dst = mods_dst_dir / Path(entry.path).name
                if not dst.exists():
                    shutil.copy2(entry.path, dst)
                present.append(guid)
                report["copied_mods"].add(guid)
            else:
                missing.append(guid)
        report["total_missing"].update(missing)
        report["cards"].append({
            "card": cp.name, "name": name,
            "required": len(required), "copied": len(present),
            "missing": missing, "excluded": len(excluded),
        })
        if progress:
            progress(i, total, name)

    # 写一份说明
    readme = out_dir / "README.txt"
    lines = ["KKTools 分享包", f"共 {len(card_paths)} 张角色卡"]
    if exclude:
        lines.append(f"（已排除参考清单中已有的 mod {len(report['excluded_mods'])} 种，未打入分享包）")
    lines.append("")
    for c in report["cards"]:
        extra = f" | 已排除 {c['excluded']}" if c.get("excluded") else ""
        lines.append(f"[{c['name']}] {c['card']}  依赖 {c['required']} | 已含 {c['copied']} | 缺失 {len(c['missing'])}{extra}")
        for m in c["missing"]:
            lines.append(f"    缺失: {m}")
    readme.write_text("\n".join(lines), encoding="utf-8")

    report["total_missing"] = sorted(report["total_missing"])
    report["copied_mods"] = sorted(report["copied_mods"])
    report["excluded_mods"] = sorted(report["excluded_mods"])
    return report


def restore_package(
    pkg_dir: str | Path,
    card_target: str | Path,
    mod_target: str | Path | None = None,
    *,
    progress: Callable[[int, int, str], None] | None = None,
) -> dict:
    """导入/恢复分享包：把包里的卡片复制到 card_target，zipmod 复制到 mod_target。

    兼容本程序生成的分享包（card/ + mods/ 结构），也兼容任意含 PNG/zipmod 的目录。
    已存在同名文件则跳过，不覆盖。
    """
    pkg = Path(pkg_dir)
    cards = [p for p in pkg.rglob("*.png") if p.is_file()]
    mods = [p for p in pkg.rglob("*.zipmod") if p.is_file()]
    Path(card_target).mkdir(parents=True, exist_ok=True)
    copied_cards = skipped_cards = copied_mods = skipped_mods = 0
    total = len(cards) + len(mods)
    done = 0
    for p in cards:
        dst = Path(card_target) / p.name
        if dst.exists():
            skipped_cards += 1
        else:
            shutil.copy2(p, dst); copied_cards += 1
        done += 1
        if progress and done % 20 == 0:
            progress(done, total, p.name)
    if mod_target:
        Path(mod_target).mkdir(parents=True, exist_ok=True)
        for p in mods:
            dst = Path(mod_target) / p.name
            if dst.exists():
                skipped_mods += 1
            else:
                shutil.copy2(p, dst); copied_mods += 1
            done += 1
            if progress and done % 20 == 0:
                progress(done, total, p.name)
    return {
        "cards": copied_cards, "cards_skipped": skipped_cards,
        "mods": copied_mods, "mods_skipped": skipped_mods,
    }


def organize_cards(
    card_dir: str | Path,
    out_dir: str | Path,
    *,
    by: str = "type",
    move: bool = False,
    progress: Callable[[int, int, str], None] | None = None,
) -> dict:
    """整理卡片：按类型(type)或角色名(character)归类复制/移动到 out_dir/<分组>/。"""
    from core.card_scan import TYPE_LABELS
    from core.kk_card import read_card_light

    src = Path(card_dir)
    out = Path(out_dir)
    files = [p for p in src.rglob("*.png") if p.is_file()]
    total = len(files)
    done = organized = 0
    for p in files:
        done += 1
        try:
            info = read_card_light(p)
        except OSError:
            continue
        if by == "character":
            group = (info.name or "未命名").strip()
        else:
            group = TYPE_LABELS.get(info.type, "其它")
        group = "".join(c for c in group if c not in r'\/:*?"<>|').strip() or "未分类"
        dst_dir = out / group
        dst = dst_dir / p.name
        try:
            if dst.exists() or src.resolve() == out.resolve():
                pass
            else:
                dst_dir.mkdir(parents=True, exist_ok=True)
                if move:
                    shutil.move(str(p), str(dst))
                else:
                    shutil.copy2(p, dst)
                organized += 1
        except OSError:
            pass
        if progress and (done % 30 == 0 or done == total):
            progress(done, total, p.name)
    return {"processed": done, "organized": organized, "by": by, "move": move}


def reconcile_dirs(dir_a: str | Path, dir_b: str | Path) -> dict:
    """离线对账：比对两个目录的文件（按文件名），列出只在A/只在B/共有。"""
    a = {p.name for p in Path(dir_a).rglob("*") if p.is_file()}
    b = {p.name for p in Path(dir_b).rglob("*") if p.is_file()}
    return {
        "only_a": sorted(a - b),
        "only_b": sorted(b - a),
        "both": len(a & b),
        "count_a": len(a), "count_b": len(b),
    }
