"""Team native user fixture over synthetic scoped saved evidence."""
from uuid import uuid4

import pytest
from app_helpers import app
from nicegui import app as nicegui_app
from nicegui import ui
from test_progression import evidence, progression_catalog
from test_today_characters import CHARACTER

from views.nicegui_team import summary_rows, team_results

pytestmark = pytest.mark.asyncio


def team_app(tmp_path, monkeypatch):
    _, source, _ = app(tmp_path, monkeypatch)
    c = progression_catalog()
    from brownstone.pipeline import run
    csv = tmp_path / 'progression.csv'
    csv.write_text('itemId,name,marketValue,minBuyout,recent,historical,updatedAt\n'
                   '1,Material,20,10,0,0,\n3,Known,2000,2000,0,0,\n'
                   '131,Next,3000,3000,0,0,\n132,Farther,2000,2000,0,0,\n133,Near,2000,2000,0,0,\n')
    run(source, csv)
    other = ('Keenagen', 'Beta', 'Alliance')
    data = {CHARACTER: evidence(c), other: evidence(c, rank=3)}
    for identity, state in data.items():
        state.update(history=[], observations=[({'captured_at': 100, 'sequence': 2}, 'fixture-machine')])
        state['bags'] = {'captured_at': 100, 'level': 5 if identity == CHARACTER else None, 'gold_copper': 255,
                         'skills': {'modern': {'rows': [{'name': 'Arbitrary title', 'skill_id': 197,
                                                        'rank': 8 if identity == CHARACTER else 3, 'max_rank': 75}]}}}
    data[CHARACTER]['history'] = [{'captured_at': 100, 'sequence': 2, 'level': 5}]
    monkeypatch.setattr('brownstone.professions.latest_data',
                        lambda config: data if config['source_id'] == 'test' else {})
    monkeypatch.setattr('brownstone.recipe_catalogs.find_catalogs', lambda *args: [{'name': 'fixture', 'catalog': c}])
    return source, c, data


async def test_roster_next_steps_choice_window_summary_and_isolation(user, tmp_path, monkeypatch):
    source, c, data = team_app(tmp_path, monkeypatch)
    await user.open('/?place=Team')
    await user.should_see('Progression')
    await user.should_see('Basilly')
    await user.should_see('Keenagen')
    assert len(user.find(marker='team-character').elements) == 2
    await user.should_see('Level 5 · Gold 2s 55c')
    user.find(marker='page-info').click()
    await user.should_see('stale')
    await user.should_see('Next step · Arbitrary title: Recipe 31 · +25 points')
    user.find(marker='page-info').click()
    await user.should_see('Current-scan profit, not a forecast')
    await user.should_see(f"rules {source['rules_version']}")
    await user.should_see('Cost to reach: cheapest usable skill-up craft')
    choice = next(e for e in user.find(ui.select).elements if e.label == 'Progression character')
    assert choice.value == '0' and len(choice.options) == 2
    summary = next(e for e in user.find(ui.table).elements if 'Profession' in e._markers and 'summary' in e._markers)
    from datetime import UTC, datetime

    from brownstone.today_loading import load_today
    from brownstone.today_settings import TodaySettings
    _, arguments = load_today(source, [c], TodaySettings(), data, datetime.now(UTC))
    result = team_results([c], data, arguments, 25)[CHARACTER]
    assert summary.rows == [r | {'id': i} for i, r in enumerate(summary_rows(result))]
    slider = next(iter(user.find(marker='reach-window').elements))
    with user.client:
        slider.set_value(26)
    # Intermediate movement doesn't rebuild; release commits the look-ahead.
    await user.should_not_see('Recipe 32 · skill 34 · +26 points')
    user.find(marker='reach-window').trigger('change')
    await user.should_see('Recipe 32 · skill 34 · +26 points')
    with user.client:
        selection = user.find(marker='team-character')
        selection.elements.intersection_update(
            e for e in selection.elements if e._props['aria-label'] == 'Select Keenagen')
        selection.click()
    await user.should_see('Recipe 33 · skill 13 · +10 points')
    await user.should_not_see('Recipe 32 · skill 34 · +31 points')
    with user.client:
        assert nicegui_app.storage.tab['team-test']['window'] == 26
        assert nicegui_app.storage.tab['team-test']['character'] == list(list(data)[1])
    # Same browser tab retains choice and slider when leaving and returning.
    await user.open('/?place=Market')
    await user.open('/?place=Team')
    await user.should_see('Progression')
    assert next(e for e in user.find(ui.select).elements if e.label == 'Progression character').value == '1'
    assert next(iter(user.find(marker='reach-window').elements)).value == 26
    other = source | {'source_id': 'other'}
    monkeypatch.setattr('brownstone.config.read_sources', lambda *args: [source, other])
    await user.open('/?game=classic&source=other&place=Team')
    await user.should_see('No characters imported for this source')
    await user.should_not_see('Basilly')
    user.tab_id = str(uuid4())
    await user.open('/?game=classic&source=test&place=Team')
    await user.should_see('Progression')
    assert next(e for e in user.find(ui.select).elements if e.label == 'Progression character').value == '0'
    assert next(iter(user.find(marker='reach-window').elements)).value == 25


