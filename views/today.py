"""Today settings and evidence tables; calculations live in brownstone.today."""
import hashlib
import json
from datetime import UTC, datetime

import streamlit as st

from brownstone import professions
from brownstone.money import format_money, parse_money, to_gold
from brownstone.today import build_today, craft_details
from brownstone.today_characters import available_characters, resolve_character
from brownstone.today_data import read_today_evidence
from brownstone.today_settings import TodaySettings, load_settings, save_settings, settings_path
from views.common import gold_columns, load_latest, read_db, show_context, show_freshness


def _settings(config, character_data):
    path = settings_path(config["data_dir"], config["source_id"])
    unreadable = False
    try:
        saved = load_settings(path)
    except (ValueError, TypeError, OSError) as error:
        st.warning(f"Could not read Today settings: {error}. Defaults are shown; save to replace this file.")
        saved = TodaySettings()
        unreadable = True
    selected = resolve_character(saved.character, character_data)
    if saved.character is not None and selected is None:
        st.caption("Saved character is no longer present in this source and market; showing All recipes.")
    summary = st.empty()
    with st.expander("Today settings", expanded=unreadable or saved.gold_copper == 0):
        st.caption("One funded plan · whole auction stacks are bought; surplus is shown · sales speed is unknown")
        return _settings_form(config, path, saved, summary, character_data, selected)


def _settings_form(config, path, saved, summary, character_data, selected):
    with st.form(f"today-settings-{config['source_id']}"):
        options = [None, *available_characters(character_data)]
        character = st.selectbox("Character", options, index=options.index(selected),
                                 format_func=lambda c: "All recipes" if c is None else " · ".join(c))
        gold = st.text_input("Gold available", value=format_money(saved.gold_copper))
        mode = st.selectbox("Minimum gain mode", ["scaled", "fixed"], index=["scaled", "fixed"].index(saved.mode))
        minimum = st.text_input("Fixed minimum gain", value=format_money(saved.minimum_copper))
        percent = st.number_input("Percentage of gold available", min_value=0.0, max_value=100.0,
                                  value=saved.percent_basis_points / 100, step=.1)
        crafts = st.number_input("Most crafts per item", min_value=1, max_value=1000, value=saved.max_crafts)
        submitted = st.form_submit_button("Save Today settings")
    if submitted:
        try:
            entered = TodaySettings(parse_money(gold), parse_money(minimum), mode, round(percent * 100),
                                    int(crafts), character)
            save_settings(path, entered)
        except (ValueError, OSError) as error:
            st.error(f"Settings not saved: {str(error).rstrip('.')}. "
                     "The tables below still use the last saved settings.")
        else:
            saved = entered
            st.success("Today settings saved locally.")
    character_summary = ""
    if saved.character is not None and resolve_character(saved.character, character_data) is not None:
        character_summary = " · Character: " + " · ".join(saved.character)
    summary.caption(f"Gold available: {format_money(saved.gold_copper)} · "
                    f"Minimum batch gain: {format_money(saved.minimum_gain)} · "
                    f"Most crafts per item: {saved.max_crafts}{character_summary}")
    if not saved.gold_copper:
        st.info("Enter the gold you have available to size the plan. Use explicit units, for example 12g 50s.")
    return saved


def render(config, catalogs):
    st.subheader("Today")
    show_context(config)
    try:
        character_data = professions.latest_data(config)
    except Exception as error:
        st.warning(f"Unable to read character evidence: {error}. Showing All recipes.")
        character_data = {}
    settings = _settings(config, character_data)
    manifest, sid, _ = load_latest(config, "Refresh or import a scan for this market to inspect Today.")
    if manifest is None:
        return
    show_freshness(config, manifest)
    try:
        ids = sorted({item for c in catalogs for item in c["items_by_id"]})
        with read_db(config) as db:
            observations, listings, metrics, vendors = read_today_evidence(db, config, sid, ids)
        arguments = dict(catalogs=catalogs, observations=observations, market=config,
                         snapshot={**manifest, "snapshot_id": sid}, settings=settings, now=datetime.now(UTC),
                         listings=listings, metrics=metrics, vendor_prices=vendors,
                         max_age_hours=config["max_age_hours"], auction_cut=config["auction_cut"],
                         character_data=character_data)
        result = _build_session_plan(arguments)
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
    _tables(result, names, arguments=arguments)


