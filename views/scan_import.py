"""Explicit addon preview, selection and reviewed import controls."""
import streamlit as st

from brownstone import import_review as review
from brownstone.pipeline import (
    StalePreviewError,
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
from views.watchlist import render_hits

_STATE = ("scan_import_preview", "scan_import_selection", "scan_import_result", "scan_import_details")


def render(config):
    with st.expander("Imported character data"):
        _show_holdings(config)
    if config.get("drop_folder"):
        _render_inputs(config)
        return
    if st.button("Preview addon scans", help=f"Reads {config['scan_path']}", width="stretch"):
        for key in _STATE:
            st.session_state.pop(key, None)
        try:
            st.session_state["scan_import_preview"] = preview_scans(config)
        except Exception as error:
            st.session_state["scan_import_result"] = review.preview_failure(error)
    # The import runs in the button's callback, before this rerun, so the result replaces the reviewed table.
    messages, failed = _show_results(config)
    preview = st.session_state.get("scan_import_preview")
    if preview is None:
        _result_details(messages, failed)
        return
    default = preview.new_ids
    selected = st.session_state.get("scan_import_selection", default)
    _summary(preview, config.get("machine"))
    button = st.container()
    problems = review.scan_problems(preview)
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


def _show_results(config):
    messages = st.session_state.pop("scan_import_result", [])
    for kind, message in messages:
        if kind != "info":
            getattr(st, kind)(message)
    if any(kind == "success" for kind, _ in messages):
        render_hits(config)
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



def _summary(preview, machine, drop_time=None):
    st.caption(review.summary(preview, machine, drop_time))


def _warning(problems):
    if problems:
        st.warning("; ".join(problems))


def _show_holdings(config):
    for caption, rows in review.holdings_sections(config):
        if rows:
            st.caption(caption)
            st.dataframe(rows, hide_index=True)


def _show_preview(preview, machine=None, drop_time=None):
    sections = review.preview_sections(preview, machine, drop_time)
    notes = review.preview_notes(preview)
    # Retain Streamlit's presentation order and empty scan table behavior.
    for _, rows in sections[:2]:
        if rows:
            st.dataframe(rows, hide_index=True)
    if preview.non_scan_mismatches and notes[0].startswith("Other house:"):
        st.caption(notes.pop(0))
    st.dataframe(sections[2][1], hide_index=True)
    for note in notes:
        st.caption(note)


def _import(config, preview):
    """Button callback: import the reviewed selection and keep the messages for the rerun."""
    st.session_state.pop("scan_import_preview", None)
    try:
        manifest = import_scans(config, scan_ids=st.session_state.get("scan_import_selection", []),
                                reviewed=preview)
    except StalePreviewError as error:
        st.session_state["scan_import_result"] = review.import_failure(error, stale=True)
        return
    except Exception as error:
        st.session_state["scan_import_result"] = review.import_failure(error)
        return
    st.session_state["scan_import_result"] = review.import_messages(config, manifest)


def _render_inputs(config):
    if st.button("Preview addon scans", width="stretch"):
        for key in _STATE:
            st.session_state.pop(key, None)
        st.session_state["scan_import_preview"] = preview_inputs(config)
    messages, failed = _show_results(config)
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
    lines, problems = review.input_summary(preview, selected)
    for line in lines:
        st.caption(line)
    return problems



def _clear_lines(preview):
    for line in review.clear_lines(preview):
        st.caption(line)


def _import_inputs(config, preview):
    st.session_state.pop("scan_import_preview", None)
    try:
        results = import_inputs(config, preview, st.session_state.get("scan_import_selection", []))
        messages = review.file_messages(results)
        # Fresh read after import supplies per-file and latest-machine cleanup evidence.
        st.session_state["scan_import_preview"] = preview_inputs(config)
        st.session_state.pop("scan_import_selection", None)
        st.session_state.pop("scan_import_details", None)
        st.session_state["scan_import_result"] = messages
    except StalePreviewError as error:
        st.session_state["scan_import_result"] = review.import_failure(error, stale=True)
    except Exception as error:
        st.session_state["scan_import_result"] = review.import_failure(error, drops=True)


def reset_identity(config):
    identity = preview_configuration(config)
    # One active review only: switching away and back cannot resurrect an old selection or result.
    if st.session_state.get("scan_import_identity") != identity:
        for key in _STATE:
            st.session_state.pop(key, None)
        st.session_state["scan_import_identity"] = identity
