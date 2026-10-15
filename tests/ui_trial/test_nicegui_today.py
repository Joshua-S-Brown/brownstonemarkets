"""Offline native user simulation over synthetic, imported evidence."""
from datetime import UTC, datetime

import pytest
from app_helpers import app, listing_evidence_app
from nicegui import ui
from test_today import catalog

from brownstone.money import format_money, parse_money
from brownstone.today import apply_removals, build_today, craft_details
from brownstone.today_loading import load_today, load_today_removals
from brownstone.today_settings import load_settings
from views.nicegui_today import buy_rows
from views.today_rows import craft_row, sell_row, vendor_row

pytestmark = pytest.mark.asyncio


def data_rows(widget):
    """Navigation metadata does not change the shared plan projection."""
    return [{k: v for k, v in row.items() if k != '_item_url'} for row in widget.rows]


@pytest.mark.parametrize('addon', [False, True])
async def test_page_matches_shared_plan_and_row_details(user, tmp_path, monkeypatch, addon):
    _, source, *_ = (listing_evidence_app(tmp_path, monkeypatch, -1) if addon else app(tmp_path, monkeypatch))
    await user.open('/')
    await user.should_see('recipes hidden')
    user.find(marker='page-info').click()
    await user.should_see('Gold available: 10g')
    from brownstone.crafting import parse_recipe_catalog
    catalogs = [{**parse_recipe_catalog(catalog()), 'catalog_id': 'fixture'}]
    _, arguments = load_today(source, catalogs, load_settings(
        source['data_dir'] / f"today-settings.{source['source_id']}.local.json"), {}, datetime.now(UTC), flood=True)
    result = build_today(**arguments)
    apply_removals(result, load_today_removals(source, result))
    user.find(kind=ui.toggle, marker='plan-display').elements.pop().set_value('Table')
    widget = user.find('Craft').elements
    craft_table = next(e for e in widget if isinstance(e, ui.table))
    sells = {r['output_item_id']: r for r in result['sell']}
    assert data_rows(craft_table) == [{**craft_row(r, sells[r['output_item_id']]), 'id': i}
                                     for i, r in enumerate(result['craft'])]
    tables = {next(iter(t._markers)): t for t in all_tables(user)}
    names = {i: item['name'] for c in catalogs for i, item in c['items_by_id'].items()}
    assert data_rows(tables['Buy']) == [{**r, 'id': i} for i, r in enumerate(buy_rows(result, names))]
    assert data_rows(tables['Sell']) == [{**sell_row(r), 'id': i} for i, r in enumerate(result['sell'])]
    vendor = next(t for t in all_tables(user) if 'vendor' in t._markers)
    assert data_rows(vendor) == [
        {**r, 'id': i} for i, r in enumerate(vendor_row(r, names) for r in result['below_vendor'])]
    await user.should_see('recipes hidden')
    user.find(marker='page-info').click()
    for remaining in result['remaining'].values():
        await user.should_see(f"{remaining} more rows outside this list's 10-row limit.")
    user.find(kind=ui.table, marker='Craft').trigger('rowClick', [{}, craft_table.rows[0], 0])
    await user.should_see(f"Materials for {result['craft'][0]['output_name']}")
    materials = next(t for t in all_tables(user) if 'Materials' in t._markers)
    assert [r['Material'] for r in materials.rows] == [
        r['item_name'] for r in craft_details(result['craft'][0])['materials']]
    assert sum(parse_money(r['Cost']) for r in materials.rows) == result['craft'][0]['batch_cost_copper']
    if not addon:
        await user.should_see('not available for this source')


async def test_stale_rows_and_settings_round_trip(user, tmp_path, monkeypatch):
    _, source, path = app(tmp_path, monkeypatch, stale=True)
    await user.open('/')
    await user.should_see('recipes hidden')
    user.find(marker='page-info').click()
    await user.should_see('Saved prices are stale')
    tables = list(all_tables(user))
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
    await user.open('/')
    user.find(marker='page-info').click()
    await user.should_see('Gold 12g 50s · entered')


