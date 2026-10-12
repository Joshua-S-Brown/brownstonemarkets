"""Offline native user simulation over synthetic, imported evidence."""
from datetime import UTC, datetime
from pathlib import Path

import pytest
from nicegui import ui
from test_today import catalog
from test_today_view import app, listing_evidence_app

from brownstone.money import format_money
from brownstone.today import build_today, craft_details
from brownstone.today_loading import load_today
from brownstone.today_settings import load_settings
from views.nicegui_today import buy_rows, vendor_rows
from views.today_rows import craft_row, sell_row

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize('addon', [False, True])
async def test_page_matches_shared_plan_and_row_details(user, tmp_path, monkeypatch, addon):
    _, source, *_ = (listing_evidence_app(tmp_path, monkeypatch, -1) if addon else app(tmp_path, monkeypatch))
    await user.open('/')
    await user.should_see('Gold available: 10g')
    from brownstone.crafting import parse_recipe_catalog
    catalogs = [{**parse_recipe_catalog(catalog()), 'catalog_id': 'fixture'}]
    _, arguments = load_today(source, catalogs, load_settings(
        source['data_dir'] / f"today-settings.{source['source_id']}.local.json"), {}, datetime.now(UTC))
    result = build_today(**arguments)
    widget = user.find('Craft').elements
    craft_table = next(e for e in widget if isinstance(e, ui.table))
    sells = {r['output_item_id']: r for r in result['sell']}
    assert craft_table.rows == [{**craft_row(r, sells[r['output_item_id']]), 'id': i}
                                for i, r in enumerate(result['craft'])]
    tables = {next(iter(t._markers)): t for t in user.find(ui.table).elements}
    names = {i: item['name'] for c in catalogs for i, item in c['items_by_id'].items()}
    assert tables['Buy'].rows == [{**r, 'id': i} for i, r in enumerate(buy_rows(result, names))]
    assert tables['Sell'].rows == [{**sell_row(r), 'id': i} for i, r in enumerate(result['sell'])]
    vendor = next(t for t in user.find(ui.table).elements if 'vendor' in t._markers)
    assert vendor.rows == [{**r, 'id': i} for i, r in enumerate(vendor_rows(result, names))]
    for remaining in result['remaining'].values():
        await user.should_see(f"{remaining} more rows outside this list's 10-row limit.")
    user.find(kind=ui.table, marker='Craft').trigger('rowClick', [{}, craft_table.rows[0], 0])
    await user.should_see(f"Materials for {result['craft'][0]['output_name']}")
    materials = next(t for t in user.find(ui.table).elements if 'Materials' in t._markers)
    assert [r['Material'] for r in materials.rows] == [
        r['item_name'] for r in craft_details(result['craft'][0])['materials']]
    assert sum(round(r['Cost (g)'] * 10000) for r in materials.rows) == result['craft'][0]['batch_cost_copper']
    if not addon:
        await user.should_see('not available for this source')


async def test_stale_rows_and_settings_round_trip(user, tmp_path, monkeypatch):
    _, source, path = app(tmp_path, monkeypatch, stale=True)
    await user.open('/')
    await user.should_see('Saved prices are stale')
    tables = list(user.find(ui.table).elements)
    assert all(row['State'] == 'stale — inspect only' for table in tables for row in table.rows)
    old = path.read_bytes()
    user.find(kind=ui.input, content='Gold available').clear().type('12')
    user.find('Save Today settings').click()
    await user.should_see('Settings not saved')
    assert path.read_bytes() == old
    user.find(kind=ui.input, content='Gold available').clear().type('12g 50s')
    user.find('Save Today settings').click()
    await user.should_see('Today settings saved locally.')
    assert load_settings(path).gold_copper == 125000
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(Path(__file__).resolve().parents[2] / 'app.py')).run()
    assert not at.exception
    assert any('Gold available: 12g 50s' in c.value for c in at.caption)


