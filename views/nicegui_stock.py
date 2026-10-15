"""Stock place: one evidence load, cached filtering and Save-only local targets."""
from datetime import UTC, datetime

from nicegui import ui

from brownstone import ledger, stock
from brownstone.freshness import age_caption
from brownstone.money import format_money
from views import nicegui_theme as theme


def money(value):
    return format_money(value) if value is not None else 'no price'


def capture_text(capture):
    label = f"{capture['character']} · {capture['kind']}"
    age = capture['age_hours']
    text = f'{label} · {age:.1f}h old' if age is not None else f'{label} unknown'
    if capture['units'] == 0:
        text += ' · empty'
    if capture.get('partial'):
        text += ' · partly readable'
    if capture['excluded']:
        text += f" · {capture['excluded']} unreadable capture(s) excluded"
    return text


def render(config, catalogs):
    try:
        result = stock.load_stock(config, catalogs, datetime.now(UTC))
    except Exception as error:
        with ui.card().classes('bs-card bs-empty'):
            ui.label(f'Unable to read Stock evidence: {error}. Check saved evidence in Data '
                     'and the local targets file, then reload.').classes('bs-sentence')
        return
    theme.info_button('Stock evidence', lambda: evidence(result))
    with ui.row().classes('gap-3 items-center'):
        theme.chip(f"{len(result['captures']) // 2} characters")
        for capture in result['captures']:
            theme.chip(capture_text(capture))
        if result['freshness']:
            theme.chip(age_caption(result['freshness'], config['max_age_hours']))
            if result['freshness']['stale']:
                theme.badge('Stale', 'warn')
        else:
            theme.badge('No complete scan · import in Data', 'warn')
    with ui.element('div').classes('bs-tiles'):
        theme.tile('Items held', str(result['items_held']))
        theme.tile('Value at listed prices', money(result['value_copper']),
                   note=f"Excludes {result['excluded_prices']} held items with no price")
        theme.tile('Items short', str(result['items_short']))
        theme.tile('Cost to fill within limits', money(result['buy_cost_copper']))
    ui.label('At listed prices, not what it would sell for. Holdings cover readable captures only.').classes('bs-note')
    ui.button('Set stock targets', on_click=lambda: targets_dialog(result)).mark('stock-targets')
    if not result['captures']:
        with ui.card().classes('bs-card bs-empty'):
            ui.label('No character captures for this source and market. Import bags and bank snapshots in Data.')
    stock_table(result)
    with ui.expansion('Holdings by character and location'):
        names = {r['key']: r['name'] for r in result['rows']}
        plain_table([{'Item': names[h['key']],
                      'Character': h['character'], 'Location': h['kind'], 'Units': h['units']}
                     for h in result['holdings']], 'stock-holdings')
        ui.label('Each location has its own capture time; open an unknown bank and import to complete holdings.')
    # Gold is additive (UI-15): a ledger failure must not hide the holdings answer above it.
    try:
        gold = ledger.load(config)
    except Exception as error:
        with ui.card().classes('bs-card bs-empty'):
            ui.label(f'Unable to read gold evidence: {error}. Check saved journal evidence in Data, '
                     'then reload.').classes('bs-sentence')
        return
    gold_section(gold)


def table_row(row):
    short = row.get('short')
    return {'Item': row['name'], 'Held': row['held'],
            'Target': row['entry'].target_units if row['entry'] else '—',
            'Short': ('at most ' if row['at_most'] else '') + str(short) if short is not None else '—',
            'Buy now': row.get('buy_units', '—'), 'Wait': row.get('wait_units', '—'),
            'Unlisted units': row.get('unlisted_units', '—'),
            'Buy cost': money(row['buy_cost_copper']) if row['entry'] else '—',
            'Fill cost': ('insufficient listings' if row['unlisted_units'] else money(row.get('fill_cost_copper')))
            if row['entry'] else '—',
            'Value': money(row['value_copper']), 'item_id': row['item_id']}


def plain_table(rows, marker, *, row_key='id'):
    keys = [k for k in rows[0] if k not in ('id', 'item_id')] if rows else []
    rows = [{'id': i, **row} for i, row in enumerate(rows)]
    return ui.table(columns=[{'name': k, 'label': k, 'field': k, 'align': 'left'} for k in keys],
                    rows=rows, row_key=row_key, pagination=15).classes('w-full').props('flat bordered').mark(marker)


