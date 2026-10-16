"""Pure Team projections shared by the web adapters and the native migration view."""
from . import hiring, progression, recipe_catalogs
from .today_characters import available_characters

BOARD_KEYS = ('observations', 'market', 'snapshot', 'now', 'max_age_hours', 'auction_cut')
HONESTY = ('Cost to reach is an estimate, with no credit for selling results. Current-scan profit, not a forecast; '
           'sales speed and demand unknown; beta prices; yellow skill-up chances are estimates.')
HIRING_LABELS = ('Current-scan prices are not a forecast; listings never sales; sales speed and demand unknown; '
                 'beta prices; estimated yellow chances unconfirmed on Forever. '
                 'Forever tier levels use trainer lists where known, otherwise Classic assumptions. '
                 'Costs give no credit for selling results. No gathering income. Tier fees not included (unknown).')


def training_payback(recipe):
    """Return a status and integer craft count, leaving wording to the view."""
    training, profit = recipe.get('training_cost_copper'), recipe.get('profit_copper')
    if not training:
        return {'status': 'absent', 'crafts': None}
    if profit is None:
        return {'status': 'unknown', 'crafts': None}
    if profit <= 0:
        return {'status': 'never', 'crafts': None}
    return {'status': 'crafts', 'crafts': (training + profit - 1) // profit}


def next_step(group):
    return {'kind': 'note' if group['note'] else 'best' if group['best'] else 'none',
            'note': group['note'], 'best': group['best']}


def alternative_kind(recipe):
    return None if recipe is None else 'learn' if progression.learnable(recipe) else 'hunt'


def gathering(group):
    return group.get('skill_id') in {hiring.SKILL_IDS[n] for n in ('mining', 'herbalism', 'skinning', 'fishing')}


def all_incomplete(rows):
    return bool(rows) and all(not row['estimate']['complete'] for row in rows)


def team_board(catalogs, data, arguments):
    if arguments is None or not data:
        return None
    try:
        return progression.team_board(catalogs, character_data=data, **{k: arguments[k] for k in BOARD_KEYS})
    except ValueError:
        return None


def team_results(catalogs, data, arguments, window, shared=None):
    if arguments is None:
        return {}
    graph, board = shared or (None, None)
    return {c: progression.build_progression(
        catalogs=catalogs, character_data=data, character=c, window=window, recipe_graph=graph, board=board,
        **{key: arguments[key] for key in (*BOARD_KEYS, 'listings', 'metrics')}) for c in available_characters(data)}


def path_result(result):
    """Annotate computed decisions, retaining all original calculation evidence."""
    groups = []
    for group in result['professions']:
        def recipe(row):
            return row | {'learn_from': recipe_catalogs.learning_label(row), 'payback': training_payback(row)}
        groups.append(group | {'recipes': [recipe(r) for r in group['recipes']],
                               'best': recipe(group['best']) if group['best'] else None,
                               'alternative': recipe(group['alternative']) if group.get('alternative') else None,
                               'alternative_kind': alternative_kind(group.get('alternative')),
                               'gathering': gathering(group), 'next_step': next_step(group)['kind']})
    return result | {'professions': groups}
