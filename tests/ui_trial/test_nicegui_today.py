"""Offline native user simulation over synthetic, imported evidence."""
from datetime import UTC, datetime
from pathlib import Path

import pytest
from nicegui import ui
from test_today import catalog
from test_today_view import app, listing_evidence_app

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
    craft = next(t for t in user.find(ui.table).elements if 'Craft' in t._markers)
    assert any(r.get('Can make') == 'Unknown' for r in craft.rows)
    assert any(c['name'] == 'Can make' for c in craft.columns)
