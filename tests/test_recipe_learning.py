"""STORY-050: source evidence is optional, lossless, validated and displayed only in catalogs."""
import json
from copy import deepcopy

import pytest
from test_recipe_catalogs import make_workspace
from test_recipe_import import PAGE, selection
from test_today import catalog

from brownstone import recipe_catalogs as rc
from brownstone.crafting import parse_recipe_catalog
from brownstone.recipe_import import build_catalog, dumps_catalog, extract_page


def page(source=None, cost=None):
    return PAGE.replace('"learnedat":45,',
                        f'"learnedat":45,"source":{json.dumps(source)},"trainingcost":{json.dumps(cost)},')


@pytest.mark.parametrize('source', [[1], [2], [4], [5], [6], [16], [21], [2, 5], [99], [5, 2, 5]])
def test_each_code_and_multiple_codes_preserved_in_page_order(source):
    result = build_catalog(extract_page(page(source, 100), 'sha', '2026-10-08'), selection())
    bag = result['recipes'][1]
    assert bag['learned_from'] == source
    assert bag['training_cost_copper'] == 100
    labels = {2: 'drop', 4: 'quest', 5: 'vendor', 6: 'trainer'}
    assert rc.learning_label(bag) == ', '.join(labels.get(c, f'other (code {c})') for c in source)
    assert parse_recipe_catalog(result)['recipes_by_id'][3755]['learned_from'] == source


@pytest.mark.parametrize('source', [None, [], '6', 6, [True], [0], [-1], [6, '5'], [2.5]])
def test_missing_or_malformed_source_absent(source):
    result = build_catalog(extract_page(page(source), 'sha', '2026-10-08'), selection())
    assert 'learned_from' not in result['recipes'][1]
    assert rc.learning_label(result['recipes'][1]) == 'unknown'
    assert rc.learning_label(result['recipes'][0]) == 'unknown'  # Skill 1 alone proves no starting status.


@pytest.mark.parametrize('cost', [None, '100', True, 0, -1, 1.5, [], {}])
def test_missing_or_malformed_training_cost_absent(cost):
    result = build_catalog(extract_page(page([6], cost), 'sha', '2026-10-08'), selection())
    assert 'training_cost_copper' not in result['recipes'][1]


@pytest.mark.parametrize('cost', [1, 100, 10000])
def test_explicit_integer_training_cost_copper(cost):
    result = build_catalog(extract_page(page([6], cost), 'sha', '2026-10-08'), selection())
    assert parse_recipe_catalog(result)['recipes_by_id'][3755]['training_cost_copper'] == cost


@pytest.mark.parametrize(('field', 'value'), [('learned_from', []), ('learned_from', [True]),
                                             ('learned_from', [0]), ('learned_from', '6'),
                                             ('training_cost_copper', True), ('training_cost_copper', 0),
                                             ('training_cost_copper', -1),
                                             ('training_cost_copper', 1.5), ('training_cost_copper', '100')])
def test_loader_rejects_malformed_learning_fields(field, value):
    raw = catalog()
    raw['recipes'][0][field] = value
    with pytest.raises(ValueError, match=field):
        parse_recipe_catalog(raw)


def test_older_catalog_loads_and_selection_cannot_override_page_evidence():
    assert parse_recipe_catalog(catalog())['recipes_by_id']
    pick = selection(recipe_defaults={'learned_from': [99], 'training_cost_copper': 999})
    result = build_catalog(extract_page(PAGE, 'sha', '2026-10-08'), pick)
    assert all('learned_from' not in r and 'training_cost_copper' not in r for r in result['recipes'])


def test_save_and_regeneration_change_only_learning_fields_and_version(tmp_path):
    config, archive = make_workspace(tmp_path)
    entry, = rc.find_catalogs(config)
    raw = page([2, 5], 100).encode()
    legacy = rc.preview_update(entry, raw, '2026-10-01')['catalog']
    legacy['catalog_version'] = '0.1'
    legacy['recipes'][1].pop('learned_from')
    legacy['recipes'][1].pop('training_cost_copper')
    entry['catalog_path'].write_text(dumps_catalog(legacy))
    entry, = rc.find_catalogs(config)
    before = deepcopy(entry['catalog'])
    result = rc.regenerate(entry, raw, 'fixture.html', '2026-10-01', archive)
    after = deepcopy(result['catalog'])
    assert after['catalog_version'] == '0.2'
    after['catalog_version'] = before['catalog_version']
    assert after['recipes'][1].pop('learned_from') == [2, 5]
    assert after['recipes'][1].pop('training_cost_copper') == 100
    assert after == before
    updated, = rc.find_catalogs(config)
    assert not rc.preview_update(updated, raw, '2026-10-01')['changed']
