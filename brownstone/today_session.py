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
        place = 'bank' if line['kind'] == 'bank' else 'bags'
        return f"{line['character']}: take {line['units']} {name} from the {place}"
    if stage == 'mail':
        return f"{line['character']} mails {line['units']} {name} to {line['to']}"
    if stage == "craft":
        maker = f" · {made_by_label(line)}" if line.get("profession") else ""
        return (f"Craft: {name}{maker} · recipe {line['recipe_id']} ({line['catalog_id']}) · "
                f"{line['batch_size']} crafts")
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
    return queue | {'lines': lines[:index] + gold_mail_lines(result, character_data, funds) + lines[index:]}


PLAN_RESET = ("Scan, settings or catalog evidence changed: session choices and queue ticks reset. "
              "Previous choices were dropped, not resized; a fresh default plan is shown.")


def session_plan(arguments, state):
    """Pure session merge shared by both presentations; never mutate caller state."""
    state = deepcopy(state)
    context = plan_context(arguments)
    note = ''
    if state.get('context') != context:
        note = PLAN_RESET if state else ''
        state = dict(context=context, choices=None, refill=True, rows=[], ticks={})
    result = build_today(**arguments, choices=state['choices'], refill=state['refill'])
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
    return result, state, note


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
        character, place = route_place(line, crafts, character_data, next(posts) if line['stage'] == 'post' else None)
        key = (line['stage'], character, place)
        if not stops or stops[-1]['key'] != key:
            stops.append(dict(key=key, stage=line['stage'], character=character, place=place, lines=[]))
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
    places = {'take': line.get('kind', 'bags'), 'mail': 'mailbox', 'gold mail': 'mailbox',
              'gold unknown': 'mailbox', 'auction house': 'auction house', 'vendor': 'vendor',
              'post': f"auction house · {line.get('post_duration_hours', 24)}h posts"}
    if stage != 'craft':
        return character, places[stage]
    profession = line.get('profession') or 'profession unknown'
    state = next((data for c, data in character_data.items() if c[0] == character), None)
    rank = recipe_rank(state, line['recipe_id']) if state else None
    return character, f"{profession} · rank {rank if rank is not None else 'unknown'}"
