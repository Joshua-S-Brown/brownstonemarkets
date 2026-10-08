"""Read-only character evidence, scoped and deduplicated independently of auction prices."""
import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb

from . import professions
from .config import MARKET_KEYS
from .freshness import FUTURE_TOLERANCE_HOURS
from .money import to_gold
from .scans import _list, _utc


def content_hash(record: dict) -> str:
    if "skills" in record:
        from .journal import _typed
        record = record | {"skills": _typed(record["skills"])}
    return hashlib.sha256(json.dumps(record, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()


def _integer(value, name: str, minimum: int = 0) -> None:
    if value is not None and (type(value) is not int or not minimum <= value <= 2**63 - 1):
        raise ValueError(f"Snapshot {name} must be an integer >= {minimum}, or missing")


def summarize(record: dict, now: datetime) -> dict:
    if not isinstance(record, dict):
        raise ValueError("Snapshot must be a table")
    for key in ("snapshot_id", "character", "realm", "faction", "addon_version", "event"):
        if not isinstance(record.get(key), str) or not record[key]:
            raise ValueError(f"Snapshot needs {key}")
    if record.get("kind") not in ("bags", "bank"):
        raise ValueError("Snapshot kind must be bags or bank")
    moment = _utc(record.get("captured_at"), record.get("captured_at_utc"), "captured_at")
    if moment > now + timedelta(hours=FUTURE_TOLERANCE_HOURS):
        raise ValueError("Snapshot captured in the future; check the computer's clock")
    _integer(record.get("gold_copper"), "gold_copper")
    _integer(record.get("sequence"), "sequence", 1)
    professions.validate_skills(record)
    slots = _list(record.get("slots"), "snapshot slots")
    _validate_slots(slots)
    containers = _list(record.get("containers"), "snapshot containers")
    for container in containers:
        if not isinstance(container, dict) or type(container.get("container_id")) is not int:
            raise ValueError("Snapshot container needs integer container_id")
        _integer(container.get("container_id"), "container_id", -2**31)
        _integer(container.get("size"), "container size")
    return {**{key: record[key] for key in ("snapshot_id", "character", "realm", "faction", "kind")},
            "captured_at": moment.isoformat(), "snapshot_sha256": content_hash(record),
            "slots": len(slots), "items": _item_count(slots),
            "units": None if any(s.get('count') is None for s in slots) else sum(s['count'] for s in slots),
            "complete": _complete(record),
            "gold_copper": record.get("gold_copper")}


def _item_count(slots: list) -> int | None:
    if any(s.get("item_id") is None for s in slots):
        return None
    return len({s["item_id"] for s in slots})


def unreadable_backpack(record: dict) -> bool:
    """A bags read the client answered with a 0-slot backpack (beta logout, 08 Oct): its values are not evidence."""
    return record.get("kind") == "bags" and any(
        isinstance(c, dict) and c.get("container_id") == 0 and c.get("size") == 0
        for c in _list(record.get("containers"), "snapshot containers"))


def _complete(record: dict) -> bool:
    if unreadable_backpack(record):
        return False
    containers = _list(record.get("containers"), "snapshot containers")
    return bool(containers) and all(c.get("size") is not None and c.get("slots_readable") is not False
                                    for c in containers)


def _validate_slots(slots: list) -> None:
    seen = set()
    for slot in slots:
        if not isinstance(slot, dict) or type(slot.get("container_id")) is not int:
            raise ValueError("Snapshot slot needs integer container_id")
        if type(slot.get("slot")) is not int or slot["slot"] < 1:
            raise ValueError("Snapshot slot needs positive slot")
        key = (slot["container_id"], slot["slot"])
        if key in seen:
            raise ValueError("Duplicate snapshot container/slot")
        seen.add(key)
        _integer(slot.get("item_id"), "item_id", 1)
        _integer(slot.get("count"), "count", 1)
        if slot.get("item_link") is not None and not isinstance(slot["item_link"], str):
            raise ValueError("Snapshot item_link must be text or missing")


def check_house(record: dict, config: Mapping[str, Any]) -> list[str]:
    evidence = config.get("scan_evidence", {})
    expected_realm = evidence.get("realm") or config.get("realm")
    observed_realm = record["realm"]
    if not evidence.get("realm"):
        observed_realm = observed_realm.lower().replace(" ", "-")
    problems = []
    if expected_realm and observed_realm != expected_realm:
        problems.append(f"Snapshot {record['snapshot_id']}: realm {record['realm']!r} != {expected_realm!r}")
    expected_faction = evidence.get("faction") or config["faction"]
    if expected_faction and record["faction"].lower() != expected_faction.lower():
        problems.append(f"Snapshot {record['snapshot_id']}: faction does not match {expected_faction}")
    return problems


def _has_snapshots(db) -> bool:
    # Older schemas lack the table; preview never migrates them.
    return db.execute("SELECT 1 FROM information_schema.tables WHERE table_name='character_snapshots'").fetchone() \
        is not None


def states(config: Mapping[str, Any], records: list[dict], db=None) -> list[dict | None]:
    """Each record's stored content hash for this source, or None when it isn't imported yet."""
    if db is None:
        path = Path(config["data_dir"]) / "brownstone.duckdb"
        if not path.exists():
            return [None] * len(records)
        with duckdb.connect(str(path), read_only=True) as connection:
            return states(config, records, connection)
    if not records or not _has_snapshots(db):
        return [None] * len(records)
    cursor = db.execute(f"SELECT snapshot_id, snapshot_sha256, {', '.join(MARKET_KEYS)} FROM character_snapshots "
                        "WHERE source_id = ? AND list_contains(?, snapshot_id)",
                        [config["source_id"], [r["snapshot_id"] for r in records]])
    stored = {}
    for snapshot_id, sha256, *market in cursor.fetchall():
        if market != [config[key] for key in MARKET_KEYS]:
            raise ValueError(f"Snapshot {snapshot_id} belongs to a different market; use a separate source_id")
        stored[snapshot_id] = {"snapshot_sha256": sha256}
    return [stored.get(r["snapshot_id"]) for r in records]


def check_conflicts(records: list[dict], existing: list[dict | None]) -> None:
    for record, previous in zip(records, existing, strict=True):
        if previous and previous["snapshot_sha256"] != content_hash(record):
            raise ValueError(f"Snapshot {record['snapshot_id']} conflict: imported before with different content")


def load(db, config: Mapping[str, Any], records: list[dict], collection_id: str,
         file_hash: str, now: datetime) -> list[dict]:
    existing = states(config, records, db)
    check_conflicts(records, existing)
    results = []
    for record, previous in zip(records, existing, strict=True):
        if check_house(record, config):
            results.append({"snapshot_id": record["snapshot_id"], "outcome": "other_house"})
            continue
        summary = summarize(record, now)
        if not previous:
            identity = {"source_id": config["source_id"], **{key: config[key] for key in MARKET_KEYS}}
            row = {**identity, **{k: summary[k] for k in
                   ("snapshot_id", "snapshot_sha256", "character", "kind", "captured_at", "gold_copper")},
                   "character_realm": record["realm"], "character_faction": record["faction"],
                   "machine": config.get("machine"), "collection_id": collection_id,
                   "source_sha256": file_hash, "record_json": json.dumps(record, ensure_ascii=False)}
            columns = list(row)
            db.execute(f"INSERT INTO character_snapshots ({','.join(columns)}) VALUES "
                       f"({','.join('?' for _ in columns)})", list(row.values()))
            for slot in _list(record.get("slots"), "slots"):
                db.execute("INSERT INTO character_slots VALUES (?, ?, ?, ?, ?, ?, ?)",
                           [config["source_id"], record["snapshot_id"], slot["container_id"], slot["slot"],
                            slot.get("item_id"), slot.get("count"), slot.get("item_link")])
        results.append({**summary, "outcome": "duplicate" if previous else "imported"})
    return results


def preview_rows(preview, machine: str | None = None) -> list[dict]:
    return [{"Snapshot ID": r["snapshot_id"], "Character": r["character"], "Realm": r["realm"],
             "Faction": r["faction"], "Kind": r["kind"], "Captured (UTC)": s["captured_at"],
             "Gold": to_gold(s["gold_copper"]), "Slots": s["slots"], "Items": s["items"],
             "Containers readable": s["complete"], "Machine": machine,
             "Import state": "duplicate" if known_record else "other house" if mismatch else "new"}
            for r, s, known_record, mismatch in zip(preview.snapshots, preview.snapshot_summaries,
                                                   preview.snapshot_known, preview.snapshot_mismatches, strict=True)]


def latest_rows(config: Mapping[str, Any]) -> list[dict]:
    path = Path(config["data_dir"]) / "brownstone.duckdb"
    if not path.exists():
        return []
    with duckdb.connect(str(path), read_only=True) as db:
        if not _has_snapshots(db):
            return []
        rows = db.execute("SELECT record_json, machine FROM character_snapshots WHERE source_id=? AND " +
                          " AND ".join(f"{key}=?" for key in MARKET_KEYS) +
                          " ORDER BY captured_at, CAST(json_extract_string(record_json, '$.sequence') AS BIGINT) "
                          "NULLS FIRST, snapshot_id",
                          [config["source_id"], *[config[k] for k in MARKET_KEYS]])
        characters: dict[tuple, dict] = {}
        for raw, machine in rows.fetchall():
            r = json.loads(raw)
            key = (r["character"], r["realm"], r["faction"])
            characters.setdefault(key, {})
            if not unreadable_backpack(r):
                characters[key][r["kind"]] = (r, machine)
    return [_latest_row(key, value) for key, value in sorted(characters.items())]


def _latest_row(key: tuple, value: dict) -> dict:
    row = dict(zip(("Character", "Realm", "Faction"), key, strict=True))
    for kind in ("bags", "bank"):
        r, machine = value.get(kind, ({}, None))
        slots = _list(r.get("slots"), "slots")
        complete = _complete(r)
        time_text = (_utc(r["captured_at"], r.get("captured_at_utc"), "captured_at").strftime("%Y-%m-%dT%H:%M:%SZ")
                     if r else "bank unknown" if kind == "bank" else "unknown")
        row.update({f"{kind.title()} (UTC)": time_text,
                    f"{kind.title()} machine": machine,
                    f"{kind.title()} containers readable": complete if r else None,
                    f"{kind.title()} slots": len(slots) if complete else None,
                    f"{kind.title()} items": _item_count(slots) if complete else None})
        if kind == "bags":
            row["Gold"] = to_gold(r.get("gold_copper"))
    return row
