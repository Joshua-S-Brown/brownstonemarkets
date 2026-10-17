"""STORY-068: captured materials are valued, scoped and reserved without changing Board routes."""
from copy import deepcopy
from datetime import timedelta

import pytest
from test_today import NOW, catalog, output_catalog, plan

from brownstone import today_holdings
from brownstone.team_holdings import holdings
from brownstone.today import TODAY_VERSION, _batch, _candidates, _quote, apply_removals, craft_details
from brownstone.today_characters import project_recipes
from brownstone.today_session import plan_context, queue_line_text
from brownstone.today_settings import TodaySettings
from views.today_rows import material_card_rows, sell_row


def evidence(*rows, age=1, unknown_bank=False):
    units = [{'key': (item, None, 'base'), 'item_id': item, 'character': name, 'realm': 'realm',
              'faction': 'alliance', 'kind': place, 'units': count} for item, count, name, place in rows]
    captures = [{'character': name, 'realm': 'realm', 'faction': 'alliance', 'kind': kind,
                 'age_hours': age, 'unknown': False} for name, kind in {(u['character'], u['kind']) for u in units}]
    if unknown_bank:
        captures.append({'character': rows[0][2], 'realm': 'realm', 'faction': 'alliance', 'kind': 'bank',
                         'age_hours': None, 'unknown': True})
    return {}, {}, captures, units


def nested_catalog(yield_units=1):
    c = deepcopy(catalog())
    c['items_by_id'][4] = {**c['items_by_id'][1], 'item_id': 4, 'name': 'Bolt', 'role': 'intermediate'}
    c['recipes_by_id'][40] = {**c['recipes_by_id'][30], 'recipe_id': 40, 'output_item_id': 4,
                            'output_quantity': yield_units, 'inputs': [{'item_id': 1, 'quantity': 2 * yield_units}]}
    c['recipes_by_id'][30]['inputs'][0] = {'item_id': 4, 'quantity': 2}
    c['recipe_for_output'][4] = 40
    return c


def held(row, item):
    return sum(p['quantity'] for p in row['purchases'] if p['method'] == 'held' and p['item_id'] == item)


@pytest.mark.parametrize('nested', [False, True])
@pytest.mark.parametrize('count', [0, 1, 3, 7, 12])
@pytest.mark.parametrize('funds', [10, 30, 90, 1000])
def test_batch_matches_every_size_brute_force(nested, count, funds):
    """Reference search quotes every size, including whole-stack dips and held multi-yield breaks."""
    from test_today import MARKET, SNAPSHOT

    from brownstone.today import Ladder

    catalogs = [nested_catalog(2) if nested else catalog()]
    observations = {1: {'min_buyout': 10, 'market_value': 20}, 3: {'min_buyout': 150}}
    projection = project_recipes(catalogs, {}, None, False)
    rows, _, _, _ = _candidates(catalogs, observations, MARKET, SNAPSHOT, NOW, 24, .05, projection, None, {})
    row = rows[0]
    remaining = {4 if nested else 1: count, 1: count, 2: count}
    ladders = {1: Ladder([(2, 20, 10), (7, 140, 20), (40, 2000, 50)])}
    settings = TodaySettings(funds, 1, 'fixed', max_crafts=13)
    feasible = []
    for size in range(1, settings.max_crafts + 1):
        quote = _quote(row['shopping_choices'], size, ladders, {}, remaining, row)
        if quote is not None and today_holdings.gold_cost(quote) <= funds:
            feasible.append((row['net_revenue_copper'] * size - sum(q['cost_copper'] for q in quote), -size))
    actual, _ = _batch(row, settings, ladders, {}, funds, remaining)
    if feasible:
        profit, negative_size = max(feasible)
        assert (actual['batch_size'], actual['batch_profit_copper']) == (-negative_size, profit)
    else:
        assert actual is None


def test_leaf_reduces_gold_but_held_value_counts_in_profit():
    settings = TodaySettings(10, 1, 'fixed', max_crafts=1)
    assert not plan(settings)['craft']
    result = plan(settings, holdings_data=evidence((1, 2, 'Basilly', 'bags')))
    row = result['craft'][0]
    assert held(row, 1) == 2
    assert (row['gold_cost_copper'], row['batch_cost_copper'], row['batch_profit_copper']) == (10, 28, 162)
    assert result['shopping_total_copper'] == result['queue']['gold_needed_copper'] == 10
    assert [r['item_id'] for r in result['buy']] == [2]
    assert result['sell'][0]['undercut_batch_profit_copper'] == 161
    assert material_card_rows(craft_details(row)['materials'])[0]['Cost'] == 'worth 18c if sold'


