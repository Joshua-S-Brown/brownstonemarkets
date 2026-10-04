import argparse
import sys
import tomllib
from pathlib import Path

from .config import ADDON_PROVIDER, LOCAL_OVERRIDES, read_sources
from .pipeline import import_scans, run
from .recipe_import import archive_page, build_catalog, catalog_changes, dumps_catalog, extract_page, load_selection

ROOT = Path(__file__).resolve().parents[1]


def recipes_main(argv: list[str]) -> None:
    """Generate a recipe catalog from a Wowhead profession page saved in a browser (never downloads)."""
    parser = argparse.ArgumentParser(prog="python -m brownstone recipes", description=recipes_main.__doc__)
    parser.add_argument("--page", type=Path, required=True,
                        help="Saved page, e.g. https://www.wowhead.com/forever/spells/professions/tailoring")
    parser.add_argument("--selection", type=Path, required=True, help="config/recipe-selections/<catalog>.toml")
    parser.add_argument("--output", type=Path, help="Catalog to write (default: config/<selection name>.toml)")
    parser.add_argument("--saved-at", help="Date the page was saved, YYYY-MM-DD (default: earlier archive, then "
                                           "the file's date)")
    parser.add_argument("--archive-dir", type=Path, default=ROOT / "data/recipe-sources")
    args = parser.parse_args(argv)
    output = args.output or ROOT / "config" / args.selection.name
    try:
        copy, manifest = archive_page(args.page, args.archive_dir, args.saved_at)
        extract = extract_page(copy.read_text(encoding="utf-8", errors="replace"), manifest["sha256"],
                               manifest["saved_at"])
        catalog = build_catalog(extract, load_selection(args.selection))
        text = dumps_catalog(catalog)
        changes = None
        if output.exists():
            changes = catalog_changes(tomllib.loads(output.read_text(encoding="utf-8")), tomllib.loads(text))
        output.write_text(text, encoding="utf-8")
    except Exception as error:
        print(f"Recipe import failed: {error}", file=sys.stderr)
        sys.exit(1)
    print(f"Archived {manifest['source_url']} (saved {manifest['saved_at']}, SHA-256 {manifest['sha256'][:12]}...) "
          f"as {copy}")
    print(f"Wrote {len(catalog['recipes'])} recipes and {len(catalog['items'])} items to {output}")
    for line in changes or (["no recipe or vendor price changes"] if changes is not None else []):
        print(f"  {line}")


def main() -> None:  # noqa: C901
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1:2] == ["recipes"]:
        recipes_main(sys.argv[2:])
        return
    parser = argparse.ArgumentParser(description="Collect TSM snapshots or import BrownstoneScan addon scans")
    parser.add_argument("--config", type=Path, default=ROOT / "config/market.toml")
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
