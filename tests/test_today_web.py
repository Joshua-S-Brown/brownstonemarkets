"""STORY-083: shared merge, complete route, API state, settings and lazy session contracts.

Rule coverage migrated from test_nicegui_today*, alongside Vitest interaction tests.
"""
from copy import deepcopy
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app_helpers import app as fixture_app
from app_helpers import listing_evidence_app
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_today import MARKET, NOW, SNAPSHOT, catalog

import api
from api import today
from brownstone import today_loading, today_session
from brownstone.today import apply_removals, build_today, craft_details
from brownstone.today_settings import TodaySettings, load_settings, settings_path
from views import today_rows

TOKEN = {'X-Brownstone-Token': 'offline-token'}


@pytest.fixture
def browser(tmp_path, monkeypatch):
    _, source, path = fixture_app(tmp_path, monkeypatch)
    monkeypatch.setattr(today, '_cache', {})
    server = FastAPI()
    api.install(server, tmp_path / 'dist', 'offline-token')
    with TestClient(server) as client:
        yield client, source, path


def request(browser, state=None, view='route'):
    client, source, _ = browser
    return client.post('/api/today/plan', params={'source': source['source_id']},
                       json={'view': view, 'state': state or {}}, headers=TOKEN)


def arguments(**updates):
    return dict(catalogs=[catalog()], market=MARKET, snapshot=SNAPSHOT, settings=TodaySettings(100000, 1, 'fixed'),
                now=NOW, observations={1: {'min_buyout': 10}, 3: {'min_buyout': 2000}},
                max_age_hours=24, auction_cut=.05) | updates


def test_merge_reset_dropped_choices_appended_rows_and_input_immutable():
    args = arguments()
    result, state, note = today_session.session_plan(args, {})
    assert not note and state['rows'] and state['choices'] is None
    state['choices'] = [dict(catalog_id='fixture', recipe_id=30, batch_size=10000)]
    original = deepcopy(state)
    result, changed, _ = today_session.session_plan(args, state)
    assert state == original and result['dropped_choices']
    assert changed['choices'][0]['batch_size'] is None
    state = dict(state, rows=[], choices=[])
    result, changed, _ = today_session.session_plan(args, state)
    assert changed['rows'] and changed['choices'][0]['batch_size'] == result['craft'][0]['batch_size']
    state['ticks'] = {'0': True}
    _, changed, note = today_session.session_plan(arguments(settings=TodaySettings(10000)), state)
    assert note == today_session.PLAN_RESET and changed['ticks'] == {} and changed['choices'] is None


def test_every_stage_route_preserves_lines_and_group_order():
    lines = [dict(stage='take', name='Cloth', character='A', kind='bank', units=2),
             dict(stage='take', name='Thread', character='A', kind='bank', units=1),
             dict(stage='mail', name='Cloth', character='A', to='B', units=2),
             dict(stage='gold mail', name='B', character='A', copper=123),
             dict(stage='gold unknown', name='C', copper=50),
             dict(stage='auction house', name='Cloth', item_id=1, purchased_units=3,
                  highest_unit_copper=20, cost_copper=60),
             dict(stage='vendor', name='Thread', item_id=2, purchased_units=1, highest_unit_copper=10, cost_copper=10),
             dict(stage='craft', name='Robe', catalog_id='fixture', recipe_id=30, batch_size=1,
                  profession='tailoring', made_by='B'),
             dict(stage='post', name='Robe', quantity=1, unit_copper=200, profit_copper=130,
                  deposit_copper=100, post_duration_hours=8)]
    crafts = [dict(output_name='Robe', made_by='B', purchases=[dict(item_id=1, method='buy'),
                                                           dict(item_id=2, method='vendor')])]
    stops = today_session.route_stops({'lines': lines}, crafts, {})
    assert [line['evidence'] for s in stops for line in s['lines']] == lines
    assert [line['index'] for s in stops for line in s['lines']] == list(range(len(lines)))
    assert len(stops[0]['lines']) == 2 and stops[0]['place'] == 'bank'
    assert stops[2]['place'] == 'mailbox'
    assert stops[3]['character'] == 'B' and stops[4]['character'] == 'B'
    assert stops[-2]['place'] == 'tailoring · rank unknown'
    assert stops[-1]['place'] == 'auction house · 8h posts'
    assert 'refunded on a sale' in stops[-1]['lines'][0]['text']


def test_ticks_reset_on_queue_or_context_but_not_confidence():
    queue = {'lines': [dict(name='Cloth', confidence='Low', confidence_reasons=['old'])]}
    state = today_session.queue_state(queue, {'context': 'one'})
    state['ticks']['0'] = True
    altered = {'lines': [dict(name='Cloth', confidence='High', confidence_reasons=[])]}
    assert today_session.queue_state(altered, state)['ticks'] == {'0': True}
    assert today_session.queue_state(queue, state | {'context': 'two'})['ticks'] == {}
    assert today_session.queue_state({'lines': [dict(name='Thread')]}, state)['ticks'] == {}


