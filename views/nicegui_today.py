"""Native NiceGUI Today components over the shared saved-evidence path."""
from datetime import UTC, datetime
from functools import partial
from urllib.parse import urlencode

import duckdb
from nicegui import app, ui

from brownstone.freshness import STALE_WARNING, age_caption
from brownstone.money import format_money, parse_money
from brownstone.recipe_graph import step_label
from brownstone.session_options import build_options
from brownstone.today import build_today, craft_details, purchase_uses
from brownstone.today_characters import available_characters, resolve_character
from brownstone.today_funds import resolve_funds
from brownstone.today_loading import load_today, load_today_characters
from brownstone.today_session import digest, plan_context, queue_line, queue_total, stable_queue
from brownstone.today_settings import TodaySettings, load_settings, save_settings, settings_path
from brownstone.watchlist import hit_text, known_names, load_entries, read_watchlist, watchlist_path
from views import nicegui_theme as theme
from views import today_rows as tr
from views.nicegui_market import item_link

TABS = ['Plan', 'Shopping list', 'Sell', 'Queue', 'Extras']
LEGACY_TABS = {'Craft': 'Plan', 'Buy': 'Shopping list', 'Below vendor': 'Extras'}


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
    if label == 'Reachable recipes':
        widget.add_slot('body-cell-Status', '<q-td :props="props"><span class="bs-badge bs-neutral">'
                        '{{props.value}}</span></q-td>')
        widget.add_slot('body-cell-Confidence', '<q-td :props="props"><span class="bs-badge" '
                        ':class="props.value === \'High\' ? \'bs-good\' : \'bs-warn\'">'
                        '{{props.value}}</span></q-td>')
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
            ui.label(f"{'↳ ' * step['depth']}{step_label(step)}: {step['crafts']} crafts → "
                     f"{step['quantity']} units · {tr.state(step)}")
        ui.button('Close', on_click=dialog.close)
    dialog.on('hide', dialog.delete)
    dialog.open()


def freshness_caption(freshness, config, *, banner=True):
    with ui.row().classes('bs-chip'):
        if freshness['stale']:
            theme.badge('Stale', 'warn')
        ui.label(tr.scan_status(freshness))
    if freshness['stale'] and banner:
        scan_banner(freshness)


def scan_banner(freshness):
    theme.banner(tr.stale_banner(freshness), 'How to scan', scan_help)


def scan_help():
    with theme.dialog('How to scan') as popup:
        ui.label('Open the auction house and run /bscan. Wait for the scan to finish, then /reload '
                 'or log out to save the file. Use Data → Import to check for new scans and import.')
        ui.label("Don't /bscan clear until the new scan is imported.")
    popup.on('hide', popup.delete)
    popup.open()


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
    with theme.dialog('Today settings') as dialog:
        ui.label(tr.SETTINGS_NOTE)
        stored = [saved]
        with ui.element('div').classes('bs-settings-grid'):
            character = ui.select({str(i): 'Our team' if c is None else ' · '.join(c)
                                   for i, c in enumerate(identities)}, value=str(identities.index(selected)),
                                  label='Character').classes('w-full')
            unknown = ui.switch('Include unknown recipes', value=saved.include_unknown)
            override = ui.switch('Enter an amount instead', value=saved.gold_override)
            gold = ui.input('Gold available', value=format_money(saved.gold_copper))
            mode = ui.select({'fixed': 'Fixed amount', 'scaled': 'Scale with available gold'},
                             value=saved.mode, label='Minimum gain mode').classes('w-full')
            minimum = ui.input('Fixed minimum gain', value=format_money(saved.minimum_copper))
            percent = ui.number('Percentage of gold available', value=saved.percent_basis_points / 100,
                                min=0, max=100, step=.1)
            crafts = ui.number('Most crafts per item', value=saved.max_crafts, min=1, max=1000, step=1)
        percent.bind_visibility_from(mode, 'value', backward=lambda value: value == 'scaled')
        ui.label('Scaled uses the greater of the fixed minimum and this percentage of available gold.').classes(
            'bs-note').bind_visibility_from(mode, 'value', backward=lambda value: value == 'scaled')
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
                stored[0] = entered
                message.set_text('Today settings saved locally.')
                on_saved(entered)
                dialog.close()
                ui.notify('Today settings saved locally.', type='positive')

        with ui.row().classes('w-full justify-end'):
            ui.button('Cancel', on_click=dialog.close).props('flat')
            ui.button('Save Today settings', on_click=save)
    def open_settings():
        current = stored[0]
        character.set_value(str(identities.index(resolve_character(current.character, character_data))))
        unknown.set_value(current.include_unknown)
        override.set_value(current.gold_override)
        gold.set_value(format_money(current.gold_copper))
        mode.set_value(current.mode)
        minimum.set_value(format_money(current.minimum_copper))
        percent.set_value(current.percent_basis_points / 100)
        crafts.set_value(current.max_crafts)
        message.set_text('')

        dialog.open()

    theme.settings_button(open_settings)
    if unreadable:
        open_settings()
    return open_settings

