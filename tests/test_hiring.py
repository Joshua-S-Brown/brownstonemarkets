"""STORY-059 offline hiring costs, team feeds, evidence, scopes and immutability."""
from copy import deepcopy

import pytest
from test_action_board import observed
from test_recipe_graph import SMITH, character, make_catalog
from test_today import MARKET, NOW, SNAPSHOT

from brownstone import hiring
from brownstone.action_board import POLICY_VERSION, rank_catalogs
from brownstone.progression import estimate_cost, skillup_walk
from brownstone.today import TODAY_VERSION, build_today
from brownstone.today_characters import recipe_status, team_makeable
from brownstone.today_settings import TodaySettings


def fixture():
    miner = make_catalog('mining', 'mining', 10, 2, [(1, 2)])
    miner['recipes_by_id'][10]['skillup_colors'] = [1, 300, 301, 302]
    smith = make_catalog('smith', 'blacksmithing', 20, 3, [(2, 3)])
    return [miner, smith]


def context(catalogs=None, data=None, prices=None, **changes):
    catalogs = fixture() if catalogs is None else catalogs
    data = {SMITH: character(catalogs[1])} if data is None else data
    return hiring.prepare(**(dict(catalogs=catalogs, observations=observed(
        {1: 5, 2: 100, 3: 1000} if prices is None else prices), market=MARKET, snapshot=SNAPSHOT,
        character_data=data, now=NOW) | changes))


def row(ctx, name='mining'):
    return next(r for r in hiring.summaries(ctx)['rows'] if r['profession'] == name)


def test_trainer_only_pattern_count_training_once_and_cumulative_walk():
    catalogs = fixture()
    c = catalogs[0]
    pattern = c['recipes_by_id'][10] | {'recipe_id': 11, 'learned_from': [5], 'inputs': []}
    c['recipes_by_id'][11] = pattern
    ctx = context(catalogs)
    hire = hiring.new_hire(catalogs, 'mining')
    assert recipe_status(c['recipes_by_id'][10], hire)['craft_status'] == 'Train now'
    assert recipe_status(pattern, hire)['craft_status'] == 'Unknown'
    entries = [(c, c['recipes_by_id'][10])]
    walk = skillup_walk(entries, hire, 1, 300, ctx['prices'])
    result = hiring.detail(ctx, row(ctx))
    assert result['needs_pattern'] == 1
    for tier in result['tiers']:
        assert tier['estimate'] == estimate_cost(entries, hire, 1, 300, tier['cap'], ctx['prices'], walk)
        assert tier['estimate']['cost_copper'] == 10 * (tier['cap'] - 1) + 1
        assert sum(s['training_cost_copper'] for s in tier['estimate']['steps']) == 1
        assert tier['tier_fees'] == 'tier fees not included (unknown)'
        assert all(type(s['cost_copper']) is int for s in tier['estimate']['steps'])
    assert [t['required_level'] for t in result['tiers']] == [None, 10, 20, 35]


@pytest.mark.parametrize('failure,reason', [('training', 'training cost is unknown'),
                                          ('material', 'has no price for'), ('zero', 'has no price for'),
                                          ('colour', 'skill-up colour is unknown'), ('gap', 'no qualifying')])
def test_incomplete_never_free(failure, reason):
    catalogs = fixture()
    recipe = catalogs[0]['recipes_by_id'][10]
    prices = {1: 5, 2: 100, 3: 1000}
    if failure == 'training':
        recipe.pop('training_cost_copper')
    elif failure in ('material', 'zero'):
        prices[1] = 0
    elif failure == 'colour':
        recipe.pop('skillup_colors')
    else:
        recipe['skillup_colors'] = [1, 2, 3, 4]
    result = hiring.detail(context(catalogs, prices=prices), row(context(catalogs, prices=prices)))
    assert all(not t['estimate']['complete'] and t['estimate']['cost_copper'] is None for t in result['tiers'])
    assert reason in result['tiers'][0]['estimate']['reasons'][0]


