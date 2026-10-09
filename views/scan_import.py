"""Explicit addon preview, selection and reviewed import controls."""
import streamlit as st

from brownstone import character_snapshots, journal, professions
from brownstone.pipeline import (
    StalePreviewError,
    import_guidance,
    import_scans,
    preview_configuration,
    preview_scans,
)
from brownstone.scan_inputs import (
    CLEAR_REMINDER,
    file_rows,
    import_inputs,
    latest_rows,
    preview_inputs,
)

_STATE = ("scan_import_preview", "scan_import_selection", "scan_import_result", "scan_import_details")
# Prefix of the pipeline error for a SavedVariables file the game hasn't written scans to yet.
_NO_SCANS = "The file has no scans."


def render(config):
    with st.expander("Imported character data"):
        _show_holdings(config)
    if config.get("drop_folder"):
        _render_inputs(config)
        return
    _reset_identity(config)
    if st.button("Preview addon scans", help=f"Reads {config['scan_path']}", width="stretch"):
        for key in _STATE:
            st.session_state.pop(key, None)
        try:
            st.session_state["scan_import_preview"] = preview_scans(config)
        except Exception as error:
            st.session_state["scan_import_result"] = [("error", f"Preview failed: {error}. The scan file or database "
                "may be busy: wait for /reload or logout to finish and for any other Brownstone import to end, "
                "then Preview again.")]
    # The import runs in the button's callback, before this rerun, so the result replaces the reviewed table.
    messages, failed = _show_results()
    preview = st.session_state.get("scan_import_preview")
    if preview is None:
        _result_details(messages, failed)
        return
    default = preview.new_ids
    selected = st.session_state.get("scan_import_selection", default)
    _summary(preview, config.get("machine"))
    button = st.container()
    problems = _scan_problems(preview)
    if set(selected) != set(default):
        problems.append("Selection differs from the default")
    _warning(problems)
    with st.expander("Details", expanded=_details_open(problems, failed)):
        _detail_messages(messages)
        _show_preview(preview, config.get("machine"))
        if preview.new_ids or preview.new_record_ids:
            selected = st.multiselect("New scans to import", default, default=default, key="scan_import_selection")
            if preview.new_record_ids:
                st.caption("All new matching character records in this file will also be imported.")
    if selected or preview.new_record_ids:
        with button:
            st.button("Import addon scan", type="primary", width="stretch", on_click=_import, args=(config, preview))


def _show_results():
    messages = st.session_state.pop("scan_import_result", [])
    for kind, message in messages:
        if kind != "info":
            getattr(st, kind)(message)
    return messages, any(kind == "error" for kind, _ in messages)


def _detail_messages(messages):
    for kind, message in messages:
        if kind == "info":
            st.info(message)


def _result_details(messages, failed):
    # Errors are already shown above; Details only appears when it has notes to hold.
    if any(kind == "info" for kind, _ in messages):
        with st.expander("Details", expanded=failed):
            _detail_messages(messages)


def _details_open(problems, failed):
    """Open Details on problems and keep it open for the rest of this review, so it never closes mid-edit."""
    if problems or failed:
        st.session_state["scan_import_details"] = True
    return st.session_state.get("scan_import_details", False)


def _count(number, singular, plural):
    return f"{number} {singular if number == 1 else plural}"


def _summary(preview, machine, drop_time=None):
    scans, records = len(preview.new_ids), len(preview.new_record_ids)
    if scans or records:
        origin = f"dropped {drop_time:%d %b %H:%M UTC}" if drop_time else "local file"
        st.caption(f"{machine}, {origin}: {_count(scans, 'new scan', 'new scans')}, "
                   f"{_count(records, 'character record', 'character records')}")
    else:
        _nothing_new()


def _nothing_new(note=""):
    st.caption("Nothing new for this source. If you scanned since, type /reload in game and Preview again. "
               "Don't /bscan clear until the new scan is imported." + note)


