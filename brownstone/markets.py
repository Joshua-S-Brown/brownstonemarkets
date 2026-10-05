"""Market identity: which auction house a price belongs to, independent of who observed it.

A market is game version + environment (live/beta) + region + the house within the region:
- Classic Era: a realm and faction (Mankrik, Alliance).
- Retail: a connected realm (cross-faction), or the region-wide commodity pool.
- Forever: no realms; a server type (normal/pvp/roleplaying/hardcore) and faction, or neutral.

``market_id`` is derived from these fields, so two sources configured for the same house and environment
always agree on it. Sources (who observed it) are identified separately by ``source_id``.
"""
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

# Every field that distinguishes one market's prices from another's. Never join on fewer.
MARKET_KEYS = ("market_id", "game_version", "region", "scope", "realm", "server_type", "faction", "environment")

SCOPES = {"house", "region"}  # house: one auction house's listings; region: a region-wide pool.
FACTIONS = {"alliance", "horde", "neutral", ""}  # "" means cross-faction.
SERVER_TYPES = {"normal", "pvp", "roleplaying", "hardcore", ""}  # Forever only; "" elsewhere.
_LEGACY_FACTION_SUFFIXES = ("-alliance", "-horde")


def market_id(fields: Mapping[str, Any]) -> str:
    """Canonical ID, e.g. classic-us-mankrik-alliance, forever-us-roleplaying-alliance.

    Live IDs stay unchanged; beta economies append "-beta".
    """
    parts = [fields["game_version"], fields["region"]]
    parts += [value for key in ("realm", "server_type", "faction") if (value := fields.get(key))]
    if fields["scope"] == "region":
        parts.append("commodities")
    if fields.get("environment") == "beta":
        parts.append("beta")
    return "-".join(parts)


def validate(fields: Mapping[str, Any]) -> None:
    """Raise ValueError unless the fields describe exactly one auction house."""
    label = fields.get("source_id", "?")
    if not fields.get("game_version") or not fields.get("region"):
        raise ValueError(f"{label}: every market needs game_version and region")
    validate_environment(fields)
    if fields.get("scope") not in SCOPES:
        raise ValueError(f"{label}: scope must be house or region")
    if fields.get("faction", "") not in FACTIONS:
        raise ValueError(f"{label}: faction must be alliance, horde, neutral or blank")
    if fields.get("server_type", "") not in SERVER_TYPES:
        raise ValueError(f"{label}: server_type must be normal, pvp, roleplaying, hardcore or blank")
    if fields["scope"] == "region" and fields.get("realm"):
        raise ValueError(f"{label}: a region-wide market has no realm")
    if fields["scope"] == "house" and not (fields.get("realm") or fields.get("server_type")):
        raise ValueError(f"{label}: a house market needs a realm or, for realmless games, a server_type")
    if fields.get("realm") and fields.get("server_type"):
        raise ValueError(f"{label}: use a realm or a server_type, not both")


def validate_environment(fields: Mapping[str, Any]) -> None:
    """Forever must explicitly choose its economy; other games are live only (default set in config)."""
    environment = fields.get("environment")
    label = fields.get("source_id", "?")
    if fields.get("game_version") != "forever":
        if "environment" in fields and environment != "live":
            raise ValueError(f"{label}: environment must be live for {fields.get('game_version')}")
        return
    if environment not in {"live", "beta"}:
        raise ValueError(f"{label}: environment must be live or beta (required for forever)")


# Frozen legacy classification boundary; official Blizzard launch date in
# docs/requirements.md → Product direction → Official dates (checked 2026-10-04).
LEGACY_FOREVER_LAUNCH = datetime(2026, 11, 4, tzinfo=UTC)


def legacy_environment(record: Mapping[str, Any]) -> str:
    """Stored collection time, never scan evidence or names, classifies pre-environment data."""
    collected = record.get("collected_at")
    if isinstance(collected, str):
        collected = datetime.fromisoformat(collected.replace("Z", "+00:00"))
    if collected is not None and collected.tzinfo is None:
        collected = collected.replace(tzinfo=UTC)
    return ("beta" if record.get("game_version") == "forever"
            and collected is not None and collected < LEGACY_FOREVER_LAUNCH else "live")


def upgrade_legacy(record: dict) -> dict:
    """Read an old manifest or stored scan in the current shape without changing the original.

    Before the split, ``market_id`` was the source's ID, scope ``realm`` meant one house, and
    Classic faction lived in the realm slug (``mankrik-alliance``).
    """
    if "source_id" in record:
        upgraded = dict(record)
        if "environment" not in upgraded:
            upgraded["environment"] = legacy_environment(upgraded)
            if upgraded["environment"] == "beta" and _has_market_fields(upgraded):
                upgraded["market_id"] = market_id(upgraded)
        return upgraded
    upgraded = {**record, "source_id": record.get("market_id"), "legacy": True}
    upgraded["environment"] = record.get("environment", legacy_environment(record))
    upgraded.setdefault("server_type", "")
    if upgraded.get("scope") == "realm":
        upgraded["scope"] = "house"
    realm = upgraded.get("realm") or ""
    upgraded.setdefault("faction", "")
    if upgraded.get("game_version") == "classic" and not upgraded["faction"]:
        for suffix in _LEGACY_FACTION_SUFFIXES:
            if realm.endswith(suffix):
                upgraded["realm"], upgraded["faction"] = realm.removesuffix(suffix), suffix[1:]
    if _has_market_fields(upgraded):
        upgraded["market_id"] = market_id(upgraded)
    return upgraded


def _has_market_fields(record: Mapping[str, Any]) -> bool:
    """Incomplete records keep their stored ID; the identity filter then excludes them."""
    return bool(record.get("game_version") and record.get("region") and record.get("scope") in SCOPES)
