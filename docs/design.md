# Brownstone design

How the system is built. Rules and their rationale live in `requirements.md`; this document covers structure, data contracts and extension points.

## Data flow

```text
TSM CSV ──download──▶ bronze (exact bytes + manifest JSON)
        ──normalize─▶ silver (validated Parquet, one per collection)
        ──load──────▶ DuckDB market_snapshots (deduplicated analytical snapshots)
        ──rank──────▶ gold (discount-screen CSV/Parquet per collection)

SavedVariables .lua ──copy──▶ bronze (gzip of the exact bytes, stored once per SHA-256, + manifest JSON)
        ──parse/check─▶ scans (Lua subset parser, house evidence, stack unit prices)
        ──silver──────▶ per scan: _scan, _listings and, if complete, _prices Parquet
        ──load────────▶ DuckDB addon_scans + scan_listings + market_snapshots (complete scans only)

saved Wowhead page ──archive─▶ data/recipe-sources (exact bytes once per SHA-256 + manifest)
        ──extract─▶ recipes and items ──select─▶ catalog TOML (config/recipe-selections/*.toml)

catalog TOML ──load──▶ crafting / action_board ◀── price_observations (DuckDB)
```

Raw bytes are written before validation, so failures stay inspectable. DuckDB writes are transactional, but silver, DuckDB and gold together are not one atomic operation (see `status.md` for recovery).

## Modules

```text
app.py                  Streamlit entry: sidebar, Refresh, view dispatch
views/                  Streamlit only; display, no calculations
  common.py             snapshot loading, freshness display, gold columns
  crafting.py           Action Board and recipe explanation
  catalogs.py           Recipe catalogs page: status, add and update a profession (preview, then write)
  market.py             Browse market and Opportunities
brownstone/             importable without Streamlit
  config.py             market.toml (+ untracked market.local.toml overrides) → list[Source] (typed, validated)
  markets.py            market identity: MARKET_KEYS, derived market_id, validation, legacy upgrade
  sources.py            HTTP download
  scans.py              BrownstoneScan SavedVariables: parse, validate, house check, unit and item prices
  normalization.py      CSV → validated frame
  pipeline.py           orchestration of one collection: run (TSM CSV) or import_scans (addon)
  storage.py            DuckDB schema and migrations, load/dedup, manifests, scoped price and depth reads
  analysis.py           browse and discount screen queries
  freshness.py          the one staleness policy
  money.py              copper ↔ gold display helpers
  crafting.py           catalog loading, expansion, route costs, price bases
  recipe_import.py      saved Wowhead profession page → archive, extract, catalog TOML (no network)
  recipe_catalogs.py    catalogs found by selection file: status, previews and the add/update writes
  selection_files.py    in-place edits of a selection file that keep its comments
  action_board.py       ranking and label policy (versioned)
  cli.py                `python -m brownstone`: collect or import a source; `recipes` subcommand
launch.py               local server launcher with code-fingerprint restart
```

Dependencies point inward: `app.py` → `views/` → `brownstone`. Domain modules (`action_board`, `freshness`, `money`, and `crafting` apart from reading a catalog file) do no other I/O and take the clock as a parameter. The `dashboard` extra (Streamlit) is needed only for `app.py` and `views/`.

## Data contracts

| Entity | Identity | Notes |
| --- | --- | --- |
| Market | `game_version, region, scope, realm, server_type, faction` → derived `market_id` | One auction house. Crafting also needs the source's `rules_version` |
| Source | `source_id` (+ `provider`, `source_url`) | One feed observing one market; a `[[sources]]` entry; names its data folders |
| Collection | `snapshot_id` (UTC time + random suffix) | Bronze CSV + manifest with source and market identity; manifest records `analytical_snapshot_id` |
| Analytical snapshot | source + upstream scan time + SHA-256 | Repeated identical content from the same source reuses the earlier ID |
| Price observation | analytical snapshot + source + market identity + item ID | Integer copper: `min_buyout, market_value, recent_value, historical_value` |
| Addon scan | `source_id, scan_id` → `snapshot_id = <source_id>:<scan_id>` | `addon_scans`: status, `partial`, `priced`, times, counts, `nonexact_stacks`, client, house evidence, scan and file SHA-256. Its import manifest lists every scan with an outcome (`imported`, `duplicate`, `partial (not priced)`, `empty`) and counts `already_imported`; `scan_id`, `updated_at` and `analytical_snapshot_id` name the newest complete scan, and status is `no_complete_scan` when there is none |
| Listing | `source_id, scan_id, listing_index` + market identity | `scan_listings`: `item_id, item_name, quantity, buyout` (whole stack), `unit_buyout` (exact only), `unit_buyout_ceil`, `min_bid, bid, complete_info` |
| Catalog | `game_version, rules_version, catalog_version` | TOML generated from a selection file and one saved page (CRAFT-08). Header: `source_url`, `source_sha256`, `verified_at`. Items: role, Wowhead URL, optional `vendor_price_copper` with `vendor_price_source_url`, `vendor_verified`, `availability`. Recipes: inputs, `output_quantity`, `required_skill`, Wowhead spell URL, `verification_url`, `evidence_sha256`, optional `output_quantity_verified`, `availability` |
| Recipe selection | file name = catalog name | `config/recipe-selections/<catalog>.toml`: catalog header fields, finished `[[recipes]]` (with optional overrides), `[recipe_defaults]`, `[[items]]` vendor evidence and notes |
| Recipe source page | SHA-256 | `data/recipe-sources/wowhead/<game>/<profession>/<sha16>.html` + `.json` manifest: page URL, `saved_at`, `archived_at`, original file name |

