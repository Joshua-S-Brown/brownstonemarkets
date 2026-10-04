"""Orchestrate one source; reusable operations live in focused modules."""
import hashlib
import io
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
import duckdb
import polars as pl
import pyarrow.parquet as pq
from .config import read_config
from .sources import download
from .normalization import normalize, PRICE_COLUMNS
from .analysis import rank
from .storage import load_snapshot


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
        frame = frame.with_columns(
            *[pl.lit(config.get(key), dtype=pl.String).alias(key)
              for key in ["game_version", "region", "scope", "realm"]],
            pl.lit(manifest["sha256"]).alias("source_sha256"),
        )
        silver = folders["silver"] / f"{sid}.parquet"
        pq.write_table(frame.to_arrow(), silver, compression="zstd")
        with duckdb.connect(str(base / "brownstone.duckdb")) as db:
            db.begin()
            analytical_sid, inserted = load_snapshot(db, silver, frame, config)
            result = rank(db, analytical_sid, config)
            db.commit()
        gold = folders["gold"] / f"{sid}_opportunities.csv"
        result.write_csv(gold)
        pq.write_table(result.to_arrow(), gold.with_suffix(".parquet"), compression="zstd")
        manifest.update(status="complete", rows=frame.height, opportunities=result.height,
                        analytical_snapshot_id=analytical_sid, new_observation=inserted,
                        **{key: config.get(key) for key in ["game_version", "region", "scope", "realm"]},
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
