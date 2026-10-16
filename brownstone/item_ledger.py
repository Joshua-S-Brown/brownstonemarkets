"""Item-only journal interpretation and reconciliation (UI-16); no prices or UI imports."""
import json
import re
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from . import beta_evidence, ledger, sales
from .markets import scope_predicate
from .storage import has_table

ITEM_LEDGER_VERSION = 1
MATCH_SECONDS = 2
CASTS = {'UNIT_SPELLCAST_SUCCEEDED', 'C_TradeSkillUI.CraftRecipe'}
TAKES = {'TakeInboxItem', 'AutoLootMailItem'}
SELLS = {'SellCursorItem', 'C_MerchantFrame.SellAllJunkItems', 'UseContainerItem', 'C_Container.UseContainerItem'}


def load(config, db=None):
    """Read each scoped evidence table once, preserving the database's machine provenance."""
    if db is None:
        path = Path(config['data_dir']) / 'brownstone.duckdb'
        if not path.exists():
            return project([])
        with duckdb.connect(str(path), read_only=True) as connection:
            return load(config, connection)
    scope, params = scope_predicate(config)
    records, snapshots = [], []
    if has_table(db, 'character_journal'):
        records = [json.loads(raw) | {'machine': machine} for raw, machine in db.execute(
            f"SELECT record_json, machine FROM character_journal WHERE {scope} "
            "AND family IN ('bags','loot','craft','vendor','mail','auction')", params).fetchall()]
    if has_table(db, 'character_snapshots'):
        snapshots = [json.loads(raw) | {'machine': machine} for raw, machine in db.execute(
            f"SELECT record_json, machine FROM character_snapshots WHERE {scope} AND kind IN ('bags','bank')",
            params).fetchall()]
    return project(records, snapshots)


def _baseline(record, first):
    version = tuple(int(p) for p in record.get('addon_version', '999').split('.') if p.isdecimal())
    return bool(record.get('baseline_missing') or 'item_changes' not in record or (first and version <= (0, 10, 0)))


def project(records, snapshots=()):
    """Project scoped records without mutating the source; preserve one movement per entry/item."""
    records = list({r['entry_id']: r for r in records}.values())
    snapshots = list({r['snapshot_id']: r for r in snapshots}.values())
    groups = defaultdict(list)
    for r in records:
        groups[sales.character(r), r.get('machine'), r.get('login_at')].append(r)
    movements, gaps = [], []
    for rows in groups.values():
        new, missing = _session(sorted(rows, key=sales.order))
        movements.extend(new)
        gaps.extend(missing)
    movements.sort(key=lambda m: (m['at'], m['sequence'], m['entry_id'], m['item_id']))
    transfers = _transfers(movements, records + snapshots)
    reconciliation, unreadable = reconcile(movements, gaps, snapshots)
    return {'item_ledger_version': ITEM_LEDGER_VERSION, 'movements': movements, 'baselines': gaps,
            'totals': summarize(movements), 'team': team(movements), 'transfers': transfers,
            'reconciliation': reconciliation, 'unreadable_snapshots': unreadable}


def _near(before, after):
    return (after.get('login_at') is not None and sales.order(before) <= sales.order(after)
            and 0 <= after['captured_at'] - before['captured_at'] <= MATCH_SECONDS)


def _recent(rows, record, events):
    return next((r for r in reversed(rows) if r['event'] in events and _near(r, record)), None)


def _chat(record, history):
    text = record.get('arguments', {}).get('1', '')
    match = sales.LINK.search(text)
    if not match or not text.startswith('You '):  # other players' loot is not ours
        return None
    category = 'other'
    if text.startswith('You receive loot:'):
        category = 'gathered or looted'
    elif text.startswith('You create:') and _recent(history, record, CASTS):
        category = 'craft out'
    elif text.startswith('You receive item:') and _recent(history, record, {'BuyMerchantItem'}):
        category = 'vendor purchase'
    count = re.search(r'\|h\|rx(\d+)', text)
    return {'record': record, 'item_id': int(match[1]), 'remaining': int(count[1]) if count else 1,
            'category': category, 'reason': None, 'counterparty': None}


