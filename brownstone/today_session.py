"""Shared session identity and queue prose; no framework state or calculations."""
import hashlib
import json
from copy import deepcopy

from brownstone.money import format_money
from brownstone.recipe_graph import made_by_label
from brownstone.today import TODAY_VERSION, build_today, craft_details
from brownstone.today_characters import recipe_rank
from brownstone.today_funds import recorded_balances


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def plan_context(arguments):
    # Listings, observations and metrics are read for the snapshot ID, so the snapshot identifies them.
    context = {key: arguments[key] for key in ("catalogs", "market", "snapshot", "settings",
                                              "max_age_hours", "auction_cut")}
    context["today_version"] = TODAY_VERSION
    context["character_data"] = sorted(arguments.get("character_data", {}).items())
    evidence = arguments.get('holdings_data')
    context['holdings_data'] = ([{k: v for k, v in c.items() if k != 'age_hours'}
                                 for c in evidence[2]], evidence[3]) if evidence else None
    return digest(context)


def stable_queue(queue):
    """Queue identity without confidence labels, so age transitions keep ticks."""
    return {**queue, "lines": [{k: v for k, v in line.items() if k not in ("confidence", "confidence_reasons")}
                               for line in queue["lines"]]}


def queue_total(queue):
    profit = queue["expected_profit_copper"]
    deposits = queue.get("deposits_to_post_copper")
    return (f"Gold needed: {format_money(queue['gold_needed_copper'])} · "
            f"Deposits to post: {format_money(deposits) if deposits is not None else 'unknown'} · "
            f"Expected profit at undercut: {format_money(profit) if profit is not None else 'unavailable'}")


def queue_line(line):
    text = queue_line_text(line)
    if "confidence" in line:
        reasons = ", ".join(line["confidence_reasons"])
        text += f" · {line['confidence']} confidence" + (f" ({reasons})" if reasons else "")
    return text


def queue_line_text(line):
    stage, name = line["stage"], line["name"]
    if stage == 'gold mail':
        return f"{line['character']} mails {format_money(line['copper'])} to {name}"
    if stage == 'gold unknown':
        return f"{name}'s gold isn't captured; {name} needs {format_money(line['copper'])} for purchases"
    if stage in ("auction house", "vendor"):
        return (f"Buy at {stage}: {name} · {line['purchased_units']} units · "
                f"highest unit {format_money(line['highest_unit_copper'])} · total {format_money(line['cost_copper'])}")
    if stage == 'take':
        return f"{line['character']}: take {line['units']} {name}" + held_note(line)
    if stage == 'mail':
        return f"{line['character']}: mail {line['units']} {name} to {line['to']}" + held_note(line)
    if stage == "craft":
        maker = f" · {made_by_label(line)}" if line.get("profession") else ""
        return (f"Craft: {name}{maker} · recipe {line['recipe_id']} ({line['catalog_id']}) · "
                f"{line['batch_size']} crafts" + held_note(line))
    price = format_money(line["unit_copper"]) if line["unit_copper"] is not None else "unavailable"
    profit = format_money(line["profit_copper"]) if line["profit_copper"] is not None else "unavailable"
    deposit = deposit_text(line)
    held = line.get('held_outputs', [])
    if held:
        owners = ', '.join(f"{u['character']} ({u['kind']}): {u['units']}" for u in held)
        value = line.get('held_value_copper')
        return (f"Post: {name} · post {line['quantity']} crafted + {sum(u['units'] for u in held)} held "
                f"({owners}) · undercut unit {price} · profit {profit} · held value "
                f"{format_money(value) if value is not None else 'unavailable'} · {deposit}")
    return f"Post: {name} · {line['quantity']} units · undercut unit {price} · profit {profit} · {deposit}"


def held_note(line):
    """Shared Route and copied Queue action/purpose suffix."""
    if line['stage'] == 'craft':
        items = [f"{a['units']} {a['name']}" for a in line.get('own_bags', [])]
        return ' · uses ' + ' and '.join(items) + ' you hold' if items else ''
    purposes = line.get('purposes', [])
    purpose = ', for ' + ' and '.join(p['name'] for p in purposes) if purposes else ''
    if line.get('purpose_step'):
        purpose += f" (step {line['purpose_step']})"
    if line['stage'] != 'take':
        return purpose
    mail = f", then mail them to {line['to']}" if line.get('to') != line['character'] and line.get('to') else ''
    place = ' out of the bank' if line['kind'] == 'bank' else ' from the bags'
    return place + purpose + mail


