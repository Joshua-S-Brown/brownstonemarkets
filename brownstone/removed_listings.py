"""Scoped, read-only disappearance evidence; no price estimates or sale attribution."""
from collections import defaultdict
from datetime import timedelta

from .scan_changes import _MATCH_SQL, eligible_scans
from .storage import scope_predicate

MAX_GAP = timedelta(hours=12)
# UI-10: Classic Era bounds, accepted for Forever on 2026-10-16.
BUCKET_LOWER_SECONDS = {1: 0, 2: 1800, 3: 7200, 4: 43200}
CATEGORIES = ('early', 'expiry', 'unknown')


def scan_pairs(db, config) -> list[dict]:
    scans = eligible_scans(db, config)
    return [{'earlier': earlier, 'later': later,
             'gap': later['finished_at'] - earlier['finished_at'],
             'skipped': later['finished_at'] - earlier['finished_at'] > MAX_GAP}
            for later, earlier in zip(scans, scans[1:], strict=False)]


def qualifying_pairs(db, config, limit=10) -> list[dict]:
    """The newest adjacent pairs within MAX_GAP: UI-11 churn and Today's removal check share them."""
    return [pair for pair in scan_pairs(db, config) if not pair['skipped']][:limit]


def recent_comparisons(db, config, item_ids, limit=10) -> list[dict]:
    """Compare qualifying_pairs without re-reading the scan list for every pair."""
    return [_compare(db, config, pair, item_ids) for pair in qualifying_pairs(db, config, limit)]


def unavailable(config, pairs):
    if config['provider'] != 'addon':
        return 'TSM source: no addon scan pairs.'
    return 'Gap too long: no consecutive scans within 12 hours.' if pairs else 'Fewer than two eligible scans.'


def _counts(db, config, pair, item_ids):
    predicate, scope = scope_predicate(config)
    item_filter = '' if item_ids is None else ' AND item_id IN (SELECT unnest(?))'
    query = (f'SELECT item_id, variant_id, variant_state, quantity, buyout, time_left, '
             f'min(loaded_item_name(item_name)) AS item_name, count(*) AS listings FROM scan_listings '
             f'WHERE {predicate} AND scan_id=? AND snapshot_id=? {item_filter} '
             'GROUP BY item_id, variant_id, variant_state, quantity, buyout, time_left')
    parameters = []
    for side in ('earlier', 'later'):
        scan = pair[side]
        parameters.extend([*scope, scan['scan_id'], scan['snapshot_id']])
        if item_ids is not None:
            parameters.append(item_ids)
    # Item-ID filtering retains every variant/state so the shared legacy rule sees the whole item.
    return db.execute(f"""WITH a AS ({query}), b AS ({query}), {_MATCH_SQL}
        SELECT 'earlier', item_id, variant_id, match_state, quantity, buyout, time_left, item_name, listings FROM am
        UNION ALL
        SELECT 'later', item_id, variant_id, match_state, quantity, buyout, time_left, item_name, listings FROM bm
        """, parameters).fetchall()


def _known_names(db, config, item_ids):
    # DATA-02: only items without a loaded name in the pair fall back to the version-scoped lookup.
    return dict(db.execute('SELECT item_id, item_name FROM item_names WHERE game_version=? '
                           'AND item_id IN (SELECT unnest(?))', [config['game_version'], item_ids]).fetchall())


def _empty_item(item_id, variant_id, state):
    return {'item_id': item_id, 'variant_id': variant_id, 'variant_state': state,
            'item_name': None, 'evidence': [], 'earlier_listings': 0, 'earlier_units': 0,
            **{category: {'listings': 0, 'units': 0} for category in CATEGORIES},
            'without_buyout': {'earlier': 0, 'later': 0}}


