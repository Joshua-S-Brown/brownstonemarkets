"""STORY-080: vendor top-ups retain whole-listing costs and scoped plan reservations, offline."""
from copy import deepcopy

import pytest
from test_today import catalog, output_catalog, plan
from test_today_holdings import evidence

from brownstone.today import (
    TODAY_VERSION,
    Ladder,
    _batch,
    _profit_peaks,
    _quote,
    apply_removals,
    craft_details,
    purchase_uses,
)
from brownstone.today_holdings import gold_cost
from brownstone.today_settings import TodaySettings
from views.today_rows import buy_row


def vendor_catalog():
    c = catalog()
    c['items_by_id'][1]['vendor_price_copper'] = 25
    return c


def topup_plan(**overrides):
    args = dict(catalogs=[vendor_catalog()], observations={1: {'min_buyout': 10},
                                                         3: {'min_buyout': 200}},
                listings={1: [(3, 30, 10), (3, 75, 25), (100, 3000, 30)]})
    return plan(**(args | overrides))


def test_ladder_price_bound_includes_equal_listings_and_reservations():
    ladder = Ladder([(3, 30, 10), (3, 75, 25), (10, 300, 30)])
    assert ladder.units_at_or_below(25) == 6
    assert ladder.units_at_or_below(25, 1) == 3
    assert ladder.units_at_or_below(25, 2) == ladder.units_at_or_below(25, 3) == 0
    assert ladder.units_at_or_below(9) == Ladder([]).units_at_or_below(25) == 0


def test_split_purchases_reconcile_buy_details_queue_removals_and_display():
    p = topup_plan()
    craft = p['craft'][0]
    materials = [r for r in craft['purchases'] if r['item_id'] == 1]
    assert [(r['method'], r['quantity'], r['purchased_units'], r['cost_copper'],
             r['highest_unit_copper'], r['end']) for r in materials] == [
                 ('buy', 6, 6, 105, 25, 2), ('vendor', 4, 4, 100, 25, 0)]
    assert (craft['batch_size'], craft['batch_cost_copper'], craft['batch_profit_copper']) == (5, 255, 695)
    assert craft['limiting_factor'] == 'per-item cap'
    assert p['today_version'] == TODAY_VERSION == 15
    assert gold_cost(craft['purchases']) == p['shopping_total_copper'] == 255
    assert sum(r['cost_copper'] for r in craft_details(craft)['materials']) == 255
    uses = purchase_uses(p['craft'])
    assert uses[(1, 'buy')] == {'Fixture 3': 6}
    assert uses[(1, 'vendor')] == {'Fixture 3': 4}
    rendered = [buy_row(r, {1: 'Cloth', 2: 'Thread'}) for r in p['buy'] if r['item_id'] == 1]
    assert {r['Route'] for r in rendered} == {'buy', 'vendor'}
    assert {r['Purchased units'] for r in rendered} == {6, 4}
    before = deepcopy(p['queue'])
    apply_removals(p, {3: {'pairs': 3, 'units': 0}})
    lines = [r for r in p['queue']['lines'] if r.get('item_id') == 1]
    assert [(r['stage'], r['quantity'], r['cost_copper']) for r in lines] == [
        ('auction house', 6, 105), ('vendor', 4, 100)]
    assert p['queue']['gold_needed_copper'] == before['gold_needed_copper'] == 255


def test_ladder_entirely_below_vendor_price_keeps_plan_and_board_costs():
    # Whole stacks cover the batch exactly, so no partly used stack competes with the vendor.
    args = dict(observations={1: {'min_buyout': 10}, 3: {'min_buyout': 200}},
                listings={1: [(3, 30, 10), (7, 140, 20)]})
    before = plan(**args)
    after = plan(catalogs=[vendor_catalog()], **args)
    for field in ('buy', 'sell', 'queue', 'shopping_total_copper', 'hidden'):
        assert before[field] == after[field]
    for field in ('batch_size', 'batch_cost_copper', 'batch_profit_copper', 'profit_by_basis',
                  'craft_cost_copper', 'limiting_factor'):
        assert before['craft'][0][field] == after['craft'][0][field]


