"""Crafting: the Action Board, then one recipe's summary and the evidence behind it."""
from datetime import UTC, datetime

import streamlit as st

from brownstone.action_board import (
    catalog_for_row,
    catalog_identity,
    compatible,
    compatible_catalogs,
    filter_profession,
    rank_catalogs,
)
from brownstone.crafting import PRICE_BASES, basis_prices, evaluate_recipe, material_plan
from brownstone.money import format_money, to_gold
from brownstone.storage import listing_depth, price_observations
from views.common import gold_columns, load_latest, read_db, show_context, show_freshness

BASIS_LABELS = {"cautious": "Cautious (recommended)", "listed": "Cheapest listing"}


def render(config, catalogs):
    st.subheader("Crafting")
    show_context(config)
    selected = compatible_catalogs(catalogs, config)
    _incompatible_catalogs(config, catalogs)
    if not selected:
        st.info(f"No compatible recipe catalog for {config['game_version']} / "
                f"{config.get('rules_version', 'no rules version')}. "
                "Add or update a profession on Recipe catalogs.")
        return
    for catalog in selected:
        st.caption(f"{catalog['profession'].title()} · catalog {catalog.get('catalog_version', 'unversioned')} · "
                   f"status {catalog['status']} · {len(catalog['recipes_by_id'])} recipes · {catalog.get('notes', '')}")

    manifest, sid, _ = load_latest(config, "Refresh or import a scan for this market to price the catalog.")
    if manifest is None:
        return
    left, right = st.columns(2)
    sort_by = left.selectbox("Rank by", ["profit", "margin"])
    basis = right.selectbox("Prices", list(PRICE_BASES), format_func=BASIS_LABELS.get,
                            help="\n\n".join(f"**{BASIS_LABELS[k]}:** {v}." for k, v in PRICE_BASES.items()))
    item_ids = sorted({item for catalog in selected for item in catalog["items_by_id"]})
    try:
        with read_db(config) as db:
            observations = price_observations(db, config, sid, item_ids)
            depth = listing_depth(db, config, sid, item_ids)
        board = rank_catalogs(selected, observations, config, manifest, now=datetime.now(UTC),
                             sort_by=sort_by, basis=basis, max_age_hours=config["max_age_hours"],
                             auction_cut=config["auction_cut"])
    except Exception as error:
        st.error(f"Unable to build the Action Board: {error}")
        return
    profession = st.selectbox("Profession", [None, *sorted({c['profession'] for c in selected})],
                              format_func=lambda p: p.title() if p else "All professions",
                              key=f"profession-{config['source_id']}")
    board = filter_profession(board, profession)
    _board(selected, config, manifest, sid, board, basis, depth)
    if not board["rows"]:
        st.info("No finished recipes in these catalogs for the selected profession.")
        return
    rows = {(row["catalog_id"], row["recipe_id"]): row for row in board["rows"]}
    selection = st.selectbox("Recipe", list(rows), format_func=lambda key: (
        f"{rows[key]['output_name']} — {rows[key]['profession'].title()} · {key[0]} · recipe {key[1]}"),
        key=f"recipe-{config['source_id']}")
    catalog = catalog_for_row(selected, rows[selection])
    recipe_id = selection[1]
    _recipe_heading(catalog, recipe_id)
    buy, sell = basis_prices(observations, basis)
    try:
        evaluation = evaluate_recipe(catalog, recipe_id, buy, config["auction_cut"], sell)
    except ValueError as error:
        st.error(f"This recipe cannot be evaluated: {error}")
        return
    _summary(catalog, evaluation, basis)
    with st.expander("Inputs and buy / craft / vendor choices", expanded=True):
        _choices(catalog, evaluation["choices"], observations, "Input", depth)
    with st.expander("Shopping list for the chosen routes"):
        st.caption("Bought intermediates stay on this list. All-craft materials are listed separately.")
        _choices(catalog, evaluation["shopping_choices"], observations, "Item", depth)
    _materials(catalog, recipe_id)
    with st.expander("Assumptions and provenance"):
        st.markdown(
            f"- **Prices:** {PRICE_BASES[basis]}. Zero or missing prices are unavailable, never free.\n"
            f"- **Routes:** cheapest valid buy, craft or vendor route per input. Vendor prices are undiscounted "
            f"catalog values; vendor stock and reputation discounts are not modeled.\n"
            f"- **Revenue:** {config['auction_cut']:.0%} auction cut; revenue rounds down to the copper and "
            f"break-even rounds up. Deposits and sale speed are not modeled.\n"
            f"- **Depth:** auction listings and units in the priced scan, including listings without a buyout. "
            f"Display only: depth does not affect costs, labels or ranking, and is not vendor stock.\n"
            f"- **Quantities:** one recipe execution.\n"
            f"- **Recipe source:** [{catalog['recipes_by_id'][recipe_id]['name']}]"
            f"({catalog['recipes_by_id'][recipe_id]['source_url']})")


