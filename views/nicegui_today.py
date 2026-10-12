"""Native NiceGUI Today components over the shared saved-evidence path."""
from datetime import UTC, datetime
from functools import partial
from urllib.parse import urlencode

import duckdb
from nicegui import app, ui

from brownstone.freshness import STALE_WARNING, age_caption
from brownstone.money import format_money, parse_money
from brownstone.today import build_today, craft_details, purchase_uses
from brownstone.today_characters import available_characters, resolve_character
from brownstone.today_funds import resolve_funds
from brownstone.today_loading import load_today, load_today_characters
from brownstone.today_session import digest, plan_context, queue_line, queue_total, stable_queue
from brownstone.today_settings import TodaySettings, load_settings, save_settings, settings_path
from brownstone.watchlist import hit_text, known_names, load_entries, read_watchlist, watchlist_path
from views import today_rows as tr

TABS = ['Craft', 'Buy', 'Sell', 'Below vendor', 'Queue']


def table(rows, *, label, row_key='id'):
    rows = [{**row, 'id': i} for i, row in enumerate(rows)]
    keys = list(dict.fromkeys(key for row in rows for key in row if key != 'id'))
    decisions = {
        'Craft': ['Item', 'State', 'Can make', 'Who can make it', 'Batch', 'Material cost (g)',
                  'Batch profit (g)', 'Profit per craft (g)', 'Confidence'],
        'Sell': ['Output', 'State', 'Batch', 'Lowest competing unit (g)', 'Listings', 'Units',
                 'Undercut unit (g)', 'Profit at undercut for batch (g)', 'Thin', 'Confidence', 'Reasons'],
        'Buy': ['Material', 'State', 'Route', 'For', 'Required units', 'Purchased units', 'Cost (g)',
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


def buy_rows(result, names):
    uses = purchase_uses(result['craft'])
    return [tr.buy_row(r, names, used_for='; '.join(f'{name}: {units} units'
                                                 for name, units in uses[(r['item_id'], r['method'])].items()))
            for r in result['buy']]


def details_dialog(row):
    details = craft_details(row)
    with ui.dialog() as dialog, ui.card().classes('w-full'):
        ui.label(f"Materials for {row['output_name']} · {row['batch_size']} crafts")
        table([tr.material_row(r) for r in details['materials']], label='Materials')
        ui.label(f"Batch material cost: {format_money(row['batch_cost_copper'])}. "
                 'Whole-stack surplus has no revenue credit. Vendor stock is unknown.')
        for step in details['intermediate_steps']:
            ui.label(f"{'↳ ' * step['depth']}{step['item_name']}: {step['crafts']} crafts → "
                     f"{step['quantity']} units · {tr.state(step)}")
        ui.button('Close', on_click=dialog.close)
    dialog.on('hide', dialog.delete)
    dialog.open()


def freshness_caption(freshness, config):
    ui.label(age_caption(freshness, config['max_age_hours']))
    if freshness['stale']:
        with ui.card().props('flat bordered'):
            ui.icon('warning', color='warning')
            ui.label(STALE_WARNING)


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
                    ui.label(hit_text(row, names))
    except Exception as error:
        ui.label(f'Watchlist evidence unavailable: {error}')


def settings_form(config, saved, character_data, on_saved, *, unreadable=False):
    identities = [None, *available_characters(character_data)]
    selected = resolve_character(saved.character, character_data)
    if saved.character is not None and selected is None:
        ui.label(tr.MISSING_CHARACTER)
    funds = resolve_funds(saved, character_data, datetime.now(UTC), config['max_age_hours'])
    with ui.expansion('Today settings', value=unreadable or funds.settings.gold_copper == 0).classes('w-full'):
        ui.label(tr.SETTINGS_NOTE)
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
    crafts = [{**tr.craft_row(r, sells[r['output_item_id']]), 'id': i} for i, r in enumerate(result['craft'])]
    with ui.tabs(value=active_tab) as tabs:
        for name in TABS:
            ui.tab(name)
    tabs.on_value_change(lambda e: app.storage.tab.update({'today-active-tab': e.value}))
    tabs.on_value_change(lambda e: ui.navigate.history.replace('/?' + urlencode({
        'game': config['game_version'], 'source': config['source_id'], 'place': 'Today', 'tab': e.value})))
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
                display = ui.toggle(['Cards', 'Table'], value=(session or {}).get('display', 'Cards'))
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
            ui.label(f"{result['remaining']['craft']} {tr.ROW_LIMIT_NOTE}.")
            ui.label('Open a card or click a table row to inspect materials and catalog steps.')
            ui.label(tr.hidden_line(result['hidden']))
            with ui.expansion('Catalog checks'):
                if result['catalog_checks']:
                    table(result['catalog_checks'], label='Catalog checks')
                else:
                    ui.label('No differences in comparable matched recipe evidence.')
        with ui.tab_panel('Buy'):
            table(buy_rows(result, names), label='Buy')
            ui.label(f"{result['remaining']['buy']} {tr.ROW_LIMIT_NOTE}.")
            ui.label(tr.shopping_line(result))
        with ui.tab_panel('Sell'):
            table([tr.sell_row(r) for r in result['sell']], label='Sell')
            ui.label(f"{result['remaining']['sell']} {tr.ROW_LIMIT_NOTE}.")
        with ui.tab_panel('Below vendor'):
            ui.label(tr.VENDOR_ASIDE)
            table([tr.vendor_row(r, names) for r in result['below_vendor']], label='Below vendor')
            ui.label(f"{result['remaining']['below_vendor']} {tr.ROW_LIMIT_NOTE}.")
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
                ui.label(tr.ZERO_GOLD_HINT)
            try:
                manifest, arguments = load_today(config, catalogs, settings, latest_characters, datetime.now(UTC))
                if manifest is None:
                    ui.label(tr.NO_SNAPSHOT)
                    return
                result = session_plan(arguments, session, reset_note)
            except Exception as error:
                ui.label(f'Unable to build Today: {error}')
                return
            freshness_caption(result['freshness'], config)
            ui.label(tr.provenance(result, config, manifest, arguments['snapshot']['snapshot_id']))
            if not result['listing_evidence_available']:
                ui.label(tr.NO_LISTINGS)
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
    with ui.card().classes('w-full rounded-xl shadow-sm border-l-4 border-amber-800').mark('craft-card'):
        ui.label(f"{row['output_name']} · {row['batch_size']} crafts").classes('text-xl font-semibold')
        ui.label(f"Batch profit {format_money(row['batch_profit_copper'])} · "
                 f"per craft {format_money(row['profit_per_craft_copper'])}")
        character = tr.craft_row(row, sell)
        capability = [f"{key}: {character[key]}" for key in ('Can make', 'Who can make it') if key in character]
        ui.label(' · '.join([f"{row['confidence']} confidence", *capability, tr.state(row)]))
        if character.get('Learning'):
            ui.label(character['Learning'])
        ui.label(f"Cautious sale {format_money(row['sale_price_copper'])} · "
                 f"{competition(sell)} · "
                 f"limited by {row['limiting_factor']}" + (' · thin' if sell['thin'] else ''))
        with ui.expansion('What to buy and where to sell').classes('w-full'):
            ui.label(f"What to buy · Material cost {format_money(row['batch_cost_copper'])}").classes('font-semibold')
            for material in details['materials']:
                route = 'vendor' if material['method'] == 'vendor' else 'auction house'
                ui.label(f"{material['item_name']} · {route} · {material['purchased_units']} units · "
                         f"{format_money(material['cost_copper'])} · "
                         f"highest unit {format_money(material['highest_unit_copper'])}")
            for step in details['intermediate_steps']:
                ui.label(f"{'↳ ' * step['depth']}{step['item_name']}: {step['crafts']} crafts").style(
                    f"margin-left: {step['depth']}rem")
            price, profit = sell['undercut_copper'], sell['undercut_batch_profit_copper']
            ui.label(f"Where to sell · Auction house · "
                     f"Sell at {format_money(price) if price is not None else 'unavailable'} · "
                     f"{competition(sell)} · "
                     f"profit {format_money(profit) if profit is not None else 'unavailable'}")


def competition(sell):
    if sell['listings'] is None or sell['units'] is None:
        return 'competing listings and units not available for this source'
    return f"{sell['listings']} listings / {sell['units']} units"


def queue_panel(result, session):
    queue = result['queue']
    identity = digest({'queue': stable_queue(queue), 'context': session.get('context')})
    if session.get('queue_identity') != identity:
        session.update(queue_identity=identity, ticks={})
    texts = [queue_line(line) for line in queue['lines']]
    for i, text in enumerate(texts):
        ui.checkbox(text, value=session['ticks'].get(str(i), False),
                    on_change=lambda e, index=str(i): session['ticks'].update({index: e.value}))
    total = queue_total(queue)
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
            reset_note.set_text(tr.PLAN_RESET)
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
        ui.label(tr.unreadable_settings(error))
        return TodaySettings(), True
    return saved, False
