"""Read-only beta report orchestration; imports run exclusively inside disposable directories."""
import gzip
import hashlib
import json
import tempfile
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from . import beta_evidence as evidence
from . import pipeline, professions, scans
from .config import Source


def analyze(raw: bytes, now: datetime) -> tuple[dict, tuple]:
    report: dict = {"file": {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}, "checks": []}
    try:
        database = scans.read_addon_database(raw)
    except (ValueError, TypeError) as error:
        evidence.check(report, "parse", "fail", str(error))
        return report, ([], [], [])
    lists = _record_lists(report, database)
    report["file"].update(file_format=database["schema_version"], addon_versions=_versions(database, lists),
                          record_counts=dict(zip(("scans", "snapshots", "journal"), map(len, lists), strict=True)),
                          approximate_bytes=_sizes(lists), size_basis="compact typed JSON UTF-8; approximate Lua size")
    report["file"]["journal_counts_by_family"] = dict(Counter(
        r.get("family", "unknown") if isinstance(r, dict) else "invalid" for r in lists[2]))
    valid_scans, records = evidence.validate(report, lists, now)
    report["scans"] = [_scan_facts(r) for r in valid_scans]
    report["characters"] = _characters(records)
    moments = [r["captured_at"] for r in records] + [r[k] for r in valid_scans for k in ("started_at", "finished_at")]
    report["file"]["time_span_utc"] = [_utc(min(moments)), _utc(max(moments))] if moments else None
    sessions = evidence.load_sessions(records)
    evidence.session_checks(report, sessions, database)
    evidence.reconciliation(report, records)
    evidence.profession_checks(report, records)
    evidence.coverage(report, records, database)
    report["session_method"] = ("Inferred shared-sequence order: PLAYER_LOGOUT closes a load; identity/login changes "
                                "and decreasing session_time start one. GetTime may persist across reload. "
                                "Without a captured boundary loads cannot be distinguished. Diagnostics/errors "
                                "are saved only for the latest load and cannot be recovered for earlier loads.")
    return report, lists


def _record_lists(report: dict, database: dict) -> tuple:
    lists = []
    for kind in ("scans", "snapshots", "journal"):
        try:
            lists.append(scans.addon_record_list(database, kind))
        except ValueError as error:
            evidence.check(report, "import validation", "fail", f"{kind}: {error}")
            lists.append([])
    return tuple(lists)


def _utc(seconds) -> str:
    return datetime.fromtimestamp(seconds, UTC).isoformat()


def _versions(database: dict, lists: tuple) -> list[str]:
    versions = {str(r["addon_version"]) for values in lists for r in values
                if isinstance(r, dict) and "addon_version" in r}
    if database.get("addon_version"):
        versions.add(str(database["addon_version"]))
    return sorted(versions)


def _sizes(lists: tuple) -> dict:
    sizes: dict = {"scans": sum(map(evidence.serialized_size, lists[0])),
             "snapshots": sum(map(evidence.serialized_size, lists[1]))}
    families: Counter = Counter()
    for r in lists[2]:
        families[r.get("family", "unknown") if isinstance(r, dict) else "invalid"] += evidence.serialized_size(r)
    sizes["journal_by_family"] = dict(families)
    return sizes


def _scan_facts(r: dict) -> dict:
    # Never project scan payloads, errors, item names or listings: ADDON-07.
    return {k: r.get(k) for k in ("scan_id", "started_at", "finished_at", "listing_count")}


