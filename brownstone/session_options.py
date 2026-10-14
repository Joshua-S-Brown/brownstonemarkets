"""This session: read-only composition of the reserved plan and Team estimates (UI-12)."""
from fractions import Fraction
from math import ceil

from . import action_board, farming, flood_signals, progression, today_characters
from .crafting import basis_prices, evaluate_recipe
from .markets import MARKET_KEYS
from .recipe_graph import route_catalog

PROGRESSION_KEYS = ('observations', 'market', 'snapshot', 'now', 'max_age_hours', 'auction_cut', 'listings', 'metrics')
# Classic Era's proficiency ladder (warcraft.wiki.gg/wiki/Classic_proficiency): a tier's cap gives the next
# tier and the character level its trainer requires. Unconfirmed on Forever, like CRAFT-11's yellow chances.
NEXT_TIER = {75: ('Journeyman', 10), 150: ('Expert', 20), 225: ('Artisan', 35)}


def base_signal(rows, item_id):
    """Only the unambiguous base/legacy identity may label catalog routes; never pool variants."""
    matches = [r for r in rows if r['item_id'] == item_id]
    base = next((r for r in matches if r['variant_state'] == 'base' and r['variant_id'] is None), None)
    if base is not None:
        return base
    if len(matches) == 1 and matches[0]['variant_state'] is None and matches[0]['variant_id'] is None:
        return matches[0]
    return None


def profession_order(group):
    best = group['best']
    profit = best['profit_copper'] if best else None
    cost = best['estimate']['cost_copper'] if best else None
    return (profit is None, -(profit or 0), cost is None, cost or 0, group['profession'])


def _materials(estimate, catalogs, prices, graph):
    """Retain existing cheapest-route quantities for the chosen cost steps, with no new price read."""
    steps = []
    for step in estimate['steps']:
        catalog = catalogs[step['catalog_id']]
        catalog = route_catalog(catalog, step['recipe_id'], prices, graph)
        choices = evaluate_recipe(catalog, step['recipe_id'], prices)['shopping_choices']
        steps.append(step | {'materials': [m | {'item_name': catalog['items_by_id'][m['item_id']]['name']}
                                           for m in choices]})
    return steps


def _profession(group, catalogs, prices, graph):
    capped = group['rank'] is not None and group['max_rank'] is not None and group['rank'] >= group['max_rank']
    recipes = [] if capped else [r | {'estimate': r['estimate'] | {
        'steps': _materials(r['estimate'], catalogs, prices, graph)}} for r in group['recipes']]
    return group | {'capped': capped, 'recipes': recipes}


def _crafts(plan, catalogs, state):
    result = []
    for row in plan['craft']:
        recipe = catalogs[row['catalog_id']]['recipes_by_id'][row['recipe_id']]
        status = today_characters.recipe_status(recipe, state)
        if status['craft_status'] in ('Known', 'Train now'):
            result.append(row | {'session_status': status})
    return result


def _item_ids(characters, plan):
    ids = {r['output_item_id'] for r in plan['craft']}
    ids.update(r['item_id'] for c in characters for r in c['farming']['rows'])
    ids.update(p['item_id'] for r in plan['craft'] for p in r['purchases'])
    for character in characters:
        for row in character['crafts']:
            ids.add(row['output_item_id'])
            ids.update(p['item_id'] for p in row['purchases'])
        for group in character['professions']:
            for recipe in group['recipes']:
                ids.add(recipe['output_item_id'])
                ids.update(m['item_id'] for s in recipe['estimate']['steps'] for m in s['materials'])
    return sorted(ids)


def _label_estimate(estimate, rows):
    steps = []
    cheap = 0
    for step in estimate['steps']:
        materials = [m | {'signal': base_signal(rows, m['item_id'])} for m in step['materials']]
        cheap_per_craft = sum(m['total_cost_copper'] for m in materials if m['method'] == 'buy'
                              and m['signal'] and m['signal']['overshoot']['label'] == 'cheap')
        cheap += ceil(cheap_per_craft * Fraction(step['expected_crafts']))
        steps.append(step | {'materials': materials})
    # A partial walk is not an estimate of the total or its cheap share.
    return estimate | {'steps': steps, 'cheap_cost_copper': cheap if estimate['complete'] else None}


