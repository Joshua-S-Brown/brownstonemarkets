"""Native NiceGUI Today components over the shared saved-evidence path."""
from datetime import UTC, datetime
from urllib.parse import urlencode

import duckdb
from nicegui import ui

from brownstone.money import format_money, parse_money, to_gold
from brownstone.today import build_today, craft_details
from brownstone.today_characters import available_characters, resolve_character
from brownstone.today_funds import resolve_funds
from brownstone.today_loading import load_today
from brownstone.today_settings import TodaySettings, load_settings, save_settings, settings_path
from brownstone.watchlist import known_names, load_entries, read_watchlist, watchlist_path
from views.today_rows import craft_row, sell_row

TABS = ['Craft', 'Buy', 'Sell', 'Below vendor']


def table(rows, *, label, row_key='id'):
    rows = [{**row, 'id': i} for i, row in enumerate(rows)]
    keys = list(dict.fromkeys(key for row in rows for key in row if key != 'id'))
    decisions = {
        'Craft': ['Item', 'State', 'Can make', 'Who can make it', 'Batch', 'Material cost (g)',
                  'Batch profit (g)', 'Profit per craft (g)', 'Confidence'],
        'Sell': ['Output', 'State', 'Batch', 'Lowest competing unit (g)', 'Listings', 'Units',
                 'Undercut unit (g)', 'Profit at undercut for batch (g)', 'Thin', 'Confidence', 'Reasons'],
        'Buy': ['Material', 'State', 'Route', 'Required units', 'Purchased units', 'Cost (g)',
                'Highest unit price (g)', 'Cheap now'],
    }.get(label, keys)

    def columns(selected):
        return [{'name': key, 'label': key, 'field': key, 'sortable': True, 'align': 'left'}
                for key in selected if key in keys]

    with ui.row():
        search = ui.input(f'Filter {label}').props('dense clearable')
        evidence = ui.switch('Show evidence columns')
    widget = ui.table(columns=columns(decisions), rows=rows, row_key=row_key, pagination=10)
    widget.props('dense flat bordered')
    widget.classes('w-full').mark(label)
    evidence.on_value_change(lambda e: setattr(widget, 'columns', columns(keys if e.value else decisions)))
    search.bind_value_to(widget, 'filter')
    if not rows:
        ui.label('No rows clear these settings with the available evidence.')
    return widget


def state(row):
    return 'stale — inspect only' if row['stale'] else 'potential gain'


def buy_rows(result, names):
    return [{'Material': names.get(r['item_id'], f"Item {r['item_id']}"), 'Route': r['method'],
             'Required units': r['quantity'], 'Purchased units': r['purchased_units'],
             'Cost (g)': to_gold(r['cost_copper']), 'Highest unit price (g)': to_gold(r['highest_unit_copper']),
             'Scan p25 (g)': to_gold(r['p25_copper']), 'Cheap now': r['cheap_now'], 'State': state(r)}
            for r in result['buy']]


def vendor_rows(result, names):
    return [{'Item': names.get(r['item_id'], f"Item {r['item_id']}"), 'Units': r['purchased_units'],
             'Cost (g)': to_gold(r['cost_copper']), 'Vendor pays per unit (g)': to_gold(r['vendor_sell_copper']),
             'Highest listing unit (g)': to_gold(r['highest_unit_copper']), 'Gain (g)': to_gold(r['gain_copper']),
             'State': state(r)} for r in result['below_vendor']]


def details_dialog(row):
    details = craft_details(row)
    with ui.dialog() as dialog, ui.card().classes('w-full'):
        ui.label(f"Materials for {row['output_name']} · {row['batch_size']} crafts")
        table([{'Material': r['item_name'], 'Route': 'vendor' if r['method'] == 'vendor' else 'auction house',
                'Required units': r['quantity'], 'Purchased units': r['purchased_units'],
                'Cost (g)': to_gold(r['cost_copper']),
                'Highest unit price (g)': to_gold(r['highest_unit_copper']), 'State': state(r)}
               for r in details['materials']], label='Materials')
        ui.label(f"Batch material cost: {format_money(row['batch_cost_copper'])}. "
                 'Whole-stack surplus has no revenue credit. Vendor stock is unknown.')
        for step in details['intermediate_steps']:
            ui.label(f"{'↳ ' * step['depth']}{step['item_name']}: {step['crafts']} crafts → "
                     f"{step['quantity']} units · {state(step)}")
        ui.button('Close', on_click=dialog.close)
    dialog.on('hide', dialog.delete)
    dialog.open()


