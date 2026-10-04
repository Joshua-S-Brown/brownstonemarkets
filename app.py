"""Local market review; ingestion only runs when the user clicks Refresh."""
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import polars as pl
import streamlit as st

from brownstone.pipeline import run
from brownstone.config import read_config
from brownstone.analysis import rank, browse
from brownstone.crafting import evaluate_recipe, load_recipe_catalog, material_plan
from brownstone.storage import completed_snapshots, recipe_prices
from brownstone.action_board import MARKET, rank_recipes

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="Brownstone Markets", page_icon="📊", layout="wide")
st.title("Brownstone Markets")
st.caption("Your local WoW market research desk")

try:
    all_config = read_config(ROOT / "config/market.toml")
except Exception as error:
    st.error(f"Could not read market configuration: {error}")
    st.stop()

with st.sidebar:
    st.header("Market")
    sources = all_config.get("sources", [all_config])
    selected = st.selectbox("Data source", range(len(sources)), format_func=lambda index: sources[index].get("label", sources[index]["market_id"]))
    config = sources[selected]
    st.caption("Regional commodity prices" if config.get("scope") == "region" else "Realm-specific item prices")
    st.caption("Change your market in config/market.toml.")
    refresh = st.button("Refresh from TSM", type="primary", width="stretch")
    view = st.radio("View", ["Opportunities", "Browse market", "Crafting"],
                    index=2 if config["market_id"] == MARKET["market_id"] else 0)
    if view != "Crafting":
        st.divider()
        st.header("Screening filters")
        discount = st.slider("Minimum discount (%)", 0, 90, int(config["min_discount"] * 100), 5)
        limit = st.selectbox("Show up to", [20, 50, 100], index=0)
        search = st.text_input("Find an item", placeholder="Name or item ID")
        st.caption("Filters update the table without downloading data.")

if refresh:
    with st.spinner("Downloading and preserving the latest market snapshot…"):
        try:
            run(config)
            st.success("Market data refreshed and saved.")
        except Exception as error:
            st.error(f"Refresh failed: {error}. Your previous successful snapshot remains available.")

