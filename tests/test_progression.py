"""Offline Team reach, evidence, current-board values and copper estimate boundaries."""
from copy import deepcopy
from fractions import Fraction

import pytest
from test_today import MARKET, NOW, SNAPSHOT, catalog
from test_today_characters import CHARACTER, state

from brownstone.action_board import rank_catalogs
from brownstone.progression import build_progression, estimate_cost, expected_crafts, summary_sort
from brownstone.today_characters import profession_rank


def progression_catalog():
    c = catalog()
    base = c['recipes_by_id'][30]
    base.update(required_skill=1, skillup_colors=[1, 20, 40, 60], learned_from=[6], training_cost_copper=100)
    for rid, required in [(31, 33), (32, 34), (33, 13)]:
        output = rid + 100
        c['items_by_id'][output] = c['items_by_id'][3] | {'item_id': output, 'name': f'Output {rid}'}
        c['recipes_by_id'][rid] = base | {'recipe_id': rid, 'name': f'Recipe {rid}', 'required_skill': required,
                                        'output_item_id': output}
        c['recipe_for_output'][output] = rid
    c['recipes'] = list(c['recipes_by_id'].values())
    c['items'] = list(c['items_by_id'].values())
    return c


def evidence(c=None, **changes):
    c = c or progression_catalog()
    data = state(rank=8)
    surface = data['recipes']['Arbitrary title']['known_recipes']
    surface.update(name='Arbitrary title', max_rank=75, rows=[{'recipe_id': rid, 'learned': rid == 30}
                                                           for rid in c['recipes_by_id']])
    surface.update(changes)
    return data


def calculate(c=None, data=None, **changes):
    c = c or progression_catalog()
    observations = {i: {'min_buyout': 200} for i in c['items_by_id']}
    observations[1] = {'min_buyout': 10}
    return build_progression(**(dict(catalogs=[c], observations=observations, market=MARKET, snapshot=SNAPSHOT,
                                    character_data={CHARACTER: data or evidence(c)}, character=CHARACTER, now=NOW)
                                | changes))


def rows(result):
    return result['professions'][0]['recipes']


def test_window_boundaries_slider_known_excluded_and_board_profit():
    result = calculate()
    assert {r['recipe_id'] for r in rows(result)} == {31, 33}  # +25, +5; +26 excluded, Known excluded.
    assert {r['recipe_id'] for r in rows(calculate(window=26))} == {31, 32, 33}
    assert {r['recipe_id'] for r in rows(calculate(window=5))} == {33}
    assert len(rows(calculate(window=100))) == 3
    assert all(r['points_needed'] == r['required_skill'] - 8 for r in rows(result))
    c = progression_catalog()
    board = rank_catalogs([c], {i: {'min_buyout': 200} for i in c['items_by_id']} | {1: {'min_buyout': 10}},
                          MARKET, SNAPSHOT, now=NOW)
    profits = {r['recipe_id']: r['profit_copper'] for r in board['rows']}
    assert all(r['profit_copper'] == profits[r['recipe_id']] for r in rows(result))
    assert result['professions'][0]['rank'] == 8
    assert result['professions'][0]['max_rank'] == 75


@pytest.mark.parametrize('window', [4, 101, 25.5, True])
def test_invalid_window(window):
    with pytest.raises(ValueError, match='window'):
        calculate(window=window)


def test_pattern_unknown_and_unlisted_never_attributed_by_title():
    c = progression_catalog()
    c['recipes_by_id'][31]['learned_from'] = [5]
    c['recipes_by_id'][33].pop('learned_from')
    data = evidence(c)
    data['recipes']['Arbitrary title']['known_recipes']['rows'] = [
        row for row in data['recipes']['Arbitrary title']['known_recipes']['rows'] if row['recipe_id'] != 32]
    result = calculate(c, data, window=100)
    assert result['unlisted'] == {'fixture': 1}
    assert {r['recipe_id'] for r in rows(result)} == {31, 33}
    assert next(r for r in rows(result) if r['recipe_id'] == 31)['needs_pattern']
    unknown = next(r for r in rows(result) if r['recipe_id'] == 33)
    assert unknown['craft_status'] == 'Unknown'
    # Renaming the evidence has no effect on membership or status.
    assert result['professions'][0]['profession'] == 'Arbitrary title'


@pytest.mark.parametrize('rank,expected', [(1, 1), (19, 1), (20, 1), (21, Fraction(40, 39)),
                                          (39, Fraction(40, 21)), (40, 0), (60, 0), (0, 0)])
def test_orange_yellow_green_grey_boundaries(rank, expected):
    assert expected_crafts(progression_catalog()['recipes_by_id'][30], rank) == expected


