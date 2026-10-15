# Brownstone design

How the system is built. Rules and their rationale live in `requirements.md`; this document covers structure, data contracts and extension points.

## Data flow

```text
TSM CSV ──download──▶ bronze (exact bytes + manifest JSON)
        ──normalize─▶ silver (validated Parquet, one per collection)
        ──load──────▶ DuckDB market_snapshots (deduplicated analytical snapshots)
        ──rank──────▶ gold (CLI screening CSV/Parquet per collection)

SavedVariables .lua ──copy──▶ bronze (gzip of the exact bytes, stored once per SHA-256, + manifest JSON)
        ──parse/check─▶ scans (Lua subset parser, house evidence, stack unit prices)
        ──silver──────▶ per scan: _scan, _listings, _items and, if complete, _prices Parquet
        ──load────────▶ DuckDB addon_scans + scan_listings + scan_items + scan_metrics; market_snapshots for complete scans only

saved Wowhead page ──archive─▶ data/recipe-sources (exact bytes once per SHA-256 + manifest)
        ──extract─▶ recipes and items ──select─▶ catalog TOML (config/recipe-selections/*.toml)

catalog TOML ──load──▶ crafting / action_board ◀── price_observations (DuckDB)
```

CLI collection bytes are written before validation, so failures stay inspectable; addon previews and stale reviewed imports write nothing (DATA-01/ADDON-06). DuckDB writes are transactional, but silver, DuckDB and gold together are not one atomic operation (see `status.md` for recovery).

## App and modules

`nicegui_app.py` owns loopback entry, URL place/source/Today-tab/view state and lifecycle;
`launch_nicegui.py` owns native launch, browser fallback and the path/byte fingerprint of
both entries plus brownstone/views Python sources. Reuse/restart requires authenticated
launcher state; the fingerprint has no dependency on a removed entry.

| Place | View | Job |
| --- | --- | --- |
| Today | nicegui_today | Plan cards/table, shopping, sell, queue, extras, This session |
| Team | nicegui_team | Roster, progression, hiring |
| Market | nicegui_market | Item search/chains, movement, removals, flood evidence |
| Stock | nicegui_stock | Captured holdings, listed value, manual targets |
| Data | nicegui_import | Explicit addon review/import |

`views/nicegui_theme.py` owns light tokens, chips/badges/banners/tiles/cards/dialogs/empty states.
`views/today_rows.py` projects framework-free rows/wording. The header wraps place tabs,
separates Data, and offers source/page information and Today settings. Native text selection
is enabled. Evidence lives in dialogs/disclosures; rules are UI-07/08.

Per-tab state (`app.storage.tab`) holds Today choices/refill/preferences/ticks per source,
Team character/window per source, and one import review invalidated by source/config change.
Import results replace review; drops refresh file evidence. Place/source/tab are URL-backed.
Settings drafts reopen from saved values and persist only on Save.

Dependencies point inward: entry → views → brownstone; brownstone never imports display
frameworks/views. Calculation modules take supplied data/clock and do not download.

| Modules | Responsibility |
| --- | --- |
| config, markets | Typed Source, local overrides, MARKET_KEYS/derived ID/scope |
| sources, normalization, pipeline | TSM download/validate/collect; shared addon preview/import |
| scans, scan_details, variants | Lua parsing, validation, references, variant identity |
| addon_records, character_snapshots, journal, sales, professions, characters | Non-scan lifecycle and scoped projections |
| scan_inputs, drop_files, import_review | Drop inventory, review rows/status, per-file imports |
| storage, metrics, item_names | Migrations, facts/reads, versioned metrics and labels |
| analysis, scan_changes, removed_listings, flood_signals | Browse/CLI screening and scoped market comparisons |
| crafting, action_board, skillups, recipe_graph | Catalog validation, routes/ranking, bands, team graph |
| recipe_import, recipe_catalogs | Saved-page CLI generation; selection-based discovery/learning labels |
| progression, hiring, session_options, farming | Reach costs, hire comparisons, This session composition |
| today*, stock, watchlist | Funded plan/loading/evidence/settings, holdings/targets, retained hit engine |
| freshness, money, navigation | Freshness, copper display, questions/experience order |
| beta_report, beta_evidence, beta_markdown | Isolated evidence checks and private report |
| cli | collect/import, recipes, beta-report (`python -m brownstone`) |

## Data contracts

