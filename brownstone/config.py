"""Load and validate config/market.toml into a list of fully resolved sources."""
import re
import tomllib
from pathlib import Path
from typing import NotRequired, TypedDict

# A market is this whole identity; item IDs never join across any of these.
MARKET_KEYS = ("market_id", "game_version", "region", "scope", "realm")
_SLUG = re.compile(r"[a-zA-Z0-9_-]+")


class Source(TypedDict):
    """One price feed plus the shared settings it inherits from the top of market.toml."""
    market_id: str
    game_version: str
    region: str
    scope: str  # "realm" or "region"
    realm: str  # "" for regional sources
    source_url: str
    data_dir: Path
    max_age_hours: float
    auction_cut: float
    min_discount: float
    top_n: int
    label: NotRequired[str]
    ruleset: NotRequired[str]  # Required for crafting; matches a catalog's ruleset.
    allow_missing_updated_at: NotRequired[bool]


def _validate(source: dict) -> Source:
    missing = [key for key in Source.__required_keys__ if key not in source]
    if missing:
        raise ValueError(f"Source {source.get('market_id', '?')} is missing {sorted(missing)}")
    if not _SLUG.fullmatch(source["market_id"]):
        raise ValueError("market_id must contain only letters, numbers, underscores or hyphens")
    if source["scope"] not in {"region", "realm"}:
        raise ValueError("Source scope must be region or realm")
    if not source["game_version"] or not source["region"]:
        raise ValueError("Every source needs game_version and region")
    if (source["scope"] == "realm") != bool(source["realm"]):
        raise ValueError("Only realm sources must specify a realm")
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
    sources = [_validate({**raw, **entry}) for entry in entries]
    if len({source["market_id"] for source in sources}) != len(sources):
        raise ValueError("Source market IDs must be unique")
    return sources
