"""STORY-036: bundle evidence, manual vendor marks and sale ceilings, entirely offline."""
import copy
import tomllib
from pathlib import Path

import pytest
from test_recipe_import import extract, selection
from test_today import MARKET, NOW, SNAPSHOT, catalog, plan

from brownstone.action_board import rank_catalogs
from brownstone.crafting import evaluate_recipe, parse_recipe_catalog
from brownstone.recipe_catalogs import find_catalogs, parse_catalogs
from brownstone.recipe_import import _catalog_item, build_catalog, dumps_catalog
from views.today_rows import craft_row, sell_row, vendor_cap_label

ROOT = Path(__file__).resolve().parents[1]


def test_bundle_division_and_confirmed_note_survive_regeneration():
    note = {'item_id': 2320, 'vendor': True, 'vendor_quantity': 5, 'vendor_verified': True,
            'vendor_note': '2026-10-15 beta report, entry fixture, NPC 340, Stormwind City'}
    selected = selection(items=[note])
    first = build_catalog(extract(), selected)
    second = build_catalog(extract(), selected)
    assert dumps_catalog(first) == dumps_catalog(second)
    loaded = parse_recipe_catalog(tomllib.loads(dumps_catalog(second)))
    item = loaded['items_by_id'][2320]
    assert item['vendor_price_copper'] == 2
    assert item['vendor_bundle_price_copper'] == 10
    assert item['vendor_quantity'] == 5
    assert item['vendor_verified'] is True
    assert item['vendor_note'] == note['vendor_note']


@pytest.mark.parametrize('quantity', [3, 0, -1, True, 1.5])
def test_inexact_or_invalid_bundle_refused(quantity):
    with pytest.raises(ValueError, match='vendor_quantity'):
        build_catalog(extract(), selection(items=[{'item_id': 2320, 'vendor': True,
                                                  'vendor_quantity': quantity}]))


@pytest.mark.parametrize('field,value', [('vendor_quantity', 0), ('vendor_quantity', True),
                                         ('vendor_bundle_price_copper', 49)])
def test_loader_validates_bundle_evidence(field, value):
    raw = tomllib.loads(dumps_catalog(build_catalog(extract(), selection())))
    item = next(i for i in raw['items'] if i['item_id'] == 2320)
    item[field] = value
    with pytest.raises(ValueError, match='[Vv]endor'):
        parse_recipe_catalog(raw)


def test_page_buyprice_alone_never_marks_new_or_limited_stock():
    page = extract()
    assert page['items']['2320']['buyprice'] > 0
    assert 'vendor_price_copper' not in _catalog_item(page, 2320, 'material', {})


def test_confirmed_new_marks_and_limited_stock_selections():
    catalogs, errors = parse_catalogs(find_catalogs(ROOT / 'config'))
    assert not errors
    limited = {4357, 4364, 4382, 6533, 10938, 2447, 785, 2449}
    new = {'Coal': 500, 'Elemental Flux': 150000, 'Star Wood': 4500, 'Thick Logs': 200000,
           'Mote of Magic': 10, 'Copper Rod': 124, 'Demonic Figurine': 10000, 'Imbued Vial': 6000}
    seen = set()
    for c in catalogs:
        if c['game_version'] != 'forever':
            continue
        for item in c['items_by_id'].values():
            if item['item_id'] in limited:
                assert 'vendor_price_copper' not in item
            if item['name'] in new:
                seen.add(item['name'])
                assert item['vendor_verified'] is True
                assert item['vendor_price_copper'] == new[item['name']]
                assert 'unlimited stock' in item['vendor_note']
                assert 'vendor NPC' in item['vendor_note']
    assert seen == set(new)


def test_crafted_vendor_output_sale_post_and_labels_are_capped():
    c = catalog()
    c['items_by_id'][3]['vendor_price_copper'] = 124
    p = plan(catalogs=[c])
    row, sell = p['craft'][0], p['sell'][0]
    assert row['sale_price_copper'] == sell['undercut_copper'] == 124
    assert row['profit_by_basis'] == {'cautious': 67, 'listed': 87}
    assert row['batch_profit_copper'] == sell['undercut_batch_profit_copper']
    assert vendor_cap_label(row) == vendor_cap_label(sell) == 'capped at vendor price 1s 24c'
    assert craft_row(row, sell)['Vendor ceiling'] == sell_row(sell)['Vendor ceiling'] == vendor_cap_label(row)
    assert c['items_by_id'][3]['role'] == 'finished'
    assert c['recipes_by_id'][30]['inputs'][0]['quantity'] == 2
    board = rank_catalogs([c], {1: {'min_buyout': 20}, 3: {'min_buyout': 200}},
                          MARKET, SNAPSHOT, now=NOW)
    assert board['rows'][0]['sale_price_copper'] == 124


