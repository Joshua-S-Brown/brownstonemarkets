"""Offline route exploration: one cost walker, exact waterfall, source-scoped evidence."""
from copy import deepcopy
from pathlib import Path

import pytest
from test_market_explorer import explorer_fixture
from test_scans import NOW

from brownstone import market_explorer, recipe_catalogs, supply_chain
from brownstone.crafting import evaluate_recipe, route_options


@pytest.fixture
def chain(tmp_path):
    config, catalog = explorer_fixture(tmp_path)
    return market_explorer.load_explorer(config, [catalog], NOW)


def test_options_force_each_method_and_all_invalid_overrides(chain):
    c, recipe = supply_chain.select(chain, 'tailoring', 2393)
    prices = {2589: 11, 2996: 100, 2576: 2000, 2320: 30, 2324: 30}
    assert route_options(c, prices, 2996, (2393,)) == [(100, 'buy', {2996: 1}), (22, 'craft', {2589: 2})]
    for method, expected in [('buy', 100), ('craft', 22)]:
        result = evaluate_recipe(c, recipe['recipe_id'], prices, forced={2996: method})
        assert result['choices'][0]['method'] == method
        assert result['choices'][0]['unit_cost_copper'] == expected
        assert (2996 in result['shopping_list']) == (method == 'buy')
    for method in ('vendor', 'buy'):
        result = evaluate_recipe(c, 2393, prices, forced={2320: method})
        assert next(r for r in result['shopping_choices'] if r['item_id'] == 2320)['method'] == method
    for forced, reason in [({2996: 'vendor'}, 'unavailable'), ({2576: 'buy'}, 'root'),
                           ({999: 'buy'}, 'outside'), ({2320: 'craft'}, 'unavailable'),
                           ({2996: 'unknown'}, 'unavailable')]:
        with pytest.raises(ValueError, match=reason):
            evaluate_recipe(c, 2393, prices, forced=forced)


def test_waterfall_batch_graph_holdings_and_search(chain):
    normal = supply_chain.route(chain, 'tailoring', 2393)
    value = evaluate_recipe(chain['recipes'][0]['catalog'], 2393, {2589: 11, 2996: 100, 2576: 2000, 2324: 30})
    assert sum(line['amount_copper'] for line in normal['waterfall'][:-1]) == value['profit_copper']
    assert normal['waterfall'][-1]['amount_copper'] == value['profit_copper']
    batch = supply_chain.route(chain, 'tailoring', 2393, 5)
    assert batch['profit_copper'] == 5 * normal['profit_copper']
    assert batch['spend_copper'] == 5 * normal['spend_copper']
    assert [leaf['quantity'] for leaf in batch['leaves']] == [5 * leaf['quantity'] for leaf in normal['leaves']]
    assert next(n for n in normal['nodes'] if n['item_id'] == 2589)['column'] == 2
    assert next(e for e in normal['edges'] if e['child'] == 2589)['quantity'] == 2
    forced = supply_chain.route(chain, 'tailoring', 2393, forced={2996: 'buy'})
    assert next(n for n in forced['nodes'] if n['item_id'] == 2996)['forced']
    assert forced['spend_copper'] > normal['spend_copper']
    held = deepcopy(chain)
    next(r for r in held['items'] if r['item_id'] == 2589)['quality'] = 2
    assert next(n for n in supply_chain.route(held, 'tailoring', 2393)['nodes']
                if n['item_id'] == 2589)['quality'] == 2
    held['holdings'] = ({(2589, None, 'base'): 999}, {}, [{'unknown': False, 'partial': False}], [])
    assert supply_chain.route(held, 'tailoring', 2393)['spend_copper'] == normal['spend_copper']
    assert supply_chain.outputs(chain, '2996')['hits'][0]['recipe_id'] == 2963
    assert supply_chain.outputs(chain, 'shirt')['hits'][0]['item_id'] == 2576
    assert supply_chain.outputs(chain, '')['hits'] == [] and supply_chain.outputs(chain, '')['hit_count'] == 0
    many = supply_chain.outputs(chain | {'recipes': chain['recipes'] * 60}, '2')
    assert len(many['hits']) == supply_chain.HIT_LIMIT < many['hit_count']
    assert next(leaf for leaf in normal['leaves'] if leaf['item_id'] == 2589)['depth'] == '11 units listed'
    assert next(leaf for leaf in normal['leaves'] if leaf['item_id'] == 2320)['depth'] == 'Vendor'
    unlisted = chain | {'metrics': [m for m in chain['metrics'] if m['item_id'] != 2589]}
    assert unlisted['metrics']
    assert next(leaf for leaf in supply_chain.route(unlisted, 'tailoring', 2393)['leaves']
                if leaf['item_id'] == 2589)['depth'] == 'Not listed'


