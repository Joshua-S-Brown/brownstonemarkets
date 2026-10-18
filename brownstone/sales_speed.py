"""UI-19: time-weighted early removals, an upper bound on sales, never a forecast."""
from datetime import timedelta
from fractions import Fraction
from statistics import median

import duckdb

from . import removed_listings
from .config import SPEED_DEFAULTS

LABEL = 'removed early (upper bound on sales; includes cancels and reposts)'


def summarize(samples, config):
    options = {key: config.get(key, value) for key, value in SPEED_DEFAULTS.items()}
    seconds = sum(s['seconds'] for s in samples)
    count = len(samples)
    hours = seconds / 3600
    enough = count >= options['speed_min_pairs'] and seconds >= options['speed_min_hours'] * 3600
    rate = Fraction(sum(s['removed'] for s in samples) * 86400, seconds) if seconds else Fraction(0)
    supply = median([Fraction(s['listed']) for s in samples]) if samples else None
    daily = int(rate) if enough else None
    reason = (f'not enough scan gaps ({count}, {hours:.1f} h)' if not enough else
              f'no early removals in {count} scan gaps' if not rate else '')
    return {'label': LABEL, 'pairs': count, 'hours': hours, 'daily_units': daily,
            'median_units': float(supply) if supply is not None else None,
            'days_supply': float(supply / rate) if enough and rate and supply is not None else None,
            'suggested_units': int(min(rate * options['speed_cover_days'],
                                       supply * options['speed_cap_percent'] / 100))
            if enough and supply is not None else None,
            'reason': reason, 'settings': options}


def read(db, config, item_ids):
    """Read adjacent pairs once for all requested items, preserving UI-10 identity matching."""
    pairs = removed_listings.scan_pairs(db, config)
    if not pairs or not item_ids:
        return []
    cutoff = pairs[0]['later']['finished_at'] - timedelta(
        days=config.get('speed_window_days', SPEED_DEFAULTS['speed_window_days']))
    samples: dict[tuple, list[dict]] = {}
    for pair in pairs:
        if pair['skipped'] or pair['earlier']['finished_at'] < cutoff:
            continue
        for row in removed_listings._compare(db, config, pair, item_ids)['items']:
            state = None if row['variant_state'] == 'legacy' else row['variant_state']
            evidence = samples.setdefault((row['item_id'], row['variant_id'], state), [])
            if row['earlier_listings']:
                evidence.append({'seconds': int(pair['gap'].total_seconds()),
                                 'removed': row['early']['units'], 'listed': row['earlier_units']})
    return [dict(zip(('item_id', 'variant_id', 'variant_state'), identity, strict=True)) |
            summarize(evidence, config) for identity, evidence in samples.items()]


def load(config, item_ids):
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb'), read_only=True) as db:
        return read(db, config, item_ids)


def select(rows, item_id, variant_id, state, config):
    # Base uses legacy evidence only when this item has no separate modern identity.
    if state == 'base' and not any(r['item_id'] == item_id and r['variant_state'] is not None for r in rows):
        variant_id, state = None, None
    return next((r for r in rows if (r['item_id'], r['variant_id'], r['variant_state']) ==
                 (item_id, variant_id, state)), summarize([], config))