def freshness_caption(freshness, config):
    if freshness['upstream_known']:
        ui.label(f"Prices scanned {freshness['age_hours']:.1f} hours ago "
                 f"({freshness['observed_at']:%Y-%m-%d %H:%M} UTC) · stale after {config['max_age_hours']} hours")
    else:
        ui.label(f"Price age unknown: this source gives no scan time. Downloaded "
                 f"{freshness['age_hours']:.1f} hours ago; prices may be older. "
                 f"Stale after {config['max_age_hours']} hours since download.")
    if freshness['stale']:
        with ui.card().props('flat bordered'):
            ui.icon('warning', color='warning')
            ui.label('Saved prices are stale or future-dated. Refresh before acting on them.')


def watchlist_hits(config, catalogs):
    try:
        entries = load_entries(watchlist_path(config['data_dir'], config['source_id']))
        if not entries:
            return
        with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb'), read_only=True) as db:
            result = read_watchlist(db, config, entries, datetime.now(UTC))
            names = known_names(db, config, catalogs)
        hits = [r for r in result['rows'] if r['buy_hit'] or r['sell_hit']]
        if hits:
            with ui.expansion(f'Watchlist hits ({len(hits)})', value=True):
                for row in hits:
                    ui.label(_hit_text(row, names))
    except Exception as error:
        ui.label(f'Watchlist evidence unavailable: {error}')


def _hit_text(row, names):
    # Same wording as the Streamlit panel (views/watchlist.render_hits): only the sides that hit.
    states = []
    if row['buy_hit']:
        units = (f"{row['buy_units']} units at or below target" if row['buy_units'] is not None
                 else 'units not available for this source')
        states.append(f"Buy {row['buy_state']} · {units}")
    if row['sell_hit']:
        states.append(f"Sell {row['sell_state']}")
    item = row['entry'].item_id
    return f"{names.get(item, 'Unknown item')} ({item}) · {format_money(row['price'])} · {'; '.join(states)}"


def settings_form(config, saved, character_data, on_saved, *, unreadable=False):
    identities = [None, *available_characters(character_data)]
    selected = resolve_character(saved.character, character_data)
    if saved.character is not None and selected is None:
        ui.label('Saved character is no longer present in this source and market; showing Our team.')
    funds = resolve_funds(saved, character_data, datetime.now(UTC), config['max_age_hours'])
    with ui.expansion('Today settings', value=unreadable or funds.settings.gold_copper == 0).classes('w-full'):
        ui.label('One funded plan · whole auction stacks are bought; surplus is shown · sales speed is unknown')
        with ui.row():
            character = ui.select({str(i): 'Our team' if c is None else ' · '.join(c)
                                   for i, c in enumerate(identities)}, value=str(identities.index(selected)),
                                  label='Character')
            unknown = ui.switch('Include unknown recipes', value=saved.include_unknown)
            override = ui.switch('Enter an amount instead', value=saved.gold_override)
            gold = ui.input('Gold available', value=format_money(saved.gold_copper))
            mode = ui.select(['scaled', 'fixed'], value=saved.mode, label='Minimum gain mode')
            minimum = ui.input('Fixed minimum gain', value=format_money(saved.minimum_copper))
            percent = ui.number('Percentage of gold available', value=saved.percent_basis_points / 100,
                                min=0, max=100, step=.1)
            crafts = ui.number('Most crafts per item', value=saved.max_crafts, min=1, max=1000, step=1)
        message = ui.label('')

        def save():
            try:
                count = float(crafts.value)
                if not count.is_integer():
                    raise ValueError('Most crafts per item must be an integer')
                entered = TodaySettings(parse_money(gold.value), parse_money(minimum.value), mode.value,
                                        round(float(percent.value) * 100), int(count),
                                        identities[int(character.value)], override.value, unknown.value)
                save_settings(settings_path(config['data_dir'], config['source_id']), entered)
            except (ValueError, TypeError, OSError) as error:
                message.set_text(f'Settings not saved: {error}. Tables still use the last saved settings.')
            else:
                message.set_text('Today settings saved locally.')
                on_saved(entered)

        ui.button('Save Today settings', on_click=save)


