"""One CSV -> immutable bronze -> validated silver -> DuckDB -> gold."""
from __future__ import annotations

import hashlib
import io
import json
import re
import tomllib
import uuid
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import polars as pl
import pyarrow.parquet as pq
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

PRICE_COLUMNS = {
    "marketValue": "market_value", "minBuyout": "min_buyout",
    "recent": "recent_value", "historical": "historical_value",
}
REQUIRED = {"itemId", "name", "updatedAt", *PRICE_COLUMNS}


def read_config(path: Path) -> dict:
    path = path.resolve()
    with path.open("rb") as file:
        config = tomllib.load(file)
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", config["market_id"]):
        raise ValueError("market_id must contain only letters, numbers, underscores or hyphens")
    if not config["source_url"].startswith("https://"):
        raise ValueError("source_url must use HTTPS")
    if config["max_age_hours"] <= 0 or config["top_n"] <= 0:
        raise ValueError("max_age_hours and top_n must be positive")
    if not 0 <= config["auction_cut"] < 1 or not 0 <= config["min_discount"] < 1:
        raise ValueError("auction_cut and min_discount must be in [0, 1)")
    # Paths are relative to the project, never the caller's working directory.
    config["data_dir"] = (path.parent.parent / config["data_dir"]).resolve()
    return config


def download(url: str) -> bytes:
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    with requests.Session() as session:
        session.mount("https://", HTTPAdapter(max_retries=retry))
        response = session.get(url, timeout=(10, 60), headers={"User-Agent": "BrownstoneMarkets/0.1"})
        response.raise_for_status()
        if not response.content or len(response.content) > 100_000_000:
            raise ValueError("Empty or oversized source CSV")
        return response.content


def normalize(raw: bytes, market_id: str, snapshot_id: str, collected_at: datetime,
              max_age_hours: float) -> pl.DataFrame:
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
    if any(frame.null_count().row(0)):
        raise ValueError("Required fields cannot be null")
    if frame["item_id"].n_unique() != frame.height:
        raise ValueError("Duplicate item IDs in snapshot")
    if frame.filter(pl.col("item_id") <= 0).height:
        raise ValueError("Item IDs must be positive")
    if frame.filter(pl.any_horizontal([pl.col(c) < 0 for c in PRICE_COLUMNS.values()])).height:
        raise ValueError("Prices must be nonnegative integer copper")
    if frame["updated_at"].n_unique() != 1:
        raise ValueError("Expected a single upstream timestamp per file")
    age = (collected_at - frame["updated_at"][0]).total_seconds() / 3600
    if age > max_age_hours or age < -0.25:
        raise ValueError(f"Upstream timestamp is stale or in the future (age={age:.2f}h)")
    # Zero is preserved as unavailable/no listing, then excluded from ranking.
    return frame.with_columns(
        pl.lit(market_id).alias("market_id"),
        pl.lit(snapshot_id).alias("snapshot_id"),
        pl.lit(collected_at).alias("collected_at"),
    )


def rank(connection: duckdb.DuckDBPyConnection, snapshot_id: str, config: dict) -> pl.DataFrame:
    return connection.execute("""
        WITH price_references AS (
            SELECT *, least(market_value, recent_value, historical_value) AS reference_copper
            FROM market_snapshots WHERE snapshot_id = ?
              AND min_buyout > 0 AND market_value > 0 AND recent_value > 0 AND historical_value > 0
        ), candidates AS (
            SELECT *, 1.0 - min_buyout::DOUBLE / reference_copper AS discount,
                reference_copper * (1 - ?) - min_buyout AS net_spread_copper
            FROM price_references
        )
        SELECT row_number() OVER (ORDER BY discount DESC, net_spread_copper DESC, item_id) AS rank,
            snapshot_id, market_id, item_id, item_name, updated_at,
            min_buyout, reference_copper, discount, net_spread_copper,
            min_buyout / 10000.0 AS buy_gold,
            net_spread_copper / 10000.0 AS net_spread_gold
        FROM candidates WHERE discount >= ? AND net_spread_copper > 0
        ORDER BY rank LIMIT ?
    """, [snapshot_id, config["auction_cut"], config["min_discount"], config["top_n"]]).pl()


def run(config: dict, input_path: Path | None = None) -> tuple[pl.DataFrame, Path]:
    raw = input_path.read_bytes() if input_path else download(config["source_url"])
    now = datetime.now(timezone.utc)
    sid = now.strftime("%Y%m%dT%H%M%S%fZ") + "_" + uuid.uuid4().hex[:8]
    base = Path(config["data_dir"])
    folders = {layer: base / layer / config["market_id"] for layer in ("bronze", "silver", "gold")}
    for folder in folders.values():
        folder.mkdir(parents=True, exist_ok=True)
    bronze = folders["bronze"] / f"{sid}.csv"
    with bronze.open("xb") as file:
        file.write(raw)
    manifest = {
        "snapshot_id": sid, "market_id": config["market_id"], "collected_at": now.isoformat(),
        "source": str(input_path.resolve()) if input_path else config["source_url"],
        "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "status": "received",
    }
    metadata = bronze.with_suffix(".json")
    try:
        frame = normalize(raw, config["market_id"], sid, now, config["max_age_hours"])
        silver = folders["silver"] / f"{sid}.parquet"
        pq.write_table(frame.to_arrow(), silver, compression="zstd")
        with duckdb.connect(str(base / "brownstone.duckdb")) as db:
            db.execute("CREATE TABLE IF NOT EXISTS market_snapshots AS SELECT * FROM read_parquet(?) LIMIT 0", [str(silver)])
            db.begin()
            db.execute("INSERT INTO market_snapshots SELECT * FROM read_parquet(?)", [str(silver)])
            result = rank(db, sid, config)
            db.commit()
        gold = folders["gold"] / f"{sid}_opportunities.csv"
        result.write_csv(gold)
        pq.write_table(result.to_arrow(), gold.with_suffix(".parquet"), compression="zstd")
        manifest.update(status="complete", rows=frame.height, opportunities=result.height,
                        updated_at=frame["updated_at"][0].isoformat(),
                        zero_price_rows=frame.filter(pl.any_horizontal([pl.col(c) == 0 for c in PRICE_COLUMNS.values()])).height,
                        missing_name_rows=pl.read_csv(io.BytesIO(raw), infer_schema=False).filter(
                            pl.col("name").is_null() | (pl.col("name") == "")).height)
    except Exception as error:
        manifest.update(status="failed", error=str(error))
        raise
    finally:
        metadata.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return result, gold
