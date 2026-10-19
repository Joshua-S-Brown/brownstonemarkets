"""Offline session composition: plan invariance, scoped characters and honest cost labels."""
from copy import deepcopy
from datetime import timedelta
from unittest.mock import Mock

import pytest
from test_progression import evidence, progression_catalog
from test_today import MARKET, NOW, SNAPSHOT
from test_today_characters import CHARACTER

from brownstone.session_options import base_signal, build_options, milestones, next_steps, next_tier, profession_order
from brownstone.today import build_today
from brownstone.today_settings import TodaySettings
from views.today_rows import session_display


def arguments(**changes):
    c = progression_catalog()
    return dict(catalogs=[c], observations={i: {'min_buyout': 200} for i in c['items_by_id']} |
                {1: {'min_buyout': 10}}, market=MARKET, snapshot=SNAPSHOT, now=NOW,
                settings=TodaySettings(10000, 1, 'fixed'), max_age_hours=24, auction_cut=.05,
                listings=None, metrics=None, character_data={CHARACTER: evidence(c)}) | changes


def signal(item_id, *, variant_state='base', variant_id=None, label='cheap'):
    return {'item_id': item_id, 'variant_id': variant_id, 'variant_state': variant_state,
            'crowding': 'contested', 'overshoot': {'label': label}}


def compose(monkeypatch, args, rows=None):
    read = Mock(return_value={'rows': rows or [], 'note': '', 'scan': None, 'freshness': None})
    monkeypatch.setattr('brownstone.flood_signals.signals', read)
    plan = build_today(**args)
    original = deepcopy((plan, args))
    result = build_options(None, MARKET, args, plan)
    assert (plan, args) == original  # Every plan field, order/rank and today_version remain identical.
    assert build_today(**args) == plan
    assert read.call_count == 1
    assert read.call_args.args[3] == args['now']
    return result, plan, read


def test_team_status_order_plan_invariance_and_single_union_read(monkeypatch):
    args = arguments()
    unknown = ('Zed', 'Beta', 'Alliance')
    capable = ('Able', 'Beta', 'Alliance')
    args['character_data'].update({unknown: {'recipes': {}, 'seen': {}, 'bags': {}}, capable: evidence()})
    result, plan, read = compose(monkeypatch, args, [signal(1), signal(3)])
    assert [c['character'] for c in result['characters']] == sorted(args['character_data'])
    assert len(result['characters']) == 3
    assert result['characters'][-1]['crafts'] == result['characters'][-1]['professions'] == []
    for c in result['characters'][:2]:
        assert [r['recipe_id'] for r in c['crafts']] == [r['recipe_id'] for r in plan['craft']]
        assert c['craft_profit_copper'] == sum(r['batch_profit_copper'] for r in plan['craft'])
        assert c['crafts'][0]['signal']['crowding'] == 'contested'
        assert c['crafts'][0]['purchases'][0]['signal']['overshoot']['label'] == 'cheap'
    assert set(read.call_args.args[2]) == {1, 2, 3, 131, 133}


def test_cheapest_route_quantities_training_and_cheap_share(monkeypatch):
    args = arguments()
    args['character_data'][CHARACTER]['recipes']['Arbitrary title']['known_recipes']['rows'][0]['learned'] = False
    result, _, _ = compose(monkeypatch, args, [signal(1), signal(2)])
    recipes = result['characters'][0]['professions'][0]['recipes']
    near = next(r for r in recipes if r['recipe_id'] == 33)
    estimate = near['estimate']
    assert estimate['cost_copper'] == 5 * 30 + 100
    assert estimate['cheap_cost_copper'] == 5 * 20  # Two 10c bought units; vendor and training excluded.
    assert all(type(s['cost_copper']) is int for s in estimate['steps'])
    assert [m['quantity'] for m in estimate['steps'][0]['materials']] == [2, 1]
    catalog = args['catalogs'][0]['items_by_id']
    assert [m['item_name'] for m in estimate['steps'][0]['materials']] == [
        catalog[m['item_id']]['name'] for m in estimate['steps'][0]['materials']]


@pytest.mark.parametrize('prices', [{}, {1: {'min_buyout': 0}}])
def test_missing_prices_incomplete_reasons_never_free(monkeypatch, prices):
    result, _, _ = compose(monkeypatch, arguments(observations=prices))
    group = result['characters'][0]['professions'][0]
    assert group['best'] is None
    for r in group['recipes']:
        assert r['profit_copper'] is None and r['board_reason'] == 'missing prices'
        assert r['estimate']['cost_copper'] is r['estimate']['cheap_cost_copper'] is None
        assert 'has no price for' in r['estimate']['reasons'][0]


