"""Market browsing and chain navigation over the shared explorer projection."""
from datetime import UTC, datetime
from urllib.parse import urlencode

from nicegui import ui

from brownstone import market_explorer as explorer
from brownstone.freshness import age_caption
from brownstone.money import format_money
from views import nicegui_theme as theme


def money(value):
    return format_money(value) if value is not None and value > 0 else 'unknown'


def change(value, metric):
    if value is None:
        return 'unknown'
    shown = format_money(value) if metric in ('min_buyout', 'market_value') else f'{value:,}'
    return ('+' if value > 0 else '') + shown


def item_url(config, item_id):
    return '/?' + urlencode({'place': 'Market', 'game': config['game_version'],
                             'source': config['source_id'], 'item': item_id})


def item_link(config, item_id, name):
    return ui.link(name, item_url(config, item_id)).classes(
        'min-h-[44px] inline-flex items-center underline').style('color:var(--brand)')


def render(config, catalogs, item: int | None = None):
    try:
        result = explorer.load_explorer(config, catalogs, datetime.now(UTC))
    except Exception as error:
        empty(f'Unable to read Market evidence: {error}. Use Data to check saved scans.')
        return
    theme.info_button('Market evidence', lambda: evidence(result))
    if result['snapshot'] is None:
        empty('No saved snapshot for this source and market. Use Data → Import, then return to Market.')
        return
    with ui.row().classes('gap-3 items-center'):
        theme.chip(age_caption(result['freshness'], config['max_age_hours']))
        if not result['freshness']['upstream_known']:
            theme.chip(f"Snapshot collected {result['freshness']['observed_at'].astimezone(UTC):%Y-%m-%d %H:%M} UTC")
        if result['freshness']['stale']:
            theme.badge('Stale', 'warn')
        theme.chip(f"{len({i for c in result['catalogs'] for i in c['items_by_id']})} items in our chains")
    if result['warning']:
        ui.label(result['warning']).classes('bs-note')
    if not result['catalogs']:
        empty('No compatible catalogs for this source’s game and rules version. '
              'Inspect Recipe catalogs in the old app.')
    search_panel(result)
    if item is not None:
        show_item(result, explorer.item_page(result, item))
    movement(result)


def empty(message):
    with ui.card().classes('bs-card bs-empty'):
        ui.label(message).classes('bs-sentence')


def search_panel(result):
    with ui.card().classes('bs-card'):
        ui.label('Find an item').classes('text-xl font-bold')
        search = ui.input('Item name or ID').classes('w-full').props('clearable').mark('market-search')
        ui.button('Search', on_click=lambda: update()).mark('market-search-button')
        area = ui.column().classes('w-full')
        def update():
            area.clear()
            query = search.value or ''
            rows = list({r['item_id']: r for r in reversed(explorer.search_items(result, query))}.values())
            rows.sort(key=lambda r: (r['item_name'], r['item_id']))
            with area:
                if not query.strip():
                    ui.label('Search by name or ID to open an item and walk its chain.')
                    return
                ui.label(f'{len(rows)} matches').classes('bs-note')
                if not rows:
                    ui.label('No matching items in this snapshot. Try another name or ID.')
                for row in rows[:30]:
                    item_link(result['config'], row['item_id'], row['item_name'])
                if len(rows) > 30:
                    ui.label('Showing the first 30. Refine your search to find any item.')
        search.on_value_change(lambda e: update())
        update()


def show_item(result, page):
    config = result['config']
    with ui.card().classes('bs-card').mark('market-item'):
        ui.label(page['name']).classes('text-2xl font-bold')
        prices(page)
        if not page['in_chain']:
            ui.label('This item is in no compatible catalog. Price evidence only.')
            return
        ui.label('Made from').classes('text-xl font-bold')
        for row in page['made_from']:
            recipe_heading(config, row)
            for material in row['materials']:
                with ui.row().classes('items-center gap-2').style(f"padding-left:{material['depth'] * 24}px"):
                    item_link(config, material['item_id'], material['item_name'])
                    ui.label(f"× {material['quantity']} · {material['method']} · "
                             f"{money(material['unit_cost_copper'])} / unit · "
                             f"{money(material['total_cost_copper'])} total")
            with ui.expansion('Expanded quantities (catalog recipe; independent of buy route)'):
                for item_id, units in row['value'].get('expanded_materials', {}).items():
                    item_link(config, item_id, row['catalog']['items_by_id'][item_id]['name'] + f' × {units}')
        if not page['made_from']:
            ui.label('No compatible recipe makes this item.')
        used_in(config, page)
        ui.label('Skill-up demand').classes('text-xl font-bold')
        for demand in page['demand']:
            ui.label(' · '.join(demand['professions']) + ': ' + ', '.join(demand['bands']))
        ui.label('Catalog skill-up bands, not observed demand or sales. No forecast.').classes('bs-note')
        if not page['demand']:
            ui.label('No skill-up bands in the compatible catalogs need this material.')


def prices(page):
    if not page['observed']:
        ui.label('Not listed in this snapshot; prices unknown.')
    metrics = {(r['variant_id'], r['variant_state']): r for r in page['metrics']}
    for row in page['observed']:
        identity = (row['variant_id'], row['variant_state'])
        if len(page['observed']) > 1 or row['variant_state'] not in (None, 'base'):
            theme.badge('Base item' if row['variant_state'] in (None, 'base') else row['variant_state'])
        with ui.expansion('Item identity'):
            ui.label(f"Item {page['item_id']} · variant {row['variant_id'] or 'none'} · "
                     f"state {row['variant_state'] or 'legacy'}")
        depth = metrics.get(identity, {})
        with ui.element('div').classes('bs-tiles'):
            theme.tile('Lowest buyout / unit', money(row['min_buyout']))
            theme.tile('Market value / unit', money(row['market_value']))
            theme.tile('Listings', str(depth.get('listings', 'unknown')))
            theme.tile('Units listed', str(depth.get('units', 'unknown')))
    with ui.row().classes('gap-3'):
        theme.chip('Vendor buy / unit: ' + (' / '.join(money(v) for v in page['vendor_buy']) or 'unknown'))
        theme.chip('Vendor sell / unit: ' + money(page['vendor_sell']))
    ui.label('Listings are supply, not sales. Prices are current saved evidence.').classes('bs-note')


