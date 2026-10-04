"""Load and validate config/market.toml into a list of fully resolved sources."""
import re
import tomllib
from pathlib import Path
from typing import Any, NotRequired, TypedDict

from . import markets
from .markets import MARKET_KEYS

__all__ = ["MARKET_KEYS", "NEUTRAL_AUCTION_CUT", "Source", "build_source", "read_sources"]

_SLUG = re.compile(r"[a-z0-9_-]+")
# Neutral auction houses (Booty Bay, Gadgetzan, Everlook) take 15% instead of 5%.
NEUTRAL_AUCTION_CUT = 0.15


class Source(TypedDict):
    """One feed observing one market, plus the shared settings it inherits from market.toml.

    ``source_id`` names the feed (and its data folder); the market fields name the auction house.
    """
    source_id: str
    provider: str  # Who observed the prices, e.g. "tsm" or "addon".
    source_url: str
    market_id: str  # Derived from the market fields; never configured directly.
    game_version: str
    region: str
    scope: str  # "house" or "region"
    realm: str  # "" for realmless or region-wide markets
    server_type: str  # Forever: normal/pvp/roleplaying/hardcore; "" elsewhere
    faction: str  # alliance/horde/neutral, or "" for cross-faction
    data_dir: Path
    max_age_hours: float
    auction_cut: float
    min_discount: float
    top_n: int
    label: NotRequired[str]
    rules_version: NotRequired[str]  # Required for crafting; matches a catalog's rules_version.
    allow_missing_updated_at: NotRequired[bool]


_REQUIRED_IN_FILE = ("source_id", "provider", "source_url", "game_version", "region", "scope",
                     "max_age_hours", "auction_cut", "min_discount", "top_n")


def build_source(shared: dict, entry: dict) -> Source:
    """Merge one [[sources]] entry over the shared settings, validate it and derive market_id."""
    if "market_id" in entry:
        raise ValueError(f"{entry.get('source_id', '?')}: market_id is derived from the market fields; remove it")
    # Precedence: blank market fields < shared settings < neutral-house cut < the entry itself.
    source: dict[str, Any] = {"realm": "", "server_type": "", "faction": "", **shared}
    if {**source, **entry}.get("faction") == "neutral" and "auction_cut" not in entry:
        source["auction_cut"] = NEUTRAL_AUCTION_CUT
    source.update(entry)
    missing = [key for key in _REQUIRED_IN_FILE if key not in source]
    if missing:
        raise ValueError(f"Source {source.get('source_id', '?')} is missing {missing}")
    if not _SLUG.fullmatch(source["source_id"]):
        raise ValueError("source_id must contain only lowercase letters, numbers, underscores or hyphens")
    markets.validate(source)
    source["market_id"] = markets.market_id(source)
    if not source["source_url"].startswith("https://"):
        raise ValueError("source_url must use HTTPS")
    if source["max_age_hours"] <= 0 or source["top_n"] <= 0:
        raise ValueError("max_age_hours and top_n must be positive")
    if not 0 <= source["auction_cut"] < 1 or not 0 <= source["min_discount"] < 1:
        raise ValueError("auction_cut and min_discount must be in [0, 1)")
    return source  # type: ignore[return-value]  # Keys and values checked above.


def read_sources(path: Path) -> list[Source]:
    """Every configured source, in file order, each merged with the shared settings.

    A file without ``[[sources]]`` describes a single source at the top level.
    """
    path = path.resolve()
    with path.open("rb") as file:
        raw = tomllib.load(file)
    entries = raw.pop("sources", None) or [{}]
    # Paths are relative to the project, never the caller's working directory.
    raw["data_dir"] = (path.parent.parent / raw.get("data_dir", "data")).resolve()
    sources = [build_source(raw, entry) for entry in entries]
    if len({source["source_id"] for source in sources}) != len(sources):
        raise ValueError("Source IDs must be unique")
    return sources
