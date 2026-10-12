"""Display-only place and section navigation (UI-01)."""
import streamlit as st

from brownstone.navigation import QUESTIONS

PLACES = {
    "Today": ("Today plan", "All recipes"),
    "Team": ("Characters",),
    "Market": ("Browse market", "Skill-up demand", "Watchlist", "Below usual price"),
    "Data": ("Import", "Recipe catalogs", "Scan changes"),
}

LEGACY = {
    "Crafting": ("Today", "All recipes"),
    "Characters": ("Team", "Characters"),
    "Browse market": ("Market", "Browse market"),
    "Skill-ups": ("Market", "Skill-up demand"),
    "Watchlist": ("Market", "Watchlist"),
    "Opportunities": ("Market", "Below usual price"),
    "Recipe catalogs": ("Data", "Recipe catalogs"),
    "Scan changes": ("Data", "Scan changes"),
}


def retain_state():
    # Assigning remembered widget values keeps them through Streamlit's cleanup when another
    # source is selected. Keep the original per-source key, including migration of old page names.
    for key in list(st.session_state):
        if key.startswith(("view-", "section-")) or key == "scan_import_selection":
            st.session_state[key] = st.session_state[key]


def sidebar(source_id):
    key = f"view-{source_id}"
    old = st.session_state.get(key)
    if old in LEGACY:
        place, section = LEGACY[old]
        st.session_state[key] = place
        st.session_state[f"section-{source_id}-{place}"] = section
    # One radio keeps keyboard navigation and the remembered place in one widget; Data is
    # visually separated within that radio. The scope prevents styling unrelated view controls.
    st.html("""<style>.st-key-places [role=radiogroup] > :last-child {
        border-top: 1px solid rgba(128,128,128,.4); margin-top: .75rem; padding-top: .75rem;
    }</style>""")
    with st.container(key="places"):
        return st.radio("View", list(PLACES), index=0, key=key, width="stretch")


def section(place, source_id):
    st.header(place)
    st.caption(QUESTIONS[place])
    options = PLACES[place]
    key = f"section-{source_id}-{place}"
    return st.segmented_control("Section", options, default=None if key in st.session_state else options[0], key=key,
                                selection_mode="single", required=True)
