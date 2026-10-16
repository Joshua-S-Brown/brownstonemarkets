"""Read-only Market explorer composition. Prices and routes retain their existing paths."""
from datetime import UTC, datetime

import duckdb

from . import analysis, farming, flood_signals, removed_listings, sales, scan_changes
from .action_board import catalog_identity, compatible_catalogs, rank_catalogs
from .crafting import basis_prices, evaluate_recipe
from .freshness import assess
from .metrics import read_scan_metrics
from .recipe_graph import RecipeGraph, label_routes, route_catalog
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
    result = {'config': config, 'catalogs': selected,
              'incompatible': [c for c in catalogs if c not in selected], 'warning': warning, 'snapshot': None,
              'observations': {}, 'characters': characters, 'items': [], 'metrics': [],
              'vendors': {}, 'recipes': [], 'demand': [], 'freshness': None,
              'movement': {'note': 'No earlier scan', 'rows': [], 'comparison': None},
              'removals': {'pair': None, 'rows': [], 'note': 'Fewer than two eligible scans.'}}
    if manifest is None:
        return result
    snapshot = arguments['snapshot']
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb'), read_only=True) as db:
        items = analysis.browse(db, snapshot['snapshot_id'], config, limit=2_147_483_647).to_dicts()
        qualities = captured_qualities(db, config, snapshot['snapshot_id'])
        metrics = read_scan_metrics(db, config, snapshot['snapshot_id']) or []
        roles = flood_signals.catalog_roles(selected)
        floods = flood_signals.top_lists(flood_signals.signals(db, config, sorted(roles), now), roles)
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
