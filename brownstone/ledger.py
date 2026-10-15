"""Gold evidence and reconciliation (UI-15), independent of prices and UI frameworks."""
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from . import character_snapshots, farming, sales
from .markets import scope_predicate
from .storage import has_table

LEDGER_VERSION = 1
MATCH_SECONDS = 1
HOOKS = {
    'BuyMerchantItem': ('vendor purchase', -1), 'RepairAllItems': ('repairs', -1),
    'BuyTrainerService': ('training', -1), 'C_MerchantFrame.SellAllJunkItems': ('vendor sale', 1),
    'C_Container.UseContainerItem': ('vendor sale', 1), 'UseContainerItem': ('vendor sale', 1),
    'SellCursorItem': ('vendor sale', 1), 'SendMail': ('mail out', -1),
    'AUCTION_HOUSE_PURCHASE_COMPLETED': ('auction purchase', -1),
    **{k: ('auction deposit', -1) for k in sales.POSTS | {'StartAuction', 'PostAuction'}},
}


def load(config, db=None):
    """One scoped journal read and one scoped bags read; never opens a writable database."""
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
            "AND family IN ('money','vendor','auction','mail','loot')", params).fetchall()]
    if has_table(db, 'character_snapshots'):
        snapshots = [json.loads(raw) for (raw,) in db.execute(
            f"SELECT record_json FROM character_snapshots WHERE {scope} AND kind = 'bags'", params).fetchall()]
    return project(records, snapshots)


def _valid(record):
    return all(type(record.get(k)) is int for k in ('before_copper', 'after_copper'))


def _order(record):
    return sales.order(record) if 'entry_id' in record else (record['captured_at'], record.get('sequence', 0))


def project(records, snapshots=()):
    """Project already scoped evidence; one movement can have invoice allocation parts."""
    unique = {r['entry_id']: r for r in records}
    groups = defaultdict(list)
    for r in unique.values():
        groups[sales.character(r), r.get('machine'), r.get('login_at')].append(r)
    movements = []
    for rows in groups.values():
        movements.extend(_session(sorted(rows, key=sales.order)))
    movements.sort(key=lambda m: (m['at'], m['sequence'], m['entry_id']))
    excluded = sum(r['event'] == 'PLAYER_MONEY' and not _valid(r) for r in unique.values())
    reconciled, unreadable = reconcile(list(unique.values()), snapshots)
    totals = summarize(movements)
    return {'ledger_version': LEDGER_VERSION, 'movements': movements, 'totals': totals,
            'team': {'in_copper': sum(r['in_copper'] for r in totals),
                     'out_copper': sum(r['out_copper'] for r in totals)},
            'excluded_money': excluded, 'unreadable_snapshots': unreadable, 'reconciliation': reconciled}


def _session(rows):
    movements, pending = [], []
    inbox = []
    hook = None
    # Reuse farming's exact coin matching, including its five-second and interference rules.
    coin_ids = _coin_ids(rows)
    for r in rows:
        if 'inbox' in r:
            inbox = sorted(sales.values(r['inbox'].get('messages')), key=lambda m: m.get('index', 0))
        if r['event'] == 'TakeInboxMoney':
            index = r.get('arguments', {}).get('1')
            message = inbox.pop(index - 1) if type(index) is int and 0 < index <= len(inbox) else None
            pending.append((r['captured_at'], _mail_parts(r, message)))
        if r['event'] in HOOKS:
            hook = r
        if r['event'] == 'PLAYER_MONEY' and _valid(r):
            movement = _movement(r)
            pending = [(at, parts) for at, parts in pending if r['captured_at'] - at <= MATCH_SECONDS]
            _classify(movement, r, hook, pending, coin_ids)
            movements.append(movement)
    return movements


def _coin_ids(rows):
    result = set()
    coins = farming.coin_windows([(r | {'sequence': sales.order(r)[1]}, r.get('machine')) for r in rows])
    for (_, _, window, _), amount in coins.items():
        if amount is None:
            continue
        following = next((r for r in rows if r['event'] == 'PLAYER_MONEY'
                          and sales.order(r) > (window[0], window[1] or 0)), None)
        if following is not None:
            result.add(following['entry_id'])
    return result