if view == "Crafting":
    st.subheader("Crafting")
    try:
        catalogs = [load_recipe_catalog(path) for path in sorted((ROOT / "config").glob("*-tailoring.toml"))]
    except Exception as error:
        st.error(f"Could not read the recipe catalog: {error}")
        st.stop()

    matching_catalog = next(
        (index for index, candidate in enumerate(catalogs)
         if candidate["game_version"] == config["game_version"]),
        0,
    )
    selected_catalog = st.selectbox(
        "Recipe catalog",
        range(len(catalogs)),
        index=matching_catalog,
        format_func=lambda index: (
            f"{catalogs[index]['game_version'].title()} "
            f"{catalogs[index]['profession'].title()} — {catalogs[index]['ruleset']}"
        ),
    )
    catalog = catalogs[selected_catalog]

    catalog_name = f"{catalog['game_version'].title()} {catalog['profession'].title()}"
    left, middle, right = st.columns(3)
    left.metric("Catalog", catalog_name)
    middle.metric("Recipes", len(catalog["recipes_by_id"]))
    right.metric("Catalog status", catalog["status"])
    st.caption(f"Ruleset: {catalog['ruleset']} · {catalog.get('notes', '')}")

    board = None
    board_market = all(config.get(key) == value for key, value in MARKET.items())
    if board_market and catalog["game_version"] == "classic" and catalog["ruleset"] == "classic-era":
        st.subheader("Classic Tailoring Action Board v0.1")
        st.caption("Representative bag subset, not the complete profession. Potential craft means positive estimated profit; demand and sale likelihood are unknown.")
        sort_by = st.selectbox("Rank by", ["profit", "margin"])
        manifests = completed_snapshots(config)
        if not manifests:
            st.info("Refresh Mankrik Alliance to rank this subset with saved prices.")
        else:
            latest = max(manifests, key=lambda record: record["collected_at"])
            sid = latest.get("analytical_snapshot_id", latest["snapshot_id"])
            try:
                with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb"), read_only=True) as db:
                    prices = recipe_prices(db, config, sid, sorted(catalog["items_by_id"]))
                board = rank_recipes(catalog, prices, config, latest, now=datetime.now(timezone.utc),
                                     sort_by=sort_by, max_age_hours=config["max_age_hours"],
                                     auction_cut=config["auction_cut"])
            except Exception as error:
                st.error(f"Unable to read the Action Board: {error}")
                st.stop()
            st.caption(f"{board['freshness_basis'].title()} age: {board['age_hours']:.1f} hours · stale threshold: {config['max_age_hours']} hours · Policy {board['policy_version']}")
            if board["stale"]:
                st.warning("Saved prices are stale or future-dated. Refresh before acting on these estimates.")
            if not latest.get("updated_at"):
                st.caption("Upstream scan time is unknown. Collection freshness does not establish when upstream prices were observed.")
            st.caption(f"Source: {latest['source']} · Collected: {latest['collected_at']} · Upstream: {latest.get('updated_at') or 'unknown'}")
            st.caption(f"Analytical snapshot: {sid} · SHA-256: {latest['sha256']}")
            board_rows = []
            for row in board["rows"]:
                board_rows.append({"Rank": row["rank"], "Bag": row["output_name"], "Action": row["action"],
                    **{label: row[key] / 10000 if row[key] is not None else None for label, key in [
                        ("Craft cost (g)", "craft_cost_copper"), ("Output minimum buyout (g)", "sale_price_copper"),
                        ("Net revenue (g)", "net_revenue_copper"), ("Estimated profit (g)", "profit_copper")]},
                    "Margin (%)": row["margin"] * 100 if row["margin"] is not None else None})
            st.dataframe(board_rows, hide_index=True, width="stretch")
            st.caption("Margin = profit / net revenue. Zero profit is non-actionable and uses the negative margin label. Missing prices take precedence over stale data; incomplete estimates sort last.")

    recipes = sorted(catalog["recipes_by_id"].values(), key=lambda recipe: recipe["name"])
    if board is not None:
        recipes = [catalog["recipes_by_id"][row["recipe_id"]] for row in board["rows"]]
    recipe_id = st.selectbox(
        "Recipe",
        [recipe["recipe_id"] for recipe in recipes],
        format_func=lambda selected_id: catalog["recipes_by_id"][selected_id]["name"],
    )
    recipe = catalog["recipes_by_id"][recipe_id]
    output = catalog["items_by_id"][recipe["output_item_id"]]
    st.markdown(f"### {recipe['name']}")
    st.caption(
        f"Recipe {recipe_id} · Skill {recipe['required_skill']} · "
        f"Produces {recipe['output_quantity']} × {output['name']} (item {output['item_id']})"
    )

    direct_rows = []
    for ingredient in recipe["inputs"]:
        item = catalog["items_by_id"][ingredient["item_id"]]
        direct_rows.append({
            "Ingredient": item["name"], "Item ID": item["item_id"],
            "Quantity": ingredient["quantity"], "Role": item["role"],
            "Source": item["source_url"],
        })
    st.markdown("#### Direct recipe")
    st.dataframe(
        direct_rows,
        hide_index=True,
        width="stretch",
        column_config={"Source": st.column_config.LinkColumn("Source")},
    )

    base_rows = []
    for item_id, quantity in material_plan(catalog, recipe_id).items():
        item = catalog["items_by_id"][item_id]
        base_rows.append({
            "Base material": item["name"], "Item ID": item_id,
            "Quantity": quantity, "Acquisition": "vendor" if item.get("vendor_price_copper") else "market",
        })
    st.markdown("#### Fully expanded shopping list (all-craft recipe)")
    st.dataframe(base_rows, hide_index=True, width="stretch")

    if config["game_version"] != catalog["game_version"]:
        st.info(
            f"Profit is not calculated because the selected market is {config['game_version']} "
            f"and this catalog is {catalog['game_version']}. Choose a compatible market to join prices safely."
        )
    else:
        manifests = completed_snapshots(config)
        if not manifests:
            st.info("Refresh this market before calculating recipe cost and profit.")
        else:
            latest = max(manifests, key=lambda record: record["collected_at"])
            sid = latest.get("analytical_snapshot_id", latest["snapshot_id"])
            try:
                with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb"), read_only=True) as db:
                    prices = recipe_prices(db, config, sid, sorted(catalog["items_by_id"]))
                evaluation = evaluate_recipe(catalog, recipe_id, prices, config["auction_cut"])
            except Exception as error:
                st.error(f"Unable to evaluate this recipe: {error}")
                st.stop()
            st.markdown("#### Direct input choices")
            st.dataframe([{
                "Input": choice["item_name"], "Quantity": choice["quantity"], "Choice": choice["method"],
                "Unit cost (copper)": choice["unit_cost_copper"], "Total cost (copper)": choice["total_cost_copper"],
                "Observed buyout (copper)": prices.get(choice["item_id"]) or None,
                "Source": catalog["items_by_id"][choice["item_id"]]["source_url"],
            } for choice in evaluation["choices"]], hide_index=True, width="stretch",
                column_config={"Source": st.column_config.LinkColumn("Catalog source")})
            st.markdown("#### Shopping list for selected routes")
            st.caption("Purchased intermediates remain on this list; the fully expanded materials above show the all-craft recipe quantities.")
            st.dataframe([{
                "Item": catalog["items_by_id"][choice["item_id"]]["name"],
                "Quantity": choice["quantity"], "Choice": choice["method"],
                "Unit cost (copper)": choice["unit_cost_copper"],
                "Total cost (copper)": choice["total_cost_copper"],
                "Observed buyout (copper)": prices.get(choice["item_id"]) or None,
                "Vendor unit price (copper)": catalog["items_by_id"][choice["item_id"]].get("vendor_price_copper"),
                "Source": catalog["items_by_id"][choice["item_id"]]["source_url"],
            } for choice in evaluation["shopping_choices"]], hide_index=True, width="stretch",
                column_config={"Source": st.column_config.LinkColumn("Catalog source")})
            if evaluation["break_even_copper"] is not None:
                st.metric("Break-even output unit price", f"{evaluation['break_even_copper'] / 10000:,.4f} g")
            st.caption(f"Prices are unit minimum buyouts; zero and missing prices are unavailable. Cheapest valid buy/craft/vendor route wins; vendor prices are undiscounted catalog assumptions. Auction cut: {config['auction_cut']:.0%}. Net revenue rounds down to copper; break-even rounds up. All quantities are for one recipe execution.")
            if not evaluation["valid"]:
                missing = ", ".join(str(item_id) for item_id in evaluation["missing_item_ids"])
                st.warning(f"No complete estimate: required market prices are missing for item IDs {missing}.")
            else:
                cost, sale, profit = st.columns(3)
                cost.metric("Craft cost", f"{evaluation['craft_cost_copper'] / 10000:,.2f} g")
                sale.metric("Minimum buyout", f"{evaluation['sale_price_copper'] / 10000:,.2f} g")
                profit.metric("Estimated profit", f"{evaluation['profit_copper'] / 10000:,.2f} g")
                st.caption(
                    f"Uses minimum buyouts and a {config['auction_cut']:.0%} auction cut. "
                    "Deposit cost, listing quantity and sale speed are not modeled."
                )

    st.markdown(f"[Recipe provenance]({recipe['source_url']})")
    st.stop()