def _board(catalogs, config, manifest, sid, board, basis, depth):
    st.markdown("#### Action Board")
    st.caption("Selected catalogs may cover only part of each profession. Potential craft means positive estimated "
               "profit; demand and sale likelihood are unknown. Post-launch recipes can't be crafted yet.")
    show_freshness(config, manifest)
    st.caption("Depth counts all listings and units in the same scan as prices, including listings without a "
               "buyout. Not listed means zero observed supply; unavailable means this snapshot has no listing "
               "depth. Direct inputs are shown even when the chosen route crafts them or buys from a vendor. "
               "Depth does not change costs, labels or ranking.")
    other = next(name for name in PRICE_BASES if name != basis)
    rows = [_board_row(catalog_for_row(catalogs, row), row, other, depth) for row in board["rows"]]
    gold = [name for name in rows[0] if name.endswith("(g)")] if rows else []
    st.dataframe(rows, hide_index=True, width="stretch", column_config={
        **gold_columns(*gold), "Margin (%)": st.column_config.NumberColumn(format="%.1f")})
    for row in board["rows"]:
        if "error" in row:
            st.warning(f"{row['output_name']} ({row['profession'].title()} · {row['catalog_id']}) "
                       f"could not be evaluated: {row['error']}")
    st.caption(f"Margin = profit / net revenue. Zero profit is labeled negative margin. Missing prices take "
               f"precedence over stale data; incomplete rows sort last. Policy {board['policy_version']} · "
               f"snapshot {sid} · source {manifest['source']} · SHA-256 {manifest['sha256'][:12]}…")


def _board_row(catalog, row, other, depth):
    return {
        "Rank": row["rank"], "Item": _labeled(catalog["recipes_by_id"][row["recipe_id"]], row["output_name"]),
        "Profession": row["profession"].title(), "Action": row["action"],
        **_depth_columns(depth, row["output_item_id"], "Output "),
        "Direct input depth": "; ".join(
            f"{catalog['items_by_id'][ingredient['item_id']]['name']}: {_depth_text(depth, ingredient['item_id'])}"
            for ingredient in catalog["recipes_by_id"][row["recipe_id"]]["inputs"]),
        "Craft cost (g)": to_gold(row["craft_cost_copper"]),
        "Sale price (g)": to_gold(row["sale_price_copper"]),
        "Net revenue (g)": to_gold(row["net_revenue_copper"]),
        "Profit (g)": to_gold(row["profit_copper"]),
        "Margin (%)": row["margin"] * 100 if row["margin"] is not None else None,
        f"Profit at {BASIS_LABELS[other].split(' (')[0].lower()} prices (g)": to_gold(row["profit_by_basis"][other]),
    }


def _labeled(record, name):
    return f"{name} (post-launch)" if record.get("availability") == "post-launch" else name


def _incompatible_catalogs(config, catalogs):
    st.button("Open Recipe catalogs", on_click=_open_catalogs, args=(config["source_id"],))
    for catalog in catalogs:
        if catalog["game_version"] != config["game_version"] or compatible(catalog, config):
            continue
        with st.expander(f"{catalog_identity(catalog)} · {catalog['profession'].title()} · "
                         f"rules {catalog['rules_version']} · inspection only"):
            st.info(f"Rules mismatch: catalog {catalog['rules_version']}; selected source "
                    f"{config.get('rules_version', 'no rules version')}. This catalog is never priced.")
            recipe_id = st.selectbox("Inspect recipe", sorted(catalog["recipes_by_id"]),
                                     format_func=lambda r, c=catalog: c["recipes_by_id"][r]["name"],
                                     key=f"inspect-{catalog_identity(catalog)}")
            _recipe_heading(catalog, recipe_id)
            try:
                _materials(catalog, recipe_id)
            except ValueError as error:
                st.warning(f"This recipe cannot be expanded: {error}")


