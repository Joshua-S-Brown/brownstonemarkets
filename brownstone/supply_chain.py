"""Pure Supply chains projections over one scoped Market explorer load."""
from .action_board import catalog_identity
from .crafting import basis_prices, evaluate_recipe, route_options, unit_route
from .recipe_graph import label_routes, made_by_label, route_catalog
from .session_options import base_signal
from .today_characters import recipe_status

HIT_LIMIT = 50


def output(row):
    recipe, catalog = row['recipe'], row['catalog']
    item = catalog['items_by_id'][recipe['output_item_id']]
    return {'catalog_id': catalog_identity(catalog), 'recipe_id': recipe['recipe_id'],
            'item_id': item['item_id'], 'name': item['name'], 'profession': recipe['profession'],
            'profit_copper': row['value']['profit_copper']}


def outputs(explorer, query=''):
    rows = explorer['recipes']
    q = query.strip().casefold()
    # No snapshot still permits catalog exploration, including unsupported recipes.
    if not rows:
        rows = [{'catalog': c, 'recipe': r, 'value': {'profit_copper': None}}
                for c in explorer['catalogs'] for r in c['recipes_by_id'].values()]
    # Search hits only for a query, capped: an empty query would otherwise send every recipe.
    def matches(row):
        item = row['recipe']['output_item_id']
        return q in row['catalog']['items_by_id'][item]['name'].casefold() or q in str(item)

    hits = [output(r) for r in rows if matches(r)] if q else []
    return {'ranked': [output(r) for r in rows if r['value']['profit_copper'] is not None][:10],
            'hits': hits[:HIT_LIMIT], 'hit_count': len(hits)}


def select(explorer, catalog_id, recipe_id):
    catalog = next((c for c in explorer['catalogs'] if catalog_identity(c) == catalog_id), None)
    if catalog is None or recipe_id not in catalog['recipes_by_id']:
        raise LookupError('Unknown compatible recipe')
    row = next((r for r in explorer['recipes'] if catalog_identity(r['catalog']) == catalog_id
                and r['recipe']['recipe_id'] == recipe_id), None)
    # recipe_rows already selected the team maker using route_catalog, independently of forcing.
    routed = route_catalog(row['catalog'] if row else catalog, recipe_id, {})
    return routed, catalog['recipes_by_id'][recipe_id]


def route(explorer, catalog_id, recipe_id, batch=1, maximum=5, forced=None):
    if type(batch) is not int or not 1 <= batch <= maximum:
        raise ValueError(f'Batch must be between 1 and {maximum}')
    catalog, recipe = select(explorer, catalog_id, recipe_id)
    base = {'catalog_id': catalog_id, 'recipe_id': recipe_id, 'name': catalog['items_by_id'][
        recipe['output_item_id']]['name'], 'batch': batch, 'max_crafts': maximum}
    buy, sell = basis_prices(explorer['observations'], 'cautious')
    try:
        value = label_routes(evaluate_recipe(catalog, recipe_id, buy, explorer['config']['auction_cut'],
                                             sell, forced), catalog)
        nodes, edges = build_graph(explorer, catalog, recipe, buy, forced)
        cost = value['craft_cost_copper']
        if cost is not None and cost % recipe['output_quantity']:
            raise ValueError('Fractional unit costs are not supported')
    except ValueError as error:
        if forced:
            raise
        return base | {'reason': 'unsupported recipe: ' + str(error), 'nodes': [], 'edges': [],
                       'waterfall': [], 'leaves': [], 'spend_copper': None, 'profit_copper': None,
                       'can_add': False, 'evidence': {'basis': 'Cautious'}}
    original = next(c for c in explorer['catalogs'] if catalog_identity(c) == catalog_id)
    intermediate = original['items_by_id'][recipe['output_item_id']]['role'] != 'finished'
    nodes[0]['unit_cost_copper'] = (value['craft_cost_copper'] // recipe['output_quantity']
                                    if value['craft_cost_copper'] is not None else None)
    leaves = leaf_rows(explorer, catalog, value, batch)
    profit = None if intermediate else value['profit_copper']
    reason = ('Intermediate: no Action Board profit row' if intermediate else
              '' if explorer['snapshot'] else 'No Action Board row: import a priced scan in Data.')
    return base | {'reason': reason,
                   'nodes': nodes, 'edges': edges, 'leaves': leaves,
                   'waterfall': waterfall(value, leaves, recipe, intermediate, batch),
                   'spend_copper': multiply(value['craft_cost_copper'], batch),
                   'profit_copper': multiply(profit, batch),
                   'can_add': not intermediate and explorer['snapshot'] is not None,
                   'evidence': {'basis': 'Cautious', 'snapshot': explorer['snapshot'],
                                'rules_version': catalog['rules_version'],
                                'warnings': value.get('catalog_warnings', []),
                                'holdings_warning': explorer.get('holdings_warning'),
                                'holdings_captures': explorer.get('holdings', ({}, {}, [], []))[2],
                                'postage': 'Cross-profession postage is unconfirmed and uncharged.'}}


def multiply(value, count):
    return None if value is None else value * count