def test_cap_no_estimates_and_skill_without_recipe_list(monkeypatch):
    data = evidence(max_rank=8)
    data['bags'] = {'skills': {'modern': {'rows': [
        {'name': 'Mining', 'skill_id': 186, 'rank': 3, 'max_rank': 75}]}}}
    result, _, _ = compose(monkeypatch, arguments(character_data={CHARACTER: data}))
    groups = result['characters'][0]['professions']
    capped = next(g for g in groups if g['capped'])
    assert capped['recipes'] == [] and capped['best'] is None
    mining = next(g for g in groups if g['profession'] == 'Mining')
    assert mining['note'] == 'recipes unknown' and mining['recipes'] == []


def test_incomplete_colour_and_unvalued_reason(monkeypatch):
    args = arguments()
    args['catalogs'][0]['recipes_by_id'][30]['skillup_colors'] = None
    result, _, _ = compose(monkeypatch, args)
    r = result['characters'][0]['professions'][0]['recipes'][0]
    assert r['estimate']['cost_copper'] is None
    assert 'skill-up colour is unknown' in r['estimate']['reasons'][0]
    assert result['characters'][0]['professions'][0]['best'] is not None
    assert session_display(result, args)['lever'] is None
    assert r['estimate']['cheap_cost_copper'] is None


def test_profit_cost_ties_deterministic():
    def group(name, profit=None, cost=None):
        return {'profession': name, 'best': None if profit is None else {
            'profit_copper': profit, 'estimate': {'cost_copper': cost}}}
    groups = [group('Z', 100, 10), group('A', 100, 10), group('costly', 100, 20),
              group('incomplete', 100), group('higher', 101), group('empty')]
    assert [g['profession'] for g in sorted(groups, key=profession_order)] == [
        'higher', 'A', 'Z', 'costly', 'incomplete', 'empty']


def test_variants_separate_and_legacy_compatibility():
    variant = signal(1, variant_state='variant', variant_id='suffix')
    legacy = signal(1, variant_state=None)
    assert base_signal([variant], 1) is None
    assert base_signal([variant, legacy], 1) is None
    assert base_signal([legacy], 1) == legacy
    base = signal(1)
    assert base_signal([base, variant], 1) == base
    assert base_signal([base], 2) is None


def test_stale_scope_and_incompatible_catalog(monkeypatch):
    args = arguments(now=NOW + timedelta(days=2))
    result, _, _ = compose(monkeypatch, args)
    assert result['freshness']['stale']
    assert result['snapshot'] == SNAPSHOT
    assert all(r['stale'] for r in result['characters'][0]['crafts'])
    with pytest.raises(ValueError, match='source'):
        compose(monkeypatch, arguments(snapshot=SNAPSHOT | {'source_id': 'other'}))
    with pytest.raises(ValueError, match='market'):
        compose(monkeypatch, arguments(snapshot=SNAPSHOT | {'realm': 'other'}))
    args = arguments()
    args['catalogs'][0]['rules_version'] = 'incompatible'
    result, _, _ = compose(monkeypatch, args)
    assert result['characters'][0]['crafts'] == []
    assert result['characters'][0]['professions'][0]['recipes'] == []


def test_yellow_rounding_and_nested_material_route(monkeypatch):
    args = arguments(character_data={CHARACTER: evidence(rank=21)})
    result, _, _ = compose(monkeypatch, args, [signal(1)])
    recipe = next(r for r in result['characters'][0]['professions'][0]['recipes'] if r['recipe_id'] == 31)
    from fractions import Fraction
    from math import ceil
    assert recipe['estimate']['cheap_cost_copper'] == sum(ceil(20 * Fraction(40, 60 - rank))
                                                        for rank in range(21, 33))
    # Cheapest route buys a cheap intermediate rather than assigning its raw inputs as purchases.
    args = arguments()
    args['catalogs'][0]['items_by_id'][131]['role'] = 'intermediate'
    args['catalogs'][0]['recipes_by_id'][30]['inputs'] = [{'item_id': 131, 'quantity': 2}]
    args['catalogs'][0]['recipes_by_id'][31]['inputs'] = [{'item_id': 1, 'quantity': 2}]
    args['observations'][131] = {'min_buyout': 1}
    result, _, _ = compose(monkeypatch, args, [signal(131)])
    near = next(r for r in result['characters'][0]['professions'][0]['recipes'] if r['recipe_id'] == 33)
    assert near['estimate']['cost_copper'] == near['estimate']['cheap_cost_copper'] == 10
    assert near['estimate']['steps'][0]['materials'][0]['item_id'] == 131


@pytest.mark.parametrize('key', ['source_id', 'game_version', 'region', 'scope', 'realm', 'server_type',
                                 'faction', 'environment', 'rules_version'])
