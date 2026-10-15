"""Offline evidence validation and shared UI-12 lookup contracts."""
from datetime import date

import pytest

from brownstone import tier_levels


def test_tracked_evidence_values_and_provenance():
    levels = tier_levels.load()
    assert len(levels) == 9
    for (profession, tier), row in levels.items():
        assert row['level'] == (10 if profession == 'fishing' else 0)
        assert row['character'] == 'Cicelyna' and row['captured_date'] == date(2026, 10, 15)
        assert row['entry_id'].startswith('8:Cicelyna18:Classic Beta PvE 2:journal:')
        assert tier in tier_levels.TIERS
    assert 'Cooking Journeyman 0' in tier_levels.explanation(levels, 'forever')
    assert 'Classic Era tier levels' in tier_levels.explanation(levels, 'classic_era')
    assert 'none' in tier_levels.explanation({}, 'forever')


@pytest.mark.parametrize('change', [
    {'level': -1}, {'level': True}, {'level': '0'}, {'tier': 'Master'}, {'profession': ''},
    {'entry_id': ''}, {'character': 1}, {'captured_date': '2026-10-15'}, {'extra': 'field'},
])
def test_invalid_evidence_rows(tmp_path, change):
    row = next(iter(tier_levels.load().values())) | change
    with pytest.raises(ValueError):
        tier_levels._validate(row)


@pytest.mark.parametrize('text', ['bad = [', 'levels = 0', '', 'levels = []\nextra = 1'])
def test_malformed_file_is_error(tmp_path, text):
    path = tmp_path / 'tiers.toml'
    path.write_text(text)
    with pytest.raises(ValueError):
        tier_levels.load(path)


def test_duplicate_case_insensitive_key_is_error(tmp_path):
    block = '''[[levels]]
profession = "Cooking"
tier = "Journeyman"
level = 0
entry_id = "record"
character = "Cicelyna"
captured_date = 2026-10-15
'''
    path = tmp_path / 'tiers.toml'
    path.write_text(block + block.replace('Cooking', 'COOKING'))
    with pytest.raises(ValueError, match='Duplicate'):
        tier_levels.load(path)
    path.write_text('levels = []')
    assert tier_levels.load(path) == {}