def test_shared_material_reserves_cheap_listings_once_and_shares_vendor_route():
    second = output_catalog(4, 'second')
    second['items_by_id'][1]['vendor_price_copper'] = 25
    p = topup_plan(catalogs=[vendor_catalog(), second], observations={
        1: {'min_buyout': 10}, 3: {'min_buyout': 200}, 4: {'min_buyout': 180}})
    crafts = sorted(p['craft'], key=lambda r: r['plan_order'])
    assert [r['batch_size'] for r in crafts] == [5, 5]
    purchases = [[r for r in c['purchases'] if r['item_id'] == 1] for c in crafts]
    assert [r['method'] for r in purchases[0]] == ['buy', 'vendor']
    assert [(r['method'], r['quantity'], r['cost_copper']) for r in purchases[1]] == [('vendor', 10, 250)]
    merged = {(r['item_id'], r['method']): r for r in p['buy']}
    assert merged[(1, 'buy')]['purchased_units'] == 6
    assert (merged[(1, 'vendor')]['quantity'], merged[(1, 'vendor')]['cost_copper']) == (14, 350)
    assert p['shopping_total_copper'] == p['queue']['gold_needed_copper'] == 555


def test_holdings_cover_need_before_auction_and_vendor_and_reserve_across_crafts():
    second = output_catalog(4, 'second')
    second['items_by_id'][1]['vendor_price_copper'] = 25
    p = topup_plan(catalogs=[vendor_catalog(), second], holdings_data=evidence((1, 3, 'Basilly', 'bags')),
                   observations={1: {'min_buyout': 10}, 3: {'min_buyout': 200}, 4: {'min_buyout': 180}})
    first, second = sorted(p['craft'], key=lambda r: r['plan_order'])
    assert [(r['method'], r['quantity']) for r in first['purchases'] if r['item_id'] == 1] == [
        ('held', 3), ('buy', 6), ('vendor', 1)]
    assert [(r['method'], r['quantity']) for r in second['purchases'] if r['item_id'] == 1] == [('vendor', 10)]
    assert first['gold_cost_copper'] == 180
    assert first['batch_cost_copper'] == 207  # Three held units valued at 9c after the cut.
    assert p['shopping_total_copper'] == p['queue']['gold_needed_copper'] == 480
    assert sum(gold_cost(c['purchases']) for c in p['craft']) == 480


@pytest.mark.parametrize('listings', [{}, {1: [(100, 3000, 30)]}])
def test_missing_or_above_cap_listings_use_vendor_without_listing_limit(listings):
    p = topup_plan(listings=listings)
    craft = p['craft'][0]
    assert (craft['batch_size'], craft['batch_cost_copper'], craft['limiting_factor']) == (5, 300, 'per-item cap')
    assert all(r['method'] == 'vendor' for r in p['buy'])


def test_topup_still_stops_at_gold_and_whole_stacks_do_not_credit_surplus():
    p = topup_plan(settings=TodaySettings(195, 1, 'fixed', max_crafts=10))
    craft = p['craft'][0]
    assert (craft['batch_size'], craft['batch_cost_copper'], craft['limiting_factor']) == (4, 195, 'gold available')
    p = topup_plan(settings=TodaySettings(10000, 1, 'fixed', max_crafts=1))
    buy = next(r for r in p['buy'] if r['item_id'] == 1)
    assert (buy['quantity'], buy['purchased_units'], buy['cost_copper']) == (2, 3, 30)


def test_vendor_topup_profit_peaks_ignore_expensive_listings():
    choice = {'item_id': 1, 'method': 'buy', 'quantity': 2, 'unit_cost_copper': 10,
              'vendor_price_cap_copper': 25}
    ladders = {1: Ladder([(3, 30, 10), (3, 75, 25), (2, 60, 30), (2, 80, 40)])}
    assert _profit_peaks([choice], 10, ladders, {}) == [1, 2, 3, 4, 10]
    assert _profit_peaks([choice], 10, ladders, {1: 2}) == [1, 10]


