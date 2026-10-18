"""Team's offline contracts, migrated native rule checks and cache boundaries."""
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from app_helpers import team_app
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_today_characters import CHARACTER

import api
from api import context, team
from brownstone import character_snapshots, hiring, team_view, today_loading, today_session
from brownstone.today_settings import TodaySettings


@pytest.fixture
def browser(tmp_path, monkeypatch):
    source, catalog, data = team_app(tmp_path, monkeypatch)
    monkeypatch.setattr(team, '_cache', {})
    server = FastAPI()
    api.install(server, tmp_path / 'dist', 'offline-token')
    with TestClient(server) as client:
        yield client, source, catalog, data


def get(browser, path='team', **params):
    return browser[0].get('/api/' + path, params={'source': browser[1]['source_id']} | params)


@pytest.mark.parametrize('training,profit,status,crafts', [
    (100, 30, 'crafts', 4), (100, 25, 'crafts', 4), (100, 0, 'never', None),
    (100, -1, 'never', None), (100, None, 'unknown', None), (0, 30, 'absent', None),
    (None, 30, 'absent', None)])
def test_payback_rounding_never_unknown_absent(training, profit, status, crafts):
    assert team_view.training_payback({'training_cost_copper': training, 'profit_copper': profit}) == {
        'status': status, 'crafts': crafts}


@pytest.mark.parametrize('skill,expected', [(186, True), (182, True), (393, True), (356, True),
                                         (197, False), (None, False)])
def test_gathering_uses_skill_id_not_title(skill, expected):
    assert team_view.gathering({'profession': 'Unrelated title', 'skill_id': skill}) is expected


def test_next_step_alternative_and_all_incomplete_decisions():
    best = {'learned_from': [6]}
    for group, kind in [({'note': 'unknown', 'best': best}, 'note'), ({'note': '', 'best': best}, 'best'),
                        ({'note': '', 'best': None}, 'none')]:
        assert team_view.next_step(group)['kind'] == kind
    assert team_view.alternative_kind(best) == 'learn'
    assert team_view.alternative_kind({'learned_from': [2]}) == 'hunt'
    assert team_view.alternative_kind(None) is None
    assert not team_view.all_incomplete([])
    assert team_view.all_incomplete([{'estimate': {'complete': False}}])
    assert not team_view.all_incomplete([{'estimate': {'complete': False}}, {'estimate': {'complete': True}}])


def test_roster_progression_matches_shared_build_and_window(browser):
    response = get(browser)
    assert response.status_code == 200, response.text
    result = response.json()
    assert len(result['roster']) == 2
    assert result['roster'][0]['card']['level'] == 5
    assert result['roster'][0]['card']['gold_copper'] == 255
    assert result['roster'][0]['card']['stale']
    assert result['all_incomplete']
    assert 'listings never sales' in result['hiring_labels']
    _, args = today_loading.load_today(browser[1], [browser[2]], TodaySettings(), browser[3], datetime.now(UTC))
    expected = team_view.team_results([browser[2]], browser[3], args, 25)
    groups = result['roster'][0]['progression']['professions']
    assert groups[0]['best']['name'] == expected[CHARACTER]['professions'][0]['best']['name']
    assert 'Recipe 32' not in [r['name'] for r in groups[0]['recipes']]
    later = get(browser, window=26).json()
    assert 'Recipe 32' in [r['name'] for r in later['roster'][0]['progression']['professions'][0]['recipes']]
    assert all(r['estimate']['steps'] for r in groups[0]['recipes'])
    assert get(browser, window=101).status_code == 422