def plan_tables(result, names, active_tab, config, session=None, on_change=None):
    sells = {r['output_item_id']: r for r in result['sell']}
    crafts = [{**tr.craft_row(r, sells[r['output_item_id']]), 'id': i} for i, r in enumerate(result['craft'])]
    with ui.tabs(value=active_tab).classes('bs-tabs') as tabs:
        for name in TABS:
            ui.tab(name)
    tabs.on_value_change(lambda e: app.storage.tab.update({'today-active-tab': e.value}))
    tabs.on_value_change(lambda e: ui.navigate.history.replace('/?' + urlencode({
        'game': config['game_version'], 'source': config['source_id'], 'place': 'Today', 'tab': e.value})))
    with ui.tab_panels(tabs, value=active_tab).classes('w-full'):
        with ui.tab_panel('Plan'):
            if result['character_note']:
                ui.label(result['character_note'])
            if session is not None:
                with ui.expansion('Plan controls', value=session.get('controls_open', False),
                                  on_value_change=lambda e: session.update(controls_open=e.value)):
                    adjustment_controls(result, session, on_change)
                if session.get('hide_low'):
                    crafts = [r for r in crafts if r['Confidence'] != 'Low']
            with ui.row().classes('w-full justify-end'):
                display = ui.toggle(['Cards', 'Table'], value=(session or {}).get('display', 'Cards')).mark(
                    'plan-display')
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

            with ui.expansion('Catalog checks'):
                if result['catalog_checks']:
                    table(result['catalog_checks'], label='Catalog checks')
                else:
                    ui.label('No differences in comparable matched recipe evidence.')
        with ui.tab_panel('Shopping list'):
            table(buy_rows(result, names), label='Buy')

            ui.label(tr.shopping_line(result))
        with ui.tab_panel('Sell'):
            table([tr.sell_row(r) for r in result['sell']], label='Sell')

        with ui.tab_panel('Extras'):
            ui.label(tr.VENDOR_ASIDE)
            table([tr.vendor_row(r, names) for r in result['below_vendor']], label='Below vendor')

        with ui.tab_panel('Queue'):
            queue_panel(result, session if session is not None else {})
    return tabs


