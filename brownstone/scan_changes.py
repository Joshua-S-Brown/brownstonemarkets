"""Historical addon comparisons, confined to one observer and auction house."""
from collections.abc import Mapping
from datetime import UTC
from typing import Any

from .config import ADDON_PROVIDER
from .storage import scope_predicate

METRICS = ("min_buyout", "market_value", "listings", "units")


def eligible_scans(db, config: Mapping[str, Any]) -> list[dict]:
    """Distinct complete, priced scans, newest finish first (never import manifests)."""
    if config["provider"] != ADDON_PROVIDER:
        return []
    predicate, parameters = scope_predicate(config)
    rows = db.execute(
        f"SELECT scan_id, snapshot_id, finished_at FROM addon_scans WHERE {predicate} "
        "AND status='completed' AND NOT partial AND priced ORDER BY finished_at DESC, scan_id DESC",
        parameters,
    ).fetchall()
    return [{"scan_id": scan_id, "snapshot_id": snapshot_id, "finished_at": finished.astimezone(UTC)}
            for scan_id, snapshot_id, finished in rows]


def _scan_items_sql(predicate: str) -> str:
    # This scan's own loaded names come first (price row, then listings with lexical ties, per DATA-02);
    # only items without one fall back to the version-scoped lookup.
    return f"""
        SELECT d.item_id, coalesce(p.item_name, d.item_name, n.item_name, 'Item ' || d.item_id::VARCHAR)
                AS item_name,
            CASE WHEN p.min_buyout > 0 THEN p.min_buyout END AS min_buyout,
            CASE WHEN p.market_value > 0 THEN p.market_value END AS market_value, d.listings, d.units
        FROM (SELECT item_id, min(loaded_item_name(item_name)) AS item_name, count(*) AS listings,
                sum(quantity)::BIGINT AS units
            FROM scan_listings WHERE {predicate} AND scan_id=? AND snapshot_id=? GROUP BY item_id) d
        LEFT JOIN (SELECT item_id, loaded_item_name(item_name) AS item_name, min_buyout, market_value
            FROM market_snapshots WHERE {predicate} AND snapshot_id=?) p USING (item_id)
        LEFT JOIN item_names n ON n.game_version=? AND n.item_id=d.item_id
    """


def compare_scans(db, config: Mapping[str, Any], first_id: str, second_id: str,
                  item_ids: list[int] | None = None) -> dict:
    """Compare two eligible IDs chronologically; None means unavailable, never free.

    Only per-item aggregates cross into Python. New/vanished rows have a missing side
    and blank changes. A shared item is changed if any price or supply metric differs.
    An optional item-ID filter applies equally to all three lists.
    """
    scans = {scan["scan_id"]: scan for scan in eligible_scans(db, config)}
    if first_id == second_id or first_id not in scans or second_id not in scans:
        raise ValueError("Choose two distinct complete priced scans from the selected source and market")
    earlier, later = sorted((scans[first_id], scans[second_id]), key=lambda s: (s["finished_at"], s["scan_id"]))
    predicate, scope = scope_predicate(config)
    query = _scan_items_sql(predicate)
    parameters = []
    for scan in (earlier, later):
        parameters.extend([*scope, scan["scan_id"], scan["snapshot_id"], *scope, scan["snapshot_id"],
                           config["game_version"]])
    rows = db.execute(f"""WITH a AS ({query}), b AS ({query})
        SELECT coalesce(a.item_id, b.item_id), coalesce(b.item_name, a.item_name),
            a.min_buyout, a.market_value, a.listings, a.units,
            b.min_buyout, b.market_value, b.listings, b.units
        FROM a FULL OUTER JOIN b USING (item_id) ORDER BY item_id""", parameters).fetchall()
    result: dict = {"earlier": earlier, "later": later,
                    "gap": later["finished_at"] - earlier["finished_at"], "items": [], "new": [], "vanished": []}
    allowed = None if item_ids is None else set(item_ids)
    for item_id, name, *values in rows:
        if allowed is not None and item_id not in allowed:
            continue
        row = _diff_row(item_id, name, values)
        group = "new" if row["earlier"] is None else "vanished" if row["later"] is None else "items"
        result[group].append(row)
    return result


def _diff_row(item_id: int, name: str, values: list) -> dict:
    earlier = dict(zip(METRICS, values[:4], strict=True)) if values[2] is not None else None
    later = dict(zip(METRICS, values[4:], strict=True)) if values[6] is not None else None
    changes = {metric: None for metric in METRICS}
    if earlier is not None and later is not None:
        changes = {metric: later[metric] - earlier[metric]
                   if earlier[metric] is not None and later[metric] is not None else None for metric in METRICS}
    return {"item_id": item_id, "item_name": name, "earlier": earlier, "later": later,
            "change": changes, "changed": earlier != later}
