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
