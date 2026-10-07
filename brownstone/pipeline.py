"""Orchestrate one source; reusable operations live in focused modules."""
import gzip
import hashlib
import io
import json
import os
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import polars as pl
import pyarrow.parquet as pq

from . import scan_details, scans
from .analysis import rank
from .config import ADDON_PROVIDER, MARKET_KEYS, Source
from .freshness import FUTURE_TOLERANCE_HOURS
from .item_names import remember_local_catalog_names
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


# A hard cap bounds memory and makes an unexpectedly large/repeated scan file retryable.
MAX_SCAN_BYTES = 256 * 1024 * 1024


class StalePreviewError(ValueError):
    """The reviewed preparation no longer describes this import."""


@dataclass
class ScanPreview:
    """Read-only preparation; retain exact bytes and configuration, not a path to reread later."""
    raw: bytes
    configuration: str
    records: list[dict]
    summaries: list[dict]
    known: list[dict | None]
    # Per scan: why it is from another auction house than this source's market; empty when it matches.
    mismatches: list[list[str]]

    @property
    def new_ids(self) -> list[str]:
        return [s["scan_id"] for s, existing, mismatch in zip(self.summaries, self.known, self.mismatches,
                                                              strict=True) if existing is None and not mismatch]


def preview_configuration(config: Source, path: Path | None = None) -> str:
    """Session identity includes source, market, evidence, input and destination configuration."""
    return json.dumps({**config, "input_path": str(Path(path or config["scan_path"]).resolve())},
                      sort_keys=True, default=str)


def _file_signature(stat: os.stat_result) -> tuple[int, ...]:
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def _read_scan_bytes(path: Path) -> bytes:
    """Bounded read with best-effort detection of replacement or writes; not an atomic snapshot.

    Descriptor and path stats are each compared only with themselves: on Windows, ``os.fstat`` and
    ``Path.stat`` use different APIs and can disagree about an unchanged file.
    """
    path_before = _file_signature(path.stat())
    with path.open("rb") as file:
        before = _file_signature(os.fstat(file.fileno()))
        raw = file.read(MAX_SCAN_BYTES + 1)
        after = _file_signature(os.fstat(file.fileno()))
    if len(raw) > MAX_SCAN_BYTES:
        raise ValueError("Scan file exceeds the 256 MiB read limit; retry with a smaller saved file")
    if before != after or path_before != _file_signature(path.stat()) or len(raw) != after[2]:
        raise ValueError("Scan file changed while reading; wait for /reload or logout to finish and Preview again")
    return raw


def _known_scans(db, config: Source, summaries: list[dict]) -> list[dict | None]:
    # Older schemas may lack addon_scans. Preview never migrates them.
    if not db.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='addon_scans'").fetchone()[0]:
        return [None] * len(summaries)
    return [known_scan(db, config, summary["scan_id"]) for summary in summaries]


def _read_known(config: Source, summaries: list[dict]) -> list[dict | None]:
    path = Path(config["data_dir"]) / "brownstone.duckdb"
    if not path.exists():
        return [None] * len(summaries)
    with duckdb.connect(str(path), read_only=True) as db:
        return _known_scans(db, config, summaries)


def _check_conflicts(summaries: list[dict], known: list[dict | None]) -> None:
    for summary, existing in zip(summaries, known, strict=True):
        if existing and existing["scan_sha256"] != summary["scan_sha256"]:
            raise ValueError(f"Scan {summary['scan_id']} conflict: was imported before with different content")


def preview_scans(config: Source, input_path: Path | None = None, now: datetime | None = None) -> ScanPreview:
    """Validate and classify without creating files, directories, manifests or a database.

    Preview validates every file scan's header, time and listings. A scan from another auction house
    (account-wide SavedVariables hold every character's scans) is listed as not importable instead of
    failing the file; explicit CLI imports validate only their selected scans.
    """
    if config["provider"] != ADDON_PROVIDER:
        raise ValueError(f"{config['source_id']} is not an addon source")
    raw = _read_scan_bytes(Path(input_path or config["scan_path"]))
    records = _select_scans(scans.read_saved_variables(raw), None)
    summaries = _validate_scans(records, now or datetime.now(UTC))
    known = _read_known(config, summaries)
    _check_conflicts(summaries, known)
    mismatches = [scans.check_house(record, config) for record in records]
    return ScanPreview(raw, preview_configuration(config, input_path), records, summaries, known, mismatches)


