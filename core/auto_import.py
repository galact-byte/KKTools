"""分享包自动归位，先提供只读计划，再复制到用户选定的游戏。"""
from __future__ import annotations

import shutil
from pathlib import Path

from core import kk_card, settings, stego


def _plan_target(folder: Path, name: str, digest: str, reserved: dict[Path, str]) -> tuple[Path, bool]:
    preferred = folder / name
    matches = [preferred] + sorted(folder.glob(f'{preferred.stem} (*){preferred.suffix}'))
    matches += [p for p in reserved if p.parent == folder
                and (p.name == name or (p.stem.startswith(preferred.stem + ' (') and p.suffix == preferred.suffix))]
    for existing in matches:
        if reserved.get(existing) == digest:
            return existing, True
        if existing.is_file() and not existing.is_symlink() and stego._sha256_file(existing) == digest:
            return existing, True
    target, n = preferred, 2
    while target.exists() or target.is_symlink() or target in reserved:
        target = folder / f'{preferred.stem} ({n}){preferred.suffix}'
        n += 1
    reserved[target] = digest
    return target, False


def plan_import(pkg_dir: str, fallback_game: str = '') -> dict:
    pkg = Path(pkg_dir)
    if not pkg_dir.strip() or not pkg.is_dir():
        raise ValueError('请选择有效的分享包目录')
    if fallback_game not in ('', 'KK', 'KKS'):
        raise ValueError('游戏版本无效')
    pkg = pkg.resolve()
    cfg = settings.load()
    files, skipped = [], []
    reserved: dict[Path, str] = {}
    for source in sorted(pkg.rglob('*')):
        if not source.is_file() or source.suffix.lower() not in ('.png', '.zipmod'):
            continue
        game, kind, subdir = '', '', ''
        try:
            if source.is_symlink():
                raise ValueError('跳过链接文件')
            if source.suffix.lower() == '.zipmod':
                game, kind, subdir = fallback_game, 'mod', 'mods'
            else:
                info = kk_card.read_card_light(source)
                kind, game = info.type, info.game
                if kind == 'character':
                    card = kk_card.KoikatuCard.load(source)
                    sex = (card.parameter or {}).get('sex')
                    if sex not in (0, 1):
                        raise ValueError('角色性别无法确认')
                    game = card.game
                    subdir = 'UserData/chara/' + ('female' if sex == 1 else 'male')
                elif kind == 'coordinate':
                    subdir = 'UserData/coordinate'
                elif kind == 'scene':
                    # 场景没有可靠的版本字段，由用户指定归属。
                    game, subdir = fallback_game, 'UserData/studio/scene'
                else:
                    raise ValueError('普通图片或无法识别的卡片')
            if game not in ('KK', 'KKS'):
                raise ValueError('请指定场景和 Mod 的目标游戏版本')
            root_text = str(cfg.get('kk_game_dir' if game == 'KK' else 'kks_game_dir') or '').strip()
            if not root_text or not Path(root_text).is_dir():
                raise ValueError(f'尚未配置有效的 {game} 游戏目录')
            root = Path(root_text).resolve()
            folder = root / subdir
            if not folder.resolve().is_relative_to(root):
                raise ValueError('目标目录链接指向游戏目录之外')
            if folder.resolve().is_relative_to(pkg.resolve()):
                raise ValueError('输出目录位于分享包内部，请另选分享包目录')
            digest = stego._sha256_file(source)
            target, duplicate = _plan_target(folder.resolve(), source.name, digest, reserved)
            files.append({'source': str(source), 'target': str(target), 'game': game, 'type': kind,
                          'sha256': digest, 'duplicate': duplicate})
        except (ValueError, OSError, kk_card.KKCardError) as exc:
            skipped.append({'source': str(source), 'reason': str(exc)})
    return {'pkgDir': str(pkg), 'fallbackGame': fallback_game, 'files': files, 'skipped': skipped}


def validate_plan(plan: dict) -> None:
    """写盘前重新比对，只执行用户已经预览且仍然有效的计划。"""
    try:
        current = plan_import(plan['pkgDir'], plan['fallbackGame'])
    except (ValueError, OSError) as exc:
        raise ValueError('归位来源或目标已变化，请重新预览后确认') from exc
    if current != plan:
        raise ValueError('归位来源、目标或文件内容已变化，请重新预览后确认')


def apply_import(plan: dict, progress=None) -> dict:
    validate_plan(plan)
    copied, duplicates, errors, outputs = 0, 0, [], []
    files = plan['files']
    for i, item in enumerate(files, 1):
        source, target = Path(item['source']), Path(item['target'])
        try:
            if item['duplicate']:
                if stego._sha256_file(target) != item['sha256']:
                    raise ValueError('重复文件已变化，请重新预览')
                duplicates += 1
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                created = False
                try:
                    with target.open('xb') as dst:
                        created = True
                        with source.open('rb') as src:
                            shutil.copyfileobj(src, dst)
                    if stego._sha256_file(target) != item['sha256']:
                        raise ValueError('源文件在复制时发生变化，请重新预览')
                except Exception:
                    if created:
                        target.unlink(missing_ok=True)
                    raise
                copied += 1
                outputs.append(str(target))
        except (OSError, ValueError) as exc:
            errors.append({'source': str(source), 'reason': str(exc)})
        if progress:
            progress(i, len(files), f'归位 {i}/{len(files)}：{source.name}')
    return {'copied': copied, 'duplicates': duplicates, 'skipped': plan['skipped'], 'errors': errors, 'outputs': outputs}
