"""转换必须拒绝缺损结构，且不能捏造作者身份。"""
import msgpack
import pytest

from core import card_convert, kk_card
from test_card_convert import _make_full_kk_card, _pack_custom


def _damaged_card(change):
    card = kk_card.KoikatuCard.from_bytes(_make_full_kk_card())
    change(card)
    for info in card.block_order:
        if info.name in card.blocks:
            info.size = len(card.blocks[info.name])
    card._dirty = True
    return card.to_bytes()


def test_converting_unknown_author_does_not_create_random_author_groups():
    original = _make_full_kk_card(with_kkex=False)
    ids = []
    for _ in range(2):
        converted, _ = card_convert.convert_card_bytes(original, 'KKS')
        card = kk_card.KoikatuCard.from_bytes(converted)
        assert kk_card.extract_card_author(card)[:3] == ('', (), '')
        ids.append(card.get_block_dict('About')['dataID'])
    assert ids[0] != ids[1]


def test_real_user_identity_survives_conversion():
    original = kk_card.KoikatuCard.from_bytes(_make_full_kk_card(with_kkex=False))
    about = {'version': '0.0.0', 'language': 0, 'userID': '12345678-1234-1234-1234-123456789abc',
             'dataID': '87654321-1234-1234-1234-123456789abc'}
    payload = msgpack.packb(about, use_bin_type=True)
    original.blocks['About'] = payload
    original.block_order.append(kk_card.BlockInfo('About', '0.0.0', 0, len(payload)))
    original._dirty = True
    converted, _ = card_convert.convert_card_bytes(original.to_bytes(), 'KKS')
    card = kk_card.KoikatuCard.from_bytes(converted)
    assert card.blocks['About'] == payload
    assert kk_card.extract_card_author(card)[0] == 'KKSID:12345678'


@pytest.mark.parametrize('block', ['Custom', 'Coordinate', 'Parameter', 'Status'])
def test_missing_required_block_is_rejected_before_writing(tmp_path, block):
    def remove(card):
        card.blocks.pop(block)
        card.block_order[:] = [i for i in card.block_order if i.name != block]
    raw = _damaged_card(remove)
    source = tmp_path / 'broken.png'
    destination = tmp_path / 'broken_KKS.png'
    source.write_bytes(raw)
    with pytest.raises(card_convert.CardConvertError, match=block):
        card_convert.convert_card_file(source, 'KKS', out_dir=tmp_path)
    assert source.read_bytes() == raw
    assert not destination.exists()


@pytest.mark.parametrize(('block', 'payload'), [
    ('Coordinate', msgpack.packb([])),
    ('Coordinate', msgpack.packb([b'truncated-slot'])),
    ('Parameter', msgpack.packb({'version': '0.0.5'})),
    ('Parameter', msgpack.packb({'version': '0.0.99', 'sex': 1, 'attribute': {}})),
    ('Status', msgpack.packb([])),
    ('Custom', _pack_custom({'version': '0.0.2'}, {'version': '0.0.2'}, {'version': '0.0.4', 'parts': 'broken'})),
])
def test_structurally_invalid_blocks_are_rejected(block, payload):
    raw = _damaged_card(lambda card: card.blocks.__setitem__(block, payload))
    with pytest.raises(card_convert.CardConvertError, match=block):
        card_convert.convert_card_bytes(raw, 'KKS')


def test_source_is_preserved_on_validation_failure_with_overwrite(tmp_path):
    raw = _damaged_card(lambda card: card.blocks.__setitem__('Coordinate', msgpack.packb([])))
    source = tmp_path / 'source.png'
    source.write_bytes(raw)
    with pytest.raises(card_convert.CardConvertError):
        card_convert.convert_card_file(source, 'KKS', overwrite=True)
    assert source.read_bytes() == raw
    assert not source.with_suffix('.png.bak').exists()


def test_required_blocks_are_checked_again_after_serialization(monkeypatch):
    serialize = kk_card.KoikatuCard.to_bytes
    def drop_coordinate(card):
        card.blocks.pop('Coordinate', None)
        card.block_order[:] = [i for i in card.block_order if i.name != 'Coordinate']
        return serialize(card)
    monkeypatch.setattr(kk_card.KoikatuCard, 'to_bytes', drop_coordinate)
    with pytest.raises(card_convert.CardConvertError, match='Coordinate'):
        card_convert.convert_card_bytes(_make_full_kk_card(), 'KKS')