def test_signal_scope_must_match_plan(monkeypatch, key):
    read = Mock()
    monkeypatch.setattr('brownstone.flood_signals.signals', read)
    args = arguments()
    plan = build_today(**args)
    with pytest.raises(ValueError, match='plan source'):
        build_options(None, MARKET | {key: 'other'}, args, plan)
    read.assert_not_called()


def test_next_steps_craft_then_level_and_character_level_gate(monkeypatch):
    args = arguments()
    args['character_data'][CHARACTER]['bags']['level'] = 6
    result, _, _ = compose(monkeypatch, args, [signal(1)])
    character = result['characters'][0]
    assert character['level'] == 6
    kinds = [s['kind'] for s in character['next_steps']]
    assert kinds[0] == 'craft'
    group = character['professions'][0]
    assert group['tier'] == {'name': 'Journeyman', 'cap': 75, 'required_level': 10, 'level_ok': False,
                             'source': 'classic'}
    level = next(s for s in character['next_steps'] if s['kind'] == 'level_character')
    assert level['tier']['required_level'] == 10
    step = next(s for s in character['next_steps'] if s['kind'] == 'level_profession')
    assert step['recipe'] is group['best'] and step['recipe']['estimate']['complete']
    assert kinds == ['craft', 'level_profession', 'level_character']
    # Each reach appears once, lowest first, and every recipe keeps its own row.
    reaches = [m['skill'] for m in group['milestones']]
    assert reaches == sorted(set(reaches))
    assert sum(len(m['recipes']) for m in group['milestones']) == len(group['recipes'])


@pytest.mark.parametrize(('rank', 'maximum', 'level', 'expected'), [
    (8, 75, None, {'name': 'Journeyman', 'cap': 75, 'required_level': 10, 'level_ok': False, 'source': 'classic'}),
    (150, 150, 20, {'name': 'Expert', 'cap': 150, 'required_level': 20, 'level_ok': True, 'source': 'classic'}),
    (200, 225, 34, {'name': 'Artisan', 'cap': 225, 'required_level': 35, 'level_ok': False, 'source': 'classic'}),
    (250, 300, 60, None), (None, 75, 10, None)])
def test_next_tier_classic_levels(rank, maximum, level, expected):
    assert next_tier({'rank': rank, 'max_rank': maximum}, level) == expected


def test_next_steps_train_nothing_and_evidence():
    tier = {'name': 'Journeyman', 'cap': 75, 'required_level': 10, 'level_ok': True}
    capped = {'best': None, 'tier': tier, 'capped': True, 'recipes': []}
    assert [s['kind'] for s in next_steps({'crafts': [], 'professions': [capped]})] == ['nothing', 'train']
    blocked = capped | {'tier': tier | {'level_ok': False}}
    assert [s['kind'] for s in next_steps({'crafts': [], 'professions': [blocked]})] == [
        'nothing', 'level_character']
    assert next_steps({'crafts': [], 'professions': []}) == [{'kind': 'evidence'}]
    incomplete = {'required_skill': 30, 'profit_copper': 5, 'estimate': {'complete': False}}
    open_group = {'best': incomplete, 'tier': None, 'capped': False, 'recipes': [incomplete]}
    assert [s['kind'] for s in next_steps({'crafts': [{}], 'professions': [open_group]})] == ['craft']


def test_milestones_share_one_estimate_per_reach():
    estimate = {'cost_copper': 9}
    recipes = [{'required_skill': 30, 'estimate': estimate, 'id': 1}, {'required_skill': 10, 'estimate': {}, 'id': 2},
               {'required_skill': 30, 'estimate': estimate, 'id': 3}]
    result = milestones(recipes)
    assert [m['skill'] for m in result] == [10, 30]
    assert [r['id'] for r in result[1]['recipes']] == [1, 3] and result[1]['estimate'] is estimate


def test_farming_plan_ranking_version_invariance_and_union(monkeypatch):
    from test_farming import loot
    args = arguments()
    args['character_data'][CHARACTER]['observations'] = sum((loot(t) for t in (0, 150, 300)), [])
    args['observations'][2770] = {'min_buyout': 11, 'market_value': 20}
    result, plan, read = compose(monkeypatch, args)
    row = result['characters'][0]['farming']['rows'][0]
    assert row['units_per_hour'] == 36 and row['value_per_hour_copper'] == 376
    assert 2770 in read.call_args.args[2]
    assert result['freshness'] == plan['freshness']


