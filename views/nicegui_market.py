"""Market browsing and chain navigation over the shared explorer projection."""
from datetime import UTC, datetime
from urllib.parse import urlencode

from nicegui import ui

from brownstone import market_explorer as explorer
from brownstone.freshness import age_caption
from brownstone.money import format_money
from brownstone.recipe_graph import made_by_label
from views import nicegui_theme as theme
from views.nicegui_navigation import set_href
from views.nicegui_stock import capture_text
from views.today_rows import vendor_cap_label


def money(value):
    return format_money(value) if value is not None and value > 0 else 'unknown'


def change(value, metric):
    if value is None:
        return 'unknown'
    shown = format_money(value) if metric in ('min_buyout', 'market_value') else f'{value:,}'
    return ('+' if value > 0 else '') + shown


def item_url(config, item_id, origin=None):
    return '/?' + urlencode({'place': 'Market', 'game': config['game_version'],
                             'source': config['source_id'], 'item': item_id,
                             **(origin if origin is not None else config.get('_origin', {}))})


def item_link(config, item_id, name, origin=None):
    link = ui.link(name, item_url(config, item_id, origin)).classes(
        'min-h-[44px] inline-flex items-center underline').style('color:var(--brand)')

    if '_location_updates' in config:
        config['_location_updates'].append(lambda: set_href(link, item_url(config, item_id, origin)))
    return link


def render(config, catalogs, item: int | None = None, origin=None):
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
    page = explorer.item_page(result, item) if item is not None else None
    config = {**config, '_origin': origin or ({'origin_place': 'Market', 'origin_item': str(item),
                                            'origin_name': page['name']} if page else {})}
    result = {**result, 'config': config}
    search_panel(result)
    if page is not None:
        show_item(result, page)
    else:
        flood_lists(result)
        removal_list(result)
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
    with ui.column().classes('w-full').mark('market-item'):
        ui.label(page['name']).classes('text-2xl font-bold')
        try:
            summary = explorer.item_summary(config, result, page, datetime.now(UTC))
        except Exception as error:
            ui.label(f'Unable to read item summary: {error}. Use Data to check saved scans.')
            summary = None
        if summary:
            summary_card(result, page, summary)
        with ui.tabs().classes('w-full') as tabs:
            for name in ('Summary', 'Crafting', 'Market', 'Identity and evidence'):
                ui.tab(name)
        with ui.tab_panels(tabs, value='Summary').classes('w-full'):
            with ui.tab_panel('Summary'):
                own_sales(summary)
                where_to_get(config, summary or {
                    'farming': None,
                    'wowhead_url': explorer.wowhead_item_url(config['game_version'], page['item_id'])})
            with ui.tab_panel('Crafting'):
                crafting(config, page)
            with ui.tab_panel('Market'):
                prices(page)
                if summary and summary['floods_error']:
                    ui.label(f"Unable to read flood signals: {summary['floods_error']}. "
                             'Use Data to check saved scans.')
                elif summary:
                    item_floods(summary['floods'], page)
                try:
                    history = explorer.item_removals(config, page['item_id'])
                except Exception as error:
                    ui.label(f'Unable to read removed listings: {error}. Use Data to check saved scans.')
                else:
                    removal_history(history)
            with ui.tab_panel('Identity and evidence'):
                ui.label(f"Item {page['item_id']}")
                for row in page['observed']:
                    ui.label(f"Variant {row['variant_id'] or 'none'} · state {row['variant_state'] or 'legacy'}")
                ui.button('Provenance and catalogs', on_click=lambda: evidence(result))


