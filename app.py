"""Streamlit entry point: market selection, user-triggered refresh and view dispatch.

Ingestion only runs when the user clicks Refresh (TSM) or Import addon scan. Views live in ``views/``.
"""
from pathlib import Path

import streamlit as st

from brownstone.action_board import compatible
from brownstone.config import ADDON_PROVIDER, LOCAL_OVERRIDES, read_sources
from brownstone.crafting import load_recipe_catalog
from brownstone.pipeline import clear_reminder, import_scans, run
from brownstone.storage import upgrade_database
from views import crafting, market

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="Brownstone Markets", page_icon="📊", layout="wide")
st.title("Brownstone Markets")
st.caption("Your local WoW market research desk · prices in gold")

try:
    sources = [source for source in read_sources(ROOT / "config/market.toml", ROOT / "config" / LOCAL_OVERRIDES)
               if source["enabled"]]
    catalogs = [load_recipe_catalog(path) for path in sorted((ROOT / "config").glob("*-tailoring.toml"))]
except Exception as error:
    st.error(f"Could not read configuration: {error}")
    st.stop()
if not sources:
    st.error("No enabled data source. Set enabled = true for a source in config/market.toml or "
             "config/market.local.toml, then reload.")
    st.stop()

# Views open the database read-only, so bring an older database up to date first.
try:
    if upgrade_database(sources[0]["data_dir"]):
        st.toast("Database upgraded to the current schema.")
except Exception as error:
    st.error(f"Could not upgrade the database: {error}. Close other Brownstone windows or terminals and reload.")
    st.stop()

with st.sidebar:
    st.header("Market")
    selected = st.selectbox("Data source", range(len(sources)),
                            format_func=lambda i: sources[i].get("label", sources[i]["source_id"]))
    config = sources[selected]
    st.caption(f"Market {config['market_id']} · {config['provider'].upper()} feed"
               + (" · region-wide commodities" if config["scope"] == "region" else "")
               + " · edit config/market.toml to change sources")
    addon = config["provider"] == ADDON_PROVIDER
    refresh = st.button("Import addon scan" if addon else "Refresh from TSM", type="primary", width="stretch",
                        help=f"Reads {config['scan_path']}" if addon else None)
    views = ["Crafting", "Browse market", "Opportunities"]
    craftable = any(compatible(catalog, config) for catalog in catalogs)
    # Keyed per source so each market remembers its own view.
    view = st.radio("View", views, index=0 if craftable else 1, key=f"view-{config['source_id']}")

if refresh and addon:
    with st.spinner("Preserving and importing the addon scan file…"):
        try:
            manifest = import_scans(config)
            outcomes = "; ".join(f"{s['scan_id']} {s['status']}: {s['outcome']}" for s in manifest["scans"])
            if manifest["status"] == "complete":
                st.success(f"Imported. Prices now come from scan {manifest['scan_id']}. {outcomes}.")
            else:
                st.warning(f"No complete scan in the file, so prices are unchanged. {outcomes}.")
            if reminder := clear_reminder(manifest):
                st.info(reminder)
        except Exception as error:
            st.error(f"Import failed: {error}. Your previous successful snapshot remains available.")
elif refresh:
    with st.spinner("Downloading and preserving the latest market snapshot…"):
        try:
            run(config)
            st.success("Market data refreshed and saved.")
        except Exception as error:
            st.error(f"Refresh failed: {error}. Your previous successful snapshot remains available.")

if view == "Crafting":
    crafting.render(config, catalogs)
elif view == "Browse market":
    market.render_browse(config)
else:
    market.render_opportunities(config)
