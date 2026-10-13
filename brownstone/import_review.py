"""Framework-free import review projections shared by both apps."""
from datetime import UTC

from brownstone import character_snapshots, journal, professions
from brownstone.freshness import observed_at
from brownstone.pipeline import import_guidance

_NO_SCANS = "The file has no scans."

def _count(number, singular, plural):
    return f"{number} {singular if number == 1 else plural}"

def scan_problems(preview):
    problems = []
    partial = [s["scan_id"] for s in preview.summaries if s["partial"] and s["scan_id"] in preview.new_ids]
    if partial:
        problems.append("New partial scan: " + ", ".join(partial))
    if any(preview.mismatches + preview.non_scan_mismatches):
        problems.append("Records from another auction house")
    return problems

def _quiet_empty(file, preview):
    return (not file.drop_time and file.error.startswith(_NO_SCANS)
            and any(f.preview for f in preview.files))

def summary(preview, machine, drop_time=None):
    scans, records = len(preview.new_ids), len(preview.new_record_ids)
    if scans or records:
        origin = f"dropped {drop_time:%d %b %H:%M UTC}" if drop_time else "local file"
        return (f"{machine}, {origin}: {_count(scans, 'new scan', 'new scans')}, "
                f"{_count(records, 'character record', 'character records')}")
    return nothing_new()


def nothing_new(note=""):
    return ("Nothing new for this source. If you scanned since, type /reload in game and Preview again. "
            "Don't /bscan clear until the new scan is imported." + note)


def scan_rows(preview, machine=None, drop_time=None):
    return [{
        "Machine": machine, "Drop (UTC)": str(drop_time or ""),
        "Scan ID": summary["scan_id"],
        "Started (UTC)": summary["started_at"].strftime("%Y-%m-%d %H:%M:%S UTC"),
        "Finished (UTC)": summary["finished_at"].strftime("%Y-%m-%d %H:%M:%S UTC"),
        "Status": summary["status"], "Listings": summary["listing_count"],
        "Import state": "Already imported" if existing else "Other house" if mismatch else "New",
        "Partial": summary["partial"],
    } for summary, existing, mismatch in zip(preview.summaries, preview.known, preview.mismatches, strict=True)]


def input_summary(preview, selected):
    lines = []
    problems = []
    already = sum(f.fully_imported for f in preview.files)
    quiet = any(_quiet_empty(f, preview) for f in preview.files)
    note = " Local scan_path file has no scans." if quiet else ""
    if not preview.new_files:
        lines.append(nothing_new(note))
    else:
        for file in preview.files:
            if str(file.path) in preview.new_files:
                lines.append(summary(file.preview, file.machine, file.drop_time))
        if already or quiet:
            lines.append(f"{_count(already, 'file', 'files')} already imported." + note)
    drops = sum(f.fully_imported for f in preview.files if f.drop_time)
    if drops:
        lines.append(f"{_count(drops, 'dropped file is', 'dropped files are')} fully imported and can be deleted "
                   "from the drop folder by hand")
    for file in preview.files:
        reasons = scan_problems(file.preview) if file.preview else []
        if file.error and not _quiet_empty(file, preview):
            reasons.append(file.error)
        # A selected new drop is the normal case; flag only drops this import would leave behind.
        if file.drop_time and not file.fully_imported and str(file.path) not in selected:
            reasons.append("not fully imported")
        if reasons:
            problems.append(f"{file.path.name}: " + "; ".join(reasons))
    return lines, problems

def clear_lines(preview):
    lines = []
    for file in preview.latest():
        if file.fully_imported:
            lines.append(f"{file.machine}: /bscan clear is safe only if you haven't played there "
                         "since its latest drop.")
        else:
            lines.append(f"{file.machine}: don't /bscan clear; its latest drop is not fully imported.")
    return lines