def render(config, catalogs, character_data, active_tab='Craft'):
    saved, unreadable = read_saved_settings(config)
    active_tab = LEGACY_TABS.get(active_tab, active_tab)
    current_tab = active_tab if active_tab in TABS else 'Plan'
    storage = app.storage.tab
    key = 'today-plan-' + config['source_id']
    session = storage.setdefault(key, {})
    reset_note = ui.label('')
    reset_note.bind_visibility_from(reset_note, 'text', backward=bool)
    plan = ui.column().classes('w-full')

    first = [character_data]  # the page already read evidence; later updates re-read it

    def update(settings):
        nonlocal current_tab
        latest_characters, warning = (first.pop(), None) if first else load_today_characters(config)
        funds = resolve_funds(settings, latest_characters, datetime.now(UTC), config['max_age_hours'])
        settings = funds.settings
        plan.clear()
        with plan:
            if warning:
                ui.label(warning)
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
            info[0] = lambda: plan_info(result, config, manifest, arguments, funds, session)
            display = view_toggle(session)
            with ui.column().classes('w-full') as status:
                plan_status(result, settings, funds, config, settings_dialog, open_info, latest_characters, session)
            if not result['listing_evidence_available']:
                ui.label(tr.NO_LISTINGS)
            watchlist_hits(config, catalogs)
            names = {i: item['name'] for c in catalogs for i, item in c['items_by_id'].items()}
            with (session_view(display, config, arguments, result, session, status),
                  ui.expansion('Other plan views') if not result['craft'] else ui.column().classes('w-full gap-3')):
                tabs = plan_tables(result, names, current_tab, config, session, lambda: update(saved_settings[0]))

            def remember(e):
                nonlocal current_tab
                current_tab = e.value

            tabs.on_value_change(remember)

    info = [lambda: no_plan_info(config, saved, character_data)]

    def open_info():
        info[0]()

    theme.info_button('How this plan was made', open_info)
    saved_settings = [saved]

    def settings_saved(settings):
        saved_settings[0] = settings
        update(settings)

    settings_dialog = settings_form(config, saved, character_data, settings_saved, unreadable=unreadable)
    update(saved)


def plan_status(result, settings, funds, config, settings_dialog, open_info, character_data, session):
    with ui.row().classes('items-center gap-3'):
        theme.chip(tr.planning_label(settings.character, character_data))
        freshness_caption(result['freshness'], config, banner=False)
        theme.chip(f'Gold {format_money(settings.gold_copper)} · ' +
                   ('entered' if funds.origin == 'entered amount' else 'recorded'))
        theme.chip(f"{sum(tr.display_hidden(result, session.get('hide_low')).values()):,} recipes hidden · why?",
                   on_click=open_info)
    if result['freshness']['stale']:
        scan_banner(result['freshness'])
    if not result['craft']:
        theme.empty(tr.empty_sentence(result['hidden'], settings.minimum_gain, settings.gold_copper),
                    settings_dialog, open_info)
    else:
        with ui.element('div').classes('bs-tiles'):
            for label, value in tr.summary_tiles(result, hide_low=session.get('hide_low', False)):
                theme.tile(label, value, profit=label in ('Expected profit', 'Best craft'),
                           compact=label == 'Best craft')


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
                if maximum == 0:  # Nothing affordable, so nothing to choose.
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
    character = tr.craft_row(row, sell)
    with ui.card().classes('bs-card').mark('craft-card'):
        with ui.row().classes('w-full justify-between items-start'):
            with ui.column().classes('gap-2 flex-1 min-w-64'):
                with ui.row().classes('items-center'):
                    ui.label(f"{row['output_name']} · {row['batch_size']} crafts").classes('text-xl font-bold')
                    status = character.get('Can make', 'Our team' if row.get('who_can_make_it') else 'Unknown')
                    theme.badge(status, 'good' if status == 'Known' else 'neutral')
                    theme.badge(f"{row['confidence']} confidence", 'good' if row['confidence'] == 'High' else 'warn')
                    if row['stale']:
                        theme.badge('stale — inspect only', 'warn')
                purchases = ', '.join(f"{m['purchased_units']} {m['item_name']}" for m in details['materials'])
                price = sell['undercut_copper']
                step = ' (whole silver: unstackable)' if sell.get('price_step') == 'whole silver' else ''
                ui.label(f"Buy {purchases} · sell at {format_money(price) if price is not None else 'unavailable'}"
                         f"{step} each · {competition(sell)}")
                ui.label(f"Limited by {row['limiting_factor']}" + (' · thin' if sell['thin'] else '')).classes(
                    'bs-note')
            with ui.column().classes('items-end gap-0'):
                ui.label(format_money(row['batch_profit_copper'])).classes('bs-big bs-profit')
                ui.label(f"per craft {format_money(row['profit_per_craft_copper'])} · "
                         f"costs {format_money(row['batch_cost_copper'])}").classes('bs-note')
        with (ui.expansion('What to buy and where to sell').classes('w-full'),
              ui.element('div').classes('bs-details')):
            with ui.column().classes('gap-2'):
                ui.label(f"What to buy · Material cost {format_money(row['batch_cost_copper'])}")
                purchases = tr.material_card_rows(details['materials'])
                ui.table(columns=[{'name': key, 'label': key, 'field': key, 'align': 'left'}
                                  for key in ('Material', 'Where', 'Units', 'Cost')], rows=purchases,
                         row_key='Material').classes('w-full').props('flat hide-bottom').mark('Reserved purchases')
                with ui.expansion('Material evidence'):
                    for material in details['materials']:
                        route = 'vendor' if material['method'] == 'vendor' else 'auction house'
                        ui.label(f"{material['item_name']} · {route} · {material['purchased_units']} units "
                                 f"· {format_money(material['cost_copper'])} · "
                                 f"highest unit {format_money(material['highest_unit_copper'])}")
                        ui.label(f"{material['quantity']} needed").classes('bs-note')
                for choice in row['choices']:
                    if choice.get('route_note'):
                        ui.label(f"{choice['item_name']} · {choice['route_note']}").classes('bs-note')
                for step in details['intermediate_steps']:
                    ui.label(f"{'↳ ' * step['depth']}{step_label(step)}"
                             f": {step['crafts']} crafts").style(
                        f"margin-left: {step['depth']}rem")
            with ui.column().classes('gap-2'):
                profit = sell['undercut_batch_profit_copper']
                ui.label(f"Where to sell · Auction house · Sell at "
                         f"{format_money(price) if price is not None else 'unavailable'} · "
                         f"{competition(sell)} · profit "
                         f"{format_money(profit) if profit is not None else 'unavailable'}")
                ui.label(f"Batch profit {format_money(row['batch_profit_copper'])}")
                ui.label(f"Cautious sale {format_money(row['sale_price_copper'])} · {competition(sell)} · "
                         f"limited by {row['limiting_factor']}" + (' · thin' if sell['thin'] else ''))
                capability = [f"{key}: {character[key]}" for key in ('Can make', 'Who can make it')
                              if key in character]
                ui.label(' · '.join(capability))
                ui.label(character.get('Learning', ''))
                ui.label('Why: ' + '; '.join(row['confidence_reasons']))

