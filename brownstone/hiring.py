"""Read-only new-hire comparisons; scoped evidence and prices are supplied by the caller."""
from . import action_board, professions, progression, tier_levels, today_characters
from .crafting import basis_prices, evaluate_recipe
from .markets import MARKET_KEYS
from .recipe_catalogs import PROFESSIONS, profession_title
from .recipe_graph import RecipeGraph
from .scans import _list
from .session_options import NEXT_TIER

CAPS = (*NEXT_TIER, 300)
TIER_FEES = 'tier fees not included (unknown)'
NO_CATALOG = 'no catalog: gathering income and supply are not modelled'
SECONDARY = {185, 129, 356}  # Cooking, First Aid, Fishing: no primary slot.
# Slot-only mappings: CRAFT-13's Classic skill-page evidence; other IDs reuse Character eligibility.
SKILL_IDS = today_characters.PROFESSION_SKILL_IDS | {'herbalism': 182, 'skinning': 393, 'fishing': 356}


def new_hire(catalogs, profession):
    """Hypothetical rank-one list: every trainer recipe explicitly unlearned, no other profession."""
    recipes = [r for c in catalogs if c['profession'] == profession for r in c['recipes_by_id'].values()
               if _trainer(r)]
    return {'bags': {}, 'recipes': {profession_title(profession): {'known_recipes': {
        'name': profession_title(profession), 'rank': 1, 'max_rank': 300,
        'skill_id': SKILL_IDS.get(profession),
        'rows': [{'recipe_id': r['recipe_id'], 'learned': False} for r in recipes]}}}}


def _holders(catalogs, data, profession):
    recipe_ids = {r for c in catalogs if c['profession'] == profession for r in c['recipes_by_id']}
    result = []
    for character, state in sorted(data.items()):
        records = [record for record in state['recipes'].values()
                   if (SKILL_IDS.get(profession) is not None and
                       today_characters._skill_id(record['known_recipes']) == SKILL_IDS[profession])
                   or any(r.get('recipe_id') in recipe_ids
                          for r in _list(record['known_recipes'].get('rows'), 'recipe rows'))]
        if records:
            record = max(records, key=professions._order)
            rank, maximum = today_characters.profession_rank(state, record)
            result.append({'character': character, 'rank': rank, 'max_rank': maximum})
        else:
            rows = [r for r in professions.data_rows(state) if r['skill_id'] is not None
                    and r['skill_id'] == SKILL_IDS.get(profession)]
            result.extend({'character': character, 'rank': r['rank'], 'max_rank': r['max_rank']} for r in rows)
    return result


def prepare(catalogs, observations, market, snapshot, character_data, *, now, max_age_hours=24, auction_cut=.05,
            shared=None):
    """Build the unchanged team board once, plus the eligible consuming rows and cautious prices.

    ``shared`` is ``progression.team_board``'s (graph, board) for the same evidence, reused when present.
    """
    if snapshot.get('source_id') != market['source_id']:
        raise ValueError('The snapshot belongs to a different source')
    if any(snapshot.get(k) != market.get(k) for k in MARKET_KEYS):
        raise ValueError('The snapshot belongs to a different market')
    catalogs = action_board.compatible_catalogs(catalogs, market)
    makers = today_characters.team_makeable(catalogs, character_data) or {}
    graph, board = shared if shared is not None and shared[0] is not None else (RecipeGraph(catalogs, makers, market),
                                                                                 None)
    if board is None:
        board = action_board.rank_catalogs(catalogs, observations, market, snapshot, now=now,
                                          max_age_hours=max_age_hours, auction_cut=auction_cut,
                                          recipe_graph=graph) if catalogs else {'rows': [], 'freshness': None}
    return {'catalogs': catalogs, 'market': market, 'data': character_data, 'makers': makers, 'board': board,
            'tier_levels': tier_levels.load(),
            'prices': basis_prices(observations, 'cautious')[0],
            'consumers': [r for r in board['rows'] if makers.get((r['catalog_id'], r['recipe_id']))],
            'catalog_warnings': graph.warnings,
            'progression_arguments': dict(catalogs=catalogs, observations=observations, market=market,
                snapshot=snapshot, character_data=character_data, now=now, max_age_hours=max_age_hours,
                auction_cut=auction_cut, recipe_graph=graph)}


def _trainer(recipe):
    return 6 in (recipe.get('learned_from') or [])


def _unknown_source(recipe):
    return not recipe.get('learned_from')


def _training_catalogs(context, profession):
    """Own catalog-local routes: trainer recipes plus any recipe the current team already makes."""
    result = []
    for catalog in context['catalogs']:
        if catalog['profession'] == profession:
            name = action_board.catalog_identity(catalog)
            recipes = {rid: r for rid, r in catalog['recipes_by_id'].items()
                       if _trainer(r) or context['makers'].get((name, rid))}
            catalog = catalog | {'recipes_by_id': recipes,
                                 'recipe_for_output': {r['output_item_id']: rid for rid, r in recipes.items()}}
        result.append(catalog)
    return result


def cost_walk(context, profession):
    catalogs = _training_catalogs(context, profession)
    graph = RecipeGraph(catalogs, context['makers'], context['market'])
    entries = [(c, r) for c in catalogs if c['profession'] == profession
               for r in c['recipes_by_id'].values() if _trainer(r)]
    entries = progression._routed_entries(entries, context['prices'], graph)
    state = new_hire(catalogs, profession)
    steps, gap = progression.skillup_walk(entries, state, 1, 300, context['prices'])
    if gap is None:
        return steps, gap
    point = len(steps) + 1
    unknown = sum(_unknown_source(r) and r.get('required_skill') is not None and r['required_skill'] <= point
                  for c in context['catalogs'] if c['profession'] == profession for r in c['recipes_by_id'].values())
    return steps, gap + (f'; {unknown} recipes at or below rank {point} have no learning-source evidence'
                         if unknown else '')


