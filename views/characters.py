"""Visual character cards; evidence and calculations live in brownstone.characters."""
import altair as alt
import streamlit as st

from brownstone.characters import build_characters
from brownstone.money import format_money


def _utc(text: str | None) -> str:
    """ISO UTC evidence time as short display text."""
    return f"{text[:16].replace('T', ' ')} UTC" if text else "unknown"

# Decorative only: reported skill IDs, never name-based calculation or classification.
ICONS = {171: "⚗️", 164: "⚒️", 333: "✨", 202: "⚙️", 165: "🪡", 197: "🧵",
         182: "🌿", 186: "⛏️", 393: "🪶", 185: "🍳", 129: "🩹", 356: "🎣"}


def render(config) -> None:
    st.subheader("Characters")
    st.caption("Who can do what · imported character evidence")
    try:
        cards = build_characters(config)
    except Exception as error:
        st.error(f"Unable to read characters: {error}")
        return
    if not cards:
        st.info("No characters imported for this source. Use Import addon scan in the sidebar to import snapshots "
                "and journals.")
        return
    st.caption(f"{len(cards)} characters · source {config['source_id']} · market {config['market_id']}")
    # Each row has at most two cards; native flex wrapping stacks them on narrow screens.
    for offset in range(0, len(cards), 2):
        with st.container(horizontal=True, gap="medium"):
            for card in cards[offset:offset + 2]:
                with st.container(border=True, width=520):
                    _card(card)


def _card(card: dict) -> None:
    st.subheader(card["name"])
    st.caption(f"{card['realm']} · {card['faction']} · {card['machine'] or 'machine unknown'}")
    st.caption(f"Last seen {card['last_seen_relative']} · {_utc(card['last_seen_utc'])}")
    with st.container(horizontal=True):
        if card["stale"]:
            st.badge("stale", color="orange")
        if card["skills_status"] == "skills unknown":
            st.badge("skills unknown", color="gray")
        elif card["skills_status"] == "possibly incomplete":
            st.badge("possibly incomplete", color="yellow")
    left, right = st.columns(2)
    left.metric("Level", card["level"] if card["level"] is not None else "unknown")
    right.metric("Gold", format_money(card["gold_copper"]) if card["gold_copper"] is not None else "unknown")
    if card["bags_at"] is None:
        st.caption("No readable bags snapshot")
    if not card["professions"] and card["skills_status"] != "skills unknown":
        st.caption("No skill lines reported in the latest readable snapshot.")
    for profession in card["professions"]:
        _profession(profession)
    _history(card["history"])


def _profession(row: dict) -> None:
    st.markdown(f"{ICONS.get(row['skill_id'], '🔹')} **{row['name']}**")
    rank = "unknown" if row["rank"] is None else str(row["rank"])
    maximum = "unknown" if row["max_rank"] is None else str(row["max_rank"])
    if row["progress"] is None:
        st.caption(f"Rank {rank} / {maximum}")
    else:
        st.progress(row["progress"], text=f"{rank} / {maximum}")
    with st.container(horizontal=True):
        if row["at_cap"]:
            st.badge("at cap: train the next tier", color="green")
        if row["possibly_incomplete"]:
            st.badge("possibly incomplete", color="yellow")
    if row["recipe_source"] == "unknown":
        st.caption("Known recipes: unknown")
        return
    count = row["known_count"]
    st.caption(f"Known recipes: {count if count is not None else 'unknown'} · {row['recipe_source']}")
    if "window list" in row["recipe_source"]:
        st.caption(f"Window list: {_utc(row['recipes_at'])}")
    if row["seen_at"]:
        st.caption(f"Seen crafted: {_utc(row['seen_at'])}")


def _history(rows: list[dict]) -> None:
    with st.expander("Progress over time", expanded=False):
        if not rows:
            st.caption("No readable level or rank history yet.")
            return
        chart = alt.Chart(alt.Data(values=[row | {"Observed UTC": row["UTC"]} for row in rows])).mark_line(
            point=True).encode(
            x=alt.X("UTC:T", title="Snapshot (UTC)", axis=alt.Axis(format="%b %d %H:%M"), scale=alt.Scale(type="utc")),
            y=alt.Y("Value:Q", title="Level / skill rank", scale=alt.Scale(zero=False)),
            color=alt.Color("Series:N", title="Observed"),
            order=[alt.Order("UTC:T"), alt.Order("Sequence:Q")],
            tooltip=["Observed UTC:N", "Series:N", "Value:Q", "Sequence:Q"])
        st.altair_chart(chart, width="stretch")
        st.dataframe(rows, hide_index=True, width="stretch")
