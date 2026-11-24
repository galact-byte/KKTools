"""后端缺陷回归：独立文件副本，不依赖前端或真实游戏目录。"""
import base64
import json
import random
import tempfile
import zipfile
from pathlib import Path

import msgpack
import pytest

from core import auto_import, settings, stego
from core.kk_card import KoikatuCard, png_data_length
from test_kk_card import _build_synthetic_card, _make_png
from test_workflow_extensions import card_at, finish
from web_bridge import KKToolsBridge


@pytest.fixture
def bridge(tmp_path, monkeypatch):
    scratch = tmp_path / 'internal-temp'
    scratch.mkdir()
    monkeypatch.setattr(tempfile, 'tempdir', str(scratch))
    monkeypatch.setattr(settings, '_CONFIG_PATH', tmp_path / 'config.json')
    monkeypatch.setattr(settings, 'app_dir', lambda: tmp_path)
    return KKToolsBridge()


def import_source(tmp_path):
    pkg, game = tmp_path / 'pkg', tmp_path / 'game'
    pkg.mkdir(); game.mkdir()
    settings.save({'kk_game_dir': str(game)})
    card_at(pkg / 'card.png')
    return pkg, game


def assert_rejected(bridge, response):
    if response['ok']:
        state = finish(bridge, response)
        assert state['status'] == 'error', state
        assert '预览' in state['error']
    else:
        assert '预览' in response['error']


@pytest.mark.parametrize('part', ['001', '002', '1000'])
def test_pack_preserves_orphaned_volume_recovery(bridge, tmp_path, part):
    source = tmp_path / 'data.bin'
    source.write_bytes(random.Random(1).randbytes(2 * 1024 * 1024))
    out = tmp_path / 'out'; out.mkdir()
    old = out / f'data.zip.{part}'
    old.write_bytes(b'old-volume')
    record = Path(stego.write_recovery_sidecar(old, redundancy=True))
    original = record.read_bytes()
    old.unlink()
    done = finish(bridge, bridge.start_pack({'sources': [str(source)], 'outDir': str(out),
        'independent': True, 'splitMB': 1, 'writeRecovery': True}))
    assert done['status'] == 'done', done
    assert record.read_bytes() == original
    outputs = done['result']['jobs'][0]['outputs']
    assert Path(outputs[0]).name == 'data (2).zip.001'
    assert all(stego.verify_recovery(p)['ok'] for p in outputs)


@pytest.mark.parametrize('metadata', [True, False])
@pytest.mark.parametrize('disguise', [False, True])
def test_layered_volumes_restore_original_bytes(bridge, tmp_path, metadata, disguise):
    source = tmp_path / 'secret.bin'
    source.write_bytes(random.Random(2).randbytes(2 * 1024 * 1024))
    carrier = tmp_path / 'carrier.png'
    carrier.write_bytes(_make_png((0, 0, 0), (3, 3)))
    packed = finish(bridge, bridge.start_pack({'sources': [str(source)], 'outDir': str(tmp_path/'out'),
        'independent': True, 'passwords': ['inner', 'outer'], 'splitMB': 1,
        'stegoMode': 'image' if disguise else 'none', 'carrierPath': str(carrier)}))
    assert packed['status'] == 'done', packed
    first = Path(packed['result']['outputs'][0])
    assert len(packed['result']['outputs']) >= 2
    # 只保留分卷和可选的层数记录，不能靠未分卷的原包解压。
    original = first.with_suffix('')
    original.unlink()
    if not metadata:
        stego.seal_sidecar_path(original).unlink()
    done = finish(bridge, bridge.start_unpack({'inputPath': str(first),
        'outDir': str(tmp_path/'unpack'), 'passwords': ['inner', 'outer']}))
    assert done['status'] == 'done', done
    assert (tmp_path/'unpack/secret.bin').is_file(), done
    assert (tmp_path/'unpack/secret.bin').read_bytes() == source.read_bytes()
    assert not (tmp_path/'unpack/payload.kkz').exists()
    assert list((tmp_path/'internal-temp').iterdir()) == []


