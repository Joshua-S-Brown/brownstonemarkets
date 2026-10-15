"""Own auction outcomes (requirements UI-14); pure projection reusable by the ledger."""
import json
import re
from collections import defaultdict
from pathlib import Path

import duckdb

from .markets import scope_predicate
from .storage import has_table

POSTS = {'C_AuctionHouse.PostCommodity', 'C_AuctionHouse.PostItem'}
RETURN_PREFIXES = {'Auction expired: ': 'expired', 'Auction canceled: ': 'cancelled'}
DURATIONS = {1: 2, 2: 8, 3: 24}
LINK = re.compile(r'\|Hitem:(\d+):.*?\|h\[([^]]+)\]')


def values(table):
    return list(table.values()) if isinstance(table, dict) else table or []


def character(record):
    return tuple(record.get(k) for k in ('character', 'realm', 'faction'))


def order(record):
    suffix = record['entry_id'].rsplit(':', 1)[-1]
    return record['captured_at'], int(suffix) if suffix.isdecimal() else record.get('sequence', 0)


def load(config, db=None):
    """One journal read, with source/full market isolation and scoped scan name evidence."""
    if db is None:
        path = Path(config['data_dir']) / 'brownstone.duckdb'
        if not path.exists():
            return project([])
        with duckdb.connect(str(path), read_only=True) as connection:
            return load(config, connection)
    if not has_table(db, 'character_journal'):
        return project([])
    scope, params = scope_predicate(config)
    records = [json.loads(r[0]) for r in db.execute(
        f"SELECT record_json FROM character_journal WHERE {scope} AND family IN ('auction','bags','mail')",
        params).fetchall()]
    names = defaultdict(set)
    if has_table(db, 'market_snapshots'):
        for item, name in db.execute(f'SELECT DISTINCT item_id, item_name FROM market_snapshots WHERE {scope}',
                                     params).fetchall():
            if name:
                names[item].add(name)
    return project(records, names)


def _post(hook, following):
    args = _tuple(hook['arguments'])
    quantity = args.get('3', 0)
    unit = _unit_price(args, hook['event'].endswith('PostCommodity'))
    row = {'character': character(hook), 'entry_id': hook['entry_id'], 'at': hook['captured_at'],
           'quantity': quantity, 'duration_hours': DURATIONS.get(args.get('2')), 'item_id': None,
           'unit_copper': unit,
           'auction_id': None, 'confirmed': False, 'reason': 'missing creation or unique bag decrease'}
    created = [_tuple(r['arguments']).get('1') for r in following if r['event'] == 'AUCTION_HOUSE_AUCTION_CREATED']
    bags = [int(i) for r in following if r['event'] == 'BAG_UPDATE_DELAYED'
            and len(r.get('item_changes', {})) == 1
            for i, count in r['item_changes'].items() if count == -quantity]
    if any(r['event'] == 'AUCTION_HOUSE_SHOW_ERROR' for r in following):
        row['reason'] = 'auction house refused post'
    elif len(created) == 1 and bags and _positive(created[0]) and row['duration_hours'] and unit:
        row.update(item_id=bags[0], auction_id=created[0], confirmed=True, reason=None)
    return row


def posts(records):
    sessions = defaultdict(list)
    for r in records:
        sessions[character(r), r.get('login_at')].append(r)
    result = []
    for rows in sessions.values():
        rows.sort(key=order)
        starts = [i for i, r in enumerate(rows) if r['event'] in POSTS]
        for n, start in enumerate(starts):
            end = starts[n + 1] if n + 1 < len(starts) else len(rows)
            following = rows[start + 1:end] if rows[start].get('login_at') is not None else []
            result.append(_post(rows[start], following))
    return sorted(result, key=lambda r: (r['at'], r['entry_id']))


def _message(record, message):
    header, invoice = _tuple(message.get('header', {})), _tuple(message.get('invoice', {}))
    days = header.get('7')
    if not isinstance(days, (int, float)):
        return None
    attachments = [(m.group(1), m.group(2), _tuple(a.get('info', {})).get('4'))
                   for a in values(message.get('items')) if (m := LINK.search(a.get('link', '')))]
    # Buyer name and inbox position are mutable; only invoice contents establish identity.
    stable = {k: v for k, v in invoice.items() if k != '3'} if invoice.get('1') else None
    money = header.get('5')
    if money == 0 and invoice.get('1') == 'seller' and all(
            type(invoice.get(k)) is int for k in ('4', '6', '7')):
        money = invoice.get('4', 0) + invoice.get('6', 0) - invoice.get('7', 0)
    key = json.dumps([character(record), header.get('3'), header.get('4'), money,
                      stable, attachments], sort_keys=True)
    return key, {'character': character(record), 'entry_id': record['entry_id'],
                 'at': record['captured_at'] - (30 - days) * 86400,
                 'sender': header.get('3', ''), 'subject': header.get('4', ''),
                 'invoice': stable, 'attachments': attachments, 'observed_money': [header.get('5')]}