| Entity | Identity | Notes |
| --- | --- | --- |
| Market | `game_version, region, scope, realm, server_type, faction, environment` → derived `market_id` | One auction house. Crafting also needs the source's `rules_version` |
| Source | `source_id` (+ `provider`, `source_url`) | One feed observing one market; a `[[sources]]` entry; names its data folders |
| Collection | `snapshot_id` (UTC time + random suffix) | Bronze CSV + manifest with source and market identity; manifest records `analytical_snapshot_id` |
| Analytical snapshot | source + upstream scan time + SHA-256 | Repeated identical content from the same source reuses the earlier ID |
| Price observation | analytical snapshot + source + market identity + item ID + variant/resolution | Integer copper: `min_buyout, market_value, recent_value, historical_value` |
| Item name lookup | `game_version, item_id` | `item_names`: label, `origin_rank` (observed 1, catalog 0), `observed_at`, evidence reference. Label policy is DATA-02; no market/source/rules identity is relaxed for prices or supply |
| Addon scan | `source_id, scan_id` → `snapshot_id = <source_id>:<scan_id>` | `addon_scans`: status, `partial`, `priced`, times, counts, `nonexact_stacks`, client, house evidence, scan and file SHA-256. Its import manifest lists every scan with an outcome (`imported`, `duplicate`, `partial (not priced)`, `empty`) and counts `already_imported`, `remaining_unimported` (including unselected scans) and `other_house` (file scans from another auction house); `scan_id`, `updated_at` and `analytical_snapshot_id` name the newest complete scan, and status is `no_complete_scan` when there is none |
| Listing | `source_id, scan_id, listing_index` + market identity | `scan_listings`: `item_id, item_name, quantity, buyout` (whole stack), `unit_buyout` (exact only), `unit_buyout_ceil`, `min_bid, bid, complete_info`, plus nullable ADDON-09 fields and ADDON-08 variant/resolution |
| Scan metrics | version + source + full market + scan/snapshot + item/variant/state | `scan_metrics`: integer price/count facts and share/coverage numerators; rules in ADDON-10. `metric_key` is canonical JSON of every identity field, preserving nulls without hash/delimiter collisions; primary key enforces uniqueness |
| Scan item reference | source + scan + item ID + full market identity | `scan_items`: first-pass observations, separate pass values and effective-field provenance; `effective_scan_items` resolves references under ADDON-09; `_items.parquet` in silver; legacy scans have no reference observations |
| Catalog | `game_version, rules_version, catalog_version` | TOML generated from a selection file and one saved page (CRAFT-08). Header: `source_url`, `source_sha256`, `verified_at`, optional `page_coverage` (CRAFT-08). Items: role, Wowhead URL, optional unit `vendor_price_copper`, `vendor_quantity` (default 1), `vendor_bundle_price_copper` (exact unit × quantity) with `vendor_price_source_url`, `vendor_verified`, `availability`. Recipes: inputs, `output_quantity`, `required_skill` (absent when Wowhead's 9999 sentinel, CRAFT-08), optional `skillup_colors`, `learned_from`, `training_cost_copper` (CRAFT-08), Wowhead spell URL, `verification_url`, `evidence_sha256`, optional `output_quantity_verified`, `availability` |
| Recipe selection | file name = catalog name | `config/recipe-selections/<catalog>.toml`: catalog header fields, finished `[[recipes]]` (with optional overrides), `[recipe_defaults]`, `[[items]]` vendor evidence and notes, including positive `vendor_quantity`; importer divides the page buy price exactly and retains the bundle price (CRAFT-08) |
| Recipe source page | SHA-256 | `data/recipe-sources/wowhead/<game>/<profession>/<sha16>.html` + `.json` manifest: page URL, `saved_at`, `archived_at`, original file name |

### Schema migrations

`storage.SCHEMA_VERSION` and ordered `MIGRATIONS` are authoritative. `upgrade_database`
backs up the starting file before pending idempotent steps; record each version after its
steps complete. Newer schemas refuse. DuckDB column-add/update cannot reliably share one
transaction, so interrupted upgrades must replay. Add numbered `_migrate_to_N`, register
and bump version; do not edit frozen DDL. Nullable legacy fields preserve original evidence.

| Version | Current schema contribution |
| --- | --- |
| 1 | Initial market snapshots |
| 2 | Source/market identity split |
| 3 | Addon scans and listings |
| 4 | Explicit environment and legacy cutover adapter |
| 5 | Version/item name lookup and named read views |
| 6 | Variant identity, scan items, capture availability |
| 7 | scan_metrics frozen DDL; derived initialization outside migrations |
| 8 | Item-pass/effective-reference fields and view |
| 9 | Nullable scan machine, no backfill |
| 10 | Character snapshots/slots |
| 11 | Raw character journal |

Pipeline upgrades existing databases; explicit import creates one if needed.
Preview never creates/migrates. `load_snapshot` refuses old schemas. Manifests remain raw:
`markets.upgrade_legacy` adapts pre-split/environment fields on read, retaining explicit values.
`completed_snapshots` filters source/all MARKET_KEYS and chooses observation time. Legacy
environment uses migration 4's frozen 2026-11-04 00:00 UTC collection boundary (Forever before
that boundary is beta; others live; missing listing times use parent scan, missing parent time live). IDs/hash/history never relabel on reimport.

Named views preserve numeric/base fields, replacing labels only through DATA-02. Compare uses
scan's loaded price/listing name first, lookup next, Item ID last. Lookup joins only game/item
(one-to-one), never prices/supply. New imports update name candidates in their transaction;
validated catalogs seed on upgrade/import (including duplicates)/app startup, without creating
DB for catalogs alone. Bad catalogs warn/exclude; numeric depth/craft readers retain base tables.

### Format-4 item pass

The addon appends the finished listing scan before starting its transient request queue. Only
`item_pass` in that saved table changes afterward; queue/cursor/pending IDs never enter
SavedVariables. Pass status `running` after an interrupted reload is valid evidence, not a
resumption request. Capture bounds and lifecycle policy live in ADDON-09; exact saved fields and
counter semantics live in `addon/README.md`.

`scan_details.item_frame` retains first-pass observations. `pass_frame` validates metadata and
separate pass rows; `reference_frame` joins within one scan, preserves both sets of values and
records fields effectively filled by the pass. The pipeline checks all reference IDs against
this scan's listings before writing. `_items.parquet` contains first-pass, pass and provenance
columns. `effective_frame` is the in-memory equivalent of `effective_scan_items` (a test compares
the two); a pass row repeating a first-pass value is rejected; Today reads
that view with the unchanged source/full-market/scan/snapshot predicate. Other item-level/stack
readers should use the same view. Format-4 availability adds `item_first_available`,
`item_pass_added`, `item_effective_available` and pass counters; existing `item_available` remains
first-pass availability. Formats 1–3 keep their previous availability shape and null provenance.
Mixed 1/2/3/4 files share the same exact-byte archive and canonical scan-ID/hash deduplication.

## Scan import preview

pipeline.preview_scans returns ScanPreview exact bytes/resolved config/parsed records/validated
summaries/known state; new_ids derived. Missing/old scan tables mean no known scans, never upgrade.
Bounded _read_scan_bytes and shared prepare/select/check/listing/hash helpers implement ADDON-06.
Validate references/types/unique membership/duration; aggregate availability. CLI validates selected
scans only; preview checks all with per-scan house mismatches excluded from new_ids.
Reviewed import recomputes bytes/config/known state, rejects unknown/empty/imported selection,
rechecks under writer before archive, then consumes in-memory bytes. Explicit import creates/upgrades.
_save_collection preserves bytes/manifest; _load_collection is shared transaction. _file_scan_state
classifies saved exact-hash/other-house/remaining, unselected invalid remains. import_guidance protects
subsets. Data uses import_review summary/action/details and one source/config-bound review; results
replace it, errors discard it. Best-effort reads and non-atomic bronze/silver/DB limitations persist.

### Multiple input files (STORY-037)