def _evidence(row):
    return {"State": "stale — inspect only" if row["stale"] else "potential gain"}


def _table(rows, rest, decisions, key, *, selection_key=None, rest_text="more rows outside this list's 10-row limit"):
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
    st.caption(f"{rest} {rest_text}.")
    return selected if rows else []


def _tables(result, names, *, arguments=None):
    craft_tab, buy_tab, sell_tab, vendor_tab, queue_tab = st.tabs(["Craft", "Buy", "Sell", "Below vendor", "Queue"])
    with craft_tab:
        if arguments is not None:
            result = _plan_controls(result, arguments)
        sells = {r["output_item_id"]: r for r in result["sell"]}
        hide_low = st.toggle("Hide Low confidence", key=f"today-hide-low-{result['source_id']}")
        visible, hidden_counts = _filter_confidence(result, hide_low)
        decision_character = ["Can make", "Learning"] if result["character"] else ["Who can make it"]
        craft = [_craft_row(row, sells[row["output_item_id"]]) for row in visible]
        selected = _table(craft, result["remaining"]["craft"],
               ["Item", "Profession", *decision_character, "Batch", "Limited by", "Material cost (g)",
                "Batch profit (g)", "Profit per craft (g)", "Thin", "Confidence", "Reasons"], "craft",
               selection_key=_selection_key({**result, "craft": visible}),
               rest_text=("more rows outside this list's 10-row limit" if result["refill"]
                          else "more crafts fit the remaining gold; refill is off"))
        if selected:
            _craft_details(visible[selected[0]])
        elif craft:
            st.caption("Select a craft row to see its materials and catalog craft steps.")
        hidden = "; ".join(f"{reason}: {count}" for reason, count in sorted(hidden_counts.items()))
        st.caption("Hidden recipes: " + (hidden or "0"))
        with st.expander("Catalog checks", expanded=False):
            if result["catalog_checks"]:
                st.dataframe(result["catalog_checks"], hide_index=True, width="stretch")
            else:
                st.caption("No differences in comparable matched recipe evidence.")
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
                "Profit at undercut for batch (g)", "Thin", "Confidence", "Reasons"], "sell")
    with vendor_tab:
        st.caption("Independent aside, not part of the craft budget.")
        _table([{"Item": names.get(r["item_id"], f"Item {r['item_id']}"),
                 "Item ID": r["item_id"], "Listings": r["listings"], "Units": r["purchased_units"],
                 "Cost (g)": to_gold(r["cost_copper"]), "Vendor pays per unit (g)": to_gold(r["vendor_sell_copper"]),
                 "Highest listing unit (g)": to_gold(r["highest_unit_copper"]), "Gain (g)": to_gold(r["gain_copper"]),
                 **_evidence(r)} for r in result["below_vendor"]], result["remaining"]["below_vendor"],
               ["Item", "Units", "Cost (g)", "Vendor pays per unit (g)", "Gain (g)"], "vendor")

    with queue_tab:
        _queue(result)


def _craft_row(row, sell):
    return {"Item": row["output_name"], "Profession": row["profession"].title(), "Catalog": row["catalog_id"],
            "Recipe": row["recipe_id"], "Batch": row["batch_size"], "Limited by": row["limiting_factor"],
            "Material cost (g)": to_gold(row["batch_cost_copper"]),
            "Batch profit (g)": to_gold(row["batch_profit_copper"]),
            "Profit per craft (g)": to_gold(row["profit_per_craft_copper"]),
            "Cautious output unit (g)": to_gold(row["sale_price_copper"]), "Listings": sell["listings"],
            "Units": sell["units"], "Thin": sell["thin"], "Availability": row["availability"],
            "Evidence notes": "; ".join(row["evidence_notes"]), "Recipe source": row["recipe_source"],
            **_character_columns(row), **_confidence_columns(row), **_evidence(row)}


def _character_columns(row):
    if "craft_status" not in row:
        return {"Who can make it": ", ".join(row.get("who_can_make_it", [])) or "unknown"}
    learning = row["character_reason"]
    if row["craft_status"] == "Train now":
        cost = row["training_cost_copper"]
        learning = "Training: " + (format_money(cost) if cost is not None else "cost unknown")
    return {"Can make": row["craft_status"], "Learning": learning}