def deposit_text(row):
    """Shared Sell/Queue deposit wording, retaining measured zero and unknown."""
    value = row.get("deposit_copper")
    duration = row.get("post_duration_hours", 24)
    amount = format_money(value) if value is not None else "unknown"
    return f"deposit {amount} · lost if it expires: {amount} · refunded on a sale · {duration}h"


def headline_profit(row, sell):
    """Use the reserved Sell quote, falling back explicitly when it cannot be posted."""
    post = sell['undercut_batch_profit_copper']
    profit = row['batch_profit_copper'] if post is None else post
    return {'headline_profit_copper': profit, 'headline_per_craft_copper': profit // row['batch_size'],
            'profit_basis': ' at cautious sale price' if post is None else ''}


def gold_mail_lines(result, character_data, funds):
    """Suggest transfers from recorded surpluses; never change funding or the reserved plan."""
    balances = recorded_balances(character_data)
    # A saved character missing from this projection plans as Our team (resolve_funds), so mail follows.
    if funds.settings.character in character_data or funds.origin == 'entered amount' or len(balances) < 2:
        return []
    purchases = {}
    for row in result['craft']:
        maker = row.get('made_by')
        if maker:
            purchases[maker] = purchases.get(maker, 0) + sum(
                m['cost_copper'] for m in craft_details(row)['materials'] if m['method'] != 'held')
    available = {c[0]: gold - purchases.get(c[0], 0) for c, gold in balances.items()}
    lines = []
    for maker, cost in sorted(purchases.items()):
        if maker not in available:
            lines.append({'stage': 'gold unknown', 'name': maker, 'copper': cost})
            continue
        gap = max(0, -available[maker])
        donors = sorted(available, key=lambda name: (-available[name], name))
        for donor in donors:
            amount = min(gap, max(0, available[donor]))
            if amount:
                lines.append({'stage': 'gold mail', 'name': maker, 'character': donor, 'copper': amount})
                available[donor] -= amount
                gap -= amount
    return lines


def queue_with_gold(result, character_data, funds):
    """Presentation-only Queue with gold after all held-item transfers and before purchases."""
    queue = result['queue']
    lines = queue['lines']
    index = next((i for i, line in enumerate(lines) if line['stage'] not in ('take', 'mail')), len(lines))
    queue = queue | {'lines': deepcopy(lines[:index] + gold_mail_lines(result, character_data, funds) + lines[index:])}
    if not any(line.get('purposes') for line in queue['lines']):
        return queue
    steps = {}
    for number, stop in enumerate(route_stops(queue, result['craft'], character_data), 1):
        for entry in stop['lines']:
            line = entry['evidence']
            if line['stage'] == 'craft':
                steps.setdefault((line['catalog_id'], line['recipe_id']), number)
    for line in queue['lines']:
        targets = [steps[p['catalog_id'], p['recipe_id']] for p in line.get('purposes', [])
                   if (p['catalog_id'], p['recipe_id']) in steps]
        if targets:
            line['purpose_step'] = min(targets)
    return queue


PLAN_RESET = ("Scan, settings or catalog evidence changed: session choices and queue ticks reset. "
              "Previous choices were dropped, not resized; a fresh default plan is shown.")


def session_plan(arguments, state):
    """Pure session merge shared by both presentations; never mutate caller state."""
    state = deepcopy(state)
    context = plan_context(arguments)
    note = ''
    if state.get('context') != context:
        note = PLAN_RESET if state.get('choices') or any(state.get('ticks', {}).values()) else ''
        state = dict(context=context, choices=None, refill=True, rows=[], ticks={})
    result = build_today(**arguments, choices=state['choices'], refill=state['refill'])
    explain_drops(result, state)
    dropped = {(d['catalog_id'], d['recipe_id']) for d in result['dropped_choices']}
    for choice in state['choices'] or []:
        if (choice['catalog_id'], choice['recipe_id']) in dropped:
            choice['batch_size'] = None
    known = {(r['catalog_id'], r['recipe_id']) for r in state['rows']}
    new = [r for r in sorted(result['craft'], key=lambda r: r['plan_order'])
           if (r['catalog_id'], r['recipe_id']) not in known]
    state['rows'].extend(new)
    if state['choices'] is not None:
        state['choices'].extend({k: r[k] for k in ('catalog_id', 'recipe_id', 'batch_size')} for r in new)
    state['feasible_choices'] = [{k: row[k] for k in ('catalog_id', 'recipe_id', 'batch_size')}
                                 for row in result['craft']]
    return result, state, note


