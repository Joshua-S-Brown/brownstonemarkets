"""Crafting: the Action Board, then one recipe's summary and the evidence behind it."""
from datetime import UTC, datetime

import streamlit as st

from brownstone.action_board import compatible, rank_recipes
from brownstone.crafting import PRICE_BASES, basis_prices, evaluate_recipe, material_plan
from brownstone.money import format_money, to_gold
from brownstone.storage import price_observations
from views.common import gold_columns, load_latest, read_db, show_freshness

BASIS_LABELS = {"cautious": "Cautious (recommended)", "listed": "Cheapest listing"}


def render(config, catalogs):
    st.subheader("Crafting")
    default = next((i for i, c in enumerate(catalogs) if compatible(c, config)), 0)
    index = st.selectbox("Recipe catalog", range(len(catalogs)), index=default, format_func=lambda i: (
        f"{catalogs[i]['game_version'].title()} {catalogs[i]['profession'].title()} — {catalogs[i]['ruleset']}"))
    catalog = catalogs[index]
    st.caption(f"Catalog {catalog.get('catalog_version', 'unversioned')} · status {catalog['status']} · "
               f"{len(catalog['recipes_by_id'])} recipes · {catalog.get('notes', '')}")

    if not compatible(catalog, config):
        st.info(f"Inspection only: this catalog is {catalog['game_version']} / {catalog['ruleset']}, but the "
                f"selected market is {config['game_version']} / {config.get('ruleset', 'no ruleset')}. "
                "Prices are never joined across game versions or rulesets.")
        recipe_id = _pick_recipe(catalog, sorted(catalog["recipes_by_id"],
                                                 key=lambda r: catalog["recipes_by_id"][r]["name"]))
        _recipe_heading(catalog, recipe_id)
        _materials(catalog, recipe_id)
        return

    manifest, sid, _ = load_latest(config, "Refresh this market to price the catalog.")
    if manifest is None:
        return
    left, right = st.columns(2)
    sort_by = left.selectbox("Rank by", ["profit", "margin"])
    basis = right.selectbox("Prices", list(PRICE_BASES), format_func=BASIS_LABELS.get,
                            help="\n\n".join(f"**{BASIS_LABELS[k]}:** {v}." for k, v in PRICE_BASES.items()))
    try:
        with read_db(config) as db:
            observations = price_observations(db, config, sid, sorted(catalog["items_by_id"]))
        board = rank_recipes(catalog, observations, config, manifest, now=datetime.now(UTC),
                             sort_by=sort_by, basis=basis, max_age_hours=config["max_age_hours"],
                             auction_cut=config["auction_cut"])
    except Exception as error:
        st.error(f"Unable to build the Action Board: {error}")
        return
    _board(catalog, config, manifest, sid, board, basis)

    recipe_id = _pick_recipe(catalog, [row["recipe_id"] for row in board["rows"]])
    _recipe_heading(catalog, recipe_id)
    buy, sell = basis_prices(observations, basis)
    try:
        evaluation = evaluate_recipe(catalog, recipe_id, buy, config["auction_cut"], sell)
    except ValueError as error:
        st.error(f"This recipe cannot be evaluated: {error}")
        return
    _summary(catalog, evaluation, basis)
    with st.expander("Inputs and buy / craft / vendor choices", expanded=True):
        _choices(catalog, evaluation["choices"], observations, "Input")
    with st.expander("Shopping list for the chosen routes"):
        st.caption("Bought intermediates stay on this list. All-craft materials are listed separately.")
        _choices(catalog, evaluation["shopping_choices"], observations, "Item")
    _materials(catalog, recipe_id)
    with st.expander("Assumptions and provenance"):
        st.markdown(
            f"- **Prices:** {PRICE_BASES[basis]}. Zero or missing prices are unavailable, never free.\n"
            f"- **Routes:** cheapest valid buy, craft or vendor route per input. Vendor prices are undiscounted "
            f"catalog values; vendor stock and reputation discounts are not modeled.\n"
            f"- **Revenue:** {config['auction_cut']:.0%} auction cut; revenue rounds down to the copper and "
            f"break-even rounds up. Deposits, listing depth and sale speed are not modeled.\n"
            f"- **Quantities:** one recipe execution.\n"
            f"- **Recipe source:** [{catalog['recipes_by_id'][recipe_id]['name']}]"
            f"({catalog['recipes_by_id'][recipe_id]['source_url']})")


def _board(catalog, config, manifest, sid, board, basis):
    st.markdown(f"#### {catalog['profession'].title()} Action Board")
    st.caption("Representative subset, not the complete profession. Potential craft means positive estimated "
               "profit; demand and sale likelihood are unknown.")
    show_freshness(config, manifest)
    other = next(name for name in PRICE_BASES if name != basis)
    rows = [{
        "Rank": row["rank"], "Item": row["output_name"], "Action": row["action"],
        "Craft cost (g)": to_gold(row["craft_cost_copper"]),
        "Sale price (g)": to_gold(row["sale_price_copper"]),
        "Net revenue (g)": to_gold(row["net_revenue_copper"]),
        "Profit (g)": to_gold(row["profit_copper"]),
        "Margin (%)": row["margin"] * 100 if row["margin"] is not None else None,
        f"Profit at {BASIS_LABELS[other].split(' (')[0].lower()} prices (g)": to_gold(row["profit_by_basis"][other]),
    } for row in board["rows"]]
    gold = [name for name in rows[0] if name.endswith("(g)")] if rows else []
    st.dataframe(rows, hide_index=True, width="stretch", column_config={
        **gold_columns(*gold), "Margin (%)": st.column_config.NumberColumn(format="%.1f")})
    for row in board["rows"]:
        if "error" in row:
            st.warning(f"{row['output_name']} could not be evaluated: {row['error']}")
    st.caption(f"Margin = profit / net revenue. Zero profit is labeled negative margin. Missing prices take "
               f"precedence over stale data; incomplete rows sort last. Policy {board['policy_version']} · "
               f"snapshot {sid} · source {manifest['source']} · SHA-256 {manifest['sha256'][:12]}…")


def _pick_recipe(catalog, recipe_ids):
    return st.selectbox("Recipe", recipe_ids, format_func=lambda r: catalog["recipes_by_id"][r]["name"])


def _recipe_heading(catalog, recipe_id):
    recipe = catalog["recipes_by_id"][recipe_id]
    output = catalog["items_by_id"][recipe["output_item_id"]]
    st.markdown(f"### {recipe['name']}")
    st.caption(f"Recipe {recipe_id} · skill {recipe['required_skill']} · makes {recipe['output_quantity']} × "
               f"{output['name']} (item {output['item_id']})")


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


def _choices(catalog, choices, observations, label):
    rows = []
    for choice in choices:
        item = catalog["items_by_id"][choice["item_id"]]
        observed = observations.get(choice["item_id"], {})
        rows.append({
            label: item["name"], "Quantity": choice["quantity"], "Choice": choice["method"],
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