async def test_no_snapshot_roster_missing_choice_and_evidence_errors(user, tmp_path, monkeypatch):
    source, _, data = team_app(tmp_path, monkeypatch)
    # Switch to a source without a scan but with explicitly supplied character evidence.
    monkeypatch.setattr('brownstone.config.read_sources', lambda *args: [source | {'source_id': 'empty'}])
    monkeypatch.setattr('brownstone.professions.latest_data', lambda config: data)
    await user.open('/?place=Team')
    await user.should_see('No snapshot for this source and market')
    assert len(user.find(marker='team-character').elements) == 2
    with user.client:
        nicegui_app.storage.tab['team-empty']['character'] = ['Gone', 'Beta', 'Alliance']
    await user.open('/?place=Team')
    await user.should_see('Progression')
    assert next(e for e in user.find(ui.select).elements if e.label == 'Progression character').value == '0'

    def broken(config):
        raise OSError('fixture unreadable')

    monkeypatch.setattr('brownstone.professions.latest_data', broken)
    await user.open('/?place=Team')
    # Evidence is read once; its failure is explained, never retried by the roster cards.
    await user.should_see('Unable to read character evidence: fixture unreadable')
    await user.should_see('No characters imported for this source')


async def test_unknown_bags_empty_history_recipes_unknown_and_pattern(user, tmp_path, monkeypatch):
    _, c, data = team_app(tmp_path, monkeypatch)
    data[CHARACTER]['bags'] = {}
    data[CHARACTER]['history'] = []
    c['recipes_by_id'][31]['learned_from'] = [5]
    data[CHARACTER]['recipes']['Arbitrary title']['known_recipes']['possibly_incomplete'] = True
    # Bags-only skill: no recipe attribution by profession names.
    data[list(data)[1]]['recipes'] = {}
    await user.open('/?place=Team')
    await user.should_see('Basilly')
    user.find(marker='page-info').click()
    await user.should_see('No readable bags snapshot')
    await user.should_see('No readable level or rank history yet.')
    await user.should_see('recipes unknown')
    await user.should_see('needs pattern or other source')
    await user.should_see('Unknown')
    await user.should_see('Training: cost unknown')


async def test_learn_from_column_unknown_tile_note_roster_and_comparison(user, tmp_path, monkeypatch):
    _, c, _ = team_app(tmp_path, monkeypatch)
    c['recipes_by_id'][31]['learned_from'] = [2]
    c['recipes_by_id'][33]['learned_from'] = [6]
    await user.open('/?place=Team')
    await user.should_see('needs skill 13 · trainer')
    await user.should_see('Pattern worth hunting')
    await user.should_see('look for the pattern on the auction house or farm it; drops are not guaranteed')
    await user.should_see('Next step · Arbitrary title: Recipe 33 · +5 points')
    reachable = next(e for e in user.find(ui.table).elements if 'Reachable' in e._markers)
    assert [r['Recipe'] for r in reachable.rows] == ['Recipe 31', 'Recipe 33']
    assert [r['Learn from'] for r in reachable.rows] == ['drop', 'trainer']
    assert any(col['label'] == 'Learn from' for col in reachable.columns)
    summary = next(e for e in user.find(ui.table).elements if 'summary' in e._markers)
    assert summary.rows[0]['Best reachable recipe'] == 'Recipe 33'
    from views.nicegui_team import reachable_rows
    missing = c['recipes_by_id'][33] | {'points_needed': 5, 'profit_copper': None,
        'estimate': {'complete': False, 'reasons': ['missing']}, 'confidence': 'Unavailable', 'learned_from': []}
    assert reachable_rows({'recipes': [missing]})[0]['Learn from'] == 'unknown'


async def test_drop_best_offers_learnable_route_and_no_tile_without_alternative(user):
    from views.nicegui_team import progression_detail

    def recipe(name, codes, profit):
        return {'name': name, 'learned_from': codes, 'profit_copper': profit, 'required_skill': 10,
                'points_needed': 2, 'estimate': {'complete': True, 'cost_copper': 240, 'steps': []},
                'confidence': 'Medium', 'craft_status': 'Not yet', 'needs_pattern': False, 'character_reason': '',
                'board_reason': '', 'confidence_reasons': []}

    drop, trainer = recipe('Raptor Bites', [2], 194), recipe('Wolf Meat', [6], -45)

    @ui.page('/alternative')
    def page():
        progression_detail({'professions': [
            {'profession': 'Cooking', 'skill_id': 185, 'rank': 2, 'max_rank': 75, 'recipes': [drop, trainer],
             'best': drop, 'alternative': trainer, 'note': ''},
            {'profession': 'Tailoring', 'skill_id': 197, 'rank': 2, 'max_rank': 75, 'recipes': [drop],
             'best': drop, 'alternative': None, 'note': ''}]})

    await user.open('/alternative')
    await user.should_see('Or learn now')
    await user.should_see('trainer · -45c per craft · needs skill 10 · reliable while you look for the pattern')
    await user.should_not_see('Pattern worth hunting')