async def test_source_resolution_tabs_filter_and_corrupt_settings(user, tmp_path, monkeypatch):
    _, source, path = app(tmp_path, monkeypatch, corrupt=True)
    second = {**source, 'source_id': 'second', 'label': 'Second observer'}
    monkeypatch.setattr('brownstone.config.read_sources', lambda *args: [source, second])
    await user.open('/')
    await user.should_see('Choose one above')
    await user.open('/?game=classic&source=test&tab=Buy')
    await user.should_see('Could not read Today settings')
    assert next(iter(user.find(ui.tabs).elements)).value == 'Buy'
    assert path.read_text() == 'not json'
    user.find('Filter Buy').type('Material')
    buy = next(t for t in user.find(ui.table).elements if 'Buy' in t._markers)
    assert buy.filter == 'Material'


@pytest.mark.parametrize('hours', [-25, 1])
async def test_addon_stale_and_future_labels(user, tmp_path, monkeypatch, hours):
    listing_evidence_app(tmp_path, monkeypatch, hours)
    await user.open('/')
    await user.should_see('Saved prices are stale')
    assert all(r['State'] == 'stale — inspect only' for t in user.find(ui.table).elements for r in t.rows)


async def test_character_watchlist_and_failed_save_keep_plan(user, tmp_path, monkeypatch):
    from test_today_characters import CHARACTER, state

    from brownstone.watchlist import Entry, save_entries, watchlist_path
    _, source, path = app(tmp_path, monkeypatch)
    monkeypatch.setattr('brownstone.today_loading.professions.latest_data',
                        lambda config: {CHARACTER: state(learned=True)})
    save_entries(watchlist_path(source['data_dir'], source['source_id']), [Entry(1, 10)])
    await user.open('/')
    await user.should_see('Watchlist hits (1)')
    user.find(kind=ui.select, content='Character').click()
    user.find('Basilly · Beta · Alliance').click()
    user.find('Save Today settings').click()
    await user.should_see('No captured gold for Basilly; using the entered amount.')
    assert load_settings(path).character == CHARACTER
    row = next(t for t in user.find(ui.table).elements if 'Craft' in t._markers).rows[0]
    assert row['Can make'] == 'Known'
    table_before = next(t for t in user.find(ui.table).elements if 'Craft' in t._markers)
    old = path.read_bytes()

    def fail(*args):
        raise OSError('read only fixture')

    monkeypatch.setattr('views.nicegui_today.save_settings', fail)
    user.find('Save Today settings').click()
    await user.should_see('Settings not saved')
    assert path.read_bytes() == old
    assert next(t for t in user.find(ui.table).elements if 'Craft' in t._markers) is table_before

    from dataclasses import replace

    from brownstone.today_settings import save_settings
    save_settings(path, replace(load_settings(path), character=('Gone', 'Beta', 'Alliance')))
    missing = path.read_bytes()
    await user.open('/')
    await user.should_see('Saved character is no longer present')
    await user.should_not_see('Character: Gone')
    assert path.read_bytes() == missing


async def test_forever_first_disabled_and_no_snapshot(user, tmp_path, monkeypatch):
    _, source, _ = app(tmp_path, monkeypatch)
    forever = {**source, 'source_id': 'forever', 'game_version': 'forever', 'label': 'Forever observer'}
    disabled = {**source, 'source_id': 'disabled', 'enabled': False}
    monkeypatch.setattr('brownstone.config.read_sources', lambda *args: [disabled, source, forever])
    await user.open('/')
    await user.should_see('Showing WoW Forever')
    await user.should_see('Refresh or import a scan')
    experiences = next(s for s in user.find(ui.select).elements if s.label == 'Experience')
    assert list(experiences.options) == ['forever', 'classic']
    await user.should_not_see('disabled')


async def test_recorded_funds_summary_plan_override_and_missing(user, tmp_path, monkeypatch):
    from test_today_characters import CHARACTER
    from test_today_funds import funds_data

    from brownstone.today_settings import TodaySettings, save_settings
    data = funds_data()
    monkeypatch.setattr('brownstone.today_loading.professions.latest_data', lambda config: data)
    _, _, path = app(tmp_path, monkeypatch)
    save_settings(path, TodaySettings(250000, 1, 'fixed', character=CHARACTER))
    await user.open('/')
    await user.should_see('Gold available: 2s 55c (Basilly, captured 2026-10-11 10:57 UTC')
    buy = next(t for t in user.find(ui.table).elements if 'Buy' in t._markers)
    assert sum(round(r['Cost (g)'] * 10000) for r in buy.rows) <= 255
    user.find('Enter an amount instead').click()
    user.find(kind=ui.input, content='Gold available').clear().type('1s')
    user.find('Save Today settings').click()
    await user.should_see('Gold available: 1s (entered amount)')
    assert load_settings(path).gold_override
    data[CHARACTER]['bags'] = {}
    user.find('Enter an amount instead').click()
    user.find('Save Today settings').click()
    await user.should_see('No captured gold for Basilly; using the entered amount.')


