import io
from datetime import datetime
import polars as pl
PRICE_COLUMNS = {"marketValue": "market_value", "minBuyout": "min_buyout", "recent": "recent_value", "historical": "historical_value"}
REQUIRED = {"itemId", "name", "updatedAt", *PRICE_COLUMNS}


def normalize(raw: bytes, market_id: str, snapshot_id: str, collected_at: datetime,
              max_age_hours: float, allow_missing_updated_at: bool = False) -> pl.DataFrame:
    frame = pl.read_csv(io.BytesIO(raw), infer_schema=False)
    missing = REQUIRED - set(frame.columns)
    if missing:
        raise ValueError(f"Missing source columns: {sorted(missing)}")
    if frame.is_empty():
        raise ValueError("Source has no rows")
    frame = frame.select(
        pl.col("itemId").cast(pl.Int64, strict=True).alias("item_id"),
        pl.when(pl.col("name").is_null() | (pl.col("name") == ""))
        .then(pl.concat_str([pl.lit("Item "), pl.col("itemId")]))
        .otherwise(pl.col("name")).alias("item_name"),
        *[pl.col(src).cast(pl.Int64, strict=True).alias(dst) for src, dst in PRICE_COLUMNS.items()],
        pl.col("updatedAt").str.to_datetime(time_zone="UTC", strict=True).alias("updated_at"),
    )
    required_values = ["item_id", "item_name", *PRICE_COLUMNS.values()]
    if any(frame.select(required_values).null_count().row(0)):
        raise ValueError("Required fields cannot be null")
    if frame["item_id"].n_unique() != frame.height:
        raise ValueError("Duplicate item IDs in snapshot")
    if frame.filter(pl.col("item_id") <= 0).height:
        raise ValueError("Item IDs must be positive")
    if frame.filter(pl.any_horizontal([pl.col(c) < 0 for c in PRICE_COLUMNS.values()])).height:
        raise ValueError("Prices must be nonnegative integer copper")
    timestamp_nulls = frame["updated_at"].null_count()
    if timestamp_nulls == frame.height:
        if not allow_missing_updated_at:
            raise ValueError("Required fields cannot be null")
    elif timestamp_nulls:
        raise ValueError("Upstream timestamps must be either complete or entirely unavailable")
    elif frame["updated_at"].n_unique() != 1:
        raise ValueError("Expected a single upstream timestamp per file")
    if timestamp_nulls == 0:
        age = (collected_at - frame["updated_at"][0]).total_seconds() / 3600
        if age > max_age_hours or age < -0.25:
            raise ValueError(f"Upstream timestamp is stale or in the future (age={age:.2f}h)")
    # Zero is preserved as unavailable/no listing, then excluded from ranking.
    return frame.with_columns(
        pl.lit(market_id).alias("market_id"),
        pl.lit(snapshot_id).alias("snapshot_id"),
        pl.lit(collected_at).alias("collected_at"),
    )