def test_best_profit_limited_by_tier_required_skill_and_trainer():
    catalogs = fixture()
    for rid, required, source in [(11, 76, [6]), (12, 151, [6]), (13, 226, [6]), (14, 1, [5])]:
        r = catalogs[0]['recipes_by_id'][10] | {'recipe_id': rid, 'output_item_id': rid, 'required_skill': required,
                                              'learned_from': source, 'name': f'Recipe {rid}'}
        catalogs[0]['recipes_by_id'][rid] = r
        catalogs[0]['items_by_id'][rid] = {'item_id': rid, 'name': str(rid), 'role': 'finished'}
    ctx = context(catalogs, prices={1: 5, 2: 100, 3: 1000, 11: 200, 12: 300, 13: 400, 14: 10000})
    assert [t['best']['recipe_id'] for t in hiring.detail(ctx, row(ctx))['tiers']] == [10, 11, 12, 13]
    assert (
        [r['profession'] for r in hiring.summaries(ctx, window=74)['rows']] ==
        [r['profession'] for r in hiring.summaries(ctx, window=75)['rows']])
    assert next(r for r in hiring.summaries(ctx, window=74)['rows']
                if r['profession'] == 'mining')['best_now']['recipe_id'] == 10
    assert next(r for r in hiring.summaries(ctx, window=75)['rows']
                if r['profession'] == 'mining')['best_now']['recipe_id'] == 11
    ctx = context(catalogs, prices={1: 100, 2: 100, 3: 1000, 11: 2000})
    rows = hiring.summaries(ctx)['rows']
    assert rows[0]['profession'] == 'mining'  # At 300 beats smith; now it loses money.
    assert rows[0]['best_now']['profit_copper'] < 0 < rows[1]['best_now']['profit_copper']
    catalogs[0]['recipes_by_id'][10]['required_skill'] = 27
    assert next(r for r in hiring.summaries(context(catalogs))['rows']
                if r['profession'] == 'mining')['best_now'] is None


def test_feeds_counts_top_three_quantities_train_now_and_unrelated():
    catalogs = fixture()
    for rid, q in [(21, 4), (22, 5), (23, 6)]:
        catalogs[1]['recipes_by_id'][rid] = catalogs[1]['recipes_by_id'][20] | {
            'recipe_id': rid, 'name': f'Armour {rid}', 'inputs': [{'item_id': 2, 'quantity': q}]}
    data = {SMITH: character(catalogs[1], learned=False)}
    ctx = context(catalogs, data)
    result = hiring.feeds(ctx, 'mining', 75)
    assert result['count'] == 4
    assert [s['saved_copper'] for s in result['top']] == [540, 450, 360]
    assert [s['recipe_id'] for s in result['top']] == [23, 22, 21]
    assert all(s['material'] == 'Copper Bar' for s in result['top'])
    assert hiring.feeds(ctx, 'cooking', 300) == {'count': 0, 'top': [], 'note': 'feeds nothing'}
    catalogs[0]['recipes_by_id'][10]['required_skill'] = 76
    assert hiring.feeds(context(catalogs, data), 'mining', 75)['count'] == 0
    assert hiring.feeds(context(catalogs, data), 'mining', 150)['count'] == 4
    # Unknown and Not yet consumers are excluded; missing baseline costs cannot become savings.
    data[SMITH]['recipes']['Arbitrary title']['known_recipes']['rows'] = []
    assert hiring.feeds(context(catalogs, data), 'mining', 300)['count'] == 0
    assert hiring.feeds(context(catalogs, prices={1: 5, 3: 1000}), 'mining', 300)['count'] == 0


def test_existing_holders_exact_ids_rank_and_two_primary_comparison():
    catalogs = fixture()
    data = {SMITH: character(catalogs[1])}
    data[SMITH]['bags'] = {'captured_at': 101, 'skills': {'modern': {'rows': [
        {'name': 'Smith title', 'skill_id': 164, 'rank': 12, 'max_rank': 150},
        {'name': 'Mining', 'skill_id': 186, 'rank': 8, 'max_rank': 75},
        {'name': 'Cooking', 'skill_id': 185, 'rank': 100, 'max_rank': 150},
        {'name': 'Fishing', 'skill_id': 356, 'rank': 100, 'max_rank': 150}]}}}
    surface = data[SMITH]['recipes']['Arbitrary title']['known_recipes']
    surface['skill_id'] = 164
    r = catalogs[1]['recipes_by_id'][20] | {'recipe_id': 21, 'required_skill': 13, 'name': 'Next armour'}
    catalogs[1]['recipes_by_id'][21] = r
    surface['rows'].append({'recipe_id': 21, 'learned': False})
    ctx = context(catalogs, data)
    assert row(ctx, 'blacksmithing')['holders'] == [{'character': SMITH, 'rank': 12, 'max_rank': 150}]
    comparison = hiring.comparisons(ctx)
    assert len(comparison) == 1
    assert [g['profession'] for g in comparison[0]['professions']] == ['blacksmithing', 'mining']
    assert comparison[0]['professions'][0]['best']['recipe_id'] == 21
    # Team's holdings-first results are shown as they are, never re-walked without holdings.
    team = {SMITH: {'professions': [g | {'best': g['best'] and g['best'] | {'estimate': {'cost_copper': 7}}}
                                    for g in hiring.progression.build_progression(
                                        **ctx['progression_arguments'], character=SMITH, board=ctx['board'])[
                                        'professions']]}}
    shown = hiring.comparisons(ctx, results=team)[0]['professions'][0]['best']
    assert shown['estimate'] == {'cost_copper': 7}
    data[SMITH]['bags']['skills']['modern']['rows'].pop(1)
    assert hiring.comparisons(context(catalogs, data)) == []