async def test_all_recipes_recorded_total_summary(user, tmp_path, monkeypatch):
    from test_today_funds import funds_data
    monkeypatch.setattr('brownstone.today_loading.professions.latest_data', lambda config: funds_data())
    _, _, path = app(tmp_path, monkeypatch)
    await user.open('/')
    await user.should_see('Gold available: 2s 55c (across 1 characters; gold must be mailed to the crafter)')
    assert load_settings(path).gold_copper == 100000


async def test_team_unknown_switch_counts_and_no_evidence_notice(user, tmp_path, monkeypatch):
    from test_today_characters import CHARACTER
    from test_today_team import skills_state

    from brownstone.today_characters import NO_CHARACTER_EVIDENCE
    data = {CHARACTER: skills_state([197])}
    monkeypatch.setattr('brownstone.today_loading.professions.latest_data', lambda config: data)
    _, _, path = app(tmp_path, monkeypatch)
    await user.open('/')
    await user.should_see('Save Today settings')
    choices = next(e for e in user.find(ui.select).elements if e.label == 'Character')
    assert choices.options['0'] == 'Our team'
    await user.should_see('unknown for every character: 1')
    assert not next(t for t in user.find(ui.table).elements if 'Craft' in t._markers).rows
    user.find('Include unknown recipes').click()
    user.find('Save Today settings').click()
    await user.should_see('Today settings saved locally.')
    assert load_settings(path).include_unknown
    craft = next(t for t in user.find(ui.table).elements if 'Craft' in t._markers).rows[0]
    assert craft['Can make'] == 'Unknown' and craft['Who can make it'] == 'unknown'
    data.clear()
    await user.open('/')
    await user.should_see(NO_CHARACTER_EVIDENCE)


async def test_team_only_plans_capable_names(user, tmp_path, monkeypatch):
    from test_today_characters import CHARACTER, state
    from test_today_team import skills_state
    data = {CHARACTER: state(learned=True), ('Other', 'Beta', 'Alliance'): skills_state()}
    monkeypatch.setattr('brownstone.today_loading.professions.latest_data', lambda config: data)
    app(tmp_path, monkeypatch)
    await user.open('/')
    await user.should_see('Save Today settings')
    craft = next(t for t in user.find(ui.table).elements if 'Craft' in t._markers).rows[0]
    assert craft['Who can make it'] == 'Basilly'


async def test_mixed_team_keeps_unknown_column_after_known_row(user, tmp_path, monkeypatch):
    from dataclasses import replace

    from test_today import output_catalog
    from test_today_characters import CHARACTER, state

    from brownstone.pipeline import run
    from brownstone.today_settings import save_settings
    monkeypatch.setattr('brownstone.today_loading.professions.latest_data',
                        lambda config: {CHARACTER: state(learned=True)})
    first, unknown = catalog(), output_catalog(4, 'unknown')
    unknown['recipes_by_id'][31] = unknown['recipes_by_id'].pop(30) | {'recipe_id': 31}
    unknown['recipe_for_output'][4] = 31
    unknown['recipes'][0]['recipe_id'] = 31
    _, source, path = app(tmp_path, monkeypatch)
    csv = tmp_path / 'mixed.csv'
    csv.write_text('itemId,name,marketValue,minBuyout,recent,historical,updatedAt\n'
                   '1,Material,20,10,0,0,\n3,Known,2000,2000,0,0,\n4,Unknown,2000,2000,0,0,\n')
    run(source, csv)
    monkeypatch.setattr('brownstone.recipe_catalogs.find_catalogs', lambda *args: [
        {'name': c['catalog_id'], 'catalog': c} for c in (first, unknown)])
    save_settings(path, replace(load_settings(path), include_unknown=True))
    await user.open('/')
    await user.should_see('Save Today settings')
    craft = next(t for t in user.find(ui.table).elements if 'Craft' in t._markers)
    assert any(r.get('Can make') == 'Unknown' for r in craft.rows)
    assert any(c['name'] == 'Can make' for c in craft.columns)