async def test_source_resolution_tabs_filter_and_corrupt_settings(user, tmp_path, monkeypatch):
    _, source, path = app(tmp_path, monkeypatch, corrupt=True)
    second = {**source, 'source_id': 'second', 'label': 'Second observer'}
    monkeypatch.setattr('brownstone.config.read_sources', lambda *args: [source, second])
    await user.open('/')
    await user.should_see('Choose one above')
    await user.open('/?game=classic&source=test&tab=Buy')
    await user.should_see('Could not read Today settings')
    assert next(iter(user.find(ui.tabs).elements)).value == 'Shopping list'
    assert path.read_text() == 'not json'
    user.find('Filter Buy').type('Material')
    buy = next(t for t in all_tables(user) if 'Buy' in t._markers)
    assert buy.filter == 'Material'


@pytest.mark.parametrize('hours', [-25, 1])
async def test_addon_stale_and_future_labels(user, tmp_path, monkeypatch, hours):
    listing_evidence_app(tmp_path, monkeypatch, hours)
    await user.open('/')
    await user.should_see('recipes hidden')
    user.find(marker='page-info').click()
    await user.should_see('Saved prices are stale')
    assert all(r['State'] == 'stale — inspect only' for t in all_tables(user) for r in t.rows)


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
    await user.should_see('recipes hidden')
    user.find(marker='page-info').click()
    await user.should_see('No captured gold for Basilly; using the entered amount.')
    assert load_settings(path).character == CHARACTER
    row = next(t for t in all_tables(user) if 'Craft' in t._markers).rows[0]
    assert row['Can make'] == 'Known'
    table_before = next(t for t in all_tables(user) if 'Craft' in t._markers)
    old = path.read_bytes()

    def fail(*args):
        raise OSError('read only fixture')

    monkeypatch.setattr('views.nicegui_today.save_settings', fail)
    user.find('Save Today settings').click()
    await user.should_see('Settings not saved')
    assert path.read_bytes() == old
    assert next(t for t in all_tables(user) if 'Craft' in t._markers) is table_before

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
    await user.should_see('WoW Forever')
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
    await user.should_see('recipes hidden')
    user.find(marker='page-info').click()
    await user.should_see('Gold available: 2s 55c (Basilly, captured 2026-10-11 10:57 UTC')
    assert load_settings(path).gold_copper == 250000  # Resolved funds are never saved automatically.
    buy = next(t for t in all_tables(user) if 'Buy' in t._markers)
    assert sum(parse_money(r['Cost']) for r in buy.rows) <= 255
    user.find('Enter an amount instead').click()
    user.find(kind=ui.input, content='Gold available').clear().type('1s')
    user.find('Save Today settings').click()
    await user.should_see('recipes hidden')
    user.find(marker='page-info').click()
    await user.should_see('Gold available: 1s (entered amount)')
    recorded = next(t for t in all_tables(user) if 'Recorded' in t._markers)
    assert recorded.rows[0]['Recorded gold'] == '2s 55c'
    assert recorded.rows[0]['Captured (UTC)'] == '2026-10-11 10:57 UTC'
    assert load_settings(path).gold_override
    data[CHARACTER]['bags'] = {}
    user.find('Enter an amount instead').click()
    user.find('Save Today settings').click()
    await user.should_see('recipes hidden')
    user.find(marker='page-info').click()
    await user.should_see('No captured gold for Basilly; using the entered amount.')


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
    await user.should_see('recipes hidden')
    user.find(marker='page-info').click()
    await user.should_see('unknown for every character: 1')
    assert not next(t for t in all_tables(user) if 'Craft' in t._markers).rows
    user.find('Include unknown recipes').click()
    user.find('Save Today settings').click()
    await user.should_see('Today settings saved locally.')
    assert load_settings(path).include_unknown
    craft = next(t for t in all_tables(user) if 'Craft' in t._markers).rows[0]
    assert craft['Can make'] == 'Unknown' and craft['Who can make it'] == 'unknown'
    await user.should_see('Can make: Unknown · Who can make it: unknown')
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
    craft = next(t for t in all_tables(user) if 'Craft' in t._markers).rows[0]
    assert craft['Who can make it'] == 'Basilly' and 'Can make' not in craft
    await user.should_see('Who can make it: Basilly')
    await user.should_not_see('Can make: Unknown')


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
    craft = next(t for t in all_tables(user) if 'Craft' in t._markers)
    assert any(r.get('Can make') == 'Unknown' for r in craft.rows)
    assert any(c['name'] == 'Can make' for c in craft.columns)