def test_no_catalog_bottom_once_and_empty_catalogs():
    result = hiring.summaries(context())
    assert result['no_catalog'].count('herbalism') == result['no_catalog'].count('skinning') == 1
    assert 'mining' not in result['no_catalog']
    assert hiring.NO_CATALOG == 'no catalog: gathering income and supply are not modelled'
    assert hiring.summaries(context([], {}))['rows'] == []


def test_sort_profit_completeness_cost_name_and_missing():
    def r(name, profit, cost):
        return {'profession': name, 'best': {'profit_copper': profit} if profit is not None else None,
                'estimate': {'complete': cost is not None, 'cost_copper': cost}}
    rows = [r('missing', None, 1), r('incomplete', 10, None), r('b', 10, 2), r('a', 10, 2),
            r('cheap', 10, 1), r('higher', 11, None), r('negative', -1, 1)]
    assert [x['profession'] for x in sorted(rows, key=hiring.summary_sort)] == [
        'higher', 'cheap', 'a', 'b', 'incomplete', 'negative', 'missing']


@pytest.mark.parametrize('field,value', [('rules_version', 'other'), ('game_version', 'forever'),
                                        ('faction', 'horde'), ('realm', 'other')])
def test_catalog_scope_never_joins(field, value):
    catalogs = fixture()
    catalogs[0][field] = value
    ctx = context(catalogs)
    assert [r['profession'] for r in hiring.summaries(ctx)['rows']] == ['blacksmithing']
    assert hiring.feeds(ctx, 'mining', 300)['count'] == 0


@pytest.mark.parametrize('changes,reason', [({'source_id': 'other'}, 'source'), ({'realm': 'other'}, 'market')])
def test_snapshot_scope_refused(changes, reason):
    with pytest.raises(ValueError, match=reason):
        context(snapshot=SNAPSHOT | changes)


def test_today_board_versions_and_inputs_unchanged():
    catalogs = fixture()
    data = {SMITH: character(catalogs[1])}
    observations = observed({1: 5, 2: 100, 3: 1000})
    original = deepcopy((catalogs, data, observations))
    args = dict(catalogs=catalogs, observations=observations, market=MARKET, snapshot=SNAPSHOT,
                now=NOW, character_data=data)
    plan = build_today(**args, settings=TodaySettings(1000, 1, 'fixed'))
    board_args = {k: v for k, v in args.items() if k != 'character_data'}
    board = rank_catalogs(**board_args, team_makeable=team_makeable(catalogs, data))
    ctx = hiring.prepare(**args)
    for r in hiring.summaries(ctx)['rows']:
        hiring.detail(ctx, r)
    assert (catalogs, data, observations) == original
    assert plan == build_today(**args, settings=TodaySettings(1000, 1, 'fixed'))
    assert board == rank_catalogs(**board_args, team_makeable=team_makeable(catalogs, data))
    assert (POLICY_VERSION, TODAY_VERSION) == ('0.4', 15)