def _sell_row(row):
    return {"Output": row["output_name"], "Catalog": row["catalog_id"], "Recipe": row["recipe_id"],
            "Batch": row["batch_size"], "Lowest competing unit (g)": to_gold(row["lowest_copper"]),
            "Listings": row["listings"], "Units": row["units"], "Largest stack units": row["largest_stack_units"],
            "Undercut unit (g)": to_gold(row["undercut_copper"]),
            "Profit at undercut for batch (g)": to_gold(row["undercut_batch_profit_copper"]),
            "Thin": row["thin"], **_confidence_columns(row), **_evidence(row)}


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


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _context(arguments):
    # Listings, observations and metrics are read for the snapshot ID, so the snapshot identifies them.
    context = {key: arguments[key] for key in ("catalogs", "market", "snapshot", "settings",
                                              "max_age_hours", "auction_cut")}
    context["character_data"] = sorted(arguments.get("character_data", {}).items())
    return _digest(context)


def _session_choices(state, prefix):
    choices = []
    for row in state["rows"]:
        identity = f"{prefix}-{row['catalog_id']}-{row['recipe_id']}"
        checked = st.session_state.get(f"{identity}-chosen", state["values"].get(f"{identity}-chosen", True))
        size = st.session_state.get(f"{identity}-size", state["values"].get(f"{identity}-size", row["batch_size"]))
        choices.append({"catalog_id": row["catalog_id"], "recipe_id": row["recipe_id"],
                        "batch_size": size if checked else None})
    pristine = len(choices) == state["default_count"] and all(
        c["batch_size"] == r["batch_size"]
        for c, r in zip(choices, state["rows"][:state["default_count"]], strict=True))
    return None if pristine else choices


def _build_session_plan(arguments):
    source = arguments["market"]["source_id"]
    context = _context(arguments)
    state = st.session_state.get(f"today-choices-{source}")
    if state is None or state["context"] != context:
        return build_today(**arguments)
    prefix = f"today-plan-{source}-{context}"
    refill_key = f"{prefix}-refill"
    refill = st.session_state.get(refill_key, state["values"].get(refill_key, True))
    return build_today(**arguments, choices=_session_choices(state, prefix), refill=refill)


def _plan_controls(default, arguments):
    source = arguments["market"]["source_id"]
    context = _context(arguments)
    state_key = f"today-choices-{source}"
    state = st.session_state.get(state_key)
    if state is None or state["context"] != context:
        if state is not None:
            st.info("Scan, settings or catalog evidence changed: session choices and queue ticks reset. "
                    "Previous choices were dropped, not resized; a fresh default plan is shown.")
            for key in state["widgets"]:
                st.session_state.pop(key, None)
        state = {"context": context, "rows": sorted(default["craft"], key=lambda r: r["plan_order"]),
                 "widgets": [], "values": {}, "default_count": len(default["craft"])}
        st.session_state[state_key] = state
    for key, value in state["values"].items():
        if key not in st.session_state:
            st.session_state[key] = value
    prefix = f"today-plan-{source}-{context}"
    refill_key = f"{prefix}-refill"
    result = default
    named = {(r["catalog_id"], r["recipe_id"]): r["output_name"] for r in state["rows"]}
    for dropped in result["dropped_choices"]:
        name = named.get((dropped["catalog_id"], dropped["recipe_id"]), f"Recipe {dropped['recipe_id']}")
        st.warning(f"{name}: {dropped['reason']}")
        identity = f"{prefix}-{dropped['catalog_id']}-{dropped['recipe_id']}"
        st.session_state[f"{identity}-chosen"] = False
        st.session_state[f"{identity}-size"] = 1
    _seed(refill_key, True)
    st.toggle("Refill freed gold with next-best crafts", key=refill_key)
    state["widgets"] = [refill_key]
    limits = {(r["catalog_id"], r["recipe_id"]): r["maximum"] for r in result["choice_limits"]}
    known = {(r["catalog_id"], r["recipe_id"]) for r in state["rows"]}
    state["rows"].extend(r for r in sorted(result["craft"], key=lambda r: r["plan_order"])
                         if (r["catalog_id"], r["recipe_id"]) not in known)
    _choice_widgets(state, prefix, limits)
    state["values"] = {key: st.session_state[key] for key in state["widgets"]}
    result["session_context"] = context
    return result


