"""Read-only Market explorer composition. Prices and routes retain their existing paths."""
from datetime import UTC, datetime

import duckdb

from . import analysis, farming, flood_signals, item_history, removed_listings, sales, scan_changes
from .action_board import catalog_identity, compatible_catalogs, rank_catalogs
from .crafting import basis_prices, evaluate_recipe
from .freshness import assess
from .metrics import read_scan_metrics
from .recipe_graph import RecipeGraph, label_routes, made_by_label, route_catalog
from .recipe_import import GAME_PATHS
from .session_options import base_signal
from .skillups import build_skillups
from .storage import scope_predicate
from .today_characters import project_recipes, recipe_status, team_makeable
from .today_loading import _load_holdings, load_today, load_today_characters
from .today_settings import TodaySettings


def load_explorer(config, catalogs, now: datetime) -> dict:
    selected = compatible_catalogs(catalogs, config)
    characters, warning = load_today_characters(config)
    manifest, arguments = load_today(config, selected, TodaySettings(), characters, now)
    holdings, holdings_warning = _load_holdings(config, now)
    result = {'holdings': holdings or ({}, {}, [], []), 'holdings_warning': holdings_warning, 'config': config,
              'catalogs': selected,
              'incompatible': [c for c in catalogs if c not in selected], 'warning': warning, 'snapshot': None,
              'observations': {}, 'characters': characters, 'items': [], 'metrics': [],
              'vendors': {}, 'recipes': [], 'demand': [], 'freshness': None,
              'movement': {'note': 'No earlier scan', 'rows': [], 'comparison': None},
              'removals': {'pair': None, 'rows': [], 'note': 'Fewer than two eligible scans.'}}
    if manifest is None:
        result["market"] = market_page(result, {})
        return result
    snapshot = arguments['snapshot']
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb'), read_only=True) as db:
        items = analysis.browse(db, snapshot['snapshot_id'], config, limit=2_147_483_647).to_dicts()
        qualities = captured_qualities(db, config, snapshot['snapshot_id'])
        metrics = read_scan_metrics(db, config, snapshot['snapshot_id']) or []
        roles = flood_signals.catalog_roles(selected)
        floods = flood_signals.top_lists(flood_signals.signals(db, config, sorted(roles), now), roles)
        histories = item_history.histories(db, config, sorted(roles))
        movement = scan_movement(db, config, selected, now)
        removals = removed_listings.top_removals(db, config, sorted(
            {item for catalog in selected for item in catalog['items_by_id']}))
    items = [{**row, 'quality': qualities.get((row['item_id'], row['variant_id'], row['variant_state'])),
              **{k: row[k] if row[k] and row[k] > 0 else None
                        for k in ('min_buyout', 'market_value')}} for row in items]
    result.update(observations=arguments['observations'], snapshot=snapshot, items=items, metrics=metrics,
                  movement=movement, removals=removals, floods=floods,
                  vendors=arguments['vendor_prices'], freshness=assess(snapshot, now, config['max_age_hours']),
                  recipes=recipe_rows(selected, arguments, characters),
                  demand=skill_demand(selected))
    result["market"] = market_page(result, histories)
    return result


def recipe_rows(catalogs, arguments, characters) -> list[dict]:
    if not catalogs:
        return []
    catalogs = compatible_catalogs(catalogs, arguments['market'])
    makers = team_makeable(catalogs, characters)
    graph = RecipeGraph(catalogs, makers, arguments["market"]) if makers is not None else None
    keys = ('now', 'max_age_hours', 'auction_cut')
    board = rank_catalogs(catalogs, arguments['observations'], arguments['market'], arguments['snapshot'],
                          **{key: arguments[key] for key in keys}, recipe_graph=graph)
    ranked = {(row['catalog_id'], row['recipe_id']): row for row in board['rows']}
    projection = project_recipes(catalogs, characters, None)
    buy, sell = basis_prices(arguments['observations'], 'cautious')
    rows = []
    for catalog in catalogs:
        identity = catalog_identity(catalog)
        for recipe in catalog['recipes_by_id'].values():
            key = (identity, recipe['recipe_id'])
            valued = ranked.get(key)
            statuses = [{'character': ' · '.join(c), **recipe_status(recipe, state)}
                        for c, state in sorted(characters.items())]
            try:
                routed = route_catalog(catalog, recipe["recipe_id"], buy, graph)
            except ValueError as error:
                rows.append({"catalog": catalog, "recipe": recipe,
                             "value": {"profit_copper": None, "action": "unsupported recipe: " + str(error)},
                             "status": projection["statuses"].get(key, {}), "characters": statuses, "materials": []})
                continue
            if valued is None:
                valued = intermediate_value(routed, recipe, buy, sell, arguments['auction_cut'])
            rows.append({'catalog': routed, 'recipe': recipe, 'value': valued,
                         'status': projection['statuses'].get(key, {}), 'characters': statuses,
                         'materials': routed_materials(routed, valued, buy, sell)})
    return sorted(rows, key=lambda r: (r['value']['profit_copper'] is None,
                                      -(r['value']['profit_copper'] or 0),
                                      r['recipe']['recipe_id'], catalog_identity(r['catalog'])))