async def test_adjustments_match_planner_queue_ticks_and_reset(user, tmp_path, monkeypatch):
    _, source = listing_evidence_app(tmp_path, monkeypatch, -1)
    path = source['data_dir'] / f"today-settings.{source['source_id']}.local.json"
    await user.open('/')
    await user.should_see('Adjust crafts')
    from brownstone.crafting import parse_recipe_catalog
    catalogs = [{**parse_recipe_catalog(catalog()), 'catalog_id': 'fixture'}]
    _, arguments = load_today(source, catalogs, load_settings(path), {}, datetime.now(UTC))
    default = build_today(**arguments)
    row = default['craft'][0]
    user.find('Queue').click()
    queue_tick = next(e for e in user.find(ui.checkbox).elements if e.text.startswith('Buy at'))
    tick_text = queue_tick.text
    user.find(kind=ui.checkbox, content=tick_text).click()
    user.find('Hide Low confidence').click()
    await user.should_see('Hidden Low confidence')
    assert next(e for e in user.find(ui.checkbox).elements if e.text == tick_text).value
    assert next(iter(user.find(ui.tabs).elements)).value == 'Queue'
    user.find('Hide Low confidence').click()
    batch = user.find(kind=ui.number, content=f"Batch for {row['output_name']}")
    box = next(iter(batch.elements))
    box.set_value(1)
    # Typing alone doesn't rebuild (it would replace the box mid-typing); blur commits.
    assert next(iter(batch.elements)) is box
    batch.trigger('blur')
    choices = [{'catalog_id': row['catalog_id'], 'recipe_id': row['recipe_id'], 'batch_size': 1}]
    expected = build_today(**arguments, choices=choices)
    await user.should_see(f"Whole shopping list: {format_money(expected['shopping_total_copper'])}")
    buy = next(t for t in user.find(ui.table).elements if 'Buy' in t._markers)
    names = {i: item['name'] for c in catalogs for i, item in c['items_by_id'].items()}
    assert buy.rows == [{**r, 'id': i} for i, r in enumerate(buy_rows(expected, names))]
    assert not any(e.value for e in user.find(ui.checkbox).elements if e.text.startswith('Buy at'))
    user.find('Refill freed gold').click()
    user.find(kind=ui.checkbox, content=row['output_name']).click()
    await user.should_see('Whole shopping list: 0c')
    assert not next(t for t in user.find(ui.table).elements if 'Buy' in t._markers).rows
    user.find('Refill freed gold').click()
    await user.should_see('Whole shopping list: 0c')
    # Settings change resets adjustments and retains the active tab.
    user.find('Save Today settings').click()
    # Same settings don't reset; a changed cap does.
    user.find(kind=ui.number, content='Most crafts per item').elements.pop().set_value(2)
    user.find('Save Today settings').click()
    await user.should_see('Previous choices were dropped, not resized')
    assert next(iter(user.find(ui.tabs).elements)).value == 'Queue'
    assert next(t for t in user.find(ui.table).elements if 'Craft' in t._markers).rows
    # The reset note shows only on the rebuild that reset.
    user.find('Hide Low confidence').click()
    await user.should_not_see('Previous choices were dropped, not resized')


async def test_cards_reserved_cost_unknown_and_stale(user, tmp_path, monkeypatch):
    app(tmp_path, monkeypatch, stale=True)
    await user.open('/')
    await user.should_see('Adjust crafts')
    user.find(ui.toggle).elements.pop().set_value('Cards')
    cards = user.find(marker='craft-card').elements
    assert cards and all(c._props['materials_copper'] == c._props['cost_copper'] for c in cards)
    await user.should_see('Can make: Unknown')
    await user.should_see('stale — inspect only')
    await user.should_see('What to buy and where to sell')


