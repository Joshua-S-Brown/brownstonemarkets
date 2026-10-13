"""Read-only crowding and relative-price evidence from scoped scan metrics (UI-11)."""
from datetime import timedelta
from fractions import Fraction

from .config import FLOOD_DEFAULTS
from .freshness import assess
from .metrics import METRICS_VERSION
from .removed_listings import scan_pairs
from .scan_changes import _scan_items_sql, eligible_scans
from .storage import scope_predicate


def settings(config):
    return {key: config.get(key, value) for key, value in FLOOD_DEFAULTS.items()}


def _read(db, config, scan, item_ids):
    predicate, scope = scope_predicate(config)
    parameters = [*scope, scan['scan_id'], scan['snapshot_id'], *scope, scan['snapshot_id'],
                  *scope, scan['scan_id'], scan['snapshot_id'], config['game_version'],
                  *scope, scan['scan_id'], scan['snapshot_id'], item_ids]
    rows = db.execute(f"""WITH named AS ({_scan_items_sql(predicate)}),
        supply AS (SELECT item_id, variant_id, variant_state, largest_stack_units FROM scan_metrics
            WHERE {predicate} AND scan_id=? AND snapshot_id=? AND metrics_version={METRICS_VERSION})
        SELECT named.*, supply.largest_stack_units FROM named JOIN supply
            ON named.item_id=supply.item_id AND named.variant_id IS NOT DISTINCT FROM supply.variant_id
            AND named.variant_state IS NOT DISTINCT FROM supply.variant_state
        WHERE named.item_id IN (SELECT unnest(?))""", parameters).fetchall()
    columns = ('item_id', 'variant_id', 'variant_state', 'item_name', 'min_buyout', 'market_value',
               'listings', 'units', 'largest_stack_units')
    return [dict(zip(columns, row, strict=True)) for row in rows]


class Rows(list):
    """One scan's rows with an item index: matching every row against a whole scan was quadratic."""

    def __init__(self, rows):
        super().__init__(rows)
        self.by_item: dict[int, list[dict]] = {}
        for row in self:
            self.by_item.setdefault(row['item_id'], []).append(row)


def _same_item(rows, item_id):
    return rows.by_item.get(item_id, []) if isinstance(rows, Rows) else [r for r in rows if r['item_id'] == item_id]


def _match(current, rows):
    """ADDON-08: exact identity, with legacy/base compatibility only for pure base scans."""
    same_item = _same_item(rows, current['item_id'])
    exact = next((r for r in same_item if (r['variant_id'], r['variant_state']) ==
                  (current['variant_id'], current['variant_state'])), None)
    if exact is not None:
        return exact
    state = current['variant_state']
    if state not in (None, 'base') or current['variant_id'] is not None:
        return None
    other = 'base' if state is None else None
    return next((r for r in same_item if r['variant_state'] == other and r['variant_id'] is None), None)


def _compatible(current, rows, newest):
    # Both sides must retain the pure-base condition; a base row alongside variants cannot use legacy history.
    match = _match(current, rows)
    if match is None or current['variant_state'] == match['variant_state']:
        return match
    base_rows = rows if current['variant_state'] is None else newest
    if all(r['variant_state'] == 'base' for r in _same_item(base_rows, current['item_id'])):
        return match
    return None


def _churn(current, history, pairs, newest):
    changed = 0
    known = 0
    for pair in pairs:
        a_rows, b_rows = (history[pair[side]['scan_id']] for side in ('earlier', 'later'))
        a, b = (_compatible(current, rows, newest) for rows in (a_rows, b_rows))
        if a is None or b is None or not a['min_buyout'] or not b['min_buyout']:
            continue
        # A pair itself must satisfy legacy/base compatibility, too.
        if _compatible(a, b_rows, a_rows) is None:
            continue
        known += 1
        changed += a['min_buyout'] != b['min_buyout']
    return {'changed': changed, 'pairs': known}


def crowding(listings, churn, options):
    if listings <= options['flood_thin_listings']:
        return 'thin'
    if listings >= options['flood_contested_listings'] and (
            not churn['pairs'] or churn['changed'] * 100 >= churn['pairs'] * options['flood_churn_percent']):
        return 'contested'
    return 'steady'