def stock_table(result):
    with ui.card().classes('bs-card w-full'):
        ui.label('What needs restocking').classes('text-xl font-bold')
        with ui.row().classes('items-center gap-3'):
            search = ui.input('Name or item ID').props('clearable').mark('stock-search')
            chains = ui.switch('Our catalog chains only').mark('stock-chains')
        rows = [table_row(r) for r in result['rows']]
        widget = plain_table(rows, 'stock-table')
        def update():
            widget.rows = [table_row(r) for r in stock.filter_rows(result, search.value or '', chains.value)]
        search.on_value_change(lambda e: update())
        chains.on_value_change(lambda e: update())
        ui.label('Short items first. Unlisted units have no fill price. Costs buy whole stacks; surplus is included.')
        with ui.expansion('Target and purchase evidence'):
            for row in result['rows']:
                target_evidence(row)


def limit_text(entry):
    if entry.buy_percent is not None:
        return f'{entry.buy_percent}% of this scan’s market value'
    if entry.buy_copper is not None:
        return money(entry.buy_copper) + ' / unit'
    return 'No buy limit'


def target_evidence(row):
    if not row['entry']:
        return
    entry = row['entry']
    ui.label(f"{row['name']} · item {row['item_id']} · {limit_text(entry)}")
    if row['limit_unknown']:
        theme.badge('Market value missing · buy limit unknown · wait', 'warn')
    elif row['limit_copper'] is not None:
        ui.label('Effective limit: ' + money(row['limit_copper']) + ' / unit')
    ui.label(f"Whole-stack buy: {row['purchased_units']} units · above-limit cost: "
             + money(row['wait_cost_copper']))


def targets_dialog(result):
    # Fresh drafts each opening. No file reads until Save validates the current saved file.
    draft = {entry.item_id: entry for entry in result['entries']}
    with theme.dialog('Stock targets') as popup:
        ui.label('Team totals. Enter an item ID; names are never guessed. Save applies all draft changes.')
        item = ui.input('Item ID').classes('w-full').mark('stock-item-id')
        units = ui.input('Target units').classes('w-full').mark('stock-units')
        mode = ui.select(['No limit', 'Fixed copper', 'Market value percent'],
                         value='No limit', label='Buy limit').classes('w-full')
        limit = ui.input('Limit (integer copper or percent)').classes('w-full').mark('stock-limit')
        message = ui.label('').classes('bs-note')
        area = ui.column().classes('w-full')
        def show():
            area.clear()
            with area:
                for entry in draft.values():
                    name = result['names'].get(entry.item_id)
                    label = f'{name} ({entry.item_id})' if name else f'Item {entry.item_id}'
                    ui.label(f'{label}: {entry.target_units} units · {limit_text(entry)}')
        def apply():
            try:
                entry = stock.Entry(int(item.value), int(units.value),
                                    int(limit.value) if mode.value == 'Fixed copper' else None,
                                    int(limit.value) if mode.value == 'Market value percent' else None)
                draft[entry.item_id] = entry
                message.text = 'Draft updated; Save to keep it.'
                show()
            except (ValueError, TypeError) as error:
                message.text = f'Draft rejected: {error}'
        def remove():
            try:
                draft.pop(int(item.value), None)
                show()
            except (ValueError, TypeError):
                message.text = 'Enter an item ID to remove its target.'
        def save():
            try:
                stock.save_entries(stock.targets_path(result['config']['data_dir'], result['config']['source_id']),
                                   list(draft.values()))
            except (ValueError, TypeError, OSError) as error:
                message.text = f'Save rejected: {error}. Last saved targets kept.'
                return
            popup.close()
            ui.navigate.reload()
        ui.button('Update draft', on_click=apply).props('flat').mark('stock-draft')
        ui.button('Remove target from draft', on_click=remove).props('flat')
        ui.button('Save targets', on_click=save).mark('stock-save')
        show()
    popup.on('hide', popup.delete)
    popup.open()


