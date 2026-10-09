"""New optional catalog fields from synthetic saved-page fixtures."""
from copy import deepcopy

import pytest
from test_recipe_import import PAGE, selection
from test_today import catalog

from brownstone.crafting import parse_recipe_catalog
from brownstone.recipe_import import build_catalog, dumps_catalog, extract_page


@pytest.mark.parametrize('colors', [[1, 25, 37, 50], None, [0, 25, 37, 50], [1, 37, 25, 50],
                                   [1, 2.5, 3, 4], [True, 2, 3, 4], [1, 2, 3]])
def test_generator_colors_copied_or_omitted(colors):
    import json
    text = PAGE.replace('"learnedat":45,', f'"learnedat":45,"colors":{json.dumps(colors)},')
    result = build_catalog(extract_page(text, 'sha', '2026-10-08'), selection())
    recipe = result['recipes'][1]
    if colors == [1, 25, 37, 50]:
        assert recipe['skillup_colors'] == colors
    else:
        assert 'skillup_colors' not in recipe


def test_page_coverage_and_unchanged_page_regeneration_changes_only_new_fields():
    import json
    import tomllib
    extra = [{'id': 8, 'name': 'Enchant', 'reagents': [[2589, 1]]},
             {'id': 9, 'name': 'Rank'},
             {'id': 10, 'name': 'Season', 'creates': [4238, 1, 1], 'reagents': [[2589, 1]], 'seasonId': 2}]
    text = PAGE.replace('var listviewspells = [', 'var listviewspells = '+json.dumps(extra)[:-1]+',')
    page = extract_page(text, 'sha', '2026-10-08')
    result = build_catalog(page, selection())
    assert result['page_coverage'] == {'usable': 2, 'no_item': 1, 'unknown_yield': 1}
    assert tomllib.loads(dumps_catalog(result)) == result
    before = deepcopy(result)
    before.pop('page_coverage')
    page['recipes']['3755']['skillup_colors'] = [45, 50, 60, 75]
    after = build_catalog(page, selection(catalog_version='0.2'))
    assert after['recipes'][1].pop('skillup_colors') == [45, 50, 60, 75]
    after.pop('page_coverage')
    after['catalog_version'] = '0.1'
    assert after == before


@pytest.mark.parametrize('colors', [[0, 1, 2, 3], [1, 3, 2, 4], [1, 2, 3], [1, 2, 3, 4.5], [True, 2, 3, 4]])
def test_parser_rejects_colors(colors):
    c = catalog()
    c['recipes'][0]['skillup_colors'] = colors
    with pytest.raises(ValueError, match='skillup_colors'):
        parse_recipe_catalog(c)


@pytest.mark.parametrize('counts', [{'usable': -1, 'no_item': 0, 'unknown_yield': 0},
                                   {'usable': True, 'no_item': 0, 'unknown_yield': 0},
                                   {'usable': 1.5, 'no_item': 0, 'unknown_yield': 0}, {}, None])
def test_parser_rejects_coverage(counts):
    c = catalog()
    c['page_coverage'] = counts
    with pytest.raises(ValueError, match='page_coverage'):
        parse_recipe_catalog(c)


def test_parser_accepts_new_fields_and_old_catalogs():
    c = catalog()
    assert parse_recipe_catalog(c)['recipes_by_id']
    c['page_coverage'] = {'usable': 1, 'no_item': 0, 'unknown_yield': 0}
    c['recipes'][0]['skillup_colors'] = [1, 1, 1, 25]
    assert parse_recipe_catalog(c)['recipes_by_id'][30]['skillup_colors'] == [1, 1, 1, 25]


def test_save_catalog_fields_and_version_bump_match_generator(tmp_path):
    import tomllib

    from test_recipe_catalogs import make_workspace

    from brownstone import recipe_catalogs as rc
    config, archive = make_workspace(tmp_path)
    entry, = rc.find_catalogs(config)
    raw = PAGE.replace('"learnedat":45,', '"learnedat":45,"colors":[45,50,60,75],').encode()
    result = rc.regenerate(entry, raw, 'fixture.html', '2026-10-08', archive)
    written = tomllib.loads(entry['catalog_path'].read_text())
    assert written['page_coverage'] == {'usable': 2, 'no_item': 0, 'unknown_yield': 1}
    assert written['recipes'][1]['skillup_colors'] == [45, 50, 60, 75]
    assert written['catalog_version'] == '0.2'
    assert written == result['catalog']
    updated, = rc.find_catalogs(config)
    assert not rc.preview_update(updated, raw, '2026-10-08')['changed']


@pytest.mark.parametrize('flag', [{'raw_material': True}, {'raw_material': False, 'raw_material_note': 'n'},
                                  {'raw_material': 'yes', 'raw_material_note': 'n'}])
def test_parser_rejects_raw_material_without_true_and_note(flag):
    c = catalog()
    c['items'][0].update(flag)
    with pytest.raises(ValueError, match='raw_material'):
        parse_recipe_catalog(c)
