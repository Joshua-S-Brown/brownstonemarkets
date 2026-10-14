"""Measured gathered-loot rates over already scoped character journal evidence (UI-13)."""
import re
from collections import Counter, defaultdict
from fractions import Fraction

ITEM = re.compile(r'\|Hitem:(\d+)')
QUANTITY = re.compile(r'\|h(?:\|r)?\s*x(\d+)\s*[.!]?\s*$')


def item_id(link):
    match = ITEM.search(link) if isinstance(link, str) else None
    return int(match[1]) if match and int(match[1]) > 0 else None


def source(slot):
    guid = slot.get('sources', {}).get('1', slot.get('sources', {}).get(1, ''))
    parts = guid.split('-') if isinstance(guid, str) else []
    kind = {'Creature': 'mob', 'GameObject': 'object'}.get(parts[0] if parts else '', 'unknown')
    identity = int(parts[5]) if kind in ('mob', 'object') and len(parts) > 5 and parts[5].isdigit() else None
    return kind, identity if kind == 'object' or (identity and identity > 0) else None


def _match(record, windows):
    message = record.get('arguments', {}).get('1', record.get('arguments', {}).get(1, ''))
    item = item_id(message)
    for window in reversed(windows):
        for slot in window.get('loot_slots', []):
            if item is not None and item_id(slot.get('link')) == item:
                quantity = QUANTITY.search(message)
                kind, identity = source(slot)
                return {'item_id': item, 'units': int(quantity[1]) if quantity else 1,
                        'time': record['captured_at'], 'zone': window.get('zone', {}),
                        'source_kind': kind, 'object_id': identity if kind == 'object' else None,
                        'npc_id': identity if kind == 'mob' else None,
                        'window_id': (window.get('captured_at'), window.get('sequence'), window.get('entry_id')),
                        'entry_id': record.get('entry_id')}
    return None


def gathered(observations):
    """Only matching loot windows establish gathering; flags and message names have no role."""
    windows: dict[tuple, list] = defaultdict(list)
    seen = set()
    result = []
    ordered = sorted(observations, key=lambda pair: (pair[0].get('captured_at', -1),
                                                    pair[0].get('sequence', -1)))
    for record, machine in ordered:
        entry = record.get('entry_id')
        if entry is not None and entry in seen:
            continue
        seen.add(entry)
        key = (machine, record.get('login_at'))
        moment = record.get('captured_at')
        if type(moment) is not int:
            continue
        windows[key] = [w for w in windows[key] if 0 <= moment - w['captured_at'] <= 5]
        event = record.get('event')
        if event == 'LOOT_OPENED':
            windows[key].append(record)
        elif event in ('TakeInboxItem', 'AutoLootMailItem') or record.get('family') in ('craft', 'vendor', 'trade'):
            windows[key].clear()
        elif event == 'CHAT_MSG_LOOT':
            loot = _match(record, windows[key])
            if loot is not None:
                result.append(loot | {'machine': machine, 'login_at': record.get('login_at')})
    return result


def stretches(loots, idle_minutes=10):
    result = []
    for loot in loots:
        key = (loot['zone'].get('map_id'), loot['machine'], loot['login_at'])
        if not result or key[0] != result[-1]['key'][0] or loot['time'] - result[-1]['last'] > idle_minutes * 60:
            result.append({'key': key, 'first': loot['time'], 'last': loot['time'], 'loots': []})
        result[-1]['last'] = loot['time']
        result[-1]['loots'].append(loot)
    return [s | {'seconds': s['last'] - s['first'],
                 'qualifies': s['last'] - s['first'] >= 300 and len(s['loots']) >= 3,
                 **_spot(s['loots'])} for s in result]


