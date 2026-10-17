"""Pure allocation along the Board's retained route; captured Stock evidence is supplied as data."""
from math import gcd, lcm

from .crafting import unit_route


def route_evidence(catalog, prices, row):
    steps = []
    for index, step in enumerate(row['intermediate_steps']):
        multiple = _whole_multiple(step, row['intermediate_steps'][index + 1:])
        cost, _, leaves = unit_route(catalog, prices, step['item_id'], (row['recipe_id'],))
        steps.append({**step, 'unit_cost_copper': cost, 'leaves': leaves, 'holding_multiple': multiple})
    return steps


def consumers(catalog, row):
    """Who uses each direct input: a cross-profession step's maker, otherwise the row's crafter (None).

    An item used by more than one person stays with the crafter, as before.
    """
    users = {}
    for item in catalog['recipes_by_id'][row['recipe_id']]['inputs']:
        users.setdefault(item['item_id'], set()).add(None)
    for step in row['intermediate_steps']:
        other = step.get('catalog_id', row['catalog_id']) != row['catalog_id']
        for item in catalog['recipes_by_id'][step['recipe_id']]['inputs']:
            users.setdefault(item['item_id'], set()).add(step.get('made_by') if other else None)
    return {item: next(iter(makers)) for item, makers in users.items() if len(makers) == 1 and None not in makers}


def _whole_multiple(step, following):
    """Replacing a parent must leave whole executions throughout its retained subtree (CRAFT-02)."""
    multiple = step['quantity'] // step['crafts']
    for child in following:
        if child['depth'] <= step['depth']:
            break
        multiple = lcm(multiple, step['quantity'] // gcd(step['quantity'], child['crafts']))
    return multiple


def scoped(evidence, character):
    if not evidence:
        return {}, [], []
    _, _, captures, units = evidence
    def selected(r):
        return character is None or (r['character'], r['realm'], r['faction']) == character
    captures = [r for r in captures if selected(r)]
    units = [r for r in units if selected(r) and r['key'][2] == 'base']
    totals = {}
    for unit in units:
        totals[unit['item_id']] = totals.get(unit['item_id'], 0) + unit['units']
    return totals, captures, units


def requirements(row, batch, remaining):
    """Reduce parents before descendants; holding an intermediate replaces its entire leaf subtree."""
    needs = {c['item_id']: c['quantity'] * batch for c in row['shopping_choices']}
    available, held, steps, parents = dict(remaining), [], [], []
    for step in row.get('holding_steps', []):
        while parents and parents[-1][0] >= step['depth']:
            parents.pop()
        scale_num, scale_den = parents[-1][1:] if parents else (batch, 1)
        quantity = step['quantity'] * scale_num // scale_den
        yield_units = step['quantity'] // step['crafts']
        multiple = step['holding_multiple']
        use = min(quantity, available.get(step['item_id'], 0)) // multiple * multiple
        _consume(step, use, available, held)
        for item, units in step['leaves'].items():
            needs[item] -= use * units
        left = quantity - use
        steps.append({**step, 'quantity': left, 'crafts': left // yield_units})
        parents.append((step['depth'], left, step['quantity']))
    for choice in row['shopping_choices']:
        item = choice['item_id']
        use = min(needs[item], available.get(item, 0))
        _consume(choice, use, available, held)
        needs[item] -= use
    return needs, held, steps


def _consume(choice, quantity, available, held):
    if not quantity:
        return
    item = choice['item_id']
    available[item] -= quantity
    held.append({**choice, 'method': 'held', 'quantity': quantity, 'purchased_units': quantity,
                 'highest_unit_copper': choice['held_unit_copper'],
                 'cost_copper': choice['held_unit_copper'] * quantity, 'end': 0})


def gold_cost(purchases):
    return sum(p['cost_copper'] for p in purchases if p['method'] != 'held')


def allocate(crafts, units, captures, max_age_hours):
    """Resolve reserved counts to people and places only after the funded plan has been chosen."""
    pool = [dict(u) for u in units]
    for row in sorted(crafts, key=lambda r: r['plan_order']):
        allocations = []
        for purchase in row['purchases']:
            if purchase['method'] == 'held':
                to = row.get('holding_consumers', {}).get(purchase['item_id'], row.get('made_by'))
                allocations.extend({**a, 'to': to} for a in _allocate(purchase['item_id'], purchase['quantity'],
                                                                        to, pool))
        row['held_allocations'] = allocations
    for row in sorted(crafts, key=lambda r: r['plan_order']):
        output = row['output_item_id']
        row['held_outputs'] = _allocate(output, sum(u['units'] for u in pool if u['item_id'] == output),
                                        row.get('made_by'), pool)
        _stale_reason(row, captures, max_age_hours)


def _stale_reason(row, captures, max_age_hours):
    used = {(u['character'], u['realm'], u['faction'], u['kind'])
            for u in [*row['held_allocations'], *row['held_outputs']]}
    stale = any(c['age_hours'] is not None and c['age_hours'] > max_age_hours
                for c in captures if (c['character'], c['realm'], c['faction'], c['kind']) in used)
    if stale:
        row['confidence_reasons'].append('held count from a stale capture')


def _allocate(item, quantity, maker, pool):
    rows = sorted((u for u in pool if u['item_id'] == item),
                  key=lambda u: (u['character'] != maker, u['character'], u['kind'] != 'bags'))
    result = []
    for unit in rows:
        take = min(quantity, unit['units'])
        if take:
            result.append({**unit, 'units': take})
            unit['units'] -= take
            quantity -= take
    return result


def queue_lines(crafts):
    """Keep allocated output purposes on real held-material actions."""
    lines = []
    for row in sorted(crafts, key=lambda r: r['plan_order']):
        purpose = {'catalog_id': row['catalog_id'], 'recipe_id': row['recipe_id'], 'name': row['output_name']}
        for allocation in row.get('held_allocations', []):
            other = allocation['to'] and allocation['character'] != allocation['to']
            # Bags need no step for a known crafter; with no crafter, say where the units are.
            take = allocation['kind'] == 'bank' or not allocation['to']
            stages = (['take'] if take else []) + (['mail'] if other else [])
            for stage in stages:
                lines.append({**allocation, 'stage': stage, 'name': row['material_names'][allocation['item_id']],
                              'purposes': [purpose]})
    grouped = {}
    for line in lines:
        key = (line['stage'], line['character'], line['kind'], line['item_id'], line['to'])
        if key in grouped:
            grouped[key]['units'] += line['units']
            for purpose in line['purposes']:
                if purpose not in grouped[key]['purposes']:
                    grouped[key]['purposes'].append(purpose)
        else:
            grouped[key] = dict(line)
    order = list(dict.fromkeys(line['character'] for line in lines))
    # Bank mail follows its withdrawal in that bank stop; bags mail shares a mailbox.
    return sorted(grouped.values(), key=lambda line: (order.index(line['character']),
                  line['kind'] != 'bags', line['item_id'], line['stage'] != 'take'))


def own_bags(row, maker):
    return [{'units': a['units'], 'name': row['material_names'][a['item_id']]}
            for a in row.get('held_allocations', [])
            if a['kind'] == 'bags' and a['character'] == a['to'] and a['to'] == maker]
