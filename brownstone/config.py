"""Load and validate config/market.toml into a list of fully resolved sources."""
import re
import tomllib
from pathlib import Path
from typing import Any, NotRequired, TypedDict

from . import markets
from .markets import MARKET_KEYS
from .scans import EVIDENCE_FIELDS

__all__ = ["ADDON_PROVIDER", "LOCAL_OVERRIDES", "MARKET_KEYS", "NEUTRAL_AUCTION_CUT", "Source", "build_source",
           "read_sources"]

_SLUG = re.compile(r"[a-z0-9_-]+")
# Neutral auction houses (Booty Bay, Gadgetzan, Everlook) take 15% instead of 5%.
NEUTRAL_AUCTION_CUT = 0.15


class Source(TypedDict):
    """One feed observing one market, plus the shared settings it inherits from market.toml.

    ``source_id`` names the feed (and its data folder); the market fields name the auction house.
    """
    source_id: str
    provider: str  # Who observed the prices, e.g. "tsm" or "addon".
    enabled: bool  # Disabled sources stay configured but are hidden from the app and refused by the CLI.
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
    source_url: NotRequired[str]  # HTTPS download; every provider except "addon".
    scan_path: NotRequired[Path]  # provider "addon": the local SavedVariables file to import.
    scan_evidence: NotRequired[dict[str, str]]  # provider "addon": values each scan must match.


_REQUIRED_IN_FILE = ("source_id", "provider", "game_version", "region", "scope",
                     "max_age_hours", "auction_cut", "min_discount", "top_n")
ADDON_PROVIDER = "addon"  # Our own BrownstoneScan SavedVariables; every other provider is an HTTPS CSV.


def build_source(shared: dict, entry: dict) -> Source:
    """Merge one [[sources]] entry over the shared settings, validate it and derive market_id."""
    if "market_id" in entry:
        raise ValueError(f"{entry.get('source_id', '?')}: market_id is derived from the market fields; remove it")
    if "data_dir" in entry:
        # Every source shares one folder and one database; the app upgrades and reads that one.
        raise ValueError(f"{entry.get('source_id', '?')}: data_dir is shared; set it once at the top of market.toml")
    # Precedence: blank market fields < shared settings < neutral-house cut < the entry itself.
    source: dict[str, Any] = {"realm": "", "server_type": "", "faction": "", "enabled": True, **shared}
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
    _validate_feed(source)
    if source["max_age_hours"] <= 0 or source["top_n"] <= 0:
        raise ValueError("max_age_hours and top_n must be positive")
    if not 0 <= source["auction_cut"] < 1 or not 0 <= source["min_discount"] < 1:
        raise ValueError("auction_cut and min_discount must be in [0, 1)")
    return source  # type: ignore[return-value]  # Keys and values checked above.


def _validate_feed(source: dict) -> None:
    """An addon source reads a local scan file and checks house evidence; others download over HTTPS."""
    label = source["source_id"]
    if not isinstance(source["enabled"], bool):
        raise ValueError(f"{label}: enabled must be true or false")
    if source["provider"] == ADDON_PROVIDER:
        if "source_url" in source:
            raise ValueError(f"{label}: an addon source reads scan_path, not source_url")
        if not source.get("scan_path"):
            raise ValueError(f"{label}: an addon source needs scan_path, the SavedVariables file to import")
        source["scan_path"] = Path(source["scan_path"])
        evidence = source.setdefault("scan_evidence", {})
        unknown = set(evidence) - set(EVIDENCE_FIELDS)
        if unknown:
            raise ValueError(f"{label}: unknown scan_evidence {sorted(unknown)}; use {sorted(EVIDENCE_FIELDS)}")
        if not all(isinstance(value, str) and value for value in evidence.values()):
            raise ValueError(f"{label}: scan_evidence values must be non-empty text")
        return
    if "scan_path" in source or "scan_evidence" in source:
        raise ValueError(f"{label}: scan_path and scan_evidence are for addon sources only")
    if not str(source.get("source_url", "")).startswith("https://"):
        raise ValueError(f"{label}: source_url must use HTTPS")


LOCAL_OVERRIDES = "market.local.toml"  # Next to market.toml; ignored by Git.


def read_sources(path: Path, local: Path | None = None) -> list[Source]:
    """Every configured source, in file order, each merged with the shared settings.

    A file without ``[[sources]]`` describes a single source at the top level. ``local`` is an
    optional, untracked file of per-machine settings, ``[sources.<source_id>]`` tables merged over
    that source's entry (for example ``enabled`` and a ``scan_path`` inside a personal folder).
    """
    path = path.resolve()
    with path.open("rb") as file:
        raw = tomllib.load(file)
    entries = raw.pop("sources", None) or [{}]
    if local is not None and local.exists():
        with local.open("rb") as file:
            overrides = tomllib.load(file).get("sources", {})
        known = {entry.get("source_id") for entry in entries}
        unknown = set(overrides) - known
        if unknown:
            raise ValueError(f"{local.name} overrides unknown sources {sorted(unknown)}")
        for entry in entries:
            override = overrides.get(entry.get("source_id"), {})
            if {"source_id", "market_id"} & set(override):
                raise ValueError(f"{local.name} cannot change source_id or market_id")
            entry.update(override)
    # Paths are relative to the project, never the caller's working directory.
    root = path.parent.parent
    raw["data_dir"] = (root / raw.get("data_dir", "data")).resolve()
    for entry in entries:
        if isinstance(entry.get("scan_path"), str):
            entry["scan_path"] = (root / entry["scan_path"]).resolve()
    sources = [build_source(raw, entry) for entry in entries]
    if len({source["source_id"] for source in sources}) != len(sources):
        raise ValueError("Source IDs must be unique")
    return sources