def _takes(record, inbox):
    args = record.get('arguments', {})
    index, slots = args.get('1'), [args.get('2', 1)]
    if record['event'] == 'AutoLootMailItem' and '2' not in args and type(index) is int and 0 < index <= len(inbox):
        # Auto-loot takes every attachment of the message, not only the first.
        slots = [a.get('index') for a in sales.values(inbox[index - 1].get('items'))] or slots
    return [_take(record, inbox, index, slot) for slot in slots]


def _take(record, inbox, index, slot):
    message = inbox[index - 1] if type(index) is int and 0 < index <= len(inbox) else None
    projected = sales.messages([record | {'inbox': {'messages': [message]}}]) if message else []
    items = sales.values(message.get('items')) if message else []
    attachment = next((a for a in items if a.get('index') == slot), None)
    link = sales.LINK.search(attachment.get('link', '')) if attachment else None
    count = attachment.get('info', {}).get('4') if attachment else None
    valid = bool(projected and link and type(count) is int and count > 0)
    category = 'mail in'
    if projected:
        mail = projected[0]
        if list(sales._returns(mail)):
            category = 'expired/cancelled return'
        elif mail['subject'].startswith('Auction won:'):
            category = 'auction purchase'
    if attachment:
        items.remove(attachment)
        message['items'] = items
        if not items and message.get('header', {}).get('5') == 0:
            inbox.pop(index - 1)
    return {'record': record, 'item_id': int(link[1]) if valid else None,
            'remaining': count if valid else None, 'category': category if valid else 'mail in (unidentified)',
            'counterparty': projected[0]['sender'] if projected else None,
            'reason': None if valid else 'Missing inbox index, attachment identity or count'}


def _inbox(record):
    inbox = deepcopy(sorted(sales.values(record['inbox'].get('messages')), key=lambda m: m.get('index', 0)))
    for message in inbox:
        # Lua serializes attachments with gaps as a table keyed by slot ({"7": ...}); keep that slot.
        items = message.get('items')
        slots = items.items() if isinstance(items, dict) else enumerate(items or [], 1)
        for slot, attachment in slots:
            if str(slot).isdecimal():
                attachment.setdefault('index', int(slot))
    return inbox


def _confirmed_posts(rows):
    orders = {r['entry_id']: sales.order(r) for r in rows}
    result = []
    for post in sales.posts(rows):
        if not post['confirmed']:
            continue
        # Locate the exact bag decrease already confirmed by sales, rather than spending
        # its quantity against another nearby decrease of this item.
        bag = next((r for r in rows if r['event'] == 'BAG_UPDATE_DELAYED'
                    and sales.order(r) > orders[post['entry_id']]
                    and len(r.get('item_changes', {})) == 1
                    and r.get('item_changes', {}).get(str(post['item_id'])) == -post['quantity']), None)
        if bag:
            result.append(post | {'bag_id': bag['entry_id']})
    return result


def _session(rows):
    history, pending, movements, gaps = [], [], [], []
    inbox = []
    bank, first, loading = False, True, None
    posts = _confirmed_posts(rows)
    for r in rows:
        if 'inbox' in r:
            inbox = _inbox(r)
        if r['event'] in {'BANKFRAME_OPENED', 'BANKFRAME_CLOSED'}:
            bank = r['event'] == 'BANKFRAME_OPENED'
        if r['event'] == 'CHAT_MSG_LOOT' and (chat := _chat(r, history)):
            pending.append(chat)
        if r['event'] in TAKES:
            pending.extend(_takes(r, inbox))
        if r['event'] != 'BAG_UPDATE_DELAYED':
            loading = None
        elif _baseline(r, first) or (loading is not None and r['captured_at'] - loading <= MATCH_SECONDS):
            # Bags keep loading just after a login baseline (beta: ammo, ore, stone already held).
            gaps.append(r)
            loading = r['captured_at'] if loading is None else loading
        else:
            movements.extend(_bag(r, history, pending, posts, bank))
        first = first and r['event'] != 'BAG_UPDATE_DELAYED'
        history.append(r)
    return movements, gaps


