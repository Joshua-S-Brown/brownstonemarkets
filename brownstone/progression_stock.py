"""Holdings and listing reservations for the team's independent reach walks (CRAFT-11)."""
from fractions import Fraction
from math import ceil

from . import farming, today_holdings
from .money import after_cut
from .today import Ladder


def reach_supplies(evidence, data, listings, now, max_age_hours, auction_cut, idle_minutes=10, cell_percent=5):
    """One mutable pool for a composition, separate from Today's funded plan and synthetic hires."""
    _, captures, units = today_holdings.scoped(evidence, None)
    rates = {}
    for character, state in sorted(data.items()):
        for row in farming.history(state.get('observations', []), idle_minutes, cell_percent)['rows']:
            item = row['item_id']
            if row['units_per_hour'] > rates.get(item, {}).get('units_per_hour', 0):
                rates[item] = row | {'character': character}
    return {'pool': [dict(u) for u in units], 'bought': {}, 'reserved': {}, 'rates': rates,
            'ladders': {i: Ladder(rows) for i, rows in (listings or {}).items()}, 'auction_cut': auction_cut,
            'at_least': not captures or any(c['unknown'] or c.get('partial', False) or c['age_hours'] is None
                                           or not 0 <= c['age_hours'] <= max_age_hours for c in captures)}


def cash_step(catalog, result, crafts, supplies, character, prices):
    """Try one candidate against copies; only the chosen candidate spends the shared supplies."""
    trial = supplies | {'pool': [dict(u) for u in supplies['pool']],
                        'bought': dict(supplies['bought']), 'reserved': dict(supplies['reserved'])}
    cash = Fraction(0)
    needs, materials = held_intermediates(catalog, result, crafts, trial, character, prices)
    for choice in result['shopping_choices']:
        item = choice['item_id']
        quantity = needs[choice['item_id']]
        held = today_holdings._allocate(item, quantity, character[0], trial['pool'])
        short = quantity - sum(u['units'] for u in held)
        cost, purchased = purchase(choice, short, trial, catalog['items_by_id'][item]['name'])
        cash += cost
        materials.append(choice | {'item_name': catalog['items_by_id'][item]['name'],
                                   'quantity': float(quantity),
                                   'held': [u | {'units': float(u['units']), 'expected_units': str(u['units']),
                                                 'mail': u['character'] != character[0]} for u in held],
                                   'unit_worth_copper': supplies.get('worth_prices', prices).get(item),
                                   'buy_quantity': float(short),
                                   'buy_expected_units': str(short),
                                   'purchased_units': purchased,
                                   'cash_cost_copper': ceil(cash) - sum(m['cash_cost_copper'] for m in materials),
                                   'farm': trial['rates'].get(item), 'at_least': trial['at_least'],
                                   'auction_cut': trial['auction_cut']})
    return {'cost_copper': sum(m['cash_cost_copper'] for m in materials), 'materials': materials,
            'auction_cut': trial['auction_cut'], '_supplies': trial}


def purchase(choice, quantity, supplies, name):
    """Carry whole-listing surplus forward, including fractional yellow expectations."""
    item = choice['item_id']
    surplus = min(quantity, supplies['bought'].get(item, 0))
    quantity -= surplus
    supplies['bought'][item] = supplies['bought'].get(item, 0) - surplus
    if not quantity:
        return 0, 0
    if not choice['unit_cost_copper']:
        raise ValueError(f'has no price for {name}')
    if choice['method'] == 'vendor':
        return quantity * choice['unit_cost_copper'], float(quantity)
    ladder = supplies['ladders'].get(item)
    quote = ladder.quote(ceil(quantity), supplies['reserved'].get(item, 0)) if ladder else None
    if quote is None:
        raise ValueError(f'insufficient listings for {name}: need {ceil(quantity)} more units')
    supplies['reserved'][item] = quote['end']
    supplies['bought'][item] += quote['purchased_units'] - quantity
    return quote['cost_copper'], quote['purchased_units']


def summarize(steps, auction_cut):
    """Aggregate the selected prefix, so held worth and farm time never become cash cost."""
    held, buys = {}, {}
    for step in steps:
        for material in step.get('materials', []):
            for unit in material['held']:
                key = (material['item_id'], unit['character'], unit['realm'], unit['faction'], unit['kind'])
                row = held.setdefault(key, unit | {'units': Fraction(0), 'item_name': material['item_name'],
                                                  'unit_worth_copper': material['unit_worth_copper']})
                row['units'] += Fraction(unit['expected_units'])
            if material['buy_quantity'] and material['method'] == 'buy':
                row = buys.setdefault(material['item_id'], {'item_id': material['item_id'],
                    'item_name': material['item_name'], 'quantity': Fraction(0),
                    'purchased_units': 0, 'farm': material['farm']})
                row['quantity'] += Fraction(material['buy_expected_units'])
                row['purchased_units'] += material['purchased_units']
    for row in held.values():
        price = row.pop('unit_worth_copper')
        row['worth_copper'] = after_cut(price, row['units'], auction_cut) if price else None
        row.pop('expected_units', None)
        row['units'] = float(row['units'])
    for row in buys.values():
        rate = row['farm']
        row['farm_hours'] = ceil(row['quantity'] * 10 / rate['units_per_hour']) / 10 if rate else None
        row['quantity'] = float(row['quantity'])
    return {'held': list(held.values()), 'buy': list(buys.values()),
            'holdings_at_least': any(m['at_least'] for s in steps for m in s.get('materials', []))}


def held_intermediates(catalog, result, crafts, supplies, character, prices):
    """Use captured intermediates before their retained leaf subtree, in whole route multiples."""
    needs = {c['item_id']: c['quantity'] * crafts for c in result['shopping_choices']}
    materials, parents = [], []
    for step in today_holdings.route_evidence(catalog, prices, result):
        while parents and parents[-1][0] >= step['depth']:
            parents.pop()
        scale = parents[-1][1] if parents else crafts
        quantity = step['quantity'] * scale
        available = sum(u['units'] for u in supplies['pool'] if u['item_id'] == step['item_id'])
        use = min(quantity, available) // step['holding_multiple'] * step['holding_multiple']
        held = today_holdings._allocate(step['item_id'], use, character[0], supplies['pool'])
        for item, units in step['leaves'].items():
            needs[item] -= use * units
        parents.append((step['depth'], (quantity - use) / step['quantity']))
        if held:
            materials.append({'item_id': step['item_id'], 'item_name': catalog['items_by_id'][step['item_id']]['name'],
                'method': 'held', 'quantity': float(use), 'buy_quantity': 0, 'cash_cost_copper': 0,
                'total_cost_copper': 0, 'unit_worth_copper': supplies.get('worth_prices', prices).get(step['item_id']),
                'held': [u | {'units': float(u['units']), 'expected_units': str(u['units']),
                              'mail': u['character'] != character[0]} for u in held],
                'at_least': supplies['at_least'], 'auction_cut': supplies['auction_cut']})
    return needs, materials
