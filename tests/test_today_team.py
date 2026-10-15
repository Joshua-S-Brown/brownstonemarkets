"""Offline STORY-057 skill-ID completeness, team union and filtered planning."""
from copy import deepcopy
from dataclasses import replace

import pytest
from test_character_snapshots import snapshot
from test_journal import write
from test_scans import NOW, addon_source
from test_today import catalog, output_catalog, plan
from test_today_characters import CHARACTER, recipe, state

from brownstone.config import MARKET_KEYS
from brownstone.pipeline import import_scans
from brownstone.professions import latest_data
from brownstone.today_characters import NO_CHARACTER_EVIDENCE, PROFESSION_SKILL_IDS, recipe_status
from brownstone.today_settings import TodaySettings, load_settings, save_settings
from views.today_rows import _character_columns


def skills_state(ids=(), *, modern=True, incomplete=False):
    rows = [{'index': i, 'skill_id': sid, 'name': 'Unrelated label', 'rank': 8}
            for i, sid in enumerate(ids, 1)]
    api = {'rows': rows, 'possibly_incomplete': incomplete}
    if modern:
        api['indexes'] = {'n': 6, **{str(i): i for i in range(1, len(rows) + 1)}}
    else:
        api['counts'] = {'1': len(rows), 'n': 1}
    return {'bags': {'captured_at': 200, 'sequence': 1,
                     'skills': {'modern' if modern else 'legacy': api}}, 'recipes': {}, 'seen': {}}


@pytest.mark.parametrize('modern', [True, False])
def test_no_profession_only_with_complete_list(modern):
    evidence = skills_state(modern=modern)
    status = recipe_status(recipe(), evidence)
    assert status['craft_status'] == 'Not yet'
    assert status['character_reason'] == 'no character has this profession'
    evidence['bags']['skills']['modern' if modern else 'legacy']['possibly_incomplete'] = True
    assert recipe_status(recipe(), evidence)['craft_status'] == 'Unknown'


@pytest.mark.parametrize('surface', [None, {}, {'modern': {'rows': []}},
    {'modern': {'indexes': {'n': 6, '1': 1}, 'rows': []}},
    {'modern': {'indexes': {'n': 6, '1': 1}, 'rows': [{'index': 1, 'name': 'Tailoring'}]}},
    {'legacy': {'counts': {'1': 1}, 'rows': []}},
    {'legacy': {'counts': {'1': 1}, 'rows': [{'name': 'Tailoring'}]}}])
def test_unreadable_skills_stay_unknown(surface):
    evidence = skills_state()
    evidence['bags']['skills'] = surface
    assert recipe_status(recipe(), evidence)['craft_status'] == 'Unknown'


def test_skill_id_table_never_names_and_positive_knowledge():
    assert PROFESSION_SKILL_IDS == {'alchemy': 171, 'blacksmithing': 164, 'cooking': 185,
        'enchanting': 333, 'engineering': 202, 'first-aid': 129, 'leatherworking': 165,
        'mining': 186, 'tailoring': 197}
    for profession, sid in PROFESSION_SKILL_IDS.items():
        assert recipe_status(recipe(profession=profession), skills_state([sid]))['craft_status'] == 'Unknown'
        assert recipe_status(recipe(profession=profession), skills_state())['craft_status'] == 'Not yet'
    misleading = skills_state([164])
    misleading['bags']['skills']['modern']['rows'][0]['name'] = 'Tailoring'
    assert recipe_status(recipe(), misleading)['craft_status'] == 'Not yet'
    assert recipe_status(recipe(profession='unmapped'), misleading)['craft_status'] == 'Unknown'
    learned = state(learned=True) | {'bags': skills_state([197])['bags']}
    assert recipe_status(recipe(), learned)['craft_status'] == 'Known'
    seen = skills_state([197]) | {'seen': {'anything': {30: {}}}}
    assert recipe_status(recipe(), seen)['craft_status'] == 'Known'
    learned['bags'] = skills_state()['bags']
    seen['bags'] = skills_state()['bags']
    assert recipe_status(recipe(), learned)['craft_status'] == 'Not yet'
    assert recipe_status(recipe(), seen)['craft_status'] == 'Not yet'
    # Profession learned after the skills snapshot: the newer window list wins.
    learned['bags']['captured_at'] = 50
    assert recipe_status(recipe(), learned)['craft_status'] == 'Known'
    assert recipe_status(recipe(), state() | {'bags': learned['bags']})['craft_status'] == 'Train now'


