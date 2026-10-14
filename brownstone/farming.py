"""Measured gathered-loot rates over already scoped character journal evidence (UI-13)."""
import re
from collections import defaultdict
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
    object_id = int(parts[5]) if kind == 'object' and len(parts) > 5 and parts[5].isdigit() else None
    return kind, object_id


def _match(record, windows):
    message = record.get('arguments', {}).get('1', record.get('arguments', {}).get(1, ''))
    item = item_id(message)
    for window in reversed(windows):
        for slot in window.get('loot_slots', []):
            if item is not None and item_id(slot.get('link')) == item:
                quantity = QUANTITY.search(message)
                kind, object_id = source(slot)
                return {'item_id': item, 'units': int(quantity[1]) if quantity else 1,
                        'time': record['captured_at'], 'zone': window.get('zone', {}),
                        'source_kind': kind, 'object_id': object_id, 'entry_id': record.get('entry_id')}
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
                 'qualifies': s['last'] - s['first'] >= 300 and len(s['loots']) >= 3} for s in result]


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
    return {'rows': rows, 'stretches': evidence, 'recorded_seconds': sum(s['seconds'] for s in evidence),
            'excluded_stretches': sum(not s['qualifies'] for s in evidence)}


def valued(history, sell_prices, signals, auction_cut):
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
    return history | {'rows': rows}
