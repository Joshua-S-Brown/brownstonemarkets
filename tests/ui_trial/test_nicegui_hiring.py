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
    assert table.rows[0]['Cost'] == '1s 50c'  # 2 × 20c material + 10c vendor + 100c training.
    assert table.rows[0]['Training'] == '1s'


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


@pytest.mark.parametrize('one_complete', [False, True])
async def test_all_incomplete_note_and_row_cost_suppression(user, tmp_path, monkeypatch, one_complete):
    team_app(tmp_path, monkeypatch)
    original = hiring.summaries

    def summaries(context, **kwargs):
        result = original(context, **kwargs)
        if one_complete:
            result['rows'][0]['estimate'] = {'complete': True, 'cost_copper': 150}
        return result

    monkeypatch.setattr(hiring, 'summaries', summaries)
    await user.open('/?place=Team')
    await user.should_see('Instead of a new hire')
    note = 'Cost to 300 is incomplete for every profession; open one to see why'
    labels = [e._props['label'] for e in user.find(ui.expansion).elements
              if any(m.startswith('hire-') for m in e._markers)]
    assert labels
    if one_complete:
        await user.should_not_see(note)
        assert any('cost to 300: 1s 50c' in label for label in labels)
        # With a mixture, the other incomplete rows still disclose their costs.
        with user.client:
            from views.nicegui_team import hiring_row
            hiring_row({}, {'profession': 'cooking', 'holders': [], 'best': None,
                            'estimate': {'complete': False, 'cost_copper': None}})
        await user.should_see('cost to 300: incomplete')
    else:
        await user.should_see(note)
        assert all('cost to 300:' not in label for label in labels)


async def test_hire_steps_money_unknown_and_copper_sort(user):
    from views.nicegui_team import hiring_detail

    @ui.page('/hire-money')
    def page():
        hiring_detail({'needs_pattern': 0, 'unknown_source': 0, 'tiers': [
            {'cap': 75, 'required_level': None, 'best': None, 'tier_fees': 'unknown',
             'feeds': {'count': 0, 'top': []}, 'estimate': {'complete': False, 'reasons': ['missing'], 'steps': [
                 {'rank': 1, 'recipe': 'A', 'expected_crafts': '1', 'cost_copper': 10000,
                  'training_cost_copper': 101},
                 {'rank': 2, 'recipe': 'B', 'expected_crafts': '1', 'cost_copper': 200,
                  'training_cost_copper': None},
                 {'rank': 3, 'recipe': 'C', 'expected_crafts': '1', 'cost_copper': None,
                  'training_cost_copper': 0}]}}]})

    await user.open('/hire-money')
    table = next(e for e in user.find(ui.table).elements if 'New' in e._markers)
    assert [(r['Cost'], r['Training']) for r in table.rows] == [
        ('1g', '1s 1c'), ('2s', 'unknown'), ('unknown', '0c')]
    assert [r['Cost_copper'] for r in table.rows] == [10000, 200, None]
    assert [r['Training_copper'] for r in table.rows] == [101, None, 0]
    for label in ('Cost', 'Training'):
        column = next(c for c in table.columns if c['label'] == label)
        assert f'rowA["{label}_copper"]' in column[':sort']
        assert column['sortable']
    assert 'toFixed' not in str(table.slots)