def import_messages(config, manifest):
    outcomes = "; ".join([f"{s['scan_id']} {s['status']}: {s['outcome']}" for s in manifest["scans"]] +
                         [f"{s['record_type']} {s['record_id']}: {s['outcome']}"
                          for s in manifest.get("snapshots", [])] +
                         [f"Journal {r['Character']} {r['Family']}: {r['Entries']} {r['Outcome']}"
                          for r in journal.outcome_rows(manifest.get("non_scan_records", []))])
    if manifest["status"] == "complete":
        result = ("success", f"Imported. Collection prices come from scan {manifest['scan_id']}. {outcomes}.")
    elif not manifest["scans"]:
        result = ("success", f"Imported character records; prices are unchanged. {outcomes}.")
    else:
        result = ("warning", f"No complete scan among the imported scans, so prices are unchanged. {outcomes}.")
    clear = (f"{config.get('machine')}: /bscan clear is safe only if you haven't scanned since this preview."
             if manifest["fully_imported"]
             else f"{config.get('machine')}: don't /bscan clear; records remain unimported.")
    return [result, ("caption", clear), ("info", import_guidance(manifest))]


def file_messages(results):
    return [("error" if r["status"] == "error" else "success",
             f"{r['file']}: {r.get('error', r['status'])}") for r in results]


def preview_failure(error):
    return [("error", f"Preview failed: {error}. The scan file or database "
             "may be busy: wait for /reload or logout to finish and for any other Brownstone import to end, "
             "then Preview again.")]


def import_failure(error, *, stale=False, drops=False):
    note = ("Nothing was imported." if stale else "Preview again." if drops else
            "Preview again before retrying. Your previous snapshot remains available.")
    return [("error", f"Import failed: {error}. {note}")]


def holdings_sections(config):
    return [(caption, reader(config)) for caption, reader in (
        ("Latest imported level, skills and known recipes with their evidence source; "
         "missing values are unknown", professions.latest_rows),
        ("Latest imported active-auction observation; missing counts are unknown", journal.active_auction_rows),
        ("Imported event journal by character and family", journal.latest_rows),
        ("Latest imported character snapshots (gold in gold; bank has its own observation time)",
         character_snapshots.latest_rows))]


def preview_sections(preview, machine=None, drop_time=None):
    return [("Journal preview", journal.preview_rows(preview, machine)),
            ("Character preview", character_snapshots.preview_rows(preview, machine)),
            ("Scan preview", scan_rows(preview, machine, drop_time))]


def preview_notes(preview):
    notes = []
    reasons = [reason for reasons in preview.non_scan_mismatches for reason in reasons]
    if reasons:
        notes.append("Other house: " + "; ".join(reasons))
    notes.append("Partial scans are preserved but never feed prices. Reads use best-effort change detection.")
    reasons = [reason for mismatch in preview.mismatches for reason in mismatch]
    if reasons:
        notes.append("Not importable into this source (another auction house): " + "; ".join(reasons))
    return notes


def status_chips(config, preview=None):
    """Read saved evidence only; checking drop files remains an explicit action."""
    from brownstone.storage import completed_snapshots

    manifests = completed_snapshots(config)
    count = imported_scan_count(manifests)
    newest = manifests[0] if manifests else None
    stamp = observed_at(newest).astimezone(UTC).strftime('%d %b %H:%M UTC') if newest else 'none yet'
    characters = len(professions.latest_data(config))
    folder = 'not configured' if not config.get('drop_folder') else 'check for new scans'
    if preview is not None and hasattr(preview, 'files'):
        drops = [f for f in preview.files if f.drop_time]
        folder = f'{len(drops)} files · {sum(f.fully_imported for f in drops)} imported'
    return [f'{count} scans imported · newest {stamp}', f'Drop folder · {folder}', f'{characters} characters']


def imported_scan_count(manifests):
    """Count unique imported complete scans, rather than collection manifests or stopped scans."""
    if not any('scans' in m for m in manifests):
        return len(manifests)
    return len({s['scan_id'] for m in manifests for s in m.get('scans', [])
                if s['status'] == 'completed' and s['outcome'] in {'imported', 'duplicate'}})


def file_status_lines(preview):
    """Per-machine locations and local empty-file guidance from the existing review evidence."""
    lines = [f"{f.machine} · latest drop {f.drop_time:%d %b %H:%M UTC}" for f in preview.latest()]
    for file in preview.files:
        if not file.drop_time:
            empty = file.preview is not None and not file.preview.summaries
            note = 'no scans in the file' if empty else 'see file details'
            lines.append(f'{file.machine} · game file · {note}')
    return lines