def _choice_widgets(state, prefix, limits):
    for row in state["rows"]:
        identity = f"{prefix}-{row['catalog_id']}-{row['recipe_id']}"
        tick_key, size_key = f"{identity}-chosen", f"{identity}-size"
        maximum = limits.get((row["catalog_id"], row["recipe_id"]), row["feasible_size"])
        if not st.session_state.get(tick_key, True) and st.session_state.get(size_key, 1) > max(1, maximum):
            st.session_state[size_key] = 1
        _seed(tick_key, True)
        _seed(size_key, min(row["batch_size"], max(1, maximum)))
        tick, batch = st.columns([3, 1])
        with tick:
            st.checkbox(row["output_name"], key=tick_key, disabled=maximum == 0)
        with batch:
            st.number_input(f"Batch for {row['output_name']}", min_value=1, max_value=max(1, maximum),
                            key=size_key, disabled=maximum == 0)
        state["widgets"].extend([tick_key, size_key])


def _seed(key, value):
    # Widgets get their start value only through session state, never also through `value=`.
    if key not in st.session_state:
        st.session_state[key] = value


def _queue_line(line):
    text = _queue_line_text(line)
    if "confidence" in line:
        reasons = ", ".join(line["confidence_reasons"])
        text += f" · {line['confidence']} confidence" + (f" ({reasons})" if reasons else "")
    return text


def _queue_line_text(line):
    stage, name = line["stage"], line["name"]
    if stage in ("auction house", "vendor"):
        return (f"Buy at {stage}: {name} · {line['purchased_units']} units · "
                f"highest unit {format_money(line['highest_unit_copper'])} · total {format_money(line['cost_copper'])}")
    if stage == "craft":
        return f"Craft: {name} · recipe {line['recipe_id']} ({line['catalog_id']}) · {line['batch_size']} crafts"
    price = format_money(line["unit_copper"]) if line["unit_copper"] is not None else "unavailable"
    profit = format_money(line["profit_copper"]) if line["profit_copper"] is not None else "unavailable"
    return f"Post: {name} · {line['quantity']} units · undercut unit {price} · profit {profit}"


def _queue(result):
    queue = result["queue"]
    stable_queue = {**queue, "lines": [{k: v for k, v in line.items()
                                      if k not in ("confidence", "confidence_reasons")} for line in queue["lines"]]}
    identity = _digest({"queue": stable_queue, "context": result.get("session_context"), "evidence": [
        {k: r[k] for k in ("source_id", "market_id", "snapshot_id", "scan_id")}
        for r in result["craft"]]})
    key = f"today-queue-{identity}"
    source = result["source_id"]
    state_key = f"today-queue-state-{source}"
    previous = st.session_state.get(state_key, {})
    if previous.get("identity") != key:
        for tick in previous.get("ticks", {}):
            st.session_state.pop(tick, None)
        previous = {"identity": key, "ticks": {}}
    lines = [_queue_line(line) for line in queue["lines"]]
    tick_keys = [f"{key}-{i}" for i in range(len(lines))]
    for text, tick in zip(lines, tick_keys, strict=True):
        if tick not in st.session_state and tick in previous["ticks"]:
            st.session_state[tick] = previous["ticks"][tick]
        st.checkbox(text, key=tick)
    st.session_state[state_key] = {"identity": key, "ticks": {tick: st.session_state[tick] for tick in tick_keys}}
    profit = queue["expected_profit_copper"]
    total = (f"Gold needed: {format_money(queue['gold_needed_copper'])} · "
             f"Expected profit at undercut: {format_money(profit) if profit is not None else 'unavailable'}")
    st.caption(total)
    if result["freshness"]["stale"]:
        st.caption("stale — inspect only")
    if st.toggle("Copy as text", key=f"today-queue-copy-{source}"):
        st.code("\n".join([*lines, total]), language=None)


def _confidence_columns(row):
    return {"Confidence": row["confidence"], "Reasons": ", ".join(row["confidence_reasons"])}


def _filter_confidence(result, hide_low):
    rows = [r for r in result["craft"] if not hide_low or r["confidence"] != "Low"]
    hidden = dict(result["hidden"])
    if hide_low and len(rows) < len(result["craft"]):
        hidden["low confidence"] = len(result["craft"]) - len(rows)
    return rows, hidden
