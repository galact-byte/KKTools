"""扩展工作流的真实文件回归；所有输入输出均为测试副本。"""
import csv
import io
import json
import struct
import time
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from core import settings, stego
from core.kk_card import KoikatuCard, write_cs_string
from test_kk_card import _build_synthetic_card
from web_bridge import KKToolsBridge


@pytest.fixture
def bridge(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, '_CONFIG_PATH', tmp_path / 'config.json')
    monkeypatch.setattr(settings, 'app_dir', lambda: tmp_path)
    return KKToolsBridge()


def finish(bridge, response):
    assert response['ok'], response
    for _ in range(1000):
        state = bridge.poll_task(response['data']['taskId'])['data']
        if state['status'] != 'running':
            return state
        time.sleep(.01)
    pytest.fail('任务超时')


def card_at(path, game='KK', sex=1):
    raw, _ = _build_synthetic_card()
    card = KoikatuCard.from_bytes(raw)
    if game == 'KKS':
        card.marker = '【KoiKatuCharaSun】'
    card.update_parameter({'sex': sex})
    card.save(path, backup=False)
    return path


def test_batch_packs_each_source_and_keeps_existing_outputs(bridge, tmp_path):
    a, b = tmp_path / 'a', tmp_path / 'b'
    a.mkdir(); b.mkdir()
    (a / 'same.txt').write_text('first')
    (b / 'same.txt').write_text('second')
    out = tmp_path / 'out'; out.mkdir()
    (out / 'same.zip').write_bytes(b'original')
    result = finish(bridge, bridge.start_pack({'sources': [str(a/'same.txt'), str(b/'same.txt')],
        'outDir': str(out), 'independent': True, 'writeRecovery': True}))
    assert result['status'] == 'done', result
    jobs = result['result']['jobs']
    assert len(jobs) == 2 and all(j['ok'] for j in jobs)
    assert (out / 'same.zip').read_bytes() == b'original'
    contents = []
    for job in jobs:
        with zipfile.ZipFile(job['outputs'][0]) as z:
            contents.append(z.read('same.txt'))
        assert stego.verify_recovery(job['outputs'][0])['ok']
    assert contents == [b'first', b'second']


def test_batch_failure_does_not_discard_other_results(bridge, tmp_path):
    source = tmp_path / 'ok.txt'; source.write_text('ok')
    result = finish(bridge, bridge.start_pack({'sources': [str(tmp_path/'missing'), str(source)],
        'outDir': str(tmp_path/'out'), 'independent': True}))
    assert result['status'] == 'done', result
    jobs = result['result']['jobs']
    assert [j['ok'] for j in jobs] == [False, True]
    assert 'error' in jobs[0]


def test_auto_import_previews_and_routes_versions_without_overwrite(bridge, tmp_path):
    pkg = tmp_path / 'pkg'; pkg.mkdir()
    kk = tmp_path / 'KK'; kk.mkdir()
    kks = tmp_path / 'KKS'; kks.mkdir()
    settings.save({'kk_game_dir': str(kk), 'kks_game_dir': str(kks)})
    first = card_at(pkg/'female.png')
    card_at(pkg/'male.png', 'KKS', 0)
    Image.new('RGB', (3,3)).save(pkg/'ordinary.png')
    (pkg/'test.zipmod').write_bytes(b'mod')
    target = kk/'UserData/chara/female'; target.mkdir(parents=True)
    (target/'female.png').write_bytes(b'existing')
    before = sorted(str(p) for p in kk.rglob('*'))
    preview = bridge.preview_auto_import(str(pkg), 'KKS')
    assert preview['ok'], preview
    assert len(preview['data']['files']) == 3
    assert len(preview['data']['skipped']) == 1
    assert sorted(str(p) for p in kk.rglob('*')) == before
    result = finish(bridge, bridge.start_auto_import(str(pkg), 'KKS'))
    assert result['status'] == 'done', result
    assert (target/'female.png').read_bytes() == b'existing'
    assert (target/'female (2).png').read_bytes() == first.read_bytes()
    assert (kks/'UserData/chara/male/male.png').is_file()
    assert (kks/'mods/test.zipmod').read_bytes() == b'mod'
    assert bridge.preview_auto_import(str(pkg), 'KKS')['ok']
    again = finish(bridge, bridge.start_auto_import(str(pkg), 'KKS'))
    assert again['result']['copied'] == 0
    assert again['result']['duplicates'] == 3