@pytest.mark.parametrize('metadata', [True, False])
@pytest.mark.parametrize('passwords', [['inner', 'wrong'], ['outer']])
def test_layered_volumes_fail_without_complete_passwords(bridge, tmp_path, metadata, passwords):
    source = tmp_path/'secret.txt'; source.write_bytes(b'secret')
    packed = finish(bridge, bridge.start_pack({'sources': [str(source)],
        'outDir': str(tmp_path/'out'), 'passwords': ['inner', 'outer'], 'splitMB': .0001}))
    assert packed['status'] == 'done', packed
    first = Path(packed['result']['outputs'][0])
    if not metadata:
        stego.seal_sidecar_path(first.with_suffix('')).unlink()
    done = finish(bridge, bridge.start_unpack({'inputPath': str(first),
        'outDir': str(tmp_path/'unpack'), 'passwords': passwords}))
    assert done['status'] == 'error', done
    assert not list((tmp_path/'unpack').rglob('*'))
    assert list((tmp_path/'internal-temp').iterdir()) == []


@pytest.mark.parametrize('filename', ['secret.txt', 'payload.kkz'])
def test_single_layer_still_tries_password_candidates(bridge, tmp_path, filename):
    source = tmp_path / filename; source.write_bytes(b'secret')
    packed = finish(bridge, bridge.start_pack({'sources': [str(source)],
        'outDir': str(tmp_path/'out'), 'passwords': ['correct'], 'splitMB': .0001}))
    done = finish(bridge, bridge.start_unpack({'inputPath': packed['result']['outputs'][0],
        'outDir': str(tmp_path/'unpack'), 'passwords': ['wrong', 'correct']}))
    assert done['status'] == 'done', done
    assert (tmp_path/'unpack'/filename).read_bytes() == b'secret'


@pytest.mark.parametrize('mode', ['plain', 'disguise', 'layered'])
def test_batch_excludes_output_subtree_including_old_packages(bridge, tmp_path, mode):
    a, b = tmp_path/'a', tmp_path/'b'; a.mkdir(); b.mkdir()
    (a/'first.txt').write_bytes(b'first'); (b/'second.txt').write_bytes(b'second')
    nested = b/'sub'; nested.mkdir(); (nested/'keep.txt').write_bytes(b'keep')
    out = b/'output'; out.mkdir(); (out/'old.zip').write_bytes(b'old-package')
    carrier = tmp_path/'carrier.png'; carrier.write_bytes(_make_png((0, 0, 0), (3, 3)))
    done = finish(bridge, bridge.start_pack({'sources': [str(a), str(b)], 'outDir': str(out),
        'independent': True, 'stegoMode': 'image' if mode == 'disguise' else 'none',
        'carrierPath': str(carrier), 'passwords': ['inner', 'outer'] if mode == 'layered' else []}))
    assert done['status'] == 'done', done
    assert all(j['ok'] for j in done['result']['jobs']), done
    b_pack = done['result']['jobs'][1]['outputs'][0]
    if mode == 'layered':
        stego.extract_layered(b_pack, tmp_path/'unpack', ['inner', 'outer'])
        contents = sorted(p.relative_to(tmp_path/'unpack').as_posix() for p in (tmp_path/'unpack').rglob('*') if p.is_file())
    else:
        with zipfile.ZipFile(b_pack) as z:
            contents = sorted(z.namelist())
    assert contents == ['second.txt', 'sub/keep.txt']
    assert (out/'old.zip').read_bytes() == b'old-package'


