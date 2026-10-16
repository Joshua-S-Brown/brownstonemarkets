"""Item-only, read-only price history and listing ladders (UI-17)."""
from datetime import UTC, datetime

import duckdb

from .flood_signals import compatible_identity
from .freshness import assess
from .metrics import METRICS_VERSION
from .scan_changes import eligible_scans
from .storage import scope_predicate


def _metrics_by_scan(db, config, scans, item_ids):
    """One item-only read across the given scans, keyed by scan ID; each row must match its scan's snapshot."""
    predicate, scope = scope_predicate(config)
    rows = db.execute(f"""SELECT scan_id, snapshot_id, item_id, variant_id, variant_state, min_buyout,
        unit_buyout_p25, listings, units FROM scan_metrics
        WHERE {predicate} AND metrics_version=? AND item_id IN (SELECT unnest(?)) AND scan_id IN (SELECT unnest(?))""",
        [*scope, METRICS_VERSION, item_ids, [s['scan_id'] for s in scans]]).fetchall()
    snapshots = {s['scan_id']: s['snapshot_id'] for s in scans}
    by_scan: dict[str, list[dict]] = {s['scan_id']: [] for s in scans}
    for scan_id, snapshot_id, *values in rows:
        if snapshots[scan_id] == snapshot_id:
            by_scan[scan_id].append(dict(zip(('item_id', 'variant_id', 'variant_state', 'min_buyout',
                                              'market_value', 'listings', 'units'), values, strict=True)))
    return by_scan


def _base(rows):
    return next((r for r in rows if r['variant_state'] == 'base' and r['variant_id'] is None), None)


def _reference(history, item_id):
    # The latest format-3 evidence decides whether legacy observations can describe the base.
    # With legacy-only history retain its original identity, without claiming variant evidence.
    rows = next((rows for rows in history.values() if any(r['variant_state'] is not None for r in rows)), [])
    if rows:
        return {'item_id': item_id, 'variant_id': None, 'variant_state': 'base'}, rows
    legacy = {'item_id': item_id, 'variant_id': None, 'variant_state': None}
    return legacy, [legacy]


def histories(db, config, item_ids):
    """Batch grid histories: one scoped metrics read, no per-row connections or repeated scan reads."""
    scans = eligible_scans(db, config)
    combined = _metrics_by_scan(db, config, scans, item_ids)
    indexed: dict = {item: {s['scan_id']: [] for s in scans} for item in item_ids}
    for scan, rows in combined.items():
        for row in rows:
            indexed[row['item_id']][scan].append(row)
    result = {}
    for item in item_ids:
        by_scan = indexed[item]
        evidence = _history(config, scans, by_scan, item)
        newest = by_scan[scans[0]['scan_id']] if scans else []
        evidence['series'] = {(r['item_id'], r['variant_id'], r['variant_state']): [
            compatible_identity(r, by_scan[s['scan_id']], newest) for s in reversed(scans)] for r in newest}
        result[item] = evidence
    return result


def history(db, config, item_id):
    return histories(db, config, [item_id])[item_id]


def _history(config, scans, by_scan, item_id):
    """Every eligible scan, including gaps. Numeric facts come only from stored current-version metrics."""
    reference, reference_rows = _reference(by_scan, item_id)
    points = []
    for scan in reversed(scans):
        rows = by_scan[scan['scan_id']]
        row = _base(rows) or compatible_identity(reference, rows, reference_rows)
        points.append({**scan, 'metrics': row})
    newest = by_scan[scans[0]['scan_id']] if scans else []
    return {'scans': scans, 'points': points, 'reference': reference, 'reference_rows': reference_rows,
            'other_identities': sum(r['variant_state'] not in (None, 'base') for r in newest),
            'note': ('TSM source: no addon price history.' if config['provider'] != 'addon'
                     else 'No eligible scans. Use Data to import complete priced scans.') if not scans else ''}


def ladder(db, config, item_id, evidence, scan_id, now):
    """Only an eligible scan may supply a ladder; group exact base/compatible legacy listings in SQL."""
    scan = next((s for s in evidence['scans'] if s['scan_id'] == scan_id), None)
    if scan is None:
        raise ValueError('Choose an eligible scan from this source and market; reopen the item to refresh.')
    identities = _metrics_by_scan(db, config, [scan], [item_id])[scan_id]
    row = _base(identities) or compatible_identity(evidence['reference'], identities, evidence['reference_rows'])
    result = {'scan': scan, 'rows': [], 'no_buyout_listings': 0, 'no_buyout_units': 0,
              'note': 'Base item absent or legacy identity incompatible in this scan.',
              'freshness': assess({'updated_at': scan['finished_at'].isoformat()}, now, config['max_age_hours'])}
    if row is None:
        return result
    predicate, scope = scope_predicate(config)
    grouped = db.execute(f"""SELECT CASE WHEN unit_buyout_ceil > 0 THEN unit_buyout_ceil END AS price,
        count(*), sum(quantity) FROM scan_listings WHERE {predicate} AND scan_id=? AND snapshot_id=?
        AND item_id=? AND variant_id IS NOT DISTINCT FROM ? AND variant_state IS NOT DISTINCT FROM ?
        GROUP BY price ORDER BY price NULLS LAST""",
        [*scope, scan_id, scan['snapshot_id'], item_id, row['variant_id'], row['variant_state']]).fetchall()
    cumulative = 0
    result['note'] = ''
    for price, listings, units in grouped:
        if price is None:
            result.update(no_buyout_listings=listings, no_buyout_units=units)
        else:
            cumulative += units
            result['rows'].append({'price_copper': price, 'listings': listings, 'units': units,
                                   'cumulative_units': cumulative})
    return result


def load_history(config, item_id):
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb'), read_only=True) as db:
        return history(db, config, item_id)


def load_ladder(config, item_id, evidence, scan_id):
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb'), read_only=True) as db:
        return ladder(db, config, item_id, evidence, scan_id, datetime.now(UTC))


def zoom_end(rows, share=95):
    """Cheapest positive price covering share% of buyout units; table always retains all levels."""
    if not rows:
        return None
    total = rows[-1]['cumulative_units']
    return next(r['price_copper'] for r in rows if r['cumulative_units'] * 100 >= total * share)