def test_auto_import_unknown_scene_and_mod_are_not_guessed(bridge, tmp_path):
    pkg = tmp_path/'pkg'; pkg.mkdir()
    game = tmp_path/'game'; game.mkdir()
    settings.save({'kk_game_dir': str(game)})
    Image.new('RGB',(2,2)).save(pkg/'scene.png')
    with (pkg/'scene.png').open('ab') as f: f.write(b'KStudio')
    (pkg/'x.zipmod').write_bytes(b'mod')
    preview = bridge.preview_auto_import(str(pkg), '')
    assert preview['ok'], preview
    assert preview['data']['files'] == []
    assert len(preview['data']['skipped']) == 2
    preview = bridge.preview_auto_import(str(pkg), 'KK')['data']
    assert len(preview['files']) == 2
    assert any(Path(x['target']) == game/'UserData/studio/scene/scene.png' for x in preview['files'])


def test_auto_import_missing_game_never_uses_other_version(bridge, tmp_path):
    pkg = tmp_path/'pkg'; pkg.mkdir()
    card_at(pkg/'kks.png','KKS')
    game = tmp_path/'KK'; game.mkdir()
    settings.save({'kk_game_dir': str(game)})
    preview = bridge.preview_auto_import(str(pkg), 'KK')['data']
    assert preview['files'] == []
    assert 'KKS' in preview['skipped'][0]['reason']
    assert list(game.iterdir()) == []


def test_tags_persist_in_scan_and_do_not_change_card(bridge, tmp_path):
    card = card_at(tmp_path/'card.png'); original = card.read_bytes()
    result = bridge.set_card_tags(str(card), ['收藏', '待补 Mod', '收藏', ' '])
    assert result['ok'], result
    assert result['data'] == ['收藏', '待补 Mod']
    scanned = KKToolsBridge().scan_directory(str(tmp_path))['data']
    assert scanned[0]['tags'] == ['收藏', '待补 Mod']
    assert card.read_bytes() == original
    saved = bridge.save_card({'path': str(card), 'parameter': {'firstname':'Edited'}})
    assert saved['ok'], saved
    assert bridge.get_card_tags(saved['data']['savedPath'])['data'] == ['收藏', '待补 Mod']
    assert bridge.set_card_tags(str(card), [])['ok']
    assert bridge.get_card_tags(str(card))['data'] == []


def test_csv_export_matches_selection_and_escapes_spreadsheet_formulas(bridge, tmp_path):
    card = card_at(tmp_path/'card.png')
    parsed = KoikatuCard.load(card)
    parsed.update_parameter({'firstname':'=1+1'})
    parsed.save(card,backup=False)
    bridge.set_card_tags(str(card), ['收藏'])
    result = finish(bridge, bridge.start_export_data({'kind':'list', 'paths':[str(card)],
        'outDir':str(tmp_path/'out'), 'format':'csv'}))
    assert result['status'] == 'done',result
    data = Path(result['result']['path']).read_text(encoding='utf-8-sig')
    rows = list(csv.DictReader(io.StringIO(data)))
    assert len(rows) == 1
    assert rows[0]['名称'] == "'=1+1"
    assert rows[0]['标签'] == '收藏'
    assert rows[0]['游戏'] == 'KK'


def test_character_export_preserves_nested_data_without_modifying_card(bridge, tmp_path):
    card = card_at(tmp_path/'card.png'); original = card.read_bytes()
    result = finish(bridge, bridge.start_export_data({'kind':'character', 'paths':[str(card)],
        'outDir':str(tmp_path/'out'), 'format':'json'}))
    assert result['status'] == 'done',result
    doc = json.loads(Path(result['result']['path']).read_text(encoding='utf-8'))
    assert doc['parameter']['firstname'] == 'Ishtar'
    assert doc['blocks']['Custom'] == {'some':'blob','n':123}
    assert card.read_bytes() == original
    repeat = finish(bridge, bridge.start_export_data({'kind':'character', 'paths':[str(card)],
        'outDir':str(tmp_path/'out'), 'format':'json'}))
    assert repeat['result']['path'] != result['result']['path']


@pytest.mark.parametrize('damage', ['tail','truncate'])
def test_repair_tail_creates_verified_copy_and_keeps_original(bridge, tmp_path, damage):
    path = tmp_path/'data.bin'; original = bytes(range(256))*700
    path.write_bytes(original)
    sidecar = stego.write_recovery_sidecar(path, redundancy=True)
    broken = original[:-20] if damage == 'truncate' else original[:-20]+b'X'*20
    path.write_bytes(broken)
    result = finish(bridge, bridge.start_recovery({'path':str(path), 'sidecar':sidecar,
        'outDir':str(tmp_path/'repair'), 'repair':True}))
    assert result['status'] == 'done',result
    assert Path(result['result']['path']).read_bytes() == original
    assert path.read_bytes() == broken