@pytest.mark.parametrize('yield_units,count,used,crafts,leaf', [(1, 2, 2, 0, 0), (2, 1, 0, 1, 4),
                                                             (2, 3, 2, 0, 0)])
def test_intermediate_replaces_subtree_in_whole_crafts(yield_units, count, used, crafts, leaf):
    result = plan(TodaySettings(1000, 1, 'fixed', max_crafts=1), catalogs=[nested_catalog(yield_units)],
                  holdings_data=evidence((4, count, 'Basilly', 'bank'), (1, 1, 'Basilly', 'bags')))
    row = result['craft'][0]
    assert held(row, 4) == used
    assert sum(s['crafts'] for s in craft_details(row)['intermediate_steps']) == crafts
    assert sum(p['quantity'] for p in row['purchases'] if p['item_id'] == 1) == leaf
    assert row['batch_cost_copper'] > 0
    bolt_lines = [q for q in result['queue']['lines'] if q['stage'] == 'craft' and q['recipe_id'] == 40]
    assert len(bolt_lines) == bool(crafts)


def test_nested_parent_before_children_and_shared_branches():
    c = nested_catalog()
    c['items_by_id'][5] = {**c['items_by_id'][4], 'item_id': 5, 'name': 'Inner'}
    c['recipes_by_id'][50] = {**c['recipes_by_id'][40], 'recipe_id': 50, 'output_item_id': 5}
    c['recipes_by_id'][40]['inputs'] = [{'item_id': 5, 'quantity': 2}]
    c['recipe_for_output'][5] = 50
    result = plan(TodaySettings(1000, 1, 'fixed', max_crafts=1), catalogs=[c],
                  holdings_data=evidence((4, 1, 'B', 'bags'), (5, 1, 'B', 'bank'), (1, 2, 'B', 'bags')))
    row = result['craft'][0]
    assert [held(row, i) for i in (4, 5, 1)] == [1, 1, 2]
    assert [(s['quantity'], s['crafts']) for s in craft_details(row)['intermediate_steps']] == [(1, 1), (1, 1)]
    assert result['queue']['gold_needed_copper'] == 10


def test_shared_plan_order_and_adjusted_batch_re_reserve():
    args = dict(catalogs=[catalog(), output_catalog(4, 'second')],
                observations={1: {'min_buyout': 10}, 3: {'min_buyout': 200}, 4: {'min_buyout': 100}},
                holdings_data=evidence((1, 4, 'Basilly', 'bags')))
    settings = TodaySettings(1000, 1, 'fixed', max_crafts=2)
    result = plan(settings, **args)
    by_order = sorted(result['craft'], key=lambda r: r['plan_order'])
    assert [held(r, 1) for r in by_order] == [4, 0]
    choices = [{'catalog_id': r['catalog_id'], 'recipe_id': r['recipe_id'], 'batch_size': 1} for r in by_order]
    adjusted = plan(settings, choices=choices, refill=False, **args)
    assert [held(r, 1) for r in sorted(adjusted['craft'], key=lambda r: r['plan_order'])] == [2, 2]
    assert adjusted['queue']['gold_needed_copper'] == 20
    assert not adjusted['dropped_choices']


def test_selected_character_vs_team():
    e = evidence((1, 2, 'A', 'bags'), (1, 8, 'B', 'bank'))
    key = ('A', 'realm', 'alliance')
    from test_today_characters import state
    data = {key: state(learned=True)}
    own = plan(TodaySettings(1000, 1, 'fixed', max_crafts=2, character=key),
               character_data=data, holdings_data=e)
    team = plan(TodaySettings(1000, 1, 'fixed', max_crafts=2), character_data=data, holdings_data=e)
    assert held(own['craft'][0], 1) == 2
    assert held(team['craft'][0], 1) == 4
    assert [c['character'] for c in own['holdings_captures']] == ['A']


