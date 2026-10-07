"""Explicit addon preview, selection and reviewed import controls."""
import streamlit as st

from brownstone import character_snapshots, journal
from brownstone.pipeline import import_guidance, import_scans, preview_configuration, preview_scans
from brownstone.scan_inputs import (
    CLEAR_REMINDER,
    file_rows,
    import_inputs,
    latest_rows,
    preview_inputs,
)

_STATE = ("scan_import_preview", "scan_import_selection", "scan_import_result")


def render(config):
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
            st.error(f"Preview failed: {error}. The scan file or database may be busy: wait for /reload or "
                     "logout to finish and for any other Brownstone import to end, then Preview again.")
    # The import runs in the button's callback, before this rerun, so the result replaces the reviewed table.
    for kind, message in st.session_state.pop("scan_import_result", []):
        getattr(st, kind)(message)
    preview = st.session_state.get("scan_import_preview")
    if preview is None:
        return
    _show_preview(preview, config.get("machine"))
    if not preview.new_ids and not preview.new_record_ids:
        st.warning("Nothing new for this source: every record was imported before or is from another auction "
                   "house. If you scanned since, type /reload in game and Preview again. Don't /bscan clear "
                   "until the new scan is imported.")
        return
    selected = st.multiselect("New scans to import", preview.new_ids, default=preview.new_ids,
                              key="scan_import_selection")
    if selected or preview.new_record_ids:
        if preview.new_record_ids:
            st.caption("All new matching character records in this file will also be imported.")
        st.button("Import addon scan", type="primary", width="stretch", on_click=_import, args=(config, preview))


def _show_holdings(config):
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
    st.session_state["scan_import_result"] = [result, ("info", import_guidance(manifest))]


def _render_inputs(config):
    _reset_identity(config)
    if st.button("Preview addon scans", width="stretch"):
        for key in _STATE:
            st.session_state.pop(key, None)
        st.session_state["scan_import_preview"] = preview_inputs(config)
    for kind, message in st.session_state.pop("scan_import_result", []):
        getattr(st, kind)(message)
    preview = st.session_state.get("scan_import_preview")
    if preview is None:
        return
    st.dataframe(file_rows(preview), hide_index=True)
    for file in preview.files:
        if file.preview:
            st.caption(f"{file.path.name} — machine: {file.machine}; drop UTC: {file.drop_time or 'local file'}")
            _show_preview(file.preview, file.machine, file.drop_time)
    st.dataframe(latest_rows(preview), hide_index=True)
    st.info(CLEAR_REMINDER)
    choices = [str(f.path) for f in preview.files if f.matching_ids or f.matching_records]
    if choices:
        selected = st.multiselect("Files to import (each archived separately)", choices,
                                  default=preview.new_files, key="scan_import_selection")
        if selected:
            st.button("Import addon scan", type="primary", width="stretch", on_click=_import_inputs,
                      args=(config, preview))


def _import_inputs(config, preview):
    st.session_state.pop("scan_import_preview", None)
    try:
        results = import_inputs(config, preview, st.session_state.get("scan_import_selection", []))
        messages = [("error" if r["status"] == "error" else "success",
                     f"{r['file']}: {r.get('error', r['status'])}") for r in results]
        # Fresh read after import supplies per-file and latest-machine cleanup evidence.
        st.session_state["scan_import_preview"] = preview_inputs(config)
        st.session_state["scan_import_result"] = messages
    except Exception as error:
        st.session_state["scan_import_result"] = [("error", f"Import failed: {error}. Preview again.")]


def _reset_identity(config):
    identity = preview_configuration(config)
    # One active review only: switching away and back cannot resurrect an old selection or result.
    if st.session_state.get("scan_import_identity") != identity:
        for key in _STATE:
            st.session_state.pop(key, None)
        st.session_state["scan_import_identity"] = identity
