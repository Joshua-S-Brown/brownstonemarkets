"""Streamlit entry point: market selection, user-triggered refresh and view dispatch.

Ingestion only runs when the user clicks Refresh (TSM) or Import addon scan. Views live in ``views/``.
"""
from pathlib import Path

import streamlit as st

from brownstone.action_board import compatible
from brownstone.config import ADDON_PROVIDER, LOCAL_OVERRIDES, read_sources
from brownstone.crafting import parse_recipe_catalog
from brownstone.pipeline import import_guidance, import_scans, new_scans, run
from brownstone.recipe_catalogs import ARCHIVE_DIR, CONFIG_DIR, find_catalogs
from brownstone.storage import upgrade_database
from views import catalogs as catalogs_view
from views import crafting, market, scan_changes
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
    games = list(dict.fromkeys(source["game_version"] for source in sources))
    game = st.selectbox("Experience", games, format_func=lambda game: EXPERIENCES.get(game, game))
    experience_sources = [source for source in sources if source["game_version"] == game]
    selected: int | None = 0
    if len(experience_sources) > 1:  # Several observers of one experience: never pick one silently.
        selected = st.selectbox("Data source", range(len(experience_sources)), index=None, key=f"source-{game}",
                                placeholder="Choose a source",
                                format_func=lambda i: experience_sources[i].get("label",
                                                                            experience_sources[i]["source_id"]))
    if selected is None:
        st.info("This experience has several enabled sources. Choose one above.")
        st.stop()
    config = experience_sources[selected]
    st.caption(f"Source {config['source_id']} · {config.get('label', config['source_id'])}")
    st.caption(f"Market {config['market_id']} · {config['provider'].upper()} feed"
               + (" · region-wide commodities" if config["scope"] == "region" else "")
               + " · edit config/market.toml to change sources")
    addon = config["provider"] == ADDON_PROVIDER
    refresh = st.button("Import addon scan" if addon else "Refresh from TSM", type="primary", width="stretch",
                        help=f"Reads {config['scan_path']}" if addon else None)
    views = ["Crafting", "Browse market", "Opportunities", "Recipe catalogs", "Scan changes"]
    craftable = any(compatible(catalog, config) for catalog in catalogs)
    # Keyed per source so each market remembers its own view. Once Crafting's link has set the view,
    # the default index must not compete with it (Streamlit warns about both).
    view_key = f"view-{config['source_id']}"
    view = st.radio("View", views, index=0 if craftable or view_key in st.session_state else 1, key=view_key)

# Views open the database read-only, so bring an older database up to date first.
try:
    if upgrade_database(config["data_dir"]):
        st.toast("Database upgraded to the current schema.")
except Exception as error:
    st.error(f"Could not upgrade the database: {error}. Close other Brownstone windows or terminals and reload.")
    st.stop()

if refresh and addon:
    with st.spinner("Preserving and importing the addon scan file…"):
        try:
            manifest = import_scans(config)
            outcomes = "; ".join(f"{s['scan_id']} {s['status']}: {s['outcome']}" for s in manifest["scans"])
            if not new_scans(manifest):
                st.warning(f"{import_guidance(manifest)} ({outcomes})")
            else:
                if manifest["status"] == "complete":
                    st.success(f"Imported. Prices now come from scan {manifest['scan_id']}. {outcomes}.")
                else:
                    st.warning(f"No complete scan in the file, so prices are unchanged. {outcomes}.")
                st.info(import_guidance(manifest))
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
elif view == "Scan changes":
    scan_changes.render(config, catalogs)
elif view == "Recipe catalogs":
    catalogs_view.render(config, sources, CONFIG_DIR, ARCHIVE_DIR)
else:
    market.render_opportunities(config)