def _characters(records: list[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in records:
        groups[evidence.identity(r)].append(r)
    result = []
    for key, values in sorted(groups.items()):
        ordered = sorted(values, key=lambda r: (r["captured_at"], r.get("sequence", 0)))
        snapshots = [_snapshot_facts(r) for r in ordered if "snapshot_id" in r]
        entries = [r for r in ordered if "entry_id" in r]
        groups_by_event: dict[tuple, list[dict]] = defaultdict(list)
        for r in entries:
            groups_by_event[r["family"], r["event"]].append(r)
        journal = [dict(family=f, event=e, entries=len(rows), first_utc=_utc(rows[0]["captured_at"]),
                        last_utc=_utc(rows[-1]["captured_at"])) for (f, e), rows in sorted(groups_by_event.items())]
        owned = [r for r in entries if "owned_auctions" in r]
        recipes = {r["known_recipes"].get("name"): _recipe_facts(r) for r in entries if "known_recipes" in r}
        result.append(dict(character=key[0], realm=key[1], faction=key[2], snapshots=snapshots, journal=journal,
                           latest_owned_auctions=_owned_facts(owned[-1]) if owned else None,
                           latest_known_recipes=list(recipes.values())))
    return result


def _snapshot_facts(r: dict) -> dict:
    skills = []
    for surface, api in (r.get("skills") or {}).items():
        for skill in scans._list(api.get("rows"), "skill rows"):
            skills.append({k: skill.get(k) for k in ("name", "rank", "max_rank", "skill_id", "is_header")} |
                          {"surface": surface, "api": api.get("api")})
    return {k: r.get(k) for k in ("snapshot_id", "kind", "gold_copper", "level")} | {
        "captured_utc": _utc(r["captured_at"]), "occupied_slots": len(scans._list(r.get("slots"), "slots")),
        "container_sizes": [{k: c.get(k) for k in ("container_id", "size", "slots_readable")}
                            for c in scans._list(r.get("containers"), "containers")], "skills": skills}


def _recipe_facts(r: dict) -> dict:
    state = r["known_recipes"]
    return {k: state.get(k) for k in ("name", "api", "rank", "max_rank", "possibly_incomplete")} | {
        "entry_id": r["entry_id"], "captured_utc": _utc(r["captured_at"]),
        "listed_recipes": professions._recipe_count(state), "causes": evidence.recipe_causes(state)}


def _owned_facts(r: dict) -> dict:
    state = scans._dict(r["owned_auctions"])
    auctions = state.get("auctions") or []
    rows = list(auctions.values()) if isinstance(auctions, dict) else auctions if isinstance(auctions, list) else []
    # Raw info can contain bidder/owner names. Preserve numeric evidence through a strict whitelist.
    fields = ("auctionID", "itemID", "quantity", "status", "timeLeftSeconds", "bidAmount", "buyoutAmount",
              3, 7, 8, 9, 10, 11, 16, 17, 19)
    items = [{k: v for k, v in scans._dict(a.get("info")).items() if k in fields and type(v) in (int, float)}
             for a in rows if isinstance(a, dict)]
    counts = scans._dict(state.get("counts"))
    return dict(entry_id=r["entry_id"], captured_utc=_utc(r["captured_at"]), api=state.get("api"),
                reported_counts={str(k): v for k, v in counts.items() if type(v) is int},
                observed_rows=len(rows), full_results=state.get("full_results"), auctions=items)


def round_trip(report: dict, raw: bytes, config: Source, now: datetime) -> None:
    try:
        with tempfile.TemporaryDirectory(prefix="brownstone-beta-") as temporary:
            root = Path(temporary)
            path = root / "input.lua"
            path.write_bytes(raw)
            isolated = config.copy()
            isolated["data_dir"] = root / "data"
            isolated["scan_path"] = path
            preview = pipeline.preview_scans(isolated, path, now)
            first = pipeline.import_scans(isolated, path, now=now, reviewed=preview)
            second = pipeline.import_scans(isolated, path, now=now)
            outcomes = second["scans"] + second.get("non_scan_records", [])
            if not outcomes or any(r["outcome"] != "duplicate" for r in outcomes):
                raise ValueError("Second import did not mark every record duplicate (empty or other-house file)")
            archive = root / "data" / "bronze" / config["source_id"] / first["bronze_file"]
            if gzip.decompress(archive.read_bytes()) != raw:
                raise ValueError("Decompressed bronze archive differs from input")
        evidence.check(report, "import round trip", "pass", "Preview → import → all duplicates; exact bronze bytes")
    except Exception as error:
        evidence.check(report, "import round trip", "fail", str(error))


def compare(report: dict, current: tuple, previous_raw: bytes, now: datetime) -> None:
    previous_report, previous = analyze(previous_raw, now)
    if any(c["status"] == "fail" and c["check"] in ("parse", "import validation", "unique IDs")
           for c in previous_report["checks"]):
        evidence.check(report, "comparison", "fail", "Earlier file is invalid; comparison unavailable")
        return
    old = {_record_key(r): _hash(r) for rows in previous for r in rows if isinstance(r, dict)}
    additions: Counter = Counter()
    scan_count = 0
    for kind, rows in enumerate(current):
        for r in rows:
            if not isinstance(r, dict):
                continue
            key = _record_key(r)
            if key in old:
                if old[key] != _hash(r):
                    evidence.check(report, "comparison conflict", "fail", "Earlier ID has different content",
                                   [evidence.identifier(r)])
                continue
            if kind == 0:
                scan_count += 1
            else:
                additions[(*evidence.identity(r), r.get("family", r.get("kind")))] += 1
    report["comparison"] = dict(previous_sha256=hashlib.sha256(previous_raw).hexdigest(), new_scans=scan_count,
                                additions=[dict(character=c, realm=r, faction=f, family=family, records=count)
                                           for (c, r, f, family), count in sorted(additions.items())])
    evidence.check(report, "comparison", "pass", report["comparison"])


def _record_key(r: dict) -> tuple:
    kind = "scan" if "scan_id" in r else "journal" if "entry_id" in r else "snapshot"
    return kind, evidence.identifier(r)


def _hash(r: dict) -> str:
    from .addon_records import content_hash
    return scans.scan_content_hash(r) if "scan_id" in r else content_hash(r)


def create_report(path: Path, config: Source, output_root: Path, previous: Path | None = None,
                  now: datetime | None = None) -> tuple[Path, dict, int]:
    """Only persistent writes are a unique folder in output_root; never touches configured data."""
    started = time.perf_counter()
    now = now or datetime.now(UTC)
    code = 0
    report: dict
    try:
        raw = pipeline._read_scan_bytes(path)
    except (OSError, ValueError) as error:
        report = {"file": {"name": path.name}, "checks": []}
        evidence.check(report, "input read", "fail", str(error))
        code = 2
    else:
        report, lists = analyze(raw, now)
        report["file"]["name"] = path.name
        if not any(c["check"] == "parse" for c in report["checks"]):
            round_trip(report, raw, config, now)
        if previous is not None:
            try:
                compare(report, lists, pipeline._read_scan_bytes(previous), now)
            except (OSError, ValueError) as error:
                evidence.check(report, "previous input read", "fail", str(error))
                code = 2
    report["generated_utc"] = now.isoformat()
    report["runtime_seconds"] = round(time.perf_counter() - started, 6)
    counts = Counter(c["status"] for c in report["checks"])
    report["totals"] = {k: counts[k] for k in ("pass", "warn", "fail")}
    code = code or int(bool(counts["fail"]))
    folder = output_root / (now.strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex[:8])
    folder.mkdir(parents=True)
    from views.beta_report import markdown
    (folder / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (folder / "report.md").write_text(markdown(report), encoding="utf-8")
    return folder, report, code