def _prepare_scans(records: list[dict], config: Source, now: datetime,
                   scan_ids: Iterable[str] | None) -> tuple[list[dict], list[dict]]:
    """Shared UI/CLI selection, then header, house, time and listing validation of the selection."""
    records = _select_scans(records, scan_ids)
    summaries = _check_scans(records, config, now)
    return records, summaries


def _reviewed_preparation(config: Source, path: Path, scan_ids: Iterable[str] | None,
                          now: datetime, reviewed: ScanPreview, include_duplicates: bool = False) -> ScanPreview:
    current = preview_scans(config, path, now)
    if (current.configuration, current.raw, current.known) != (reviewed.configuration, reviewed.raw, reviewed.known):
        raise StalePreviewError("Preview is stale: file, source/configuration or imported scans changed. Preview again")
    records = _select_scans(current.records, scan_ids)
    ids = {r["scan_id"] for r in records}
    allowed = {s["scan_id"] for s, mismatch in zip(current.summaries, current.mismatches, strict=True)
               if not mismatch} if include_duplicates else set(current.new_ids)
    if not ids <= allowed:
        raise StalePreviewError("Select only new scans from this preview. Preview again")
    return current


def import_scans(config: Source, input_path: Path | None = None, scan_ids: Iterable[str] | None = None,
                 now: datetime | None = None, reviewed: ScanPreview | None = None,
                 include_duplicates: bool = False) -> dict:
    """Import BrownstoneScan SavedVariables for an addon source; returns the collection manifest.

    Reads ``input_path`` or the configured ``scan_path`` and never writes to it. Every scan must match
    the configured market's house evidence, or nothing is imported. Scans are deduplicated by scan_id per
    source. Partial scans are stored and labeled but never priced. The newest complete scan in the file
    becomes the collection's analytical snapshot, aged from its finish time.
    """
    if config["provider"] != ADDON_PROVIDER:
        raise ValueError(f"{config['source_id']} is not an addon source")
    path = Path(input_path or config["scan_path"])
    scan_ids = tuple(scan_ids) if scan_ids is not None else None
    now = now or datetime.now(UTC)
    if reviewed:
        # A stale review fails before even an archive directory or failure manifest is created.
        preparation = _reviewed_preparation(config, path, scan_ids, now, reviewed, include_duplicates)
        return _import_reviewed(config, path, now, preparation, reviewed, scan_ids)
    return _save_collection(config, path, now, _read_scan_bytes(path), scan_ids)


def _import_reviewed(config: Source, path: Path, now: datetime, preparation: ScanPreview,
                     reviewed: ScanPreview, scan_ids: Iterable[str] | None) -> dict:
    """Hold the database writer connection through the final duplicate check and import."""
    database = Path(config["data_dir"]) / "brownstone.duckdb"
    if not database.exists():
        Path(config["data_dir"]).mkdir(parents=True, exist_ok=True)
    upgrade_database(Path(config["data_dir"]), create=True)
    with duckdb.connect(str(database)) as db:
        db.begin()
        if _known_scans(db, config, reviewed.summaries) != reviewed.known:
            raise StalePreviewError("Imported scans changed. Preview again")
        return _save_collection(config, path, now, preparation.raw, scan_ids, preparation, db)


def _save_collection(config: Source, path: Path, now: datetime, raw: bytes,
                     scan_ids: Iterable[str] | None, preparation: ScanPreview | None = None, db=None) -> dict:
    sid = _collection_id(now)
    folders = _folders(config, ("bronze", "silver"))
    sha256 = hashlib.sha256(raw).hexdigest()
    bronze_file = _bronze_copy(folders["bronze"], sid, raw, sha256)
    manifest: dict = {
        "snapshot_id": sid, **_identity(config), "collected_at": now.isoformat(), "source": str(path.resolve()),
        "machine": config.get("machine"), "original_file_name": path.name,
        "bronze_file": bronze_file, "sha256": sha256, "bytes": len(raw), "status": "received",
    }
    try:
        all_records = preparation.records if preparation else scans.read_saved_variables(raw)
        records, summaries = _prepare_scans(all_records, config, now, scan_ids)
        if db is None:
            upgrade_database(Path(config["data_dir"]), create=True)
            with duckdb.connect(str(Path(config["data_dir"]) / "brownstone.duckdb")) as connection:
                connection.begin()
                _load_collection(connection, config, folders, sid, now, sha256,
                                 records, summaries, all_records, manifest)
                connection.commit()
        else:
            _load_collection(db, config, folders, sid, now, sha256, records, summaries, all_records, manifest)
            db.commit()
    except Exception as error:
        manifest.update(status="failed", error=str(error))
        raise
    finally:
        (folders["bronze"] / f"{sid}.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _load_collection(db, config: Source, folders: dict[str, Path], sid: str, now: datetime, sha256: str,
                     records: list[dict], summaries: list[dict], all_records: list[dict], manifest: dict) -> None:
    _check_conflicts(summaries, _known_scans(db, config, summaries))
    remember_local_catalog_names(db)
    results = [_import_scan(db, config, folders["silver"], sid, now, sha256, record, summary)
               for record, summary in zip(records, summaries, strict=True)]
    manifest["scans"] = results
    states = [_file_scan_state(db, config, record) for record in all_records]
    manifest["remaining_unimported"] = states.count("remaining")
    manifest["other_house"] = states.count("other_house")
    manifest["already_imported"] = sum(result["outcome"] == "duplicate" for result in results)
    priced = [result for result in results if result["priced"]]
    if priced:
        latest = max(priced, key=lambda result: result["finished_at"])
        manifest.update(status="complete", analytical_snapshot_id=latest["snapshot_id"],
                        scan_id=latest["scan_id"], rows=latest["items"], updated_at=latest["finished_at"],
                        freshness_basis="upstream", new_observation=latest["outcome"] == "imported")
    else:
        manifest.update(status="no_complete_scan")


