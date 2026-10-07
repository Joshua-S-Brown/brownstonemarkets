"""One lifecycle for non-scan records, with type-specific validation and storage adapters."""
from datetime import datetime

from . import character_snapshots as holdings
from . import journal


def record_id(record: dict) -> str:
    return record["entry_id"] if "entry_id" in record else record["snapshot_id"]


def record_type(record: dict) -> str:
    return "journal" if "entry_id" in record else "snapshot"


def summarize(record: dict, now: datetime) -> dict:
    if record_type(record) == "journal":
        return journal.summarize(record, now)
    return holdings.summarize(record, now)


def content_hash(record: dict) -> str:
    return journal.content_hash(record) if record_type(record) == "journal" else holdings.content_hash(record)


def check_house(record: dict, config) -> list[str]:
    reasons = holdings.check_house({**record, "snapshot_id": record_id(record)}, config)
    label = "Journal" if record_type(record) == "journal" else "Snapshot"
    return [reason.replace("Snapshot", label, 1) for reason in reasons]


def states(config, records: list[dict], db=None) -> list[dict | None]:
    snapshots = [r for r in records if record_type(r) == "snapshot"]
    entries = [r for r in records if record_type(r) == "journal"]
    snapshot_states = iter({"record_sha256": s["snapshot_sha256"]} if s else None
                           for s in holdings.states(config, snapshots, db))
    journal_states = iter(journal.states(config, entries, db))
    return [next(journal_states) if record_type(r) == "journal" else next(snapshot_states) for r in records]


def check_conflicts(records: list[dict], known: list[dict | None]) -> None:
    for r, previous in zip(records, known, strict=True):
        if previous and previous["record_sha256"] != content_hash(r):
            raise ValueError(f"Record {record_id(r)} conflict: imported before with different content")


def load(db, config, records: list[dict], collection: str, file_hash: str, now: datetime) -> list[dict]:
    known = states(config, records, db)
    check_conflicts(records, known)
    results = []
    for r, previous in zip(records, known, strict=True):
        outcome = "other_house" if check_house(r, config) else "duplicate" if previous else "imported"
        summary = summarize(r, now)
        if outcome == "imported":
            if record_type(r) == "snapshot":
                holdings.load(db, config, [r], collection, file_hash, now)
            else:
                journal.load_one(db, config, r, summary, collection, file_hash)
        results.append({**summary, "record_id": record_id(r), "record_type": record_type(r),
                        "outcome": outcome, "record_sha256": content_hash(r)})
    return results


def committed(results: list[dict]) -> dict[tuple[str, str], dict]:
    return {(r["record_type"], r["record_id"]):
            {"record_sha256": r["record_sha256"]}
            for r in results if r["outcome"] != "other_house"}