async def test_adjustments_match_planner_queue_ticks_and_reset(user, tmp_path, monkeypatch):
    _, source = listing_evidence_app(tmp_path, monkeypatch, -1)
    path = source['data_dir'] / f"today-settings.{source['source_id']}.local.json"
    await user.open('/')
    await user.should_see('Adjust crafts')
    user.find(kind=ui.expansion, content='Plan controls').trigger('update:modelValue', True)
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
    user.find(marker='page-info').click()
    await user.should_see('Hidden Low confidence')
    assert next(iter(user.find(kind=ui.expansion, content='Plan controls').elements)).value
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
    cards = sorted(user.find(marker='craft-card').elements, key=lambda e: e.id)
    assert len(cards) == len(expected['craft'])
    for card, row in zip(cards, expected['craft'], strict=True):
        assert f"{row['output_name']} · {row['batch_size']} crafts" in card_text(card)
        assert_card_cost(card)
    buy = next(t for t in all_tables(user) if 'Buy' in t._markers)
    names = {i: item['name'] for c in catalogs for i, item in c['items_by_id'].items()}
    assert data_rows(buy) == [{**r, 'id': i} for i, r in enumerate(buy_rows(expected, names))]
    assert not any(e.value for e in user.find(ui.checkbox).elements if e.text.startswith('Buy at'))
    user.find('Refill freed gold').click()
    user.find(kind=ui.checkbox, content=row['output_name']).click()
    await user.should_see('Whole shopping list: 0c')
    assert not next(t for t in all_tables(user) if 'Buy' in t._markers).rows
    user.find('Refill freed gold').click()
    await user.should_see('Whole shopping list: 0c')
    # Settings change resets adjustments and retains the active tab.
    user.find('Save Today settings').click()
    # Same settings don't reset; a changed cap does.
    user.find(kind=ui.number, content='Most crafts per item').elements.pop().set_value(2)
    user.find('Save Today settings').click()
    await user.should_see('Previous choices were dropped, not resized')
    assert next(iter(user.find(ui.tabs).elements)).value == 'Queue'
    assert next(t for t in all_tables(user) if 'Craft' in t._markers).rows
    # The reset note shows only on the rebuild that reset.
    user.find('Hide Low confidence').click()
    await user.should_not_see('Previous choices were dropped, not resized')