def _scan_problems(preview):
    problems = []
    partial = [s["scan_id"] for s in preview.summaries if s["partial"] and s["scan_id"] in preview.new_ids]
    if partial:
        problems.append("New partial scan: " + ", ".join(partial))
    if any(preview.mismatches + preview.non_scan_mismatches):
        problems.append("Records from another auction house")
    return problems


def _warning(problems):
    if problems:
        st.warning("; ".join(problems))


def _show_holdings(config):
    skills = professions.latest_rows(config)
    if skills:
        st.caption("Latest imported level, skills and listed recipes; missing values are unknown")
        st.dataframe(skills, hide_index=True)
    auctions = journal.active_auction_rows(config)
    if auctions:
        st.caption("Latest imported active-auction observation; missing counts are unknown")
        st.dataframe(auctions, hide_index=True)
    entries = journal.latest_rows(config)
    if entries:
        st.caption("Imported event journal by character and family")
        st.dataframe(entries, hide_index=True)
    holdings = character_snapshots.latest_rows(config)
    if holdings:
        st.caption("Latest imported character snapshots (gold in gold; bank has its own observation time)")
        st.dataframe(holdings, hide_index=True)


def _show_preview(preview, machine=None, drop_time=None):
    entries = journal.preview_rows(preview, machine)
    if entries:
        st.dataframe(entries, hide_index=True)
    if preview.snapshots:
        st.dataframe(character_snapshots.preview_rows(preview, machine), hide_index=True)
    reasons = [reason for reasons in preview.non_scan_mismatches for reason in reasons]
    if reasons:
        st.caption("Other house: " + "; ".join(reasons))
    st.dataframe([{
        "Machine": machine, "Drop (UTC)": str(drop_time or ""),
        "Scan ID": summary["scan_id"],
        "Started (UTC)": summary["started_at"].strftime("%Y-%m-%d %H:%M:%S UTC"),
        "Finished (UTC)": summary["finished_at"].strftime("%Y-%m-%d %H:%M:%S UTC"),
        "Status": summary["status"], "Listings": summary["listing_count"],
        "Import state": "Already imported" if existing else "Other house" if mismatch else "New",
        "Partial": summary["partial"],
    } for summary, existing, mismatch in zip(preview.summaries, preview.known, preview.mismatches, strict=True)],
        hide_index=True)
    st.caption("Partial scans are preserved but never feed prices. Reads use best-effort change detection.")
    reasons = [reason for mismatch in preview.mismatches for reason in mismatch]
    if reasons:
        st.caption("Not importable into this source (another auction house): " + "; ".join(reasons))


def _import(config, preview):
    """Button callback: import the reviewed selection and keep the messages for the rerun."""
    st.session_state.pop("scan_import_preview", None)
    try:
        manifest = import_scans(config, scan_ids=st.session_state.get("scan_import_selection", []),
                                reviewed=preview)
    except StalePreviewError as error:
        st.session_state["scan_import_result"] = [("error", f"Import failed: {error}. Nothing was imported.")]
        return
    except Exception as error:
        st.session_state["scan_import_result"] = [("error", f"Import failed: {error}. Preview again before "
                                                            "retrying. Your previous snapshot remains available.")]
        return
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
    st.session_state["scan_import_result"] = [result, ("caption", clear), ("info", import_guidance(manifest))]


def _render_inputs(config):
    _reset_identity(config)
    if st.button("Preview addon scans", width="stretch"):
        for key in _STATE:
            st.session_state.pop(key, None)
        st.session_state["scan_import_preview"] = preview_inputs(config)
    messages, failed = _show_results()
    preview = st.session_state.get("scan_import_preview")
    if preview is None:
        _result_details(messages, failed)
        return
    default = preview.new_files
    selected = st.session_state.get("scan_import_selection", default)
    problems = _input_summary(preview, selected)
    button = st.container()
    if set(selected) != set(default):
        problems.append("Selection differs from the default")
    _warning(problems)
    if messages:
        _clear_lines(preview)
    with st.expander("Details", expanded=_details_open(problems, failed)):
        _detail_messages(messages)
        selected = _input_details(preview, default)
    if selected:
        with button:
            st.button("Import addon scan", type="primary", width="stretch", on_click=_import_inputs,
                      args=(config, preview))


