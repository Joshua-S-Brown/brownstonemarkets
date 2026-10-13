"""Offline STORY-015b: qualified team chains reuse the existing copper route walker."""
from copy import deepcopy

import pytest
from test_action_board import MARKET as OLD_MARKET
from test_action_board import NOW as OLD_NOW
from test_action_board import combined_catalogs, observed, prices, snapshot
from test_today import MARKET, NOW, SNAPSHOT
from test_today_characters import state

from brownstone.action_board import catalog_for_row, rank_catalogs, rank_recipes
from brownstone.crafting import evaluate_recipe, parse_recipe_catalog
from brownstone.market_explorer import recipe_rows
from brownstone.progression import build_progression
from brownstone.recipe_graph import RecipeGraph, label_routes
from brownstone.today import build_today, craft_details
from brownstone.today_characters import recipe_status, team_makeable
from brownstone.today_session import plan_context, queue_line
from brownstone.today_settings import TodaySettings

MINER = ('Keenagen', 'mankrik', 'alliance')
SMITH = ('Armorer', 'mankrik', 'alliance')
TAILOR = ('Basilly', 'mankrik', 'alliance')


def make_catalog(name, profession, rid, output, inputs):
    ids = {output, *(i for i, _ in inputs)}
    items = [{'item_id': i, 'name': {1: 'Ore', 2: 'Copper Bar', 3: 'Buckle', 4: 'Belt'}.get(i, f'Item {i}'),
              'role': 'finished' if i == output else 'material', 'source_url': 'https://example.com/item'}
             for i in sorted(ids)]
    recipe = {'recipe_id': rid, 'name': f'Craft {rid}', 'profession': profession,
              'output_item_id': output, 'output_quantity': 1, 'source_url': 'https://example.com/recipe',
              'required_skill': 1, 'learned_from': [6], 'training_cost_copper': 1,
              'skillup_colors': [1, 20, 40, 60],
              'inputs': [{'item_id': i, 'quantity': q} for i, q in inputs]}
    return parse_recipe_catalog({'schema_version': 1, 'game_version': MARKET['game_version'],
                                 'rules_version': MARKET['rules_version'], 'catalog_id': name,
                                 'profession': profession, 'catalog_version': '1', 'status': 'fixture',
                                 'items': items, 'recipes': [recipe]})


def chain():
    return [make_catalog('mining', 'mining', 10, 2, [(1, 2)]),
            make_catalog('smith', 'blacksmithing', 20, 3, [(2, 3)]),
            make_catalog('tailor', 'tailoring', 30, 4, [(3, 2)])]


def character(catalog, *, learned=True, rank=8):
    data = state(rank=rank)
    surface = data['recipes']['Arbitrary title']['known_recipes']
    surface.update(name='Arbitrary title', max_rank=75,
                   rows=[{'recipe_id': r, 'learned': learned} for r in catalog['recipes_by_id']])
    return data


def evidence(catalogs):
    return {c: character(catalog) for c, catalog in zip((MINER, SMITH, TAILOR), catalogs, strict=False)}


def cost(catalogs, data=None, unit_prices=None):
    unit_prices = {1: 5, 2: 100, 3: 1000, 4: 10000} if unit_prices is None else unit_prices
    return rank_catalogs(catalogs, observed(unit_prices), MARKET, SNAPSHOT, now=NOW,
                         team_makeable=team_makeable(catalogs, data or {}))


def row(board, rid):
    return next(r for r in board['rows'] if r['recipe_id'] == rid)


def test_two_and_three_profession_chains_integer_cost_quantities_and_origins():
    catalogs = chain()
    result = cost(catalogs, evidence(catalogs))
    armour = row(result, 20)
    belt = row(result, 30)
    assert armour['craft_cost_copper'] == 30
    assert armour['shopping_list'] == {1: 6}
    assert belt['craft_cost_copper'] == 60
    assert belt['shopping_list'] == {1: 12}
    assert [(s['recipe_id'], s['catalog_id'], s['profession'], s['made_by'])
            for s in belt['intermediate_steps']] == [(20, 'smith', 'blacksmithing', 'Armorer'),
                                                    (10, 'mining', 'mining', 'Keenagen')]
    assert catalog_for_row(catalogs, belt) is catalogs[2]
    assert all(type(r['craft_cost_copper']) is int for r in result['rows'])
    assert result == cost(list(reversed(catalogs)), evidence(catalogs))


