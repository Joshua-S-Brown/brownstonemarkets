"""Business questions and experience order for app navigation."""
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
    "Supply chains": "Where does the margin come from?",
    "Ledger": "Where did our gold and goods go?",
    "Stock": "What do we hold, and what should we restock?",
    "Data": "What evidence do I have, and how do I bring it up to date?",
}


def source_label(source):
    """Shared short label without filesystem/configuration provenance."""
    game = EXPERIENCES.get(source['game_version'], source['game_version'])
    place = source.get('server_type') or source.get('realm') or source.get('scope', '')
    faction = source.get('faction', '')
    environment = source.get('environment', 'live')
    return f"{game} · {place.title()} {faction.title()}" + (f" ({environment})" if environment != 'live' else '')
