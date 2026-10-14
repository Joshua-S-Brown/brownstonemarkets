"""Wowhead's learnedat 9999 means no skill requirement; it never becomes a skill level or band (CRAFT-08/10)."""
import tomllib
from pathlib import Path

import pytest
from test_recipe_import import PAGE, selection
from test_today import catalog
from test_today_characters import recipe, state

from brownstone.crafting import NO_SKILL_SENTINEL, parse_recipe_catalog
from brownstone.market_explorer import skill_demand
from brownstone.recipe_import import build_catalog, dumps_catalog, extract_page
from brownstone.skillups import recipe_placement
from brownstone.today_characters import recipe_status

ROOT = Path(__file__).resolve().parents[1]
# The saved Forever First Aid page lists First Aid Kit 1230117 this way, with no colors.
SENTINEL_PAGE = PAGE.replace('"learnedat":45,', '"learnedat":9999,')


def sentinel_catalog():
    return build_catalog(extract_page(SENTINEL_PAGE, 'sha', '2026-10-06'), selection())


def test_generator_leaves_the_sentinel_skill_unknown():
    bag = sentinel_catalog()['recipes'][1]
    assert bag['recipe_id'] == 3755 and 'required_skill' not in bag
    assert 'required_skill' not in dumps_catalog(sentinel_catalog()).split('recipe_id = 3755')[1]
    assert sentinel_catalog()['recipes'][0]['required_skill'] == 1  # Real levels are copied unchanged.


@pytest.mark.parametrize('skill', [NO_SKILL_SENTINEL, 10000, -1, True, 1.5, '45'])
def test_loader_rejects_sentinel_and_malformed_skill(skill):
    raw = catalog()
    raw['recipes'][0]['required_skill'] = skill
    with pytest.raises(ValueError, match='required_skill'):
        parse_recipe_catalog(raw)


@pytest.mark.parametrize('skill', [0, 1, 320])
def test_loader_accepts_real_skill_levels(skill):
    raw = catalog()
    raw['recipes'][0]['required_skill'] = skill
    assert parse_recipe_catalog(raw)['recipes'][0]['required_skill'] == skill


def test_unknown_skill_is_never_a_band_on_the_item_page():
    parsed = parse_recipe_catalog(sentinel_catalog())
    assert recipe_placement(parsed['recipes_by_id'][3755]) == (['skill unknown'], 'skill unknown', True)
    linen = next(row for row in skill_demand([parsed]) if row['item_id'] == 2589)
    assert linen['bands'] == ['1–24', 'skill unknown']  # Bolt at skill 1; the bag's 9975–9999 is gone.


def test_unknown_skill_never_reads_as_trainable():
    status = recipe_status(recipe(required_skill=None), state(rank=300))
    assert status == {'craft_status': 'Unknown', 'character_reason': 'required skill unknown',
                      'training_cost_copper': None}


def test_tracked_catalogs_hold_no_sentinel():
    for path in sorted(ROOT.glob('config/*-*.toml')):
        recipes = tomllib.loads(path.read_text(encoding='utf-8')).get('recipes', [])
        assert all(r.get('required_skill', 0) < NO_SKILL_SENTINEL for r in recipes), path.name
