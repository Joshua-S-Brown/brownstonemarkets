"""One after-play check: normal import, isolated beta report, then only what changed since the last run.

The previous run's state is private (work/after-play/state.json, ignored by Git). Nothing here writes
to game files or drops; the only data writes are the normal drop-folder import.
"""
import hashlib
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from . import beta_report
from .config import Source
from .scan_changes import eligible_scans
from .scan_inputs import import_inputs, preview_inputs

README_SECTION = "## Last beta play session"


def pending_checks(readme: str) -> list[str]:
    """Numbered play actions under *Last beta play session*, markdown stripped."""
    _, found, rest = readme.partition(README_SECTION)
    if not found:
        return []
    section = rest.split("\n## ", 1)[0]
    items = re.findall(r"^\d+\.\s+(.+?)(?=^\d+\.\s|^\S|\Z)", section, re.M | re.S)
    return [re.sub(r"\s+", " ", re.sub(r"\*\*|`", "", item)).strip() for item in items]


def _label(check: dict) -> str:
    detail = check["detail"]
    if check["check"] == "coverage" and isinstance(detail, dict):
        return f"coverage: {detail['checklist']} {detail['action']}"
    text = detail if isinstance(detail, str) else json.dumps(detail, sort_keys=True, default=str)
    return f"{check['check']}: {text[:120]}"


def _evidence(report: dict) -> dict[str, int]:
    """Counts the in-game checks rely on; a change here is what a play session adds."""
    sales = report.get("your_sales") or {}
    owned = [c["latest_owned_auctions"] for c in report.get("characters", []) if c.get("latest_owned_auctions")]
    return {"sale posts": len(sales.get("posts", [])), "sale outcomes": len(sales.get("outcomes", [])),
            "unidentified invoices": sales.get("unidentified", 0),
            "trainer tier observations": len((report.get("trainer_tiers") or {}).get("observations", [])),
            "failed scan starts": len((report.get("scan_attempts") or {}).get("attempts", [])),
            "loot windows": (report.get("farming_capture") or {}).get("loot_windows", 0),
            "owned auction rows": sum(o.get("observed_rows", 0) for o in owned),
            "recipe windows": sum(len(c.get("latest_known_recipes", [])) for c in report.get("characters", []))}


def file_state(path: Path, folder: Path, report: dict) -> dict:
    checks = report.get("checks", [])
    return {"path": str(path), "sha256": report["file"].get("sha256"), "report": str(folder),
            "generated_utc": report.get("generated_utc"), "totals": report.get("totals"),
            "addon_versions": report["file"].get("addon_versions", []),
            "record_counts": report["file"].get("record_counts", {}),
            "scans": sorted(s["scan_id"] for s in report.get("scans", [])),
            "fails": sorted({_label(c) for c in checks if c["status"] == "fail"}),
            "warns": sorted({_label(c) for c in checks if c["status"] == "warn"}),
            "evidence": _evidence(report)}


def read_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _changes(title: str, before: list, after: list) -> list[str]:
    """One line per check name, e.g. every newly unseen coverage action together."""
    lines = []
    for word, labels in (("new", [x for x in after if x not in before]),
                         ("resolved", [x for x in before if x not in after])):
        groups: dict[str, list[str]] = {}
        for label in labels:
            name, _, detail = label.partition(": ")
            groups.setdefault(name, []).append(detail)
        lines += [f"  {word} {title} {name}: {'; '.join(details)}" for name, details in groups.items()]
    return lines


def file_summary(machine: str, previous: dict | None, current: dict) -> list[str]:
    """Diff-style lines for one machine's latest drop; persistent fails are always repeated."""
    old = previous or {}
    lines = [f"{machine}: {Path(current['path']).name} ({', '.join(f'{v} {k}' for k, v in current['totals'].items())})"
             f" -> {current['report']}"]
    if not previous:
        lines.append("  first after-play run for this machine; everything below is new")
    if current["addon_versions"] != old.get("addon_versions"):
        lines.append(f"  addon versions: {old.get('addon_versions') or '-'} -> {current['addon_versions']}")
    lines += [f"  new scan in file: {s}" for s in current["scans"] if s not in old.get("scans", [])]
    lines += [f"  FAIL {x}" + ("" if x in old.get("fails", []) else " (new)") for x in current["fails"]]
    lines += [f"  resolved fail: {x}" for x in old.get("fails", []) if x not in current["fails"]]
    lines += _changes("warn", old.get("warns", []), current["warns"])
    before = old.get("evidence", {})
    lines += [f"  {k}: {before.get(k, 0)} -> {v}" for k, v in current["evidence"].items() if v != before.get(k, 0)]
    return lines


