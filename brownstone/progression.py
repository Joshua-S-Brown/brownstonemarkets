"""Team progression estimates from scoped evidence and team-aware board routes."""
from fractions import Fraction
from math import ceil

from . import action_board, professions, today_characters
from .crafting import basis_prices, evaluate_recipe
from .markets import MARKET_KEYS
from .recipe_catalogs import LEARNING_LABELS
from .recipe_graph import RecipeGraph, route_catalog
from .today import Ladder, _quote, _sell
from .today_confidence import confidence, route_notes


def expected_crafts(recipe: dict, rank: int) -> Fraction | None:
    """Orange is certain; yellow uses CRAFT-11's unconfirmed Classic assumption."""
    colors = recipe.get('skillup_colors')
    if colors is None:
        return None
    orange, yellow, green, grey = colors
    if not orange <= rank < green:
        return Fraction(0)
    return Fraction(1) if rank < yellow else Fraction(grey - yellow, grey - rank)


def _usable(recipe, state, rank):
    status = today_characters.recipe_status(recipe, state, planned_rank=rank)['craft_status']
    return status in ('Known', 'Train now'), status == 'Train now'


def _step_options(entries, state, rank, prices, trained):
    options, reasons = [], []
    for catalog, recipe in entries:
        usable, trainer = _usable(recipe, state, rank)
        if not usable:
            continue
        label = recipe['name']
        crafts = expected_crafts(recipe, rank)
        if crafts is None:
            reasons.append(f'{label}: missing colour')
            continue
        if not crafts:
            continue
        key = (action_board.catalog_identity(catalog), recipe['recipe_id'])
        training = recipe.get('training_cost_copper') if trainer and key not in trained else 0
        if training is None:
            reasons.append(f'{label}: training cost unknown')
            continue
        try:
            if "route_error" in catalog:
                raise ValueError(catalog["route_error"])
            result = evaluate_recipe(catalog, recipe['recipe_id'], prices)
        except ValueError as error:
            reasons.append(f'{label}: {error}')
            continue
        cost = result['craft_cost_copper']
        if cost is None:
            missing = [r['item_id'] for r in result['choices'] if r['unit_cost_copper'] is None]
            reasons.append(f'{label}: missing material price {missing}')
            continue
        options.append({'rank': rank, 'catalog_id': key[0], 'recipe_id': key[1], 'recipe': label,
                        'expected_crafts': str(crafts), 'cost_copper': ceil(cost * crafts) + training,
                        'training_cost_copper': training})
    return options, reasons


def skillup_walk(entries, state, rank, stop, prices):
    """Greedy cheapest usable craft for each point from ``rank`` up to ``stop``, ending at the first gap.

    Every target shares this walk (each stops earlier), so one walk per profession serves them all.
    """
    steps, trained = [], set()
    for point in range(rank, stop):
        options, gaps = _step_options(entries, state, point, prices, trained)
        if not options:
            return steps, f'Rank {point}: ' + ('; '.join(gaps) or 'no qualifying skill-up craft')
        step = min(options, key=lambda r: (r['cost_copper'], r['recipe_id'], r['catalog_id']))
        steps.append(step)
        trained.add((step['catalog_id'], step['recipe_id']))
    return steps, None


def estimate_cost(entries, state, rank, maximum, target, prices, walk=None):
    """Greedy cheapest usable craft at each point; no credit for selling results.

    ``walk`` is a ``skillup_walk`` result reaching at least ``min(target, maximum)``, reused across targets.
    """
    if rank is None:
        return {'cost_copper': None, 'complete': False, 'reasons': ['rank unknown'], 'steps': []}
    if maximum is None:
        return {'cost_copper': None, 'complete': False, 'reasons': ['max rank unknown'], 'steps': []}
    stop = min(target, maximum)
    walked, gap = walk if walk is not None else skillup_walk(entries, state, rank, stop, prices)
    steps = walked[:max(0, stop - rank)]
    reasons = [gap] if gap is not None and len(steps) < stop - rank else []
    if target > maximum:
        reasons.append('train the next tier first')
    return {'cost_copper': sum(s['cost_copper'] for s in steps) if not reasons else None,
            'complete': not reasons, 'reasons': reasons, 'steps': steps}


