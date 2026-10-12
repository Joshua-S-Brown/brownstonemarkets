"""Business questions and experience order for both app navigation surfaces."""
# Forever, the target, opens by default whatever order market.toml lists sources in.
EXPERIENCES = {"forever": "WoW Forever", "classic": "Classic Era", "retail": "Retail (regression)"}


def experiences(sources: list) -> list[str]:
    """Each source's game version once, in EXPERIENCES order; unknown versions last."""
    order = list(EXPERIENCES)
    return sorted(dict.fromkeys(source["game_version"] for source in sources),
                  key=lambda game: order.index(game) if game in order else len(order))


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