def build_graph(explorer, catalog, root, buy, forced):
    nodes: dict[int, dict] = {}
    edges: dict[tuple[int, int], dict] = {}

    def visit(item_id, units, column, trail, root_node=False):
        cost, method, _ = unit_route(catalog, buy, item_id, trail, forced) if not root_node else (None, 'craft', {})
        rid = root['recipe_id'] if root_node else catalog['recipe_for_output'].get(item_id)
        recipe = catalog['recipes_by_id'][rid] if rid is not None else None
        if item_id not in nodes:
            nodes[item_id] = node(explorer, catalog, item_id, recipe, method, cost, buy, trail, forced, root_node)
        current = nodes[item_id]
        current['units'] += units
        current['column'] = max(current['column'], column)
        if method != 'craft' or recipe is None:
            return
        if rid in trail:
            raise ValueError('Recipe cycle detected')
        inputs: dict[int, int] = {}
        for ingredient in recipe['inputs']:
            child = ingredient['item_id']
            inputs[child] = inputs.get(child, 0) + ingredient['quantity']
        for child, quantity in inputs.items():
            edges[item_id, child] = {'parent': item_id, 'child': child, 'quantity': quantity}
            visit(child, units * quantity // recipe['output_quantity'], column + 1, (*trail, rid))

    visit(root['output_item_id'], root['output_quantity'], 0, (), True)
    return list(nodes.values()), list(edges.values())


def node(explorer, catalog, item_id, recipe, method, cost, buy, trail, forced, root_node):
    item = catalog['items_by_id'][item_id]
    holdings = explorer.get('holdings') or ({}, {}, [], [])
    statuses = [{'character': list(c), **recipe_status(recipe, state)}
                for c, state in sorted(explorer['characters'].items())] if recipe else []
    makers = catalog.get('team_makeable', {}).get((recipe.get('catalog_id', catalog_identity(catalog)),
                                                 recipe['recipe_id']), []) if recipe else []
    maker = {'profession': recipe['profession'], 'made_by': makers[0] if makers else None} if recipe else {}
    return {'item_id': item_id, 'name': item['name'],
            'quality': (base_signal(explorer['items'], item_id) or {}).get('quality'),
            'units': 0, 'column': 0,
            'method': method, 'unit_cost_copper': cost, 'forced': bool(forced and item_id in forced),
            'options': [{'unit_cost_copper': c, 'method': m} for c, m, _ in
                        route_options(catalog, buy, item_id, trail, forced)] if not root_node else [],
            'maker': made_by_label(maker), 'characters': statuses,
            'route_note': 'no one makes this' if item_id in catalog.get('blocked_cross_items', set()) else '',
            'held': holdings[0].get((item_id, None, 'base'), 0) if holdings[2] else None,
            'at_least': any(c['unknown'] or c['partial'] for c in holdings[2])}


def leaf_rows(explorer, catalog, value, batch):
    metrics = {r['item_id']: base_signal(explorer['metrics'], r['item_id']) for r in explorer['metrics']}
    metrics = {item: row for item, row in metrics.items() if row is not None}
    rows = []
    for choice in value['shopping_choices']:
        item_id = choice['item_id']
        units = metrics.get(item_id, {}).get('units')
        # A vendor-routed leaf is bought from a vendor; auction depth would only mislead.
        depth = ('Vendor' if choice['method'] == 'vendor' else 'Unavailable' if not explorer['metrics'] else
                 ('Not listed' if units is None else f'{units} units listed'))
        rows.append(choice | {'name': catalog['items_by_id'][item_id]['name'],
                              'quantity': choice['quantity'] * batch,
                              'total_cost_copper': multiply(choice['total_cost_copper'], batch), 'depth': depth})
    return rows


def waterfall(value, leaves, recipe, intermediate, batch):
    lines = _waterfall(value, leaves, recipe, intermediate, batch)
    running = 0
    for line in lines:
        amount = line["amount_copper"]
        start = 0 if line["label"] == "Profit" else running
        line["start_copper"] = start
        line["end_copper"] = None if amount is None else start + amount
        running = line["end_copper"] or 0
    return lines


def _waterfall(value, leaves, recipe, intermediate, batch):
    lines = []
    if not intermediate:
        sale = multiply(value['sale_price_copper'], recipe['output_quantity'])
        lines.append({'label': 'Sale' + (' · capped at vendor price' if value.get('vendor_capped') else ''),
                      'amount_copper': sale})
        if sale is None:
            return lines + [{'label': 'Missing output sale price', 'amount_copper': None}]
        lines.append({'label': 'Auction cut', 'amount_copper': value['net_revenue_copper'] - sale})
    for leaf in leaves:
        amount = leaf['total_cost_copper']
        lines.append({'label': leaf['name'] + (' · Missing price: no usable route' if amount is None else ''),
                      'amount_copper': -amount // batch if amount is not None else None,
                      'quantity': leaf['quantity'] // batch, 'unit_cost_copper': leaf['unit_cost_copper']})
        if amount is None:
            return lines
    if not intermediate:
        lines.append({'label': 'Profit', 'amount_copper': value['profit_copper']})
    return lines