def test_stock_identity_variants_unresolved_unknown_bank_stale_reason():
    key = ('Basilly', 'realm', 'alliance')
    record = {'snapshot_id': 'bags', 'captured_at': int((NOW - timedelta(hours=30)).timestamp()),
              'kind': 'bags', 'slots': [
                  {'item_id': 1, 'count': 2, 'item_link': '|Hitem:1::::::::6:1482:::::::::|h[Cloth]|h'},
                  {'item_id': 1, 'count': 99, 'item_link': '|Hitem:1::::::123::6:1482:::::::::|h[Variant]|h'},
                  {'item_id': 1, 'count': 99}], 'containers': [{'container_id': 0, 'size': 16}]}
    e = holdings({key: {'bags': (record, 'mac'), 'observations': [(record, 'mac')]}}, NOW)
    totals, captures, units = today_holdings.scoped(e, None)
    assert totals == {1: 2}
    assert len(units) == 1
    assert next(c for c in captures if c['kind'] == 'bank')['unknown']
    old = plan(TodaySettings(1000, 1, 'fixed', max_crafts=1), holdings_data=e)
    fresh = plan(TodaySettings(1000, 1, 'fixed', max_crafts=1),
                 holdings_data=evidence((1, 2, 'Basilly', 'bags')))
    assert old['craft'][0]['confidence'] == fresh['craft'][0]['confidence']
    assert 'held count from a stale capture' in old['craft'][0]['confidence_reasons']
    assert old['holdings_captures'][0]['age_hours'] == 30


def test_missing_sell_price_uses_route_cost_never_free():
    result = plan(TodaySettings(1000, 1, 'fixed', max_crafts=1),
                  holdings_data=evidence((2, 1, 'Basilly', 'bank')))
    purchase = next(p for p in result['craft'][0]['purchases'] if p['method'] == 'held')
    assert purchase['cost_copper'] == 10
    assert result['queue']['gold_needed_copper'] == 20


def test_take_mail_allocation_order_and_rebuilt_queue(monkeypatch):
    import brownstone.today as today
    original = today._candidates
    def makers(*args):
        rows, hidden, warnings, board = original(*args)
        for row in rows:
            row['made_by'] = 'Arille'
        return rows, hidden, warnings, board
    monkeypatch.setattr(today, '_candidates', makers)
    result = plan(TodaySettings(1000, 1, 'fixed', max_crafts=3), holdings_data=evidence(
        (1, 1, 'C', 'bags'), (1, 2, 'Basilly', 'bank'), (1, 1, 'Arille', 'bank'),
        (1, 1, 'Basilly', 'bags'), (1, 1, 'Arille', 'bags')))
    take = [q for q in result['queue']['lines'] if q['stage'] == 'take']
    assert [(q['character'], q['kind']) for q in take] == [
        ('Arille', 'bank'), ('Basilly', 'bank')]
    mail = [queue_line_text(q) for q in result['queue']['lines'] if q['stage'] == 'mail']
    assert mail[:2] == ['Basilly: mail 1 Fixture 1 to Arille, for Fixture 3',
                       'Basilly: mail 2 Fixture 1 to Arille, for Fixture 3']
    assert queue_line_text(take[1]) == (
        'Basilly: take 2 Fixture 1 out of the bank, for Fixture 3, then mail them to Arille')
    assert 'postage is unconfirmed' in result['queue']['mail_note']
    before = deepcopy(result['queue'])
    apply_removals(result, {3: {'pairs': 1, 'units': 1}})
    assert result['queue']['lines'][:len(take) + len(mail)] == before['lines'][:len(take) + len(mail)]
    assert result['queue']['gold_needed_copper'] == before['gold_needed_copper']


def test_held_outputs_separate_value_without_profit_credit():
    settings = TodaySettings(1000, 1, 'fixed', max_crafts=1)
    baseline = plan(settings)
    result = plan(settings, holdings_data=evidence((3, 2, 'Basilly', 'bank')))
    sell = result['sell'][0]
    assert sell['held_value_copper'] == 378
    assert sell_row(sell)['Held by'] == 'Basilly (bank): 2'
    assert sell_row(sell)['Held units'] == 2
    assert 'post 1 crafted + 2 held' in queue_line_text(result['queue']['lines'][-1])
    assert result['queue']['expected_profit_copper'] == baseline['queue']['expected_profit_copper']
    assert result['craft'][0]['batch_profit_copper'] == baseline['craft'][0]['batch_profit_copper']


def test_no_holdings_exact_plan_and_version():
    baseline = plan()
    assert plan(holdings_data=({}, {}, [], [])) == baseline
    assert baseline['today_version'] == TODAY_VERSION == 14


