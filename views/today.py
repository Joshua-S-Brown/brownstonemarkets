"""Today settings and evidence tables; calculations live in brownstone.today."""
import hashlib
import json
from datetime import UTC, datetime

import streamlit as st

from brownstone.money import format_money, parse_money, to_gold
from brownstone.today import build_today, craft_details
from brownstone.today_data import read_today_evidence
from brownstone.today_settings import TodaySettings, load_settings, save_settings, settings_path
from views.common import gold_columns, load_latest, read_db, show_context, show_freshness


def _settings(config):
    path = settings_path(config["data_dir"], config["source_id"])
    unreadable = False
    try:
        saved = load_settings(path)
    except (ValueError, TypeError, OSError) as error:
        st.warning(f"Could not read Today settings: {error}. Defaults are shown; save to replace this file.")
        saved = TodaySettings()
        unreadable = True
    summary = st.empty()
    with st.expander("Today settings", expanded=unreadable or saved.gold_copper == 0):
        st.caption("One funded plan · whole auction stacks are bought; surplus is shown · sales speed is unknown")
        return _settings_form(config, path, saved, summary)


def _settings_form(config, path, saved, summary):
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
    summary.caption(f"Gold available: {format_money(saved.gold_copper)} · "
                    f"Minimum batch gain: {format_money(saved.minimum_gain)} · "
                    f"Most crafts per item: {saved.max_crafts}")
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
    freshness = result["freshness"]
    st.caption(f"Today rules v{result['today_version']} · cautious output price · "
               f"{config['auction_cut']:.0%} auction cut · source {config['source_id']} · "
               f"market {config['market_id']} · snapshot {sid} · "
               f"scan {manifest.get('scan_id', 'not available for this source')} · "
               f"evidence {freshness['observed_at']} (UTC) · time basis {freshness['basis']}")
    _tables(result, names)


def _evidence(row):
    return {"State": "stale — inspect only" if row["stale"] else "potential gain"}


def _table(rows, rest, decisions, key, *, selection_key=None):
    evidence = st.toggle("Show evidence columns", key=f"today-evidence-{key}")
    if rows:
        columns = [*decisions, "State"]
        if evidence:
            columns.extend(name for name in rows[0] if name not in columns)
        displayed = [{name: row[name] for name in columns} for row in rows]
        gold = [name for name in columns if name.endswith("(g)")]
        options = ({"key": selection_key, "on_select": "rerun", "selection_mode": "single-row"}
                   if selection_key else {})
        event = st.dataframe(displayed, hide_index=True, width="stretch",
                             column_config=gold_columns(*gold), **options)
        selected = event.selection.rows if selection_key else []
    else:
        st.info("No rows clear these settings with the available evidence.")
    st.caption(f"{rest} more rows outside this list's 10-row limit.")
    return selected if rows else []


def _tables(result, names):
    sells = {r["output_item_id"]: r for r in result["sell"]}
    craft = [_craft_row(row, sells[row["output_item_id"]]) for row in result["craft"]]
    craft_tab, buy_tab, sell_tab, vendor_tab = st.tabs(["Craft", "Buy", "Sell", "Below vendor"])
    with craft_tab:
        selected = _table(craft, result["remaining"]["craft"],
               ["Item", "Profession", "Batch", "Limited by", "Material cost (g)", "Batch profit (g)",
                "Profit per craft (g)", "Thin"], "craft", selection_key=_selection_key(result))
        if selected:
            _craft_details(result["craft"][selected[0]])
        elif craft:
            st.caption("Select a craft row to see its materials and catalog craft steps.")
        hidden = "; ".join(f"{reason}: {count}" for reason, count in sorted(result["hidden"].items()))
        st.caption("Hidden recipes: " + (hidden or "0"))
    with buy_tab:
        buy = [{"Material": names.get(r["item_id"], f"Item {r['item_id']}"), "Item ID": r["item_id"],
                "Route": r["method"], "Required units": r["quantity"], "Purchased units": r["purchased_units"],
                "Cost (g)": to_gold(r["cost_copper"]), "Highest unit price (g)": to_gold(r["highest_unit_copper"]),
                "Scan p25 (g)": to_gold(r["p25_copper"]), "Cheap now": r["cheap_now"], **_evidence(r)}
               for r in result["buy"]]
        _table(buy, result["remaining"]["buy"],
               ["Material", "Route", "Required units", "Purchased units", "Cost (g)",
                "Highest unit price (g)", "Cheap now"], "buy")
        st.caption(f"Whole shopping list: {format_money(result['shopping_total_copper'])}. "
                   "Cheap now means average paid is strictly below scan p25; informational only. "
                   "Vendor stock is unknown.")
    with sell_tab:
        _table([_sell_row(row) for row in result["sell"]], result["remaining"]["sell"],
               ["Output", "Batch", "Lowest competing unit (g)", "Listings", "Units", "Undercut unit (g)",
                "Profit at undercut for batch (g)", "Thin"], "sell")
    with vendor_tab:
        st.caption("Independent aside, not part of the craft budget.")
        _table([{"Item": names.get(r["item_id"], f"Item {r['item_id']}"),
                 "Item ID": r["item_id"], "Listings": r["listings"], "Units": r["purchased_units"],
                 "Cost (g)": to_gold(r["cost_copper"]), "Vendor pays per unit (g)": to_gold(r["vendor_sell_copper"]),
                 "Highest listing unit (g)": to_gold(r["highest_unit_copper"]), "Gain (g)": to_gold(r["gain_copper"]),
                 **_evidence(r)} for r in result["below_vendor"]], result["remaining"]["below_vendor"],
               ["Item", "Units", "Cost (g)", "Vendor pays per unit (g)", "Gain (g)"], "vendor")


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


def _selection_key(result):
    # Stable across clock ticks/evidence toggles; any plan content or provenance change resets selection.
    plan = {key: value for key, value in result.items() if key != "freshness"}
    digest = hashlib.sha256(json.dumps(plan, sort_keys=True, default=str).encode()).hexdigest()
    key = f"today-craft-{digest}"
    previous = st.session_state.get("today-craft-selection-key")
    if previous and previous != key:
        st.session_state.pop(previous, None)
    st.session_state["today-craft-selection-key"] = key
    return key


def _craft_details(row):
    details = craft_details(row)
    st.markdown(f"**Materials for {row['output_name']} · {row['batch_size']} crafts**")
    materials = [{"Material": r["item_name"], "Item ID": r["item_id"],
                  "Route": "vendor" if r["method"] == "vendor" else "auction house",
                  "Required units": r["quantity"], "Purchased units": r["purchased_units"],
                  "Cost (g)": to_gold(r["cost_copper"]),
                  "Highest unit price (g)": to_gold(r["highest_unit_copper"]), **_evidence(r)}
                 for r in details["materials"]]
    st.dataframe(materials, hide_index=True, width="stretch",
                 column_config=gold_columns("Cost (g)", "Highest unit price (g)"))
    st.caption(f"Batch material cost: {format_money(row['batch_cost_copper'])}. "
               "All materials shown; whole-stack surplus has no revenue credit. Vendor stock is unknown.")
    if details["intermediate_steps"]:
        st.caption("Chosen catalog craft steps (indented by depth; costs are included in the materials above).")
        lines = [f"{row['output_name']}: {row['batch_size']} crafts"]
        for step in details["intermediate_steps"]:
            state = _evidence(step)["State"]
            lines.append(f"{'    ' * step['depth']}↳ {step['item_name']}: {step['crafts']} crafts → "
                         f"{step['quantity']} units · {state}")
        st.text("\n".join(lines))
