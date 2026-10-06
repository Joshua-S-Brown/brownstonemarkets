"""Versioned addon market measures. Rules: requirements.md → ADDON-10.

Calculations use listing quantities without expanding stacks into individual units.
Only aggregate counts leave seller calculations; seller strings remain local evidence.
"""
from collections.abc import Mapping
from typing import Any

import polars as pl

from .markets import MARKET_KEYS
from .variants import ITEM_KEYS

METRICS_VERSION = 1
SCAN_KEYS = ["source_id", *MARKET_KEYS, "scan_id", "snapshot_id"]
METRIC_KEYS = [*SCAN_KEYS, *ITEM_KEYS]
PRICE_COLUMNS = ("min_buyout", "unit_buyout_p10", "unit_buyout_p25", "unit_buyout_median")
COUNT_COLUMNS = ("units", "listings", "priced_units", "largest_stack_units", "seller_known_listings",
                 "seller_known_units", "seller_count", "top_seller_units")


def calculate_metrics(listings: pl.DataFrame) -> pl.DataFrame:
    """Exact counts and nullable prices: one raw scan, or fully scoped stored listings.

    Seller availability is determined by format-3 variant_state evidence. Legacy rows
    retain null seller measures even if a caller supplies a seller string accidentally.
    """
    scope_fields = set(SCAN_KEYS).intersection(listings.columns)
    if scope_fields and scope_fields != set(SCAN_KEYS):
        raise ValueError("Scoped listings require every source, market, scan and snapshot field")
    keys = METRIC_KEYS if scope_fields else ITEM_KEYS
    supply = listings.group_by(keys).agg(
        pl.col("quantity").sum().alias("units"), pl.len().cast(pl.Int64).alias("listings"),
        pl.col("quantity").max().alias("largest_stack_units"))
    priced = listings.filter(pl.col("unit_buyout_ceil") > 0).sort(*keys, "unit_buyout_ceil")
    ranked = priced.with_columns(
        pl.col("quantity").cum_sum().over(keys).alias("cumulative_units"),
        pl.col("quantity").sum().over(keys).alias("priced_units"))
    prices = ranked.group_by(keys).agg(
        pl.col("unit_buyout_ceil").min().alias("min_buyout"),
        pl.col("priced_units").first(),
        *[_percentile(p, name) for p, name in ((10, "unit_buyout_p10"), (25, "unit_buyout_p25"),
                                              (50, "unit_buyout_median"))])
    return (supply.join(prices, on=keys, how="left", nulls_equal=True)
            .join(_sellers(listings, keys), on=keys, how="left", nulls_equal=True)
            .with_columns(pl.col("priced_units").fill_null(0), pl.lit(METRICS_VERSION).alias("metrics_version"))
            .select(*keys, "metrics_version", *PRICE_COLUMNS, *COUNT_COLUMNS).sort(keys))


