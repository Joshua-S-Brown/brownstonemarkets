import argparse
import sys
from pathlib import Path

from .config import ADDON_PROVIDER, LOCAL_OVERRIDES, read_sources
from .pipeline import import_scans, run


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Collect TSM snapshots or import BrownstoneScan addon scans")
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[1] / "config/market.toml")
    parser.add_argument("--input", type=Path,
                        help="Use a local TSM CSV, or for an addon source a SavedVariables file other than scan_path")
    parser.add_argument("--source", "--market", dest="source",
                        help="Configured source_id to collect (defaults to the first enabled source)")
    parser.add_argument("--scan", action="append", dest="scans", metavar="SCAN_ID",
                        help="Addon sources: import only this scan from the file (repeatable)")
    args = parser.parse_args()
    try:
        sources = read_sources(args.config, args.config.with_name(LOCAL_OVERRIDES))
        if args.source:
            matches = [source for source in sources if source["source_id"] == args.source]
            if not matches:
                raise ValueError(f"Unknown source: {args.source}")
            config = matches[0]
            if not config["enabled"]:
                raise ValueError(f"Source {args.source} is disabled; set enabled = true in "
                                 f"{args.config.with_name(LOCAL_OVERRIDES)}")
        else:
            config = next(source for source in sources if source["enabled"])
        if config["provider"] == ADDON_PROVIDER:
            manifest = import_scans(config, args.input, args.scans)
        else:
            if args.scans:
                raise ValueError("--scan applies only to addon sources")
            result, output = run(config, args.input)
    except Exception as error:
        print(f"Pipeline failed: {error}", file=sys.stderr)
        sys.exit(1)
    if config["provider"] == ADDON_PROVIDER:
        for scan in manifest["scans"]:
            print(f"Scan {scan['scan_id']}: {scan['status']}, {scan['listing_count']:,} listings, {scan['outcome']}")
        if manifest["status"] == "complete":
            print(f"Prices for {manifest['rows']:,} items from scan {manifest['scan_id']} "
                  f"(finished {manifest['updated_at']}) are now current for {config['market_id']}")
        else:
            print("No complete scan in this file; prices are unchanged")
        return
    print(result.select("rank", "item_id", "item_name", "buy_gold", "discount", "net_spread_gold"))
    print(f"Saved {result.height} screening candidates to {output}")