def _bag(record, history, pending, posts, bank):
    result = []
    for item, units in record['item_changes'].items():
        if not units:
            continue
        m = {'entry_id': record['entry_id'], 'at': record['captured_at'], 'sequence': sales.order(record)[1],
             'character': sales.character(record), 'machine': record.get('machine'), 'item_id': int(item),
             'units': units, 'parts': []}
        remaining = abs(units)
        remaining = (_allocate(m, record, pending, remaining) if units > 0
                     else _posted(m, record, posts, remaining))
        if remaining:
            category, counterparty = _fallback(record, history, units, bank)
            reason = None
            if units > 0 and any(_near(p['record'], record) and p['record']['event'] in TAKES for p in pending):
                category, reason = 'mail in (unidentified)', 'Inbox takes do not reconcile with this item change'
            m['parts'].append({'category': category, 'units': remaining if units > 0 else -remaining,
                               'counterparty': counterparty, 'reason': reason})
        result.append(m)
    return result


def _allocate(movement, record, pending, remaining):
    taking = any(p['record']['event'] in TAKES and _near(p['record'], record) for p in pending)
    for p in pending:
        if (not _near(p['record'], record) or p['item_id'] != movement['item_id'] or not p['remaining']
                or (taking and p['category'] == 'other')):
            continue
        # Partial evidence may allocate only its observed units, never invent the rest.
        if p['remaining'] > remaining:
            continue
        count = p['remaining']
        movement['parts'].append({k: p[k] for k in ('category', 'counterparty', 'reason')} | {'units': count})
        p['remaining'] -= count
        remaining -= count
        if not remaining:
            break
    return remaining


def _posted(movement, record, posts, remaining):
    for p in posts:
        if (p['item_id'] == movement['item_id'] and p['bag_id'] == record['entry_id']
                and 0 <= record['captured_at'] - p['at'] <= MATCH_SECONDS):
            count = min(remaining, p['quantity'])
            if count:
                movement['parts'].append({'category': 'post', 'units': -count, 'reason': None, 'counterparty': None})
                remaining -= count
                p['quantity'] -= count
    return remaining


def _fallback(record, history, units, bank):
    events = CASTS | SELLS | {'SendMail', 'MAIL_SEND_SUCCESS'} if units < 0 else set()
    hook = _recent(history, record, events)
    if hook:
        event = hook['event']
        if event in CASTS:
            return 'craft in', None
        if event in {'SendMail', 'MAIL_SEND_SUCCESS'}:
            send = _recent(history, record, {'SendMail'})
            return 'mail out', send.get('arguments', {}).get('1') if send else None
        if 'UseContainerItem' not in event or hook.get('windows', {}).get('merchant') is True:
            return 'vendor sale', None
    if bank and record.get('login_at') is not None:
        return ('to bank' if units < 0 else 'from bank'), None
    return 'other', None


def _own(name, character, known):
    # Mail recipients are typed and case-insensitive in game.
    first = (name or '').casefold().split()
    matches = [c for c in known if first and (c[0] or '').casefold() == first[0] and c[1] == character[1]]
    return matches[0] if len(matches) == 1 else None


def _mail_rows(movements, known):
    result = []
    for m in movements:
        groups = {}
        for part in m['parts']:
            if part['category'] not in {'mail in', 'mail out'}:
                continue
            own = _own(part['counterparty'], m['character'], known)
            if own:
                incoming = part['units'] > 0
                row = groups.setdefault((own, incoming), {
                    'movement': m, 'parts': [], 'units': 0, 'incoming': incoming,
                    'sender': own if incoming else m['character'], 'recipient': m['character'] if incoming else own})
                row['parts'].append(part)
                row['units'] += abs(part['units'])
        result.extend(groups.values())
    return result


def _transfers(movements, evidence):
    known = {sales.character(r) for r in evidence}
    rows = _mail_rows(movements, known)
    sends = [r for r in rows if not r['incoming']]
    receives = [r for r in rows if r['incoming']]
    result = []
    for send in list(sends):
        match = next((r for r in receives if _mail_match(send, r)), None)
        if match:
            sends.remove(send)
            receives.remove(match)
            result.append(_transfer_row([send], [match]))
    # Then one mail taken in several bag entries, or several mails taken in one, on summed counts.
    for side, others in ((sends, receives), (receives, sends)):
        for row in list(side):
            if run := _summed(row, others):
                side.remove(row)
                for other in run:
                    others.remove(other)
                result.append(_transfer_row(run, [row]) if row['incoming'] else _transfer_row([row], run))
    result.extend(_transfer_row([send], []) for send in sends)
    result.extend(_transfer_row([], [receive]) for receive in receives)
    return sorted(result, key=lambda t: (t['sent'] or t['received'])['at'])


