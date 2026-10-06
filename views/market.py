"""Browse market and the discount screen (Opportunities)."""
import polars as pl
import streamlit as st

from brownstone.analysis import browse, rank, screenable_count
from brownstone.money import COPPER_PER_GOLD
from views.common import gold_columns, load_latest, read_db, show_context, show_freshness

EMPTY = "No completed snapshot yet. Click Refresh from TSM or Import addon scan to collect this market."


def _header(config, manifest, count):
    left, right = st.columns(2)
    left.metric("Items observed", f"{manifest['rows']:,}")
    right.metric("Saved snapshots", count)
    show_freshness(config, manifest)


def render_browse(config):
    st.subheader("Browse market")
    show_context(config)
    search = st.sidebar.text_input("Find an item", placeholder="Name or item ID")
    limit = st.sidebar.selectbox("Show up to", [100, 500, 2000])
    manifest, sid, count = load_latest(config, EMPTY)
    if manifest is None:
        return
    _header(config, manifest, count)
    try:
        with read_db(config) as db:
            results = browse(db, sid, config, search, limit)
    except Exception as error:
        st.error(f"Unable to read saved prices: {error}")
        return
    st.caption("All observed items, independent of discount. Categories are not assigned yet. "
               "Blank means unavailable or no listing, not free.")
    display = results.select(
        pl.col("item_name").alias("Item"), pl.col("item_id").alias("Item ID"),
        pl.col("variant_id").alias("Variant"),
        pl.col("variant_state").fill_null("legacy").alias("Variant state"),
        *[(pl.when(pl.col(src) > 0).then(pl.col(src) / COPPER_PER_GOLD)).alias(dst) for src, dst in [
            ("min_buyout", "Minimum buyout (g)"), ("market_value", "Market value (g)"),
            ("recent_value", "Recent (g)"), ("historical_value", "Historical (g)")]],
    )
    if display.is_empty():
        st.info("No items match this search.")
        return
    gold = [c for c in display.columns if c.endswith("(g)")]
    st.dataframe(display, hide_index=True, width="stretch", height=600, column_config=gold_columns(*gold))
    st.download_button("Download this table", display.write_csv(), "brownstone-market.csv", "text/csv")


def render_opportunities(config):
    st.subheader("Price opportunities")
    show_context(config)
    st.sidebar.divider()
    discount = st.sidebar.slider("Minimum discount (%)", 0, 90, int(config["min_discount"] * 100), 5)
    limit = st.sidebar.selectbox("Show up to", [20, 50, 100])
    search = st.sidebar.text_input("Find an item", placeholder="Name or item ID")
    manifest, sid, count = load_latest(config, EMPTY)
    if manifest is None:
        return
    _header(config, manifest, count)
    settings = {**config, "min_discount": discount / 100, "top_n": limit}
    try:
        with read_db(config) as db:
            results = rank(db, sid, settings, search)
            eligible = screenable_count(db, sid, config)
    except Exception as error:
        st.error(f"Unable to read saved opportunities: {error}")
        return
    st.caption("Ranked by discount against the lowest of market, recent and historical values.")
    if not eligible:
        st.info("This source has no items with market, recent and historical prices all available "
                "(Classic feeds report historical values as zero, and a single addon scan has no history), "
                "so the discount screen cannot run. "
                "Use Crafting or Browse market instead.")
        return
    if results.is_empty():
        st.info("No items match these filters. Try reducing the minimum discount or clearing the search.")
        return
    display = results.select(
        pl.col("rank").alias("Rank"), pl.col("item_name").alias("Item"),
        pl.col("item_id").alias("Item ID"), pl.col("variant_id").alias("Variant"),
        pl.col("variant_state").fill_null("legacy").alias("Variant state"),
        (pl.col("min_buyout") / COPPER_PER_GOLD).alias("Minimum buyout (g)"),
        (pl.col("reference_copper") / COPPER_PER_GOLD).alias("Reference (g)"),
        (pl.col("discount") * 100).alias("Discount (%)"),
        (pl.col("net_spread_copper") / COPPER_PER_GOLD).alias("Estimated spread (g)"),
    )
    st.dataframe(display, hide_index=True, width="stretch", height=600, column_config={
        **gold_columns("Minimum buyout (g)", "Reference (g)", "Estimated spread (g)"),
        "Discount (%)": st.column_config.NumberColumn(format="%.1f"),
    })
    st.download_button("Download this table", display.write_csv(), "brownstone-opportunities.csv", "text/csv")
    st.caption(f"Spread assumes a {config['auction_cut']:.0%} auction cut. Sale speed, deposits and listing "
               "quantity are not modeled; this is a research shortlist.")