def plan_info(result, config, manifest, arguments, funds, session):
    with theme.dialog('How this plan was made') as popup:
        ui.label(tr.provenance(result, config, manifest, arguments['snapshot']['snapshot_id']))
        ui.label(age_caption(result['freshness'], config['max_age_hours']))
        if result['freshness']['stale']:
            ui.label(STALE_WARNING)
        ui.label(funds.summary)
        if funds.settings.gold_override:
            table(tr.recorded_gold_rows(arguments['character_data'], funds.settings.character), label='Recorded gold')
        for note in funds.notes:
            ui.label(note)
        ui.label(tr.SETTINGS_NOTE)
        ui.label(tr.hidden_line(result['hidden']))
        if session.get('hide_low'):
            ui.label(f"Hidden Low confidence: {tr.display_hidden(result, True)['low confidence']}")
        for name, count in result['remaining'].items():
            ui.label(f"{name}: {count} {tr.ROW_LIMIT_NOTE}.")
    popup.on('hide', popup.delete)
    popup.open()


def competition(sell):
    if sell['listings'] is None or sell['units'] is None:
        return 'competing listings and units not available for this source'
    return f"{sell['listings']} listings / {sell['units']} units"


def queue_panel(result, session):
    queue = result['queue']
    ui.label(queue['mail_note']).classes('bs-note')
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
        ui.code('\n'.join([queue['mail_note'], *texts, total]), language='text')


def session_plan(arguments, session, reset_note):
    context = plan_context(arguments)
    reset_note.set_text('')  # The note shows only on the rebuild that reset.
    if session.get('context') != context:
        if session:
            reset_note.set_text(tr.PLAN_RESET)
        session.clear()
        session.update(context=context, choices=None, refill=True, rows=[], ticks={})
    result = build_today(**arguments, choices=session['choices'], refill=session['refill'])
    for warning in result.get('catalog_warnings', []):
        ui.label(warning).classes('bs-note')
    # A dropped choice is unticked so it isn't requested again.
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