@pytest.mark.parametrize('learned,rank,status,use', [(True, 8, 'Known', True),
                                                    (False, 8, 'Train now', True),
                                                    (False, 0, 'Not yet', False)])
def test_cross_only_known_or_train_now(learned, rank, status, use):
    catalogs = chain()[:2]
    miner = character(catalogs[0], learned=learned, rank=rank)
    assert recipe_status(catalogs[0]['recipes_by_id'][10], miner)['craft_status'] == status
    result = row(cost(catalogs, {MINER: miner, SMITH: character(catalogs[1])}), 20)
    assert result['craft_cost_copper'] == (30 if use else 300)
    assert result['choices'][0]['method'] == ('craft' if use else 'buy')
    if not use:
        assert result['choices'][0]['route_note'] == 'no one on the team makes this'


def test_unknown_recipe_is_bought_and_local_recipes_still_route():
    catalogs = chain()[:2]
    miner = character(catalogs[0])
    miner['recipes']['Arbitrary title']['known_recipes']['rows'] = []
    result = row(cost(catalogs, {MINER: miner}), 20)
    assert result['choices'][0]['route_note'] == 'no one on the team makes this'
    assert result['craft_cost_copper'] == 300
    # Existing fixtures include a local bolt which has no matching character recipe evidence.
    from test_action_board import catalog
    c = catalog() | {'catalog_id': 'tailoring'}
    graph = RecipeGraph([c], {}, OLD_MARKET)
    routed = graph.for_recipe(c, 3757, prices())
    assert evaluate_recipe(routed, 3757, prices()) == evaluate_recipe(c, 3757, prices())


def test_no_evidence_exactly_matches_existing_catalog_local_fixtures():
    catalogs = combined_catalogs()
    result = rank_catalogs(catalogs, observed(prices()), OLD_MARKET, snapshot(), now=OLD_NOW)
    assert result == rank_catalogs(catalogs, observed(prices()), OLD_MARKET, snapshot(), now=OLD_NOW,
                                  team_makeable=team_makeable(catalogs, {}))
    for actual in result['rows']:
        own = catalog_for_row(catalogs, actual)
        expected = next(r for r in rank_recipes(own, observed(prices()), OLD_MARKET, snapshot(), now=OLD_NOW)
                        ['rows'] if r['recipe_id'] == actual['recipe_id'])
        assert {k: v for k, v in actual.items() if k not in ('catalog_id', 'profession', 'rank')} == {
            k: v for k, v in expected.items() if k != 'rank'}


@pytest.mark.parametrize('extra_quantity,identity', [(1, 'z-other'), (2, 'a-other'), (2, 'z-other')])
def test_two_makers_cheaper_then_catalog_identity(extra_quantity, identity):
    catalogs = chain()[:2]
    alternate = make_catalog(identity, 'tailoring', 11, 2, [(1, extra_quantity)])
    catalogs.append(alternate)
    result = row(cost(catalogs, {MINER: character(catalogs[0]), TAILOR: character(alternate)}), 20)
    winner = identity if extra_quantity == 1 or identity == 'a-other' else 'mining'
    assert result['intermediate_steps'][0]['catalog_id'] == winner
    assert result['intermediate_steps'][0]['profession'] == ('mining' if winner == 'mining' else 'tailoring')
    assert result['craft_cost_copper'] == extra_quantity * 15
    assert result == row(cost(list(reversed(catalogs)), {MINER: character(catalogs[0]),
                                                       TAILOR: character(alternate)}), 20)