def test_repair_outside_tail_fails_and_leaves_no_output(bridge, tmp_path):
    path = tmp_path/'data.bin'; original = b'A'*150000
    path.write_bytes(original)
    sidecar = stego.write_recovery_sidecar(path, redundancy=True)
    path.write_bytes(b'B'+original[1:])
    out = tmp_path/'out'
    result = finish(bridge, bridge.start_recovery({'path':str(path), 'sidecar':sidecar,
        'outDir':str(out), 'repair':True}))
    assert result['status'] == 'error',result
    assert path.read_bytes() == b'B'+original[1:]
    assert not out.exists() or list(out.iterdir()) == []


def test_malformed_recovery_record_returns_failure(bridge, tmp_path):
    path = tmp_path/'data.bin'; path.write_bytes(b'broken')
    sidecar = tmp_path/'bad.json'; sidecar.write_text('[]')
    result = finish(bridge, bridge.start_recovery({'path':str(path),'sidecar':str(sidecar),'repair':False}))
    assert result['status'] == 'done',result
    assert not result['result']['ok']


def test_split_outputs_each_have_recovery_and_preserve_orphaned_parts(bridge, tmp_path):
    source = tmp_path / 'data.bin'
    source.write_bytes(bytes(range(256)) * 200)
    out = tmp_path / 'out'
    out.mkdir()
    (out / 'data.zip.001').write_bytes(b'previous-part')
    result = finish(bridge, bridge.start_pack({'sources': [str(source)], 'outDir': str(out),
        'archiveName': 'data', 'writeRecovery': True, 'splitMB': .0001}))
    assert result['status'] == 'done', result
    assert (out / 'data.zip.001').read_bytes() == b'previous-part'
    outputs = result['result']['outputs']
    assert len(outputs) > 1
    assert all(stego.verify_recovery(p)['ok'] for p in outputs)


@pytest.mark.parametrize('mode', ['image', 'video'])
def test_independent_disguises_are_readable_archives(bridge, tmp_path, mode):
    a = tmp_path / 'a.txt'; a.write_text('first')
    b = tmp_path / 'b.txt'; b.write_text('second')
    carrier = tmp_path / ('carrier.png' if mode == 'image' else 'carrier.mp4')
    if mode == 'image':
        Image.new('RGB', (3, 3)).save(carrier)
    else:
        carrier.write_bytes(b'\x00\x00\x00\x18ftypmp42')
    result = finish(bridge, bridge.start_pack({'sources': [str(a), str(b)],
        'outDir': str(tmp_path/'out'), 'independent': True, 'stegoMode': mode,
        'carrierPath': str(carrier), 'writeRecovery': True}))
    assert result['status'] == 'done', result
    assert len(result['result']['jobs']) == 2
    for j in result['result']['jobs']:
        assert j['ok'], j
        p = Path(j['outputs'][0])
        assert p.read_bytes().startswith(carrier.read_bytes())
        with zipfile.ZipFile(p) as z:
            assert z.read(Path(j['source']).name) == Path(j['source']).read_bytes()
        assert stego.verify_recovery(p)['ok']


def test_scene_exports_json_and_text_preserving_original(bridge, tmp_path):
    scene = tmp_path / 'scene.png'
    Image.new('RGB', (2, 2)).save(scene)
    raw, _ = _build_synthetic_card()
    card = KoikatuCard.from_bytes(raw)
    with scene.open('ab') as f:
        f.write(b'KStudio' + raw[len(card.thumbnail):])
    original = scene.read_bytes()
    for fmt in ('json', 'txt'):
        result = finish(bridge, bridge.start_export_data({'kind': 'scene', 'paths': [str(scene)],
            'outDir': str(tmp_path/'export'), 'format': fmt}))
        assert result['status'] == 'done', result
        text = Path(result['result']['path']).read_text(encoding='utf-8')
        if fmt == 'json':
            assert json.loads(text)['character_count'] == 1
        else:
            assert 'Ishtar' in text
    assert scene.read_bytes() == original


def test_encrypted_archive_can_generate_and_verify_recovery(bridge, tmp_path):
    source=tmp_path/'source'; source.mkdir(); (source/'secret.txt').write_text('private')
    result = finish(bridge, bridge.start_pack({'sources':[str(source)],'outDir':str(tmp_path/'out'),
        'passwords':['password'], 'writeRecovery':True}))
    assert result['status'] == 'done',result
    path = result['result']['outputs'][0]
    assert stego.verify_recovery(path)['ok']
