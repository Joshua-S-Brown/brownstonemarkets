"""Markdown presentation of beta evidence. No raw listing payloads enter this view.

The Markdown is a compact reading copy: repeated passes collapse to counts and long ID lists are cut.
report.json keeps every check and ID.
"""
import json
from collections import defaultdict

from .money import to_gold

ID_LIMIT = 10


def markdown(report: dict) -> str:
    totals = report["totals"]
    lines = ["# Beta evidence report", "", report["generated_utc"], "",
             f"{totals['pass']} pass, {totals['warn']} warn, {totals['fail']} fail", ""]
    lines += _checks(report["checks"])
    lines += _coverage(report.get("coverage", []))
    if 'farming_capture' in report:
        capture = report['farming_capture']
        lines += ['', '## Farming capture', '',
                  f"Loot windows: {capture['loot_windows']}; with positions: {capture['windows_with_positions']}; "
                  f"with coin slots: {capture['windows_with_coin_slots']}; "
                  f"with vendor prices: {capture['windows_with_vendor_prices']}. "
                  f"Coin slots: {capture['coin_slots']}; vendor prices: {capture['vendor_prices']}. "
                  f"With captured names: {capture['windows_with_names']}.",
                  'NPC IDs still unnamed: ' + (', '.join(map(str, capture['unnamed_npc_ids'])) or 'none') + '.']
    lines += _scan_attempts(report.get("scan_attempts", {}))
    lines += _vendor_prices(report.get("vendor_prices", {}))
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


def _vendor_prices(section: dict) -> list[str]:
    lines = ["", "## Vendor prices", "", "Captured purchase prices; catalog values are unchanged."]
    rows = section.get("observations", [])
    if not rows:
        return lines + ["", "No vendor price lists captured."]
    lines += ["", "| Item | Vendor NPC | Zone | Gold per purchase | Quantity | Stock | Standing | "
              "Catalog comparison | Entry |",
              "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for row in rows:
        stock = "unlimited" if row["stock"] == -1 else row["stock"]
        price = str(to_gold(row["price_copper"])) if type(row["price_copper"]) is int else "unknown"
        if row["extended_cost"] is not False:
            price += " (cost evidence only)"
        comparison = "; ".join(f"{c['catalog'] or 'uncatalogued'}: {c['result']}" for c in row["comparisons"])
        lines.append("| " + " | ".join(_cell(v) for v in (
            row["item_id"], row["vendor_npc_id"], row["zone"], price, row["quantity"], stock,
            row["standing"], comparison, row["entry_id"])) + " |")
    return lines


def _scan_attempts(section: dict) -> list[str]:
    if not section.get("recorded"):
        return []
    lines = ["", "## Scan attempts", "",
             f"Last answered scan: {section.get('last_reply_utc') or 'none recorded'}. Failed starts: "
             f"{len(section['attempts'])}."]
    if section["attempts"]:
        lines += ["", "| Started (UTC) | Reason | Waited (s) | Minutes since last answered scan | Late reply (s) |",
                  "| --- | --- | --- | --- | --- |"]
        for row in section["attempts"]:
            since = row["since_last_reply_seconds"]
            cells = [row["at_utc"], row["reason"], row["waited_seconds"],
                     since // 60 if type(since) is int else None, row["late_reply_seconds"]]
            lines.append("| " + " | ".join("unknown" if v is None else _cell(v) for v in cells) + " |")
    return lines