- `Source.machine` is required for addon inputs, validated by `drop_files.validate_machine`. `Source.drop_folder` is optional and accepted by `read_sources` only through local overrides; both paths resolve relative to the project. The configured data directory cannot be inside the drop folder. Rules and cleanup decisions are OPS-03.
- `brownstone/drop_contract.json` is the single naming/pattern source consumed by Python and PowerShell, including UTC format strings, filename template, and shared valid/invalid examples. The JSON is included as Python package data. The PowerShell harness runs without Pester through pytest where PowerShell exists; macOS reports an explicit skip, Windows CI executes it.
- `scan_inputs.InputFile` holds path, machine, UTC drop time, per-file `ScanPreview`, error or ignored reason. `InputPreview` includes the full inventory and resolved configuration. `preview_inputs` opens no ignored file, writes nothing, and isolates read/validation/conflict errors. `latest()` includes unreadable final drops so an older successful drop cannot be mistaken for the latest one.
- `import_inputs` recomputes the inventory, configuration, bytes and known state before any writes. Selected files import independently; later identical scans deduplicate against earlier committed files, while other unexpected duplicate-state changes invalidate that file. Each file then uses the existing reviewed importer and final writer check. This is a sequence of per-file transactions, not one batch transaction; earlier successful collections survive a later failure.
- Batch selections identify files by full path because scan IDs repeat across files. CLI `--scan` limits matching IDs in every file. The page selects files and imports their matching scans, including partial scans and duplicates; another-house entries remain unimported. `include_duplicates=True` allows an explicitly reviewed duplicate-only file to obtain its own collection; the single-file UI retains its new-only selection contract.
- Bronze manifests add `machine` (configured local name or parsed drop machine) and `original_file_name`; existing `source`, SHA-256, byte count, scan outcomes and remaining/other-house counts remain. Machine is also added to new silver scan rows and stored `addon_scans`. Byte blobs may be shared; collection manifests never collapse files. Duplicate import preserves the original stored machine and never guesses a historical one.
- `file_rows` and `latest_rows` provide common CLI/page cleanup evidence. `fully_imported` is true only for a readable nonempty file whose every scan and character snapshot has a matching stored hash and no house mismatch. Ignored names, parse errors, conflicts and other-house scans cannot give cleanup permission.
- CLI `--preview` is read-only. With a drop folder, ordinary addon import lists every file and imports only those with new scans (or, with `--scan`, those holding the requested IDs), so a repeated run never re-archives imported files; `--input` keeps the explicit single-file path and takes its machine from a drop name, otherwise from `machine`. The page keeps file status, per-file scan tables, UTC provenance and each machine's latest-drop state in Details, then refreshes that evidence after import. The fresh review resets selection to its new-file default.

### Character evidence

ADDON-11/12; fields: addon README. Format 6: scans (1–4), snapshots, sessions/shared sequence,
journal/diagnostics/errors. Latest: capture then sequence. Tuples retain nils; no analytical prices.

- scans.read_addon_records parses once; addon_records dispatches validation/hash/house/storage
  to character_snapshots/journal; shared reviewed transactions/outcomes.
- ScanPreview non_scans/summaries/known/mismatches holds non-scan state; new_record_ids controls
  import. Snapshots are compatibility projections. Matching non-scans import;
  --scan limits scans only. scan_inputs checks type/ID commits; writer rechecks.
- Snapshot canonical sorted JSON hashes retain historical values; skills subtree and all journal
  use typed keys (numeric/string distinct).
- Schema 10: source/ID/full MARKET_KEYS/character/realm/faction/kind/UTC, nullable BIGINT gold/machine,
  collection/file/content hashes/raw JSON. Slots: source/ID/container/slot, nullable item/count/link.
  Schema 11 journal: source/entry/full market/character/family/time/machine, collection/file/content
  hash/raw JSON. Collection transaction; no journal silver export.
- Manifest non_scan_records: type/ID/hash/outcome/summary; snapshots is the older-reader subset.
- character_snapshots.latest_data returns scoped readable bags/bank/history/all observations;
  professions.latest_data adds journal, trustworthy lists/seen-crafted. Ordered SQL selects small
  records/list name/ID-hash/order; skips stale lists, fetches winners by entry_id, applies newer
  profession_rank/time. Parse/pass winners only. characters.build_characters
  renders Team; latest/preview/active_auction_rows feed Import. Modern skills win names,
  never fill legacy holes.
- Merchant lists: raw vendor journal, no migration; journal.merchantItems/merchantRead mirror
  trainers (`sameMerchant` ignores position). beta_vendor projects source/full market/rules, entry/time and catalog comparisons;
  beta_markdown renders vendor prices. Confirmation: CRAFT-08.
- `sales.load` reads auction/bags/mail once with source/full market predicates and scoped scan names;
  `sales.project` is pure, reusable by the future ledger: post confirmation, arrival/multiplicity mail
  identity, invoice matching, returned mail, per-character/item units/net/newest sale/expiry run.
  Lua tuples retain string numeric keys. Collected invoice identity keeps observed header money
  separately from invoice gross/deposit/cut/net (rules: UI-14); raw storage is unchanged.
  `today_loading` passes `sales_data` into `build_today` for Today; `sales.combined` attaches scoped
  display evidence before `today_confidence` labels the selected plan. Today v12, no ranking/sizing
  changes. Sell/table/card share `today_rows.sales_text`. Market's item-only `item_summary` loads
  per-character outcomes and scoped unidentified count; `nicegui_market.own_sales` renders them.
  `beta_report` supplies validated matching-house journal and parsed scan names to the same projection;
  `beta_markdown` lists attempts/outcomes including money evidence. No schema/addon changes.
- `scan_timing` isn't imported; `beta_report.scan_attempts` reports it.

