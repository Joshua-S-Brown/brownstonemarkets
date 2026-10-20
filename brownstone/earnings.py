"""UI-20: measured time and earnings from scoped journal evidence."""
import json
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

import duckdb

from . import character_snapshots, item_ledger, ledger, sales
from .markets import scope_predicate
from .money import after_cut
from .storage import has_table

WORLD = {'quest reward', 'coin loot', 'vendor sale', 'repairs', 'quest cost'}
MARKET = {'auction sale', 'deposit refund', 'auction deposit', 'auction purchase', 'vendor purchase', 'training'}
WINDOWS = {
    'auction_house': ('AUCTION_HOUSE_SHOW', 'AUCTION_HOUSE_CLOSED'),
    'mailbox': ('MAIL_SHOW', 'MAIL_CLOSED'), 'merchant': ('MERCHANT_SHOW', 'MERCHANT_CLOSED'),
    'trainer': ('TRAINER_SHOW', 'TRAINER_CLOSED'),
    'trade_skill': ('TRADE_SKILL_SHOW', 'TRADE_SKILL_CLOSE'),
}
CAVEAT = ('Your own past sessions, not a promise; launch competition differs. Market gold includes sales '
          'of items gathered or crafted earlier; no cost basis yet.')


def item_ids(data):
    """Include past gains in Team's existing price read, even after those items left the bags."""
    rows = [r for state in data.values() for r, _ in state.get('observations', [])]
    gained = {int(item) for r in rows for item, count in r.get('item_changes', {}).items() if count > 0}
    rewards = {int(link[1]) for r in rows for item in sales.values(r.get('rewards', {}).get('items'))
               if (link := sales.LINK.search(item.get('link', '')))}
    return gained | rewards


def load(config, prices, vendors):
    """Read-only, source/full-market journal and readable bags, including every session event."""
    records, snapshots = [], []
    path = Path(config['data_dir']) / 'brownstone.duckdb'
    if path.exists():
        scope, params = scope_predicate(config)
        with duckdb.connect(str(path), read_only=True) as db:
            for table, target in (('character_journal', records), ('character_snapshots', snapshots)):
                if has_table(db, table):
                    target.extend(json.loads(raw) | {'machine': machine} for raw, machine in db.execute(
                        f'SELECT record_json, machine FROM {table} WHERE {scope}', params).fetchall())
    return project(records, snapshots, prices, vendors, config['auction_cut'],
                   config.get('farming_idle_minutes', 10))


def _bucket(label):
    return dict(label=label, world_seconds=0, market_seconds=0, world_copper=0, market_copper=0,
                loot_copper=0, unpriced_units=0, categories={}, own_mail_copper=0,
                quest_xp=0, other_xp=0, checkpoints=0, xp_incomplete=False, levels=0)


def _finish(row):
    row = row.copy()
    row['seconds'] = row['world_seconds'] + row['market_seconds']
    row['groups'] = {'world': {}, 'market': {}, 'not assigned': {}}
    for category, copper in row['categories'].items():
        group = 'world' if category in WORLD else 'market' if category in MARKET else 'not assigned'
        row['groups'][group][category] = copper
    row['thin'] = row['seconds'] < 1800
    row['xp_label'] = ('XP not captured' if not row['checkpoints'] else
                       'at least' if row['xp_incomplete'] else 'captured')
    for key, amount, seconds in (
        ('world_per_hour_copper', row['world_copper'], row['world_seconds']),
        ('market_per_hour_copper', row['market_copper'], row['market_seconds']),
        ('loot_per_hour_copper', row['loot_copper'], row['world_seconds']),
        ('xp_per_hour', row['quest_xp'] + row['other_xp'], row['world_seconds']),
    ):
        row[key] = int(Fraction(amount * 3600, seconds)) if seconds else None  # toward zero, both signs
    if not row['checkpoints']:
        row['xp_per_hour'] = None
    if row['unpriced_units'] and not row['loot_copper']:
        row['loot_per_hour_copper'] = None
    return row