def test_orange_and_yellow_copper_steps():
    c = progression_catalog()
    entries = [(c, c['recipes_by_id'][30])]
    result = estimate_cost(entries, evidence(c), 19, 75, 22, {1: 10})
    assert result['complete'] and result['cost_copper'] == 30 + 30 + 31
    assert [s['expected_crafts'] for s in result['steps']] == ['1', '1', '40/39']
    assert all(type(s['cost_copper']) is int for s in result['steps'])


@pytest.mark.parametrize('change,reason', [({'skillup_colors': [1, 2, 8, 10]}, 'no qualifying'),
                                         ({'skillup_colors': None}, 'missing colour'),
                                         ({'training_cost_copper': None}, 'training cost unknown')])
def test_gap_colours_training_incomplete(change, reason):
    c = progression_catalog()
    r = c['recipes_by_id'][30]
    r.update(change)
    data = evidence(c)
    if reason == 'training cost unknown':
        data['recipes']['Arbitrary title']['known_recipes']['rows'][0]['learned'] = False
    result = estimate_cost([(c, r)], data, 8, 75, 10, {1: 10})
    assert not result['complete'] and result['cost_copper'] is None
    assert reason in result['reasons'][0]


def test_trainer_once_and_new_trainer_at_required_rank():
    c = progression_catalog()
    base = c['recipes_by_id'][30]
    data = evidence(c)
    data['recipes']['Arbitrary title']['known_recipes']['rows'][0]['learned'] = False
    result = estimate_cost([(c, base)], data, 8, 75, 11, {1: 10})
    assert result['cost_copper'] == 190
    assert [s['training_cost_copper'] for s in result['steps']] == [100, 0, 0]
    next_recipe = c['recipes_by_id'][33]
    next_recipe.update(required_skill=9)
    base['skillup_colors'] = [1, 2, 9, 10]
    result = estimate_cost([(c, base), (c, next_recipe)], data, 8, 75, 11, {1: 10})
    assert [s['recipe_id'] for s in result['steps']] == [30, 33, 33]
    assert [s['training_cost_copper'] for s in result['steps']] == [100, 100, 0]


@pytest.mark.parametrize('prices', [{}, {1: 0}])
def test_missing_material_never_free(prices):
    c = progression_catalog()
    result = estimate_cost([(c, c['recipes_by_id'][30])], evidence(c), 8, 75, 9, prices)
    assert result['cost_copper'] is None and 'missing material price [1]' in result['reasons'][0]


def test_intermediate_without_board_profit_still_costs_cheapest_route():
    c = progression_catalog()
    c['items_by_id'][131]['role'] = 'intermediate'
    result = calculate(c)
    row = next(r for r in rows(result) if r['recipe_id'] == 31)
    assert row['profit_copper'] is None and 'intermediate' in row['board_reason']
    assert row['estimate']['complete']
    # Intermediate material: buy at 1 copper beats crafting at 30 copper.
    c['recipes_by_id'][30]['inputs'] = [{'item_id': 131, 'quantity': 2}]
    c['recipes_by_id'][31]['inputs'] = [{'item_id': 1, 'quantity': 2}]
    r = estimate_cost([(c, c['recipes_by_id'][30])], evidence(c), 8, 75, 9, {1: 10, 131: 1})
    assert r['cost_copper'] == 2
    r = estimate_cost([(c, c['recipes_by_id'][30])], evidence(c), 8, 75, 9, {1: 10})
    assert r['cost_copper'] == 40


def test_comparison_profit_cost_ties_incomplete():
    def group(name, profit, cost, complete=True):
        return {'profession': name, 'best': {'profit_copper': profit,
                'estimate': {'complete': complete, 'cost_copper': cost}}}
    groups = [group('incomplete', 100, None, False), group('costly', 100, 20), group('cheap', 100, 10),
              group('higher', 101, None, False), {'profession': 'empty', 'best': None}, group('missing', None, 1)]
    assert [r['profession'] for r in sorted(groups, key=summary_sort)] == [
        'higher', 'cheap', 'costly', 'incomplete', 'missing', 'empty']


def test_cap_still_lists_beyond_and_unknown_rank_cap():
    result = calculate(data=evidence(max_rank=8))
    assert result['professions'][0]['note'] == 'train the next tier first'
    assert len(rows(result)) == 2
    assert all(r['estimate']['cost_copper'] is None and r['estimate']['reasons'] == ['train the next tier first']
               for r in rows(result))
    assert not rows(calculate(data=evidence(rank=None)))
    assert 'max rank unknown' in rows(calculate(data=evidence(max_rank=None)))[0]['estimate']['reasons']
    assert estimate_cost([], {}, None, 75, 20, {})['reasons'] == ['rank unknown']