def test_recipe_id_collision_refuses_with_both_catalog_identities():
    catalogs = chain()
    catalogs[1]['recipes_by_id'][10] = catalogs[1]['recipes_by_id'].pop(20) | {'recipe_id': 10}
    with pytest.raises(ValueError, match='10.*mining.*smith'):
        RecipeGraph(catalogs, {}, MARKET)


@pytest.mark.parametrize('field,value,other', [('vendor_price_copper', 1, 2), ('raw_material', True, False),
                                              ('availability', 'post-launch', 'available')])
def test_disagreeing_items_warn_and_are_buy_only(field, value, other):
    catalogs = chain()[:2]
    catalogs[0]['items_by_id'][2][field] = value
    catalogs[1]['items_by_id'][2][field] = other
    result = cost(catalogs, evidence(catalogs))
    assert result['catalog_warnings'] == ['Item 2: disagreeing route fields in catalogs mining, smith; buy-only']
    assert row(result, 20)['choices'][0]['method'] == 'buy'
    assert row(result, 20)['craft_cost_copper'] == 300
    assert row(cost(catalogs, evidence(catalogs), {1: 5, 3: 1000}), 20)['craft_cost_copper'] is None


def test_cross_catalog_cycle_is_rejected_and_unrelated_row_survives():
    catalogs = chain()
    mining = make_catalog('mining', 'mining', 10, 2, [(3, 1)])
    catalogs[0] = mining
    result = cost(catalogs, evidence(catalogs))
    assert all('cycle' in r['error'] for r in result['rows'])
    independent = make_catalog('cook', 'cooking', 40, 5, [(1, 1)])
    result = cost(catalogs + [independent], evidence(catalogs), {1: 10, 2: 100, 3: 100, 4: 100, 5: 100})
    assert row(result, 40)['valid']
    with pytest.raises(ValueError, match='cycle'):
        RecipeGraph(catalogs, team_makeable(catalogs, evidence(catalogs)), MARKET).for_recipe(catalogs[1], 20, {1: 5})


@pytest.mark.parametrize('unit_prices', [{3: 1000}, {1: 0, 2: 0, 3: 1000}])
def test_missing_or_zero_prices_never_free(unit_prices):
    catalogs = chain()[:2]
    result = row(cost(catalogs, evidence(catalogs), unit_prices), 20)
    assert not result['valid'] and result['craft_cost_copper'] is None and result['profit_copper'] is None


@pytest.mark.parametrize('field,value', [('rules_version', 'different'), ('game_version', 'forever'),
                                        ('region', 'eu'), ('environment', 'beta'), ('faction', 'horde')])
def test_incompatible_catalog_never_joins(field, value):
    catalogs = chain()[:2]
    catalogs[0][field] = value
    assert row(cost(catalogs, evidence(catalogs)), 20)['craft_cost_copper'] == 300


def test_fractional_units_are_rejected_without_rounding():
    catalogs = chain()[:2]
    catalogs[0]['recipes_by_id'][10]['output_quantity'] = 3
    result = row(cost(catalogs, evidence(catalogs)), 20)
    assert 'Fractional unit' in result['error']


def test_today_selected_character_still_uses_team_queue_makers_and_dependency_order():
    catalogs = chain()
    plan = build_today(catalogs, observed({1: 5, 2: 100, 3: 1000, 4: 10000}), MARKET, SNAPSHOT,
                       TodaySettings(1000, 1, 'fixed', max_crafts=1, character=TAILOR), now=NOW,
                       character_data=evidence(catalogs))
    assert [r['recipe_id'] for r in plan['craft']] == [30]
    assert plan['buy'][0]['item_id'] == 1 and plan['buy'][0]['quantity'] == 12
    assert plan['shopping_total_copper'] == 60
    lines = [line for line in plan['queue']['lines'] if line['stage'] == 'craft']
    assert [(line['recipe_id'], line['catalog_id'], line['made_by']) for line in lines] == [
        (10, 'mining', 'Keenagen'), (20, 'smith', 'Armorer'), (30, 'tailor', 'Basilly')]
    assert 'Copper Bar · Keenagen, Mining' in queue_line(lines[0])
    assert 'not charged' in plan['queue']['mail_note'] and 'unconfirmed' in plan['queue']['mail_note']
    assert craft_details(plan['craft'][0])['intermediate_steps'][1]['made_by'] == 'Keenagen'
    assert all('profit_copper' not in s for s in plan['craft'][0]['intermediate_steps'])


