"""Native NiceGUI Today components over the shared saved-evidence path."""
from datetime import UTC, datetime
from functools import partial
from urllib.parse import urlencode

import duckdb
from nicegui import app, ui

from brownstone.money import format_money, parse_money, to_gold
from brownstone.today import build_today, craft_details
from brownstone.today_characters import available_characters, resolve_character
from brownstone.today_funds import resolve_funds
from brownstone.today_loading import load_today, load_today_characters
from brownstone.today_session import digest, plan_context, queue_line
from brownstone.today_settings import TodaySettings, load_settings, save_settings, settings_path
from brownstone.watchlist import known_names, load_entries, read_watchlist, watchlist_path
from views.today_rows import craft_row, sell_row

TABS = ['Craft', 'Buy', 'Sell', 'Below vendor', 'Queue']


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


def plan_tables(result, names, active_tab, config, session=None, on_change=None):
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
            if session is not None:
                adjustment_controls(result, session, on_change)
                if session.get('hide_low'):
                    crafts = [r for r in crafts if r['Confidence'] != 'Low']
                    ui.label(f"Hidden Low confidence: {len(result['craft']) - len(crafts)}")
            with ui.row():
                display = ui.toggle(['Table', 'Cards'], value=(session or {}).get('display', 'Table'))
            table_area = ui.column().classes('w-full')
            card_area = ui.column().classes('w-full')
            table_area.bind_visibility_from(display, 'value', backward=lambda v: v == 'Table')
            card_area.bind_visibility_from(display, 'value', backward=lambda v: v == 'Cards')
            with card_area:
                for row in result['craft']:
                    if not (session or {}).get('hide_low') or row['confidence'] != 'Low':
                        craft_card(row, sells[row['output_item_id']])
            if session is not None:
                display.on_value_change(lambda e: session.update(display=e.value))
            with table_area:
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
        with ui.tab_panel('Queue'):
            queue_panel(result, session if session is not None else {})
    return tabs


def render(config, catalogs, character_data, active_tab='Craft'):
    saved, unreadable = read_saved_settings(config)
    current_tab = active_tab if active_tab in TABS else 'Craft'
    storage = app.storage.tab
    key = 'today-plan-' + config['source_id']
    session = storage.setdefault(key, {})
    reset_note = ui.label('')
    summary = ui.label('')
    plan = ui.column().classes('w-full')

    def update(settings):
        nonlocal current_tab
        latest_characters, warning = load_today_characters(config)
        funds = resolve_funds(settings, latest_characters, datetime.now(UTC), config['max_age_hours'])
        settings = funds.settings
        summary.set_text(funds.summary)
        plan.clear()
        with plan:
            if warning:
                ui.label(warning)
            for note in funds.notes:
                ui.label(note)
            if not settings.gold_copper:
                ui.label('Enter the gold you have available to size the plan. Use explicit units, for example 12g 50s.')
            try:
                manifest, arguments = load_today(config, catalogs, settings, latest_characters, datetime.now(UTC))
                if manifest is None:
                    ui.label('Refresh or import a scan for this market to inspect Today.')
                    return
                result = session_plan(arguments, session, reset_note)
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
            tabs = plan_tables(result, names, current_tab, config, session, lambda: update(saved_settings[0]))

            def remember(e):
                nonlocal current_tab
                current_tab = e.value

            tabs.on_value_change(remember)

    saved_settings = [saved]

    def settings_saved(settings):
        saved_settings[0] = settings
        update(settings)

    settings_form(config, saved, character_data, settings_saved, unreadable=unreadable)
    update(saved)


def adjustment_controls(result, session, on_change):
    def change(identity=None, *, size=None, checked=None, **flags):
        session.update(flags)
        choices = session['choices']
        if identity is not None or 'refill' in flags:
            if choices is None:
                choices = [{k: r[k] for k in ('catalog_id', 'recipe_id', 'batch_size')} for r in session['rows']]
            for choice in choices:
                if (choice['catalog_id'], choice['recipe_id']) == identity:
                    choice['batch_size'] = size if size is not None else (
                        next(r['batch_size'] for r in session['rows']
                             if (r['catalog_id'], r['recipe_id']) == identity) if checked else None)
            session['choices'] = choices
        on_change()

    with ui.row().classes('items-center gap-6'):
        ui.switch('Refill freed gold', value=session['refill'],
                  on_change=lambda e: change(refill=e.value))
        ui.switch('Hide Low confidence', value=session.get('hide_low', False),
                  on_change=lambda e: change(hide_low=e.value))
    limits = {(r['catalog_id'], r['recipe_id']): r['maximum'] for r in result['choice_limits']}
    selected = {(r['catalog_id'], r['recipe_id']): r['batch_size'] for r in result['craft']}
    for dropped in result['dropped_choices']:
        name = next((r['output_name'] for r in session['rows']
                     if (r['catalog_id'], r['recipe_id']) == (dropped['catalog_id'], dropped['recipe_id'])),
                    f"Recipe {dropped['recipe_id']}")
        ui.label(f"{name}: {dropped['reason']}")
    with ui.expansion('Adjust crafts', value=session.get('adjust_open', False)).classes('w-full') as adjustments:
        adjustments.on_value_change(lambda e: session.update(adjust_open=e.value))
        for row in session['rows']:
            identity = (row['catalog_id'], row['recipe_id'])
            maximum = limits.get(identity, row['feasible_size'])
            with ui.row().classes('items-center w-full gap-4'):
                choose = ui.checkbox(row['output_name'], value=identity in selected,
                            on_change=lambda e, key=identity: change(key, checked=e.value)
                              ).classes('min-w-40').props('dense').mark('choose-' + str(identity))
                box = ui.number(f"Batch for {row['output_name']}", value=selected.get(identity, 1),
                                min=1, max=max(1, maximum), step=1).classes('w-56').props('dense outlined')
                if maximum == 0:  # As in Streamlit: nothing affordable, so nothing to choose.
                    choose.disable()
                    box.disable()
                # Commit on blur or Enter: a rebuild per keystroke would replace the box mid-typing.
                commit = partial(commit_batch, box, identity, maximum, selected.get(identity), change)
                box.on('blur', commit)
                box.on('keydown.enter', commit)