def _input_details(preview, default):
    st.dataframe(file_rows(preview), hide_index=True)
    for file in preview.files:
        if file.preview:
            st.caption(f"{file.path.name} — machine: {file.machine}; drop UTC: {file.drop_time or 'local file'}")
            _show_preview(file.preview, file.machine, file.drop_time)
    st.dataframe(latest_rows(preview), hide_index=True)
    st.info(CLEAR_REMINDER)
    choices = [str(f.path) for f in preview.files if f.matching_ids or f.matching_records]
    selected = []
    if choices:
        selected = st.multiselect("Files to import (each archived separately)", choices,
                                  default=default, key="scan_import_selection")
    return selected


def _input_summary(preview, selected):
    problems = []
    already = sum(f.fully_imported for f in preview.files)
    quiet = any(_quiet_empty(f, preview) for f in preview.files)
    note = " Local scan_path file has no scans." if quiet else ""
    if not preview.new_files:
        _nothing_new(note)
    else:
        for file in preview.files:
            if str(file.path) in preview.new_files:
                _summary(file.preview, file.machine, file.drop_time)
        if already or quiet:
            st.caption(f"{_count(already, 'file', 'files')} already imported." + note)
    drops = sum(f.fully_imported for f in preview.files if f.drop_time)
    if drops:
        st.caption(f"{_count(drops, 'dropped file is', 'dropped files are')} fully imported and can be deleted "
                   "from the drop folder by hand")
    for file in preview.files:
        reasons = _scan_problems(file.preview) if file.preview else []
        if file.error and not _quiet_empty(file, preview):
            reasons.append(file.error)
        # A selected new drop is the normal case; flag only drops this import would leave behind.
        if file.drop_time and not file.fully_imported and str(file.path) not in selected:
            reasons.append("not fully imported")
        if reasons:
            problems.append(f"{file.path.name}: " + "; ".join(reasons))
    return problems


def _quiet_empty(file, preview):
    return (not file.drop_time and file.error.startswith(_NO_SCANS)
            and any(f.preview for f in preview.files))


def _clear_lines(preview):
    for file in preview.latest():
        if file.fully_imported:
            st.caption(f"{file.machine}: /bscan clear is safe only if you haven't played there since its latest drop.")
        else:
            st.caption(f"{file.machine}: don't /bscan clear; its latest drop is not fully imported.")


def _import_inputs(config, preview):
    st.session_state.pop("scan_import_preview", None)
    try:
        results = import_inputs(config, preview, st.session_state.get("scan_import_selection", []))
        messages = [("error" if r["status"] == "error" else "success",
                     f"{r['file']}: {r.get('error', r['status'])}") for r in results]
        # Fresh read after import supplies per-file and latest-machine cleanup evidence.
        st.session_state["scan_import_preview"] = preview_inputs(config)
        st.session_state.pop("scan_import_selection", None)
        st.session_state.pop("scan_import_details", None)
        st.session_state["scan_import_result"] = messages
    except StalePreviewError as error:
        st.session_state["scan_import_result"] = [("error", f"Import failed: {error}. Nothing was imported.")]
    except Exception as error:
        st.session_state["scan_import_result"] = [("error", f"Import failed: {error}. Preview again.")]


def _reset_identity(config):
    identity = preview_configuration(config)
    # One active review only: switching away and back cannot resurrect an old selection or result.
    if st.session_state.get("scan_import_identity") != identity:
        for key in _STATE:
            st.session_state.pop(key, None)
        st.session_state["scan_import_identity"] = identity