def messages(records):
    """Arrival clusters retain the maximum multiplicity in any single inbox observation."""
    known = defaultdict(list)
    result = []
    for record in sorted(records, key=order):
        used = set()
        for message in values(record.get('inbox', {}).get('messages')):
            parsed = _message(record, message)
            if parsed is None:
                continue
            key, row = parsed
            match = next((i for i in known[key] if i not in used and abs(result[i]['at'] - row['at']) <= 120), None)
            if match is None:
                match = len(result)
                known[key].append(match)
                result.append(row)
            result[match]['observed_money'] = list(dict.fromkeys(
                [*result[match]['observed_money'], *row['observed_money']]))
            used.add(match)
    return result


def _sale(message, confirmed, names):
    invoice = message['invoice']
    count, total, cut = (invoice.get(k) for k in ('11', '4', '7'))
    row = {k: message[k] for k in ('character', 'entry_id', 'at')}
    row.update(gross_copper=total, cut_copper=cut, deposit_copper=invoice.get('6'),
               observed_money=message['observed_money'])
    row.update(kind='sold', quantity=count, net_copper=None, item_id=None, reason='invalid invoice units or copper')
    if not all(type(v) is int for v in (count, total, cut)) or count <= 0 or total <= 0 or not 0 <= cut <= total:
        return row
    row['net_copper'] = total - cut
    matches = {p['item_id'] for p in confirmed if p['character'] == message['character']
               and total == p['unit_copper'] * count
               and 0 <= message['at'] - p['at'] <= (p['duration_hours'] + 1) * 3600
               and invoice.get('2') in names.get(p['item_id'], set())}
    row.update(item_id=next(iter(matches)) if len(matches) == 1 else None,
               reason=None if len(matches) == 1 else 'no matching item' if not matches else 'multiple matching items')
    return row


def project(records, names=None):
    """Project already scoped records; no I/O, prices and net amounts remain integer copper."""
    names = {i: set(n) for i, n in (names or {}).items()}
    attempts = posts(records)
    mail = messages(records)
    _link_names(records, names)
    outcomes = []
    confirmed = [p for p in attempts if p['confirmed']]
    for m in mail:
        if m['invoice']:
            if m['invoice'].get('1') == 'seller':
                outcomes.append(_sale(m, confirmed, names))
        elif 'Auction House' in m['sender']:
            outcomes.extend(_returns(m))
    totals = _totals(confirmed, outcomes)
    return {'posts': attempts, 'outcomes': outcomes, 'items': totals,
            'unidentified': sum(o['kind'] == 'sold' and o['item_id'] is None for o in outcomes)}


def _returns(message):
    for prefix, kind in RETURN_PREFIXES.items():
        if message['subject'].startswith(prefix):
            for item, _, count in message['attachments']:
                if type(count) is int and count > 0:
                    yield {k: message[k] for k in ('character', 'entry_id', 'at')} | {
                        'kind': kind, 'item_id': int(item), 'quantity': count, 'reason': None}


def _totals(confirmed, outcomes):
    totals = {}
    for event in [*confirmed, *sorted(outcomes, key=lambda o: (o['at'], o['entry_id']))]:
        if event['item_id'] is None:
            continue
        key = event['character'], event['item_id']
        row = totals.setdefault(key, {'character': event['character'], 'item_id': event['item_id'],
                                     'posted': 0, 'sold': 0, 'expired': 0, 'cancelled': 0,
                                     'net_copper': 0, 'newest_sale': None, 'expiry_run': 0})
        kind = event.get('kind', 'posted')
        row[kind] += event['quantity']
        if kind == 'sold':
            row.update(net_copper=row['net_copper'] + event['net_copper'], newest_sale=event['at'], expiry_run=0)
        elif kind in ('expired', 'cancelled'):
            row['expiry_run'] += 1
    for row in totals.values():
        row['resolved'] = row['sold'] + row['expired'] + row['cancelled']
        row['average_copper'] = row['net_copper'] // row['sold'] if row['sold'] else None
    return list(totals.values())


def combined(data, item_id, selected=None):
    rows = [r for r in (data or {}).get('items', []) if r['item_id'] == item_id
            and (selected is None or r['character'] == selected)]
    sold = sum(r['sold'] for r in rows)
    return {'sold': sold, 'resolved': sum(r['resolved'] for r in rows),
            'average_copper': sum(r['net_copper'] for r in rows) // sold if sold else None,
            'expiry_run': max((r['expiry_run'] for r in rows), default=0)}


def _link_names(value, names):
    if isinstance(value, str):
        for match in LINK.finditer(value):
            names.setdefault(int(match.group(1)), set()).add(match.group(2))
    elif isinstance(value, (list, dict)):
        for child in values(value):
            _link_names(child, names)


def _tuple(table):
    """Raw Lua numeric keys and their persisted JSON spelling have the same tuple positions."""
    return {str(k): v for k, v in table.items()}


def _positive(value):
    return type(value) is int and value > 0


def _unit_price(args, commodity):
    quantity, price = args.get('3'), args.get('4' if commodity else '5')
    if not _positive(quantity) or not _positive(price):
        return None
    divisor = 1 if commodity else quantity
    return price // divisor if price % divisor == 0 else None