def recipe_heading(config, row):
    recipe, value = row['recipe'], row['value']
    with ui.row().classes('items-center gap-2'):
        item_link(config, recipe['output_item_id'], row['catalog']['items_by_id'][recipe['output_item_id']]['name'])
        ui.label(f"× {recipe['output_quantity']} · {row['catalog']['profession']}")
        profit = value['profit_copper']
        ui.label('Profit per craft: ' + (format_money(profit) if profit is not None else 'unknown'))
        theme.badge(value['action'], 'warn' if profit is None else 'neutral')


def used_in(config, page):
    ui.label('Used in').classes('text-xl font-bold')
    for row in page['used_in']:
        recipe_heading(config, row)
        quantity = sum(i['quantity'] for i in row['recipe']['inputs'] if i['item_id'] == page['item_id'])
        ui.label(f'{quantity} units per craft')
        if not row['characters']:
            theme.badge('Team: Unknown', 'warn')
        makers = row['status'].get('who_can_make_it', [])
        if makers:
            theme.badge('Can make: ' + ', '.join(makers), 'good')
        with ui.expansion('Team eligibility'):
            for character in row['characters']:
                theme.badge(character['character'] + ': ' + character['craft_status'],
                            'warn' if character['craft_status'] == 'Unknown' else 'neutral')
                if character['character_reason']:
                    ui.label(character['character_reason']).classes('bs-note')
    if not page['used_in']:
        ui.label('No compatible recipe consumes this item.')


def movement(result):
    moved = result['movement']
    with ui.card().classes('bs-card'):
        ui.label('What moved since the last scan').classes('text-xl font-bold')
        if moved['note']:
            ui.label(moved['note'])
            return
        comparison = moved['comparison']
        ui.label(f"{comparison['earlier']['finished_at']:%Y-%m-%d %H:%M:%S} UTC → "
                 f"{comparison['later']['finished_at']:%Y-%m-%d %H:%M:%S} UTC · gap {comparison['gap']}")
        earlier_age = moved['freshness']['age_hours'] + comparison['gap'].total_seconds() / 3600
        theme.chip(f'Earlier scan {earlier_age:.1f} hours old · historical')
        theme.chip(f"Later scan {moved['freshness']['age_hours']:.1f} hours old")
        if moved['freshness']['stale']:
            theme.badge('Stale', 'warn')
        for row in moved['rows']:
            with ui.row().classes('items-center gap-2'):
                item_link(result['config'], row['item_id'], row['item_name'])
                ui.label(f"Lowest buyout change: {change(row['change']['min_buyout'], 'min_buyout')} · "
                         f"units change: {change(row['change']['units'], 'units')}")
                theme.badge(row['variant_state'] or 'legacy')
            comparison_detail(row)
        if not moved['rows']:
            ui.label('No lowest-buyout or units changes in our catalog chains.')
        with ui.expansion('New and vanished listings'):
            for group in ('new', 'vanished'):
                ui.label(group.capitalize())
                for row in comparison[group]:
                    item_link(result['config'], row['item_id'], row['item_name'])
                    comparison_detail(row)


def evidence(result):
    with theme.dialog('Market evidence') as popup:
        config, snapshot = result['config'], result['snapshot']
        ui.label(f"Source {config['source_id']} · market {config['market_id']}")
        ui.label(f"Rules {config.get('rules_version', 'unknown')}")
        if snapshot:
            ui.label(f"Snapshot {snapshot['snapshot_id']} · {result['freshness']['observed_at'].astimezone(UTC)}")
        for catalog in result['catalogs']:
            ui.label(f"{catalog['catalog_id']} · rules {catalog['rules_version']}")
        with ui.expansion('Incompatible catalogs (inspect in old app → Recipe catalogs)'):
            for catalog in result['incompatible']:
                ui.label(f"{catalog['catalog_id']}: {catalog['game_version']} / {catalog['rules_version']} "
                         f"does not match {config['game_version']} / "
                         f"{config.get('rules_version', 'unknown')}; unpriced")
        ui.label('Cautious Action Board profit per craft. Routes stay within each catalog. '
                 'Movement sorts by absolute copper change, then absolute units change, and shows at most 10.')
    popup.on('hide', popup.delete)
    popup.open()


def comparison_detail(row):
    with ui.expansion('Listing evidence for ' + row['item_name']):
        ui.label(f"Item {row['item_id']} · variant {row['variant_id'] or 'none'} · "
                 f"state {row['variant_state'] or 'legacy'}")
        for side in ('earlier', 'later'):
            values = row[side]
            if values is None:
                ui.label(side.capitalize() + ': not listed')
                continue
            buyout = money(values['min_buyout']) if values['min_buyout'] else 'no buyout'
            market = money(values['market_value']) if values['market_value'] else 'no market value'
            ui.label(f"{side.capitalize()}: lowest buyout {buyout} · market value {market} · "
                     f"{values['listings']} listings · {values['units']} units")
        ui.label('Later minus earlier: ' + ' · '.join(
            f"{key.replace('_', ' ')}: {change(value, key)}" for key, value in row['change'].items()))