def test_newer_bags_rank_cap_share_evidence_and_wrong_skill_ignored():
    data = evidence()
    record = data['recipes']['Arbitrary title']
    data['bags'] = {'captured_at': 101, 'skills': {'modern': {'rows': [
        {'skill_id': 197, 'rank': 12, 'max_rank': 150}, {'skill_id': 186, 'rank': 40, 'max_rank': 75}]}}}
    assert profession_rank(data, record) == (12, 150)
    data['bags']['skills']['modern']['rows'][0].pop('max_rank')
    assert profession_rank(data, record) == (12, None)
    data['bags']['captured_at'] = 99
    assert profession_rank(data, record) == (8, 75)


def test_skill_line_no_list_and_scoping(tmp_path):
    from test_characters import fixture

    from brownstone.professions import latest_data
    from brownstone.today_characters import available_characters
    source = fixture(tmp_path)
    assert not available_characters(latest_data(source | {'source_id': 'other'}))
    assert not available_characters(latest_data(source | {'realm': 'other'}))
    assert calculate(character=('Other', 'Beta', 'Alliance'))['professions'] == []
    with pytest.raises(ValueError, match='source'):
        calculate(snapshot=SNAPSHOT | {'source_id': 'other'})
    with pytest.raises(ValueError, match='market'):
        calculate(snapshot=SNAPSHOT | {'realm': 'other'})
    data = evidence()
    data['bags'] = {'skills': {'modern': {'rows': [{'name': 'Mining', 'skill_id': 186, 'rank': 3, 'max_rank': 75}]}}}
    result = calculate(data=data)
    mining = next(g for g in result['professions'] if g['profession'] == 'Mining')
    assert mining['note'] == 'recipes unknown' and mining['best'] is None
    assert calculate(catalogs=[])['professions'][0]['best'] is None


def test_unsupported_recipe_and_confidence_supply_stale():
    c = progression_catalog()
    c['recipes_by_id'][30]['inputs'] = [{'item_id': 3, 'quantity': 1}]
    r = calculate(c)
    assert 'cycle' in rows(r)[0]['estimate']['reasons'][0].lower()
    c = progression_catalog()
    result = calculate(c, listings={}, metrics={})
    assert all(r['confidence'] == 'Low' and 'insufficient supply' in r['confidence_reasons'] for r in rows(result))
    from datetime import timedelta
    assert all(r['confidence'] == 'Low' for r in rows(calculate(now=NOW + timedelta(days=2))))
    missing = calculate(observations={1: {'min_buyout': 10}})
    assert all(r['profit_copper'] is None and r['board_reason'] == 'missing prices' for r in rows(missing))
    assert all(r['confidence'] == 'Unavailable' for r in rows(missing))
    # A broken finished output keeps the board's reason, without crashing all professions.
    c = deepcopy(c)
    c['recipes_by_id'][31]['inputs'] = [{'item_id': 131, 'quantity': 1}]
    invalid = next(r for r in rows(calculate(c)) if r['recipe_id'] == 31)
    assert invalid['board_reason'] == 'unsupported recipe'


def test_skill_names_do_not_duplicate_or_attribute_recipe_lists():
    data = evidence()
    data['bags'] = {'captured_at': 101, 'skills': {'modern': {'rows': [
        {'name': 'Different title', 'skill_id': 197, 'rank': 12, 'max_rank': 75},
        {'name': 'Arbitrary title', 'skill_id': 186, 'rank': 3, 'max_rank': 75}]}}}
    result = calculate(data=data)
    assert len(result['professions']) == 2
    known_list = next(g for g in result['professions'] if g['recipes'])
    assert known_list['rank'] == 12
    unknown_list = next(g for g in result['professions'] if not g['recipes'])
    assert unknown_list['rank'] == 3 and unknown_list['note'] == 'recipes unknown'


def test_known_recipe_in_window_excluded_unknown_never_skillup():
    c = progression_catalog()
    data = evidence(c)
    surface = data['recipes']['Arbitrary title']['known_recipes']
    surface['rows'][1]['learned'] = True
    assert 31 not in {r['recipe_id'] for r in rows(calculate(c, data))}
    surface['rows'][0]['learned'] = None
    result = estimate_cost([(c, c['recipes_by_id'][30])], data, 8, 75, 9, {1: 10})
    assert result['cost_copper'] is None and 'no qualifying' in result['reasons'][0]