def _file_scan_state(db, config: Source, record) -> str:
    """Whether a file scan is saved for this source, from another auction house, or still remaining.

    Unselected scans were never validated, so an unusable entry, or one stored under this
    source_id for a different market, counts as remaining instead of failing an import that did not
    select it. Selected scans with that mismatch are refused earlier by ``known_scan``.
    """
    if not isinstance(record, dict) or not isinstance(record.get("scan_id"), str):
        return "remaining"
    try:
        content = scans.scan_content_hash(record)
    except (TypeError, ValueError):
        return "remaining"
    try:
        existing = known_scan(db, config, record["scan_id"])
    except ValueError:
        return "remaining"
    if existing and existing["scan_sha256"] == content:
        return "saved"
    return "other_house" if scans.check_house(record, config) else "remaining"


def new_scans(manifest: dict) -> int:
    """Scans this import stored for the first time (anything but a duplicate)."""
    return sum(scan["outcome"] != "duplicate" for scan in manifest["scans"])


def import_guidance(manifest: dict) -> str:
    """What to do in game after an import, for the app and the CLI.

    The game writes scans to the file only on /reload or logout, so a file with nothing new usually means
    the latest scan is still in game memory: clearing then would lose it. Clearing is suggested only after
    an import stored something new and no file scans remain unimported. Scans from another auction
    house can't be imported into this source, so they don't block guidance, but clearing would delete
    them too. The addon also refuses to clear scans it hasn't written yet.
    """
    if manifest.get("remaining_unimported", 0):
        return (f"{manifest['remaining_unimported']} scan(s) in this file remain unimported. "
                "Import the remaining scans before clearing in game. Don't /bscan clear yet.")
    if not new_scans(manifest):
        return (f"Nothing new: all {len(manifest['scans'])} scan(s) in this file were imported before. If you "
                "scanned since, type /reload in game so the game writes the scan to the file, then import again. "
                "Don't /bscan clear until it's imported.")
    if manifest.get("other_house", 0):
        return (f"Everything for this market is saved, but {manifest['other_house']} scan(s) in this file are from "
                "another auction house and can't be imported into this source. Import them with their own source "
                "before you /bscan clear, because clearing deletes them too.")
    return ("Everything in this file is now saved. To keep the next file small, type /bscan clear, then /reload, "
            "in game.")


def _select_scans(records: list[dict], scan_ids: Iterable[str] | None) -> list[dict]:
    """The file's scans, or only the requested ones; an unknown scan ID fails the import."""
    if scan_ids is not None:
        wanted = list(scan_ids)
        unknown = set(wanted) - {record.get("scan_id") for record in records}
        if unknown:
            raise ValueError(f"Scan(s) not in this file: {sorted(unknown)}")
        records = [record for record in records if record.get("scan_id") in wanted]
    if not records:
        raise ValueError("The file has no scans. The game writes scans to it only on /reload or logout, and "
                         "/bscan clear empties it; take a scan, /reload, then import")
    return records


def _check_scans(records: list[dict], config: Source, now: datetime) -> list[dict]:
    """Validate every scan before anything is stored: header, house, clock and listings (ADDON-01, ADDON-05)."""
    summaries = [scans.summarize(record) for record in records]
    problems = [problem for record in records for problem in scans.check_house(record, config)]
    if problems:
        raise ValueError("Scan does not match the configured market " + config["market_id"] + ": "
                         + "; ".join(problems))
    return _validate_scans(records, now, summaries)


