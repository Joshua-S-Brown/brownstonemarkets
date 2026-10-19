"""STORY-098: captured facts, conservative derivation, explicit writes and unchanged walkers."""
import json
import sys
import tomllib
from copy import deepcopy
from pathlib import Path

import duckdb
import pytest
from test_progression import evidence, progression_catalog
from test_scans import addon_source
from test_today import MARKET, NOW, SNAPSHOT
from test_today_characters import CHARACTER

from brownstone import cli
from brownstone import skillup_evidence as evidence_report
from brownstone.crafting import parse_recipe_catalog
from brownstone.markets import MARKET_KEYS
from brownstone.recipe_import import dumps_catalog

FIXTURE = Path(__file__).parent / 'fixtures/skillups/journal.json'


def test_captured_numeric_missing_legacy_and_dedup_provenance():
    records = json.loads(FIXTURE.read_text())
    unlearned = {'recipe_id': 12, 'info': {'learned': False, 'relativeDifficulty': 0, 'maxTrivialLevel': 90}}
    stale = {'recipe_id': 13, 'recipe_link': '|Henchant:13|h[Cooking: Stale]|h', 'info': {'relativeDifficulty': 0}}
    records[0]['known_recipes']['rows'] += [unlearned, stale]
    observations, trainers = evidence_report.observations([*records, records[0] | {'entry_id': 'repeat'}])
    assert ('Mining', 12) not in observations and ('Mining', 13) not in observations
    readings = observations['Mining', 10]
    assert {r[4] for r in readings} == {'optimal', 'medium', 'easy', 'trivial'}
    assert {r[3] for r in readings} == {1, 14, 25, 47, 70}
    assert len(readings) == 5
    assert next(ids for r, ids in readings.items() if r[3] == 14) == {'modern-0', 'repeat'}
    assert all(r[4] is None for r in observations['Mining', 11])
    assert trainers['Mining', 'Craft 10'] == {(25, 100): {'trainer'}}


@pytest.mark.parametrize('case,status,colors', [
    ('gap', 'derived', [1, 15, 26, 70]), ('match', 'confirms', None),
    ('band', 'contradicts', None), ('grey', 'contradicts', None),
    ('no orange', 'not observed', None), ('no yellow', 'derived', [1, 15, 15, 70]),
    ('no grey', 'not observed', None), ('no skill', 'not observed', None),
    ('conflicting grey', 'contradicts', None), ('unobserved', 'not observed', None),
])
def test_confirm_contradict_and_conservative_gap(case, status, colors):
    observations, _ = evidence_report.observations(json.loads(FIXTURE.read_text()))
    readings = observations['Mining', 10]
    recipe = {'required_skill': 25}
    if case in ('match', 'band', 'grey'):
        recipe['skillup_colors'] = {'match': [1, 15, 26, 70], 'band': [1, 10, 26, 70],
                                   'grey': [1, 15, 26, 71]}[case]
    if case in ('no orange', 'no yellow'):
        readings = {r: ids for r, ids in readings.items() if r[4] != ('optimal' if case == 'no orange' else 'medium')}
    if case == 'no grey':
        readings = {(*r[:5], None, r[6]): ids for r, ids in readings.items()}
    if case == 'no skill':
        recipe = {}
    if case == 'conflicting grey':
        readings = readings | {('Bob', 'Beta', 'Alliance', 1, 'optimal', 71, 1): {'other'}}
    if case == 'unobserved':
        readings = observations['Mining', 11]
    before = deepcopy(recipe)
    assert evidence_report.compare(recipe, readings) == (status, colors)
    assert recipe == before


def test_captured_colors_are_rederived_not_confirmed():
    recipe = {'recipe_id': 10, 'name': 'Craft 10', 'required_skill': 25, 'skillup_colors': [1, 15, 26, 99],
              'skillup_colors_basis': 'captured'}
    entry = {'catalog': {'profession': 'mining', 'recipes': [recipe]}}
    rows, _, _ = evidence_report.report_rows([entry], json.loads(FIXTURE.read_text()))
    assert (rows[0]['status'], rows[0]['colors']) == ('derived', [1, 15, 26, 70])