manifests = completed_snapshots(config)
if not manifests:
    st.info("No completed snapshot yet. Click Refresh from TSM to collect your first market.")
    st.stop()

latest = max(manifests, key=lambda record: record["collected_at"])
upstream = datetime.fromisoformat(latest["updated_at"]) if latest.get("updated_at") else None
freshness_time = upstream or datetime.fromisoformat(latest["collected_at"])
age = (datetime.now(timezone.utc) - freshness_time).total_seconds() / 3600
left, middle, right = st.columns(3)
left.metric("Items observed", f"{latest['rows']:,}")
middle.metric("Scan age" if upstream else "Collection age", f"{age:.1f} hours")
right.metric("Saved snapshots", len(manifests))
if upstream:
    st.caption(f"Upstream scan: {upstream.strftime('%Y-%m-%d %H:%M UTC')} · Latest collection: {latest['collected_at']}")
else:
    st.caption(f"Latest collection: {latest['collected_at']} · This source did not provide an upstream scan timestamp.")
if age > config["max_age_hours"]:
    st.warning("This saved snapshot is stale based on its available freshness time. Refresh before evaluating current prices.")

settings = {**config, "min_discount": discount / 100, "top_n": limit}
try:
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb"), read_only=True) as db:
        # Search before LIMIT so lower-ranked matches remain discoverable.
        settings["top_n"] = latest["rows"] if search else limit
        sid = latest.get("analytical_snapshot_id", latest["snapshot_id"])
        results = (browse(db, sid, search, limit) if view == "Browse market" else rank(db, sid, settings))
    if search and view == "Opportunities":
        results = results.filter(
            pl.col("item_name").str.to_lowercase().str.contains(search.lower(), literal=True)
            | pl.col("item_id").cast(pl.String).str.contains(search, literal=True)
        ).head(limit)