def explain_drops(result, state):
    """Distinguish a newly requested size from a previously feasible choice."""
    previous = {(r['catalog_id'], r['recipe_id'], r['batch_size'])
                for r in state.get('feasible_choices', state.get('rows', []))}
    limits = {(r['catalog_id'], r['recipe_id']): r['maximum'] for r in result['choice_limits']}
    for dropped in result['dropped_choices']:
        if not dropped['reason'].startswith('Choice is no longer feasible'):
            continue
        was_planned = (dropped['catalog_id'], dropped['recipe_id'], dropped['batch_size']) in previous
        reason = 'Choice is no longer feasible' if was_planned else 'Requested batch does not fit tonight'
        maximum = limits.get((dropped['catalog_id'], dropped['recipe_id']))
        if maximum is not None:
            reason += f'; at most {maximum} fit tonight'
        dropped['reason'] = reason + '; dropped, not resized.'


def queue_state(queue, state):
    """Ticks identify the complete displayed queue plus plan context, excluding confidence."""
    state = deepcopy(state)
    identity = digest({'queue': stable_queue(queue), 'context': state.get('context')})
    if state.get('queue_identity') != identity:
        state.update(queue_identity=identity, ticks={})
    return state


def route_stops(queue, crafts, character_data):
    """Consecutive stage/character/place groups retain every Queue line and its index."""
    stops = []
    posts = iter(crafts)
    for index, line in enumerate(queue['lines']):
        post = next(posts) if line['stage'] == 'post' else None
        character, place = route_place(line, crafts, character_data, post)
        identities = route_identities(line, crafts, character_data, post)
        key = (character, place, tuple(identities))
        if not stops or stops[-1]['key'] != key:
            stops.append(dict(key=key, stage=line['stage'], character=character,
                              characters=identities, place=place, lines=[]))
        stops[-1]['lines'].append(dict(index=index, text=queue_line(line), evidence=line))
    return stops


def route_place(line, crafts, character_data, post=None):
    stage = line['stage']
    character = line.get('character') or line.get('made_by')
    if stage == 'post':
        character = post.get('made_by') if post else None
    if stage == 'gold unknown':
        character = line['name']
    if stage in ('auction house', 'vendor'):
        makers = sorted({r['made_by'] for r in crafts if r.get('made_by') and any(
            p['item_id'] == line['item_id'] and (p['method'] == 'vendor') == (stage == 'vendor')
            for p in r['purchases'])})
        character = ', '.join(makers) or character
    character = character or 'Our team'
    places = {'take': line.get('kind', 'bags'), 'mail': 'bank' if line.get('kind') == 'bank' else 'mailbox',
              'gold mail': 'mailbox',
              'gold unknown': 'mailbox', 'auction house': 'auction house', 'vendor': 'vendor',
              'post': f"auction house · {line.get('post_duration_hours', 24)}h posts"}
    if stage != 'craft':
        return character, places[stage]
    profession = line.get('profession') or 'profession unknown'
    identities = route_identities(line, crafts, character_data, post)
    state = character_data.get(identities[0]) if len(identities) == 1 else None
    rank = recipe_rank(state, line['recipe_id']) if state else None
    return character, f"{profession} · rank {rank if rank is not None else 'unknown'}"


def route_identities(line, crafts, data, post=None):
    """Resolve explicit keys first; a display name never picks an arbitrary same-name character."""
    stage = line['stage']
    if stage in ('auction house', 'vendor'):
        rows = [r for r in crafts if any(p['item_id'] == line['item_id'] and
                (p['method'] == 'vendor') == (stage == 'vendor') for p in r['purchases'])]
    else:
        rows = [post or line]
    keys = set()
    for row in rows:
        explicit = row.get('made_by_key')
        name = row.get('character') or row.get('made_by') or (row.get('name') if stage == 'gold unknown' else None)
        if explicit and tuple(explicit) in data:
            keys.add(tuple(explicit))
        elif name:
            matches = [c for c in data if c[0] == name and
                       (not row.get('realm') or c[1:] == (row['realm'], row.get('faction'))) ]
            if len(matches) == 1:
                keys.add(matches[0])
    return sorted(keys)
