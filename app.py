"""Streamlit entry point: market selection, user-triggered refresh and view dispatch.

Ingestion only runs when the user clicks Refresh. Views live in ``views/``.
"""
from pathlib import Path

import streamlit as st

from brownstone.action_board import compatible
from brownstone.config import read_config
from brownstone.crafting import load_recipe_catalog
from brownstone.pipeline import run
from views import crafting, market

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="Brownstone Markets", page_icon="📊", layout="wide")
st.title("Brownstone Markets")
st.caption("Your local WoW market research desk · prices in gold")

try:
    all_config = read_config(ROOT / "config/market.toml")
    catalogs = [load_recipe_catalog(path) for path in sorted((ROOT / "config").glob("*-tailoring.toml"))]
except Exception as error:
    st.error(f"Could not read configuration: {error}")
    st.stop()

with st.sidebar:
    st.header("Market")
    sources = all_config.get("sources", [all_config])
    selected = st.selectbox("Data source", range(len(sources)),
                            format_func=lambda i: sources[i].get("label", sources[i]["market_id"]))
    config = sources[selected]
    st.caption(("Regional commodity prices" if config.get("scope") == "region" else "Realm-specific item prices")
               + " · edit config/market.toml to change markets")
    refresh = st.button("Refresh from TSM", type="primary", width="stretch")
    views = ["Crafting", "Browse market", "Opportunities"]
    craftable = any(compatible(catalog, config) for catalog in catalogs)
    # Keyed per source so each market remembers its own view.
    view = st.radio("View", views, index=0 if craftable else 1, key=f"view-{config['market_id']}")

if refresh:
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