def test_cli_readonly_scopes_explicit_write_and_no_contradiction_write(tmp_path, monkeypatch, capsys):
    catalog = progression_catalog()
    catalog.update(profession='mining')
    for recipe in catalog['recipes']:
        recipe['profession'] = 'mining'
    catalog['recipes'][0].update(recipe_id=10, name='Craft 10', required_skill=25)
    catalog['recipes'][0].pop('skillup_colors')
    catalog = parse_recipe_catalog(catalog)
    selection = tmp_path / 'recipe-selections' / 'test.toml'
    selection.parent.mkdir()
    selection.write_text('game_version="forever"\nrules_version="forever-beta-1.60"\n'
                         'profession="mining"\nstatus="test"\ncatalog_version="1"\n'
                         '[[recipes]]\nrecipe_id = 10 # keep this comment\n\n'
                         '[[recipes]]\nrecipe_id = 31\n')
    (tmp_path / 'test.toml').write_text(dumps_catalog(catalog))
    config = addon_source(tmp_path / 'data')
    config.update(game_version=catalog['game_version'], rules_version=catalog['rules_version'])
    config['data_dir'].mkdir()
    records = json.loads(FIXTURE.read_text())
    records[0]['known_recipes']['rows'].append(
        {'recipe_id': 31, 'info': {'relativeDifficulty': 3, 'maxTrivialLevel': 60}})
    records[-1]['trainer_services'].append(
        {'info': {'1': 'Craft 10'}, 'skill_required': {'1': 'Mining', '2': 25}, 'cost': {'1': 101}})
    # A real persisted table permits full source/market predicates without a scan or migrations.
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb')) as db:
        columns = ', '.join(f'{k} VARCHAR' for k in ('source_id', *MARKET_KEYS))
        db.execute(f'CREATE TABLE character_journal ({columns}, family VARCHAR, record_json VARCHAR)')
        for record in records:
            values = [config[k] for k in ('source_id', *MARKET_KEYS)] + [record['family'], json.dumps(record)]
            db.execute(f'INSERT INTO character_journal VALUES ({", ".join("?" for _ in values)})', values)
    # Character loading is independently covered; no scan means effects must be unknown, never zero.
    monkeypatch.setattr(evidence_report.today_loading, 'load_today_characters', lambda _: ({}, None))
    before = selection.read_bytes()
    for field in ('source_id', *MARKET_KEYS):
        lines = evidence_report.run(config | {field: config[field] + '-other'}, tmp_path)
        assert not any(': derived;' in line for line in lines)
    monkeypatch.setattr(cli, '_select_source', lambda _: config)
    monkeypatch.setattr(sys, 'argv', ['brownstone', 'skillups', '--config', str(tmp_path / 'market.toml')])
    cli.main()
    text = capsys.readouterr().out
    assert 'Craft 10 (10): derived;' in text and 'trainer: confirms' in text
    assert 'Recipe 31 (31): contradicts;' in text and 'trainer: contradicts' in text
    assert 'cost=1s' in text and 'Read-only' in text and 'unknown (no snapshot)' in text
    assert selection.read_bytes() == before
    sys.argv.append('--write')
    cli.main()
    assert 'Wrote 1 derived picks' in capsys.readouterr().out
    picks = tomllib.loads(selection.read_text())['recipes']
    assert picks[0]['captured_skillup_colors'] == [1, 15, 26, 70]
    assert picks[0]['captured_colors_source'] == ['legacy', 'modern-0', 'modern-1', 'modern-2', 'modern-3']
    assert picks[1] == {'recipe_id': 31}
    assert '# keep this comment' in selection.read_text()
    after = selection.read_bytes()
    cli.main()
    capsys.readouterr()
    assert selection.read_bytes() == after


def test_effect_counts_use_actual_progression_and_hiring(monkeypatch):
    c = progression_catalog()
    base = c['recipes_by_id'][30]
    base.update(skillup_colors=[1, 300, 301, 302], skillup_colors_basis='captured')
    data = {CHARACTER: evidence(c)}
    arguments = dict(observations={i: {'min_buyout': 10} for i in c['items_by_id']}, market=MARKET,
                     snapshot=SNAPSHOT, now=NOW, max_age_hours=24, auction_cut=.05,
                     listings={1: [(1, 10, 10)] * 500, 2: [(1, 10, 10)] * 500}, metrics=None)
    monkeypatch.setattr(evidence_report.today_loading, 'load_today_characters', lambda _: (data, None))
    monkeypatch.setattr(evidence_report.today_loading, 'load_today', lambda *args: (SNAPSHOT, arguments))
    before = deepcopy(c)
    assert evidence_report.effect_counts([c], MARKET) == {'tailoring': {'hire': 1, 'path': 2}}
    assert c == before


def test_write_never_adds_a_pick_for_an_unpicked_intermediate(tmp_path):
    selection = tmp_path / 'test.toml'
    selection.write_text('profession="mining"\n\n[[recipes]]\nrecipe_id = 10\n')
    before = selection.read_bytes()
    row = {'status': 'derived', 'entry': {'selection_path': selection}, 'profession': 'Mining',
           'recipe': {'recipe_id': 20, 'name': 'Intermediate'}, 'colors': [1, 2, 3, 4],
           'observations': {('A', 'R', 'Alliance', 1, 'optimal', 4, 1): {'j1'}}}
    assert evidence_report.write_selections([row]) == (0, ['Mining / Intermediate (20)'])
    assert selection.read_bytes() == before