def next_tier(group, level):
    """The tier past this cap and whether the character is high enough level to train it."""
    tier = NEXT_TIER.get(group['max_rank'])
    if tier is None or group['rank'] is None:
        return None
    name, required = tier
    return {'name': name, 'cap': group['max_rank'], 'required_level': required,
            'level_ok': level is not None and level >= required}


def milestones(recipes):
    """Recipes at one required skill share one estimate, so each reach is shown once, lowest first."""
    by_skill = {}
    for recipe in recipes:
        by_skill.setdefault(recipe['required_skill'], []).append(recipe)
    return [{'skill': skill, 'estimate': group[0]['estimate'], 'recipes': group}
            for skill, group in sorted(by_skill.items())]


def _profession_steps(group):
    steps = []
    best = group['best']
    if best is not None and best['estimate']['complete']:
        unlocked = [r for r in group['recipes'] if r['profit_copper'] is not None
                    and r['required_skill'] <= best['required_skill'] and r is not best]
        steps.append({'kind': 'level_profession', 'group': group, 'recipe': best, 'more': len(unlocked)})
    tier = group['tier']
    if tier is not None and not tier['level_ok']:
        steps.append({'kind': 'level_character', 'group': group, 'tier': tier})
    elif tier is not None and group['capped']:
        steps.append({'kind': 'train', 'group': group, 'tier': tier})
    return steps


def next_steps(character):
    """A short line per option, crafting first; the owner still chooses between them (UI-12)."""
    steps = [{'kind': 'craft'}] if character['crafts'] else []
    for group in character['professions']:
        steps.extend(_profession_steps(group))
    if not character['professions']:
        return steps + [{'kind': 'evidence'}]
    if not any(s['kind'] in ('craft', 'level_profession') for s in steps):
        steps.insert(0, {'kind': 'nothing'})
    return steps


def _label_character(character, rows):
    crafts = [r | {'signal': base_signal(rows, r['output_item_id']), 'purchases': [
        p | {'signal': base_signal(rows, p['item_id'])} for p in r['purchases']]} for r in character['crafts']]
    groups = []
    for group in character['professions']:
        recipes = [r | {'estimate': _label_estimate(r['estimate'], rows)} for r in group['recipes']]
        groups.append(group | {'recipes': recipes, 'milestones': milestones(recipes),
                               'tier': next_tier(group, character['level']),
                               'best': next((r for r in recipes if r['profit_copper'] is not None), None)})
    result = character | {'crafts': crafts, 'professions': sorted(groups, key=profession_order),
                          'craft_profit_copper': sum(r['batch_profit_copper'] for r in crafts)}
    return result | {'next_steps': next_steps(result)}


def build_options(db, config, arguments, plan, *, window=25):
    """Use load_today's evidence and the displayed plan; one flood read for the union of item IDs."""
    if any(config.get(k) != arguments['market'].get(k) for k in (*MARKET_KEYS, 'source_id', 'rules_version')):
        raise ValueError('Session signals must use the plan source, full market and rules version')
    catalogs = action_board.compatible_catalogs(arguments['catalogs'], arguments['market'])
    by_id = {action_board.catalog_identity(c): c for c in catalogs}
    prices, sell_prices = basis_prices(arguments['observations'], 'cautious')
    data = arguments['character_data']
    graph = progression.team_graph(catalogs, data, arguments['market'])
    characters = []
    for identity in today_characters.available_characters(data):
        result = progression.build_progression(catalogs=catalogs, character_data=data, character=identity,
                                              window=window, recipe_graph=graph,
                                              **{k: arguments[k] for k in PROGRESSION_KEYS})
        level = data[identity].get('bags', {}).get('level')
        characters.append({'character': identity, 'level': level if type(level) is int else None,
                           'crafts': _crafts(plan, by_id, data[identity]),
                           'farming': farming.history(data[identity].get('observations', []),
                                                      config.get('farming_idle_minutes', 10)),
                           'professions': [_profession(g, by_id, prices, graph) for g in result['professions']],
                           'unlisted': result['unlisted']})
    signals = flood_signals.signals(db, config, _item_ids(characters, plan), arguments['now'])
    characters = [c | {'farming': farming.valued(c['farming'], sell_prices, signals['rows'],
                                                arguments['auction_cut'])} for c in characters]
    return {'characters': [_label_character(c, signals['rows']) for c in characters],
            'snapshot': arguments['snapshot'], 'freshness': plan['freshness'], 'signals': signals, 'window': window}
