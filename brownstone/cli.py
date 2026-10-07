import argparse
import sys
from pathlib import Path

from . import character_snapshots, journal
from .config import ADDON_PROVIDER, LOCAL_OVERRIDES, Source, read_sources
from .pipeline import import_guidance, import_scans, preview_scans, run
from .recipe_catalogs import ARCHIVE_DIR, CONFIG_DIR
from .recipe_import import archive_page, load_selection, prepare_catalog
from .scan_inputs import CLEAR_REMINDER, file_rows, import_inputs, input_source, latest_rows, preview_inputs

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
    parser.add_argument("--archive-dir", type=Path, default=ARCHIVE_DIR)
    args = parser.parse_args(argv)
    output = args.output or CONFIG_DIR / args.selection.name
    try:
        copy, manifest = archive_page(args.page, args.archive_dir, args.saved_at)
        current = output.read_text(encoding="utf-8") if output.exists() else None
        prepared = prepare_catalog(copy.read_bytes(), load_selection(args.selection), manifest["saved_at"], current)
        catalog, changes = prepared["catalog"], prepared["changes"]
        output.write_text(prepared["text"], encoding="utf-8")
    except Exception as error:
        print(f"Recipe import failed: {error}", file=sys.stderr)
        sys.exit(1)
    print(f"Archived {manifest['source_url']} (saved {manifest['saved_at']}, SHA-256 {manifest['sha256'][:12]}...) "
          f"as {copy}")
    print(f"Wrote {len(catalog['recipes'])} recipes and {len(catalog['items'])} items to {output}")
    for line in changes or (["no recipe or vendor price changes"] if changes is not None else []):
        print(f"  {line}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1:2] == ["recipes"]:
        recipes_main(sys.argv[2:])
        return
    if sys.argv[1:2] == ["beta-report"]:
        beta_report_main(sys.argv[2:])
        return
    parser = argparse.ArgumentParser(description="Collect TSM snapshots or import BrownstoneScan addon scans")
    parser.add_argument("--config", type=Path, default=ROOT / "config/market.toml")
    parser.add_argument("--input", type=Path,
                        help="Use a local TSM CSV, or for an addon source a SavedVariables file other than scan_path")
    parser.add_argument("--source", "--market", dest="source",
                        help="Configured source_id to collect (defaults to the first enabled source)")
    parser.add_argument("--scan", action="append", dest="scans", metavar="SCAN_ID",
                        help="Addon sources: import only this scan from the file (repeatable)")
    parser.add_argument("--preview", action="store_true", help="Read-only addon preview and drop cleanup status")
    args = parser.parse_args()
    try:
        config = _select_source(args)
        if config["provider"] == ADDON_PROVIDER:
            _addon_command(config, args)
            return
        else:
            if args.scans:
                raise ValueError("--scan applies only to addon sources")
            if args.preview:
                raise ValueError("--preview applies only to addon sources")
            result, output = run(config, args.input)
    except Exception as error:
        print(f"Pipeline failed: {error}", file=sys.stderr)
        sys.exit(1)
    print(result.select("rank", "item_id", "item_name", "buy_gold", "discount", "net_spread_gold"))
    print(f"Saved {result.height} screening candidates to {output}")


def beta_report_main(argv: list[str]) -> None:
    """Check a play-session file without writing to configured data or game files."""
    from .beta_report import create_report
    parser = argparse.ArgumentParser(prog="brownstone beta-report", description=beta_report_main.__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--config", type=Path, default=ROOT / "config/market.toml")
    parser.add_argument("--source", help="Addon source for isolated round-trip house checks")
    args = parser.parse_args(argv)
    sources = read_sources(args.config, args.config.with_name(LOCAL_OVERRIDES))
    matches = [s for s in sources if s["provider"] == ADDON_PROVIDER and
               (s["source_id"] == args.source if args.source else s["enabled"])]
    if len(matches) != 1:
        parser.error("Select one configured addon source with --source")
    folder, report, code = create_report(args.file, matches[0], ROOT / "work/beta-reports", args.previous)
    print(folder)
    print(", ".join(f"{report['totals'][status]} {status}" for status in ("pass", "warn", "fail")))
    sys.exit(code)


def _select_source(args: argparse.Namespace) -> Source:
    """The source named by --source (which must be enabled), else the first enabled source."""
    sources = read_sources(args.config, args.config.with_name(LOCAL_OVERRIDES))
    if not args.source:
        enabled = [source for source in sources if source["enabled"]]
        if not enabled:
            raise ValueError(f"No enabled source; set enabled = true for one in {args.config} or {LOCAL_OVERRIDES}")
        return enabled[0]
    matches = [source for source in sources if source["source_id"] == args.source]
    if not matches:
        raise ValueError(f"Unknown source: {args.source}")
    if not matches[0]["enabled"]:
        raise ValueError(f"Source {args.source} is disabled; set enabled = true in "
                         f"{args.config.with_name(LOCAL_OVERRIDES)}")
    return matches[0]


def _report_scans(config: Source, manifest: dict) -> None:
    for snapshot in manifest.get("snapshots", []):
        print(f"Snapshot {snapshot['snapshot_id']}: {snapshot['outcome']}")
    for row in journal.outcome_rows(manifest.get("non_scan_records", [])):
        print(f"Journal {row['Character']} {row['Family']}: {row['Entries']} {row['Outcome']}")
    for scan in manifest["scans"]:
        print(f"Scan {scan['scan_id']}: {scan['status']}, {scan['listing_count']:,} listings, {scan['outcome']}")
    if manifest["status"] == "complete":
        print(f"Prices for {manifest['rows']:,} items from scan {manifest['scan_id']} "
              f"(finished {manifest['updated_at']}) are now current for {config['market_id']}")
    elif manifest["scans"]:
        print("No complete scan among the imported scans; prices are unchanged")
    print(import_guidance(manifest))


def _addon_command(config: Source, args: argparse.Namespace) -> None:
    if config.get("drop_folder") and args.input is None:
        preview = preview_inputs(config)
        _report_inputs(preview)
        if not args.preview:
            for result in import_inputs(config, preview, scan_ids=args.scans):
                print(f"File {result['file']}: {result['status']}")
                if "manifest" in result:
                    _report_scans(config, result["manifest"])
                if "error" in result:
                    print(result["error"], file=sys.stderr)
            _report_inputs(preview_inputs(config))
        return
    if args.input is not None:
        config = input_source(config, args.input)
    if args.preview:
        single = preview_scans(config, args.input)
        for summary, known, mismatch in zip(single.summaries, single.known, single.mismatches, strict=True):
            state = "duplicate" if known else "other house" if mismatch else "new"
            print(f"{config.get('machine', 'missing')} {summary['scan_id']}: {state}")
        _report_character_records(single, config.get("machine"))
        return
    _report_scans(config, import_scans(config, args.input, args.scans))


def _report_inputs(preview) -> None:
    for row in file_rows(preview):
        print(row)
    for file in preview.files:
        if file.preview:
            _report_character_records(file.preview, file.machine)
            for summary, known, mismatch in zip(file.preview.summaries, file.preview.known,
                                                file.preview.mismatches, strict=True):
                state = "duplicate" if known else "other house" if mismatch else "new"
                print(f"  {file.machine} {summary['scan_id']}: {state}")
    for row in latest_rows(preview):
        print(row)
    print(CLEAR_REMINDER)


def _report_character_records(preview, machine) -> None:
    for row in journal.preview_rows(preview, machine) + character_snapshots.preview_rows(preview, machine):
        print(row)
