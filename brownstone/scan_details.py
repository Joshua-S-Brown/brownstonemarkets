"""Format-3 reference observations and capture-availability measurements (local only)."""
import math
from typing import Any

import polars as pl

from . import variants

EXTRA_FIELDS = ("seller_index", "time_left", "quality", "level", "level_type_index", "link_index")
LISTING_DETAILS = {"seller": pl.String, "time_left": pl.Int64, "quality": pl.Int64,
                   "level": pl.Int64, "level_type": pl.String, "required_level": pl.Int64,
                   "item_link": pl.String, "variant_id": pl.String, "variant_state": pl.String}
# Level types meaning "required level": modern clients report REQ_LEVEL, the Classic auction UI's
# column header is REQ_LEVEL_ABBR. Any other type keeps required_level null; level_type stays raw.
REQUIRED_LEVEL_TYPES = ("REQ_LEVEL", "REQ_LEVEL_ABBR")
# Valid optional values (inclusive). Out-of-range values become missing and are counted, so one odd
# client value never rejects a whole scan; the raw string stays in bronze.
OPTIONAL_RANGES = {"time_left": (1, 4), "quality": (0, 8), "level": (0, None)}
ITEM_SCHEMA = {"item_id": pl.Int64, "class_id": pl.Int64, "subclass_id": pl.Int64,
               "item_level": pl.Int64, "max_stack_size": pl.Int64, "vendor_sell_copper": pl.Int64}


def text_list(scan: dict, key: str) -> list[str]:
    values = scan.get(key, [])
    if values == {}:
        values = []
    if not isinstance(values, list) or not all(isinstance(v, str) and v.strip() for v in values):
        raise ValueError(f"{key} must be a list of nonblank text")
    return values


def indexed_text(scan: dict, fields: pl.DataFrame, index: str, table: str, name: str) -> pl.Expr:
    values = text_list(scan, table)
    if fields.filter(pl.col(index).is_null() | (pl.col(index) < 0) | (pl.col(index) > len(values))).height:
        raise ValueError(f"{index} is outside the scan's {table}")
    return pl.col(index).replace_strict(dict(enumerate(values, 1)), default=None, return_dtype=pl.String).alias(name)


def _in_range(key: str) -> pl.Expr:
    low, high = OPTIONAL_RANGES[key]
    valid = pl.col(key) >= low
    return valid & (pl.col(key) <= high) if high is not None else valid


def listing_details(scan: dict, fields: pl.DataFrame) -> pl.DataFrame:
    frame = fields.select("item_id",
                          *[pl.when(_in_range(key)).then(pl.col(key)).alias(key) for key in OPTIONAL_RANGES],
                          indexed_text(scan, fields, "seller_index", "sellers", "seller"),
                          indexed_text(scan, fields, "level_type_index", "level_types", "level_type"),
                          indexed_text(scan, fields, "link_index", "links", "item_link"))
    return frame.with_columns(
        pl.when(pl.col("level_type").is_in(REQUIRED_LEVEL_TYPES)).then(pl.col("level")).alias("required_level"),
        *variants.columns(frame["item_id"].to_list(), frame["item_link"].to_list()),
    ).drop("item_id")


def out_of_range(fields: pl.DataFrame) -> dict[str, int]:
    """Reported optional values outside OPTIONAL_RANGES (stored as missing)."""
    return {key: fields.filter(pl.col(key).is_not_null() & ~_in_range(key)).height for key in OPTIONAL_RANGES}


def item_frame(scan: dict) -> pl.DataFrame:
    """One nullable observation per item per scan; no historical/cache backfill."""
    rows = scan.get("items", []) if scan.get("schema_version") == 3 else []
    if rows == {}:
        rows = []
    if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
        raise ValueError("items must be a list of item tables")
    if any(type(r.get(k)) is not int for r in rows for k in ITEM_SCHEMA if r.get(k) is not None):
        raise ValueError("item fields must be integers")
    try:
        frame = pl.DataFrame({k: [r.get(k) for r in rows] for k in ITEM_SCHEMA}, schema=ITEM_SCHEMA, strict=True)
    except (TypeError, pl.exceptions.PolarsError) as error:
        raise ValueError("item fields must be integers") from error
    if frame["item_id"].n_unique() != frame.height:
        raise ValueError("duplicate item reference ID")
    bad = pl.col("item_id").is_null() | (pl.col("item_id") <= 0) | (pl.col("max_stack_size") <= 0)
    for key in ITEM_SCHEMA:
        bad = bad | (pl.col(key) < 0)
    if frame.filter(bad).height:
        raise ValueError("invalid item reference value")
    return frame


def duration(scan: dict) -> float | None:
    value = scan.get("duration_seconds")
    if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
        raise ValueError("duration_seconds must be finite and nonnegative")
    return float(value) if value is not None else None


def availability(listings: pl.DataFrame, items: pl.DataFrame,
                 rejected: dict[str, int] | None = None) -> dict[str, Any]:
    """Only counts leave capture analysis; never seller values or links."""
    return {"listing_total": listings.height, "item_total": items.height,
            "listing_out_of_range": rejected or dict.fromkeys(OPTIONAL_RANGES, 0),
            "listing_available": {k: listings[k].drop_nulls().len()
                                  for k in LISTING_DETAILS if k not in ("variant_id", "variant_state")},
            "item_available": {k: items[k].drop_nulls().len() for k in ITEM_SCHEMA if k != "item_id"},
            "variant_states": {state: listings.filter(pl.col("variant_state") == state).height
                               for state in ("base", "variant", "unresolved")}}
