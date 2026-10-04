"""Orchestrate one source; reusable operations live in focused modules."""
import gzip
import hashlib
import io
import json
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import polars as pl
import pyarrow.parquet as pq

from . import scans
from .analysis import rank
from .config import ADDON_PROVIDER, MARKET_KEYS, Source
from .freshness import FUTURE_TOLERANCE_HOURS
from .normalization import PRICE_COLUMNS, normalize
from .sources import download
from .storage import known_scan, load_scan, load_snapshot, upgrade_database


def _collection_id(now: datetime) -> str:
    return now.strftime("%Y%m%dT%H%M%S%fZ") + "_" + uuid.uuid4().hex[:8]


def _folders(config: Source, layers: Iterable[str]) -> dict[str, Path]:
    folders = {layer: Path(config["data_dir"]) / layer / config["source_id"] for layer in layers}
    for folder in folders.values():
        folder.mkdir(parents=True, exist_ok=True)
    return folders


def _observation_keys(config: Source) -> dict[str, str]:
    """The source and full market identity that every stored price and listing row carries."""
    return {"source_id": config["source_id"], **{key: config[key] for key in MARKET_KEYS}}  # type: ignore[literal-required]


def _identity(config: Source) -> dict:
    """Who observed (source) and which auction house (market); recorded even if validation fails."""
    return {"source_id": config["source_id"], "provider": config["provider"], **_observation_keys(config)}


def run(config: Source, input_path: Path | None = None) -> tuple[pl.DataFrame, Path]:
    if config["provider"] == ADDON_PROVIDER:
        raise ValueError(f"{config['source_id']} is an addon source; use import_scans")
    raw = input_path.read_bytes() if input_path else download(config["source_url"])
    now = datetime.now(UTC)
    sid = _collection_id(now)
    base = Path(config["data_dir"])
    folders = _folders(config, ("bronze", "silver", "gold"))
    bronze = folders["bronze"] / f"{sid}.csv"
    with bronze.open("xb") as file:
        file.write(raw)
    identity = _identity(config)
    manifest = {
        "snapshot_id": sid, **identity, "collected_at": now.isoformat(),
        "source": str(input_path.resolve()) if input_path else config["source_url"],
        "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "status": "received",
    }
    metadata = bronze.with_suffix(".json")
    try:
        frame = normalize(
            raw, config["market_id"], sid, now, config["max_age_hours"],
            config.get("allow_missing_updated_at", False),
        )
        frame = frame.with_columns(
            *[pl.lit(value, dtype=pl.String).alias(key) for key, value in _observation_keys(config).items()],
            pl.lit(manifest["sha256"]).alias("source_sha256"),
        )
        silver = folders["silver"] / f"{sid}.parquet"
        pq.write_table(frame.to_arrow(), silver, compression="zstd")
        upgrade_database(base, create=True)
        with duckdb.connect(str(base / "brownstone.duckdb")) as db:
            db.begin()
            analytical_sid, inserted = load_snapshot(db, silver, frame, config)
            result = rank(db, analytical_sid, config)
            db.commit()
        gold = folders["gold"] / f"{sid}_opportunities.csv"
        result.write_csv(gold)
        pq.write_table(result.to_arrow(), gold.with_suffix(".parquet"), compression="zstd")
        upstream_time = frame["updated_at"][0]
        manifest.update(status="complete", rows=frame.height, opportunities=result.height,
                        analytical_snapshot_id=analytical_sid, new_observation=inserted,
                        updated_at=upstream_time.isoformat() if upstream_time else None,
                        freshness_basis="upstream" if upstream_time else "collected_at",
                        zero_price_rows=frame.filter(
                            pl.any_horizontal([pl.col(c) == 0 for c in PRICE_COLUMNS.values()])).height,
                        missing_name_rows=pl.read_csv(io.BytesIO(raw), infer_schema=False).filter(
                            pl.col("name").is_null() | (pl.col("name") == "")).height)
    except Exception as error:
        manifest.update(status="failed", error=str(error))
        raise
    finally:
        metadata.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return result, gold


