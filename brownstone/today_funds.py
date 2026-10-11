"""Resolve Today funds from the shared source/full-market character projection."""
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from .freshness import is_stale
from .money import format_money
from .today_settings import TodaySettings


@dataclass(frozen=True)
class TodayFunds:
    settings: TodaySettings
    origin: str
    notes: tuple[str, ...] = ()

    @property
    def summary(self) -> str:
        settings = self.settings
        return (f"Gold available: {format_money(settings.gold_copper)} ({self.origin}) · "
                f"Minimum batch gain: {format_money(settings.minimum_gain)} · "
                f"Most crafts per item: {settings.max_crafts}")


def _capture_label(character: tuple, bags: dict, now: datetime, max_age_hours: float) -> str:
    captured = datetime.fromtimestamp(bags["captured_at"], UTC)
    age = (now - captured).total_seconds() / 3600
    label = f"{character[0]}, captured {captured:%Y-%m-%d %H:%M} UTC"
    if is_stale(age, max_age_hours):
        label += f"; stale gold capture, age {age:.1f} hours"
    return label


def resolve_funds(settings: TodaySettings, data: dict, now: datetime, max_age_hours: float) -> TodayFunds:
    """Data must be professions.latest_data for the selected source and full market.

    Its bags record is the newest readable capture, with same-second sequence ordering.
    Missing or zero gold stays unknown under Today's funds rule.
    """
    if settings.gold_override:
        return TodayFunds(settings, "entered amount")
    # A saved character missing from this source and market plans as All recipes, so funds follow.
    selected = settings.character if settings.character in data else None
    characters = [selected] if selected is not None else sorted(data)
    captures = []
    missing = []
    for character in characters:
        bags = data.get(character, {}).get("bags", {})
        gold = bags.get("gold_copper")
        if type(gold) is int and gold > 0 and "captured_at" in bags:
            captures.append((character, bags))
        else:
            missing.append(character[0])
    if not captures:
        who = selected[0] if selected else "this source's characters"
        return TodayFunds(settings, "entered amount", (f"No captured gold for {who}; using the entered amount.",))
    total = sum(bags["gold_copper"] for _, bags in captures)
    labels = tuple(_capture_label(c, bags, now, max_age_hours) for c, bags in captures)
    effective = replace(settings, gold_copper=total)
    if selected is not None:
        return TodayFunds(effective, labels[0])
    notes = labels
    if missing:
        notes += (f"No captured gold for {', '.join(missing)}; excluded from the recorded total.",)
    return TodayFunds(effective, f"across {len(captures)} characters; gold must be mailed to the crafter", notes)
