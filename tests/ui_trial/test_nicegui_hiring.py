"""New-hire disclosures reuse Team styling and compute tier feeds only on first opening."""
import pytest
from nicegui import ui

from brownstone import hiring
from tests.ui_trial.test_nicegui_team import team_app
from views.nicegui_team import hiring_section

pytestmark = pytest.mark.asyncio


async def test_team_hiring_lazy_detail_labels_and_repeat_open(user, tmp_path, monkeypatch):
    team_app(tmp_path, monkeypatch)
    original = hiring.detail
    calls = []

    def detail(context, row):
        calls.append(row['profession'])
        return original(context, row)

    monkeypatch.setattr(hiring, 'detail', detail)
    await user.open('/?place=Team')
    await user.should_see('Add a character?')
    await user.should_see('Instead of a new hire')
    await user.should_see('no catalog: gathering income and supply are not modelled')
    await user.should_see('listings never sales')
    assert calls == []
    # Below the roster and the selected character's next steps.
    assert min(e.id for e in user.find(marker='hiring-section').elements) > max(
        e.id for e in user.find(marker='reach-window').elements)
    user.find(marker='hire-tailoring').trigger('update:modelValue', True)
    await user.should_see('New hire: rank 1, no known recipes')
    await user.should_see('character level 35')
    await user.should_see('tier fees not included (unknown)')
    await user.should_see('What it feeds: feeds nothing')
    await user.should_see('incomplete: Rank 40: no qualifying skill-up craft')
    assert calls == ['tailoring']
    user.find(marker='hire-tailoring').trigger('update:modelValue', False)
    user.find(marker='hire-tailoring').trigger('update:modelValue', True)
    assert calls == ['tailoring']
    # Changing the reach window refreshes the roster but keeps the opened hire row and its detail.
    user.find(marker='reach-window').trigger('change', 30)
    await user.should_see('New hire: rank 1, no known recipes')
    assert calls == ['tailoring']
    assert next(iter(user.find(marker='hire-tailoring').elements)).value is True
    user.find('Cost steps to 75').click()
    await user.should_see('New hire cost steps')
    table = next(e for e in user.find(ui.table).elements if 'New' in e._markers)
    assert table.rows[0]['Cost (g)'] == .015  # 2 × 20c material + 10c vendor + 100c training.
    assert table.rows[0]['Training (g)'] == .01


async def test_team_hiring_without_characters_and_without_scan(user, tmp_path, monkeypatch):
    team_app(tmp_path, monkeypatch)
    monkeypatch.setattr('brownstone.professions.latest_data', lambda config: {})
    await user.open('/?place=Team')
    await user.should_see('No characters imported for this source')
    await user.should_see('Add a character?')
    await user.should_see('No character has two evidenced primary professions.')
    user.find(marker='hire-tailoring').trigger('update:modelValue', True)
    assert next(iter(user.find(marker='hire-tailoring').elements))._props['caption'] == 'Team: no evidenced holder'
    await user.should_see('New hire: rank 1')
    with user.client:
        hiring_section([], {}, None)
    await user.should_see('Import a current scan to compare new hires.')


async def test_hiring_scope_error_is_visible(user, tmp_path, monkeypatch):
    team_app(tmp_path, monkeypatch)

    def broken(*args, **kwargs):
        raise ValueError('fixture scope refusal')

    monkeypatch.setattr(hiring, 'prepare', broken)
    await user.open('/?place=Team')
    await user.should_see('Unable to compare new hires: fixture scope refusal')


async def test_hiring_feed_savings_and_primary_comparison_display(user):
    from test_hiring import context, fixture
    from test_recipe_graph import SMITH, character

    catalogs = fixture()
    data = {SMITH: character(catalogs[1])}
    data[SMITH]['recipes']['Arbitrary title']['known_recipes']['skill_id'] = 164
    data[SMITH]['bags'] = {'skills': {'modern': {'rows': [
        {'name': 'Mining', 'skill_id': 186, 'rank': 8, 'max_rank': 75}]}}}
    ctx = context(catalogs, data)

    @ui.page('/hire-feeds')
    def page():
        hiring_section(catalogs, data, ctx['progression_arguments'])

    await user.open('/hire-feeds')
    await user.should_see('Armorer · mankrik · alliance')
    await user.should_see('Blacksmithing · unknown per craft')
    user.find(marker='hire-mining').trigger('update:modelValue', True)
    await user.should_see('What it feeds: 1 current team board rows become cheaper')
    await user.should_see('Copper Bar → Craft 20 · 2s 70c saved per craft')