def test_team_cost_to_reach_uses_team_made_bar():
    catalogs = chain()[:2]
    smith = catalogs[1]
    target = deepcopy(smith['recipes_by_id'][20]) | {'recipe_id': 21, 'required_skill': 9, 'output_item_id': 5}
    smith['recipes_by_id'][21] = target
    smith['items_by_id'][5] = smith['items_by_id'][3] | {'item_id': 5}
    smith['recipe_for_output'][5] = 21
    data = evidence(catalogs)
    data[SMITH]["recipes"]["Arbitrary title"]["known_recipes"]["rows"][-1]["learned"] = False
    args = dict(catalogs=catalogs, observations=observed({1: 5, 2: 100, 3: 1000, 5: 1000}), market=MARKET,
                snapshot=SNAPSHOT, character=SMITH, now=NOW)
    result = build_progression(**args, character_data=data)
    assert result['professions'][0]['recipes'][0]['estimate']['cost_copper'] == 30
    data.pop(MINER)
    assert build_progression(**args, character_data=data)['professions'][0]['recipes'][0]['estimate'][
        'cost_copper'] == 300


def test_market_made_from_used_in_show_same_routes_and_no_intermediate_profit():
    catalogs = chain()
    catalogs[0]['items_by_id'][2]['role'] = 'intermediate'
    args = dict(observations=observed({1: 5, 2: 100, 3: 1000, 4: 10000}), market=MARKET, snapshot=SNAPSHOT,
                now=NOW, max_age_hours=24, auction_cut=.05)
    rows = recipe_rows(catalogs, args, evidence(catalogs))
    belt = next(r for r in rows if r['recipe']['recipe_id'] == 30)
    assert belt['value']['craft_cost_copper'] == 60
    assert [(m['item_id'], m['method'], m['quantity']) for m in belt['materials']] == [
        (3, 'craft', 2), (2, 'craft', 6), (1, 'buy', 12)]
    assert belt['materials'][1]['made_by'] == 'Keenagen'
    assert next(r for r in rows if r['recipe']['recipe_id'] == 10)['value']['profit_copper'] is None


def test_plan_context_includes_version_so_old_choices_and_ticks_reset(monkeypatch):
    import brownstone.today_session as session
    args = dict(catalogs=chain(), market=MARKET, snapshot=SNAPSHOT, settings=TodaySettings(),
                max_age_hours=24, auction_cut=.05, character_data={})
    current = plan_context(args)
    monkeypatch.setattr(session, 'TODAY_VERSION', 5)
    assert plan_context(args) != current


def test_graph_labeling_leaves_cost_walk_unchanged():
    catalogs = chain()
    graph = RecipeGraph(catalogs, team_makeable(catalogs, evidence(catalogs)), MARKET)
    routed = graph.for_recipe(catalogs[2], 30, {1: 5})
    plain = evaluate_recipe(routed, 30, {1: 5, 4: 10000})
    labeled = label_routes(deepcopy(plain), routed)
    assert labeled['craft_cost_copper'] == plain['craft_cost_copper']
    assert labeled['shopping_list'] == plain['shopping_list']


def test_builder_filters_full_market_and_rules_before_collision_checks():
    catalogs = chain()[:2]
    incompatible = deepcopy(catalogs[0]) | {'catalog_id': 'other-house', 'faction': 'horde'}
    wrong_rules = deepcopy(catalogs[0]) | {'catalog_id': 'old-rules', 'rules_version': 'old'}
    graph = RecipeGraph(catalogs + [incompatible, wrong_rules], team_makeable(catalogs, evidence(catalogs)), MARKET)
    assert len(graph.recipes) == 2
    assert evaluate_recipe(graph.for_recipe(catalogs[1], 20, {1: 5}), 20, {1: 5})['craft_cost_copper'] == 30
    with pytest.raises(ValueError, match='identities must be unique'):
        RecipeGraph([catalogs[0], catalogs[0]], {}, MARKET)


