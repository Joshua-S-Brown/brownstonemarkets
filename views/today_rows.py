"""Framework-free Today wording for the API adapters; copper conversion uses money.py."""
from brownstone.money import format_money
from brownstone.tier_levels import fallback_label
from brownstone.today_characters import recipe_colour


def capture_label(capture):
    """One holdings capture with its age; a missing location is never shown as empty."""
    age = capture['age_hours']
    state = f"{age:.1f} hours old" if age is not None else f"{capture['kind']} not captured"
    return f"{capture['character']} · {capture['kind']} · {state}"


def empty_sentence(hidden, minimum_copper, gold_copper):
    """Explain the largest exclusions without claiming knowledge or prices we do not have."""
    reasons = sorted(((reason, count) for reason, count in hidden.items() if count),
                     key=lambda entry: (-entry[1], entry[0]))[:2]
    why = ' Most recipes are hidden because ' + ' and '.join(
        HIDDEN_WORDING.get(r, r) for r, _ in reasons) + '.' if reasons else ''
    return (f"No craft meets the {format_money(minimum_copper)} minimum batch gain with "
            f"{format_money(gold_copper)} available.{why} Review your settings or inspect all reasons.")


HIDDEN_WORDING = {
    'no character has this profession': 'your team does not have the required professions',
    'rank below required skill': 'profession ranks are below the required skill',
    'below minimum gain': 'profit is below minimum gain',
    'one craft exceeds funds': 'one craft costs more than the available gold',
    'insufficient listed materials': 'there are not enough listed materials',
    'missing prices': 'prices are missing',
}


CROWDING = {'thin': ('thin: few listings', 'warn'), 'contested': ('contested: many sellers', 'warn')}
OVERSHOOT = {'cheap': ('cheap right now', 'good'), 'high': ('pricier than usual', 'warn'),
             'too few days': ('price history too short', 'neutral'), 'no buyout': ('no buyout', 'neutral')}


def warning_text(fields):
    signal = fields.get('signal') or {}
    words = [labels[key][0] for labels, key in ((CROWDING, signal.get('crowding')),
             (OVERSHOOT, signal.get('overshoot', {}).get('label'))) if key in labels]
    removals = fields.get('early_removals')
    if removals and removals['pairs'] >= 3 and removals['units'] == 0:
        words.append(f"no early removals in {removals['pairs']} scan gaps")
    if fields.get('price_note'):
        words.append(fields['price_note'])
    return '; '.join(words)


def vendor_cap_label(*rows):
    """Label only a value the vendor price actually lowered; a sale already below it is uncapped."""
    row = next((r for r in rows if r.get('vendor_capped')), None)
    return f"capped at vendor price {format_money(row['vendor_price_cap_copper'])}" if row else ""


def vendor_cap_suffix(*rows):
    label = vendor_cap_label(*rows)
    return f" · {label}" if label else ""


def cheap_share(estimate):
    cheap, cost = estimate['cheap_cost_copper'], estimate['cost_copper']
    if cheap is None:
        return 'cheap auction materials unknown'
    if cheap == cost and cost:
        return 'all on materials that are cheap right now'
    return f'{format_money(cheap)} of it on cheap auction materials' if cheap else 'no cheap auction materials'


def step_text(step, character, window):
    """One plain line per option; the figures are the ones in the details below."""
    name = character['character'][0]
    kind = step['kind']
    if kind == 'craft':
        rows = ', '.join(f"{r['batch_size']} {r['output_name']}" for r in character['crafts'])
        return (f"Craft {rows} · planned profit {format_money(character['craft_profit_copper'])}"
                f"{session_profit_basis(character)}")
    if kind == 'nothing':
        return (f'Nothing to craft or level within {window} points. '
                'Gathering is an option here.')
    if kind == 'evidence':
        return 'No professions seen yet: open each profession window next login so Brownstone can read them.'
    group = step['group']
    profession = group['profession']
    if kind == 'level_profession':
        recipe, estimate = step['recipe'], step['recipe']['estimate']
        more = f" (+{step['more']} more on the way)" if step['more'] else ''
        return (f"Level {profession} {group['rank']} → {recipe['required_skill']} for "
                f"{format_money(estimate['cost_copper'])}, {cheap_share(estimate)} · unlocks {recipe['name']} "
                f"at {format_money(recipe['profit_copper'])} per craft{more}{vendor_cap_suffix(recipe)}")
    tier = step['tier']
    if len(step.get('groups', [])) > 1:
        return merged_tier_text(step, character)
    if kind == 'train':
        return (f"{profession} is capped at {tier['cap']}: train {tier['name']} {profession} at a trainer"
                f"{fallback_label(tier)}")
    level = character['level']
    reach = (f"{profession} is capped at {tier['cap']}" if group['capped']
             else f"Before {profession} reaches {tier['cap']}")
    now = f"{level} → {tier['required_level']}" if level is not None else f"to {tier['required_level']} (level unknown)"
    return f"{reach}: level {name} {now} to train {tier['name']}{fallback_label(tier)}"


def merged_tier_text(step, character):
    professions = [g['profession'] for g in step['groups']]
    names = ', '.join(professions[:-1]) + ' and ' + professions[-1]
    tier = step['tier']
    if step['kind'] == 'train':
        return f"Train {tier['name']} at a trainer: {names}{fallback_label(tier)}"
    level = character['level']
    now = f"{level} → {tier['required_level']}" if level is not None else f"to {tier['required_level']} (level unknown)"
    return f"Level {character['character'][0]} {now} to train {tier['name']} {names}{fallback_label(tier)}"


