"""Explicit addon preview, selection and reviewed import controls."""
import streamlit as st

from brownstone.pipeline import import_guidance, import_scans, preview_configuration, preview_scans

_STATE = ("scan_import_preview", "scan_import_selection", "scan_import_result")


def render(config):
    identity = preview_configuration(config)
    # One active review only: switching away and back cannot resurrect an old selection or result.
    if st.session_state.get("scan_import_identity") != identity:
        for key in _STATE:
            st.session_state.pop(key, None)
        st.session_state["scan_import_identity"] = identity
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
    _show_preview(preview)
    if not preview.new_ids:
        st.warning("Nothing new for this source: every scan was imported before or is from another auction "
                   "house. If you scanned since, type /reload in game and Preview again. Don't /bscan clear "
                   "until the new scan is imported.")
        return
    selected = st.multiselect("New scans to import", preview.new_ids, default=preview.new_ids,
                              key="scan_import_selection")
    if selected:
        st.button("Import addon scan", type="primary", width="stretch", on_click=_import, args=(config, preview))


def _show_preview(preview):
    st.dataframe([{
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
    outcomes = "; ".join(f"{s['scan_id']} {s['status']}: {s['outcome']}" for s in manifest["scans"])
    if manifest["status"] == "complete":
        result = ("success", f"Imported. Collection prices come from scan {manifest['scan_id']}. {outcomes}.")
    else:
        result = ("warning", f"No complete scan among the imported scans, so prices are unchanged. {outcomes}.")
    st.session_state["scan_import_result"] = [result, ("info", import_guidance(manifest))]