def crafting(config, page):
    if not page['in_chain']:
        ui.label('This item is in no compatible catalog. Price evidence only.')
        return
    ui.label('Made from').classes('text-xl font-bold')
    for row in page['made_from']:
        recipe_heading(config, row)
        catalog_warnings(row['value'])
        for material in row['materials']:
            with ui.row().classes('items-center gap-2').style(f"padding-left:{material['depth'] * 24}px"):
                item_link(config, material['item_id'], material['item_name'])
                ui.label(f"× {material['quantity']} · {material['method']} · "
                         f"{money(material['unit_cost_copper'])} / unit · "
                         f"{money(material['total_cost_copper'])} total"
                         + (f" · {made_by_label(material)}" if material.get('profession') else '')
                         + (f" · {material['route_note']}" if material.get('route_note') else ''))
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
        ui.label(vendor_cap_label(value))
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
        ui.label('Cautious Action Board profit per craft. '
                 'Routes include team-makeable materials across compatible catalogs. '
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


REMOVAL_LABELS = {'early': 'Removed early', 'expiry': 'Could have expired', 'unknown': 'Time left unknown'}


def removal_pair_heading(pair):
    ui.label(f"{pair['earlier']['finished_at']:%Y-%m-%d %H:%M:%S} UTC → "
             f"{pair['later']['finished_at']:%Y-%m-%d %H:%M:%S} UTC · gap {pair['gap']}")


def removal_counts(row):
    theme.badge(row['variant_state'] + (f" · {row['variant_id']}" if row['variant_id'] else ''))
    for key, label in REMOVAL_LABELS.items():
        value = row[key]
        ui.label(f"{label}: {value['listings']:,} listings · {value['units']:,} units")
    ui.label(f"Listings without a buyout (excluded): earlier {row['without_buyout']['earlier']:,} · "
             f"later {row['without_buyout']['later']:,}")
    with ui.expansion('Matching evidence'):
        ui.label(f"Item {row['item_id']} · variant {row['variant_id'] or 'none'} · state {row['variant_state']}")
        for group in row['evidence']:
            ui.label(f"Stack {group['quantity']} · whole-stack buyout {format_money(group['buyout'])} · "
                     f"earlier {group['earlier']} → later {group['later']} · removed {group['removed']}")
            for bucket in group['chosen_buckets']:
                ui.label(f"Time-left bucket {bucket['time_left'] or 'unknown'}: {bucket['listings']} listings · "
                         f"{REMOVAL_LABELS[bucket['category']]}")


def removal_history(history):
    with ui.column().classes('w-full').mark('item-removals'):
        ui.label('Removed between scans').classes('text-xl font-bold')
        ui.label('Removed early is an upper bound on sales: bought or cancelled. '
                 'Time-left bounds use Classic Era evidence; Forever beta check pending.').classes('bs-note')
        if history['note']:
            ui.label(history['note'])
        pairs = [p for p in history['pairs'] if not p['skipped']]
        skipped = len(history['pairs']) - len(pairs)
        ui.label(f"{skipped} skipped gap{'' if skipped == 1 else 's'} (over 12 hours)")
        removal_pairs(pairs[:3])
        if len(pairs) > 3:
            with ui.expansion('Show all scan gaps'):
                removal_pairs(pairs[3:])


def removal_pairs(pairs):
    for pair in pairs:
        removal_pair_heading(pair)
        for row in pair['items']:
            removal_counts(row)
        if not pair['items']:
            ui.label('No listings for this item in either scan; no removals.')


def removal_list(result):
    removed = result['removals']
    with ui.card().classes('bs-card').mark('market-removals'):
        ui.label('Removed early in our chains').classes('text-xl font-bold')
        ui.label('Upper bound on sales; cancellations and reprices can look the same. '
                 'Largest identity per item; variants never pooled.').classes('bs-note')
        if removed['note']:
            ui.label(removed['note'])
            return
        removal_pair_heading(removed['pair'])
        for row in removed['rows']:
            item_link(result['config'], row['item_id'], row['item_name'])
            removal_counts(row)
        if not removed['rows']:
            ui.label('No units removed early in our catalog chains.')


def flood_heading(floods):
    options = floods['settings']
    ui.label(f"Typical: earlier {options['flood_window_days']} days · "
             f"at least {options['flood_min_days']} distinct UTC days · "
             f"cheap ≤ {options['flood_cheap_percent']}% · high ≥ {options['flood_high_percent']}%.").classes('bs-note')
    ui.label(f"Contested: ≥ {options['flood_contested_listings']} listings and lowest buyout changes in "
             f"≥ {options['flood_churn_percent']}% of up to 10 comparable consecutive pairs (gap ≤ 12 hours). "
             f"Thin: ≤ {options['flood_thin_listings']} listings. Without pairs: listings only, churn unknown."
             ).classes(
                 'bs-note')
    ui.label('Listed supply, not sales or a forecast. Variants never pooled; sellers unknown.').classes('bs-note')
    if floods['note']:
        ui.label(floods['note'])
    if floods['scan']:
        theme.chip(f"Scan {floods['scan']['finished_at']:%Y-%m-%d %H:%M:%S} UTC")
        theme.chip(f"{floods['freshness']['age_hours']:.1f} hours old")
        if floods['freshness']['stale']:
            theme.badge('Stale', 'warn')


def flood_row(row):
    churn, overshoot = row['churn'], row['overshoot']
    theme.badge(row['crowding'], 'warn' if row['crowding'] == 'contested' else 'neutral')
    theme.badge((row['variant_state'] or 'legacy') + (f" · {row['variant_id']}" if row['variant_id'] else ''))
    ui.label(f"{row['listings']:,} listings · {row['units']:,} units listed · largest stack "
             f"{row['largest_stack_units']:,}/{row['units']:,} units "
             f"({100 * row['largest_stack_units'] / row['units']:.1f}%)")
    ui.label(f"Lowest buyout changed: {churn['changed']}/{churn['pairs']} comparable pairs" if churn['pairs']
             else 'Lowest buyout churn unknown: no comparable pairs')
    theme.badge(overshoot['label'], 'warn' if overshoot['label'] in ('cheap', 'high') else 'neutral')
    ratio = overshoot['ratio']
    ui.label(f"Lowest buyout / unit: {money(row['min_buyout'])} · typical: {money(overshoot['typical_copper'])} · "
             f"{overshoot['days']} days, {overshoot['scans']} scans" +
             (f" · {100 * ratio['numerator'] / ratio['denominator']:.1f}% of typical" if ratio else ''))


def flood_lists(result):
    floods = result['floods']
    with ui.card().classes('bs-card').mark('market-floods'):
        ui.label('Flood signals in our chains').classes('text-xl font-bold')
        flood_heading(floods)
        for key, title in (('contested', 'Most contested'), ('overshoots', 'Biggest overshoots · cheap and high')):
            ui.label(title).classes('text-lg font-bold')
            for row in floods[key]:
                flood_list_row(result['config'], row, key)
            if not floods[key]:
                ui.label('No contested chain items.' if key == 'contested' else
                         'No qualifying overshoots; item pages show thin, short or missing history.')
            if key == 'overshoots':
                ui.label(f"Thin items (≤ {floods['settings']['flood_thin_listings']} listings) are left out here; "
                         'their item pages still flag them.').classes('bs-note')


def item_floods(floods, page):
    with ui.column().classes('w-full').mark('item-floods'):
        ui.label('Crowding and overshoots').classes('text-xl font-bold')
        flood_heading(floods)
        roles = [label for key, label in (('used_in', 'material'), ('made_from', 'output')) if page[key]]
        ui.label(' / '.join(roles) or 'Outside catalog chains').classes('bs-note')
        for row in floods['rows']:
            flood_row(row)
        if not floods['rows'] and not floods['note']:
            ui.label('Not listed in the newest eligible scan; no flood signal.')


def flood_list_row(config, row, group):
    with ui.row().classes('items-center gap-2'):
        item_link(config, row['item_id'], row['item_name'])
        theme.badge((row['variant_state'] or 'legacy') + (f" · {row['variant_id']}" if row['variant_id'] else ''))
        ui.label(row['role']).classes('bs-note')
        if group == 'contested':
            theme.badge('contested', 'warn')
            churn = row['churn']
            ui.label(f"{row['listings']:,} listings · changes {churn['changed']}/{churn['pairs']} pairs"
                     if churn['pairs'] else f"{row['listings']:,} listings · churn unknown")
        else:
            overshoot = row['overshoot']
            theme.badge(overshoot['label'], 'warn')
            ratio = overshoot['ratio']
            ui.label(f"{100 * ratio['numerator'] / ratio['denominator']:.1f}% of typical · "
                     f"{overshoot['days']} days, {overshoot['scans']} scans")
    with ui.expansion('Flood evidence for ' + row['item_name']):
        flood_row(row)


def catalog_warnings(value):
    for warning in value.get("catalog_warnings", []):
        ui.label(warning).classes("bs-note")


def summary_card(result, page, summary):
    with ui.card().classes('bs-card').mark('item-summary'):
        observed, signal = summary['observed'], summary['signal']
        if observed is None:
            ui.label('Not listed in this snapshot')
        typical = signal['overshoot']['typical_copper'] if signal else None
        with ui.element('div').classes('bs-tiles'):
            theme.tile('Price now / unit', money(observed['min_buyout']) if observed else 'unknown')
            theme.tile('Typical / unit', money(typical) if typical else 'typical unknown')
            theme.tile('Units listed', str(summary['metrics'].get('units', 'unknown')))
            theme.tile('Listings', str(summary['metrics'].get('listings', 'unknown')))
            theme.tile('Vendor buy / unit', ' / '.join(money(v) for v in page['vendor_buy']) or 'unknown')
            theme.tile('Vendor sell / unit', money(page['vendor_sell']))
            theme.tile('Held by the team', 'unknown' if summary['held'] is None
                       else ('at least ' if summary['at_least'] else '') + str(summary['held']))
        if signal:
            theme.badge(signal['crowding'])
            theme.badge(signal['overshoot']['label'])
        ui.label('Best use in our catalogs').classes('text-lg font-bold')
        for key, label in (('used_in', 'Used in'), ('made_from', 'Made from')):
            choice = summary[key]
            if choice['recipe']:
                ui.label(label + ' · Profit per craft: ' + format_money(choice['recipe']['value']['profit_copper']))
                ui.label(vendor_cap_label(choice['recipe']['value']))
                item_id = choice['recipe']['recipe']['output_item_id']
                item_link(result['config'], item_id, choice['recipe']['catalog']['items_by_id'][item_id]['name'])
            elif page[key] or key == 'used_in':
                ui.label(label + ' · no profitable use known · ' + choice['reason'])
        summary_evidence(result, summary)


def summary_evidence(result, summary):
    signal = summary['signal']
    with ui.expansion('Summary evidence'):
        if result['snapshot']:
            ui.label(f"Snapshot {result['snapshot']['snapshot_id']}")
            ui.label(age_caption(result['freshness'], result['config']['max_age_hours']))
        if summary['floods_error']:
            ui.label(f"Unable to read flood signals: {summary['floods_error']}")
        else:
            flood_heading(summary['floods'])
        if signal:
            flood_row(signal)
        if summary['holdings_warning']:
            ui.label(summary['holdings_warning'])
        if not summary['captures']:
            ui.label('No character captures for this source and market. Import bags and bank snapshots in Data.')
        for capture in summary['captures']:
            ui.label(capture_text(capture))
            if capture['unknown']:
                ui.label(capture['character'] + ' · ' + capture['kind'] + ' not captured')
            ui.label(f"Capture {capture['captured_at']} · snapshot {capture['snapshot_id']} · "
                     f"machine {capture['machine'] or 'unknown'}")
        for row in summary['holdings']:
            ui.label(f"{row['character']} · {row['realm']} · {row['kind']}: {row['units']}")


def where_to_get(config, summary):
    from views.nicegui_today import farming_caveat, session_farming

    ui.label('Where to get it').classes('text-xl font-bold')
    if summary['farming'] is None:
        ui.label('Farming evidence unavailable. Use Data to check saved character evidence.')
    elif not summary['farming']:
        ui.label('not gathered yet')
    for character in summary['farming'] or []:
        ui.label(' · '.join(character['character'])).classes('text-lg font-bold')
        session_farming(character['farming'], config, limit=None)
    if any(c['farming']['rows'] or c['farming'].get('spots') for c in summary['farming'] or []):
        farming_caveat()
    ui.link('Wowhead drop sources and places', summary['wowhead_url'], new_tab=True).classes(
        'min-h-[44px] inline-flex items-center underline')


def own_sales(summary):
    from views.today_rows import sales_text

    ui.label('Your sales').classes('text-lg font-semibold')
    if summary is None or summary.get('sales_error'):
        ui.label('Sales evidence unavailable' + (f": {summary['sales_error']}" if summary else ''))
        return
    for row in summary.get('your_sales', []):
        latest = (f"{datetime.fromtimestamp(row['newest_sale'], UTC):%Y-%m-%d %H:%M} UTC"
                  if row['newest_sale'] else 'none yet')
        ui.label(f"{' · '.join(row['character'])}: {sales_text(row)} · {row['posted']} posted · "
                 f"{row['expired']} expired · {row['cancelled']} cancelled · newest sale {latest}")
    if not summary.get('your_sales'):
        ui.label('none resolved yet')
    ui.label(f"Unidentified seller invoices in this source and market: {summary.get('unidentified_sales', 0)}")