@pytest.mark.parametrize('addon', [False, True])
def test_api_matches_shared_plan_reserved_costs_complete_queue_and_copy(browser, monkeypatch, tmp_path, addon):
    if addon:
        _, source = listing_evidence_app(tmp_path, monkeypatch, -1)
        browser = browser[0], source, settings_path(source['data_dir'], source['source_id'])
    response = request(browser)
    assert response.status_code == 200, response.text
    data = response.json()
    source = browser[1]
    _, args = today_loading.load_today(source, [catalog()], load_settings(browser[2]), {}, datetime.now(UTC),
                                      flood=True, holdings=True)
    expected = build_today(**args)
    apply_removals(expected, today_loading.load_today_removals(source, expected))
    assert data['plan']['queue'] == expected['queue']
    assert len(data['plan']['craft']) == len(expected['craft'])
    assert data['copy_text'] == '\n'.join([expected['queue']['mail_note'],
        *map(today_session.queue_line, expected['queue']['lines']), today_session.queue_total(expected['queue'])])
    assert sum(m['cost_copper'] for m in craft_details(expected['craft'][0])['materials']) == (
        data['plan']['craft'][0]['batch_cost_copper'])
    assert data['session'] is None and data['settings'] == asdict(load_settings(browser[2]))


def test_one_load_cached_until_inputs_plan_state_settings_or_hour_change(browser, monkeypatch):
    spy = Mock(wraps=today_loading.load_today)
    build = Mock(wraps=today_session.session_plan)
    monkeypatch.setattr(today_loading, 'load_today', spy)
    monkeypatch.setattr(today_session, 'session_plan', build)
    data = request(browser).json()
    request(browser)
    request(browser, data['state'], 'opportunities')
    assert spy.call_count == build.call_count == 1
    data['state'] |= {'ticks': {'0': True}, 'hide_low': True}
    ticked = request(browser, data['state']).json()
    assert spy.call_count == 1 and ticked['state']['ticks'] == {'0': True} and ticked['state']['hide_low']
    stale = request(browser, data['state'] | {'queue_identity': 'old'}).json()
    assert spy.call_count == 2 and stale['state']['ticks'] == {} and stale['state']['hide_low']
    data['state']['refill'] = False
    request(browser, data['state'])
    assert spy.call_count == 3
    monkeypatch.setattr(today, 'datetime', SimpleNamespace(now=lambda zone: datetime.now(UTC) + timedelta(hours=2)))
    request(browser, data['state'])
    assert spy.call_count == 4


def test_lazy_level_up_reuses_flood_and_load_and_preserves_plan(browser, monkeypatch):
    from brownstone import flood_signals
    signals = Mock(wraps=flood_signals.signals)
    options = Mock(wraps=today.session_options.build_options)
    monkeypatch.setattr(flood_signals, 'signals', signals)
    monkeypatch.setattr(today.session_options, 'build_options', options)
    route = request(browser).json()
    assert options.call_count == 0
    level = request(browser, route['state'], 'level-up').json()
    assert level['plan'] == route['plan'] and level['session']['characters'] == []
    request(browser, route['state'], 'level-up')
    assert options.call_count == 1 and signals.call_count == 1


@pytest.mark.parametrize('endpoint', ['plan', 'settings'])
def test_post_token_and_source_refusal(browser, endpoint):
    client, _, _ = browser
    assert client.post('/api/today/' + endpoint, json={}).status_code == 403
    assert client.post('/api/today/' + endpoint + '?source=foreign',
                       json={'settings': {}}, headers=TOKEN).status_code == 404
    assert request(browser, view='invented').status_code == 422


def test_settings_saved_cancelled_invalid_and_failed_write_keep_saved_plan(browser, monkeypatch):
    client, source, path = browser
    data = request(browser).json()
    before = path.read_bytes()
    assert client.post('/api/today/settings', json={'settings': {'max_crafts': 0}}, headers=TOKEN).status_code == 400
    assert before == path.read_bytes()
    saved = data['settings'] | {'post_duration_hours': 8}
    assert client.post('/api/today/settings', json={'settings': saved}, headers=TOKEN).status_code == 200
    assert load_settings(path).post_duration_hours == 8
    data['state']['ticks'] = {'0': True}
    updated = request(browser, data['state']).json()
    assert updated['reset_note'] == today_session.PLAN_RESET and updated['state']['ticks'] == {}
    assert all(line['post_duration_hours'] == 8 for line in updated['plan']['queue']['lines']
               if line['stage'] == 'post')
    before = path.read_bytes()
    monkeypatch.setattr(today.today_settings, 'save_settings', Mock(side_effect=OSError('read only')))
    assert client.post('/api/today/settings', json={'settings': saved}, headers=TOKEN).status_code == 409
    assert path.read_bytes() == before
    assert request(browser, updated['state']).json()['plan'] == updated['plan']


def test_corrupt_settings_not_replaced_and_no_snapshot_explained(browser, monkeypatch):
    browser[2].write_text('not json')
    data = request(browser).json()
    assert 'Unable to read Today settings' in data['notes'][0]
    assert browser[2].read_text() == 'not json'
    monkeypatch.setattr(today_loading, 'load_today', lambda *a, **k: (None, None))
    monkeypatch.setattr(today, '_cache', {})
    assert request(browser).status_code == 409


