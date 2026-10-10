"""Character cards and progression from the shared scoped evidence projections."""
from datetime import UTC, datetime, timedelta

from . import professions

STALE_DAYS = 7


def build_characters(config, now: datetime | None = None) -> list[dict]:
    """Return plain card data; unknown values remain None and money stays integer copper."""
    now = now or datetime.now(UTC)
    cards = [_card(key, state, now) for key, state in professions.latest_data(config).items()]
    return sorted(cards, key=lambda card: (-card["last_seen"], card["name"], card["realm"], card["faction"]))


def _card(key: tuple, state: dict, now: datetime) -> dict:
    bags = state["bags"]
    last, machine = max(state["observations"], key=lambda pair: professions._order(pair[0]))
    moment = datetime.fromtimestamp(last["captured_at"], UTC)
    skills = professions.data_rows(state)
    return {"name": key[0], "realm": key[1], "faction": key[2], "machine": machine,
            "last_seen": last["captured_at"], "last_seen_utc": moment.isoformat(),
            "last_seen_relative": relative_time(moment, now),
            "bags_at": bags.get("captured_at"), "level": bags.get("level"),
            "gold_copper": bags.get("gold_copper"),
            "stale": bool(bags and now - datetime.fromtimestamp(bags["captured_at"], UTC) > timedelta(days=STALE_DAYS)),
            "skills_status": skills[0]["skills_status"],
            "professions": [_profession(row) for row in skills if row["name"] is not None],
            "history": history_rows(state["history"])}


def _profession(row: dict) -> dict:
    rank, maximum = row["rank"], row["max_rank"]
    return row | {"at_cap": rank is not None and maximum is not None and rank == maximum,
                  "progress": min(rank / maximum, 1.0) if rank is not None and maximum else None}


def history_rows(snapshots: list[dict]) -> list[dict]:
    """Long-form observed level/rank points, with missing values omitted, never filled."""
    rows = []
    for record in snapshots:
        values = {"Level": record.get("level"), **{
            name: skill.get("rank") for name, skill in professions._skills(record).items()}}
        moment = datetime.fromtimestamp(record["captured_at"], UTC).isoformat()
        for name, value in values.items():
            if value is not None:
                rows.append({"UTC": moment, "Sequence": record.get("sequence"), "Series": name, "Value": value})
    return rows


def relative_time(moment: datetime, now: datetime) -> str:
    seconds = int((now - moment).total_seconds())
    if seconds < 0:
        return "in the future"
    for unit, width in (("day", 86400), ("hour", 3600), ("minute", 60)):
        if seconds >= width:
            count = seconds // width
            return f"{count} {unit}{'s' if count != 1 else ''} ago"
    return "just now"