async def test_cards_reserved_cost_unknown_and_stale(user, tmp_path, monkeypatch):
    app(tmp_path, monkeypatch, stale=True)
    await user.open('/')
    await user.should_see('Adjust crafts')
    assert next(iter(user.find(kind=ui.toggle, marker='plan-display').elements)).value == 'Cards'
    cards = user.find(marker='craft-card').elements
    assert cards
    for card in cards:
        assert_card_cost(card)
        assert 'Who can make it: unknown' in card_text(card)
        assert any(e.text == 'Unknown' for e in card.descendants()
                   if isinstance(e, ui.label) and 'bs-badge' in e.classes)
        assert 'stale — inspect only' in card_text(card)
        assert not next(e for e in card.descendants() if isinstance(e, ui.expansion)).value
    user.find(kind=ui.expansion, content='What to buy and where to sell').trigger('update:modelValue', True)
    await user.should_see('What to buy · Material cost')
    assert next(e for e in next(iter(cards)).descendants() if isinstance(e, ui.expansion)).value
    user.find(kind=ui.toggle, marker='plan-display').elements.pop().set_value('Table')
    table = next(t for t in all_tables(user) if 'Craft' in t._markers)
    assert table.parent_slot.parent.visible
    user.find(kind=ui.toggle, marker='plan-display').elements.pop().set_value('Cards')
    assert not table.parent_slot.parent.visible
    await user.should_see('Who can make it: unknown')
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
    user.find(kind=ui.toggle, marker='plan-display').elements.pop().set_value('Table')
    crafts = next(t for t in all_tables(user) if 'Craft' in t._markers)
    assert len(crafts.rows) == 10
    await user.should_see('recipes hidden')
    user.find(marker='page-info').click()
    await user.should_see('1 more rows outside this list')
    original = [r['Item'] for r in crafts.rows]
    checkbox = next(e for e in user.find(ui.checkbox).elements if e.text == original[0])
    user.find(kind=ui.checkbox, content=checkbox.text).click()
    crafts = next(t for t in all_tables(user) if 'Craft' in t._markers)
    assert len(crafts.rows) == 10 and original[0] not in [r['Item'] for r in crafts.rows]
    assert set(r['Item'] for r in crafts.rows) - set(original)
    # Refill rows are ticked and become explicit when refill is turned off.
    user.find('Refill freed gold').click()
    assert len(next(t for t in all_tables(user) if 'Craft' in t._markers).rows) == 10
    with user.client:
        user.find(kind=ui.toggle, marker='plan-display').elements.pop().set_value('Cards')
    assert len(user.find(marker='craft-card').elements) == 10
    for card in user.find(marker='craft-card').elements:
        assert_card_cost(card)
    assert [next(e.text.split(' · ')[0] for e in c.descendants() if isinstance(e, (ui.label, ui.link)))
            for c in sorted(user.find(marker='craft-card').elements, key=lambda e: e.id)] == [
                r['Item'] for r in next(t for t in all_tables(user) if 'Craft' in t._markers).rows]
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
    toggle = user.find(kind=ui.toggle, marker='plan-display').elements.pop()
    assert toggle.value == 'Cards'
    with user.client:
        toggle.set_value('Table')
    assert original[0] not in [r['Item'] for r in
                               next(t for t in all_tables(user) if 'Craft' in t._markers).rows]
    assert not next(e for e in user.find(ui.switch).elements if e.text == 'Refill freed gold').value
    # A second browser tab gets its own untouched default plan.
    from uuid import uuid4
    user.tab_id = str(uuid4())
    await user.open('/?game=classic&source=test')
    await user.should_see('Adjust crafts')
    assert original[0] in [r['Item'] for r in
                           next(t for t in all_tables(user) if 'Craft' in t._markers).rows]
    assert next(e for e in user.find(ui.switch).elements if e.text == 'Refill freed gold').value


def card_text(card):
    return '\n'.join(e.text for e in card.descendants() if isinstance(e, (ui.label, ui.link)))


def assert_card_cost(card):
    labels = [e.text for e in card.descendants() if isinstance(e, ui.label)]
    cost = next(t.removeprefix('What to buy · Material cost ') for t in labels
                if t.startswith('What to buy · Material cost '))
    materials = [t for t in labels if ' · highest unit ' in t]
    assert sum(parse_money(t.split(' · ')[3]) for t in materials) == parse_money(cost)