def test_same_name_keys_outside_source_and_unknown_evidence(browser, monkeypatch):
    data = browser[3]
    twin = (CHARACTER[0], 'Other realm', 'Horde')
    data[twin] = deepcopy(data[CHARACTER])
    data[twin]['bags'] = {}
    data[twin]['history'] = []
    data[twin]['recipes'] = {}
    # Record endpoints receive exact identities; neither falls back to a name.
    one = get(browser, 'team/character', name=CHARACTER[0], realm=CHARACTER[1], faction=CHARACTER[2])
    two = get(browser, 'team/character', name=twin[0], realm=twin[1], faction=twin[2])
    assert one.status_code == two.status_code == 200
    assert one.json()['character'] != two.json()['character']
    assert one.json()['card']['level'] == 5
    assert two.json()['card']['level'] is None and two.json()['card']['gold_copper'] is None
    assert not two.json()['card']['stale'] and not two.json()['card']['history']
    assert not two.json()['holdings']['items']
    assert get(browser, 'team/character', name=twin[0], realm='Elsewhere', faction=twin[2]).status_code == 404
    assert browser[0].get('/api/team', params={'source': 'outside'}).status_code == 404


def test_learning_order_best_alternative_known_counts_and_unknown(browser):
    catalog = browser[2]
    catalog['recipes_by_id'][31]['learned_from'] = [2]
    catalog['recipes_by_id'][33]['learned_from'] = [6]
    record = get(browser, 'team/character', name=CHARACTER[0], realm=CHARACTER[1], faction=CHARACTER[2]).json()
    group = record['progression']['professions'][0]
    assert [r['name'] for r in group['recipes']] == ['Recipe 31', 'Recipe 33']
    assert [r['learn_from'] for r in group['recipes']] == ['drop', 'trainer']
    assert group['best']['name'] == 'Recipe 33' and group['alternative_kind'] == 'hunt'
    assert record['card']['professions'][0]['recipe_source'] == 'window list'
    assert record['evidence']['machine'] == 'fixture-machine'
    assert record['evidence']['skills_status']
    assert record['evidence']['source_id'] == browser[1]['source_id']


def test_one_board_per_window_lazy_hire_detail_and_invalidation(browser, monkeypatch):
    board_calls, detail_calls = [], []
    original_board, original_detail = team_view.team_board, hiring.detail

    def board(*args):
        board_calls.append(1)
        return original_board(*args)

    def detail(ctx, row):
        detail_calls.append(row['profession'])
        return original_detail(ctx, row)

    monkeypatch.setattr(team_view, 'team_board', board)
    monkeypatch.setattr(hiring, 'detail', detail)
    first = get(browser).json()
    assert get(browser).json() == first
    assert detail_calls == [] and len(board_calls) == 1
    detail_result = get(browser, 'team/hire/tailoring')
    assert detail_result.status_code == 200, detail_result.text
    assert get(browser, 'team/hire/tailoring').json() == detail_result.json()
    assert detail_calls == ['tailoring'] and len(board_calls) == 1
    assert detail_result.json()['tiers'][0]['estimate']['steps'][0]['cost_copper'] == 150
    assert 'tier fees not included' in detail_result.json()['tiers'][0]['tier_fees']
    assert detail_result.json()['tiers'][-1]['required_level'] == 35
    get(browser, window=30)
    assert len(board_calls) == 2
    get(browser, 'team/hire/tailoring')
    assert len(detail_calls) == 1
    assert get(browser, 'team/hire/unknown').status_code == 404
    original_inputs = context._inputs
    monkeypatch.setattr(context, '_inputs', lambda *args: (*original_inputs(*args), 'changed-config'))
    get(browser)
    assert len(board_calls) == 3
    path = browser[1]['data_dir'] / 'brownstone.duckdb'
    path.touch()
    get(browser)
    assert len(board_calls) == 4
    current = datetime.now(UTC)

    class Clock:
        @staticmethod
        def now(tz):
            return current + timedelta(hours=2)

    monkeypatch.setattr(team, 'datetime', Clock)
    get(browser)
    assert len(board_calls) == 5


