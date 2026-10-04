import re
import tomllib
from pathlib import Path


def read_config(path: Path) -> dict:
    path = path.resolve()
    with path.open("rb") as file:
        config = tomllib.load(file)
    if "sources" in config:
        sources = config.pop("sources")
        resolved = []
        for source in sources:
            if source.get("scope") not in {"region", "realm"}:
                raise ValueError("Source scope must be region or realm")
            if not source.get("game_version") or not source.get("region"):
                raise ValueError("Every source needs game_version and region")
            if (source["scope"] == "realm") != bool(source.get("realm")):
                raise ValueError("Only realm sources must specify a realm")
            if not re.fullmatch(r"[a-zA-Z0-9_-]+", source["market_id"]) or not source["source_url"].startswith("https://"):
                raise ValueError("Invalid market ID or source URL")
            resolved.append({**config, **source})
        if not resolved or len({s["market_id"] for s in resolved}) != len(resolved):
            raise ValueError("Sources must be nonempty with unique market IDs")
        config.update(resolved[0])
        config["sources"] = resolved
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", config["market_id"]):
        raise ValueError("market_id must contain only letters, numbers, underscores or hyphens")
    if not config["source_url"].startswith("https://"):
        raise ValueError("source_url must use HTTPS")
    if config["max_age_hours"] <= 0 or config["top_n"] <= 0:
        raise ValueError("max_age_hours and top_n must be positive")
    if not 0 <= config["auction_cut"] < 1 or not 0 <= config["min_discount"] < 1:
        raise ValueError("auction_cut and min_discount must be in [0, 1)")
    # Paths are relative to the project, never the caller's working directory.
    config["data_dir"] = (path.parent.parent / config["data_dir"]).resolve()
    for source in config.get("sources", []):
        source["data_dir"] = config["data_dir"]
    return config