def _merge(target, row):
    for key in target:
        if key == 'categories':
            for category, copper in row[key].items():
                target[key][category] = target[key].get(category, 0) + copper
        elif key == 'xp_incomplete':
            target[key] |= row[key] or (not row['checkpoints'] and bool(row['world_seconds']))
        elif key != 'label':
            target[key] += row[key]


def _intervals(rows, key, show, close):
    intervals, start, last = [], None, None
    for r in rows:
        event = r['event']
        if key == 'trade_skill':
            event = {'CRAFT_SHOW': show, 'CRAFT_CLOSE': close}.get(event, event)
        if event == close and start is not None:
            intervals.append((start, r['captured_at']))
            start = last = None
        elif event == show or r.get('windows', {}).get(key) is True:
            last = r['captured_at']
            if start is None:
                start = last
        elif start is not None and 'windows' in r:  # closed without its event, e.g. a reload
            intervals.append((start, last))
            start = last = None
    return intervals + ([(start, last)] if start is not None else [])


def _windows(rows):
    intervals = [i for key, (show, close) in WINDOWS.items() for i in _intervals(rows, key, show, close)]
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def _band(level):
    first = (level - 1) // 5 * 5 + 1 if type(level) is int and level > 0 else None
    return f'{first}–{first + 4}' if first else 'level unknown'


def _loot(rows, movements):
    """UI-16 gains plus observed fixed/chosen quest rewards, never every offered choice."""
    result = defaultdict(list)
    for m in movements:
        units = sum(p['units'] for p in m['parts'] if p['category'] == 'gathered or looted' and p['units'] > 0)
        if units:
            result[m['entry_id']].append((m['item_id'], units))
    chosen = None
    for r in rows:
        if r['event'] == 'GetQuestReward':
            chosen = r.get('arguments', {}).get('1')
        if r['event'] == 'QUEST_TURNED_IN' and r.get('family') == 'quest':
            for item in sales.values(r.get('rewards', {}).get('items')):
                link = sales.LINK.search(item.get('link', ''))
                units = item.get('info', {}).get('3')
                selected = item.get('kind') == 'reward' or item.get('index') == chosen
                if selected and link and type(units) is int and units > 0:
                    result[r['entry_id']].append((int(link[1]), units))
            chosen = None
    return result


def _entry(row, record, parts, loot, known, prices, vendors, cut, in_market):
    for p in parts:
        category, copper = p['category'], p['copper']
        if category in {'mail in', 'mail out'} and item_ledger._own(
                p.get('counterparty'), sales.character(record), known):
            row['own_mail_copper'] += copper
            continue
        row['categories'][category] = row['categories'].get(category, 0) + copper
        if category in WORLD:
            row['world_copper'] += copper
        elif category in MARKET:
            row['market_copper'] += copper
    if not in_market:
        for item, units in loot:
            price, vendor = prices.get(item), vendors.get(item)
            if price is not None and price > 0:
                row['loot_copper'] += after_cut(price, units, cut)
            elif vendor is not None and vendor > 0:
                row['loot_copper'] += vendor * units
            else:
                row['unpriced_units'] += units
    if record.get('family') == 'xp':
        row['checkpoints'] += 1
        row['quest_xp'] += record.get('quest_xp') or 0
        row['other_xp'] += record.get('other_xp') or 0
        row['xp_incomplete'] |= record.get('other_xp') is None