def test_no_scan_roster_empty_team_and_read_failure(browser, monkeypatch):
    source = browser[1] | {'source_id': 'empty'}
    monkeypatch.setattr(context, 'resolve', lambda _: source)
    monkeypatch.setattr('brownstone.professions.latest_data', lambda _: browser[3])
    result = get(browser).json()
    assert len(result['roster']) == 2
    assert not result['hires'] and 'No snapshot' in result['notes'][0]
    monkeypatch.setattr('api.ledger.cached', lambda _: dict(gold=dict(totals=[dict(
        character=CHARACTER, day=datetime.now(UTC).date().isoformat(), category='other',
        in_copper=120, out_copper=20)])))
    next_record = browser[0].post('/api/team/character/next', params={'source': 'empty'},
                                  headers={'X-Brownstone-Token': 'offline-token'},
                                  json=dict(character=CHARACTER))
    assert next_record.status_code == 200, next_record.text
    assert next_record.json()['stops'] == [] and next_record.json()['gold']['net_copper'] == 100
    monkeypatch.setattr('brownstone.professions.latest_data', lambda _: {})
    team._cache.clear()
    assert not get(browser).json()['roster']

    def broken(_):
        raise OSError('fixture unreadable')

    monkeypatch.setattr('brownstone.professions.latest_data', broken)
    team._cache.clear()
    assert 'fixture unreadable' in get(browser).json()['notes'][0]


def test_hiring_scope_error_and_no_character_hiring(browser, monkeypatch):
    monkeypatch.setattr('brownstone.professions.latest_data', lambda _: {})
    result = get(browser).json()
    assert result['hires'] and not result['roster'] and not result['comparisons']
    assert all(not r['holders'] for r in result['hires'])

    def broken(**kwargs):
        raise ValueError('fixture scope refusal')

    monkeypatch.setattr(hiring, 'prepare', broken)
    team._cache.clear()
    assert 'fixture scope refusal' in get(browser).json()['notes'][0]


def test_purchase_stop_keeps_two_full_crafter_keys():
    one, two = ('Maker', 'A', 'Alliance'), ('Maker', 'B', 'Horde')
    crafts = [dict(made_by='Maker', made_by_key=c, purchases=[{'item_id': 1, 'method': 'buy'}]) for c in (one, two)]
    line = dict(stage='auction house', item_id=1, name='Cloth', purchased_units=2,
                highest_unit_copper=10, cost_copper=20)
    stops = today_session.route_stops({'lines': [line]}, crafts, {one: {}, two: {}})
    assert stops[0]['characters'] == [one, two]
    # An ambiguous label alone cannot open either character.
    assert today_session.route_identities({'stage': 'craft', 'made_by': 'Maker'}, [], {one: {}, two: {}}) == []


def test_holdings_exact_variants_capture_partial_and_unknown_bank(browser, monkeypatch):
    now = int(datetime.now(UTC).timestamp())
    record = dict(snapshot_id='bags-one', captured_at=now, kind='bags', containers=[{'container_id': 0, 'size': None}],
                  slots=[{'container_id': 0, 'slot': 1, 'item_id': 10, 'count': 2,
                          'item_link': '|cffffffff|Hitem:10:0:0:0:0:0:1:0:0:0:0:0:0|h[Monkey robe]|h|r'},
                         {'container_id': 0, 'slot': 2, 'item_id': 10, 'count': 3,
                          'item_link': '|cffffffff|Hitem:10:0:0:0:0:0:2:0:0:0:0:0:0|h[Bear robe]|h|r'}])
    monkeypatch.setattr('brownstone.character_snapshots.latest_data', lambda _: {
        CHARACTER: {'bags': (record, 'machine'), 'observations': [(record, 'machine')]}})
    result = get(browser, 'team/character', name=CHARACTER[0], realm=CHARACTER[1], faction=CHARACTER[2]).json()
    assert len(result['holdings']['items']) == 2
    assert [r['units'] for r in result['holdings']['items']] == [2, 3]
    assert len({r['variant_id'] for r in result['holdings']['items']}) == 2
    captures = result['holdings']['captures']
    assert captures[0]['partial'] and captures[0]['snapshot_id'] == 'bags-one'
    assert captures[1]['unknown'] and captures[1]['age_hours'] is None


def test_progression_failures_are_explained_and_shared_board_handles_absence(browser, monkeypatch):
    assert team_view.team_board([], {}, None) is None
    assert team_view.team_results([], {}, None, 25) == {}

    def broken(*args, **kwargs):
        raise ValueError('fixture broken routes')

    monkeypatch.setattr('brownstone.progression.team_board', broken)
    assert team_view.team_board([], {'present': {}}, dict.fromkeys(team_view.BOARD_KEYS)) is None
    monkeypatch.setattr(team_view, 'team_results', broken)
    response = get(browser)
    assert response.status_code == 503 and 'fixture broken routes' in response.json()['detail']