def no_plan_info(config, saved, character_data):
    funds = resolve_funds(saved, character_data, datetime.now(UTC), config['max_age_hours'])
    with theme.dialog('How this plan was made') as popup:
        ui.label(f"source {config['source_id']} · market {config['market_id']}")
        ui.label(tr.NO_SNAPSHOT)
        ui.label(funds.summary)
        for note in funds.notes:
            ui.label(note)
    popup.on('hide', popup.delete)
    popup.open()


def view_toggle(session):
    """Sits under the page title in both views so it never moves when the view changes."""
    return ui.toggle(['Today plan', 'This session'], value=session.get('view', 'Today plan')).props(
        'no-caps padding="10px 22px"').classes('text-base').mark('session-view')


def session_view(display, config, arguments, result, session, status):
    """Compose lazily when This session opens and preserve the displayed plan's choices."""
    status.bind_visibility_from(display, 'value', backward=lambda v: v == 'Today plan')
    plan_area = ui.column().classes('w-full')
    options_area = ui.column().classes('w-full gap-4')
    plan_area.bind_visibility_from(display, 'value', backward=lambda v: v == 'Today plan')
    options_area.bind_visibility_from(display, 'value', backward=lambda v: v == 'This session')
    loaded = False

    def show(value):
        nonlocal loaded
        session['view'] = value
        if value != 'This session' or loaded:
            return
        with options_area:
            try:
                window = app.storage.tab.get('team-' + config['source_id'], {}).get('window', 25)
                with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb'), read_only=True) as db:
                    options = build_options(db, config, arguments, result, window=window)
                session_options(options, config)
                loaded = True
            except Exception as error:
                ui.label(f'Unable to build session options: {error}')
    display.on_value_change(lambda e: show(e.value))
    show(display.value)
    return plan_area


CROWDING = {'thin': ('thin: few listings', 'warn'), 'contested': ('contested: many sellers', 'warn')}
OVERSHOOT = {'cheap': ('cheap right now', 'good'), 'high': ('pricier than usual', 'warn'),
             'too few scans': ('price history too short', 'neutral'), 'no buyout': ('no buyout', 'neutral')}


def session_money(value):
    return format_money(value) if value is not None else 'unknown'


def session_signal(signal):
    """Only labels worth acting on; steady and typical stay in the evidence."""
    if signal is None:
        ui.label('Listing / relative-price evidence unavailable').classes('bs-note')
        return
    with ui.row().classes('items-center gap-2'):
        for text, tone in (CROWDING.get(signal['crowding'], (None, None)),
                           OVERSHOOT.get(signal['overshoot']['label'], (None, None))):
            if text:
                theme.badge(text, tone)
        with ui.expansion('Listing evidence').classes('bs-note'):
            churn = signal['churn']
            history = signal['overshoot']
            ui.label(f"{signal['crowding']} · {history['label']} · {signal['listings']} listings · "
                     f"{signal['units']} units · largest stack {signal['largest_stack_units']} / "
                     f"{signal['units']} units")
            ui.label(f"Lowest-buyout changes {churn['changed']} / {churn['pairs']} comparable pairs"
                     if churn['pairs'] else 'Lowest-buyout churn unknown')
            lowest = signal['min_buyout'] if signal['min_buyout'] and signal['min_buyout'] > 0 else None
            ui.label(f"Typical {session_money(history['typical_copper'])} · {history['scans']} earlier priced "
                     f"scans · current lowest {session_money(lowest)}")


def cheap_share(estimate):
    cheap, cost = estimate['cheap_cost_copper'], estimate['cost_copper']
    if cheap is None:
        return 'cheap auction materials unknown'
    if cheap == cost and cost:
        return 'all on materials that are cheap right now'
    return f'{format_money(cheap)} of it on cheap auction materials' if cheap else 'no cheap auction materials'