def mob_label(npc, names):
    if npc is None:
        return 'Gathering · zone only'
    return f'{names[npc]} (NPC {npc})' if npc in names else f'NPC {npc}'


def spot_position(spot):
    cell = spot.get('cell')
    if cell is None:
        return '—'
    half = spot['cell_percent'] // 2
    return f'around {cell[0] + half}, {cell[1] + half}'


def spot_coin_share(spot):
    coin, total = spot['coin_copper'], spot['value_copper']
    if coin is None:
        return 'Coin unavailable'
    return f'Coin {coin * 100 // total}%' if total else 'Coin unknown'


def session_profit_basis(character):
    bases = [r.get('profit_basis') for r in character['crafts']]
    if bases and all(bases):
        return ' at cautious sale price'
    return ' (includes crafts at cautious sale price)' if any(bases) else ''


def session_display(options, arguments):
    """Readable session projection retaining all evidence; no extra loads or estimates."""
    characters = []
    levers = []
    for character in options['characters']:
        groups = []
        for group in character['professions']:
            recipes = [r | {'skillup_band': recipe_band(r, group['rank'], arguments['catalogs'],
                                arguments.get('character_data', {}).get(tuple(character['character']))),
                            'estimate': r['estimate'] | {'material_notes': reach_notes(r['estimate'])}}
                       for r in group['recipes']]
            groups.append(group | {'recipes': recipes,
                'best': next((r for r in recipes if group['best'] is not None and
                              (r['catalog_id'], r['recipe_id']) ==
                              (group['best']['catalog_id'], group['best']['recipe_id'])), None),
                'milestones': [
                m | {'estimate': m['estimate'] | {'material_notes': reach_notes(m['estimate'])},
                     'recipes': [r for r in recipes if r['required_skill'] == m['skill']]}
                for m in group['milestones']]})
        farming = character['farming']
        spots = [spot | {'mob': mob_label(spot['npc_id'], farming.get('npc_names', {})),
                          'position': spot_position(spot), 'coin_share': spot_coin_share(spot)}
                 for spot in farming['spots']]
        characters.append(character | {'professions': groups, 'farming': farming | {'spots': spots},
                                       'options_text': [step_text(step, character, options['window'])
                                                        for step in character['next_steps']]})
        for step, text in zip(character['next_steps'], characters[-1]['options_text'], strict=True):
            if step['kind'] == 'level_profession':
                recipe = step['recipe']
                levers.append({'character': character['character'], 'profession': step['group']['profession'],
                               'reach': recipe['required_skill'], 'cost_copper': recipe['estimate']['cost_copper'],
                               'profit_copper': recipe['profit_copper'], 'text': text})
    lever = min(levers, key=lambda row: (-row['profit_copper'], row['cost_copper'],
                                        row['character'], row['profession']), default=None)
    return options | {'characters': characters, 'lever': lever}


def recipe_band(row, rank, catalogs, character_state=None):
    recipe = next((c['recipes_by_id'].get(row['recipe_id']) for c in catalogs
                   if c['catalog_id'] == row['catalog_id']), None)
    game_color = recipe_colour(character_state, row['recipe_id']) if character_state else None
    game = game_color and f"{game_color}{'' if rank is None else f' at rank {rank}'} (from the game)"
    colors = recipe.get('skillup_colors') if recipe else None
    if not colors:
        return (f'{game} · ' if game else '') + 'skill-up range unknown: catalog has no colour bands'
    orange, yellow, green, grey = colors
    thresholds = f'orange {orange}, yellow {yellow}, green {green}, grey {grey}'
    if rank is None:
        return f'{game} · {thresholds}' if game else 'skill-up colour unknown: character rank unknown'
    color = band_colour(rank, colors)
    label = f"needs {orange} · you're {rank}" if color == 'not yet' else f'{color} at rank {rank}'
    if game:
        label = game + (f' · catalog says needs {orange}' if color == 'not yet' else '')
    return f'{label} · {thresholds}'


def band_colour(rank, colors):
    orange, yellow, green, grey = colors
    if rank < orange:
        return 'not yet'
    if orange == green:
        return 'no reliable skill-ups'
    return next((label for threshold, label in ((yellow, 'orange'), (green, 'yellow'), (grey, 'green'))
                 if rank < threshold), 'grey')


def reach_notes(estimate):
    """Held value is worth, and measured farming time is an alternative to cash."""
    notes = []
    if estimate.get('holdings_at_least'):
        notes.append('Held amounts are at least the captured count; captures are partial, missing or stale.')
    for row in estimate.get('held', []):
        worth = format_money(row['worth_copper']) if row['worth_copper'] is not None else 'unknown'
        notes.append(f"Held {row['units']:g} {row['item_name']} from {row['character']}’s {row['kind']} · "
                     f"worth {worth} if sold" + (f" · mail from {row['character']}" if row.get('mail') else ''))
    for row in estimate.get('buy', []):
        purchase = f"Buy {row['purchased_units']}" if row['purchased_units'] else 'Use earlier reach purchases for'
        notes.append(f"{purchase} {row['item_name']} · ≈ {row['quantity']:g} units needed")
        rate = row['farm']
        if rate:
            notes.append(f"Or farm ≈ {row['farm_hours']:.1f} h at {rate['zone'] or 'unknown zone'} "
                         f"({rate['character'][0]}’s own rate) · your own past sessions, not a promise; "
                         'launch respawn competition differs; listings are not sales.')
    unused = estimate.get('unused_stock')
    if unused:
        notes.append(f"Buying everything is cheaper over these {unused['points']} points: "
                     f"{format_money(unused['cost_copper'])}, against {format_money(unused['held_cost_copper'])} "
                     'using held stock; held stock stays for later.')
    return notes