def test_holdings_context_resets_choices_without_clock_age():
    args = dict(catalogs=[], market={}, snapshot={}, settings=TodaySettings(), max_age_hours=24, auction_cut=.05)
    assert plan_context(args) != plan_context({**args, 'holdings_data': evidence((1, 2, 'B', 'bags'))})


def test_no_holdings_matches_pre_story_golden():
    import json
    from pathlib import Path

    before = json.loads((Path(__file__).parent / 'fixtures/today_no_holdings.json').read_text())
    current = json.loads(json.dumps(plan(), default=str))
    def strip_version(value):
        if isinstance(value, dict):
            return {k: strip_version(v) for k, v in value.items()
                    if k not in ('today_version', 'deposit_copper', 'post_duration_hours', 'deposits_to_post_copper',
                                  'your_sales', 'max_expiries', 'unplanned')}
        if isinstance(value, list):
            return [strip_version(v) for v in value]
        return value
    assert strip_version(current) == strip_version(before)


def test_context_handles_exact_identity_keys_and_ignores_age():
    args = dict(catalogs=[], market={}, snapshot={}, settings=TodaySettings(), max_age_hours=24, auction_cut=.05)
    e = evidence((1, 2, 'B', 'bags'))
    e = ({(1, None, 'base'): 2}, {(1, None, 'base'): 'Cloth'}, e[2], e[3])
    aged = deepcopy(e)
    aged[2][0]['age_hours'] += 1
    assert plan_context({**args, 'holdings_data': e}) == plan_context({**args, 'holdings_data': aged})


def test_held_leaf_does_not_change_board_route_to_buy_intermediate():
    result = plan(TodaySettings(1000, 1, 'fixed', max_crafts=1), catalogs=[nested_catalog()],
                  observations={1: {'min_buyout': 20}, 4: {'min_buyout': 1}, 3: {'min_buyout': 200}},
                  listings={4: [(2, 2, 1)]}, holdings_data=evidence((1, 100, 'B', 'bags')))
    row = result['craft'][0]
    assert not row['intermediate_steps']
    assert row['choices'][0]['method'] == 'buy'
    assert held(row, 1) == 0
    assert {p['item_id'] for p in row['purchases']} == {2, 4}


def test_held_outputs_never_take_materials_reserved_by_later_craft():
    c = nested_catalog()
    second = output_catalog(4, 'second')
    result = plan(TodaySettings(1000, 1, 'fixed', max_crafts=1), catalogs=[c, second],
                  observations={1: {'min_buyout': 10}, 3: {'min_buyout': 1000}, 4: {'min_buyout': 100}},
                  holdings_data=evidence((4, 2, 'B', 'bags')))
    assert sum(u['units'] for row in result['craft'] for u in row.get('held_outputs', [])) == 0
    assert sum(held(row, 4) for row in result['craft']) == 2


def test_stale_held_output_reason_and_inputs_not_mutated():
    e = evidence((3, 2, 'B', 'bags'), age=30)
    original = deepcopy(e)
    result = plan(holdings_data=e)
    assert e == original
    assert 'held count from a stale capture' in result['craft'][0]['confidence_reasons']
    assert result['craft'][0]['confidence'] == plan()['craft'][0]['confidence']


def test_repeated_take_lines_group_by_character_place():
    result = plan(TodaySettings(1000, 1, 'fixed', max_crafts=1),
                  catalogs=[catalog(), output_catalog(4, 'second')],
                  observations={1: {'min_buyout': 10}, 3: {'min_buyout': 200}, 4: {'min_buyout': 100}},
                  holdings_data=evidence((1, 4, 'B', 'bank')))
    take = [q for q in result['queue']['lines'] if q['stage'] == 'take']
    assert len(take) == 1 and take[0]['units'] == 4


def test_held_materials_do_not_need_or_reserve_listing_depth():
    result = plan(TodaySettings(10, 1, 'fixed', max_crafts=1), listings={},
                  metrics={1: {'units': 10}, 3: {'min_buyout': 200, 'listings': 5, 'units': 10,
                                               'largest_stack_units': 1}},
                  holdings_data=evidence((1, 2, 'B', 'bags')))
    row = result['craft'][0]
    assert row['confidence'] == 'High'
    assert result['queue']['gold_needed_copper'] == 10