def test_import_preview_reserves_conflicts_without_writing(bridge, tmp_path):
    pkg, game = import_source(tmp_path)
    dest = game/'UserData/chara/female'; dest.mkdir(parents=True)
    existing = dest/'card.png'; existing.write_bytes(b'original')
    nested = pkg/'nested'; nested.mkdir()
    second = card_at(nested/'card.png'); parsed = KoikatuCard.load(second)
    parsed.update_parameter({'firstname': 'Different'}); parsed.save(second, backup=False)
    before = sorted(str(p) for p in game.rglob('*'))
    plan = bridge.preview_auto_import(str(pkg))['data']
    assert sorted(str(p) for p in game.rglob('*')) == before
    assert [Path(x['target']).name for x in plan['files']] == ['card (2).png', 'card (3).png']
    done = finish(bridge, bridge.start_auto_import(str(pkg)))
    assert done['status'] == 'done', done
    assert done['result']['outputs'] == [x['target'] for x in plan['files']]
    assert existing.read_bytes() == b'original'


@pytest.mark.parametrize('change', ['new', 'deleted', 'content', 'config', 'target'])
def test_import_rejects_stale_preview_before_any_copy(bridge, tmp_path, change):
    pkg, game = import_source(tmp_path)
    assert bridge.preview_auto_import(str(pkg))['ok']
    if change == 'new':
        card_at(pkg/'unpreviewed.png')
    elif change == 'deleted':
        (pkg/'card.png').unlink()
    elif change == 'content':
        parsed = KoikatuCard.load(pkg/'card.png')
        parsed.update_parameter({'firstname': 'Changed'})
        parsed.save(pkg/'card.png', backup=False)
    elif change == 'config':
        other = tmp_path/'other-game'; other.mkdir()
        settings.save({'kk_game_dir': str(other)})
    else:
        dest = game/'UserData/chara/female'; dest.mkdir(parents=True)
        (dest/'card.png').write_bytes(b'existing')
    assert_rejected(bridge, bridge.start_auto_import(str(pkg)))
    if change == 'target':
        assert (game/'UserData/chara/female/card.png').read_bytes() == b'existing'
    else:
        assert not list(game.rglob('*.png'))
    assert not list((tmp_path/'other-game').rglob('*.png'))


def test_import_requires_preview_and_refresh_after_completion(bridge, tmp_path):
    pkg, game = import_source(tmp_path)
    assert_rejected(bridge, bridge.start_auto_import(str(pkg)))
    assert not list(game.iterdir())
    assert bridge.preview_auto_import(str(pkg))['ok']
    done = finish(bridge, bridge.start_auto_import(str(pkg)))
    assert done['status'] == 'done', done
    assert_rejected(bridge, bridge.start_auto_import(str(pkg)))
    plan = bridge.preview_auto_import(str(pkg))['data']
    assert Path(plan['files'][0]['target']).name == 'card.png'
    done = finish(bridge, bridge.start_auto_import(str(pkg)))
    assert done['result']['duplicates'] == 1 and done['result']['copied'] == 0


def test_core_import_revalidates_queued_plan(bridge, tmp_path):
    pkg, game = import_source(tmp_path)
    plan = auto_import.plan_import(str(pkg))
    card_at(pkg/'unpreviewed.png')
    with pytest.raises(ValueError, match='预览'):
        auto_import.apply_import(plan)
    assert not list(game.iterdir())