async def test_cards_shared_buy_uses_vendor_and_intermediate(user, monkeypatch):
    from test_today import chain_catalog, output_catalog, plan

    from views.nicegui_today import plan_tables
    second = output_catalog(4, 'second')
    second['items_by_id'][4]['name'] = 'Second output'
    result = plan(catalogs=[chain_catalog(), second], listings={1: [(30, 300, 10), (30, 600, 20)]},
                  observations={1: {'min_buyout': 10}, 3: {'min_buyout': 2000}, 4: {'min_buyout': 2000}},
                  metrics={3: {'min_buyout': 200, 'listings': 2, 'units': 8, 'largest_stack_units': 3},
                           4: {'min_buyout': 200, 'listings': 3, 'units': 8, 'largest_stack_units': 3}})
    assert len(result['craft']) == 2

    def fail(*args, **kwargs):
        raise AssertionError('Rendering must not re-quote listings')

    monkeypatch.setattr('brownstone.today.Ladder.quote', fail)

    @ui.page('/cards')
    def page():
        plan_tables(result, {1: 'Shared material', 2: 'Vendor thread'}, 'Craft',
                    {'game_version': 'classic', 'source_id': 'fixture'})

    await user.open('/cards')
    cards = sorted(user.find(marker='craft-card').elements, key=lambda e: e.id)
    for card, row in zip(cards, result['craft'], strict=True):
        text = card_text(card)
        assert_card_cost(card)
        assert ("Profit at the cautious sale price (used for ranking): "
                + format_money(row['batch_profit_copper'])) in text
        sell = next(r for r in result['sell'] if r['output_item_id'] == row['output_item_id'])
        profit = sell['undercut_batch_profit_copper']
        assert f"per craft {format_money(profit // row['batch_size'])}" in text
        assert f"Sell at {format_money(sell['undercut_copper'])}" in text
        assert f"profit {format_money(sell['undercut_batch_profit_copper'])}" in text
        why = (f"Cautious sale {format_money(row['sale_price_copper'])} · "
               f"{sell['listings']} listings / {sell['units']} units · limited by {row['limiting_factor']}"
               + (' · thin' if sell['thin'] else ''))
        assert why in text
        assert f"{row['output_name']} · {row['batch_size']} crafts" in text
        assert f"{row['confidence']} confidence" in text
        for material in craft_details(row)['materials']:
            route = 'vendor' if material['method'] == 'vendor' else 'auction house'
            assert (f"{material['item_name']} · {route} · {material['purchased_units']} units · "
                    f"{format_money(material['cost_copper'])} · "
                    f"highest unit {format_money(material['highest_unit_copper'])}") in text
        assert ' · vendor · ' in text
    chain = next(c for c in cards if 'Intermediate 5' in card_text(c))
    assert '↳ Intermediate 5: ' in card_text(chain)
    assert '↳ ↳ Intermediate 6: ' in card_text(chain)
    assert any(e.style.get('margin-left') == '2rem' for e in chain.descendants() if isinstance(e, ui.label))
    user.find('Shopping list').click()
    buy = next(t for t in all_tables(user) if 'Buy' in t._markers)
    assert 'For' in [c['name'] for c in buy.columns]
    for displayed, merged in zip(buy.rows, result['buy'], strict=True):
        contributions = displayed['For'].split('; ')
        assert len(contributions) == 2
        assert sum(int(c.rsplit(': ', 1)[1].removesuffix(' units')) for c in contributions) == (
            merged['purchased_units'])
        for row in result['craft']:
            purchase = next(p for p in row['purchases']
                            if (p['item_id'], p['method']) == (merged['item_id'], merged['method']))
            assert f"{row['output_name']}: {purchase['purchased_units']} units" in contributions
    assert sum(parse_money(r['Cost']) for r in buy.rows) == result['shopping_total_copper']
    assert sum(r['batch_cost_copper'] for r in result['craft']) == result['shopping_total_copper']


def all_tables(user):
    return [e for e in user.client.elements.values() if isinstance(e, ui.table)]


async def test_hidden_low_row_click_opens_shown_craft(user):
    from test_today import chain_catalog, output_catalog, plan

    from views.nicegui_today import plan_tables
    second = output_catalog(4, 'second')
    second['items_by_id'][4]['name'] = 'Second output'
    result = plan(catalogs=[chain_catalog(), second], listings={1: [(30, 300, 10), (30, 600, 20)]},
                  observations={1: {'min_buyout': 10}, 3: {'min_buyout': 2000}, 4: {'min_buyout': 2000}},
                  metrics={3: {'min_buyout': 200, 'listings': 2, 'units': 8, 'largest_stack_units': 3},
                           4: {'min_buyout': 200, 'listings': 3, 'units': 8, 'largest_stack_units': 3}})
    result['craft'][0]['confidence'], result['craft'][1]['confidence'] = 'Low', 'High'
    shown = result['craft'][1]

    @ui.page('/hidden-low')
    def page():
        plan_tables(result, {1: 'Shared material', 2: 'Vendor thread'}, 'Plan',
                    {'game_version': 'classic', 'source_id': 'fixture'},
                    {'hide_low': True, 'display': 'Table', 'refill': False, 'choices': None,
                     'rows': result['craft'], 'ticks': {}})

    await user.open('/hidden-low')
    craft_table = next(t for t in all_tables(user) if 'Craft' in t._markers)
    assert [r['Item'] for r in craft_table.rows] == [shown['output_name']]
    user.find(kind=ui.table, marker='Craft').trigger('rowClick', [{}, craft_table.rows[0], 0])
    await user.should_see(f"Materials for {shown['output_name']}")