def test_invalid_maker_does_not_hide_a_valid_competing_maker():
    catalogs = chain()[:2]
    invalid = make_catalog('a-fractional', 'tailoring', 11, 2, [(1, 1)])
    invalid['recipes_by_id'][11]['output_quantity'] = 2
    catalogs.append(invalid)
    result = row(cost(catalogs, {MINER: character(catalogs[0]), TAILOR: character(invalid)}), 20)
    assert result['craft_cost_copper'] == 30
    assert result['intermediate_steps'][0]['catalog_id'] == 'mining'


def test_cross_maker_selected_independently_for_each_price_basis():
    catalogs = chain()[:2]
    observed_prices = observed({1: 5, 2: 100, 3: 1000}, {1: 100})
    result = rank_catalogs(catalogs, observed_prices, MARKET, SNAPSHOT, now=NOW,
                          team_makeable=team_makeable(catalogs, evidence(catalogs)))
    assert row(result, 20)['choices'][0]['method'] == 'buy'
    assert row(result, 20)['profit_by_basis'] == {'cautious': 650, 'listed': 920}


def test_session_estimate_materials_expand_through_team_graph(monkeypatch):
    from brownstone.session_options import build_options
    catalogs = chain()[:2]
    smith = catalogs[1]
    target = deepcopy(smith['recipes_by_id'][20]) | {'recipe_id': 21, 'required_skill': 9, 'output_item_id': 5}
    smith['recipes_by_id'][21] = target
    smith['items_by_id'][5] = smith['items_by_id'][3] | {'item_id': 5}
    data = evidence(catalogs)
    data[SMITH]['recipes']['Arbitrary title']['known_recipes']['rows'][-1]['learned'] = False
    args = dict(catalogs=catalogs, observations=observed({1: 5, 2: 100, 3: 1000, 5: 1000}),
                market=MARKET, snapshot=SNAPSHOT, character_data=data, now=NOW, max_age_hours=24,
                auction_cut=.05, listings=None, metrics=None, settings=TodaySettings(1000, 1, 'fixed'))
    plan = build_today(**args)
    original = deepcopy(plan)
    monkeypatch.setattr('brownstone.flood_signals.signals', lambda *args: {'rows': [], 'note': ''})
    options = build_options(None, MARKET, args, plan)
    armorer = next(c for c in options['characters'] if c['character'] == SMITH)
    estimate = armorer['professions'][0]['recipes'][0]['estimate']
    assert estimate['cost_copper'] == 30
    assert estimate['steps'][0]['materials'] == [{'item_id': 1, 'quantity': 6, 'method': 'buy',
        'unit_cost_copper': 5, 'total_cost_copper': 30, 'item_name': 'Ore', 'signal': None}]
    assert plan == original


def test_selected_output_maker_is_kept_even_when_another_character_also_knows_it():
    catalogs = chain()
    data = evidence(catalogs)
    data[('Aaron', 'mankrik', 'alliance')] = character(catalogs[2])
    plan = build_today(catalogs, observed({1: 5, 2: 100, 3: 1000, 4: 10000}), MARKET, SNAPSHOT,
                       TodaySettings(1000, 1, 'fixed', max_crafts=1, character=TAILOR), now=NOW,
                       character_data=data)
    assert plan['craft'][0]['made_by'] == 'Basilly'
    assert next(line for line in plan['queue']['lines'] if line.get('recipe_id') == 30)['made_by'] == 'Basilly'



def test_graph_requires_catalog_qualified_root_and_preserves_input_data():
    catalogs = chain()
    original = deepcopy(catalogs)
    graph = RecipeGraph(catalogs, team_makeable(catalogs, evidence(catalogs)), MARKET)
    with pytest.raises(ValueError, match='does not belong'):
        graph.for_recipe(catalogs[0], 20, {1: 5})
    with pytest.raises(ValueError, match='does not belong'):
        graph.for_recipe(catalogs[0], 999, {1: 5})
    label_routes(evaluate_recipe(graph.for_recipe(catalogs[1], 20, {1: 5}), 20, {1: 5}),
                 graph.for_recipe(catalogs[1], 20, {1: 5}))
    assert catalogs == original