def _percentile(percent: int, name: str) -> pl.Expr:
    rank = (pl.col("priced_units") // 100) * percent + ((pl.col("priced_units") % 100) * percent + 99) // 100
    return pl.col("unit_buyout_ceil").filter(pl.col("cumulative_units") >= rank).min().alias(name)


def _sellers(listings: pl.DataFrame, keys: list[str]) -> pl.DataFrame:
    available = listings.filter(pl.col("variant_state").is_not_null()).select(keys).unique()
    known = listings.filter(pl.col("variant_state").is_not_null() & pl.col("seller").is_not_null()
                            & (pl.col("seller").str.strip_chars() != ""))
    sellers = known.group_by(*keys, "seller").agg(
        pl.col("quantity").sum().alias("seller_units"), pl.len().cast(pl.Int64).alias("seller_listings"))
    counts = sellers.group_by(keys).agg(
        pl.len().cast(pl.Int64).alias("seller_count"), pl.col("seller_units").max().alias("top_seller_units"),
        pl.col("seller_units").sum().alias("seller_known_units"),
        pl.col("seller_listings").sum().alias("seller_known_listings"))
    return available.join(counts, on=keys, how="left", nulls_equal=True).with_columns(
        pl.col("seller_known_units", "seller_known_listings").fill_null(0))


def _eligible_listings(db, scan: tuple[str, str] | None = None) -> pl.DataFrame:
    joins = " AND ".join(f"l.{k} IS NOT DISTINCT FROM s.{k}" for k in SCAN_KEYS)
    predicate = " AND s.source_id=? AND s.scan_id=?" if scan else ""
    # Never read seller strings into returned results, logs or reports: only this local calculator.
    return db.execute(f"SELECT l.* FROM scan_listings l JOIN addon_scans s ON {joins} "
                      "WHERE s.status='completed' AND NOT s.partial AND s.priced" + predicate,
                      list(scan) if scan else []).pl()


def store_scan_metrics(db, source_id: str, scan_id: str) -> None:
    """Compute one new scan inside the caller's import transaction."""
    _insert_metrics(db, calculate_metrics(_eligible_listings(db, (source_id, scan_id))))


def _metric_rows(frame: pl.DataFrame) -> pl.DataFrame:
    # Canonical structured key preserves NULL separately from every actual string, including
    # legacy/base states. No hash collision or delimiter ambiguity; all identity fields participate.
    return frame.with_columns(pl.struct("metrics_version", *METRIC_KEYS).struct.json_encode().alias("metric_key"))


def _insert_metrics(db, frame: pl.DataFrame, replace: bool = False) -> None:
    db.register("_calculated_scan_metrics", _metric_rows(frame).to_arrow())
    try:
        command = "INSERT OR REPLACE" if replace else "INSERT"
        db.execute(f"{command} INTO scan_metrics BY NAME SELECT * FROM _calculated_scan_metrics")
    finally:
        db.unregister("_calculated_scan_metrics")


def rebuild_scan_metrics(db) -> int:
    """Atomically replace v1 metrics from stored listings; owns its transaction.

    Call on an upgraded database outside any existing write transaction. Returns row count.
    Initialization uses this same path, including retries after an interrupted backfill.
    """
    db.execute("BEGIN TRANSACTION")
    try:
        frame = calculate_metrics(_eligible_listings(db))
        # Upsert first: DuckDB cannot delete/reinsert an indexed key in one transaction.
        # Then remove identities no longer supported by the eligible listing evidence.
        _insert_metrics(db, frame, replace=True)
        db.register("_rebuilt_metric_keys", _metric_rows(frame).select("metric_key").to_arrow())
        try:
            db.execute("DELETE FROM scan_metrics WHERE metrics_version=? AND metric_key NOT IN "
                       "(SELECT metric_key FROM _rebuilt_metric_keys)", [METRICS_VERSION])
        finally:
            db.unregister("_rebuilt_metric_keys")
        db.execute("INSERT OR REPLACE INTO schema_info VALUES ('metrics_version', ?)", [str(METRICS_VERSION)])
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK")
        raise
    return frame.height


def initialize_metrics(db) -> None:
    """Separate derived-data backfill from frozen schema migrations."""
    row = db.execute("SELECT value FROM schema_info WHERE key='metrics_version'").fetchone()
    if row is None or row[0] != str(METRICS_VERSION):
        rebuild_scan_metrics(db)


def _scope(config: Mapping[str, Any], snapshot_id: str) -> tuple[str, list[Any]]:
    keys = ["source_id", *MARKET_KEYS]
    return " AND ".join(f"{k}=?" for k in keys) + " AND snapshot_id=?", [*[config[k] for k in keys], snapshot_id]


def _scan(db, config: Mapping[str, Any], snapshot_id: str) -> tuple[str, list[Any]] | None:
    # Config validates scan evidence using scans.py; defer this import to avoid that cycle.
    from .config import ADDON_PROVIDER

    if config["provider"] != ADDON_PROVIDER:
        return None
    predicate, parameters = _scope(config, snapshot_id)
    row = db.execute(f"SELECT scan_id FROM addon_scans WHERE {predicate} "
                     "AND status='completed' AND NOT partial AND priced", parameters).fetchone()
    return (predicate + " AND scan_id=?", [*parameters, row[0]]) if row else None


def read_scan_metrics(db, config: Mapping[str, Any], snapshot_id: str) -> list[dict] | None:
    """All exact item identities in one eligible scan; null means unavailable.

    Shares are returned as numerator/denominator counts, with explicit coverage counts.
    Empty results mean no listed identities, never a missing price encoded as zero.
    """
    scope = _scan(db, config, snapshot_id)
    if scope is None:
        return None
    predicate, parameters = scope
    columns = [*ITEM_KEYS, *PRICE_COLUMNS, *COUNT_COLUMNS, "metrics_version"]
    rows = db.execute(f"SELECT {', '.join(columns)} FROM scan_metrics WHERE {predicate} "
                      "AND metrics_version=? ORDER BY item_id, variant_state, variant_id",
                      [*parameters, METRICS_VERSION]).fetchall()
    return [_with_shares(dict(zip(columns, row, strict=True))) for row in rows]


def _ratio(numerator: int | None, denominator: int) -> dict[str, int] | None:
    return {"numerator": numerator, "denominator": denominator} if numerator is not None and denominator else None


def _with_shares(row: dict) -> dict:
    return {**row, "largest_stack_share": _ratio(row["largest_stack_units"], row["units"]),
            "top_seller_share": _ratio(row["top_seller_units"], row["seller_known_units"]),
            "seller_listing_coverage": _ratio(row["seller_known_listings"], row["listings"]),
            "seller_unit_coverage": _ratio(row["seller_known_units"], row["units"])}


def units_below_price(db, config: Mapping[str, Any], snapshot_id: str, item_id: int,
                      price_copper: int, variant_id: str | None = None,
                      variant_state: str | None = None) -> int | None:
    """Strictly below threshold, exact identity (null state selects legacy only)."""
    if type(price_copper) is not int or price_copper <= 0:
        raise ValueError("price_copper must be a positive integer")
    scope = _scan(db, config, snapshot_id)
    if scope is None:
        return None
    predicate, parameters = scope
    row = db.execute(f"SELECT coalesce(sum(quantity), 0) FROM scan_listings WHERE {predicate} "
                     "AND item_id=? AND variant_id IS NOT DISTINCT FROM ? "
                     "AND variant_state IS NOT DISTINCT FROM ? AND unit_buyout_ceil > 0 AND unit_buyout_ceil < ?",
                     [*parameters, item_id, variant_id, variant_state, price_copper]).fetchone()
    return int(row[0])