def overshoot(price, prices, options):
    prices = sorted(p for p in prices if p is not None and p > 0)
    result = {'scans': len(prices), 'typical_copper': None, 'ratio': None, 'label': 'too few scans'}
    if len(prices) < options['flood_min_scans']:
        return result
    middle = len(prices) // 2
    typical = (prices[middle] + prices[(len(prices) - 1) // 2]) // 2
    result.update(typical_copper=typical, label='no buyout' if not price or price <= 0 else 'typical')
    if not price or price <= 0:
        return result
    result['ratio'] = {'numerator': price, 'denominator': typical}
    if price * 100 <= typical * options['flood_cheap_percent']:
        result['label'] = 'cheap'
    elif price * 100 >= typical * options['flood_high_percent']:
        result['label'] = 'high'
    return result


def signals(db, config, item_ids, now):
    """Only selected IDs; earlier scan median never includes the newest eligible scan."""
    options = settings(config)
    scans = eligible_scans(db, config)
    result = {'rows': [], 'settings': options, 'scan': None, 'freshness': None,
              'note': 'TSM source: no addon flood signals.' if config['provider'] != 'addon' else 'No eligible scans.'}
    if not scans:
        return result
    pairs = [p for p in scan_pairs(db, config) if not p['skipped']][:10]
    cutoff = scans[0]['finished_at'] - timedelta(days=options['flood_window_days'])
    earlier = [s for s in scans[1:] if s['finished_at'] >= cutoff]
    needed = {s['scan_id']: s for s in [scans[0], *earlier]}
    for pair in pairs:
        needed.update({pair[side]['scan_id']: pair[side] for side in ('earlier', 'later')})
    history = {key: Rows(_read(db, config, scan, item_ids)) for key, scan in needed.items()}
    newest = history[scans[0]['scan_id']]
    result.update(scan=scans[0], note='', freshness=assess(
        {'updated_at': scans[0]['finished_at'].isoformat()}, now, config['max_age_hours']))
    for row in newest:
        churn = _churn(row, history, pairs, newest)
        previous = [_compatible(row, history[s['scan_id']], newest) for s in earlier]
        prices = [r['min_buyout'] for r in previous if r is not None]
        result['rows'].append({**row, 'crowding': crowding(row['listings'], churn, options), 'churn': churn,
                               'overshoot': overshoot(row['min_buyout'], prices, options)})
    return result


def catalog_roles(catalogs):
    roles: dict[int, set[str]] = {}
    for catalog in catalogs:
        for item_id in catalog['items_by_id']:
            roles.setdefault(item_id, set())
        for recipe in catalog['recipes_by_id'].values():
            roles[recipe['output_item_id']].add('output')
            for material in recipe['inputs']:
                roles[material['item_id']].add('material')
    return {item_id: ' / '.join(sorted(values)) or 'chain item' for item_id, values in roles.items()}


def top_lists(result, roles):
    rows = [{**r, 'role': roles[r['item_id']]} for r in result['rows'] if r['item_id'] in roles]
    def tie(r):
        return (r['item_id'], r['variant_state'] or '', r['variant_id'] or '')
    contested = sorted((r for r in rows if r['crowding'] == 'contested'),
                       key=lambda r: (-r['listings'],
                                      -Fraction(r['churn']['changed'], r['churn']['pairs'] or 1), *tie(r)))
    # Thin identities' one-off quotes would crowd out real swings; their item pages still flag them.
    overshoots = sorted((r for r in rows if r['overshoot']['label'] in ('cheap', 'high') and r['crowding'] != 'thin'),
                        key=lambda r: (-abs(Fraction(r['overshoot']['ratio']['numerator'],
                                                     r['overshoot']['ratio']['denominator']) - 1), *tie(r)))
    return {**result, 'contested': contested[:10], 'overshoots': [r for label in ('cheap', 'high')
                                             for r in [r for r in overshoots if r['overshoot']['label'] == label][:5]]}