def _mail_parts(record, message):
    if message is None:
        return None
    # Shared mail identity and seller invoice interpretation, including validity checks.
    mail_record = record | {'inbox': {'messages': [message]}}
    messages = sales.messages([mail_record])
    if not messages:
        return None
    amount = messages[0]['observed_money'][0]
    if type(amount) is not int or amount <= 0:
        return None
    outcomes = sales.project([mail_record])['outcomes']
    if not outcomes:
        return [{'category': 'mail in', 'copper': amount}]
    sale = outcomes[0]
    net = sale.get('net_copper')
    if type(net) is not int or not 0 <= net <= amount:
        return None
    return [{'category': 'auction sale', 'copper': net},
            {'category': 'deposit refund', 'copper': amount - net}]


def _movement(r):
    return {'entry_id': r['entry_id'], 'at': r['captured_at'], 'sequence': sales.order(r)[1],
            'character': sales.character(r),
            'machine': r.get('machine'), 'copper': r['after_copper'] - r['before_copper'],
            'parts': [], 'reason': None}


def _classify(movement, r, hook, pending, coin_ids):
    amount = movement['copper']
    if pending and amount > 0 and r.get('login_at') is not None:
        parts = []
        for i, (_, allocation) in enumerate(pending):
            if allocation is None:
                break
            parts.extend(allocation)
            if sum(p['copper'] for p in parts) == amount:
                movement['parts'] = parts
                del pending[:i + 1]
                return
        movement['parts'] = [{'category': 'mail in (unidentified)', 'copper': amount}]
        movement['reason'] = 'Inbox takes do not reconcile with this money change'
        pending.clear()
        return
    category = 'other'
    if r.get('login_at') is not None and hook and 0 <= r['captured_at'] - hook['captured_at'] <= MATCH_SECONDS:
        candidate, sign = HOOKS[hook['event']]
        merchant = hook.get('windows', {}).get('merchant') is True
        if amount * sign > 0 and ('UseContainerItem' not in hook['event'] or merchant):
            category = candidate
    if category == 'other' and r.get('login_at') is not None and r['entry_id'] in coin_ids:
        category = 'coin loot'
    movement['parts'] = [{'category': category, 'copper': amount}]


def summarize(movements):
    totals = {}
    for m in movements:
        day = datetime.fromtimestamp(m['at'], UTC).date().isoformat()
        for part in m['parts']:
            key = m['character'], day, part['category']
            row = totals.setdefault(key, {'character': m['character'], 'day': day, 'category': part['category'],
                                          'in_copper': 0, 'out_copper': 0})
            amount = part['copper']
            row['in_copper'] += max(0, amount)
            row['out_copper'] += max(0, -amount)
    return sorted(totals.values(), key=lambda r: (r['character'], r['day'], r['category']))


def reconcile(records, snapshots):
    groups = defaultdict(list)
    unreadable = 0
    for r in snapshots:
        if r.get('kind') != 'bags':
            continue
        if character_snapshots.unreadable_backpack(r):
            unreadable += 1
        else:
            groups[sales.character(r)].append(r)
    result = []
    for char, bags in groups.items():
        bags.sort(key=_order)
        for before, after in zip(bags, bags[1:], strict=False):
            interval = [r for r in records if sales.character(r) == char and r['event'] == 'PLAYER_MONEY'
                        and _order(before) < _order(r) <= _order(after)]
            actual = after['gold_copper'] - before['gold_copper'] if all(
                type(r.get('gold_copper')) is int for r in (before, after)) else None
            recorded = sum(r['after_copper'] - r['before_copper'] for r in interval if _valid(r))
            complete = all(_valid(r) for r in interval)
            result.append({'character': char, 'from': before['captured_at'], 'to': after['captured_at'],
                           'before_id': before['snapshot_id'], 'after_id': after['snapshot_id'],
                           'actual_copper': actual, 'recorded_copper': recorded,
                           'unexplained_copper': actual - recorded if actual is not None and complete else None,
                           'reason': None if complete and actual is not None else 'Missing gold or money baseline'})
    return result, unreadable