def step_text(step, character, window):
    """One plain line per option; the figures are the ones in the details below."""
    name = character['character'][0]
    kind = step['kind']
    if kind == 'craft':
        rows = ', '.join(f"{r['batch_size']} {r['output_name']}" for r in character['crafts'])
        return f"Craft {rows} · planned profit {format_money(character['craft_profit_copper'])}"
    if kind == 'nothing':
        return (f'Nothing to craft or level within {window} points. '
                'Gathering is the option here; farming rates come later (STORY-065).')
    if kind == 'evidence':
        return 'No professions seen yet: open each profession window next login so Brownstone can read them.'
    group = step['group']
    profession = group['profession']
    if kind == 'level_profession':
        recipe, estimate = step['recipe'], step['recipe']['estimate']
        more = f" (+{step['more']} more on the way)" if step['more'] else ''
        return (f"Level {profession} {group['rank']} → {recipe['required_skill']} for "
                f"{format_money(estimate['cost_copper'])}, {cheap_share(estimate)} · unlocks {recipe['name']} "
                f"at {format_money(recipe['profit_copper'])} per craft{more}")
    tier = step['tier']
    if kind == 'train':
        return f"{profession} is capped at {tier['cap']}: train {tier['name']} {profession} at a trainer"
    level = character['level']
    reach = (f"{profession} is capped at {tier['cap']}" if group['capped']
             else f"Before {profession} reaches {tier['cap']}")
    now = f"{level} → {tier['required_level']}" if level is not None else f"to {tier['required_level']} (level unknown)"
    return f"{reach}: level {name} {now} to train {tier['name']}"


def session_summary(character, options, config):
    identity = character['character']

    def select(e, key=identity):
        app.storage.tab.setdefault('team-' + config['source_id'], {}).update(character=list(key))
    with ui.row().classes('items-baseline gap-3'):
        link = ui.link(identity[0], '/?' + urlencode({
            'place': 'Team', 'game': config['game_version'], 'source': config['source_id']}))
        link.classes('text-2xl font-bold min-h-[44px] underline').on('click', select)
        level = character['level']
        ui.label(f"level {level if level is not None else 'unknown'} · {' · '.join(identity[1:])}").classes(
            'bs-note')
    for step in character['next_steps']:
        with ui.row().classes('items-start gap-2 no-wrap').mark('session-step'):
            ui.label('→').classes('font-bold')
            ui.label(step_text(step, character, options['window']))


def session_milestone(milestone, group, config):
    estimate = milestone['estimate']
    with ui.card().classes('bs-card').mark('session-recipe'):
        cost = session_money(estimate['cost_copper']) if estimate['complete'] else (
            'incomplete: ' + '; '.join(estimate['reasons']))
        ui.label(f"Reach {milestone['skill']} (+{milestone['skill'] - group['rank']} points) · cost {cost} · "
                 f"{cheap_share(estimate)}").classes('font-bold')
        for recipe in milestone['recipes']:
            with ui.row().classes('items-center gap-2'):
                item_link(config, recipe['output_item_id'], recipe['name'])
                ui.label(f"{session_money(recipe['profit_copper'])} per craft" if recipe['profit_copper'] is not None
                         else f"profit per craft unknown · {recipe['board_reason']}")
                theme.badge(recipe['confidence'] + ' confidence',
                            'warn' if recipe['confidence'] in ('Low', 'Unavailable') else 'neutral')
                if recipe['needs_pattern']:
                    theme.badge('needs pattern or other source', 'warn')
        with ui.expansion('Cost and confidence evidence'):
            for recipe in milestone['recipes']:
                ui.label(f"{recipe['name']}: {'; '.join(recipe['confidence_reasons'])}")
            for step in estimate['steps']:
                ui.label(f"Rank {step['rank']} · {step['recipe']} · {step['expected_crafts']} expected crafts · "
                         f"{format_money(step['cost_copper'])} including training "
                         f"{format_money(step['training_cost_copper'])}")
                for material in step['materials']:
                    item_link(config, material['item_id'], f"{material['item_name']} · "
                              f"{material['quantity']} units per craft · {material['method']}")
                    session_signal(material['signal'])


