"""Raw journal validation, persistence and aggregate display; never interprets transactions."""
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb

from . import character_snapshots as holdings
from . import professions
from .config import MARKET_KEYS
from .freshness import FUTURE_TOLERANCE_HOURS
from .scans import _utc

FAMILIES = {"auction", "mail", "craft", "vendor", "loot", "money", "bags", "system"}


def _typed(value):
    """Sort Lua tables without conflating numeric keys with string keys or losing nil holes."""
    if isinstance(value, dict):
        pairs = [(type(k).__name__, k, _typed(v)) for k, v in value.items()]
        return {"lua_table": sorted(pairs, key=lambda p: (p[0], str(p[1])))}
    if isinstance(value, list):
        return [_typed(v) for v in value]
    return value


def content_hash(record: dict) -> str:
    return hashlib.sha256(json.dumps(_typed(record), sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()


def summarize(record: dict, now: datetime) -> dict:
    for key in ("entry_id", "character", "realm", "faction", "addon_version", "event"):
        if not isinstance(record.get(key), str) or not record[key]:
            raise ValueError(f"Journal needs {key}")
    if record.get("family") not in FAMILIES:
        raise ValueError("Unknown journal family")
    moment = _utc(record.get("captured_at"), record.get("captured_at_utc"), "captured_at")
    if moment > now + timedelta(hours=FUTURE_TOLERANCE_HOURS):
        raise ValueError("Journal captured in the future; check the computer's clock")
    holdings._integer(record.get("sequence"), "sequence", 1)
    for key in ("before_copper", "after_copper"):
        holdings._integer(record.get(key), key)
    session = record.get("session_time")
    if session is not None and (type(session) not in (float, int) or not 0 <= session < float("inf")):
        raise ValueError("Journal session_time must be finite and nonnegative, or missing")
    _validate_payload(record)
    professions.validate_recipes(record)
    return {"record_id": record["entry_id"], "record_sha256": content_hash(record),
            "character": record["character"], "realm": record["realm"], "faction": record["faction"],
            "family": record["family"], "captured_at": moment.isoformat()}


def _validate_payload(record: dict) -> None:
    arguments = record.get("arguments", {})
    if not isinstance(arguments, dict):
        raise ValueError("Journal arguments must be an indexed table with n")
    holdings._integer(arguments.get("n"), "argument count")
    changes = record.get("item_changes", {})
    if not isinstance(changes, dict):
        raise ValueError("Journal item_changes must be a table")
    for item, count in changes.items():
        if type(item) is not int or item <= 0 or type(count) is not int or not -(2**63) < count < 2**63:
            raise ValueError("Journal changes need positive item IDs and signed integer counts")


def states(config, records: list[dict], db=None) -> list[dict | None]:
    if db is None:
        path = Path(config["data_dir"]) / "brownstone.duckdb"
        if not path.exists():
            return [None] * len(records)
        with duckdb.connect(str(path), read_only=True) as connection:
            return states(config, records, connection)
    if not db.execute("SELECT 1 FROM information_schema.tables WHERE table_name='character_journal'").fetchone():
        return [None] * len(records)
    stored = {}
    for entry, sha, *scope in db.execute(
            f"SELECT entry_id, record_sha256, {', '.join(MARKET_KEYS)} FROM character_journal "
            "WHERE source_id=? AND list_contains(?, entry_id)",
            [config["source_id"], [r["entry_id"] for r in records]]).fetchall():
        if scope != [config[k] for k in MARKET_KEYS]:
            raise ValueError(f"Journal {entry} belongs to a different market; use a separate source_id")
        stored[entry] = {"record_sha256": sha}
    return [stored.get(r["entry_id"]) for r in records]


def load_one(db, config, record: dict, summary: dict, collection: str, file_hash: str) -> None:
    row = {"source_id": config["source_id"], **{k: config[k] for k in MARKET_KEYS},
           "entry_id": record["entry_id"], "record_sha256": summary["record_sha256"],
           "character": record["character"], "character_realm": record["realm"],
           "character_faction": record["faction"], "family": record["family"],
           "captured_at": summary["captured_at"], "machine": config.get("machine"),
           "collection_id": collection, "source_sha256": file_hash,
           "record_json": json.dumps(record, ensure_ascii=False)}
    db.execute(f"INSERT INTO character_journal ({','.join(row)}) VALUES ({','.join('?' for _ in row)})",
               list(row.values()))


def preview_rows(preview, machine=None) -> list[dict]:
    grouped: dict[tuple, dict] = {}
    for r, known, mismatch in zip(preview.non_scans, preview.non_scan_known,
                                   preview.non_scan_mismatches, strict=True):
        if "entry_id" not in r:
            continue
        key = (r["character"], r["realm"], r["faction"], r["family"])
        row = grouped.setdefault(key, dict(zip(("Character", "Realm", "Faction", "Family"), key, strict=True)) |
                                 {"Machine": machine, "new": 0, "duplicate": 0, "other house": 0})
        row["other house" if mismatch else "duplicate" if known else "new"] += 1
    return list(grouped.values())


def latest_rows(config) -> list[dict]:
    path = Path(config["data_dir"]) / "brownstone.duckdb"
    if not path.exists():
        return []
    with duckdb.connect(str(path), read_only=True) as db:
        if not db.execute("SELECT 1 FROM information_schema.tables WHERE table_name='character_journal'").fetchone():
            return []
        rows = db.execute("SELECT character, character_realm, character_faction, family, count(*), "
                          "max(captured_at) FROM character_journal WHERE source_id=? AND " +
                          " AND ".join(f"{k}=?" for k in MARKET_KEYS) + " GROUP BY ALL ORDER BY ALL",
                          [config["source_id"], *[config[k] for k in MARKET_KEYS]]).fetchall()
    return [dict(zip(("Character", "Realm", "Faction", "Family", "Entries", "Latest (UTC)"),
                     (*r[:-1], r[-1].astimezone(UTC).isoformat()), strict=True)) for r in rows]


def outcome_rows(results: list[dict]) -> list[dict]:
    counts = Counter((r["character"], r["family"], r["outcome"]) for r in results if r["record_type"] == "journal")
    return [{"Character": c, "Family": f, "Outcome": o, "Entries": count}
            for (c, f, o), count in sorted(counts.items())]


def active_auction_rows(config) -> list[dict]:
    """Latest raw owned-list observation per known character, within one source and market."""
    path = Path(config["data_dir"]) / "brownstone.duckdb"
    if not path.exists():
        return []
    characters: dict[tuple, dict] = {}
    scope = " AND ".join(["source_id=?", *(f"{k}=?" for k in MARKET_KEYS)])
    params = [config["source_id"], *[config[k] for k in MARKET_KEYS]]
    with duckdb.connect(str(path), read_only=True) as db:
        tables = {r[0] for r in db.execute("SELECT table_name FROM information_schema.tables").fetchall()}
        for table in ("character_snapshots", "character_journal"):
            if table in tables:
                for key in db.execute(f"SELECT DISTINCT character, character_realm, character_faction "
                                      f"FROM {table} WHERE {scope}", params).fetchall():
                    characters.setdefault(key, {})
        if "character_journal" in tables:
            rows = db.execute("SELECT character, character_realm, character_faction, record_json "
                              f"FROM character_journal WHERE {scope} AND family='auction' "
                              "AND record_json LIKE '%\"owned_auctions\"%'", params).fetchall()
            for name, realm, faction, raw in rows:
                record = json.loads(raw)
                if "owned_auctions" in record and _observation_order(record) > _observation_order(
                        characters[name, realm, faction]):
                    characters[name, realm, faction] = record
    return [_active_auction_row(key, record) for key, record in sorted(characters.items())]


def _observation_order(record: dict) -> tuple:
    return (record.get("captured_at", -1), record.get("sequence", -1), record.get("entry_id", ""))


def _active_auction_row(key: tuple, record: dict) -> dict:
    state = record.get("owned_auctions", {})
    counts = state.get("counts") or {}
    count = counts.get("2", counts.get("1")) if state.get("api") == "legacy" else counts.get("1")
    moment = (_utc(record["captured_at"], record.get("captured_at_utc"), "captured_at").isoformat()
              if record else "active auctions unknown")
    return dict(zip(("Character", "Realm", "Faction"), key, strict=True)) | {
        "Active auctions (UTC)": moment, "Auctions": count,
        "Marked sold": _sold_count(state, count)}


def _sold_count(state: dict, count) -> int | None:
    if type(count) is not int or count < 0 or state.get("full_results") is False:
        return None
    auctions = state.get("auctions", {})
    values = list(auctions.values()) if isinstance(auctions, dict) else auctions
    if len(values) != count:
        return None
    statuses = [(a.get("info") or {}).get("16" if state.get("api") == "legacy" else "status") for a in values]
    sold = 1 if state.get("api") == "legacy" else state.get("sold_status")
    if count and (sold is None or any(s is None for s in statuses)):
        return None
    return sum(s == sold for s in statuses)
