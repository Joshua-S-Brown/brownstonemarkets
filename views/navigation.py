"""Display-only place and section navigation (UI-01)."""
import streamlit as st

PLACES = {
    "Today": ("Today plan", "All recipes"),
    "Team": ("Characters",),
    "Market": ("Browse market", "Skill-up demand", "Watchlist", "Below usual price"),
    "Data": ("Import", "Recipe catalogs", "Scan changes"),
}
QUESTIONS = {
    "Today": "What should I do today to make gold?",
    "Team": "Who can do what, and how are my characters progressing?",
    "Market": "What is the market telling me?",
    "Data": "What evidence do I have, and how do I bring it up to date?",
    "Today plan": "What should I craft, buy and sell today?",
    "All recipes": "Which recipes could make a profit at the current prices?",
    "Characters": "What can each character do, and how have they progressed?",
    "Browse market": "What is listed, and at what price?",
    "Skill-up demand": "Which materials will levellers need in each skill band?",
    "Watchlist": "Have prices reached the targets I chose to watch?",
    "Below usual price": "Which items are below their recent and historical price and could be flipped?",
    "Import": "How do I bring this source's observations up to date?",
    "Recipe catalogs": "Which recipes and material costs are in my catalogs?",
    "Scan changes": "What changed in price and supply between two scans?",
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
