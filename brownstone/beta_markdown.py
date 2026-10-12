"""Markdown presentation of beta evidence. No raw listing payloads enter this view.

The Markdown is a compact reading copy: repeated passes collapse to counts and long ID lists are cut.
report.json keeps every check and ID.
"""
import json
from collections import defaultdict

from brownstone.money import to_gold

ID_LIMIT = 10


def markdown(report: dict) -> str:
    totals = report["totals"]
    lines = ["# Beta evidence report", "", report["generated_utc"], "",
             f"{totals['pass']} pass, {totals['warn']} warn, {totals['fail']} fail", ""]
    lines += _checks(report["checks"])
    lines += _coverage(report.get("coverage", []))
    lines += ["", "## Gold display", ""]
    for character in report.get("characters", []):
        for snapshot in character["snapshots"]:
            lines.append(f"- {_cell(character['character'])}, {_cell(snapshot['snapshot_id'])}: "
                         f"{to_gold(snapshot['gold_copper'])} gold ({snapshot['gold_copper']} copper)")
    lines += ["", "## Facts", "", "Every check and entry ID is in report.json.", "", "```json",
              json.dumps(_facts(report), indent=2, ensure_ascii=False), "```", ""]
    return "\n".join(lines)


def _checks(checks: list[dict]) -> list[str]:
    passes: dict[str, list[dict]] = defaultdict(list)
    for row in checks:
        if row["status"] == "pass":
            passes[row["check"]].append(row)
    shown = [row for row in checks if row["status"] != "pass" or len(passes[row["check"]]) == 1]
    lines = ["## Checks", "", "| Check | Status | Entry IDs | Evidence |", "| --- | --- | --- | --- |"]
    for row in shown:
        # Coverage evidence is the checklist table below; the row names its action only.
        detail = row["detail"]["action"] if row["check"] == "coverage" else row["detail"]
        lines.append("| " + " | ".join(_cell(value) for value in
                     (row["check"], row["status"], _ids(row["entry_ids"]), detail)) + " |")
    repeated = {name: len(rows) for name, rows in passes.items() if len(rows) > 1}
    if repeated:
        lines += ["", "Repeated passes: " + ", ".join(f"{name} ×{count}" for name, count in repeated.items())]
    return lines


def _coverage(rows: list[dict]) -> list[str]:
    lines = ["", "## Checklist coverage", "", "| Checklist | Action | Seen | Unseen | Installed hooks |",
             "| --- | --- | --- | --- | --- |"]
    for row in rows:
        lines.append("| " + " | ".join(_cell(value) for value in (
            row["checklist"], row["action"], ", ".join(row["seen"]) or "—", ", ".join(row["unseen"]) or "—",
            ", ".join(row["installed"]) or "—")) + " |")
    return lines


def _ids(ids: list[str]) -> str:
    return ", ".join(ids[:ID_LIMIT]) + (f" (+{len(ids) - ID_LIMIT} more)" if len(ids) > ID_LIMIT else "")


def _facts(report: dict) -> dict:
    sessions = [{k: v for k, v in s.items() if k != "entry_ids"} | {"records": len(s["entry_ids"])}
                for s in report.get("load_sessions", [])]
    return {k: v for k, v in report.items() if k not in ("checks", "coverage", "load_sessions")} | {
        "load_sessions": sessions}


def _cell(value) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text.replace("|", "\\|").replace("\n", "<br>").replace("`", "&#96;")