def test_team_union_names_bags_only_and_unchanged_reservations():
    c = catalog()
    c['recipes_by_id'][30].update(learned_from=[6], required_skill=8)
    other = ('Other', 'Beta', 'Alliance')
    data = {CHARACTER: state(learned=True), other: skills_state()}
    team = plan(catalogs=[c], character_data=data)
    selected = plan(TodaySettings(10000, 1, 'fixed', character=CHARACTER), catalogs=[c], character_data=data)
    assert _character_columns(team['craft'][0]) == {'Who can make it': 'Basilly'}
    for field in ('buy', 'sell', 'shopping_total_copper', 'queue'):
        assert team[field] == selected[field]
    assert plan(TodaySettings(10000, 1, 'fixed', character=other),
                catalogs=[c], character_data=data)['hidden'] == {'no character has this profession': 1}
    data[other] = state(rank=7)
    team = plan(catalogs=[c], character_data=data)
    assert team['craft'][0]['who_can_make_it'] == ['Basilly']
    data[other] = state()
    assert plan(catalogs=[c], character_data=data)['craft'][0]['who_can_make_it'] == ['Basilly', 'Other']


def test_unknown_switch_and_no_character_fallback():
    settings = TodaySettings(10000, 1, 'fixed')
    unknown = {CHARACTER: skills_state([197])}
    result = plan(settings, character_data=unknown)
    assert not result['craft'] and not result['buy'] and not result['queue']['lines']
    assert result['hidden'] == {'unknown for every character': 1}
    included = plan(replace(settings, include_unknown=True), character_data=unknown)
    assert included['craft'][0]['craft_status'] == 'Unknown'
    assert _character_columns(included['craft'][0])['Can make'] == 'Unknown'
    assert included['today_version'] == 11
    excluded = plan(replace(settings, include_unknown=True), character_data={CHARACTER: skills_state()})
    assert not excluded['craft'] and excluded['hidden'] == {'no character has this profession': 1}
    fallback = plan(settings, character_data={})
    assert fallback['craft'] and fallback['character_note'] == NO_CHARACTER_EVIDENCE
    assert not included['character_note']


def test_counts_per_reason_and_exclusion_before_prices():
    catalogs = []
    evidence = state(rank=8)
    rows = evidence['recipes']['Arbitrary title']['known_recipes']['rows']
    rows.clear()
    for i, (profession, required, source) in enumerate([
        ('blacksmithing', 1, [6]), ('tailoring', 9, [6]),
        ('tailoring', 1, [5]), ('tailoring', 1, None)], 30):
        c = output_catalog(i, str(i))
        r = c['recipes_by_id'].pop(30) | {'recipe_id': i, 'profession': profession,
                                        'required_skill': required, 'learned_from': source}
        c['recipes_by_id'][i] = r
        c['recipe_for_output'][i] = i
        rows.append({'recipe_id': i, 'learned': False})
        catalogs.append(c)
    evidence['bags'] = skills_state([197])['bags']
    result = plan(catalogs=catalogs, character_data={CHARACTER: evidence}, observations={})
    assert result['hidden'] == {'no character has this profession': 1, 'rank below required skill': 1,
                                'needs pattern or other source': 1, 'unknown for every character': 1}
    assert not result['craft']


def test_latest_snapshot_scope_freshness_sequence_and_dedup(tmp_path):
    records = [snapshot('old', sequence=1) | {'skills': skills_state([197])['bags']['skills']},
               snapshot('new', sequence=2) | {'skills': skills_state()['bags']['skills']},
               snapshot('bank', kind='bank', sequence=3) | {'skills': skills_state([197])['bags']['skills']}]
    path = write(tmp_path / 'skills.lua', [], records)
    config = addon_source(tmp_path / 'data', path)
    import_scans(config, now=NOW)
    import_scans(config, now=NOW)
    foreign = write(tmp_path / 'other.lua', [], [snapshot('foreign', character='Other') | {
        'skills': skills_state([197])['bags']['skills']}])
    import_scans(config | {'source_id': 'other', 'scan_path': foreign}, now=NOW)
    data = latest_data(config)
    assert len(data[('Alice', 'Beta', 'Alliance')]['history']) == 2
    assert recipe_status(recipe(), data[('Alice', 'Beta', 'Alliance')])['craft_status'] == 'Not yet'
    assert not plan(character_data=data)['craft']
    for key in ('source_id', *MARKET_KEYS):
        assert latest_data(config | {key: 'outside'}) == {}
    assert ('Other', 'Beta', 'Alliance') not in data
    # Newer unreadable skill evidence cannot borrow the old complete list.
    unreadable = deepcopy(records[1]) | {'snapshot_id': 'unreadable', 'sequence': 4, 'skills': {}}
    path = write(tmp_path / 'unreadable.lua', [], [unreadable])
    import_scans(config | {'scan_path': path}, now=NOW)
    assert recipe_status(recipe(), latest_data(config)[('Alice', 'Beta', 'Alliance')])['craft_status'] == 'Unknown'


def test_old_settings_team_default_and_unknown_switch_validation(tmp_path):
    path = tmp_path / 'old.json'
    path.write_text('{"gold_copper": 10000}')
    saved = load_settings(path)
    assert saved.character is None and not saved.include_unknown
    save_settings(path, replace(saved, include_unknown=True))
    assert load_settings(path).include_unknown
    with pytest.raises(ValueError, match='boolean'):
        TodaySettings(include_unknown=1)
