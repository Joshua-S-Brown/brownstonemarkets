"""Today settings and evidence tables; calculations live in brownstone.today."""
from datetime import UTC, datetime

import streamlit as st

from brownstone.money import format_money, parse_money, to_gold
from brownstone.today import build_today
from brownstone.today_data import read_today_evidence
from brownstone.today_settings import TodaySettings, load_settings, save_settings, settings_path
from views.common import gold_columns, load_latest, read_db, show_context, show_freshness


def _settings(config):
    path = settings_path(config["data_dir"], config["source_id"])
    try:
        saved = load_settings(path)
    except (ValueError, TypeError, OSError) as error:
        st.warning(f"Could not read Today settings: {error}. Defaults are shown; save to replace this file.")
        saved = TodaySettings()
    with st.form(f"today-settings-{config['source_id']}"):
        gold = st.text_input("Gold available", value=format_money(saved.gold_copper))
        mode = st.selectbox("Minimum gain mode", ["scaled", "fixed"], index=["scaled", "fixed"].index(saved.mode))
        minimum = st.text_input("Fixed minimum gain", value=format_money(saved.minimum_copper))
        percent = st.number_input("Percentage of gold available", min_value=0.0, max_value=100.0,
                                  value=saved.percent_basis_points / 100, step=.1)
        crafts = st.number_input("Most crafts per item", min_value=1, max_value=1000, value=saved.max_crafts)
        submitted = st.form_submit_button("Save Today settings")
    if submitted:
        try:
            entered = TodaySettings(parse_money(gold), parse_money(minimum), mode, round(percent * 100), int(crafts))
            save_settings(path, entered)
        except (ValueError, OSError) as error:
            st.error(f"Settings not saved: {str(error).rstrip('.')}. "
                     "The tables below still use the last saved settings.")
        else:
            saved = entered
            st.success("Today settings saved locally.")
    st.caption(f"Minimum batch gain: {format_money(saved.minimum_gain)} · one funded plan · "
               "whole auction stacks are bought; surplus is shown · sales speed is unknown")
    if not saved.gold_copper:
        st.info("Enter the gold you have available to size the plan. Use explicit units, for example 12g 50s.")
    return saved


def render(config, catalogs):
    st.subheader("Today")
    show_context(config)
    settings = _settings(config)
    manifest, sid, _ = load_latest(config, "Refresh or import a scan for this market to inspect Today.")
    if manifest is None:
        return
    show_freshness(config, manifest)
    try:
        ids = sorted({item for c in catalogs for item in c["items_by_id"]})
        with read_db(config) as db:
            observations, listings, metrics, vendors = read_today_evidence(db, config, sid, ids)
        result = build_today(catalogs, observations, config, {**manifest, "snapshot_id": sid}, settings,
                             now=datetime.now(UTC), listings=listings, metrics=metrics, vendor_prices=vendors,
                             max_age_hours=config["max_age_hours"], auction_cut=config["auction_cut"])
    except Exception as error:
        st.error(f"Unable to build Today: {error}")
        return
    if not result["listing_evidence_available"]:
        st.info("Individual listings, thin markets, cheap now, undercuts and below-vendor listings: "
                "not available for this source. Batches use funds and the per-item cap; costs are aggregate estimates.")
    names = {i: item["name"] for c in catalogs for i, item in c["items_by_id"].items()}
    st.caption(f"Today rules v{result['today_version']} · cautious output price · "
               f"{config['auction_cut']:.0%} auction cut · source {config['source_id']} · "
               f"snapshot {sid} · scan {manifest.get('scan_id', 'not available for this source')}")
    _tables(result, names)


def _evidence(row):
    return {"State": "stale — inspect only" if row["stale"] else "potential gain",
            "Evidence time (UTC)": str(row["observed_at"]), "Time basis": row["time_basis"],
            "Source": row["source_id"],
            "Scan / snapshot": row["scan_id"] or row["snapshot_id"]}


def _table(title, rows, rest):
    st.markdown(f"#### {title}")
    if rows:
        gold = [key for key in rows[0] if key.endswith("(g)")]
        st.dataframe(rows, hide_index=True, width="stretch", column_config=gold_columns(*gold))
    else:
        st.info("No rows clear these settings with the available evidence.")
    st.caption(f"{rest} more rows outside this list's 10-row limit.")


def _tables(result, names):
    sells = {r["output_item_id"]: r for r in result["sell"]}
    craft = [_craft_row(row, sells[row["output_item_id"]]) for row in result["craft"]]
    _table("1. Craft today", craft, result["remaining"]["craft"])
    hidden = "; ".join(f"{reason}: {count}" for reason, count in sorted(result["hidden"].items()))
    st.caption("Hidden recipes: " + (hidden or "0"))
    buy = [{"Material": names.get(r["item_id"], f"Item {r['item_id']}"), "Item ID": r["item_id"],
            "Route": r["method"], "Required units": r["quantity"], "Purchased units": r["purchased_units"],
            "Cost (g)": to_gold(r["cost_copper"]), "Highest unit price (g)": to_gold(r["highest_unit_copper"]),
            "Scan p25 (g)": to_gold(r["p25_copper"]), "Cheap now": r["cheap_now"], **_evidence(r)}
           for r in result["buy"]]
    _table("2. Buy for these crafts", buy, result["remaining"]["buy"])
    st.caption(f"Whole shopping list: {format_money(result['shopping_total_copper'])}. "
               "Cheap now means average paid is strictly below scan p25; informational only. Vendor stock is unknown.")
    _table("3. Sell", [_sell_row(row) for row in result["sell"]], result["remaining"]["sell"])
    with st.expander("Below vendor price — independent aside, not part of the craft budget"):
        _table("Below vendor price", [{"Item": names.get(r["item_id"], f"Item {r['item_id']}"),
                "Item ID": r["item_id"], "Listings": r["listings"], "Units": r["purchased_units"],
                "Cost (g)": to_gold(r["cost_copper"]), "Vendor pays per unit (g)": to_gold(r["vendor_sell_copper"]),
                "Highest listing unit (g)": to_gold(r["highest_unit_copper"]), "Gain (g)": to_gold(r["gain_copper"]),
                **_evidence(r)} for r in result["below_vendor"]], result["remaining"]["below_vendor"])


def _craft_row(row, sell):
    return {"Item": row["output_name"], "Profession": row["profession"].title(), "Catalog": row["catalog_id"],
            "Recipe": row["recipe_id"], "Batch": row["batch_size"], "Limited by": row["limiting_factor"],
            "Material cost (g)": to_gold(row["batch_cost_copper"]),
            "Batch profit (g)": to_gold(row["batch_profit_copper"]),
            "Profit per craft (g)": to_gold(row["profit_per_craft_copper"]),
            "Cautious output unit (g)": to_gold(row["sale_price_copper"]), "Listings": sell["listings"],
            "Units": sell["units"], "Thin": sell["thin"], "Availability": row["availability"],
            "Evidence notes": "; ".join(row["evidence_notes"]), "Recipe source": row["recipe_source"], **_evidence(row)}


def _sell_row(row):
    return {"Output": row["output_name"], "Catalog": row["catalog_id"], "Recipe": row["recipe_id"],
            "Batch": row["batch_size"], "Lowest competing unit (g)": to_gold(row["lowest_copper"]),
            "Listings": row["listings"], "Units": row["units"], "Largest stack units": row["largest_stack_units"],
            "Undercut unit (g)": to_gold(row["undercut_copper"]),
            "Profit at undercut for batch (g)": to_gold(row["undercut_batch_profit_copper"]),
            "Thin": row["thin"], **_evidence(row)}
