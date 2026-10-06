"""Streamlit entry point: market selection, user-triggered refresh and view dispatch.

Ingestion only runs when the user clicks Refresh (TSM) or Import addon scan. Views live in ``views/``.
"""
from pathlib import Path

import streamlit as st

from brownstone.config import ADDON_PROVIDER, LOCAL_OVERRIDES, read_sources
from brownstone.crafting import parse_recipe_catalog
from brownstone.item_names import seed_catalog_names
from brownstone.pipeline import run
from brownstone.recipe_catalogs import ARCHIVE_DIR, CONFIG_DIR, find_catalogs
from brownstone.storage import upgrade_database
from views import catalogs as catalogs_view
from views import crafting, market, scan_changes, scan_import, today
from views.common import EXPERIENCES

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="Brownstone Markets", page_icon="📊", layout="wide")
st.title("Brownstone Markets")
st.caption("Your local WoW market research desk · prices in gold")

try:
    sources = [source for source in read_sources(ROOT / "config/market.toml", ROOT / "config" / LOCAL_OVERRIDES)
               if source["enabled"]]
except Exception as error:
    st.error(f"Could not read configuration: {error}")
    st.stop()
catalogs = []
try:
    # Every profession's catalog, found by its selection file (STORY-014).
    entries = [entry for entry in find_catalogs(CONFIG_DIR) if entry["catalog"]]
except Exception as error:  # Unreadable selection files must not hide the other views.
    st.warning(f"Recipe catalogs unavailable: {error}")
    entries = []
for entry in entries:
    try:  # One bad catalog must not hide the others on the combined board.
        catalogs.append({**parse_recipe_catalog(entry["catalog"]), "catalog_id": entry["name"]})
    except Exception as error:
        st.warning(f"Recipe catalog {entry['name']} unavailable: {error}")
if not sources:
    st.error("No enabled data source. Set enabled = true for a source in config/market.toml or "
             "config/market.local.toml, then reload.")
    st.stop()

with st.sidebar:
    st.header("Market")
    order = list(EXPERIENCES)
    games = sorted(dict.fromkeys(source["game_version"] for source in sources),
                   key=lambda game: order.index(game) if game in order else len(order))
    game = st.selectbox("Experience", games, format_func=lambda game: EXPERIENCES.get(game, game))
    experience_sources = [source for source in sources if source["game_version"] == game]
    selected: int | None = 0
    if len(experience_sources) > 1:  # Several observers of one experience: never pick one silently.
        selected = st.selectbox("Data source", range(len(experience_sources)), index=None, key=f"source-{game}",
                                placeholder="Choose a source",
                                format_func=lambda i: experience_sources[i].get("label",
                                                                            experience_sources[i]["source_id"]))
    if selected is None:
        st.session_state.pop("scan_import_identity", None)
        st.info("This experience has several enabled sources. Choose one above.")
        st.stop()
    config = experience_sources[selected]
    st.caption(f"Source {config['source_id']} · {config.get('label', config['source_id'])}")
    st.caption(f"Market {config['market_id']} · {config['provider'].upper()} feed"
               + (" · region-wide commodities" if config["scope"] == "region" else "")
               + " · edit config/market.toml to change sources")
    addon = config["provider"] == ADDON_PROVIDER
    refresh = False
    if addon:
        scan_import.render(config)
    else:
        st.session_state.pop("scan_import_identity", None)
        refresh = st.button("Refresh from TSM", type="primary", width="stretch")
    views = ["Today", "Crafting", "Browse market", "Opportunities", "Recipe catalogs", "Scan changes"]
    # Every source starts on Today and remembers subsequent navigation.
    view_key = f"view-{config['source_id']}"
    view = st.radio("View", views, index=0, key=view_key)

# Views open the database read-only, so bring an existing older database up to date first. This never
# creates one, and Preview itself never migrates (ADDON-06).
try:
    if upgrade_database(config["data_dir"]):
        st.toast("Database upgraded to the current schema.")
except Exception as error:
    st.error(f"Could not upgrade the database: {error}. Close other Brownstone windows or terminals and reload.")
    st.stop()
# Catalog labels (DATA-02) are written once per database and catalog contents, not on every rerun.
name_seed = (str(config["data_dir"]), hash(tuple((catalog["game_version"], item["item_id"], item.get("name"))
                                                for catalog in catalogs for item in catalog.get("items", []))))
if st.session_state.get("catalog_name_seed") != name_seed:
    try:
        seed_catalog_names(config["data_dir"], catalogs)
        st.session_state["catalog_name_seed"] = name_seed
    except Exception as error:  # Labels are a convenience: never block the views over them.
        st.warning(f"Catalog item names unavailable: {error}")

if refresh:
    with st.spinner("Downloading and preserving the latest market snapshot…"):
        try:
            run(config)
            st.success("Market data refreshed and saved.")
        except Exception as error:
            st.error(f"Refresh failed: {error}. Your previous successful snapshot remains available.")

if view == "Today":
    today.render(config, catalogs)
elif view == "Crafting":
    crafting.render(config, catalogs)
elif view == "Browse market":
    market.render_browse(config)
elif view == "Scan changes":
    scan_changes.render(config, catalogs)
elif view == "Recipe catalogs":
    catalogs_view.render(config, sources, CONFIG_DIR, ARCHIVE_DIR)
else:
    market.render_opportunities(config)