def history(observations, idle_minutes=10):
    evidence = stretches(gathered(observations), idle_minutes)
    # A rate rests on all qualifying time in its zone, including stretches where the item never dropped.
    time: dict = defaultdict(lambda: [0, 0])
    totals: dict[tuple, dict] = {}
    for stretch in filter(lambda s: s['qualifies'], evidence):
        time[stretch['key'][0]][0] += stretch['seconds']
        time[stretch['key'][0]][1] += 1
        for loot in stretch['loots']:
            key = loot['item_id'], loot['zone'].get('map_id'), loot['source_kind']
            row = totals.setdefault(key, {'item_id': key[0], 'map_id': key[1], 'source_kind': key[2],
                                         'zone': loot['zone'].get('zone'), 'units': 0, 'object_ids': set()})
            row['units'] += loot['units']
            if loot['object_id'] is not None:
                row['object_ids'].add(loot['object_id'])
    rows = [r | {'seconds': time[r['map_id']][0], 'stretches': time[r['map_id']][1],
                 'units_per_hour': r['units'] * 3600 // time[r['map_id']][0], 'object_ids': sorted(r['object_ids'])}
            for r in totals.values()]
    return {'rows': rows, 'spots': _spots(evidence), 'stretches': evidence,
            'recorded_seconds': sum(s['seconds'] for s in evidence),
            'excluded_stretches': sum(not s['qualifies'] for s in evidence)}


def valued(history, sell_prices, signals, auction_cut, vendor_prices=None):
    """Integer copper at cautious listings after the cut, with UI-11 typical unit price beside it."""
    from .session_options import base_signal

    rows = []
    for row in history['rows']:
        price = sell_prices.get(row['item_id'])
        price = price if price is not None and price > 0 else None
        signal = base_signal(signals, row['item_id'])
        typical = signal['overshoot'].get('typical_copper') if signal else None
        value = int(row['units_per_hour'] * price * (1 - Fraction(str(auction_cut)))) if price else None
        rows.append(row | {'item_name': signal.get('item_name') if signal else None, 'sell_price_copper': price,
                           'value_per_hour_copper': value,
                           'typical_price_copper': typical})
    rows.sort(key=lambda r: (r['value_per_hour_copper'] is None, -(r['value_per_hour_copper'] or 0),
                             r['item_id'], str(r['map_id']), r['source_kind']))
    spots = [_value_spot(spot, sell_prices, vendor_prices or {}, auction_cut) for spot in history.get('spots', [])]
    spots.sort(key=lambda r: (r['value_per_hour_copper'] is None, -(r['value_per_hour_copper'] or 0),
                              str(r['map_id']), r['npc_id'] or 0))
    return history | {'rows': rows, 'spots': spots}


def _spot(loots):
    """One vote per creature loot window, even when several messages or items match it."""
    windows = {(r['machine'], r['login_at'], r['window_id'], r['npc_id'])
               for r in loots if r['npc_id'] is not None}
    counts = Counter(w[-1] for w in windows)
    dominant = min(counts, key=lambda npc: (-counts[npc], npc)) if counts else None
    return {'npc_id': dominant, 'also_looted': sorted(npc for npc in counts if npc != dominant)}


def _spots(evidence):
    spots: dict[tuple, dict] = {}
    for stretch in evidence:
        if not stretch['qualifies']:
            continue
        key = stretch['key'][0], stretch['npc_id']
        row = spots.setdefault(key, {'map_id': key[0], 'npc_id': key[1],
                                    'zone': stretch['loots'][0]['zone'].get('zone'),
                                    'seconds': 0, 'stretches': 0, 'items': {}, 'also_looted': set()})
        row['seconds'] += stretch['seconds']
        row['stretches'] += 1
        row['also_looted'].update(stretch['also_looted'])
        for loot in stretch['loots']:
            row['items'][loot['item_id']] = row['items'].get(loot['item_id'], 0) + loot['units']
    return [r | {'also_looted': sorted(r['also_looted'])} for r in spots.values()]


def _spot_item(item, units, sell_prices, vendor_prices, cut):
    price = sell_prices.get(item)
    vendor = vendor_prices.get(item)
    if price is not None and price > 0:
        return {'item_id': item, 'units': units, 'basis': 'auction', 'unit_copper': price,
                'value_copper': int(units * price * (1 - cut))}
    if vendor is not None and vendor > 0:
        return {'item_id': item, 'units': units, 'basis': 'vendor', 'unit_copper': vendor,
                'value_copper': units * vendor}
    return {'item_id': item, 'units': units, 'basis': 'no price', 'unit_copper': None, 'value_copper': None}


def _value_spot(spot, sell_prices, vendor_prices, auction_cut):
    items = [_spot_item(item, units, sell_prices, vendor_prices, Fraction(str(auction_cut)))
             for item, units in sorted(spot['items'].items())]
    auction = sum(r['value_copper'] for r in items if r['basis'] == 'auction')
    vendor = sum(r['value_copper'] for r in items if r['basis'] == 'vendor')
    known = any(r['value_copper'] is not None for r in items)
    total = auction + vendor if known else None
    return spot | {'items': items, 'auction_value_copper': auction, 'vendor_value_copper': vendor,
                   'coin_copper': None, 'value_copper': total,
                   'no_price_items': sum(r['basis'] == 'no price' for r in items),
                   'no_price_units': sum(r['units'] for r in items if r['basis'] == 'no price'),
                   'value_per_hour_copper': total * 3600 // spot['seconds'] if total is not None else None}
