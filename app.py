"""Local market review; ingestion only runs when the user clicks Refresh."""
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import polars as pl
import streamlit as st

from brownstone.pipeline import run
from brownstone.config import read_config
from brownstone.analysis import rank, browse
from brownstone.storage import completed_snapshots

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
    view = st.radio("View", ["Opportunities", "Browse market"])
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

manifests = completed_snapshots(config)
if not manifests:
    st.info("No completed snapshot yet. Click Refresh from TSM to collect your first market.")
    st.stop()

latest = max(manifests, key=lambda record: record["collected_at"])
upstream = datetime.fromisoformat(latest["updated_at"])
age = (datetime.now(timezone.utc) - upstream).total_seconds() / 3600
left, middle, right = st.columns(3)
left.metric("Items observed", f"{latest['rows']:,}")
middle.metric("Scan age", f"{age:.1f} hours")
right.metric("Saved snapshots", len(manifests))
st.caption(f"Upstream scan: {upstream.strftime('%Y-%m-%d %H:%M UTC')} · Latest collection: {latest['collected_at']}")
if age > config["max_age_hours"]:
    st.warning("This saved snapshot is stale. Refresh before using it to evaluate current prices.")

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