def _classify(buckets, removed, gap):
    counts = {category: 0 for category in CATEGORIES}
    chosen = []
    for bucket, count in sorted(buckets.items(), key=lambda entry: (entry[0] is None, entry[0] or 0)):
        take = min(count, removed)
        category = ('unknown' if bucket not in BUCKET_LOWER_SECONDS else
                    'expiry' if gap.total_seconds() >= BUCKET_LOWER_SECONDS[bucket] else 'early')
        counts[category] += take
        if take:
            chosen.append({'time_left': bucket, 'listings': take, 'category': category})
        removed -= take
    return counts, chosen


def compare_pair(db, config, pair, item_ids=None) -> dict:
    """Calculate an adjacent eligible pair only; excessive gaps carry no numeric evidence."""
    if pair not in scan_pairs(db, config):
        raise ValueError('Choose consecutive eligible scans from the selected source and full market')
    return _compare(db, config, pair, item_ids)


def _compare(db, config, pair, item_ids=None) -> dict:
    if pair['skipped']:
        return {**pair, 'items': []}
    items: dict = {}
    groups: dict = defaultdict(lambda: {'earlier': defaultdict(int), 'later': defaultdict(int)})
    for side, item_id, variant, state, quantity, buyout, bucket, name, count in _counts(db, config, pair, item_ids):
        identity = (item_id, variant, state)
        item = items.setdefault(identity, _empty_item(*identity))
        if side == 'earlier':
            item['earlier_listings'] += count
            item['earlier_units'] += quantity * count
        if name:
            item['item_name'] = min(name, item['item_name'] or name)
        if buyout is None or buyout <= 0:
            item['without_buyout'][side] += count
            continue
        groups[(*identity, quantity, buyout)][side][bucket] += count
    for key, sides in groups.items():
        _add_group(items[key[:3]], key[3], key[4], sides, pair['gap'])
    unnamed = sorted({item['item_id'] for item in items.values() if item['item_name'] is None})
    known = _known_names(db, config, unnamed) if unnamed else {}
    for item in items.values():
        item['item_name'] = item['item_name'] or known.get(item['item_id'], f"Item {item['item_id']}")
    return {**pair, 'items': sorted(items.values(), key=lambda r: (
        r['item_id'], r['variant_state'], r['variant_id'] or ''))}


def _add_group(item, quantity, buyout, sides, gap):
    earlier, later = (sum(sides[side].values()) for side in ('earlier', 'later'))
    removed = max(0, earlier - later)
    counts, chosen = _classify(sides['earlier'], removed, gap)
    for category, count in counts.items():
        item[category]['listings'] += count
        item[category]['units'] += count * quantity
    item['evidence'].append({'quantity': quantity, 'buyout': buyout, 'earlier': earlier, 'later': later,
                             'removed': removed, 'chosen_buckets': chosen})


def item_history(db, config, item_id) -> dict:
    """Newest first, at most ten qualifying pairs; intervening long gaps remain visible."""
    pairs = scan_pairs(db, config)
    results = []
    qualifying = 0
    for pair in pairs:
        results.append(_compare(db, config, pair, [item_id]))
        qualifying += not pair['skipped']
        if qualifying == 10:
            break
    return {'pairs': results, 'note': unavailable(config, pairs) if not results else ''}


def top_removals(db, config, item_ids) -> dict:
    """Newest qualifying adjacent pair, top ten identities in catalog chains (never pooled)."""
    pairs = scan_pairs(db, config)
    pair = next((pair for pair in pairs if not pair['skipped']), None)
    if pair is None:
        return {'pair': None, 'rows': [], 'note': unavailable(config, pairs)}
    result = _compare(db, config, pair, item_ids)
    rows = [row for row in result['items'] if row['early']['units'] > 0]
    rows.sort(key=lambda row: (-row['early']['units'], row['item_id'], row['variant_state'], row['variant_id'] or ''))
    # One link per item; show its largest identity rather than silently pooling variants.
    largest: dict = {}
    for row in rows:
        largest.setdefault(row['item_id'], row)
    return {'pair': pair, 'rows': list(largest.values())[:10], 'note': ''}