@pytest.mark.parametrize('damage', ['character', 'scene-mods', 'character-mods', 'block-bounds'])
@pytest.mark.parametrize('fmt', ['json', 'txt'])
def test_scene_export_rejects_incomplete_analysis_without_output(bridge, tmp_path, damage, fmt):
    raw, _ = _build_synthetic_card()
    card = KoikatuCard.from_bytes(raw)
    if damage == 'character':
        embedded = raw[len(card.thumbnail):-50]
    elif damage == 'scene-mods':
        embedded = b'com.bepis.sideloader.universalautoresolver\xc1'
    elif damage == 'character-mods':
        card.blocks['KKEx'] = b'\xc1'
        from core.kk_card import BlockInfo
        card.block_order.append(BlockInfo('KKEx', '0.0.0', 0, 1))
        card._dirty = True
        changed = card.to_bytes(); embedded = changed[png_data_length(changed):]
    else:
        index = msgpack.unpackb(card._lstinfo_raw, raw=False)
        index['lstInfo'][0]['size'] = len(card._data_blob) + 100
        invalid = msgpack.packb(index)
        import struct
        original_index = struct.pack('<i', len(card._lstinfo_raw)) + card._lstinfo_raw
        changed = raw.replace(original_index, struct.pack('<i', len(invalid)) + invalid)
        embedded = changed[len(card.thumbnail):]
    scene = tmp_path/'scene.png'
    scene.write_bytes(card.thumbnail + b'KStudio' + embedded)
    original = scene.read_bytes()
    done = finish(bridge, bridge.start_export_data({'kind': 'scene', 'paths': [str(scene)],
        'outDir': str(tmp_path/'export'), 'format': fmt}))
    assert done['status'] == 'error', done
    assert not (tmp_path/'export').exists() or not list((tmp_path/'export').iterdir())
    assert scene.read_bytes() == original


@pytest.mark.parametrize('trailing', [msgpack.packb({'part': 'second'}), b'\xc1', b'\x81'])
def test_character_export_preserves_all_bytes_when_block_is_not_single_object(bridge, tmp_path, trailing):
    raw, _ = _build_synthetic_card()
    card = KoikatuCard.from_bytes(raw)
    block = msgpack.packb({'part': 'first'}) + trailing
    card.blocks['Custom'] = block; card._dirty = True
    source = tmp_path/'card.png'; card.save(source, backup=False)
    original = source.read_bytes()
    done = finish(bridge, bridge.start_export_data({'kind': 'character', 'paths': [str(source)],
        'outDir': str(tmp_path/'export'), 'format': 'json'}))
    assert done['status'] == 'done', done
    doc = json.loads(Path(done['result']['path']).read_text(encoding='utf-8'))
    exported = doc['blocks']['Custom']
    assert exported.get('encoding') == 'base64', exported
    assert base64.b64decode(exported['data']) == block
    assert doc['parameter']['firstname'] == 'Ishtar'
    assert source.read_bytes() == original


def test_import_failed_source_open_removes_new_partial_target(bridge, tmp_path, monkeypatch):
    pkg, _ = import_source(tmp_path)
    plan = auto_import.plan_import(str(pkg))
    source = pkg/'card.png'
    target = Path(plan['files'][0]['target'])
    original_open = Path.open

    def racing_open(path, mode='r', *args, **kwargs):
        if path == source and mode == 'rb' and target.exists():
            raise FileNotFoundError('Source disappeared after validation')
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, 'open', racing_open)
    result = auto_import.apply_import(plan)
    assert result['copied'] == 0 and len(result['errors']) == 1
    assert not target.exists()


def test_import_late_target_conflict_never_renames_or_overwrites(bridge, tmp_path):
    pkg, _ = import_source(tmp_path)
    card_at(pkg/'second.png')
    plan = auto_import.plan_import(str(pkg))
    second = Path(plan['files'][1]['target'])

    def late_conflict(current, total, message):
        if current == 1:
            second.write_bytes(b'created-after-validation')

    result = auto_import.apply_import(plan, late_conflict)
    assert result['copied'] == 1 and len(result['errors']) == 1
    assert result['outputs'] == [plan['files'][0]['target']]
    assert second.read_bytes() == b'created-after-validation'
    assert not second.with_name('second (2).png').exists()


def test_import_change_during_copy_never_delivers_changed_source(bridge, tmp_path):
    pkg, _ = import_source(tmp_path)
    card_at(pkg/'second.png')
    plan = auto_import.plan_import(str(pkg))

    def change_after_first(current, total, message):
        if current == 1:
            (pkg/'second.png').write_bytes(b'changed-after-validation')

    result = auto_import.apply_import(plan, change_after_first)
    assert result['copied'] == 1 and len(result['errors']) == 1
    assert not Path(plan['files'][1]['target']).exists()