def eligibility_summary(previous: list[str], current: list[str], reported_scans: list[str]) -> list[str]:
    """Eligible IDs arrive newest first; a long list (first run) shows the newest three and a count."""
    new = [s for s in current if s not in previous]
    lines = [f"  newly eligible scan: {s}" for s in new[:3]]
    if len(new) > 3:
        lines.append(f"  ... and {len(new) - 3} older newly eligible scans")
    lines += [f"  NOT eligible (incomplete, partial, unpriced or other house): {s}"
              for s in reported_scans if s not in current]
    return lines or ["  no change"]


def eligible_ids(config: Source) -> list[str]:
    path = Path(config["data_dir"]) / "brownstone.duckdb"
    if not path.exists():
        return []
    with duckdb.connect(str(path), read_only=True) as db:
        return [s["scan_id"] for s in eligible_scans(db, config)]


def _import(config: Source, now: datetime) -> tuple[list[str], bool]:
    try:
        preview = preview_inputs(config, now)
        results = import_inputs(config, preview, now=now) if preview.new_files else []
    except (OSError, ValueError, RuntimeError) as error:
        return [f"  IMPORT FAILED: {error}"], False
    lines, ok = [], True
    for file in preview.files:
        if file.error:
            lines.append(f"  unreadable {file.path.name}: {file.error}")
    for result in results:
        name = Path(result["file"]).name
        if result["status"] == "error":
            ok = False
            lines.append(f"  IMPORT FAILED {name}: {result['error']}")
            continue
        manifest = result.get("manifest", {})
        new = [s["scan_id"] for s in manifest.get("scans", []) if s["outcome"] != "duplicate"]
        records = sum(r["outcome"] != "duplicate" for r in manifest.get("non_scan_records", []))
        lines.append(f"  {name}: {result['status']}, {len(new)} new scans {new or ''}, {records} new records")
    return lines or ["  nothing new to import"], ok


def run(config: Source, state_path: Path, report_root: Path, readme: str,
        now: datetime | None = None, report: Callable = beta_report.create_report) -> tuple[list[str], int]:
    """Import, report each machine's latest drop that changed, and summarize against the stored state."""
    now = now or datetime.now(UTC)
    state = read_state(state_path)
    if state.get("source_id") not in (None, config["source_id"]):
        state = {}  # Never compare across sources.
    lines = [f"After-play check for {config['source_id']} ({now:%Y-%m-%d %H:%M} UTC)",
             f"Previous run: {state.get('checked_utc', 'none')}", "Import:"]
    imported, import_ok = _import(config, now)
    lines += imported
    machines = dict(state.get("machines", {}))
    lines.append("Latest drops:")
    code = _report_drops(config, machines, report_root, now, report, lines)
    code = max(code, 0 if import_ok else 1)
    eligible = eligible_ids(config)
    reported = sorted({s for m in machines.values() for s in m.get("scans", [])})
    lines += ["Eligible scans:", *eligibility_summary(state.get("eligible", []), eligible, reported)]
    lines += ["Pending in-game checks (addon/README.md, Last beta play session):",
              *[f"  {i}. {c}" for i, c in enumerate(pending_checks(readme), 1)]]
    lines.append("Result: " + ("failures above" if code else "no failures"))
    write_state(state_path, {"source_id": config["source_id"], "checked_utc": now.isoformat(),
                             "machines": machines, "eligible": eligible})
    return lines, code


def _report_drops(config: Source, machines: dict, report_root: Path, now: datetime, report: Callable,
                  lines: list[str]) -> int:
    """Report latest drops (and the local file) whose bytes changed; a kept earlier file is compared."""
    code = 0
    preview = preview_inputs(config, now)
    latest = preview.latest()
    local = preview.files[0]  # The configured scan_path, which has no drop time.
    if not local.error and local.machine not in {f.machine for f in latest}:
        latest.append(local)
    for file in latest:
        machine = file.machine or "unknown"
        previous = machines.get(machine)
        if previous and _sha(file.path) == previous.get("sha256"):
            lines.append(f"{machine}: {file.path.name} unchanged since the previous run")
            continue
        earlier = Path(previous["path"]) if previous and Path(previous["path"]).is_file() else None
        folder, result, exit_code = report(file.path, config, report_root, earlier, now)
        current = file_state(file.path, folder, result)
        lines += file_summary(machine, previous, current)
        machines[machine] = current
        code = max(code, exit_code)
    return code


def _sha(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None
