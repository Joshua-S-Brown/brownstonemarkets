"""Conservative Forever/Classic item-link identity; names never determine variants."""
import re

import polars as pl

ITEM_KEYS = ["item_id", "variant_id", "variant_state"]
_LINK = re.compile(r"\|Hitem:([^|]+)\|h")


def _number(value: str) -> int:
    return int(value) if value else 0


def _payload_identity(parts: list[str]) -> str | None:
    """Supported stat fields; reject unrecognized tails instead of pooling them."""
    if len(parts) < 13:
        raise ValueError("truncated link")
    head = [_number(v) for v in parts[:13]]
    enchant, *gems = head[1:6]
    suffix, unique = head[6:8]
    count = head[12]
    if count < 0 or count > len(parts) - 13 or head[10] != 0 or head[11] not in (0, 1):
        raise ValueError("unsupported link layout")
    if suffix < 0 and unique:
        # Negative random suffixes can use a seed/factor; this beta has supplied no such examples.
        raise ValueError("unconfirmed suffix factor")
    bonuses = sorted(_number(v) for v in parts[13:13 + count])
    if any(b <= 0 for b in bonuses):
        raise ValueError("invalid bonus ID")
    _check_tail(parts[13 + count:])
    if not any([enchant, *gems, suffix, *bonuses]):
        return None
    return f"v1:e{enchant}:g{','.join(map(str, gems))}:s{suffix}:b{','.join(map(str, bonuses))}"


def _check_tail(tail: list[str]) -> None:
    if not tail:
        return
    count = _number(tail[0])
    if count < 0 or 1 + count * 2 > len(tail):
        raise ValueError("truncated modifiers")
    for i in range(count):
        kind, value = map(_number, tail[1 + i * 2:3 + i * 2])
        if kind != 28 or value < 0:
            raise ValueError("unconfirmed modifier")
    if any(_number(v) for v in tail[1 + count * 2:]):
        raise ValueError("unconfirmed link tail")


def identity(item_id: int, link: str | None) -> tuple[str | None, str]:
    """Return (variant ID, base/variant/unresolved); retain raw links elsewhere."""
    match = _LINK.search(link or "")
    if match is None:
        return None, "unresolved"
    parts = match[1].split(":")
    try:
        if _number(parts[0]) != item_id:
            return None, "unresolved"
        variant = _payload_identity(parts)
    except ValueError:
        return None, "unresolved"
    return variant, "variant" if variant else "base"


def columns(item_ids: list[int], links: list[str | None]) -> list[pl.Series]:
    pairs = list(zip(item_ids, links, strict=True))
    cache = {pair: identity(*pair) for pair in set(pairs)}
    identities = [cache[pair] for pair in pairs]
    return [pl.Series("variant_id", [v[0] for v in identities], dtype=pl.String),
            pl.Series("variant_state", [v[1] for v in identities], dtype=pl.String)]