def _open_catalogs(source_id):
    st.session_state[f"view-{source_id}"] = "Recipe catalogs"


def _recipe_heading(catalog, recipe_id):
    recipe = catalog["recipes_by_id"][recipe_id]
    output = catalog["items_by_id"][recipe["output_item_id"]]
    st.markdown(f"### {recipe['name']}")
    st.caption(f"Recipe {recipe_id} · skill {recipe['required_skill']} · makes {recipe['output_quantity']} × "
               f"{output['name']} (item {output['item_id']})")
    notes = [recipe.get("availability_note")]
    if recipe.get("output_quantity_verified") is False:
        notes.append(f"Output count unconfirmed: {recipe.get('output_quantity_note', '')}")
    for ingredient in recipe["inputs"]:
        item = catalog["items_by_id"][ingredient["item_id"]]
        if item.get("vendor_verified") is False:
            notes.append(f"{item['name']} vendor price unconfirmed. {item.get('vendor_note', '')}")
        if item.get("availability") == "post-launch":
            notes.append(f"{item['name']}: {item.get('availability_note', 'post-launch')}")
    for note in filter(None, notes):
        st.caption(f"⚠ {note}")


def _summary(catalog, evaluation, basis):
    if not evaluation["valid"]:
        names = ", ".join(catalog["items_by_id"][i]["name"] for i in evaluation["missing_item_ids"])
        st.warning(f"No complete estimate. No usable price for: {names}.")
    cost, sale, profit, break_even = st.columns(4)
    cost.metric("Craft cost", format_money(evaluation["craft_cost_copper"]))
    sale.metric("Sale price", format_money(evaluation["sale_price_copper"]))
    profit.metric("Estimated profit", format_money(evaluation["profit_copper"]),
                  delta=f"{evaluation['margin']:.0%} margin" if evaluation["margin"] is not None else None)
    break_even.metric("Break-even sale price", format_money(evaluation["break_even_copper"]))
    st.caption(f"{BASIS_LABELS[basis]} prices, after the auction cut, for one recipe execution.")


def _depth_columns(depth, item_id, prefix=""):
    counts = depth.get(item_id) if depth is not None else None
    return {
        f"{prefix}listings": counts["listings"] if counts is not None else None,
        f"{prefix}units": counts["units"] if counts is not None else None,
        f"{prefix}depth": "Unavailable" if counts is None else "Not listed" if not counts["listings"] else "Listed",
    }


def _depth_text(depth, item_id):
    counts = depth.get(item_id) if depth is not None else None
    if counts is None:
        return "Unavailable"
    if not counts["listings"]:
        return "Not listed"
    return f"{counts['listings']:,} listings / {counts['units']:,} units"


def _choices(catalog, choices, observations, label, depth):
    rows = []
    for choice in choices:
        item = catalog["items_by_id"][choice["item_id"]]
        observed = observations.get(choice["item_id"], {})
        rows.append({
            label: item["name"], "Quantity": choice["quantity"], "Choice": choice["method"],
            **_depth_columns(depth, choice["item_id"], "Market "),
            "Unit cost (g)": to_gold(choice["unit_cost_copper"]),
            "Total cost (g)": to_gold(choice["total_cost_copper"]),
            "Min buyout (g)": to_gold(observed.get("min_buyout") or None),
            "Market value (g)": to_gold(observed.get("market_value") or None),
            "Vendor (g)": to_gold(item.get("vendor_price_copper")),
            "Source": item["source_url"],
        })
    st.dataframe(rows, hide_index=True, width="stretch", column_config={
        **gold_columns("Unit cost (g)", "Total cost (g)", "Min buyout (g)", "Market value (g)", "Vendor (g)"),
        "Source": st.column_config.LinkColumn("Source", display_text="link")})


def _materials(catalog, recipe_id):
    with st.expander("All-craft materials (every intermediate crafted)"):
        rows = [{"Material": catalog["items_by_id"][i]["name"], "Item ID": i, "Quantity": q,
                 "Acquisition": "vendor" if catalog["items_by_id"][i].get("vendor_price_copper") else "market"}
                for i, q in material_plan(catalog, recipe_id).items()]
        st.dataframe(rows, hide_index=True, width="stretch")