@pytest.mark.parametrize('count,used', [(2, 0), (4, 4)])
def test_held_parent_leaves_whole_multi_yield_child_crafts(count, used):
    c = nested_catalog(2)
    c['recipes_by_id'][30]['inputs'][0]['quantity'] = 4
    c['items_by_id'][5] = {**c['items_by_id'][4], 'item_id': 5, 'name': 'Inner'}
    c['recipes_by_id'][50] = {**c['recipes_by_id'][40], 'recipe_id': 50, 'output_item_id': 5}
    c['recipes_by_id'][40]['inputs'] = [{'item_id': 5, 'quantity': 1}]
    c['recipe_for_output'][5] = 50
    # Four parent units need two parent crafts and one child craft. Holding only two
    # parents would leave half a child craft; keep the original whole-craft route.
    result = plan(TodaySettings(1000, 1, 'fixed', max_crafts=1), catalogs=[c],
                  holdings_data=evidence((4, count, 'B', 'bags')))
    row = result['craft'][0]
    assert held(row, 4) == used
    steps = craft_details(row)['intermediate_steps']
    assert [(s['quantity'], s['crafts']) for s in steps] == ([(4, 2), (2, 1)] if not used else [])


def test_unrelated_holdings_keep_the_pruned_plan(monkeypatch):
    import brownstone.today as today

    peaks = []
    original = today._profit_peaks
    monkeypatch.setattr(today, '_profit_peaks', lambda *a: peaks.append(a[-1]) or original(*a))
    result = plan(holdings_data=evidence((99, 5, 'B', 'bags')))
    assert peaks and all(h is None for h in peaks)  # no row uses item 99: breakpoint search, not every size
    fields = ('batch_size', 'batch_cost_copper', 'batch_profit_copper', 'purchases', 'limiting_factor')
    assert [{k: r[k] for k in fields} for r in result['craft']] == [{k: r[k] for k in fields} for r in plan()['craft']]
    assert 'reserved_steps' not in result['craft'][0]


def test_held_input_of_cross_profession_step_goes_to_that_maker():
    c = {'recipes_by_id': {30: {'inputs': [{'item_id': 4, 'quantity': 2}, {'item_id': 2, 'quantity': 1}]},
                           50: {'inputs': [{'item_id': 5, 'quantity': 1}]},
                           60: {'inputs': [{'item_id': 2, 'quantity': 1}]}}}
    row = {'recipe_id': 30, 'catalog_id': 'smithing',
           'intermediate_steps': [{'recipe_id': 50, 'catalog_id': 'smelting', 'made_by': 'Miner'},
                                  {'recipe_id': 60, 'catalog_id': 'smelting', 'made_by': 'Miner'}]}
    # Ore only feeds the miner's smelt; item 2 is also used by the smith, so it stays with the crafter.
    assert today_holdings.consumers(c, row) == {5: 'Miner'}
    assert today_holdings.consumers(c, {**row, 'intermediate_steps': [
        {'recipe_id': 50, 'catalog_id': 'smithing', 'made_by': 'Miner'}]}) == {}
    crafts = [{'plan_order': 0, 'made_by': 'Smith', 'holding_consumers': {5: 'Miner'}, 'output_item_id': 3,
               'purchases': [{'method': 'held', 'item_id': 5, 'quantity': 3}], 'material_names': {5: 'Ore'},
               'confidence_reasons': [], 'catalog_id': 'smithing', 'recipe_id': 30, 'output_name': 'Sword'}]
    _, _, captures, units = evidence((5, 2, 'Smith', 'bags'), (5, 1, 'Miner', 'bags'))
    today_holdings.allocate(crafts, units, captures, 24)
    assert [(a['character'], a['units'], a['to']) for a in crafts[0]['held_allocations']] == [
        ('Miner', 1, 'Miner'), ('Smith', 2, 'Miner')]
    mail = [line for line in today_holdings.queue_lines(crafts) if line['stage'] == 'mail']
    assert [(m['character'], m['units'], m['to']) for m in mail] == [('Smith', 2, 'Miner')]
    assert queue_line_text(mail[0]) == 'Smith: mail 2 Ore to Miner, for Sword'


def test_capture_label_never_shows_a_missing_bank_as_empty():
    from views.today_rows import capture_label

    _, _, captures, _ = evidence((1, 2, 'B', 'bags'), age=2.25, unknown_bank=True)
    assert sorted(map(capture_label, captures)) == ['B · bags · 2.2 hours old', 'B · bank · bank not captured']
