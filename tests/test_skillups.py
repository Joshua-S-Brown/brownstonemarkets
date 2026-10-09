"""CRAFT-10 expectations use synthetic catalogs; no local data or network."""
from copy import deepcopy

import pytest
from test_today import catalog

from brownstone.crafting import material_plan, parse_recipe_catalog
from brownstone.skillups import build_skillups, coverage_line, recipe_placement


@pytest.mark.parametrize('skill,band', [(24, '1–24'), (25, '25–49'), (49, '25–49'), (50, '50–74')])
def test_band_boundaries_unknown_range(skill, band):
    assert recipe_placement({'required_skill': skill}) == ([band], 'skill-up range unknown', True)


def test_spanning_three_bands_green_exclusive_unknown_and_zero_width():
    assert recipe_placement({'required_skill': 1, 'skillup_colors': [24, 30, 51, 75]})[0] == [
        '1–24', '25–49', '50–74']
    assert recipe_placement({'required_skill': 1, 'skillup_colors': [1, 25, 50, 75]})[0] == ['1–24', '25–49']
    assert recipe_placement({'skillup_colors': [1, 25, 50, 75]})[0] == ['skill unknown']
    assert recipe_placement({}) == (['skill unknown'], 'skill unknown', True)
    assert recipe_placement({'skillup_colors': [30, 30, 30, 40]}) == (
        ['skill unknown'], 'skill unknown; no reliable skill-ups', False)
    assert recipe_placement({'required_skill': 50, 'skillup_colors': [50, 50, 50, 75]}) == (
        ['50–74'], 'no reliable skill-ups', False)
    c = catalog()
    c['recipes'][0]['skillup_colors'] = [1, 1, 1, 25]
    assert build_skillups([c])['direct'] == build_skillups([c])['raw'] == []


@pytest.mark.parametrize('n', [1, 5, 50])
def test_n_and_unique_recipe_totals_across_bands_and_professions(n):
    c = catalog()
    c['recipes'][0]['skillup_colors'] = [1, 25, 51, 75]
    other = deepcopy(c)
    other['profession'] = 'engineering'
    other['recipes'][0]['profession'] = 'engineering'
    plan = build_skillups([c, other], n)
    assert len(plan['groups'][0]['bands']) == 3
    assert plan['raw'][0]['units'] == 4 * n
    assert plan['raw'][0]['professions'] == ['engineering', 'tailoring']
    assert plan['raw'][0]['bands'] == ['1–24', '25–49', '50–74']
    assert plan['groups'][0]['raw'][0]['units'] == 2 * n


@pytest.mark.parametrize('n', [0, 51, 1.5, True])
def test_n_rejected(n):
    with pytest.raises(ValueError, match='1 to 50'):
        build_skillups([catalog()], n)


def chain_catalog():
    c = catalog()
    c['items'] += [{'item_id': i, 'name': name, 'role': 'intermediate', 'source_url': 'https://example.com'}
                   for i, name in [(4, 'Thread'), (5, 'Bolt')]]
    r = c['recipes'][0]
    r['inputs'] = [{'item_id': 5, 'quantity': 3}]
    c['recipes'] += [{**r, 'recipe_id': 40, 'output_item_id': 4, 'required_skill': 25,
                      'inputs': [{'item_id': 1, 'quantity': 2}]},
                     {**r, 'recipe_id': 50, 'output_item_id': 5, 'required_skill': 50,
                      'inputs': [{'item_id': 4, 'quantity': 2}]}]
    return parse_recipe_catalog(c)


def test_intermediate_chain_and_routes_stay_in_catalog():
    c = chain_catalog()
    plan = build_skillups([c])
    assert plan['groups'][0]['recipes'][0]['raw'] == {1: 60}
    assert plan['raw'][0]['units'] == 90  # item + bolt + thread, each once
    other = catalog()
    other['recipes'][0]['inputs'] = [{'item_id': 4, 'quantity': 1}]
    other['items'].append({'item_id': 4, 'name': 'Thread', 'role': 'material', 'source_url': 'https://example.com'})
    other = parse_recipe_catalog(other)
    assert build_skillups([c, other])['groups'][1]['raw'][0]['item_id'] == 4


@pytest.mark.parametrize('failure', ['fractional', 'cycle'])
def test_expansion_errors_add_no_partial_raw_units(failure):
    c = chain_catalog()
    if failure == 'fractional':
        c['recipes_by_id'][50]['output_quantity'] = 2
    else:
        c['recipes_by_id'][40]['inputs'] = [{'item_id': 5, 'quantity': 1}]
    r = build_skillups([c])['groups'][0]['recipes'][0]
    assert r['error'] and r['raw'] == {} and r['direct'] == {5: 15}


def test_raw_expansion_uses_all_n_crafts_before_checking_fractions():
    c = chain_catalog()
    c['recipes_by_id'][50]['output_quantity'] = 5  # 3 bolts per craft: fractional for 1 craft, whole for 5
    assert build_skillups([c], 1)['groups'][0]['recipes'][0]['error']
    r = build_skillups([c], 5)['groups'][0]['recipes'][0]
    assert r['error'] is None and r['raw'] == {1: 12}


def test_post_launch_listed_excluded_then_included_and_coverage():
    c = catalog()
    c['recipes'][0]['availability'] = 'post-launch'
    p = build_skillups([c])
    assert p['excluded'] == 1 and len(p['groups'][0]['bands'][0]['recipes']) == 1
    assert p['raw'] == [] and build_skillups([c], include_post_launch=True)['raw'][0]['units'] == 10
    assert coverage_line(c) == 'coverage unknown; regenerate the catalog'
    c['page_coverage'] = {'usable': 10, 'no_item': 20, 'unknown_yield': 1}
    c['verified_at'] = '2026-10-08'
    assert coverage_line(c) == ("Catalog holds 1 of 10 usable recipes on its saved page (saved 2026-10-08); "
                                "20 recipes on the page create no item and aren't counted")
    assert build_skillups([c])['partial']
    c['page_coverage']['usable'] = 1
    assert not build_skillups([c])['partial']


def test_unknown_skill_group_and_empty_bands_through_highest_reached():
    c = catalog()
    c['recipes'][0].pop('required_skill')
    group = build_skillups([c])['groups'][0]
    assert [b['label'] for b in group['bands']] == ['skill unknown']
    assert group['direct'][0]['units'] == 10
    c['recipes'][0]['required_skill'] = 50
    group = build_skillups([c])['groups'][0]
    assert [b['label'] for b in group['bands']] == ['1–24', '25–49', '50–74']
    assert group['bands'][0]['recipes'] == group['bands'][1]['recipes'] == []


def test_raw_material_flag_stops_expansion_but_keeps_the_recipe():
    c = chain_catalog()
    c['items_by_id'][5].update(raw_material=True, raw_material_note='Bought directly.')
    plan = build_skillups([c])
    assert plan['groups'][0]['recipes'][0]['raw'] == {5: 15}
    assert 50 in {row['recipe']['recipe_id'] for row in plan['groups'][0]['recipes']}
    assert material_plan(c, 30) == {1: 12}  # The board's expansion is unchanged.