@pytest.mark.parametrize('name,skill_id,sentence', [
    ('Mining', 186, 'Mining levels by gathering, not crafting'),
    ('Unrelated title', 182, 'Unrelated title levels by gathering, not crafting'),
    ('Skinning', 393, 'Skinning levels by gathering, not crafting'),
    ('Fishing', 356, 'Fishing levels by gathering, not crafting'),
    ('Tailoring', 197, 'No catalog recipe within the next 25 points'),
    ('Mining', None, 'No catalog recipe within the next 25 points'),
])
async def test_empty_profession_sentence_by_skill_id_without_empty_tables(user, name, skill_id, sentence):
    from views.nicegui_team import progression_detail

    @ui.page('/empty-team')
    def page():
        progression_detail({'professions': [{'profession': name, 'skill_id': skill_id, 'rank': 1,
                           'max_rank': 75, 'recipes': [], 'best': None, 'note': 'recipes unknown'}]})

    await user.open('/empty-team')
    await user.should_see(sentence)
    assert not any('Reachable' in e._markers for e in user.find(ui.table).elements)
    assert all(e.rows for e in user.find(ui.table).elements)
    await user.should_not_see('No data available')


@pytest.mark.parametrize('training,profit,expected', [
    (100, 30, 'pays back training in 4 crafts'),
    (100, 25, 'pays back training in 4 crafts'),
    (100, 0, 'pays back training: never'),
    (100, -1, 'pays back training: never'),
    (100, None, 'pays back training: unknown'),
    (0, 30, 'Training: 0c'),
    (None, 30, 'Training: cost unknown'),
])
async def test_training_payback_rounding_never_unknown_and_absent(user, training, profit, expected):
    from views.nicegui_team import recipe_details

    @ui.page('/training-payback')
    def page():
        recipe = {'name': 'Fixture recipe', 'required_skill': 10, 'points_needed': 2,
                  'craft_status': 'Not yet', 'needs_pattern': False, 'character_reason': '',
                  'profit_copper': profit, 'board_reason': '', 'confidence': 'Medium',
                  'confidence_reasons': [], 'estimate': {'complete': True, 'cost_copper': 100, 'steps': []}}
        if training is not None:
            recipe['training_cost_copper'] = training
        recipe_details({'recipes': [recipe]})

    await user.open('/training-payback')
    await user.should_see(expected)
    if not training:
        await user.should_not_see('pays back training')
    await user.should_not_see(kind=ui.table)


async def test_team_cost_steps_show_money_and_profit_columns_sort_by_copper(user):
    from views.nicegui_team import progression_detail

    step = {'rank': 2, 'catalog_id': 'c', 'recipe_id': 31, 'recipe': 'Recipe 31', 'expected_crafts': '1',
            'cost_copper': 10250, 'training_cost_copper': None}
    recipes = [{'name': name, 'learned_from': [6], 'profit_copper': profit, 'required_skill': 10,
                'points_needed': 2, 'estimate': {'complete': True, 'cost_copper': 10250, 'steps': [step]},
                'confidence': 'Medium', 'craft_status': 'Not yet', 'needs_pattern': False, 'character_reason': '',
                'board_reason': '', 'confidence_reasons': []} for name, profit in (('Big', 10200), ('Small', 5000))]

    @ui.page('/cost-steps')
    def page():
        progression_detail({'professions': [{'profession': 'Cooking', 'skill_id': 185, 'rank': 2, 'max_rank': 75,
                                             'recipes': recipes, 'best': recipes[0], 'alternative': None,
                                             'note': ''}]})

    await user.open('/cost-steps')
    tables = {' '.join(e._markers): e for e in user.find(ui.table).elements}
    steps = tables['Cost steps']
    assert [(r['Cost'], r['Training']) for r in steps.rows] == [('1g 2s 50c', 'unknown')]
    assert [c['label'] for c in steps.columns] == ['Rank', 'Recipe', 'Expected crafts', 'Cost', 'Training']
    for label, column in (('Reachable recipes', 'Earns per craft'), ('Profession summary', 'Profit per craft')):
        assert ':sort' in next(c for c in tables[label].columns if c['name'] == column)