def test_hire_detail_reuses_any_window_and_holdings_failure_is_503(browser, monkeypatch):
    calls = []
    original = team_view.team_board
    monkeypatch.setattr(team_view, 'team_board', lambda *args: calls.append(1) or original(*args))
    assert get(browser, window=40).status_code == 200
    assert get(browser, 'team/hire/tailoring').status_code == 200
    assert len(calls) == 1  # No second build at the default window.
    name, realm, faction = get(browser, window=40).json()['roster'][0]['character']

    def broken(_):
        raise OSError('locked')

    monkeypatch.setattr('brownstone.character_snapshots.latest_data', broken)
    response = get(browser, 'team/character', name=name, realm=realm, faction=faction, window=40)
    assert response.status_code == 503 and 'Unable to read holdings' in response.text


def test_roster_best_action_uses_profit_completeness_cost_and_preserves_steps():
    def group(name, profit, complete, cost):
        return dict(profession=name, best=dict(profit_copper=profit,
                    estimate=dict(complete=complete, cost_copper=cost)))
    groups = [group("unknown", None, False, None), group("cheap", 10, True, 2),
              group("expensive", 10, True, 20), group("incomplete", 10, False, 1)]
    original = list(groups)
    assert team_view.roster_step(groups)["profession"] == "cheap"
    assert groups == original
    assert team_view.roster_step([group("profit", 20, False, None), *groups])["profession"] == "profit"
    assert team_view.roster_step([]) is None
    assert team_view.roster_step(groups[:1])["profession"] == "unknown"
    assert team_view.roster_step([dict(profession="Mining", best=None)])["profession"] == "Mining"


def test_character_holdings_action_order_exact_identity_and_cautious_values():
    from brownstone.crafting import basis_prices

    key = dict(character='Maker', realm='Realm', faction='Alliance')
    items = [dict(key=(i, None, 'base'), item_id=i, variant_state='base', kind='bags', units=2, **key)
             for i in range(1, 8)]
    items.append(items[0] | dict(variant_state='variant', key=(1, 'v1', 'variant')))
    allocation = items[0] | dict(to='Maker')
    craft = dict(recipe_id=10, catalog_id='catalog', held_allocations=[allocation], held_outputs=[])
    mail = dict(stage='mail', to='Other', purposes=[dict(name='Robe')], **items[0])
    stops = [dict(lines=[dict(evidence=mail), dict(evidence=mail | dict(item_id=2, key=(2, None, 'base')))]),
             dict(lines=[dict(evidence=dict(stage='craft', recipe_id=10, catalog_id='catalog'))])]
    _, prices = basis_prices({i: dict(min_buyout=100, market_value=70) for i in (1, 2, 3, 6)} |
                             {7: dict(min_buyout=0, market_value=0)}, 'cautious')
    captures = [dict(kind='bags', unknown=False, partial=False), dict(kind='bank', unknown=True, partial=False)]
    result = team_view.character_holdings(items, captures, dict(craft=[craft]), stops, prices,
                                          {i: 50 for i in (1, 2, 3, 4)} | {6: 100})
    assert [r['action'] for r in result['items']] == [
        'used in tonight’s plan (Route step 2)', 'mail to Other for Robe (Route step 1)',
        'sell', 'vendor', 'keep', 'vendor', 'keep', 'keep']
    assert result['items'][0]['unit_copper'] == 70 and result['items'][0]['value_copper'] == 140
    assert all(r['unit_copper'] is None and r['value_copper'] is None for r in result['items'] if
               r['item_id'] in (4, 5, 7) or r['variant_state'] != 'base')
    assert result['value_copper'] == 560 and result['unpriced'] == 4 and result['at_least']
    captures[1].update(unknown=False, partial=True)
    assert team_view.character_holdings([], captures, {}, [], {}, {})['at_least']
    posted = dict(characters=[tuple(key.values())], lines=[dict(evidence=dict(held_outputs=[items[0]]))])
    output = team_view.character_holdings([items[0]], captures, {}, [posted], {}, {})
    assert output['items'][0]['action'] == 'used in tonight’s plan (Route step 1)'
    craft['held_allocations'][0]['to'] = None
    unknown_maker = team_view.character_holdings([items[0]], captures, dict(craft=[craft]), stops, {}, {})
    assert unknown_maker['items'][0]['action'] == 'used in tonight’s plan (Route step 2)'
    captures[1]['partial'] = False
    assert not team_view.character_holdings([], captures, {}, [], {}, {})['at_least']
    # Another realm, location or variant of the same item ID never acquires a Route action.
    for changed in (dict(realm='Elsewhere'), dict(kind='bank'), dict(key=(1, 'v1', 'variant'))):
        row = team_view.character_holdings([items[0] | changed], captures, dict(craft=[craft]), stops, {}, {})
        assert row['items'][0]['action'] == 'keep'