API shape evidence: [Classic trade skill](https://github.com/Gethe/wow-ui-source/blob/classic_era/Interface/AddOns/Blizzard_TradeSkillUI/Vanilla/Blizzard_TradeSkillUI.lua),
[Classic craft](https://github.com/Gethe/wow-ui-source/blob/classic_era/Interface/AddOns/Blizzard_CraftUI/Vanilla/Blizzard_CraftUI.lua),
[modern auctions](https://github.com/Gethe/wow-ui-source/blob/live/Interface/AddOns/Blizzard_APIDocumentationGenerated/AuctionHouseDocumentation.lua),
[Classic auctions](https://github.com/Gethe/wow-ui-source/blob/classic_era/Interface/AddOns/Blizzard_AuctionUI/Classic/Blizzard_AuctionUI.lua).
These establish shapes, not Forever support (modern indexes 1-based; legacy saleStatus position 16,
value 1 means sold awaiting delivery); beta raw evidence remains required.

## Scan comparison

- `storage.scope_predicate` supplies the source and full `MARKET_KEYS` predicate to price, depth and comparison reads.
- `scan_changes.eligible_scans(db, config)` reads the selected source's completed, non-partial, priced `addon_scans` rows, ordered by finish time and scan ID descending. Finish times are normalized to UTC independently of DuckDB's session timezone.
- `compare_scans(db, config, first_id, second_id, item_ids=None)` validates distinct eligible IDs and orders them chronologically. DuckDB reads `scan_metrics` facts per exact identity, scoped by source, market, scan ID, snapshot ID and metrics version. `market_snapshots` and a name-only `scan_listings` aggregation provide labels, with the same scope; neither supplies numeric metrics. A full outer join returns only item aggregates to Python, never raw listings.
- The result carries earlier/later scan metadata, their time gap, shared `items`, `new` and `vanished`. Each row has item ID/name, earlier/later metric dictionaries (minimum buyout, market value, listings, units), later-minus-earlier changes and a changed flag. A missing side is `None`; unavailable prices and changes are `None`, with integer copper for all valid prices. Optional item IDs filter every list; an empty list matches nothing.
- Market composes this comparison through `market_explorer.scan_movement`; UI-06 supplies its retained comparison contract.

### Removed listings (STORY-027)

Rules live in `requirements.md` → UI-10; raw time-left capture remains ADDON-09.
`removed_listings.scan_pairs` uses `scan_changes.eligible_scans` without bridging eligible scans.
`compare_pair` validates adjacency and reads only `scan_listings` through `scope_predicate`, scan ID
and snapshot ID. SQL aggregates exact identities/quantities/whole-stack buyouts/time-left buckets,
then reuses `scan_changes._MATCH_SQL` for legacy compatibility. Item filters retain every identity
of each selected ID. Python compares key multiplicities and assigns the shortest earlier buckets
first, returning integer counts/units plus matching evidence and excluded no-buyout counts.
There is no migration, persistence, price path or forecast. `top_removals` reads only the newest
qualifying pair and catalog-chain IDs; `item_history` retains skipped gaps and at most ten qualifying
pairs. UI-11 and Today share `qualifying_pairs`; `recent_comparisons` reads the scan list once.
`market_explorer.load_explorer` adds the small top-list projection. `item_removals` opens a
read-only connection only when `views/nicegui_market.show_item` opens the item page. Shared theme
cards/badges and expansions show evidence and keep identities separate, including noncatalog items.

### Flood signals (STORY-064/072)

Rules and config defaults live in `requirements.md` → UI-11. `flood_signals.signals` reads
`scan_metrics` under `scope_predicate`, exact scan/snapshot identity and metrics version, reusing
`scan_changes.eligible_scans`, its loaded-name query and `removed_listings.qualifying_pairs`. Item-ID
filters retain all variant states to check ADDON-08's pure-base compatibility. The newest eligible
scan supplies counts and largest-stack numerator/denominator; earlier windowed scans supply the
daily points grouped by the UTC date of `finished_at`, then their median. Each signal retains
both priced-day and priced-scan counts; at most ten qualifying adjacent pairs supply comparable lowest-buyout churn.
All monetary arithmetic uses integer copper; ranking ratios use exact fractions. No migration,
write, price path or seller inference. `market_explorer.load_explorer` reads only catalog-chain
signals for the two top lists; `item_floods` opens a read-only connection only when an item page
opens. `views/nicegui_market.py` uses shared theme badges/chips, links and short-history explanations.

## Crafting calculation

- `basis_prices(observations, basis)` turns observed prices into buy and sell unit price maps (CRAFT-04).
- `evaluate_recipe(catalog, recipe_id, buy, auction_cut, sell)` chooses each input's cheapest route recursively. It returns:
  - direct choices
  - the chosen-route shopping list
  - the all-craft expansion
  - cost, net revenue, profit, margin and break-even
- `Decimal` handles the auction-cut rounding.
- `today_data.read_today_evidence` supplies scoped ADDON-10 listing/unit metrics separately
  from costs/ranking; all reads use source, full market, scan/snapshot and variant identity.
- Catalog discovery supplies `catalog_id` from the selection-file stem. Standalone catalogs default to a header identity (`game_version:rules_version:profession:catalog_version`); combined inputs must have unique identities. Rows carry `catalog_id`, `recipe_id` and `profession`, and `catalog_for_row` resolves details to the original catalog.
- `rank_catalogs` ranks qualified compatible roots once with the shared policy. Load the union
  of catalog item IDs in the same scoped analytical snapshot (CRAFT-05).
- `rank_recipes` checks that the catalog, market and snapshot are compatible, then:
  - evaluates every finished output under both bases
  - labels and sorts the rows (CRAFT-05)
  - isolates per-recipe errors so one bad recipe doesn't hide the others


### Team recipe graph (STORY-015b)

Rules live in CRAFT-12 (`requirements.md`). Framework-free `recipe_graph.RecipeGraph(catalogs,
makeable, market)` indexes compatible catalogs once for the selected market, retaining recipe
origins and item-conflict warnings. `for_recipe(catalog, recipe_id, buy_prices)` returns a
catalog-shaped projection: shared `items_by_id`/`recipes_by_id` and a deterministic
`recipe_for_output` for the root's reachable inputs. It selects competing eligible makers with
`crafting._craft_route`; `crafting._cheapest_route`, `evaluate_recipe` and `material_plan` walk
that projection unchanged. Selection runs separately for each price basis. Expansion errors remain
isolated per board recipe. `label_routes` attaches origins/makers and blocked-cross-route notes to
the calculated explanation; it adds no costing path.

`today_characters.team_makeable(catalogs, scoped_data)` supplies catalog-qualified maker names
using `recipe_status`; calculations never load character records. No data returns `None`, which
keeps `rank_catalogs` on its original catalog-local path. An evidence map with no eligible makers
still permits local routes and supplies blocked-material labels. `catalog_for_row` always resolves
the original catalog, while route details use `route_catalog` to obtain the same projection.
Today retains the board choices for sizing and queue postorder. Team routes its skill-up entries
through the same graph; This session expands those selected steps; Market uses it for finished and
unvalued intermediate recipe details. The NiceGUI views show maker/profession, catalog warnings
and Queue's uncharged-mail note. Session identity includes Today version so the existing reset path
discards obsolete choices and ticks.

## Recipe import

`recipe_import` extracts saved Wowhead `listviewspells`/item data, validates selection/game/
profession, selects single fixed-yield nonseasonal makers, expands intermediates and generates
TOML through `prepare_catalog`. `archive_page` preserves exact bytes/provenance; changed values
are listed by the CLI and require the CRAFT-01/08 version policy. No downloads.
`recipe_catalogs.find_catalogs` discovers tracked selections, loads generated catalogs;
`parse_catalogs` isolates malformed entries. `profession_title`, `PROFESSIONS` and
`learning_label` supply team metadata/verified code labels. CLI shares CONFIG_DIR/ARCHIVE_DIR.
Tests compare generated tracked catalogs against offline saved-page extracts.

## Switching to WoW Forever

Configure house/server_type/faction/explicit environment, no realm; DATA-03 derives ID.
Use addon provider with scan_path/machine/scan_evidence and optional local drop folder.
Generate compatible profession catalogs through `python -m brownstone recipes` using manually
saved Forever pages and tracked selections. Other permitted feeds need an adapter to the same
price contract. No changes to crafting/Board/views should be needed; otherwise a design defect.

## Quality gates

Pytest offline branch coverage >=floor, Ruff complexity <=10 and mypy run locally/CI from
pyproject/lock. Mypy covers brownstone, app/launcher, NiceGUI views and today_rows. Source is
a TypedDict; other records remain plain dictionaries.

## Known design debt

- `scans.parse_lua` retains the existing C901 exemption (complexity 13); splitting its token loop
  adds per-token overhead. Revisit with measurement, never add new exemptions.
- Reviewed imports parse twice; drop rechecks retain bytes/inventory in memory. Manual cleanup
  bounds inventory; no bounded-memory claim.
- Offline tests mock network downloads; configuration/upgrade errors retain partial coverage.
- completed_snapshots reads all manifests on page load; scans retain listings in DB and silver.
- Bronze/silver/DB/gold/manifest writes are not jointly atomic; Drive local rename does not prove
  remote sync completion. Recovery/replay limitations live in status.

## Variant-aware scan reads (STORY-023)

`variants.ITEM_KEYS` defines the within-scan grouping (`item_id, variant_id, variant_state`); null-safe joins preserve base/unresolved observations without pooling them with variants. `scans.item_prices` applies the same keys to names, unit-weighted percentile ranks and minimum prices. `compare_scans` groups/joins on these keys with null-safe variant comparison. Legacy null state shows as `legacy`, matching the other scan's `base` row only when that scan saw only base listings for the item ID (ADDON-08). `item_names.remember_observed_names` takes names only from base or legacy rows. `analysis.rank` returns variant identity with each row. Market and scan comparison expose identity/state alongside names.

`price_observations` retains their catalog item-ID return shape. Default reads accept base rows and historical null fields, but exclude format-3 unresolved/variant rows; explicit `variant_id`/`variant_state` arguments select an exact variant or unresolved pool (never legacy null-state rows) within the same full market/source/snapshot scope. Catalogs have no variant selectors today, so a variant-only output stays missing prices instead of inheriting a different suffix's price. No crafting rules-version check is relaxed.

Offline Lupa/WoW stubs test emitted scans across API paths/optional fields/manual lifecycle.
Python coverage excludes Lua branches and does not replace beta API/tooltip checks.

## Market metrics layer (STORY-024)

The only business definitions are ADDON-10 in `requirements.md`. `metrics.calculate_metrics` uses
Polars group/window operations over listing quantities, without per-unit row expansion. Raw
validated frames represent one scan; stored frames automatically group on every source/market/scan/
snapshot/item identity field. Partially supplied scope is rejected rather than silently discarded. The import
price adapter `scans.item_prices` selects this calculator's minimum/25th percentile into the established
price contract. `storage.load_scan` calls `metrics.store_scan_metrics` in its caller's transaction.

`metrics.rebuild_scan_metrics(db)` owns one transaction, recalculates from `scan_listings` joined to
eligible parents on every `SCAN_KEYS` field, upserts canonical keys, removes obsolete version-1 rows,
and records `schema_info.metrics_version` only on success. Upsert before deletion avoids DuckDB's
same-transaction indexed delete/reinsert limitation. Errors roll back facts and completion together.
It takes no clock and writes no run timestamp. Initialization is outside frozen migrations; a missing
completion marker retries even if the schema upgrade already finished. `upgrade_database` still
backs up the starting schema before DDL. Do not call rebuild inside another transaction.

For an already upgraded connection, manual rebuild is:

```python
from brownstone.metrics import rebuild_scan_metrics
rows = rebuild_scan_metrics(db)
```

`read_scan_metrics(db, config, snapshot_id)` returns every exact item identity and nullable prices,
counts, exact numerator/denominator shares and coverage; None means an ineligible scan. It emits no
seller strings. `units_below_price` takes an exact item/variant/state and positive integer threshold.
`scan_changes` preserves the existing name and comparison policies. Stored addon prices remain for
Market/CLI screening/crafting and TSM compatibility; their numeric calculation is shared, not duplicated.
Rebuild preserves these historical observations rather than rewriting them.

The rebuild currently materializes all eligible listings locally in Polars; no streaming/bounded-memory
claim is made. Derived metrics are not automatically invalidated by unsupported direct SQL edits to
observations: explicitly rebuild after changing stored evidence. Manual writes bypass the structured
key calculation; imports/rebuilds are the supported writers.


## Watchlist contracts

Rules: requirements → Watchlist. `watchlist` validates Entry, explicit money targets and atomic
source-local JSON; invalid/unreadable existing files refuse replacement. `build_watchlist` is a
pure clock-supplied projection. `read_watchlist` composes latest_snapshot,
today_data.read_skillup_market and metrics.units_below_price under base/legacy full scope.
Hit-name choices use scoped observations/compatible catalogs, not another source's lookup.
NiceGUI Today/Import render hits without changing host calculations; no standalone editor.

## Today contracts

Rules live in `requirements.md` → Today. Calculations are framework-free.

- **Loading.** `today_loading.load_today` picks the latest scoped snapshot, opens the database
  read-only, resolves funds and returns the `build_today` arguments with the caller's clock;
  `load_today_characters` reads `professions.latest_data` and keeps a failure for the UI to explain.
  With `holdings=True` (Today only) the loader reads `character_snapshots.latest_data` once and passes
  `team_holdings.holdings`'s totals, names, captures and location units as `holdings_data`;
  calculations never load captures. A read failure plans without holdings and returns
  `holdings_warning`, which Today shows. Stock supplies its already-read holdings instead.
  Only Today passes `flood=True` (others get `None`): one `flood_signals.signals` call supplies
  `flood_evidence` for catalog/extra and gathered IDs, which This session reuses. Each signal
  keeps its compatible earlier identity per qualifying pair. After selection,
  `load_today_removals(config, plan)` reads shown output IDs via `removed_listings.recent_comparisons`;
  `today.apply_removals` attaches confidence and rebuilds the complete Queue.
- **Evidence.** `today_data.read_today_evidence` returns `(observations, listings, metrics,
  vendor_sell_prices, stack_sizes)` for one source and analytical snapshot: base/legacy listings as
  `(quantity, full buyout, unit ceil)` tuples per item, ADDON-10 metrics and effective scan vendor
  and stack references (stack sizes for every referenced item, listed or not). Missing listing support is `None`, distinct from an eligible scan's `{}`. No seller
  strings enter this path; reads keep source, every MARKET_KEYS field, scan/snapshot and variant state.
- **Settings.** `TodaySettings` holds validated integer settings, the nullable character
  `(name, realm, faction)`, `gold_override`, `include_unknown` and `post_duration_hours` (older files load with defaults).
  `today_settings` persists one atomic JSON file per source. `today_funds.resolve_funds` turns the
  scoped projection into effective settings plus summary and notes, without persisting the balance.
- **Eligibility.** `today_characters.project_recipes` matches catalog recipe IDs against the
  projection and returns per-recipe status, team names and catalog checks; `filter_candidates` runs
  before sizing and counts excluded reasons. `PROFESSION_SKILL_IDS` carries the documented map.
- **Plan.** `build_today(catalogs, observations, market, snapshot, settings, *, now, listings, metrics,
  vendor_prices, max_age_hours, auction_cut, choices=None, refill=True, character_data, flood_evidence, holdings_data)` returns
  capped `craft`, `buy`, `sell` and `below_vendor` lists, hidden and remaining counts, shopping total,
  freshness, `choice_limits`, `dropped_choices`, `queue` and `today_version`. `Ladder` holds prefix
  units/costs for whole-stack quotes; binary search finds the affordable bound and only bound/listing
  breakpoints are quoted for rows using no held item. A row using a held item compares its bounded
  (1–1,000) feasible sizes exactly, including all holding-depletion boundaries; this preserves correctness
  for nested/multi-yield intermediates without expanding units or walking listings.
  `today_holdings` attaches routed per-unit intermediate leaves, reduces preorder branches top-down,
  and reserves held counts alongside listing offsets. Batch value includes held opportunity cost;
  funds reserve only purchased gold. After selection, location allocation consumes materials before
  assigning leftover held outputs, preventing a post from also using reserved materials.
  Each selection reserves funds and listing offsets; no per-unit expansion or
  per-recipe SQL. Craft rows keep board routes, `purchases`, `intermediate_steps` (chosen craft
  branches only), `plan_order` and `feasible_size`. `today_confidence.confidence` labels the funded
  plan afterwards. Today passes optional sell-price caps through `rank_catalogs`/`rank_recipes`'s
  cautious sell map; their buy map is unchanged. `evaluate_recipe` applies the catalog-local vendor sale ceiling (CRAFT-04), retaining `vendor_price_cap_copper` and `vendor_capped` (the ceiling lowered the value) for presentation; Today v13 also caps the post price. Today v14 splits at `Ladder.units_at_or_below`; `_capped_quote` may swap a part-used last listing for the vendor. Peaks add capped segments' first sizes. `today_warnings`
  selects base/legacy signals and carries caps/evidence into Sell and Queue posts. The NiceGUI view
  reuses `session_signal`/`CROWDING`/`OVERSHOOT` badges with on-demand removal evidence.
  `craft_details(row)` projects held/purchased materials and the batch's retained `reserved_steps`
  (or scales original steps when holdings are absent). Sell retains owners and separate held value.
  After held-output allocation, `deposits.auction_deposit` adds Sell's nullable `deposit_copper` and
  `post_duration_hours` (Today v11), taking stack size from `stack_sizes` so unlisted outputs still get one. Queue post lines retain these fields; its nullable
  `deposits_to_post_copper` sums the complete post list. Rules remain in requirements → Today.
  Queue take/mail lines and held post annotations survive `apply_removals` rebuilding;

  `purchase_uses(crafts)` groups purchased units per item/route and output (Shopping list For);
  `session_queue` projects reserved shopping, route steps in postorder and posts without re-quoting.
- **Session.** `today_session.plan_context` fingerprints catalogs, market, snapshot, settings,
  freshness limit, auction cut, Today version, character evidence and holdings (capture identity/counts, not age); a changed context resets
  choices and ticks. `today_session.queue_with_gold` projects the Queue with transfers using
  `today_funds.recorded_balances` and reserved `craft_details` purchases; `build_today` is untouched.
  Queue tick identity includes these presentation lines, excluding confidence labels (`stable_queue`).

### This session (STORY-063)

Rules live in `requirements.md` → UI-12. `session_options.build_options(db, config, arguments,
plan, window=25)` composes the displayed reserved plan with `progression.build_progression` and
its `estimate_cost` results, using only `today_loading.load_today`'s observations, listings and
metrics. Selected estimate steps reuse `evaluate_recipe`'s team-aware shopping quantities for
cheap-material attribution; no new price query. Loaded `flood_evidence` covers the union
of catalog and farming item IDs, retaining full source/market scope and separate variant identities.
Direct callers without loaded signals retain the standalone signal read.
It returns character sections, annotated copies, per-character craft totals, character level,
`next_steps` (kinds `craft`, `level_profession`, `level_character`, `train`, `nothing`, `evidence`),
per-profession `milestones` and `tier` (`NEXT_TIER` caps/names plus `tier_levels.lookup`),
snapshot/freshness and separate signal provenance; the view turns steps into lines (`step_text`). Craft copies carry `headline_profit_copper`,
`headline_per_craft_copper` and `profit_basis` from the reserved Sell row via `today_session.headline_profit`;
`tier_levels.load` validates the tracked TOML once per composition outside the calculations;
`next_tier` receives its levels and game version as data and returns the requirement source and trainer provenance.
Hiring loads the same table once in `prepare` and uses the lookup in `detail`.
`merge_tier_steps` combines equal character-level/tier/source requirements. The input plan/arguments and Today version
are untouched.
`views/nicegui_today.py` places the toggle above the plan status so it stays put, composes lazily
when **This session** opens, reads Team's per-tab/source
reach window, uses the shared theme and links to Market items and the selected Team character.

### Farming (STORY-065, STORY-074, STORY-075, STORY-077)

Rules live in `requirements.md` → UI-13. `farming.gathered` reads scoped `(record, machine)`
observations, orders by capture/sequence and deduplicates entry IDs. The addon captures only the player's loot messages; matching windows are isolated by machine/login,
and transaction hooks invalidate pending windows. `history` retains qualifying and excluded stretches,
object IDs, integer units/hour and evidence seconds. `valued` uses Today's cautious sell-side prices
and the existing union flood read's base/legacy typical unit price and loaded item label; missing prices
stay unknown. `session_options` adds farming copies to character cards without changing the plan.
`nicegui_today.session_farming` shows the top three, with all rates and stretch provenance in evidence.
`source` retains Creature NPC IDs separately from object IDs; gathered evidence retains the matched
window identity. `stretches` assigns the dominant NPC by distinct windows and `history` adds spot
aggregates alongside the unchanged item rows. `valued` accepts the newest scan vendor prices as data
from `session_options`, values all spot quantities before dividing by summed seconds, and retains
per-item auction/vendor/no-price evidence. Matched loot carries the slot's optional positive
`vendor_sell_copper`; spot aggregation retains the latest loot value per item plus every distinct observed value;
valuation prefers positive scan values and exposes every disagreement. `position_cell` uses distinct matched window positions
and median raw fractions to derive the optional lower-edge `(x, y)` percent cell. `history` accepts
`cell_percent` from the source config and groups spots by map/NPC/cell, preserving item rows.
`coin_windows` matches explicit type-2 slots to guarded same-machine/login money deltas under UI-13;
spot aggregation counts each matched window once. Missing coin remains nullable.
`session_farming` adds position-centre and coin-share columns and vendor disagreement evidence to the
spot table with the shared theme and Classic NPC links. The addon 0.12.4 shared `journal.zone()`
adds nullable raw x/y (including shared vendor context); `journal.lootSources()` adds type, quantity
and cached positive vendor copper. `beta_report.farming_capture` counts capture coverage in JSON
and Markdown. Addon 0.12.6 `journal.lootTarget` matches the guarded target Creature GUID
against odd positions in the saved slot sources and attaches the guarded name/GUID once to the window.
`farming.npc_names` derives a display-only NPC-ID map from the same scoped observations,
newest capture/sequence winning; `history` returns it beside unchanged rate/spot evidence.
`nicegui_today.mob_label` uses it for Mob, Also looted and Spot item values with ID fallbacks;
the Mob column retains its Classic Wowhead link. The beta capture section counts named windows
and lists observed NPC IDs without any captured name. No storage migration, new price query or network work.

## Team contracts

Rules: [CRAFT-11/13](requirements.md#crafting) and [Team character cards](requirements.md#team-character-cards).
nicegui_team reads shared load_today_characters and
load_today snapshot/evidence, using tab/source character/window state. Cards select; reach slider
commits on release. Tiles/reachable recipes lead; steps/history/comparison/provenance on demand.
Without scan, roster remains readable and pricing explains missing evidence.

`progression.team_board` builds team RecipeGraph/Board once, shared across character progression
and `hiring.prepare(shared=...)`. build_progression returns profession rank/max/note/evidenced skill ID, recipes/best,
unlisted counts/freshness; recipe rows retain Today status/learning/profit/reason/confidence and
estimate complete/copper/reasons/per-point steps. Unknown stays unknown.
`progression.choose_best` picks best and the other-band alternative (CRAFT-11) without reordering recipes;
`session_options` retains that recipe identity while projecting its labelled estimate.
Team's empty states use the group skill ID and `hiring.SKILL_IDS`; learning labels use
`recipe_catalogs.learning_label`. Payback and hiring cost disclosures follow Team character-card rules;
new-hire money cells retain hidden copper fields for the shared table's numeric sort.
Attribution uses Today's exact ID/rank matcher; planned_rank changes rank check only.
evaluate_recipe supplies team-aware cautious material costs, including unranked intermediates;
expected_crafts/estimate_cost use exact rational yellow expectations. One skillup_walk/window/cap
and listing ladders are shared across targets, which stop at prefix. Single-craft confidence reuses
Today quotes; no funding/reservation/sales credit or changed Board profit.

Hiring prepare reuses scoped evidence/current board. summaries returns compatible professions,
holders, rank-300 estimate/best/shared rank-one walk; no-catalog/two-primary comparisons separate.
Synthetic hire evidence is unlearned trainer recipes. Own routes use trainer/current-team recipes;
other-profession routes use current team. Summary cost eagerly resolves sort ties; lazy detail reuses
prefixes/tier maker maps. feeds evaluates current eligible Board roots with existing cost walker;
unknown/unsupported baseline never claims savings. Top consuming rows retain total savings and
hire-made material, avoiding nested double count. nicegui_team builds hiring once; first expansion
loads detail, window change rerenders comparison with shared board. Empty characters still allow
hire comparison; absent scans explain. No new price SQL/calculation I/O/Today state changes.

## Beta evidence report

`cli.beta_report_main` selects one addon source → `beta_report.create_report`; its configured
data directory is never opened. Bounded file reader/Lua parser and shared validation/hash helpers
check records independently so one failure cannot hide evidence. `beta_evidence` owns checks/
COVERAGE; `beta_markdown` renders money through money.py.

Only permanent writes are unique ignored work/beta-reports timestamp/UUID report.md/json.
JSON retains every check/ID; Markdown collapses repeated passes and caps ID lists. TemporaryDirectory
contains exact-byte input and fresh import/preview/duplicate roundtrip; check bronze decompression
against original. Empty/other-house fails; unreadable/changing exits 2, failed checks 1, pass/warn 0.

Load boundaries are inferred from account sequence, logout, identity/login changes or decreasing
uptime; GetTime can persist across reload. Missing boundaries can merge loads, missing sequence
fails. Only latest diagnostics exists; journal_errors is account-wide. Nothing reconstructs absent
historical diagnostics. Per-character/source/full-market money chains compare prior after to before;
consecutive readable bags reconcile money/bag deltas using capture/sequence intervals. Missing
read/baseline warns, residual is evidence gap, never interpreted ledger transaction.

Typed JSON sizes are approximate, not Lua offsets. Scan report keeps IDs/times/counts; owned-list
report keeps numeric facts only, excluding names. No raw sellers/mail arguments/recipe payloads
leave report. Previous comparison uses canonical source/type/ID hashes; changed existing content
fails. Coverage confirms observation only, never action success/invoice meaning/completeness.

## Skill-up map contracts

Rules: CRAFT-08/10. `skillups.build_skillups` takes compatible catalogs, N and post-launch toggle,
returning profession groups/placements/errors/bands/direct/raw totals. `material_plan` expands
all N crafts together, with raw_material stop points. Each recipe counts once in profession totals;
bands reference rows without multiplying totals. `coverage_line` supports both catalog generations.
Market uses these bands for catalog-chain context; there is no standalone skill-up page.
`today_data.read_skillup_market` supplies scoped base/legacy observations/metrics for watchlist.

## Market explorer (STORY-055)

Rules live in `requirements.md` → UI-09 (with UI-02/04/06/08, UI-10/11 and CRAFT-03).
`market_explorer.load_explorer` composes `today_loading.load_today`'s scoped snapshot/evidence,
`analysis.browse` (all items, including nonpositive prices), `metrics.read_scan_metrics`, compatible
catalogs, `action_board.rank_catalogs`, `today_characters` and `skillups.build_skillups`. All database
connections are read-only. It adds no price SQL or pricing policy. Finished-output costs/profit/reasons
come from Board rows; intermediates use `crafting.evaluate_recipe` for routes and `material_plan`'s
expanded quantities, retaining no Board profit. Routed nested choices multiply by the recorded craft
count and carry depth. Skill bands combine direct and raw memberships without multiplying quantities.
`item_page` returns all observed variant identities separately, vendor references, catalog-qualified
made-from/used-in rows and team statuses. Catalog-only items remain reachable with unknown market prices.
`item_summary` lazily composes one `item_floods` read (also reused by the Market tab),
`today_loading._load_holdings` and cached explorer character/price evidence. `base_signal` selects
only an unambiguous base/legacy price/signal/metric row; Stock's exact base holdings exclude variants.
`item_farming` values complete histories before filtering item rows and containing spots, preserving
UI-13 denominators and ordering. The item view reuses `session_farming(limit=None)` and its spot/mob
helpers; This session keeps its three-row default. `wowhead_item_url` shares recipe import's game paths.
UI-09 defines the summary, tabs and removal disclosure; home alone renders market-wide lists.
`scan_movement` calls `eligible_scans`/`compare_scans`, retaining exact identities and comparison facts;
UI-09 defines ordering, distinct-item limit and handling of missing evidence.
`views/nicegui_market.py` uses the shared theme and anchor links carrying source, game, Market and
item ID, plus the optional validated origin under UI-07. `views/nicegui_navigation.py` validates
and renders the URL-only return destination; Today updates its page-local link targets and table
anchors when tab/view changes. Standard URL navigation retains browser history and refresh.
Search renders up to 30 item
links after a query; refining the query reaches every observed item. IDs, incompatible catalog versions,
expanded quantities and comparison evidence remain in disclosures/dialogs. No session price cache or writes.

## Stock contracts

`brownstone/stock.py` composes `character_snapshots.latest_data` once, validated per-source
`Entry` targets once, and `today_loading.load_today` once. The loader's optional `item_ids`
adds held/target IDs to compatible catalog IDs in the existing `read_today_evidence` read;
there is no separate price query. Stock selects each location's latest fully readable capture
from scoped observations, preserving excluded-capture counts, UTC time and age. Holdings aggregate
slots by item, character and location; link labels and compatible catalogs supply names without
inferring IDs or categories. `build_stock` is a pure projection with cautious sale values and
`fill` uses `today.Ladder.quote` only for targets. Missing full-fill quotes remain nullable;
buy/wait quantities describe short units, while purchased units and costs include whole stacks.
Rules live in `requirements.md` → Stock.

`views/nicegui_stock.py` uses the shared theme, cached search/chain filtering, disclosures and
page information dialog. The target dialog copies saved entries into a fresh draft on opening;
Update/remove changes only that draft, Save revalidates the current file and atomically replaces
it, then reloads the page. Malformed files are preserved and explained. No schema or Today
version/state changes. Offline coverage: `tests/test_stock.py` and
`tests/ui_trial/test_nicegui_stock.py`.

## Gold ledger contracts

Rules: [UI-15](requirements.md#ui-15-gold-ledger-story-034). `ledger.load` opens read-only,
reads source/full-market journal families money/vendor/auction/mail/loot once and bags snapshots
once, preserving database machine provenance. `ledger.project` is framework-free and deduplicates
entry IDs; `sales.order` orders each character/machine/login. `sales.messages`/`sales.project`
supply inbox identity and seller net copper; `farming.coin_windows` supplies coin matching.
Movements retain one entry ID/delta with allocation parts (seller proceeds and deposit refund),
so invoice splits never duplicate the movement in reconciliation. `summarize` groups parts by
character, UTC day and category; team totals explicitly sum the groups. Snapshot reconciliation
uses capture/sequence intervals and excludes unreadable backpacks; missing baselines leave an
unknown residual. Stock loads this evidence once, below holdings, and displays cached totals,
reconciliation and expandable movements/IDs; a ledger failure shows only in the Gold area. Today and existing Stock/sales
contracts are unchanged. No storage migration, addon capture or price path.