def session_crafts(character, config):
    ui.label('Crafting to sell').classes('text-lg font-bold')
    if not character['crafts']:
        ui.label('No reserved Today plan rows this character can make.')
        return
    ui.label(f"Planned profit total {format_money(character['craft_profit_copper'])}")
    for row in character['crafts']:
        with ui.card().classes('bs-card').mark('session-craft'):
            item_link(config, row['output_item_id'], row['output_name'])
            with ui.row().classes('items-center gap-2'):
                theme.badge(row['session_status']['craft_status'])
                theme.badge(row['confidence'] + ' confidence', 'warn' if row['confidence'] == 'Low' else 'neutral')
            ui.label(f"{row['batch_size']} planned crafts · profit {format_money(row['batch_profit_copper'])} · "
                     f"per craft {format_money(row['profit_per_craft_copper'])} · "
                     f"cost {format_money(row['batch_cost_copper'])}")
            session_signal(row['signal'])
            for material in row['purchases']:
                with ui.row().classes('items-center gap-2'):
                    item_link(config, material['item_id'], row['material_names'][material['item_id']])
                    ui.label(f"{material['purchased_units']} units · {material['method']} · "
                             f"{format_money(material['cost_copper'])}")
                session_signal(material['signal'])


def session_options(options, config):
    snapshot = options['snapshot']
    signal = options['signals']
    with ui.row().classes('items-center gap-3'):
        theme.chip(age_caption(options['freshness'], config['max_age_hours']))
        if options['freshness']['stale']:
            theme.badge('stale — inspect only', 'warn')
    if signal['note']:
        ui.label(signal['note'])
    for character in options['characters']:
        with ui.card().classes('bs-card').mark('session-character'):
            session_summary(character, options, config)
            with ui.expansion(f"Details for {character['character'][0]}").classes('w-full'):
                session_crafts(character, config)
                session_professions(character, config)
    if not options['characters']:
        ui.label('No scoped Today characters imported. Use Data → Import.')
    ui.label('Farming rates come later (STORY-065).')
    with ui.expansion('How these options were made'):
        ui.label(f"Reach window {options['window']} points (set on Team) · cost and unlocks side by side; "
                 'current profit is not a forecast. Listings, never sales. No sales credit in costs. Yellow '
                 'skill-up chances and Classic Era tier levels (Journeyman 10, Expert 20, Artisan 35) are '
                 'unconfirmed on Forever.')
        ui.label(f"Snapshot {snapshot['snapshot_id']} · scan {snapshot.get('scan_id', 'unavailable')} · "
                 f"source {config['source_id']} · market {config['market_id']} · rules {config.get('rules_version')}")
        if signal['scan']:
            ui.label(f"Labels: scan {signal['scan']['scan_id']} · snapshot {signal['scan']['snapshot_id']} · "
                     f"{signal['scan']['finished_at']} · {age_caption(signal['freshness'], config['max_age_hours'])}")


def session_professions(character, config):
    ui.label('Levelling professions').classes('text-lg font-bold')
    if not character['professions']:
        ui.label('No profession list reported. Open profession windows and import character evidence.')
    for group in character['professions']:
        ui.label(f"{group['profession']} · {group['rank'] if group['rank'] is not None else 'unknown'} / "
                 f"{group['max_rank'] if group['max_rank'] is not None else 'unknown'}").classes('font-bold')
        tier = group['tier']
        if tier is not None:
            ui.label(f"{tier['name']} (past {tier['cap']}) needs character level {tier['required_level']}").classes(
                'bs-note')
        if group['capped']:
            theme.badge('capped · train the next tier first', 'warn')
        elif not group['recipes']:
            ui.label(group['note'] or 'No next recipes in reach; rank or recipe evidence may be missing.')
        for milestone in group['milestones']:
            session_milestone(milestone, group, config)
    with ui.expansion('Recipe list coverage'):
        for catalog, count in character['unlisted'].items():
            ui.label(f"{catalog}: {count} not in a recipe list; open that profession's window")