def _bronze_copy(folder: Path, sid: str, raw: bytes, sha256: str) -> str:
    """Store the file's bytes once per source, gzip-compressed; a repeat import of identical bytes reuses that file.

    Compression is lossless: the copy is checked to decompress to bytes with the original SHA-256 before it is kept
    (DATA-01). Files stored before compression stay as plain ``.lua``.
    """
    for path in sorted(folder.glob("*.json")):
        try:
            earlier = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        name = earlier.get("bronze_file")
        if earlier.get("sha256") == sha256 and name and (folder / name).is_file():
            return name
    packed = gzip.compress(raw, compresslevel=6, mtime=0)
    if hashlib.sha256(gzip.decompress(packed)).hexdigest() != sha256:
        raise RuntimeError("The compressed copy of the scan file did not round-trip; nothing was stored")
    name = f"{sid}.lua.gz"
    with (folder / name).open("xb") as file:
        file.write(packed)
    return name


def import_scans(config: Source, input_path: Path | None = None, scan_ids: Iterable[str] | None = None,
                 now: datetime | None = None) -> dict:
    """Import BrownstoneScan SavedVariables for an addon source; returns the collection manifest.

    Reads ``input_path`` or the configured ``scan_path`` and never writes to it. Every scan must match
    the configured market's house evidence, or nothing is imported. Scans are deduplicated by scan_id per
    source. Partial scans are stored and labeled but never priced. The newest complete scan in the file
    becomes the collection's analytical snapshot, aged from its finish time.
    """
    if config["provider"] != ADDON_PROVIDER:
        raise ValueError(f"{config['source_id']} is not an addon source")
    path = Path(input_path or config["scan_path"])
    raw = path.read_bytes()
    now = now or datetime.now(UTC)
    sid = _collection_id(now)
    base = Path(config["data_dir"])
    folders = _folders(config, ("bronze", "silver"))
    sha256 = hashlib.sha256(raw).hexdigest()
    bronze_file = _bronze_copy(folders["bronze"], sid, raw, sha256)
    identity = _identity(config)
    manifest: dict = {
        "snapshot_id": sid, **identity, "collected_at": now.isoformat(), "source": str(path.resolve()),
        "bronze_file": bronze_file, "sha256": sha256, "bytes": len(raw), "status": "received",
    }
    try:
        records = _select_scans(scans.read_saved_variables(raw), scan_ids)
        summaries = _check_scans(records, config, now)
        upgrade_database(base, create=True)
        results = []
        with duckdb.connect(str(base / "brownstone.duckdb")) as db:
            db.begin()
            for record, summary in zip(records, summaries, strict=True):
                results.append(_import_scan(db, config, folders["silver"], sid, now, sha256, record, summary))
            db.commit()
        manifest["scans"] = results
        # Scans the addon still holds from earlier imports; /bscan clear in game keeps the next file small.
        manifest["already_imported"] = sum(result["outcome"] == "duplicate" for result in results)
        priced = [result for result in results if result["priced"]]
        if priced:
            latest = max(priced, key=lambda result: result["finished_at"])
            manifest.update(status="complete", analytical_snapshot_id=latest["snapshot_id"],
                            scan_id=latest["scan_id"], rows=latest["items"], updated_at=latest["finished_at"],
                            freshness_basis="upstream", new_observation=latest["outcome"] == "imported")
        else:
            # Nothing priceable (only partial or empty scans): not offered to the views as a snapshot.
            manifest.update(status="no_complete_scan")
    except Exception as error:
        manifest.update(status="failed", error=str(error))
        raise
    finally:
        (folders["bronze"] / f"{sid}.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def clear_reminder(manifest: dict) -> str | None:
    """After an import, suggest clearing the addon's file when it still holds scans imported before.

    The addon keeps every scan until /bscan clear, and each import reads the whole file, so old scans
    only cost time and disk. Everything in the file is stored once an import succeeds.
    """
    count = manifest.get("already_imported", 0)
    if not count:
        return None
    return (f"{count} scan(s) in this file were already imported before. Everything in it is now saved, so you can "
            "type /bscan clear in game, then /reload, to keep the next file small.")


def _select_scans(records: list[dict], scan_ids: Iterable[str] | None) -> list[dict]:
    """The file's scans, or only the requested ones; an unknown scan ID fails the import."""
    if scan_ids is not None:
        wanted = list(scan_ids)
        unknown = set(wanted) - {record.get("scan_id") for record in records}
        if unknown:
            raise ValueError(f"Scan(s) not in this file: {sorted(unknown)}")
        records = [record for record in records if record.get("scan_id") in wanted]
    if not records:
        raise ValueError("No scans to import")
    return records


def _check_scans(records: list[dict], config: Source, now: datetime) -> list[dict]:
    """Validate every scan before anything is stored: header, house evidence and clock (ADDON-01, ADDON-05)."""
    summaries = [scans.summarize(record) for record in records]
    problems = [problem for record in records for problem in scans.check_house(record, config)]
    if problems:
        raise ValueError("Scan does not match the configured market " + config["market_id"] + ": "
                         + "; ".join(problems))
    for summary in summaries:
        if summary["finished_at"] > now + timedelta(hours=FUTURE_TOLERANCE_HOURS):
            raise ValueError(f"Scan {summary['scan_id']} finished in the future ({summary['finished_at']}); "
                             "check the computer's clock")
    return summaries


def _import_scan(db, config: Source, silver: Path, sid: str, now: datetime, sha256: str,
                 record: dict, summary: dict) -> dict:
    """Store one scan unless this source already has it; return its manifest entry."""
    result = {key: summary[key] for key in ("scan_id", "status", "stop_reason", "partial",
                                             "listing_count", "reported_count")}
    result["finished_at"] = summary["finished_at"].isoformat()
    existing = known_scan(db, config["source_id"], summary["scan_id"])
    if existing:
        if existing["scan_sha256"] != summary["scan_sha256"]:
            raise ValueError(f"Scan {summary['scan_id']} was imported before with different content")
        return {**result, "outcome": "duplicate", "snapshot_id": existing["snapshot_id"],
                "priced": bool(existing["priced"]), "items": existing["item_count"]}
    snapshot_id = f"{config['source_id']}:{summary['scan_id']}"
    identity = {**_observation_keys(config), "snapshot_id": snapshot_id}
    listings = scans.listing_frame(record)
    priced = not summary["partial"] and listings.height > 0
    prices = scans.item_prices(listings) if priced else None
    stem = silver / f"{sid}_{summary['scan_id']}"
    columns = [pl.lit(value, dtype=pl.String).alias(key) for key, value in identity.items()]
    pq.write_table(listings.with_columns(pl.lit(summary["scan_id"]).alias("scan_id"), *columns).to_arrow(),
                   f"{stem}_listings.parquet", compression="zstd")
    prices_path = None
    if prices is not None:
        prices_path = Path(f"{stem}_prices.parquet")
        pq.write_table(prices.with_columns(
            *columns, pl.lit(summary["finished_at"]).alias("updated_at"), pl.lit(now).alias("collected_at"),
            pl.lit(sha256).alias("source_sha256")).to_arrow(), prices_path, compression="zstd")
    scan_row = {key: value for key, value in summary.items() if key not in ("neutral", "errors")}
    scan_row.update(identity, priced=priced, nonexact_stacks=scans.nonexact_stacks(listings),
                    item_count=prices.height if prices is not None else None, source_sha256=sha256,
                    collection_id=sid, collected_at=now)
    scan_path = Path(f"{stem}_scan.parquet")
    pq.write_table(pl.DataFrame([scan_row]).with_columns(pl.col(pl.Null).cast(pl.String)).to_arrow(), scan_path)
    load_scan(db, scan_path, Path(f"{stem}_listings.parquet"), prices_path)
    outcome = "imported" if priced else "empty" if listings.height == 0 else "partial (not priced)"
    return {**result, "outcome": outcome, "snapshot_id": snapshot_id, "priced": priced,
            "items": scan_row["item_count"], "nonexact_stacks": scan_row["nonexact_stacks"],
            "errors": summary["errors"]}