def commit_batch(box, identity, maximum, current, change):
    if box.value != current:
        batch_change(box.value, identity, maximum, change)


def batch_change(value, identity, maximum, change):
    if value is None or not float(value).is_integer() or not 1 <= value <= maximum:
        ui.notify('Batch must be a whole number within the current bound.', type='warning')
        return
    change(identity, size=int(value))


def craft_card(row, sell):
    details = craft_details(row)
    with ui.card().classes('w-full rounded-xl shadow-sm border-l-4 border-amber-800').mark('craft-card') as card:
        card._props['cost_copper'] = row['batch_cost_copper']
        card._props['materials_copper'] = sum(r['cost_copper'] for r in details['materials'])
        ui.label(f"{row['output_name']} · {row['batch_size']} crafts").classes('text-xl font-semibold')
        ui.label(f"Batch profit {format_money(row['batch_profit_copper'])} · "
                 f"per craft {format_money(row['profit_per_craft_copper'])}")
        ui.label(f"{row['confidence']} confidence · Can make: {row.get('craft_status', 'Unknown')} · "
                 f"{', '.join(row.get('who_can_make_it', [])) or 'unknown'} · {state(row)}")
        ui.label(f"Cautious sale {format_money(row['sale_price_copper'])} · "
                 f"{sell['listings']} listings / {sell['units']} units · "
                 f"limited by {row['limiting_factor']}" + (' · thin' if sell['thin'] else ''))
        with ui.expansion('What to buy and where to sell').classes('w-full'):
            for material in details['materials']:
                route = 'vendor' if material['method'] == 'vendor' else 'auction house'
                ui.label(f"{material['item_name']} · {route} · {material['purchased_units']} units · "
                         f"{format_money(material['cost_copper'])} · "
                         f"highest unit {format_money(material['highest_unit_copper'])}")
            for step in details['intermediate_steps']:
                ui.label(f"{'↳ ' * step['depth']}{step['item_name']}: {step['crafts']} crafts")
            price, profit = sell['undercut_copper'], sell['undercut_batch_profit_copper']
            ui.label(f"Sell at {format_money(price) if price is not None else 'unavailable'} · "
                     f"profit {format_money(profit) if profit is not None else 'unavailable'}")


def queue_panel(result, session):
    queue = result['queue']
    stable = {**queue, 'lines': [{k: v for k, v in line.items() if k not in ('confidence', 'confidence_reasons')}
                                for line in queue['lines']]}
    identity = digest({'queue': stable, 'context': session.get('context')})
    if session.get('queue_identity') != identity:
        session.update(queue_identity=identity, ticks={})
    texts = [queue_line(line) for line in queue['lines']]
    for i, text in enumerate(texts):
        ui.checkbox(text, value=session['ticks'].get(str(i), False),
                    on_change=lambda e, index=str(i): session['ticks'].update({index: e.value}))
    profit = queue['expected_profit_copper']
    total = (f"Gold needed: {format_money(queue['gold_needed_copper'])} · "
             f"Expected profit at undercut: {format_money(profit) if profit is not None else 'unavailable'}")
    ui.label(total)
    if result['freshness']['stale']:
        ui.label('stale — inspect only')
    with ui.expansion('Copy as text'):
        ui.code('\n'.join([*texts, total]), language='text')


def session_plan(arguments, session, reset_note):
    context = plan_context(arguments)
    reset_note.set_text('')  # As in Streamlit, the note shows only on the rebuild that reset.
    if session.get('context') != context:
        if session:
            reset_note.set_text('Scan, settings or catalog evidence changed: session choices and queue ticks '
                                'reset. Previous choices were dropped, not resized; a fresh default plan is shown.')
        session.clear()
        session.update(context=context, choices=None, refill=True, rows=[], ticks={})
    result = build_today(**arguments, choices=session['choices'], refill=session['refill'])
    # As in Streamlit, a dropped choice is unticked so it isn't requested again.
    dropped = {(d['catalog_id'], d['recipe_id']) for d in result['dropped_choices']}
    for choice in session['choices'] or []:
        if (choice['catalog_id'], choice['recipe_id']) in dropped:
            choice['batch_size'] = None
    known = {(r['catalog_id'], r['recipe_id']) for r in session['rows']}
    new_rows = [r for r in sorted(result['craft'], key=lambda r: r['plan_order'])
                if (r['catalog_id'], r['recipe_id']) not in known]
    session['rows'].extend(new_rows)
    if session['choices'] is not None:
        session['choices'].extend({k: r[k] for k in ('catalog_id', 'recipe_id', 'batch_size')} for r in new_rows)
    return result


def read_saved_settings(config):
    path = settings_path(config['data_dir'], config['source_id'])
    try:
        saved = load_settings(path)
    except (ValueError, TypeError, OSError) as error:
        ui.label(f'Could not read Today settings: {error}. Defaults are shown; save to replace this file.')
        return TodaySettings(), True
    return saved, False
