"""Read one source/snapshot's listing evidence without seller strings."""
from .config import ADDON_PROVIDER
from .metrics import read_scan_metrics
from .storage import price_observations, scope_predicate


def read_today_evidence(db, config, snapshot_id, item_ids):
    observations = price_observations(db, config, snapshot_id, item_ids)
    metrics = read_scan_metrics(db, config, snapshot_id)
    if config["provider"] != ADDON_PROVIDER or metrics is None:
        return observations, None, None, {}
    predicate, parameters = scope_predicate(config)
    scan = db.execute(f"SELECT scan_id FROM addon_scans WHERE {predicate} AND snapshot_id=? "
                      "AND status='completed' AND NOT partial AND priced", [*parameters, snapshot_id]).fetchone()
    rows = db.execute(f"SELECT item_id, quantity, buyout, unit_buyout_ceil FROM scan_listings WHERE {predicate} "
                      "AND snapshot_id=? AND scan_id=? AND variant_id IS NULL "
                      "AND (variant_state IS NULL OR variant_state='base') AND buyout>0 "
                      "ORDER BY item_id, unit_buyout_ceil, quantity, buyout",
                      [*parameters, snapshot_id, scan[0]]).fetchall()
    ladders: dict[int, list[tuple[int, int, int]]] = {}
    for item_id, quantity, buyout, unit in rows:
        ladders.setdefault(item_id, []).append((quantity, buyout, unit))
    base_metrics = _base_metrics(metrics)
    vendor_rows = db.execute(f"SELECT item_id, vendor_sell_copper FROM effective_scan_items WHERE {predicate} "
                             "AND snapshot_id=? AND scan_id=? AND vendor_sell_copper>0",
                             [*parameters, snapshot_id, scan[0]]).fetchall()
    return observations, ladders, base_metrics, dict(vendor_rows)


def _base_metrics(metrics):
    return {row['item_id']: row for row in metrics if row['variant_id'] is None
            and row['variant_state'] in (None, 'base')}


def read_skillup_market(db, config, snapshot_id, item_ids):
    """Read-only base/legacy context for CRAFT-10; retain full source/market/snapshot scope."""
    if config['provider'] != ADDON_PROVIDER:
        observations = price_observations(db, config, snapshot_id, item_ids)
        return {item: {"units": None, "min_buyout": _positive(observations.get(item, {}).get('min_buyout'))}
                for item in item_ids}
    metrics = read_scan_metrics(db, config, snapshot_id)
    if metrics is None:
        return {item: {"units": None, "units_note": "no priced scan in this snapshot", "min_buyout": None}
                for item in item_ids}
    base = _base_metrics(metrics)
    return {item: {"units": base.get(item, {}).get('units', 0),
                   "min_buyout": _positive(base.get(item, {}).get('min_buyout'))} for item in item_ids}


def _positive(price):
    return price if price and price > 0 else None