def test_character_seven_utc_days_filter_existing_totals_and_unknown():
    from brownstone.ledger_view import day_bounds

    now = datetime(2026, 10, 17, 23, 59, tzinfo=UTC)
    rows = [dict(character=CHARACTER, day='2026-10-11', category=str(i), in_copper=i, out_copper=1)
            for i in range(5)]
    rows += [rows[0] | dict(day='2026-10-10', in_copper=1000),
             rows[0] | dict(day='2026-10-18', in_copper=2000),
             rows[0] | dict(character=('Other', *CHARACTER[1:]), in_copper=3000)]
    result = team_view.character_gold(dict(totals=rows), CHARACTER, day_bounds('7', now))
    assert (result['in_copper'], result['out_copper'], result['net_copper']) == (10, 5, 5)
    assert [r['category'] for r in result['categories']] == ['4', '3', '2']
    quiet = team_view.character_gold(dict(totals=rows[5:6]), CHARACTER, day_bounds('7', now))
    assert (quiet['in_copper'], quiet['net_copper'], quiet['categories']) == (0, 0, [])
    for evidence in (None, {}, dict(totals=rows[-1:])):
        assert team_view.character_gold(evidence, CHARACTER, day_bounds('7', now)) == dict(
            in_copper=None, out_copper=None, net_copper=None, categories=[])


def test_character_next_reuses_today_plan_numbering_settings_and_holdings_read(browser, monkeypatch):
    from api import today

    calls, reads = [], []
    build, latest = today.build, character_snapshots.latest_data

    def counted(*args):
        calls.append(1)
        return build(*args)

    def read(*args):
        reads.append(1)
        return latest(*args)

    monkeypatch.setattr(today, '_cache', {})
    monkeypatch.setattr(today, 'build', counted)
    monkeypatch.setattr(character_snapshots, 'latest_data', read)
    client, source, *_ = browser
    params, headers = {'source': source['source_id']}, {'X-Brownstone-Token': 'offline-token'}
    payload = client.post('/api/today/plan', params=params, headers=headers, json={'state': {}}).json()
    get(browser, 'team/character', name=CHARACTER[0], realm=CHARACTER[1], faction=CHARACTER[2])
    get(browser, 'ledger')  # Prime the independent Ledger cache before counting record reads.
    before = len(reads)
    response = client.post('/api/team/character/next', params=params, headers=headers,
                           json=dict(character=CHARACTER, state=payload['state']))
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['stops'] == [s | {'number': i} for i, s in enumerate(payload['stops'], 1)
                               if list(CHARACTER) in s['characters']]
    assert result['stops'] and len(calls) == 1 and len(reads) == before
    assert result['gold']['net_copper'] is None
    assert result['holdings']['at_least']
    # Changed choices use the same Today state rather than a second default plan.
    state = payload['state'] | dict(choices=[], refill=False)
    response = client.post('/api/team/character/next', params=params, headers=headers,
                           json=dict(character=CHARACTER, state=state)).json()
    changed = client.post('/api/today/plan', params=params, headers=headers, json=dict(state=state)).json()
    assert response['stops'] == [s | {'number': i} for i, s in enumerate(changed['stops'], 1)
                                 if list(CHARACTER) in s['characters']]
    assert len(calls) == 2