def test_vendor_cap_missing_intermediate_unsupported_and_batch_bounds(chain):
    chain['observations'][2576] = {'min_buyout': 500, 'market_value': 600}
    catalog, _ = supply_chain.select(chain, 'tailoring', 2393)
    catalog['items_by_id'][2576]['vendor_price_copper'] = 100
    capped = supply_chain.route(chain, 'tailoring', 2393)
    assert capped['waterfall'][0]['label'] == 'Sale · capped at vendor price'
    assert capped['waterfall'][0]['amount_copper'] == 100
    assert sum(leaf['amount_copper'] for leaf in capped['waterfall'][:-1]) == capped['waterfall'][-1]['amount_copper']
    intermediate = supply_chain.route(chain, 'tailoring', 2963)
    assert not intermediate['can_add'] and intermediate['profit_copper'] is None
    assert all(leaf['label'] not in ('Sale', 'Profit', 'Auction cut') for leaf in intermediate['waterfall'])
    chain['observations'] = {2576: {'min_buyout': 500}}
    missing = supply_chain.route(chain, 'tailoring', 2393)
    assert missing['waterfall'][-1]['amount_copper'] is None
    assert 'Missing price' in missing['waterfall'][-1]['label']
    assert missing['profit_copper'] is None
    chain['observations'] = {}
    assert supply_chain.route(chain, 'tailoring', 2393)['waterfall'][-1]['label'] == 'Missing output sale price'
    for batch in (0, 6):
        with pytest.raises(ValueError, match='Batch'):
            supply_chain.route(chain, 'tailoring', 2393, batch)
    catalog['recipes_by_id'][2963]['inputs'] = [{'item_id': 2996, 'quantity': 1}]
    assert 'unsupported recipe' in supply_chain.route(chain, 'tailoring', 2393)['reason']


def test_cross_profession_maker_blocking_and_status(chain):
    c, _ = supply_chain.select(chain, 'tailoring', 2393)
    c['team_makeable'] = {('other', 2963): ['Basilly']}
    c['blocked_cross_items'] = {2320}
    c['catalog_warnings'] = ['Evidence warning']
    c['recipes_by_id'][2963]['catalog_id'] = 'other'
    chain['characters'] = {('Basilly', 'Beta', 'Alliance'): {'recipes': {}, 'seen': {}, 'bags': {}}}
    result = supply_chain.route(chain, 'tailoring', 2393)
    bolt = next(n for n in result['nodes'] if n['item_id'] == 2996)
    assert bolt['maker'] == 'Basilly, Tailoring'
    assert bolt['characters'][0]['craft_status'] == 'Unknown'
    assert next(n for n in result['nodes'] if n['item_id'] == 2320)['route_note'] == 'no one makes this'
    assert result['evidence']['warnings'] == ['Evidence warning']
    assert 'uncharged' in result['evidence']['postage']


def test_no_snapshot_search_and_unknown_recipe(chain):
    chain['recipes'] = []
    assert supply_chain.outputs(chain, '2996')['hits']
    assert supply_chain.route(chain, 'tailoring', 2963)['nodes']
    with pytest.raises(LookupError):
        supply_chain.route(chain, 'missing', 1)
    with pytest.raises(LookupError):
        supply_chain.route(chain, 'tailoring', 999)


def test_unforced_routes_are_the_cheapest_option_across_every_catalog():
    """Without overrides each input takes the cheapest option, so forced=None keeps today's results.

    Pre-story byte equality was checked once at review across every config catalog; this stays valid
    when catalogs change instead of pinning their hashes."""
    catalogs, _ = recipe_catalogs.parse_catalogs(recipe_catalogs.find_catalogs(Path('config')))
    assert catalogs
    for catalog in catalogs:
        prices = {item: item % 113 for item in catalog['items_by_id']}  # Includes zero: missing, never free.
        for recipe_id in catalog['recipes_by_id']:
            try:
                plain = evaluate_recipe(catalog, recipe_id, prices)
            except ValueError as error:
                with pytest.raises(ValueError, match=str(error)):
                    evaluate_recipe(catalog, recipe_id, prices, forced={})
                continue
            assert evaluate_recipe(catalog, recipe_id, prices, forced={}) == plain
            for choice in plain['choices']:
                options = route_options(catalog, prices, choice['item_id'], (recipe_id,))
                expected = min(options, key=lambda o: o[:2]) if options else (None, 'missing', {})
                assert (choice['unit_cost_copper'], choice['method']) == expected[:2]


def test_shared_node_aggregates_units_at_deepest_column_and_fractional_is_unsupported(chain):
    c, _ = supply_chain.select(chain, 'tailoring', 2393)
    c['recipes_by_id'][2393]['inputs'].extend([{'item_id': 2589, 'quantity': 1}] * 2)
    result = supply_chain.route(chain, 'tailoring', 2393)
    raw = [n for n in result['nodes'] if n['item_id'] == 2589]
    assert len(raw) == 1 and raw[0]['units'] == 4 and raw[0]['column'] == 2
    assert next(e for e in result['edges'] if e['parent'] == 2576 and e['child'] == 2589)['quantity'] == 2
    c['recipes_by_id'][2963]['output_quantity'] = 3
    assert 'unsupported recipe' in supply_chain.route(chain, 'tailoring', 2393)['reason']


def test_root_eligibility_uses_selected_catalog_not_shared_item_role(chain):
    c, _ = supply_chain.select(chain, 'tailoring', 2393)
    projected = deepcopy(c)
    projected['items_by_id'][2576]['role'] = 'intermediate'
    next(r for r in chain['recipes'] if r['recipe']['recipe_id'] == 2393)['catalog'] = projected
    route = supply_chain.route(chain, 'tailoring', 2393)
    assert route['can_add'] and route['profit_copper'] is not None
    chain['snapshot'] = None
    assert not supply_chain.route(chain, 'tailoring', 2393)['can_add']