@pytest.mark.parametrize('hours', [-25, 1])
def test_addon_stale_and_future_inspect_only(browser, tmp_path, monkeypatch, hours):
    _, source = listing_evidence_app(tmp_path, monkeypatch, hours)
    data = request((browser[0], source, browser[2])).json()
    assert data['plan']['freshness']['stale']
    assert all(r['stale'] and not r['actionable'] for r in data['plan']['craft'])


def test_held_material_output_unknown_bank_and_unreadable_holdings(browser, monkeypatch):
    from test_today_characters import state
    from test_today_holdings import evidence
    monkeypatch.setattr('brownstone.professions.latest_data',
                        lambda config: {('Arille', 'realm', 'alliance'): state(learned=True)})
    held = evidence((1, 2, 'Basilly', 'bags'), (3, 2, 'Basilly', 'bags'), age=30, unknown_bank=True)
    monkeypatch.setattr(today_loading, '_load_holdings', lambda *a: (held, None))
    data = request(browser).json()
    assert any('bank not captured' in note for note in data['notes'])
    assert 'Basilly mails 2' in data['copy_text'] and 'post 5 crafted + 2 held' in data['copy_text']
    assert all(r['method'] != 'held' for r in data['plan']['buy'])
    assert 'held count from a stale capture' in data['copy_text']
    monkeypatch.setattr(today_loading, '_load_holdings', lambda *a: (None, 'Unable to read held items: bad capture'))
    monkeypatch.setattr(today, '_cache', {})
    assert request(browser).json()['plan']['holdings_warning'].startswith('Unable to read held items')


def test_warnings_retained_on_crafts_sell_route_and_confidence(browser, monkeypatch):
    from test_today_warnings import signal
    monkeypatch.setattr('brownstone.flood_signals.signals', lambda *a: {'rows': [signal(typical=1000)]})
    monkeypatch.setattr(today_loading, 'load_today_removals', lambda *a: {3: {'pairs': 3, 'units': 0}})
    data = request(browser).json()
    for row in [*data['plan']['craft'], *data['plan']['sell']]:
        assert row['confidence'] == 'Low' and row['early_removals']['units'] == 0
    post = next(line for s in data['stops'] for line in s['lines'] if line['evidence']['stage'] == 'post')
    assert post['evidence']['signal'] and post['evidence']['early_removals']['pairs'] == 3


def test_character_eligibility_funds_override_and_missing_character(browser, monkeypatch):
    from test_today_characters import CHARACTER, state
    data = {CHARACTER: state(learned=True)}
    data[CHARACTER]['bags'] = {'captured_at': int(datetime.now(UTC).timestamp()), 'gold_copper': 12345}
    monkeypatch.setattr('brownstone.professions.latest_data', lambda c: data)
    result = request(browser).json()
    assert result['funds_copper'] == 12345 and result['plan']['craft'][0]['made_by'] == CHARACTER[0]
    saved = result['settings'] | {'gold_override': True, 'gold_copper': 9999}
    browser[0].post('/api/today/settings', json={'settings': saved}, headers=TOKEN)
    overridden = request(browser).json()
    assert overridden['funds_copper'] == 9999
    assert overridden['evidence']['recorded_gold'][0]['gold_copper'] == 12345
    assert overridden['evidence']['auction_cut'] == .05
    assert all(k in overridden['evidence']['market'] for k in MARKET)
    saved.update(gold_override=False, character=['Missing', 'realm', 'alliance'])
    browser[0].post('/api/today/settings', json={'settings': saved}, headers=TOKEN)
    assert request(browser).json()['funds_copper'] == 12345


def test_bands_unknown_rank_and_catalog_evidence():
    row = {'catalog_id': 'fixture', 'recipe_id': 30}
    assert 'unknown' in today_rows.recipe_band(row, 1, [catalog()])
    c = catalog()
    c['recipes_by_id'][30]['skillup_colors'] = [1, 20, 30, 40]
    for rank, color in [(0, "needs 1 · you're 0"), (1, 'orange'), (20, 'yellow'), (30, 'green'), (40, 'grey')]:
        assert today_rows.recipe_band(row, rank, [c]).startswith(color)
    assert 'rank unknown' in today_rows.recipe_band(row, None, [c])
    assert today_rows.band_colour(20, [1, 1, 1, 40]) == 'no reliable skill-ups'


def test_failed_signal_read_is_explicit_and_character_failure_keeps_plan(browser, monkeypatch):
    monkeypatch.setattr('brownstone.flood_signals.signals', Mock(side_effect=ValueError('unreadable signals')))
    result = request(browser)
    assert result.status_code == 503 and 'unreadable signals' in result.json()['detail']
    monkeypatch.setattr('brownstone.flood_signals.signals', lambda *a: {'rows': []})
    monkeypatch.setattr('brownstone.professions.latest_data', Mock(side_effect=ValueError('bad character')))
    result = request(browser).json()
    assert result['plan']['craft'] and any('bad character' in note for note in result['notes'])