def test_crossing_cap_stops_steps_and_pattern_cannot_skillup():
    c = progression_catalog()
    result = estimate_cost([(c, c['recipes_by_id'][30])], evidence(c), 8, 10, 13, {1: 10})
    assert [r['rank'] for r in result['steps']] == [8, 9]
    assert result['cost_copper'] is None and result['reasons'] == ['train the next tier first']
    c['recipes_by_id'][30]['learned_from'] = [5]
    data = evidence(c)
    data['recipes']['Arbitrary title']['known_recipes']['rows'][0]['learned'] = False
    result = estimate_cost([(c, c['recipes_by_id'][30])], data, 8, 75, 9, {1: 10})
    assert result['cost_copper'] is None


def test_per_craft_profit_honours_output_quantity_and_material_units():
    c = progression_catalog()
    c['recipes_by_id'][31].update(output_quantity=2, inputs=[{'item_id': 1, 'quantity': 3}])
    row = next(r for r in rows(calculate(c)) if r['recipe_id'] == 31)
    assert row['profit_copper'] == 380 - 30  # Two 200c outputs after 5% cut; three 10c materials.


@pytest.mark.parametrize('codes', [[6], [5], [4], [2, 4]])
def test_learnable_band_beats_more_profitable_drop_without_reordering_list(codes):
    c = progression_catalog()
    c['recipes_by_id'][31]['learned_from'] = [2]
    c['recipes_by_id'][33]['learned_from'] = codes
    observations = {1: {'min_buyout': 10}, 131: {'min_buyout': 1000}, 133: {'min_buyout': 200}}
    group = calculate(c, observations=observations)['professions'][0]
    assert [r['recipe_id'] for r in group['recipes']] == [31, 33]
    assert group['recipes'][0]['profit_copper'] > group['best']['profit_copper']
    assert group['best'] is group['recipes'][1]
    assert group['alternative'] is group['recipes'][0]  # The better pattern stays visible to hunt.


@pytest.mark.parametrize('codes,priced', [([6], False), ([2], True), ([99], True), ([], True)])
def test_other_band_fallback_including_unvalued_trainer(codes, priced):
    c = progression_catalog()
    c['recipes_by_id'][31]['learned_from'] = [2]
    c['recipes_by_id'][33]['learned_from'] = codes
    observations = {1: {'min_buyout': 10}, 131: {'min_buyout': 1000}}
    if priced:
        observations[133] = {'min_buyout': 200}
    group = calculate(c, observations=observations)['professions'][0]
    assert group['best']['recipe_id'] == 31
    assert group['alternative'] is None
    if not priced:
        assert group['recipes'][1]['profit_copper'] is None


def test_band_keeps_summary_sort_and_loss_making_learnable_becomes_alternative():
    c = progression_catalog()
    c['recipes_by_id'][31]['learned_from'] = [2]
    c['recipes_by_id'][32]['learned_from'] = [5]
    c['recipes_by_id'][33]['learned_from'] = [4]
    observations = {1: {'min_buyout': 10}, 131: {'min_buyout': 1000},
                    132: {'min_buyout': 40}, 133: {'min_buyout': 30}}
    group = calculate(c, observations=observations, window=26)['professions'][0]
    assert group['best']['recipe_id'] == 32
    assert group['best']['profit_copper'] == 8
    assert group['alternative']['recipe_id'] == 31
    observations[132] = {'min_buyout': 20}
    group = calculate(c, observations=observations, window=26)['professions'][0]
    assert group['best']['recipe_id'] == 31  # No profitable learnable recipe: the drop leads.
    assert group['alternative']['recipe_id'] == 33 and group['alternative']['profit_copper'] < 0
    observations[133] = {'min_buyout': 32}  # floor(32 * .95) - 30 = 0.
    group = calculate(c, observations=observations, window=26)['professions'][0]
    assert group['best']['recipe_id'] == 31
    assert group['alternative']['recipe_id'] == 33 and group['alternative']['profit_copper'] == 0


def test_groups_carry_evidenced_skill_ids_without_name_inference():
    data = evidence()
    data['bags'] = {'skills': {'modern': {'rows': [
        {'name': 'Unrelated title', 'skill_id': 186, 'rank': 3, 'max_rank': 75}]}}}
    groups = calculate(data=data)['professions']
    assert {g['profession']: g['skill_id'] for g in groups} == {'Arbitrary title': 197, 'Unrelated title': 186}
    data['recipes']['Arbitrary title']['known_recipes'].pop('skill_id')
    assert next(g for g in calculate(data=data)['professions'] if g['recipes'])['skill_id'] is None


def test_today_plan_identical_to_before_story070():
    import json
    from pathlib import Path

    from test_today import plan

    from brownstone.today import TODAY_VERSION

    before = json.loads((Path(__file__).parent / 'fixtures/today_story070.json').read_text())
    assert json.loads(json.dumps(plan(), default=str)) == before
    assert TODAY_VERSION == before['today_version'] == 13
