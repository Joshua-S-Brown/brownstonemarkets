"""Display a comparison of two saved addon scans."""
import streamlit as st

from brownstone.action_board import compatible_catalogs
from brownstone.config import ADDON_PROVIDER
from brownstone.money import GOLD_TABLE_FORMAT, to_gold
from brownstone.scan_changes import METRICS, compare_scans, eligible_scans
from views.common import read_db, show_context, show_freshness

LABELS = {"min_buyout": "Min buyout", "market_value": "Market value", "listings": "Listings", "units": "Units"}


def render(config, catalogs):
    st.subheader("Scan changes")
    show_context(config)
    if config["provider"] != ADDON_PROVIDER:
        st.info("Scan changes requires an addon source. TSM snapshots have no addon scans to compare.")
        return
    if not (config["data_dir"] / "brownstone.duckdb").exists():
        st.info("Import at least two complete priced addon scans for this source and market to compare.")
        return
    try:
        with read_db(config) as db:
            scans = eligible_scans(db, config)
            if len(scans) < 2:
                st.info("Import at least two complete priced addon scans for this source and market to compare.")
                return
            _comparison(db, config, catalogs, scans)
    except Exception as error:
        st.error(f"Unable to compare scans: {error}")


def _comparison(db, config, catalogs, scans):
    by_id = {scan["scan_id"]: scan for scan in scans}
    def label(scan_id):
        return f"{by_id[scan_id]['finished_at']:%Y-%m-%d %H:%M:%S} UTC · {scan_id}"
    key = config["source_id"]
    first = st.selectbox("First scan", list(by_id), index=1, format_func=label, key=f"scan-first-{key}")
    second = st.selectbox("Second scan", [sid for sid in by_id if sid != first],
                          format_func=label, key=f"scan-second-{key}")
    selected = compatible_catalogs(catalogs, config)
    catalog_only = st.checkbox("Catalog items only", key=f"scan-catalog-{key}")
    item_ids = sorted({item for catalog in selected for item in catalog["items_by_id"]}) if catalog_only else None
    diff = compare_scans(db, config, first, second, item_ids)
    st.caption(f"Earlier: {label(diff['earlier']['scan_id'])} · Later: {label(diff['later']['scan_id'])} · "
               f"Gap: {diff['gap']}")
    for side in ("earlier", "later"):
        st.caption(f"{side.title()} scan freshness")
        show_freshness(config, {"updated_at": diff[side]["finished_at"].isoformat(),
                                "scan_id": diff[side]["scan_id"]}, warn=side == "later")
    st.caption("Prices are per unit in gold. No buyout, no market value and not listed are unavailable prices; "
               "changes are blank when either side is unavailable. Changed includes price or supply changes.")
    if catalog_only and not selected:
        st.info("No compatible recipe catalogs for the selected source; the catalog filter has no items.")
    for group, title in (("items", "Changed / unchanged"), ("new", "New"), ("vanished", "Vanished")):
        st.markdown(f"#### {title} ({len(diff[group]):,})")
        rows = [_display_row(row) for row in diff[group]]
        if rows:
            st.dataframe(rows, hide_index=True, width="stretch")
        else:
            st.info(f"No {title.lower()} items in this comparison.")


UNAVAILABLE = {"min_buyout": "no buyout", "market_value": "no market value"}


def _price(metric, value):
    return format(to_gold(value), GOLD_TABLE_FORMAT.removeprefix("%")) if value is not None else UNAVAILABLE[metric]


def _display_row(row):
    output = {"Item ID": row["item_id"], "Item": row["item_name"],
              "Status": _status(row)}
    for side in ("earlier", "later"):
        values = row[side]
        for metric in METRICS:
            value = values[metric] if values is not None else None
            display = "not listed" if values is None else _price(metric, value) if metric in METRICS[:2] else value
            suffix = " (g)" if metric in METRICS[:2] else ""
            output[f"{side.title()} {LABELS[metric]}{suffix}"] = display
    for metric in METRICS:
        value = row["change"][metric]
        output[f"Change {LABELS[metric]}" + (" (g)" if metric in METRICS[:2] else "")] = (
            to_gold(value) if metric in METRICS[:2] else value)
    return output


def _status(row):
    if row["earlier"] is None:
        return "New"
    if row["later"] is None:
        return "Vanished"
    return "Changed" if row["changed"] else "Unchanged"