def _in_order(send, receive):
    a, b = send['movement'], receive['movement']
    return (send['sender'] == receive['sender'] and send['recipient'] == receive['recipient']
            and a['item_id'] == b['item_id'] and a['at'] <= b['at'])


def _mail_match(send, receive):
    return _in_order(send, receive) and send['units'] == receive['units']


def _summed(row, others):
    """The earliest unmatched rows on the other side whose units sum exactly to this row's."""
    run, total = [], 0
    for other in others:
        if _in_order(*((other, row) if row['incoming'] else (row, other))) and total < row['units']:
            run.append(other)
            total += other['units']
    return run if len(run) > 1 and total == row['units'] else None


def _transfer_row(sends, receives):
    row = (sends or receives)[0]
    status = ('transfer' if sends and receives else 'sent, not yet received' if sends
              else 'received, no send recorded')
    if sends and receives:
        for part in (p for r in sends + receives for p in r['parts']):
            part['transfer'] = True
    return {'sender': row['sender'], 'recipient': row['recipient'], 'item_id': row['movement']['item_id'],
            'units': sum(r['units'] for r in sends or receives),
            'sent': sends[0]['movement'] if sends else None,
            'received': receives[-1]['movement'] if receives else None,
            'mails': len(sends), 'takes': len(receives), 'status': status}


def summarize(movements):
    totals = {}
    for m in movements:
        day = datetime.fromtimestamp(m['at'], UTC).date().isoformat()
        for p in m['parts']:
            key = m['character'], day, p['category']
            row = totals.setdefault(key, {'character': m['character'], 'day': day, 'category': p['category'],
                                          'in_units': 0, 'out_units': 0})
            row['in_units'] += max(0, p['units'])
            row['out_units'] += max(0, -p['units'])
    return sorted(totals.values(), key=lambda r: (r['character'], r['day'], r['category']))


def team(movements):
    parts = [p for m in movements for p in m['parts']
             if not p.get('transfer') and p['category'] not in {'to bank', 'from bank'}]
    return {'in_units': sum(max(0, p['units']) for p in parts),
            'out_units': sum(max(0, -p['units']) for p in parts)}


def _readable(record):
    inaccessible = record.get('kind') == 'bank' and any(
        c.get('container_id') == -1 and c.get('size') == 0 for c in sales.values(record.get('containers')))
    return not inaccessible and beta_evidence._inventory(record) is not None


def reconcile(movements, gaps, snapshots):
    groups = defaultdict(list)
    unreadable = 0
    for r in snapshots:
        if not _readable(r):
            unreadable += 1
        else:
            groups[sales.character(r), r['kind']].append(r)
    result = []
    for (char, kind), captures in groups.items():
        captures.sort(key=ledger._order)
        for before, after in zip(captures, captures[1:], strict=False):
            interval = [m for m in movements if m['character'] == char
                        and ledger._order(before) < (m['at'], m['sequence']) <= ledger._order(after)]
            recorded = _recorded(interval, kind)
            actual = beta_evidence.inventory_change(before, after)
            incomplete = any(sales.character(g) == char and ledger._order(before) < sales.order(g)
                             <= ledger._order(after) for g in gaps)
            result.append({'character': char, 'kind': kind, 'from': before['captured_at'], 'to': after['captured_at'],
                           'before_id': before['snapshot_id'], 'after_id': after['snapshot_id'],
                           'possibly_incomplete': incomplete, 'items': [
                               {'item_id': i, 'actual_units': actual[i], 'recorded_units': recorded[i],
                                'residual_units': actual[i] - recorded[i]}
                               for i in sorted(actual.keys() | recorded.keys())]})
    return result, unreadable


def _recorded(movements, kind):
    result: Counter = Counter()
    for m in movements:
        if kind == 'bags':
            result[m['item_id']] += m['units']
        else:
            result[m['item_id']] -= sum(p['units'] for p in m['parts'] if p['category'] in {'to bank', 'from bank'})
    return result
