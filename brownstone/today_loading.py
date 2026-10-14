"""Read-only Today evidence assembly shared by every presentation layer."""
from datetime import datetime

import duckdb

from brownstone import farming, flood_signals, professions, removed_listings
from brownstone.storage import latest_snapshot
from brownstone.today_data import read_today_evidence
from brownstone.today_funds import resolve_funds


def load_today(config, catalogs, settings, character_data, now: datetime, *, item_ids=(), flood=False):
    """Return the latest manifest and build_today arguments, or None when no snapshot exists.

    Reads retain the existing full market/source predicates. The caller owns settings,
    character evidence error presentation, and session choices; this function never writes.
    Only Today needs UI-11 signals (flood=True); other pages skip that read.
    """
    manifest, sid, _ = latest_snapshot(config)
    if manifest is None:
        return None, None
    ids = sorted({item for catalog in catalogs for item in catalog["items_by_id"]} | set(item_ids))
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb"), read_only=True) as db:
        observations, listings, metrics, vendors = read_today_evidence(db, config, sid, ids)
        flood_evidence = flood_signals.signals(db, config, _signal_ids(ids, character_data), now) if flood else None
    settings = resolve_funds(settings, character_data, now, config["max_age_hours"]).settings
    arguments = dict(catalogs=catalogs, observations=observations, market=config,
                     snapshot={**manifest, "snapshot_id": sid}, settings=settings, now=now,
                     listings=listings, metrics=metrics, vendor_prices=vendors,
                     max_age_hours=config["max_age_hours"], auction_cut=config["auction_cut"],
                     character_data=character_data, flood_evidence=flood_evidence)
    return manifest, arguments


def _signal_ids(ids, character_data):
    """Catalog items plus gathered items, so This session reuses the same read."""
    return sorted(set(ids) | {row['item_id'] for state in character_data.values()
                              for row in farming.gathered(state.get('observations', []))})


def load_today_characters(config):
    """Read the shared profession projection; retain a failure for the UI to explain."""
    try:
        return professions.latest_data(config), None
    except Exception as error:
        return {}, f"Unable to read character evidence: {error}. Showing every catalog recipe."


def load_today_removals(config, plan):
    """UI-10 history for shown outputs only, over UI-11's ten newest qualifying pairs."""
    ids = sorted({row['output_item_id'] for row in plan['craft']})
    if not ids or config.get('provider') != 'addon':
        return {}
    totals = {item_id: {'pairs': 0, 'units': 0} for item_id in ids}
    signals = {row['output_item_id']: row.get('signal') for row in plan['craft']}
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb'), read_only=True) as db:
        for result in removed_listings.recent_comparisons(db, config, ids):
            _add_removals(totals, result['items'], signals, result['earlier']['scan_id'])
    return totals


def _add_removals(totals, rows, signals, scan_id):
    for item_id, total in totals.items():
        history = (signals[item_id] or {}).get('earlier_identities', {})
        if scan_id not in history:
            continue
        state = 'legacy' if history[scan_id] is None else history[scan_id]
        matches = [r for r in rows if r['item_id'] == item_id and r['variant_id'] is None]
        row = next((r for r in matches if r['variant_state'] == state), None)
        # UI-10 normalizes compatible legacy/base pairs to base; never sum both identities.
        if row is None and state == 'legacy':
            row = next((r for r in matches if r['variant_state'] == 'base'), None)
        if row is not None:
            earlier = row['without_buyout']['earlier'] + sum(e['earlier'] for e in row['evidence'])
            total['pairs'] += bool(earlier)
            total['units'] += row['early']['units']