### Schema migrations

- **Versioning.** `storage.py` records `schema_version` in a `schema_info` table.
- **Migrations are frozen.** A fresh database replays every migration, so it is identical to an upgraded one; a test enforces this.
  - Version 1: explicit table, plus the identity columns.
  - Version 2: market/source split. Adds `source_id`, `server_type` and `faction`, moves Classic faction out of the realm slug, renames scope `realm` to `house`, and re-derives `market_id`.
  - Version 3: addon scans. Adds `addon_scans` and `scan_listings`; `market_snapshots` is unchanged.
- **Entry point.** `upgrade_database` copies the file to `brownstone.v<N>.backup.duckdb`, then runs pending migrations statement by statement. DuckDB cannot reliably add a column and update the table in one transaction, so every step is idempotent and the version is recorded only after each migration completes.
- **Callers.** The app calls it at startup and the pipeline before its write transaction. `load_snapshot` refuses an outdated schema.
- **Adding one.** Write `_migrate_to_N`, register it in `MIGRATIONS` and bump `SCHEMA_VERSION`.
- **Nullable columns,** so v0.1 databases match fresh ones; validation happens in normalization.
- **Manifests are never rewritten.** `markets.upgrade_legacy` reads pre-split manifests in the current shape.

## Crafting calculation

- `basis_prices(observations, basis)` turns observed prices into buy and sell unit price maps (CRAFT-04).
- `evaluate_recipe(catalog, recipe_id, buy, auction_cut, sell)` chooses each input's cheapest route recursively. It returns:
  - direct choices
  - the chosen-route shopping list
  - the all-craft expansion
  - cost, net revenue, profit, margin and break-even
- `Decimal` handles the auction-cut rounding.
- `storage.listing_depth` returns listing and unit counts by item for the same analytical snapshot used by `price_observations`. It first checks the scoped `addon_scans` record is complete and priced, then aggregates `scan_listings` with the source, full market identity, snapshot ID and scan ID. It returns `None` when unavailable, or zero counts for absent requested items. The Crafting view renders these separately from `rank_recipes`; depth never enters calculation or policy inputs (CRAFT-09).
- Catalog discovery supplies `catalog_id` from the selection-file stem. Standalone catalogs default to a header identity (`game_version:rules_version:profession:catalog_version`); combined inputs must have unique identities. Rows carry `catalog_id`, `recipe_id` and `profession`, and `catalog_for_row` resolves details to the original catalog.
- `rank_catalogs` selects compatible catalogs, calls `rank_recipes` separately for each graph, and applies the same shared ranking helper to all rows. `filter_profession` preserves combined ranks. Prices and depth are read once for the union of compatible catalog item IDs, using the same source, full market scope and analytical snapshot. See CRAFT-05 and UI-01/UI-04 in `requirements.md` for behavior.
- `rank_recipes` checks that the catalog, market and snapshot are compatible, then:
  - evaluates every finished output under both bases
  - labels and sorts the rows (CRAFT-05)
  - isolates per-recipe errors so one bad recipe doesn't hide the others

## Recipe import