async def test_dropped_choice_and_invalid_batch(user, tmp_path, monkeypatch):
    app(tmp_path, monkeypatch)
    await user.open('/')
    await user.should_see('Adjust crafts')
    from nicegui import app as nicegui_app

    from views.nicegui_today import batch_change
    with user.client:
        session = nicegui_app.storage.tab['today-plan-test']
    row = session['rows'][0]
    session['choices'] = [{'catalog_id': row['catalog_id'], 'recipe_id': row['recipe_id'], 'batch_size': 10000}]
    user.find('Refill freed gold').click()
    await user.should_see('Choice is no longer feasible; dropped, not resized.')
    assert session['choices'][0]['batch_size'] is None
    with user.client:
        calls = []
        batch_change(1.5, ('fixture', 30), 5, lambda *args, **kwargs: calls.append(args))
        batch_change(None, ('fixture', 30), 5, lambda *args, **kwargs: calls.append(args))
    assert not calls


async def test_refill_next_output_cards_and_source_isolation(user, tmp_path, monkeypatch):
    from test_today import output_catalog

    from brownstone.pipeline import run
    _, source, _ = app(tmp_path, monkeypatch)
    catalogs = [output_catalog(i, f'route-{i}') for i in range(3, 14)]
    for c in catalogs:
        output = c['recipes_by_id'][30]['output_item_id']
        c['recipes'][0]['output_item_id'] = output
        c['items_by_id'][output]['name'] = f'Fixture {output}'
    csv = tmp_path / 'many.csv'
    csv.write_text('itemId,name,marketValue,minBuyout,recent,historical,updatedAt\n1,Material,20,10,0,0,\n' +
                   ''.join(f'{i},Output {i},2000,2000,0,0,\n' for i in range(3, 14)))
    run(source, csv)
    monkeypatch.setattr('brownstone.recipe_catalogs.find_catalogs', lambda *args: [
        {'name': c['catalog_id'], 'catalog': c} for c in catalogs])
    await user.open('/')
    await user.should_see('Adjust crafts')
    crafts = next(t for t in user.find(ui.table).elements if 'Craft' in t._markers)
    assert len(crafts.rows) == 10
    original = [r['Item'] for r in crafts.rows]
    checkbox = next(e for e in user.find(ui.checkbox).elements if e.text == original[0])
    user.find(kind=ui.checkbox, content=checkbox.text).click()
    crafts = next(t for t in user.find(ui.table).elements if 'Craft' in t._markers)
    assert len(crafts.rows) == 10 and original[0] not in [r['Item'] for r in crafts.rows]
    assert set(r['Item'] for r in crafts.rows) - set(original)
    # Refill rows are ticked and become explicit when refill is turned off.
    user.find('Refill freed gold').click()
    assert len(next(t for t in user.find(ui.table).elements if 'Craft' in t._markers).rows) == 10
    with user.client:
        user.find(ui.toggle).elements.pop().set_value('Cards')
    assert len(user.find(marker='craft-card').elements) == 10
    assert all(c._props['cost_copper'] == c._props['materials_copper']
               for c in user.find(marker='craft-card').elements)
    # Changing source in this browser tab cannot borrow choices or evidence.
    other = source | {'source_id': 'other'}
    monkeypatch.setattr('brownstone.config.read_sources', lambda *args: [source, other])
    await user.open('/?game=classic&source=other')
    await user.should_see('Refresh or import a scan')
    with user.client:
        from nicegui import app as nicegui_app
        assert not nicegui_app.storage.tab['today-plan-other'].get('rows')

    await user.open('/?game=classic&source=test')
    await user.should_see('Adjust crafts')
    toggle = user.find(ui.toggle).elements.pop()
    assert toggle.value == 'Cards'
    with user.client:
        toggle.set_value('Table')
    assert original[0] not in [r['Item'] for r in
                               next(t for t in user.find(ui.table).elements if 'Craft' in t._markers).rows]
    assert not next(e for e in user.find(ui.switch).elements if e.text == 'Refill freed gold').value
    # A second browser tab gets its own untouched default plan.
    from uuid import uuid4
    user.tab_id = str(uuid4())
    await user.open('/?game=classic&source=test')
    await user.should_see('Adjust crafts')
    assert original[0] in [r['Item'] for r in
                           next(t for t in user.find(ui.table).elements if 'Craft' in t._markers).rows]
    assert next(e for e in user.find(ui.switch).elements if e.text == 'Refill freed gold').value