@pytest.mark.parametrize(('quantity', 'expected'), [
    (1, [('vendor', 1, 1, 25, 0)]),
    (4, [('buy', 3, 3, 30, 1), ('vendor', 1, 1, 25, 0)]),
    (20, [('buy', 20, 23, 430, 2)]),
])
def test_partly_used_last_stack_is_bought_only_when_cheaper_than_the_vendor(quantity, expected):
    choice = {'item_id': 1, 'method': 'buy', 'quantity': 1, 'unit_cost_copper': 10,
              'vendor_price_cap_copper': 25}
    ladders = {1: Ladder([(3, 30, 10), (20, 400, 20)])}
    assert [(r['method'], r['quantity'], r['purchased_units'], r['cost_copper'], r['end'])
            for r in _quote([choice], quantity, ladders, {})] == expected


LADDERS = {
    'crossing': {1: Ladder([(3, 29, 10), (3, 75, 25), (100, 3000, 30)])},
    'deep stacks': {1: Ladder([(2, 10, 5), (20, 400, 20), (5, 125, 25)]), 2: Ladder([(7, 70, 10)])},
}


@pytest.mark.parametrize('funds', [20, 30, 105, 200, 1000])
@pytest.mark.parametrize('revenue', [15, 50, 100])
@pytest.mark.parametrize('quantity', [1, 2, 4])
@pytest.mark.parametrize('ladder', LADDERS)
def test_topup_batch_matches_exhaustive_profit_search(funds, revenue, quantity, ladder):
    choices = [{'item_id': 1, 'method': 'buy', 'quantity': quantity, 'unit_cost_copper': 10,
                'vendor_price_cap_copper': 25}]
    if ladder == 'deep stacks':
        choices.append({'item_id': 2, 'method': 'buy', 'quantity': 1, 'unit_cost_copper': 10,
                        'vendor_price_cap_copper': 12})
    row = {'shopping_choices': choices, 'net_revenue_copper': revenue}
    ladders = LADDERS[ladder]
    settings = TodaySettings(funds, 0, 'fixed', max_crafts=10)
    feasible = []
    for size in range(1, 11):
        purchases = _quote(choices, size, ladders, {})
        cost = gold_cost(purchases)
        if cost <= funds:
            feasible.append((revenue * size - cost, -size, cost))
    batch, _ = _batch(row, settings, ladders, {}, funds)
    if not feasible:
        assert batch is None
    else:
        profit, negative_size, cost = max(feasible)
        assert (batch['batch_size'], batch['batch_cost_copper'], batch['batch_profit_copper']) == (
            -negative_size, cost, profit)


def test_vendor_topup_still_stops_when_more_crafts_lower_profit():
    p = topup_plan(observations={1: {'min_buyout': 1}, 3: {'min_buyout': 40}},
                   listings={1: [(2, 2, 1), (100, 3000, 30)]})
    craft = p['craft'][0]
    assert (craft['batch_size'], craft['batch_cost_copper'], craft['batch_profit_copper']) == (1, 12, 26)
    assert craft['feasible_size'] == 5
    assert craft['limiting_factor'] == 'more crafts lower profit'


def test_already_vendor_route_is_unchanged_with_or_without_auction_depth():
    args = dict(catalogs=[vendor_catalog()], observations={1: {'min_buyout': 100}, 3: {'min_buyout': 200}})
    before = plan(**args, listings={1: [(2, 20, 10), (2, 60, 30)]})
    after = plan(**args, listings={})
    assert before == after
    assert all(r['method'] == 'vendor' for r in after['buy'])


def test_explicit_choice_requotes_split_purchases_and_keeps_feasible_bound():
    p = topup_plan(choices=[{'catalog_id': 'fixture', 'recipe_id': 30, 'batch_size': 4}], refill=False)
    craft = p['craft'][0]
    assert (craft['batch_size'], craft['batch_cost_copper'], craft['limiting_factor']) == (4, 195, 'chosen batch')
    assert [(r['method'], r['quantity']) for r in craft['purchases'] if r['item_id'] == 1] == [
        ('buy', 6), ('vendor', 2)]
    assert p['choice_limits'] == [{'catalog_id': 'fixture', 'recipe_id': 30, 'maximum': 5}]