except Exception as error:
    st.error(f"Unable to read saved opportunities: {error}")
    st.stop()

if view == "Browse market":
    st.subheader("Browse market")
    st.caption("All observed items, independent of discount. Commodities include both materials and finished goods; categories are not assigned yet.")
    display = results.select(
        pl.col("item_name").alias("Item"), pl.col("item_id").alias("Item ID"),
        (pl.col("min_buyout") / 10000).alias("Minimum buyout (g)"),
        (pl.col("market_value") / 10000).alias("Market value (g)"),
        (pl.col("recent_value") / 10000).alias("Recent (g)"),
        (pl.col("historical_value") / 10000).alias("Historical (g)"),
    )
    st.caption("Zero means unavailable/no listing, not a free purchase.")
    if display.is_empty():
        st.info("No items match this search.")
    else:
        st.dataframe(display, hide_index=True, width="stretch", height=600)
        st.download_button("Download this table", display.write_csv(), "brownstone-market.csv", "text/csv")
    st.stop()

st.subheader("Price opportunities")
st.caption("Ranked by discount against the lowest of market, recent and historical values. Prices are in gold.")
display = results.select(
    pl.col("rank").alias("Rank"), pl.col("item_name").alias("Item"),
    pl.col("item_id").alias("Item ID"), pl.col("buy_gold").alias("Minimum buyout (g)"),
    (pl.col("reference_copper") / 10000).alias("Reference (g)"),
    (pl.col("discount") * 100).alias("Discount (%)"),
    pl.col("net_spread_gold").alias("Estimated spread (g)"),
)
if results.is_empty():
    st.info("No items match these filters. Try reducing the minimum discount or clearing the search.")
else:
    st.dataframe(display, hide_index=True, width="stretch", height=600,
                 column_config={name: st.column_config.NumberColumn(format="%.2f")
                                for name in ["Minimum buyout (g)", "Reference (g)", "Discount (%)", "Estimated spread (g)"]})
    st.download_button("Download this table", display.write_csv(), "brownstone-opportunities.csv", "text/csv")
st.caption(f"Spread assumes a {config['auction_cut']:.0%} auction cut. Sale speed, deposits and listing quantity are not modeled; this is a research shortlist.")