def evidence(result):
    with theme.dialog('Stock evidence') as popup:
        config = result['config']
        ui.label(f"Source {config['source_id']} · market {config['market_id']}")
        if result['snapshot']:
            ui.label(f"Snapshot {result['snapshot']['snapshot_id']}")
        ui.label('Cautious value: lower positive minimum buyout / market value (CRAFT-04); '
                 'one positive value uses that value. Missing or zero prices are excluded. '
                 'Percentage limits use ADDON-03 market value; rounded down to integer copper. '
                 'Fill walks cheapest listings first using Today’s whole-stack ladder. '
                 'Unknown locations make shortfalls at most; no Today plan changes.')
        for capture in result['captures']:
            ui.label(capture_text(capture))
            ui.label(f"Snapshot {capture['snapshot_id']} · capture {capture['captured_at']} · "
                     f"units {capture['units']} · machine {capture['machine'] or 'unknown'}")
    popup.on('hide', popup.delete)
    popup.open()


def gold_time(at):
    return datetime.fromtimestamp(at, UTC).strftime('%Y-%m-%d %H:%M:%S')


def gold_table(rows, marker):
    """Keep integer copper as table data; format for display and sort numerically."""
    widget = plain_table(rows, marker)
    for column in widget.columns:
        if column['name'].endswith('copper'):
            column.update(sortable=True, label=column['name'].replace('_copper', ' (gold)'))
            field = column['name']
            widget.add_slot('body-cell-' + field,
                            '<q-td :props="props">{{ props.row["' + field + '_text"] }}</q-td>')
    for row in widget.rows:
        for key, value in list(row.items()):
            if key.endswith('copper'):
                row[key + '_text'] = money(value) if value is not None else 'unknown'
    widget.update()


def gold_section(data):
    with ui.card().classes('bs-card w-full'):
        ui.label('Gold').classes('text-xl font-bold')
        ui.label('Where did our gold come from and go?').classes('bs-note')
        theme.chip(f"{len(data['movements'])} recorded changes")
        if data['excluded_money'] or data['unreadable_snapshots']:
            theme.badge('Incomplete evidence', 'warn')
        with ui.element('div').classes('bs-tiles'):
            theme.tile('Team gold in', money(data['team']['in_copper']))
            theme.tile('Team gold out', money(data['team']['out_copper']))
        ui.label('UTC days. Quests and flights have no event and remain other. '
                 'Team totals explicitly sum these characters; mail between them is included.').classes('bs-note')
        if not data['movements']:
            ui.label('No gold movements for this source and market. Import journal evidence in Data.')
        gold_table([{'Character': ' · '.join(r['character']), 'UTC day': r['day'],
                     'Category': r['category'], 'In_copper': r['in_copper'], 'Out_copper': r['out_copper']}
                    for r in data['totals']], 'gold-totals')
        ui.label('Reconciliation · unexplained is an evidence gap').classes('font-bold')
        if not data['reconciliation']:
            ui.label('Two readable bags captures per character are needed. Import bags snapshots in Data.')
        gold_table([{'Character': ' · '.join(r['character']), 'From UTC': gold_time(r['from']),
                     'To UTC': gold_time(r['to']), 'Actual_copper': r['actual_copper'],
                     'Recorded_copper': r['recorded_copper'], 'Unexplained_copper': r['unexplained_copper'],
                     'Reason': r['reason'] or ''} for r in data['reconciliation']], 'gold-reconciliation')
        with ui.expansion('Gold movements and evidence'):
            ui.label(f"Ledger version {data['ledger_version']} · UI-15 · economy match within "
                     f"{ledger.MATCH_SECONDS}s; coin loot within 5s. "
                     f"Excluded money baselines: {data['excluded_money']}; "
                     f"unreadable bags excluded: {data['unreadable_snapshots']}.")
            gold_table([{'UTC': gold_time(m['at']), 'Character': ' · '.join(m['character']),
                         'Machine': m['machine'] or 'unknown', 'Change_copper': m['copper'],
                         'Allocation': ', '.join(p['category'] + ': ' + money(p['copper']) for p in m['parts']),
                         'Reason': m['reason'] or '', 'Entry ID': m['entry_id']}
                         for m in data['movements']], 'gold-movements')
            plain_table([{'Before snapshot': r['before_id'], 'After snapshot': r['after_id']}
                         for r in data['reconciliation']], 'gold-snapshots')