def _session(rows, snapshots, gold, items, known, prices, vendors, cut, idle):
    first = rows[0]
    before = [r for r in snapshots.get(sales.character(first), [])
              if r.get('kind') == 'bags' and not character_snapshots.unreadable_backpack(r)
              and r['captured_at'] <= first['login_at']]
    level = max(before, key=ledger._order).get('level') if before else None
    stretches = [[]]
    for r in rows:
        if stretches[-1] and r['captured_at'] - stretches[-1][-1]['captured_at'] > idle * 60:
            stretches.append([])
        stretches[-1].append(r)
    bands = {}
    loot = _loot(rows, items)
    for index, stretch in enumerate(stretches):
        windows = _windows(stretch)
        previous = stretch[0]['captured_at']
        if index == 0 and 0 <= previous - first['login_at'] <= idle * 60:
            previous = first['login_at']
        for r in stretch:
            row = bands.setdefault(_band(level), _bucket(_band(level)))
            at = r['captured_at']
            market = sum(max(0, min(at, end) - max(previous, start)) for start, end in windows)
            row['market_seconds'] += market
            row['world_seconds'] += at - previous - market
            _entry(row, r, gold.get(r['entry_id'], []), loot.get(r['entry_id'], []), known, prices, vendors,
                   cut, any(start <= at < end for start, end in windows)
                   or any(r.get('windows', {}).get(key) is True for key in WINDOWS))
            if r['event'] == 'PLAYER_LEVEL_UP' and r.get('family') == 'xp':
                new = r.get('arguments', {}).get('1', r.get('level'))
                row['levels'] += max(0, new - level) if type(new) is int and type(level) is int else 1
                level = new
            previous = at
    total = _bucket('Session')
    for row in bands.values():
        _merge(total, row)
    return _finish(total) | dict(start=first['login_at'], end=rows[-1]['captured_at'],
                                login_at=first.get('login_at'), machine=first.get('machine'),
                                bands=[_finish(b) for b in bands.values()])


def project(records, snapshots=(), prices=None, vendors=None, cut=0.05, idle=10):
    """Project already scoped evidence. Missing login evidence is disclosed, never timed."""
    records = list({r['entry_id']: r for r in records}.values())
    loot_vendors = {int(link[1]): slot['vendor_sell_copper'] for r in sorted(records, key=sales.order)
                    for slot in r.get('loot_slots', []) if (link := sales.LINK.search(slot.get('link', '')))
                    and type(slot.get('vendor_sell_copper')) is int and slot['vendor_sell_copper'] > 0}
    vendors = loot_vendors | {i: price for i, price in (vendors or {}).items() if price is not None and price > 0}
    gold = ledger.project(records)
    parts = {m['entry_id']: m['parts'] for m in gold['movements']}
    items = item_ledger.project(records)['movements']
    known = {sales.character(r) for r in [*records, *snapshots]}
    levels = defaultdict(list)
    for r in snapshots:
        levels[sales.character(r)].append(r)
    groups = defaultdict(list)
    for r in records:
        if r.get('login_at') is not None:
            groups[sales.character(r), r.get('machine'), r['login_at']].append(r)
    characters = []
    for character in sorted(known):
        sessions = [_session(sorted(rows, key=sales.order), levels, parts, items, known,
                             prices or {}, vendors or {}, cut, idle)
                    for (key, _, _), rows in groups.items() if key == character]
        sessions.sort(key=lambda s: (s['end'], s['start']))
        total, bands = _bucket(character[0]), {}
        for session in sessions:
            _merge(total, session)
            for band in session['bands']:
                _merge(bands.setdefault(band['label'], _bucket(band['label'])), band)
        characters.append(dict(character=character, sessions=sessions, total=_finish(total),
                               bands=[_finish(b) for b in bands.values()]))
    total = _bucket('Team total')
    for character in characters:
        _merge(total, character['total'])
    return dict(characters=characters, total=_finish(total), caveat=CAVEAT,
                excluded_money=gold['excluded_money'],
                unknown_login_entries=sum(r.get('login_at') is None for r in records))


def character_record(report, key):
    """Characters without a journal still have an explicit empty record."""
    return next((c for c in report['characters'] if c['character'] == key),
                dict(character=key, sessions=[], bands=[], total=_finish(_bucket(key[0]))))