def _confidence(catalog, recipe, row, board, ladders, metrics, max_age_hours, auction_cut):
    if not row.get('valid'):
        return {'confidence': 'Unavailable', 'confidence_reasons': [row['action']]}
    purchases = _quote(row['shopping_choices'], 1, ladders, {})
    projected = row | {'evidence_notes': route_notes(catalog, recipe, row), 'purchases': purchases or [],
                       'output_quantity': recipe['output_quantity'], 'batch_size': 1,
                       'batch_cost_copper': row['craft_cost_copper']}
    label = confidence(projected, _sell(projected, metrics, auction_cut), board['freshness'],
                       max_age_hours, metrics, ladders)
    if purchases is None:
        return {'confidence': 'Low', 'confidence_reasons': [*label['confidence_reasons'], 'insufficient supply']}
    return label


def _groups(catalogs, state):
    groups, unlisted = {}, {}
    for name, record in state['recipes'].items():
        rank, maximum = today_characters.profession_rank(state, record)
        groups[name] = {'profession': name, 'rank': rank, 'max_rank': maximum, 'entries': [], 'recipes': [],
                        'note': '', 'skill_id': today_characters._skill_id(record['known_recipes'])}
    _add_unknown_skills(groups, state)
    for catalog in catalogs:
        identity = action_board.catalog_identity(catalog)
        unlisted[identity] = 0
        for recipe in catalog['recipes_by_id'].values():
            record, match = today_characters._match(state, recipe['recipe_id'])
            if not match:
                unlisted[identity] += 1
                continue
            name = record['known_recipes']['name'] if 'name' in record['known_recipes'] else next(
                name for name, value in state['recipes'].items() if value is record)
            groups[name]['entries'].append((catalog, recipe))
    return groups, unlisted


def _add_unknown_skills(groups, state):
    list_ids = {today_characters._skill_id(r['known_recipes']) for r in state['recipes'].values()}
    for row in professions.data_rows(state):
        if row['name'] is None or (row['skill_id'] is not None and row['skill_id'] in list_ids):
            continue
        if row['name'] in state['recipes'] and row['skill_id'] is None:
            continue  # This is the list's display row, rather than a bags skill line.
        name = row['name']
        key = name if name not in groups else f"{name} (skill {row['skill_id']})"
        groups[key] = {'profession': name, 'rank': row['rank'], 'max_rank': row['max_rank'],
                       'entries': [], 'recipes': [], 'note': 'recipes unknown', 'skill_id': row['skill_id']}


def summary_sort(row):
    """Current profit descending, complete before incomplete at ties, then cost and name."""
    best = row['best']
    profit = best['profit_copper'] if best else None
    estimate = best['estimate'] if best else {'complete': False, 'cost_copper': None}
    return (profit is None, -(profit or 0), not estimate['complete'], estimate['cost_copper'] or 0, row['profession'])


def build_progression(catalogs, observations, market, snapshot, character_data, character, *, now,
                      window=25, max_age_hours=24, auction_cut=.05, listings=None, metrics=None,
                      recipe_graph=None, board=None):
    """One character, full-market current scan; callers supply all evidence, the clock and optionally
    a team RecipeGraph and its Action Board already built from the same catalogs, market and character data."""
    if type(window) is not int or not 5 <= window <= 100:
        raise ValueError('Reach window must be an integer from 5 to 100')
    if snapshot.get('source_id') != market['source_id']:
        raise ValueError('The snapshot belongs to a different source')
    if any(snapshot.get(key) != market.get(key) for key in MARKET_KEYS):
        raise ValueError('The snapshot belongs to a different market')
    catalogs = action_board.compatible_catalogs(catalogs, market)
    state = character_data.get(character)
    if state is None:
        return {'professions': [], 'unlisted': {}, 'freshness': None}
    graph = recipe_graph if recipe_graph is not None else team_graph(catalogs, character_data, market)
    if board is None and catalogs:
        board = action_board.rank_catalogs(catalogs, observations, market, snapshot, now=now,
                                          max_age_hours=max_age_hours, auction_cut=auction_cut, recipe_graph=graph)
    rows = {(r['catalog_id'], r['recipe_id']): r for r in board['rows']} if board else {}
    prices, _ = basis_prices(observations, 'cautious')
    groups, unlisted = _groups(catalogs, state)
    for group in groups.values():
        group["entries"] = _routed_entries(group["entries"], prices, graph)
    ladders = {i: Ladder(values) for i, values in listings.items()} if listings is not None else None
    for group in groups.values():
        _populate(group, state, rows, prices, board, window, ladders, metrics, max_age_hours, auction_cut)
    result = {'professions': sorted(groups.values(), key=summary_sort), 'unlisted': unlisted,
              'freshness': board['freshness'] if board else None}
    return result | {'catalog_warnings': graph.warnings} if graph is not None else result


