"""新版业务接口的真实文件回归测试。"""
from pathlib import Path
import io
import time

import pytest
from PIL import Image

from core import settings, mod_index
from core.kk_card import KoikatuCard
from web_bridge import KKToolsBridge
from test_kk_card import _build_synthetic_card


@pytest.fixture
def bridge(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, '_CONFIG_PATH', tmp_path / 'config.json')
    obj = KKToolsBridge()
    obj._mod_index = mod_index.ModIndex()
    return obj


def finish(bridge, response):
    assert response['ok'], response
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        state = bridge.poll_task(response['data']['taskId'])['data']
        if state['status'] != 'running':
            assert state['status'] == 'done', state
            return state['result']
        time.sleep(.01)
    pytest.fail('后台任务超时')


def make_card(path):
    raw, _ = _build_synthetic_card()
    path.write_bytes(raw)
    return path


def test_share_export_grouping_and_import(bridge, tmp_path):
    card = make_card(tmp_path / 'chara.png')
    package = tmp_path / 'package'
    finish(bridge, bridge.start_share_export({'cardPaths': [str(card)], 'outDir': str(package), 'groupByChar': True}))
    assert (package / 'Ishtar' / 'chara.png').is_file()
    target = tmp_path / 'import'
    result = finish(bridge, bridge.start_share_import({'pkgDir': str(package), 'cardTarget': str(target)}))
    assert result['report']['cards'] == 1
    assert list(target.rglob('chara.png'))[0].read_bytes() == card.read_bytes()


def test_organize_cards_by_game(bridge, tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    make_card(source / 'chara.png')
    target = tmp_path / 'sorted'
    result = finish(bridge, bridge.start_organize_cards({'srcDir': str(source), 'outDir': str(target), 'by': 'game'}))
    assert result['report']['organized'] == 1
    assert (target / 'KK' / 'chara.png').is_file()


def test_replace_jpeg_cover_converts_to_png_and_preserves_card(bridge, tmp_path):
    source = make_card(tmp_path / 'chara.png')
    cover = tmp_path / 'cover.jpg'
    Image.new('RGB', (35, 45), 'blue').save(cover)
    result = bridge.save_card({'path': str(source), 'parameter': {'firstname': 'Edited'}, 'coverPath': str(cover)})
    assert result['ok'], result
    saved = KoikatuCard.load(result['data']['savedPath'])
    assert saved.parameter['firstname'] == 'Edited'
    assert Image.open(io.BytesIO(saved.thumbnail)).size == (35, 45)
    assert KoikatuCard.load(source).parameter['firstname'] == 'Ishtar'


def test_wallpaper_toggle_retains_path_and_blur(bridge, tmp_path):
    wallpaper = tmp_path / 'wall.png'
    Image.new('RGB', (5, 5)).save(wallpaper)
    response = bridge.save_config({'wallpaper_path': str(wallpaper), 'wallpaper_enabled': False, 'wallpaper_blur': 7})
    assert response['ok'], response
    config = bridge.get_config()['data']
    assert config['wallpaper_path'] == str(wallpaper)
    assert config['wallpaper_enabled'] is False
    assert config['wallpaper_blur'] == 7


@pytest.mark.parametrize('method,options', [
    ('start_pack', {'sources': ['missing'], 'outDir': ''}),
    ('start_share_export', {'cardPaths': ['missing'], 'outDir': ''}),
    ('start_organize_cards', {'srcDir': '', 'outDir': 'out'}),
    ('start_archive_unreferenced', {'cardDir': '', 'archiveDir': 'out'}),
])
def test_blank_required_paths_rejected_before_task(bridge, method, options):
    result = getattr(bridge, method)(options)
    assert result['ok'] is False


def test_card_save_does_not_clear_other_editor_dirty_flag(bridge, tmp_path):
    source = make_card(tmp_path / 'chara.png')
    bridge.set_dirty_state(True)
    result = bridge.save_card({'path': str(source), 'parameter': {'firstname': 'Edited'}})
    assert result['ok'], result
    assert bridge.has_unsaved_edits()


def test_mod_manifest_exchange_and_zip_export(bridge, tmp_path):
    import json
    import zipfile
    source = tmp_path / 'one.zipmod'
    source.write_bytes(b'mod-content')
    bridge._mod_index.entries['one'] = mod_index.ModEntry(guid='one', path=str(source))
    output = tmp_path / 'mine.json'
    assert bridge.export_manifest(str(output))['ok']
    assert json.loads(output.read_text(encoding='utf-8'))['guids'] == ['one']
    theirs = tmp_path / 'theirs.txt'
    theirs.write_text('two\n', encoding='utf-8')
    result = bridge.compare_manifest(str(theirs))['data']
    assert result['mine_only'] == ['one']
    assert result['theirs_only'] == ['two']
    missing = tmp_path / 'missing.txt'
    missing.write_text('one\nabsent\n', encoding='utf-8')
    result = finish(bridge, bridge.start_export_mod_list(str(missing), str(tmp_path)))
    assert result['count'] == 1
    assert result['skipped'] == 1
    with zipfile.ZipFile(result['path']) as archive:
        assert archive.read('one.zipmod') == b'mod-content'


@pytest.mark.parametrize('move', [False, True])
def test_organize_character_name_cannot_escape_output(tmp_path, move):
    from core import share
    from core.kk_card import read_card_light
    source = tmp_path / 'source'
    source.mkdir()
    card_path = make_card(source / 'chara.png')
    card = KoikatuCard.load(card_path)
    card.update_parameter({'firstname': '..', 'lastname': '', 'fullname': '..'})
    card.save(card_path, backup=False)
    assert read_card_light(card_path).name == '..'
    target = tmp_path / 'sorted'
    result = share.organize_cards(source, target, by='character', move=move)
    assert not (tmp_path / 'chara.png').exists()
    assert (target / '未命名' / 'chara.png').is_file()
    assert result['organized'] == 1


@pytest.mark.parametrize('move', [False, True])
def test_organize_mod_author_cannot_escape_output(tmp_path, move):
    source = tmp_path / 'source'
    source.mkdir()
    mod_path = source / 'one.zipmod'
    mod_path.write_bytes(b'mod-content')
    index = mod_index.ModIndex()
    index.entries['one'] = mod_index.ModEntry(guid='one', path=str(mod_path), author='..')
    target = tmp_path / 'sorted'
    result = mod_index.organize_by_author(index, target, move=move)
    assert not (tmp_path / 'one.zipmod').exists()
    assert (target / '未知作者' / 'one.zipmod').is_file()
    assert result['done'] == 1