def intermediate_value(catalog, recipe, buy, sell, cut):
    try:
        result = label_routes(evaluate_recipe(catalog, recipe['recipe_id'], buy, cut, sell), catalog)
        # The board deliberately has no intermediate-profit rows. Do not invent one here.
        return {**result, 'profit_copper': None, 'action': 'Intermediate: no Action Board profit row'}
    except ValueError as error:
        return {'profit_copper': None, 'action': 'unsupported recipe: ' + str(error)}


def routed_materials(catalog, value, buy, sell, crafts=1, depth=0) -> list[dict]:
    rows = []
    for choice in value.get('choices', []):
        quantity = choice['quantity'] * crafts
        rows.append({**choice, 'quantity': quantity, 'depth': depth,
                     'total_cost_copper': choice['total_cost_copper'] * crafts
                     if choice['total_cost_copper'] is not None else None})
        if choice['method'] != 'craft':
            continue
        nested_id = catalog['recipe_for_output'][choice['item_id']]
        nested = label_routes(evaluate_recipe(catalog, nested_id, buy, sale_prices=sell), catalog)
        made = catalog['recipes_by_id'][nested_id]['output_quantity']
        rows.extend(routed_materials(catalog, nested, buy, sell, quantity // made, depth + 1))
    return rows


def search_items(result, query: str) -> list[dict]:
    query = query.strip().casefold()
    return [row for row in result['items'] if query in row['item_name'].casefold() or query in str(row['item_id'])]


def item_page(result, item_id: int) -> dict:
    catalogs = result['catalogs']
    entries = [c['items_by_id'][item_id] for c in catalogs if item_id in c['items_by_id']]
    observed = [r for r in result['items'] if r['item_id'] == item_id]
    metrics = [r for r in result['metrics'] if r['item_id'] == item_id]
    name = (observed[0]['item_name'] if observed else entries[0]['name'] if entries else f'Item {item_id}')
    return {'item_id': item_id, 'name': name, 'observed': observed, 'metrics': metrics,
            'in_chain': bool(entries), 'vendor_buy': sorted({e['vendor_price_copper'] for e in entries
                                                           if e.get('vendor_price_copper', 0) > 0}),
            'vendor_sell': result['vendors'].get(item_id),
            'made_from': [r for r in result['recipes'] if r['recipe']['output_item_id'] == item_id],
            'used_in': [r for r in result['recipes'] if any(i['item_id'] == item_id for i in r['recipe']['inputs'])],
            'demand': [r for r in result['demand'] if r['item_id'] == item_id]}


def scan_movement(db, config, catalogs, now) -> dict:
    empty: dict = {'rows': [], 'comparison': None}
    if config['provider'] != 'addon':
        return {**empty, 'note': 'TSM source: no scan comparison'}
    scans = scan_changes.eligible_scans(db, config)
    if len(scans) < 2:
        return {**empty, 'note': 'No earlier scan'}
    ids = sorted({item for catalog in catalogs for item in catalog['items_by_id']})
    comparison = scan_changes.compare_scans(db, config, scans[0]['scan_id'], scans[1]['scan_id'], ids)
    rows = [r for r in comparison['items'] if any(r['earlier'][k] != r['later'][k]
                                                  for k in ('min_buyout', 'units'))]
    rows.sort(key=lambda r: (-abs(r['change']['min_buyout'] or 0), -abs(r['change']['units'] or 0),
                             r['item_id'], r['variant_state'] or '', r['variant_id'] or ''))
    later = comparison['later']['finished_at'].astimezone(UTC)
    largest: dict[int, dict] = {}
    for row in rows:
        largest.setdefault(row['item_id'], row)
    return {'note': '', 'rows': list(largest.values())[:10], 'comparison': comparison,
            'freshness': assess({'updated_at': later.isoformat()}, now, config['max_age_hours'])}


def skill_demand(catalogs) -> list[dict]:
    mapping = build_skillups(catalogs, n=1)
    combined: dict[int, dict] = {}
    for row in mapping['direct'] + mapping['raw']:
        target = combined.setdefault(row['item_id'], {'item_id': row['item_id'], 'bands': set(),
                                                     'professions': set()})
        target['bands'].update(row['bands'])
        target['professions'].update(row['professions'])
    return [{**row, 'bands': sorted(row['bands'],
                                  key=lambda b: int(b.split('–')[0]) if b != 'skill unknown' else 100000),
             'professions': sorted(row['professions'])}
            for row in combined.values()]


def item_removals(config, item_id):
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb'), read_only=True) as db:
        return removed_listings.item_history(db, config, item_id)


def item_floods(config, item_id, now):
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb'), read_only=True) as db:
        return flood_signals.signals(db, config, [item_id], now)


def wowhead_item_url(game_version, item_id):
    path = GAME_PATHS.get(game_version)
    return f'https://www.wowhead.com/{path + "/" if path else ""}item={item_id}'


def best_use(rows):
    known = [r for r in rows if r['value']['profit_copper'] is not None]
    best = max(known, key=lambda r: r['value']['profit_copper']) if known else None
    return {'recipe': best, 'reason': '; '.join(dict.fromkeys(r['value']['action'] for r in rows))
            or 'No compatible catalog recipe'}


def item_farming(config, result, item_id, floods):
    _, sell = basis_prices(result['observations'], 'cautious')
    characters = []
    for identity, state in sorted(result['characters'].items()):
        history = farming.history(state.get('observations', []), config.get('farming_idle_minutes', 10),
                                  config.get('farming_cell_percent', 5))
        history = farming.valued(history, sell, floods['rows'], config['auction_cut'], result['vendors'])
        # Filter after valuing: denominators and ordering remain those of This session.
        history = history | {'rows': [r for r in history['rows'] if r['item_id'] == item_id],
                             'spots': [s for s in history['spots']
                                       if any(i['item_id'] == item_id for i in s['items'])]}
        if history['rows'] or history['spots']:
            history['spots'] = [farming_spot(s, history.get('npc_names', {})) for s in history['spots']]
            characters.append({'character': identity, 'farming': history})
    return characters


def item_summary(config, result, page, now):
    try:
        floods, floods_error = item_floods(config, page['item_id'], now), None
    except Exception as error:  # A flood read failure keeps holdings, best use and farming.
        floods, floods_error = {'rows': []}, str(error)
    signal = base_signal(floods['rows'], page['item_id'])
    observed = base_signal(page['observed'], page['item_id'])
    metrics = base_signal(page['metrics'], page['item_id']) or {}
    held, warning = _load_holdings(config, now)
    totals, _, captures, units = held or ({}, {}, [], [])
    try:
        own_sales, sales_error = sales.load(config), None
    except Exception as error:  # A sales read failure keeps the rest of the summary, like floods.
        own_sales, sales_error = {'items': [], 'unidentified': 0}, str(error)
    return {'your_sales': [r for r in own_sales['items'] if r['item_id'] == page['item_id']],
            'unidentified_sales': own_sales['unidentified'], 'sales_error': sales_error,
            'observed': observed, 'metrics': metrics, 'signal': signal, 'floods': floods,
            'floods_error': floods_error,
            'held': totals.get((page['item_id'], None, 'base'), 0) if captures else None,
            'captures': captures,
            'holdings': [r for r in units if r['key'] == (page['item_id'], None, 'base')],
            'holdings_warning': warning,
            # Uncaptured or partly readable locations can only add units: the count is a lower bound.
            'at_least': any(c['unknown'] or c['partial'] for c in captures),
            'used_in': best_use(page['used_in']), 'made_from': best_use(page['made_from']),
            'farming': item_farming(config, result, page['item_id'], floods),
            'wowhead_url': wowhead_item_url(config['game_version'], page['item_id'])}


def captured_qualities(db, config, snapshot_id):
    """Only unanimous captured listing quality for this snapshot and exact variant identity."""
    predicate, scope = scope_predicate(config)
    rows = db.execute(f"""SELECT item_id, variant_id, variant_state,
        CASE WHEN count(DISTINCT quality)=1 THEN min(quality) END
        FROM scan_listings WHERE {predicate} AND snapshot_id=?
        GROUP BY item_id, variant_id, variant_state""", [*scope, snapshot_id]).fetchall()
    return {(item, variant, state): value for item, variant, state, value in rows}


def identity(row):
    return row['item_id'], row.get('variant_id'), row.get('variant_state')


def grid_rows(result, histories):
    """Snapshot identities, catalog roles and stored history; missing evidence stays null."""
    roles = flood_signals.catalog_roles(result['catalogs'])
    signals = {identity(r): r for r in result.get('floods', {}).get('rows', [])}
    metrics = {identity(r): r for r in result['metrics']}
    rows = []
    for observed in result['items']:
        key = identity(observed)
        signal, metric = signals.get(key), metrics.get(key, {})
        typical = signal['overshoot']['typical_copper'] if signal else None
        price = observed['min_buyout']
        points = histories.get(observed['item_id'], {}).get('series', {}).get(key, [])
        spark = [p['min_buyout'] if p else None for p in points]
        role = roles.get(observed['item_id'], '')
        rows.append({'item_id': observed['item_id'], 'name': observed['item_name'],
                     'variant_id': key[1], 'variant_state': key[2], 'quality': observed.get('quality'),
                     'price_copper': price, 'typical_copper': typical,
                     'gap_copper': price - typical if price and typical else None,
                     'gap_percent': (price - typical) * 100 / typical if price and typical else None,
                     'roles': (['materials'] if 'material' in role else []) +
                              (['crafts'] if 'output' in role else []) +
                              (['intermediates'] if 'material' in role and 'output' in role else []),
                     'listings': metric.get('listings'), 'units': metric.get('units'),
                     'signal': signal, 'sparkline': spark})
    return rows


def market_page(result, histories):
    floods = result.get('floods', {})
    overshoots = floods.get('overshoots', [])
    return {'rows': grid_rows(result, histories),
            'pulse': {'cheap': [r for r in overshoots if r['overshoot']['label'] == 'cheap'],
                      'high': [r for r in overshoots if r['overshoot']['label'] == 'high'],
                      'early': result['removals']['rows']},
            'removals': result['removals'], 'movement': result['movement'],
            'floods': {k: floods.get(k) for k in ('settings', 'scan', 'freshness', 'note')},
            'chain_count': len(flood_signals.catalog_roles(result['catalogs'])),
            'warning': result['warning'], 'note': '' if result['snapshot'] else
            'No saved snapshot. Use Data to import complete priced scans.'}


def chain_recipe(row, item_id):
    """UI-09 facts formerly assembled only in the NiceGUI crafting panel."""
    recipe, value, catalog = row['recipe'], row['value'], row['catalog']
    output = recipe['output_item_id']
    return {'catalog_id': catalog_identity(catalog), 'recipe_id': recipe['recipe_id'],
            'item_id': output, 'name': catalog['items_by_id'][output]['name'],
            'output_quantity': recipe['output_quantity'], 'profession': catalog['profession'],
            'quantity': sum(i['quantity'] for i in recipe['inputs'] if i['item_id'] == item_id),
            'profit_copper': value['profit_copper'], 'reason': value['action'],
            'materials': [m | {'maker': made_by_label(m) if m.get('profession') else ''}
                          for m in row['materials']], 'characters': row['characters'],
            'status': row['status'], 'warnings': value.get('catalog_warnings', []),
            'vendor_capped': value.get('vendor_capped', False),
            'vendor_price_cap_copper': value.get('vendor_price_cap_copper'),
            'expanded': [{'item_id': i, 'name': catalog['items_by_id'][i]['name'], 'quantity': n}
                         for i, n in value.get('expanded_materials', {}).items()]}


def item_chain(result, item_id):
    page = item_page(result, item_id)
    return {'in_chain': page['in_chain'], 'demand': page['demand'],
            **{key: [chain_recipe(r, item_id) for r in page[key]] for key in ('made_from', 'used_in')}}


def item_activity(config, result, item_id, now):
    summary = item_summary(config, result, item_page(result, item_id), now)
    return {key: summary[key] for key in ('your_sales', 'unidentified_sales', 'sales_error', 'held',
            'at_least', 'captures', 'holdings', 'holdings_warning', 'farming', 'wowhead_url')}


def chosen_identity(page, summary, variant):
    """An explicitly selected snapshot identity never borrows base prices, supply or quality."""
    if variant is None:
        return summary['observed'] or {}, summary['signal'] or {}, summary['metrics']
    state, variant_id = variant
    def match(row):
        return row.get('variant_state') == state and row.get('variant_id') == variant_id
    return (next((r for r in page['observed'] if match(r)), {}),
            next((r for r in summary['floods']['rows'] if match(r)), {}),
            next((r for r in page['metrics'] if match(r)), {}))


def farming_spot(spot, names):
    """Display names and position formerly confined to the native item farming panel."""
    def mob(npc):
        return (f'{names[npc]} (NPC {npc})' if npc in names else f'NPC {npc}') if npc else 'Gathering · zone only'
    cell = spot.get('cell')
    half = spot['cell_percent'] // 2
    return spot | {'mob': mob(spot['npc_id']), 'also_looted_labels': [mob(n) for n in spot['also_looted']],
                   'position': f'around {cell[0] + half}, {cell[1] + half}' if cell else '—'}