def test_market_cycle_refusal_retains_catalog_qualified_rows():
    catalogs = chain()
    catalogs[0] = make_catalog('mining', 'mining', 10, 2, [(3, 1)])
    args = dict(observations=observed({1: 5, 2: 100, 3: 1000, 4: 10000}), market=MARKET,
                snapshot=SNAPSHOT, now=NOW, max_age_hours=24, auction_cut=.05)
    result = recipe_rows(catalogs, args, evidence(catalogs))
    assert len(result) == 3
    assert all('cycle' in r['value']['action'] and not r['materials'] for r in result)
    assert {r['catalog']['catalog_id'] for r in result} == {'mining', 'smith', 'tailor'}


def test_field_one_catalog_omits_takes_the_recorded_value_without_warning():
    catalogs = chain()[:2]
    catalogs[0]['items_by_id'][2] |= {'vendor_price_copper': 7, 'vendor_verified': False}
    result = cost(catalogs, evidence(catalogs), {1: 5, 3: 1000})
    assert result['catalog_warnings'] == []
    # The smith catalog omits the bar's vendor price, so it uses the 7c the mining catalog recorded (crafting: 10c).
    armour = row(result, 20)
    assert armour['choices'][0]['method'] == 'vendor' and armour['craft_cost_copper'] == 21
    graph = RecipeGraph(catalogs, team_makeable(catalogs, evidence(catalogs)), MARKET)
    assert graph.items[2]['vendor_price_copper'] == 7 and graph.items[2]['vendor_verified'] is False


def test_invalid_maker_deeper_in_its_chain_does_not_hide_a_valid_maker():
    smith = make_catalog('smith', 'blacksmithing', 20, 3, [(2, 3)])
    rival = make_catalog('alt', 'engineering', 40, 3, [(6, 1)])
    fractional = make_catalog('weird', 'mining', 50, 6, [(1, 1)])
    fractional['recipes_by_id'][50]['output_quantity'] = 3
    tailor = make_catalog('tailor', 'tailoring', 30, 4, [(3, 2)])
    catalogs = [smith, rival, fractional, tailor]
    makeable = {(c['catalog_id'], r): ['Maker'] for c in catalogs for r in c['recipes_by_id']}
    routed = RecipeGraph(catalogs, makeable, MARKET).for_recipe(tailor, 30, {1: 10, 2: 7})
    assert routed['recipe_for_output'][3] == 20


def test_known_makers_listed_before_train_now():
    catalogs = chain()[:1]
    data = {SMITH: character(catalogs[0], learned=False), MINER: character(catalogs[0])}
    statuses = [recipe_status(catalogs[0]['recipes_by_id'][10], data[c])['craft_status'] for c in (SMITH, MINER)]
    assert statuses == ['Train now', 'Known']
    assert team_makeable(catalogs, data)[('mining', 10)] == ['Keenagen', 'Armorer']


def test_today_names_selected_character_only_for_recipes_they_can_make():
    catalogs = chain()
    data = evidence(catalogs)
    data[TAILOR]['recipes']['Arbitrary title']['known_recipes']['rows'] = []
    assert recipe_status(catalogs[2]['recipes_by_id'][30], data[TAILOR])['craft_status'] == 'Unknown'
    plan = build_today(catalogs, observed({1: 5, 2: 100, 3: 1000, 4: 10000}), MARKET, SNAPSHOT,
                       TodaySettings(1000, 1, 'fixed', max_crafts=1, character=TAILOR, include_unknown=True),
                       now=NOW, character_data=data)
    belt = next(r for r in plan['craft'] if r['recipe_id'] == 30)
    assert belt['craft_status'] == 'Unknown' and belt['made_by'] is None