def _validate_scans(records: list[dict], now: datetime, summaries: list[dict] | None = None) -> list[dict]:
    """Header, clock and listing validation shared by preview and import (house evidence is checked by callers)."""
    summaries = summaries if summaries is not None else [scans.summarize(record) for record in records]
    for summary in summaries:
        if summary["finished_at"] > now + timedelta(hours=FUTURE_TOLERANCE_HOURS):
            raise ValueError(f"Scan {summary['scan_id']} finished in the future ({summary['finished_at']}); "
                             "check the computer's clock")
    for record in records:
        frame = scans.listing_frame(record)
        items = scan_details.reference_frame(record)
        _check_reference_items(frame, items)
        scan_details.duration(record)
    return summaries


def _check_reference_items(listings: pl.DataFrame, items: pl.DataFrame) -> None:
    if items.filter(~pl.col("item_id").is_in(listings["item_id"].implode())).height:
        raise ValueError("item reference has no listing in this scan")


def _import_scan(db, config: Source, silver: Path, sid: str, now: datetime, sha256: str,
                 record: dict, summary: dict) -> dict:
    """Store one scan unless this source already has it; return its manifest entry."""
    result = {key: summary[key] for key in ("scan_id", "status", "stop_reason", "partial",
                                             "listing_count", "reported_count")}
    result["finished_at"] = summary["finished_at"].isoformat()
    existing = known_scan(db, config, summary["scan_id"])
    if existing:
        if existing["scan_sha256"] != summary["scan_sha256"]:
            raise ValueError(f"Scan {summary['scan_id']} was imported before with different content")
        return {**result, "outcome": "duplicate", "snapshot_id": existing["snapshot_id"],
                "priced": bool(existing["priced"]), "items": existing["item_count"]}
    snapshot_id = f"{config['source_id']}:{summary['scan_id']}"
    identity = {**_observation_keys(config), "snapshot_id": snapshot_id}
    listings = scans.listing_frame(record)
    items = scan_details.reference_frame(record)
    measured = scan_details.availability(listings, items, scans.optional_out_of_range(record), record)
    priced = not summary["partial"] and listings.height > 0
    prices = scans.item_prices(listings) if priced else None
    stem = silver / f"{sid}_{summary['scan_id']}"
    columns = [pl.lit(value, dtype=pl.String).alias(key) for key, value in identity.items()]
    pq.write_table(listings.with_columns(pl.lit(summary["scan_id"]).alias("scan_id"), *columns).to_arrow(),
                   f"{stem}_listings.parquet", compression="zstd")
    items_path = Path(f"{stem}_items.parquet")
    pq.write_table(items.with_columns(pl.lit(summary["scan_id"]).alias("scan_id"), *columns).to_arrow(),
                   items_path, compression="zstd")
    prices_path = None
    if prices is not None:
        prices_path = Path(f"{stem}_prices.parquet")
        pq.write_table(prices.with_columns(
            *columns, pl.lit(summary["finished_at"]).alias("updated_at"), pl.lit(now).alias("collected_at"),
            pl.lit(sha256).alias("source_sha256")).to_arrow(), prices_path, compression="zstd")
    scan_row = {key: value for key, value in summary.items() if key not in ("neutral", "errors")}
    scan_row.update(identity, format_version=record["schema_version"],
                    duration_seconds=scan_details.duration(record),
                    availability_json=json.dumps(measured, sort_keys=True) if record["schema_version"] >= 3 else None,
                    priced=priced, nonexact_stacks=scans.nonexact_stacks(listings),
                    item_count=prices.height if prices is not None else None, source_sha256=sha256,
                    collection_id=sid, collected_at=now, machine=config.get("machine"))
    scan_path = Path(f"{stem}_scan.parquet")
    pq.write_table(pl.DataFrame([scan_row]).with_columns(pl.col(pl.Null).cast(pl.String)).to_arrow(), scan_path)
    load_scan(db, scan_path, Path(f"{stem}_listings.parquet"), prices_path, items_path)
    outcome = "imported" if priced else "empty" if listings.height == 0 else "partial (not priced)"
    return {**result, "outcome": outcome, "snapshot_id": snapshot_id, "priced": priced,
            "items": scan_row["item_count"], "nonexact_stacks": scan_row["nonexact_stacks"],
            "errors": summary["errors"], "format_version": record["schema_version"],
            "duration_seconds": scan_details.duration(record), "availability": measured}