def _populate(group, state, rows, prices, board, window, ladders, metrics, max_age_hours, auction_cut):
    rank, maximum = group['rank'], group['max_rank']
    if rank is not None and maximum is not None and rank >= maximum:
        group['note'] = 'train the next tier first'
    walk = (skillup_walk(group['entries'], state, rank, min(rank + window, maximum), prices)
            if rank is not None and maximum is not None else None)
    for catalog, recipe in group['entries']:
        status = today_characters.recipe_status(recipe, state)
        required = recipe.get('required_skill')
        if (rank is None or required is None or not rank < required <= rank + window
                or status['craft_status'] == 'Known'):
            continue
        row = rows.get((action_board.catalog_identity(catalog), recipe['recipe_id']),
                       {'profit_copper': None, 'action': 'intermediate: not ranked by the Action Board'})
        estimate = estimate_cost(group['entries'], state, rank, maximum, required, prices, walk)
        group['recipes'].append(recipe | status | {'catalog_id': action_board.catalog_identity(catalog),
            'points_needed': required - rank, 'profit_copper': row['profit_copper'],
            'vendor_price_cap_copper': row.get('vendor_price_cap_copper'), 'vendor_capped': row.get('vendor_capped'),
            'board_reason': row['action'],
            'needs_pattern': 6 not in recipe.get('learned_from', []), 'estimate': estimate,
            **_confidence(catalog, recipe, row, board, ladders, metrics, max_age_hours, auction_cut)})
    group['recipes'].sort(key=lambda r: summary_sort({'best': r, 'profession': group['profession']}))
    group['best'], group['alternative'] = choose_best(group['recipes'])
    del group['entries']


def learnable(recipe):
    """CRAFT-11: a verified trainer, vendor or quest source can be acted on now; drops can't be controlled."""
    return any(LEARNING_LABELS.get(code) in ('trainer', 'vendor', 'quest') for code in recipe.get('learned_from', []))


def choose_best(recipes):
    """CRAFT-11 bands over recipes already in summary order: (best, the other route or None)."""
    valued = [r for r in recipes if r['profit_copper'] is not None]
    best = next((r for r in valued if learnable(r) and r['profit_copper'] > 0), next(iter(valued), None))
    if best is None:
        return None, None
    if learnable(best):
        return best, next((r for r in valued if not learnable(r) and r['profit_copper'] > best['profit_copper']), None)
    return best, next((r for r in valued if learnable(r)), None)


def _routed_entries(entries, prices, graph):
    result = []
    for catalog, recipe in entries:
        try:
            routed = route_catalog(catalog, recipe["recipe_id"], prices, graph)
        except ValueError as error:
            routed = catalog | {"route_error": str(error)}
        result.append((routed, recipe))
    return result


def team_board(catalogs, observations, market, snapshot, character_data, *, now, max_age_hours=24, auction_cut=.05):
    """The team RecipeGraph and Action Board that build_progression builds, once for every character."""
    catalogs = action_board.compatible_catalogs(catalogs, market)
    graph = team_graph(catalogs, character_data, market)
    board = action_board.rank_catalogs(catalogs, observations, market, snapshot, now=now, max_age_hours=max_age_hours,
                                       auction_cut=auction_cut, recipe_graph=graph) if catalogs else None
    return graph, board


def team_graph(catalogs, character_data, market):
    makers = today_characters.team_makeable(catalogs, character_data)
    return RecipeGraph(catalogs, makers, market) if makers is not None else None