def test_missing_zero_and_lower_sale_prices_are_not_raised_by_ceiling():
    c = catalog()
    c['items_by_id'][3]['vendor_price_copper'] = 124
    for sale, expected in [(None, None), (0, None), (100, 100)]:
        result = evaluate_recipe(c, 30, {1: 20}, sale_prices={3: sale})
        assert result['sale_price_copper'] == expected


def test_buy_never_above_vendor_ceiling_including_deeper_listings():
    c = catalog()
    c['items_by_id'][1]['vendor_price_copper'] = 25
    p = plan(catalogs=[c], observations={1: {'min_buyout': 10}, 3: {'min_buyout': 200}},
             listings={1: [(2, 20, 10), (2, 60, 30)]})
    assert p['craft']
    assert all(r['highest_unit_copper'] <= 25 for r in p['buy'] if r['item_id'] == 1)
    p = plan(catalogs=[c], observations={1: {'min_buyout': 100}, 3: {'min_buyout': 200}})
    purchase = next(r for r in p['buy'] if r['item_id'] == 1)
    assert purchase['method'] == 'vendor'
    assert purchase['highest_unit_copper'] == 25


def test_outputs_without_vendor_prices_unchanged():
    c = catalog()
    before = plan(catalogs=[c])
    after = plan(catalogs=[copy.deepcopy(c)])
    assert before == after
    assert before['craft'][0]['sale_price_copper'] == 200
    assert before['sell'][0]['undercut_copper'] == 199
    assert vendor_cap_label(before['craft'][0]) == ''


def test_default_bundle_quantity_and_multi_output_recipe():
    generated = build_catalog(extract(), selection())
    item = next(i for i in generated['items'] if i['item_id'] == 2320)
    assert item['vendor_quantity'] == 1
    assert item['vendor_bundle_price_copper'] == item['vendor_price_copper'] == 10
    c = catalog()
    c['recipes_by_id'][30]['output_quantity'] = 3
    c['items_by_id'][3]['vendor_price_copper'] = 10
    result = evaluate_recipe(c, 30, {1: 20, 3: 200})
    assert result['net_revenue_copper'] == 28
    assert result['profit_copper'] == -22


def test_all_forever_bundles_confirmed_and_routes_consistent():
    from brownstone.recipe_graph import RecipeGraph

    catalogs, _ = parse_catalogs(find_catalogs(ROOT / 'config'))
    forever = [c for c in catalogs if c['game_version'] == 'forever']
    bundles = {'Empty Vial', 'Leaded Vial', 'Crystal Vial', 'Mild Spices', 'Shiny Red Apple',
               'Refreshing Spring Water', 'Ice Cold Milk', 'Melon Juice', 'Sweet Nectar',
               'Moonberry Juice', 'Morning Glory Dew', 'Imbued Vial'}
    seen = set()
    for c in forever:
        for item in c['items_by_id'].values():
            if item['name'] in bundles:
                seen.add(item['name'])
                assert item['vendor_quantity'] == 5
                assert item['vendor_bundle_price_copper'] == item['vendor_price_copper'] * 5
                assert item['vendor_verified'] is True
    assert seen == bundles
    assert not RecipeGraph(forever, {}, forever[0]).warnings
    enchanting = next(c for c in forever if c['profession'] == 'enchanting')
    assert enchanting['items_by_id'][247786]['role'] == 'intermediate'
    assert enchanting['recipes_by_id'][1245320]['output_quantity'] == 3


def test_limited_stock_stays_visible_without_marking_catalog():
    from brownstone.beta_vendor import vendor_prices

    c = catalog()
    record = {**MARKET, 'family': 'vendor', 'entry_id': 'fixture', 'captured_at': 1, 'character': 'Fixture',
              'vendor_standing': 5, 'merchant_items': [dict(item_id=1, quantity=1, price_copper=20,
                                                         stock=2, extended_cost=False)]}
    result = vendor_prices([record], [c | {'catalog_id': 'fixture'}], MARKET)
    assert result['observations'][0]['stock'] == 2
    assert result['observations'][0]['comparisons'][0]['marked_price_copper'] is None
    assert 'vendor_price_copper' not in c['items_by_id'][1]


def test_label_only_when_vendor_price_lowered_the_value():
    c = catalog()
    c['items_by_id'][3]['vendor_price_copper'] = 500
    p = plan(catalogs=[c])
    row, sell = p['craft'][0], p['sell'][0]
    assert row['sale_price_copper'] == 200 and sell['undercut_copper'] == 199
    assert vendor_cap_label(row) == vendor_cap_label(sell) == craft_row(row, sell)['Vendor ceiling'] == ''
    c['items_by_id'][3]['vendor_price_copper'] = 200
    sell = plan(catalogs=[c])['sell'][0]
    assert sell['undercut_copper'] == 199 and vendor_cap_label(sell) == ''