- `archive_page` copies the saved page once per SHA-256 and writes a manifest. A rerun from the archived copy reuses the recorded `saved_at`, so catalogs rebuild identically offline.
- `extract_page` reads the page's `listviewspells` array (recipes) and the `WH.Gatherer.addData(3, …)` object (items). Wowhead leaves a few keys unquoted; everything else is JSON.
- `build_catalog` applies the selection: it adds intermediates, assigns roles (finished, intermediate, vendor material only with selection evidence, material), stamps evidence and rejects version mismatches, ambiguous creators and variable yields.
- `dumps_catalog` writes deterministic TOML. `catalog_changes` lists recipe and vendor price differences against the current file for review.
- `prepare_catalog(raw, selection, saved_at, current)` is the one generation path: extract, build, dump, validate with the board's `parse_recipe_catalog`, and diff, writing nothing. The CLI and the app call it after `archive_bytes` (which `archive_page` wraps for files on disk).
- `page_build` reads the game patch from the page's "latest patch (…)" description and the newest build Wowhead's "Added in build" filter lists for that patch.
- `recipe_catalogs` drives the app page. `find_catalogs` reads every selection file and its catalog, if generated. `catalog_status` gives version, recipe count, page date, build (from the archived copy, when it is on this machine), SHA-256, `unconfirmed_values` and `refresh_reasons`. `preview_update`/`regenerate` and `preview_new`/`create` are preview and write pairs: each write recomputes its preview, so it writes exactly what was shown. `CONFIG_DIR` and `ARCHIVE_DIR` are the defaults the CLI and app share.
- `selection_files` edits a selection file in place: `set_value` replaces one header line, and `edit_recipes` removes and adds `[[recipes]]` blocks, adds or removes vendor marks (keeping an item's other notes), drops notes on items no chosen recipe uses, and reads the result back, refusing if it doesn't match. `preview_update(entry, raw, saved_at, recipe_ids, vendor_ids, rules_version)` runs these edits before generating, so a write is exactly the preview.
- `single_makers` (in `recipe_import`) maps each item to its one usable recipe; items several usable recipes make are left out, so they are bought. The importer and the app's recipe list both use it. Choices travel as `choices(recipes, vendor)`.
- The view keys each preview by a hash of the page bytes, date and selection; changing any of them hides the write button until a new preview. After a write it reloads and lists the tracked files written (catalog and selection), never committing.
- Tests use trimmed extracts in `tests/fixtures/wowhead/` and assert that each tracked catalog equals the importer's output.

## Switching to WoW Forever

1. **Market identity (done, STORY-009).** Configure `scope = "house"`, `server_type`, `faction` and no realm, for example `forever-us-roleplaying-alliance`. Neutral houses default to a 15% cut.
2. **Price source (done, STORY-010).** There is no TSM or Blizzard feed. A `provider = "addon"` source imports the addon's SavedVariables file: bronze stays byte-for-byte, listings go to `scan_listings`, and item-level prices are derived in the `market_snapshots` shape (rules ADDON-01 to ADDON-06).
3. **Catalog (done, STORY-004).** `config/forever-tailoring.toml` is generated from the saved Forever Tailoring page (CRAFT-08). To cover another profession or more recipes, use **Add a profession** or **Update a profession** on the Recipe catalogs page.
4. **Configuration.** Add the `[[sources]]` entry: market fields, `rules_version`, `provider = "addon"`, `scan_path` and `scan_evidence` (see the disabled example in `config/market.toml`). Other non-TSM feeds get their own adapter producing the same `market_snapshots` columns.

No change to crafting, the Action Board or the views should be needed. If one is, treat it as a design defect.

## Quality gates

Ruff (lint, import order and a complexity limit of 10 per function), mypy (on `brownstone/` and `launch.py`) and pytest with a branch-coverage floor run locally and in CI; configuration is in `pyproject.toml`. `Source` is a `TypedDict`, so mypy checks config key names wherever a function is annotated with it.

## Known design debt

- **Complexity debt:** `scans.parse_lua` (13) exceeds Ruff's limit of 10 and carries `# noqa: C901`. It is kept as one loop deliberately: it runs once per token, about a million times for a 24 MB scan, and splitting it adds a function call to each. Revisit only with a measurement.
- **Coverage gaps** (92% overall as of 2026-10-04): `views/market.py` 75% (Opportunities with data, which only Retail can supply), `app.py` 89% (configuration and upgrade errors), `views/catalogs.py` 90% (error messages for unreadable selections and failed writes). `sources.py` downloads over the network, which offline tests don't exercise.
- Records other than `Source` (manifests, catalog entries, evaluation results) are plain dicts.
- `views/` is not type-checked.
- `completed_snapshots` reads every manifest on each page load; this is fine at current volumes.
- Re-importing an addon file parses it in full before deduplication can skip its scans: about 0.1 s per schema-2 scan, 0.9 s per schema-1 scan. Scans left in the file add up until `/bscan clear`, and bronze keeps a compressed copy of each distinct file (about 0.5 MB per schema-2 scan).
- Each imported scan adds about 4.7 MB to DuckDB (`scan_listings`, 101,485 rows) and 1 MB of silver. That is now the largest per-scan cost; keeping listings only in silver Parquet and querying them from there would remove it if disk becomes a problem.
- Addon silver, DuckDB and the manifest are not one atomic write, like TSM collections.
