"""Money standard: store and calculate integer copper; display gold.

Tables show decimal gold (four places, so one copper is exact and columns sort numerically).
Headline numbers and prose use the in-game ``12g 34s 56c`` form.
"""

COPPER_PER_SILVER = 100
COPPER_PER_GOLD = 10_000
GOLD_TABLE_FORMAT = "%.4f"


def to_gold(copper: int | None) -> float | None:
    return None if copper is None else copper / COPPER_PER_GOLD


def format_money(copper: int | None) -> str:
    if copper is None:
        return "—"
    sign = "-" if copper < 0 else ""
    gold, remainder = divmod(abs(copper), COPPER_PER_GOLD)
    silver, copper_part = divmod(remainder, COPPER_PER_SILVER)
    parts = [f"{gold:,}g"] if gold else []
    if silver:
        parts.append(f"{silver}s")
    if copper_part or not parts:
        parts.append(f"{copper_part}c")
    return sign + " ".join(parts)


def parse_money(text: str) -> int:
    """Parse explicit integer g/s/c amounts, including format_money's signed output."""
    import re

    value = text.strip().lower()
    sign = -1 if value.startswith("-") else 1
    value = value.removeprefix("-").strip()
    tokens = list(re.finditer(r"(\d{1,3}(?:,\d{3})+|\d+)\s*([gsc])", value))
    remainder = re.sub(r"(\d{1,3}(?:,\d{3})+|\d+)\s*([gsc])", "", value)
    if not tokens or remainder.strip():
        raise ValueError("Use explicit units, for example 12g 50s or 75s; bare numbers are not amounts.")
    units = [token[2] for token in tokens]
    if len(set(units)) != len(units):
        raise ValueError("Use each of g, s and c at most once.")
    multipliers = {"g": COPPER_PER_GOLD, "s": COPPER_PER_SILVER, "c": 1}
    return sign * sum(int(token[1].replace(",", "")) * multipliers[token[2]] for token in tokens)