def test_farming_vendor_data_passed_without_changing_plan_or_item_rows(monkeypatch):
    from test_farming import mob_loot
    args = arguments(vendor_prices={999: 7})
    args['character_data'][CHARACTER]['observations'] = sum((mob_loot(t, 10, item=999) for t in (0, 150, 300)), [])
    result, plan, read = compose(monkeypatch, args)
    history = result['characters'][0]['farming']
    assert history['rows'][0]['value_per_hour_copper'] is None
    assert history['spots'][0]['value_per_hour_copper'] == 252
    assert history['spots'][0]['items'][0]['basis'] == 'vendor'
    assert 999 in read.call_args.args[2]


def test_session_copies_sell_profit_without_changing_cautious_plan(monkeypatch):
    args = arguments(metrics={3: {'min_buyout': 200, 'listings': 4, 'units': 4, 'largest_stack_units': 1}})
    result, plan, _ = compose(monkeypatch, args)
    sells = {r['output_item_id']: r for r in plan['sell']}
    for character in result['characters']:
        for row in character['crafts']:
            quote = sells[row['output_item_id']]['undercut_batch_profit_copper']
            expected = row['batch_profit_copper'] if quote is None else quote
            assert row['headline_profit_copper'] == expected
            assert row['headline_per_craft_copper'] == expected // row['batch_size']
        assert character['craft_profit_copper'] == sum(r['headline_profit_copper'] for r in character['crafts'])


@pytest.mark.parametrize(('profession', 'level', 'version', 'required', 'source', 'kind'), [
    ('cOoKiNg', 6, 'forever', 0, 'trainer', 'train'),
    ('Cooking', None, 'forever', 0, 'trainer', 'train'),
    ('Fishing', 6, 'forever', 10, 'trainer', 'level_character'),
    ('Tailoring', 6, 'forever', 10, 'classic_fallback', 'level_character'),
    ('Cooking', 6, 'classic', 10, 'classic', 'level_character'),
    ('Cooking', 10, 'classic', 10, 'classic', 'train'),
])
def test_trainer_tiers_steps(profession, level, version, required, source, kind):
    from brownstone.tier_levels import load
    group = {'profession': profession, 'rank': 75, 'max_rank': 75,
             'best': None, 'capped': True, 'recipes': []}
    tier = next_tier(group, level, load(), version)
    assert tier['required_level'] == required and tier['source'] == source
    steps = next_steps({'crafts': [], 'professions': [group | {'tier': tier}]})
    assert [s['kind'] for s in steps] == ['nothing', kind]


def test_merge_tiers_requires_equal_level_and_source():
    from brownstone.session_options import merge_tier_steps
    base = {'kind': 'level_character', 'group': {'profession': 'Fishing'},
            'tier': {'name': 'Journeyman', 'required_level': 10, 'source': 'trainer'}}
    fallback = base | {'tier': base['tier'] | {'source': 'classic_fallback'}}
    higher = base | {'tier': base['tier'] | {'required_level': 20}}
    steps = merge_tier_steps([base, base, fallback, higher])
    assert [len(s['groups']) for s in steps] == [2, 1, 1]


def test_forever_composition_loads_once_and_preserves_plan(monkeypatch):
    from brownstone import tier_levels
    args = arguments()
    market = MARKET | {'game_version': 'forever'}
    args.update(market=market, snapshot=SNAPSHOT | {'game_version': 'forever'})
    args['catalogs'] = [c | {'game_version': 'forever'} for c in args['catalogs']]
    plan = build_today(**args)
    original = deepcopy((args, plan))
    read = Mock(wraps=tier_levels.load)
    monkeypatch.setattr(tier_levels, 'load', read)
    monkeypatch.setattr('brownstone.flood_signals.signals', lambda *a: {'rows': []})
    result = build_options(None, market, args, plan)
    assert read.call_count == 1
    assert result['characters'][0]['professions'][0]['tier']['source'] == 'classic_fallback'
    assert 'Levels from captured Forever trainer lists' in result['tier_explanation']
    assert (args, plan) == original


def test_session_uses_learnable_best_and_its_profit_order_without_changing_plan(monkeypatch):
    args = arguments()
    c = args['catalogs'][0]
    c['recipes_by_id'][31]['learned_from'] = [2]
    args['observations'][131] = {'min_buyout': 1000}
    result, _, _ = compose(monkeypatch, args)
    character = result['characters'][0]
    group = character['professions'][0]
    assert group['recipes'][0]['recipe_id'] == 31
    assert group['best']['recipe_id'] == 33
    step = next(s for s in character['next_steps'] if s['kind'] == 'level_profession')
    assert step['recipe']['recipe_id'] == 33
    competitor = group | {'profession': 'Another', 'best': group['best'] | {'profit_copper': 200}}
    assert sorted([group, competitor], key=profession_order) == [competitor, group]