def test_material_routes_current_team_plus_own_trainers_never_other_hire_professions():
    catalogs = fixture()
    # A smith hire needs bar. With no current miner it buys; with one, CRAFT-12 crafts it.
    catalogs[1]['recipes_by_id'][20]['skillup_colors'] = [1, 300, 301, 302]
    absent = context(catalogs, {})
    assert row(absent, 'blacksmithing')['estimate']['cost_copper'] == 299 * 300 + 1
    miner = ('Miner', 'Beta', 'Alliance')
    present = context(catalogs, {miner: character(catalogs[0])})
    assert row(present, 'blacksmithing')['estimate']['cost_copper'] == 299 * 30 + 1
    # Own trainer intermediates may be made even when no character knows them.
    own = make_catalog('tailor', 'tailoring', 30, 4, [(2, 3)])
    own['items_by_id'][1] = catalogs[0]['items_by_id'][1]
    own['recipes_by_id'][31] = catalogs[0]['recipes_by_id'][10] | {
        'recipe_id': 31, 'profession': 'tailoring', 'required_skill': 1}
    own['recipes_by_id'][30]['skillup_colors'] = [1, 300, 301, 302]
    own['recipes_by_id'][31].pop('skillup_colors')
    trainer = row(context([own], {}), 'tailoring')
    assert trainer['estimate']['cost_copper'] == 299 * 30 + 1
    # Changing that intermediate to a pattern means it must be bought, never assumed known.
    own['recipes_by_id'][31]['learned_from'] = [5]
    pattern = row(context([own], {}), 'tailoring')
    assert pattern['estimate']['cost_copper'] == 299 * 300 + 1
    # A teammate who knows that pattern makes it for the hire; the hire's own skill-ups stay trainer-only.
    tailor = ('Tailor', 'Beta', 'Alliance')
    taught = context([own], {tailor: character(own)})
    assert row(taught, 'tailoring')['estimate']['cost_copper'] == 299 * 30 + 1
    assert all(s['recipe_id'] == 30 for s in row(taught, 'tailoring')['walk'][0])


def test_unknown_learning_source_is_neither_pattern_nor_trainer_and_explains_the_gap():
    catalogs = fixture()
    recipe = catalogs[0]['recipes_by_id'][10]
    recipe.pop('learned_from')
    ctx = context(catalogs)
    result = hiring.detail(ctx, row(ctx))
    assert (result['needs_pattern'], result['unknown_source']) == (0, 1)
    reason = result['tiers'][0]['estimate']['reasons'][0]
    assert reason == ('Rank 1: no qualifying skill-up craft; '
                      '1 recipes at or below rank 1 have no learning-source evidence')
    assert result['tiers'][0]['estimate']['cost_copper'] is None


def test_feed_unsupported_routes_and_conflicting_item_evidence_do_not_claim_savings():
    catalogs = fixture()
    catalogs[0]['recipes_by_id'][10]['output_quantity'] = 3
    assert hiring.feeds(context(catalogs), 'mining', 300)['count'] == 0
    catalogs = fixture()
    catalogs[0]['items_by_id'][2]['vendor_price_copper'] = 5
    catalogs[1]['items_by_id'][2]['vendor_price_copper'] = 6
    ctx = context(catalogs)
    assert ctx['catalog_warnings']
    assert hiring.feeds(ctx, 'mining', 300)['count'] == 0


def test_catalog_header_identity_and_stale_snapshot_keep_current_profit_visible():
    from datetime import timedelta
    catalogs = fixture()
    for catalog in catalogs:
        catalog.pop('catalog_id')
    ctx = context(catalogs, now=NOW + timedelta(days=2))
    assert ctx['board']['freshness']['stale']
    assert row(ctx)['best']['profit_copper'] == 85
    assert hiring.feeds(ctx, 'mining', 75)['top'][0]['saved_copper'] == 270


def test_hiring_uses_shared_trainer_levels_case_insensitively():
    from brownstone.tier_levels import load
    catalogs = fixture()
    catalogs[0]['profession'] = 'cOoKiNg'
    ctx = context(catalogs)
    ctx['market'] = ctx['market'] | {'game_version': 'forever'}
    tiers = hiring.detail(ctx, row(ctx, 'cOoKiNg'))['tiers']
    assert [t['required_level'] for t in tiers] == [None, 0, 20, 35]
    assert tiers[1]['source'] == 'trainer'
    assert tiers[1]['evidence'] == load()[('cooking', 'Journeyman')]
    assert tiers[2]['source'] == 'classic_fallback'


def test_hiring_first_aid_catalog_slug():
    catalogs = fixture()
    catalogs[0]['profession'] = 'first-aid'
    ctx = context(catalogs)
    ctx['market'] = ctx['market'] | {'game_version': 'forever'}
    assert hiring.detail(ctx, row(ctx, 'first-aid'))['tiers'][1]['required_level'] == 0