def plan_tables(result, names, active_tab, config):
    sells = {r['output_item_id']: r for r in result['sell']}
    crafts = [{**craft_row(r, sells[r['output_item_id']]), 'id': i} for i, r in enumerate(result['craft'])]
    with ui.tabs(value=active_tab) as tabs:
        for name in TABS:
            ui.tab(name)
    tabs.on_value_change(lambda e: ui.navigate.history.replace('/?' + urlencode({
        'game': config['game_version'], 'source': config['source_id'], 'tab': e.value})))
    with ui.tab_panels(tabs, value=active_tab).classes('w-full'):
        with ui.tab_panel('Craft'):
            if result['character_note']:
                ui.label(result['character_note'])
            widget = table(crafts, label='Craft')
            widget.on('rowClick', lambda e: details_dialog(result['craft'][e.args[1]['id']]))
            ui.label(f"{result['remaining']['craft']} more rows outside this list's 10-row limit.")
            ui.label('Click a craft to inspect materials and catalog steps.')
            ui.label('Hidden recipes: ' + ('; '.join(f'{k}: {v}' for k, v in sorted(result['hidden'].items())) or '0'))
            with ui.expansion('Catalog checks'):
                if result['catalog_checks']:
                    table(result['catalog_checks'], label='Catalog checks')
                else:
                    ui.label('No differences in comparable matched recipe evidence.')
        with ui.tab_panel('Buy'):
            table(buy_rows(result, names), label='Buy')
            ui.label(f"{result['remaining']['buy']} more rows outside this list's 10-row limit.")
            ui.label(f"Whole shopping list: {format_money(result['shopping_total_copper'])}. "
                     'Cheap now means average paid is strictly below scan p25; informational only. '
                     'Vendor stock is unknown.')
        with ui.tab_panel('Sell'):
            table([sell_row(r) for r in result['sell']], label='Sell')
            ui.label(f"{result['remaining']['sell']} more rows outside this list's 10-row limit.")
        with ui.tab_panel('Below vendor'):
            ui.label('Independent aside, not part of the craft budget.')
            table(vendor_rows(result, names), label='Below vendor')
            ui.label(f"{result['remaining']['below_vendor']} more rows outside this list's 10-row limit.")
    return tabs


def render(config, catalogs, character_data, active_tab='Craft'):
    path = settings_path(config['data_dir'], config['source_id'])
    unreadable = False
    try:
        saved = load_settings(path)
    except (ValueError, TypeError, OSError) as error:
        ui.label(f'Could not read Today settings: {error}. Defaults are shown; save to replace this file.')
        saved = TodaySettings()
        unreadable = True
    current_tab = active_tab if active_tab in TABS else 'Craft'
    summary = ui.label('')
    plan = ui.column().classes('w-full')

    def update(settings):
        nonlocal current_tab
        funds = resolve_funds(settings, character_data, datetime.now(UTC), config['max_age_hours'])
        settings = funds.settings
        summary.set_text(funds.summary)
        plan.clear()
        with plan:
            for note in funds.notes:
                ui.label(note)
            if not settings.gold_copper:
                ui.label('Enter the gold you have available to size the plan. Use explicit units, for example 12g 50s.')
            try:
                manifest, arguments = load_today(config, catalogs, settings, character_data, datetime.now(UTC))
                if manifest is None:
                    ui.label('Refresh or import a scan for this market to inspect Today.')
                    return
                result = build_today(**arguments)
            except Exception as error:
                ui.label(f'Unable to build Today: {error}')
                return
            freshness_caption(result['freshness'], config)
            ui.label(f"Today rules v{result['today_version']} · cautious output price · {config['auction_cut']:.0%} "
                     f"auction cut · source {config['source_id']} · market {config['market_id']} · "
                     f"snapshot {arguments['snapshot']['snapshot_id']} · "
                     f"scan {manifest.get('scan_id', 'not available for this source')} · "
                     f"evidence {result['freshness']['observed_at']} (UTC) · time basis {result['freshness']['basis']}")
            if not result['listing_evidence_available']:
                ui.label('Individual listings, thin markets, cheap now, undercuts and below-vendor listings: '
                         'not available for this source. Batches use funds and the per-item cap; '
                         'costs are aggregate estimates.')
            watchlist_hits(config, catalogs)
            names = {i: item['name'] for c in catalogs for i, item in c['items_by_id'].items()}
            tabs = plan_tables(result, names, current_tab, config)

            def remember(e):
                nonlocal current_tab
                current_tab = e.value

            tabs.on_value_change(remember)

    settings_form(config, saved, character_data, update, unreadable=unreadable)
    update(saved)
