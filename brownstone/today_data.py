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
    base_metrics = {row['item_id']: row for row in metrics if row['variant_id'] is None
                    and row['variant_state'] in (None, 'base')}
    vendor_rows = db.execute(f"SELECT item_id, vendor_sell_copper FROM effective_scan_items WHERE {predicate} "
                             "AND snapshot_id=? AND scan_id=? AND vendor_sell_copper>0",
                             [*parameters, snapshot_id, scan[0]]).fetchall()
    return observations, ladders, base_metrics, dict(vendor_rows)