def _best(context, profession, cap):
    ids = {(action_board.catalog_identity(c), r['recipe_id']) for c in context['catalogs']
           if c['profession'] == profession for r in c['recipes_by_id'].values()
           if _trainer(r) and r.get('required_skill') is not None and r['required_skill'] <= cap}
    return next((r for r in context['board']['rows'] if (r['catalog_id'], r['recipe_id']) in ids
                 and r['profit_copper'] is not None), None)


def summary_sort(row):
    best = row['best']
    profit = best['profit_copper'] if best else None
    estimate = row['estimate']
    return (profit is None, -(profit or 0), not estimate['complete'], estimate['cost_copper'] or 0,
            row['profession'])


def summaries(context, *, window=25, results=None):
    """Rank-300 estimates are needed for sorting; tier feed graphs wait until a disclosure opens."""
    rows = []
    names = sorted({c['profession'] for c in context['catalogs']})
    for name in names:
        walk = cost_walk(context, name)
        rows.append({'profession': name, 'best': _best(context, name, 300),
                     'best_now': _best(context, name, 1 + window), 'walk': walk,
                     'holders': _holders(context['catalogs'], context['data'], name),
                     'estimate': progression.estimate_cost([], {}, 1, 300, 300, context['prices'], walk)})
    return {'rows': sorted(rows, key=summary_sort),
            'no_catalog': sorted(set((*PROFESSIONS, 'herbalism', 'skinning', 'fishing')) - set(names)),
            'comparisons': comparisons(context, window=window, results=results)}


def comparisons(context, *, window=25, results=None):
    """Two primary slots, with CRAFT-11's best reachable profit at Team's remembered window.

    Team passes its own results so the comparison shows the same holdings-first reach costs."""
    result = []
    for character, state in sorted(context['data'].items()):
        primary = [name for name, sid in SKILL_IDS.items() if sid not in SECONDARY
                   and _holders(context['catalogs'], {character: state}, name)]
        if len(primary) != 2:
            continue
        progress = (results or {}).get(character) or progression.build_progression(
            **context['progression_arguments'], character=character, window=window, board=context['board'])
        groups = []
        for name in sorted(primary):
            matches = [g for g in progress['professions'] if any(r.get('profession') == name for r in g['recipes'])
                       or any(today_characters._skill_id(record['known_recipes']) == SKILL_IDS[name]
                              for title, record in state['recipes'].items() if title == g['profession'])]
            groups.append({'profession': name, 'best': next((g['best'] for g in matches if g['best']), None)})
        result.append({'character': character, 'professions': groups})
    return result


def feeds(context, profession, cap):
    """Cost reductions for eligible current board rows; never value an unpriced baseline as zero."""
    makers = {key: list(value) for key, value in context['makers'].items()}
    for catalog in context['catalogs']:
        if catalog['profession'] != profession:
            continue
        for recipe in catalog['recipes_by_id'].values():
            if (_trainer(recipe) and recipe.get('required_skill') is not None
                    and recipe['required_skill'] <= cap):
                makers.setdefault((action_board.catalog_identity(catalog), recipe['recipe_id']), []).append('New hire')
    graph = RecipeGraph(context['catalogs'], makers, context['market'])
    savings = []
    for row in context['consumers']:
        saving = _saving(context, graph, row, profession)
        if saving:
            savings.append(saving)
    savings.sort(key=lambda r: (-r['saved_copper'], r['catalog_id'], r['recipe_id']))
    return {'count': len(savings), 'top': savings[:3], 'note': '' if savings else 'feeds nothing'}


def _saving(context, graph, row, profession):
    if row['craft_cost_copper'] is None:
        return None
    catalog = action_board.catalog_for_row(context['catalogs'], row)
    try:
        routed = graph.for_recipe(catalog, row['recipe_id'], context['prices'])
        value = evaluate_recipe(routed, row['recipe_id'], context['prices'])
    except ValueError:
        return None
    cost = value['craft_cost_copper']
    if cost is None or cost >= row['craft_cost_copper']:
        return None
    materials = sorted({s['item_name'] for s in value['intermediate_steps']
                        if graph.recipes[s['recipe_id']]['profession'] == profession})
    return {'catalog_id': row['catalog_id'], 'recipe_id': row['recipe_id'], 'recipe':
            catalog['recipes_by_id'][row['recipe_id']]['name'], 'material': ', '.join(materials),
            'saved_copper': row['craft_cost_copper'] - cost}


def detail(context, row):
    name = row['profession']
    recipes = [r for c in context['catalogs'] if c['profession'] == name for r in c['recipes_by_id'].values()]
    levels = {next_cap: tier_levels.lookup(context['tier_levels'], context['market']['game_version'], name,
                                         *NEXT_TIER[cap])
              for cap, next_cap in zip(CAPS, CAPS[1:], strict=False)}
    return {'profession': name,
            'needs_pattern': sum(not _trainer(r) and not _unknown_source(r) for r in recipes),
            'unknown_source': sum(_unknown_source(r) for r in recipes),
            'tiers': [{'cap': cap, **levels.get(cap, {'required_level': None}), 'tier_fees': TIER_FEES,
                       **tier(context, row, cap), 'feeds': feeds(context, name, cap)} for cap in CAPS]}


def tier(context, row, cap):
    """CRAFT-13 hire cost and best trainer craft at one cap; Team's planned roster reuses it."""
    return {'estimate': progression.estimate_cost([], {}, 1, 300, cap, context['prices'], row['walk']),
            'best': _best(context, row['profession'], cap)}
