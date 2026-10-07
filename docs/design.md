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
        ──silver──────▶ per scan: _scan, _listings, _items and, if complete, _prices Parquet
        ──load────────▶ DuckDB addon_scans + scan_listings + scan_items + scan_metrics; market_snapshots for complete scans only

saved Wowhead page ──archive─▶ data/recipe-sources (exact bytes once per SHA-256 + manifest)
        ──extract─▶ recipes and items ──select─▶ catalog TOML (config/recipe-selections/*.toml)

catalog TOML ──load──▶ crafting / action_board ◀── price_observations (DuckDB)
```

CLI collection bytes are written before validation, so failures stay inspectable; addon previews and stale reviewed imports write nothing (DATA-01/ADDON-06). DuckDB writes are transactional, but silver, DuckDB and gold together are not one atomic operation (see `status.md` for recovery).

## Modules

```text
app.py                  Streamlit entry: sidebar, Refresh, view dispatch
views/                  Streamlit only; display, no calculations
  common.py             snapshot loading, freshness display, gold columns
  crafting.py           Action Board and recipe explanation
  today.py              Collapsible settings, funded plan tabs and optional evidence columns
  catalogs.py           Recipe catalogs page: status, one add-or-update flow (live review, then Save)
  market.py             Browse market and Opportunities
  scan_changes.py       Saved addon comparison tables, scan choices and catalog filter
  scan_import.py        Sidebar addon preview, new-scan selection and explicit reviewed import
brownstone/             importable without Streamlit
  config.py             market.toml (+ untracked market.local.toml overrides) → list[Source] (typed, validated)
  markets.py            market identity: MARKET_KEYS, derived market_id, validation, legacy upgrade
  sources.py            HTTP download
  scans.py              BrownstoneScan SavedVariables: parse, validate, house check, unit and item prices
  drop_files.py          shared Windows/Python naming contract and machine validation
  scan_inputs.py         independent input files, reviewed batch import and cleanup evidence
  scan_details.py       format-3/4 reference/pass validation, effective values and local availability counts
  metrics.py            versioned aggregate calculator, transactional rebuild and scoped readers
  variants.py           conservative link parser and canonical item identity (ADDON-08)
  normalization.py      CSV → validated frame
  pipeline.py           run (TSM CSV), read-only preview_scans and shared reviewed/CLI import_scans
  scan_changes.py       Eligible scan IDs and scoped SQL per-item historical comparisons
  storage.py            DuckDB schema and migrations, load/dedup, manifests, scoped price and depth reads
  item_names.py         keeps derived version-scoped labels current on import, catalog seeding and app start
  analysis.py           browse and discount screen queries
  freshness.py          the one staleness policy
  money.py              explicit g/s/c parser and copper ↔ gold display helpers
  crafting.py           catalog loading, expansion, route costs, price bases
  recipe_import.py      saved Wowhead profession page → archive, extract, catalog TOML (no network)
  recipe_catalogs.py    catalogs found by selection file: status, previews and the add/update writes
  selection_files.py    in-place edits of a selection file that keep its comments
  action_board.py       ranking and label policy (versioned)
  today.py              Today v1 prefix ladders, batch sizing, reservation, shopping/sell/aside results
  today_data.py         one scoped read of prices, base/legacy listings, metrics and vendor references
  today_settings.py     validated integer settings and atomic local JSON persistence
  cli.py                `python -m brownstone`: collect or import a source; `recipes` subcommand
launch.py               local server launcher with code-fingerprint restart
```

Dependencies point inward: `app.py` → `views/` → `brownstone`. Domain modules (`action_board`, `freshness`, `money`, and `crafting` apart from reading a catalog file) do no other I/O and take the clock as a parameter. The `dashboard` extra (Streamlit) is needed only for `app.py` and `views/`.

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
| Catalog | `game_version, rules_version, catalog_version` | TOML generated from a selection file and one saved page (CRAFT-08). Header: `source_url`, `source_sha256`, `verified_at`. Items: role, Wowhead URL, optional `vendor_price_copper` with `vendor_price_source_url`, `vendor_verified`, `availability`. Recipes: inputs, `output_quantity`, `required_skill`, Wowhead spell URL, `verification_url`, `evidence_sha256`, optional `output_quantity_verified`, `availability` |
| Recipe selection | file name = catalog name | `config/recipe-selections/<catalog>.toml`: catalog header fields, finished `[[recipes]]` (with optional overrides), `[recipe_defaults]`, `[[items]]` vendor evidence and notes |
| Recipe source page | SHA-256 | `data/recipe-sources/wowhead/<game>/<profession>/<sha16>.html` + `.json` manifest: page URL, `saved_at`, `archived_at`, original file name |

### Schema migrations

- **Versioning.** `storage.py` records `schema_version` in a `schema_info` table.
- **Migrations are frozen.** A fresh database replays every migration, so it is identical to an upgraded one; a test enforces this.
  - Version 1: explicit table, plus the identity columns.
  - Version 2: market/source split. Adds `source_id`, `server_type` and `faction`, moves Classic faction out of the realm slug, renames scope `realm` to `house`, and re-derives `market_id`.
  - Version 3: addon scans. Adds `addon_scans` and `scan_listings`; `market_snapshots` is unchanged.
  - Version 4: adds `environment` to all three observation tables. Stored Forever rows collected before the frozen 2026-11-04 00:00 UTC boundary become beta; all others become live. Listings lack `collected_at`, so the migration uses the parent `addon_scans` row matched by `source_id, scan_id`; a missing/null timestamp falls into live. Beta IDs are re-derived with the suffix instead of blindly appending, making interruption/replay harmless. Only null environments are classified, so already classified rows stay intact. The frozen date cites the official source under Product direction in `requirements.md`.
  - Version 5: adds `item_names`, the `loaded_item_name` SQL macro, and `named_market_snapshots` / `named_scan_listings` views. Backfills both stored price rows and all listings; listing timestamps come from their parent scan matched on source, scan ID and every market key. It changes no observation rows. The table, macro, views and backfill are frozen SQL in `storage.py`; table creation, view replacement and the deterministic backfill (existing winners kept) are replayable. Valid local catalogs seed after the upgrade, outside the frozen observation migration; malformed catalogs of any kind are skipped.
  - Version 6: adds nullable richer listing fields, `variant_id, variant_state` on listings and prices, `format_version, duration_seconds, availability_json` on scans, and `scan_items`. Rebinds named views after column additions (DuckDB binds star projections at creation). Historical rows and hashes are unchanged. Replay is idempotent, with schema-5 backup before the upgrade; fresh and upgraded layouts are tested. Capture and variant rules are ADDON-08/09 in `requirements.md`.
  - Version 7: adds `scan_metrics` and a canonical structured identity primary key. DDL only; no
    calculation is frozen in the migration. `ensure_schema` then calls `metrics.initialize_metrics`,
    also retried by `upgrade_database` when schema 7 exists without the metrics completion marker.
    Eligibility, measures, nulls and seller policy live in ADDON-10 (`requirements.md`).
  - Version 8: adds nullable `pass_item_level`, `pass_max_stack_size`, `pass_vendor_sell_copper` (BIGINT) and `pass_fields_json` (VARCHAR) to `scan_items`. Original columns retain first-pass values. `effective_scan_items` uses `coalesce(first, pass)` for each of the three reference fields; zero is present. Provenance JSON is an ordered list of fields supplied by the pass, `[]` for format-4 items needing no pass value, null for all older formats/historical rows. DDL and view replacement are idempotent; schema-7 backup precedes upgrade. No historical rows or hashes are rewritten.
  - Version 9: adds nullable `machine VARCHAR` to `addon_scans`, with no backfill or change to identities, hashes, prices or listings. `ADD COLUMN IF NOT EXISTS` is replayable. The normal schema-8 backup precedes upgrade; older scans keep null, including after duplicate import. Fresh and upgraded scan layouts agree.
  - Version 10: adds character snapshot parents and slots; the record/storage contract is in
    *Character snapshots* below and capture/clear rules in ADDON-11. Existing observations are unchanged.
  - Version 11: adds raw scoped `character_journal`; contracts are below. Existing tables stay unchanged.
- **Entry point.** `upgrade_database` copies the file to `brownstone.v<N>.backup.duckdb`, then runs pending migrations statement by statement. DuckDB cannot reliably add a column and update the table in one transaction, so every step is idempotent and the version is recorded only after each migration completes.
- **Callers.** The app calls it at startup for whichever source is selected (an existing database only; it never creates one) and the pipeline before its write transaction. Preview itself never migrates; a missing database waits for the first import. `load_snapshot` refuses an outdated schema.
- **Adding one.** Write `_migrate_to_N`, register it in `MIGRATIONS` and bump `SCHEMA_VERSION`.
- **Nullable columns,** so v0.1 databases match fresh ones; validation happens in normalization.
- **Manifests are never rewritten.** `markets.upgrade_legacy` reads pre-split and pre-environment manifests in the current shape. Missing environments use the same collection-time boundary as migration 4; explicit environments remain authoritative. `completed_snapshots` filters adapted records by source and every `MARKET_KEYS` field before choosing the latest observation.
- **Shared identity.** `MARKET_KEYS` includes the derived ID and all seven market fields, including `environment` (DATA-03). Browse, Opportunities, crafting prices, depth, Scan changes and analytical deduplication use the entire scope. `known_scan` retrieves the stable source/scan key, adapts schema-3 records for read-only preview and checks every market key before returning deduplication state; a scope mismatch refuses key reuse. Source IDs and `<source_id>:<scan_id>` snapshot IDs are unchanged.
- **Name read contract.** Schema 5 defines the missing-name check (`loaded_item_name`, which also trims) and resolution once in the named SQL views, preserving every base column and replacing only `item_name`. Browse/search and Opportunities query `named_market_snapshots`. Scan changes keeps each scan's own loaded name (price row, then its listings with lexical ties) and falls back to the lookup, then `Item <id>`, retaining all existing source/market/snapshot predicates. The app seeds parsed catalog labels once per session and catalog contents, through `item_names.seed_catalog_names`, and only warns on failure. Numeric-only price and depth readers still use base tables; crafting/depth displays already name items from their own catalogs. Lookup joins on game version/item ID carry labels only and are one-to-one by primary key.
- **Name writes.** `load_snapshot` and `load_scan` update only candidates from the newly inserted snapshot, inside the caller's transaction. TSM imports and addon collection imports also seed validated local catalogs, including duplicate imports; the app seeds its parsed catalogs when an existing database is ready, so regenerated catalogs become available on rerun. No database is created for a catalog or preview alone. Malformed local catalogs are excluded from seeding and keep the existing UI warnings. Evidence references identify the stored source/snapshot/price or source/scan/listing, or the catalog item's source URL. Winner policy is solely DATA-02.

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

- `pipeline.preview_scans` returns a `ScanPreview` containing exact file bytes, a serialized resolved configuration, parsed records, validated summaries and the relevant existing `known_scan` records. `new_ids` is derived from those records. Missing databases and older schemas without `addon_scans` mean no known scans; preview never upgrades.
- `_read_scan_bytes` implements the bounded descriptor/path read described by ADDON-06. `_prepare_scans`, `_select_scans`, `_check_scans`, `scans.listing_frame` and `scans.scan_content_hash` are shared with CLI import; there is one parser and one per-scan hash format. Validation also checks item-reference types, uniqueness and membership in this scan, plus finite nonnegative duration; capture availability is local aggregate evidence. CLI validation stays limited to selected scans. UI previews validate every scan's header, times and listings (`_validate_scans`), but record house mismatches per scan in `ScanPreview.mismatches`; `new_ids` excludes them.
- `import_scans(..., reviewed=preview, scan_ids=...)` recomputes and compares bytes/configuration/known records before any archive write. It rejects unknown, empty or already-imported selections. A final duplicate check under the writer transaction precedes `_save_collection`; the writer consumes the recomputed in-memory bytes. Fresh databases and migrations are created only during explicit import. Preview remains read-only across schema 3 and 4.
- `_save_collection` preserves raw bytes and manifests, and `_load_collection` shares transactional deduplication and per-scan import with the CLI. `_file_scan_state` classifies every file scan after loading as saved (same ID and hash), `other_house` or remaining, without validating unselected scans; an unusable entry counts as remaining. `import_guidance` uses those counts to protect subsets and warn about other-house scans.
- `views/scan_import.render` owns one active review and selection in Streamlit session state. Configuration/source switches discard both; changing to a TSM source also invalidates the active addon identity. Each Preview click clears prior state before reading. Import runs in the button's `on_click` callback and stores its messages for the rerun, so the result replaces the reviewed table. Errors discard the review and require another click. `app.py` orchestrates these controls and keeps TSM refresh unchanged.
- Bronze/silver/database together are still not atomic; normal import-write failures retain a failed manifest for diagnosis. Best-effort file-read detection cannot prevent every concurrent game write (ADDON-06).

### Multiple input files (STORY-037)

- `Source.machine` is required for addon inputs, validated by `drop_files.validate_machine`. `Source.drop_folder` is optional and accepted by `read_sources` only through local overrides; both paths resolve relative to the project. The configured data directory cannot be inside the drop folder. Rules and cleanup decisions are OPS-03.
- `brownstone/drop_contract.json` is the single naming/pattern source consumed by Python and PowerShell, including UTC format strings, filename template, and shared valid/invalid examples. The JSON is included as Python package data. The PowerShell harness runs without Pester through pytest where PowerShell exists; macOS reports an explicit skip, Windows CI executes it.
- `scan_inputs.InputFile` holds path, machine, UTC drop time, per-file `ScanPreview`, error or ignored reason. `InputPreview` includes the full inventory and resolved configuration. `preview_inputs` opens no ignored file, writes nothing, and isolates read/validation/conflict errors. `latest()` includes unreadable final drops so an older successful drop cannot be mistaken for the latest one.
- `import_inputs` recomputes the inventory, configuration, bytes and known state before any writes. Selected files import independently; later identical scans deduplicate against earlier committed files, while other unexpected duplicate-state changes invalidate that file. Each file then uses the existing reviewed importer and final writer check. This is a sequence of per-file transactions, not one batch transaction; earlier successful collections survive a later failure.
- Batch selections identify files by full path because scan IDs repeat across files. CLI `--scan` limits matching IDs in every file. The page selects files and imports their matching scans, including partial scans and duplicates; another-house entries remain unimported. `include_duplicates=True` allows an explicitly reviewed duplicate-only file to obtain its own collection; the single-file UI retains its new-only selection contract.
- Bronze manifests add `machine` (configured local name or parsed drop machine) and `original_file_name`; existing `source`, SHA-256, byte count, scan outcomes and remaining/other-house counts remain. Machine is also added to new silver scan rows and stored `addon_scans`. Byte blobs may be shared; collection manifests never collapse files. Duplicate import preserves the original stored machine and never guesses a historical one.
- `file_rows` and `latest_rows` provide common CLI/page cleanup evidence. `fully_imported` is true only for a readable nonempty file whose every scan and character snapshot has a matching stored hash and no house mismatch. Ignored names, parse errors, conflicts and other-house scans cannot give cleanup permission.
- CLI `--preview` is read-only. With a drop folder, ordinary addon import lists every file and imports only those with new scans (or, with `--scan`, those holding the requested IDs), so a repeated run never re-archives imported files; `--input` keeps the explicit single-file path and takes its machine from a drop name, otherwise from `machine`. The page shows file status, per-file scan tables, UTC provenance and each machine's latest-drop state, then refreshes those tables after import.

### Character snapshots (STORY-032)

Capture and clear/session rules live in requirements.md → ADDON-11/12. Addon 0.8.0 keeps
account-wide format 6 with `scans` (unchanged record formats 1–4), `snapshots`, `sessions` and
`snapshot_sequence`, `journal` and `journal_diagnostics`. Each snapshot is a keyed table, with `slots` and `containers` arrays;
exact links and nullable client values are preserved without variant interpretation yet.
Length-prefixed character/realm + kind + Unix seconds + persistent sequence identify an event.
The sequence prevents two bank/logout observations in the same second from overwriting each other;
latest reads order same-second evidence by its numeric `sequence`, then ID.

`scans.read_addon_records` parses both record lists once; `read_saved_variables` retains its scan-only
return contract for existing callers. `character_snapshots` validates evidence, canonicalizes content
for SHA-256, checks character house evidence, queries scoped duplicates and reads latest per-character
bags/bank independently. The original file's exact bytes remain authoritative bronze evidence.

Migration **10** adds `character_snapshots` (source/ID primary key, full MARKET_KEYS, character
realm/faction, kind, UTC timestamp, nullable BIGINT gold, machine, collection/file/content hashes,
original record JSON) and `character_slots` (source/ID/container/slot primary key, nullable BIGINT
item/count and exact link). Slots belong to the fully scoped parent; no cross-character or price join
is introduced. Frozen DDL is replayable; existing tables/rows/hashes are unchanged and migration
backs up the starting database. Preview can query schemas before 10 without upgrading.

`ScanPreview.non_scans`, `non_scan_summaries`, `non_scan_known`, `non_scan_mismatches` are the
single state for both snapshots and journal entries; known state uses `record_sha256` for both.
`new_record_ids` drives import availability.
Snapshot-only properties are read-only compatibility projections, never parallel state.
`addon_records` dispatches validation/storage by record type, while sharing house, hash/conflict,
preview/review, transaction and outcome logic. Scan selection/`--scan` limits only scans; every
matching non-scan record in each selected file imports. `scan_inputs` tracks expected commits by
(type, ID) across overlapping drops and refuses unrelated state changes. The final writer check
compares the same non-scan known state before archiving. Conflicts isolate the affected file.

Migration **11** adds `character_journal`, source/entry-ID primary key, full MARKET_KEYS,
character/character realm/faction, event family, UTC capture time, machine, collection ID, source
file hash, canonical content hash and raw `record_json`. JSON stringifies Lua numeric keys;
canonical SHA-256 uses sorted typed-key pairs recursively to preserve nil-hole tuple tables with `n`
and distinguish numeric keys from string keys.
Snapshot canonical hashes are unchanged. Preview of older schemas reads unknown journal state
without migrating. Upgrades back up the starting schema; replayable DDL changes no historical rows.
Journal rows load directly with snapshots/scans inside the collection transaction; no journal silver
export or interpretation. Exact bytes are preserved in the shared bronze blob. The manifest's
`non_scan_records` is the common outcome list (`record_type`, `record_id`, `record_sha256`, outcome,
summary); `snapshots` remains a derived compatibility projection for historical consumers.
A collection without priced scans cannot replace prices. Latest imported bank evidence persists.

Journal records use `entry_id`, `sequence`, `event`, `family`, `arguments`, `captured_at`,
`captured_at_utc`, `session_time`, character/realm/faction, addon version, login marker and `windows`.
Money adds `before_copper`/`after_copper`; bags add numeric `item_changes` or `baseline_missing`.
Mail adds `inbox` with counts and message array (index, header/invoice counted tuples, attachment
info/link); send hooks add a cached `draft` plus `draft_is_last_observed`. Overflow adds `skipped`.
STORY-040 adds `owned_auctions` to family `auction`: `api`, counted `counts`, `auctions`
(index + raw `info`; legacy also `item_link`/`time_left`), and nullable modern `full_results`/
`sold_status`. Modern info is a field-preserving table; legacy info is a tuple with `n`.
The matching owned-update event reads cached results only; the transient last successfully saved
list suppresses equal states and resets on reload. Version 0.7.0 retains file format 6/schema 11;
no new import path, table or migration. API/capture/display rules live in ADDON-12.
STORY-041 adds `level` and `skills` to bags snapshots. `skills.legacy` has API name,
counted count tuple and rows; `skills.modern` has API name, counted profession indexes and rows.
Each row keeps its original index, counted `info`, name, rank/max and available ID; legacy headers
remain in raw evidence. Modern rows are a dense array even when the index tuple has nil holes.
Legacy rows also keep header expansion, with `possibly_incomplete` on the surface when a header is
collapsed. The import page reads only the newest bags snapshot per character and newest list per
character/profession (SQL `QUALIFY` on capture time, then sequence).
Snapshot hashing retains historical hashes exactly; only the new `skills` subtree uses the journal's
typed-key canonical encoder, so counted tuples cannot conflate numeric and string keys.
Stored snapshot JSON retains those tuples without sorting mixed key types.
`known_recipes` in family `craft` has API prefix, counted profession/count returns, name/rank/max,
indexed rows with counted raw info, links/link IDs, made tuple/min/max, reagent count tuple and
reagent rows (raw info/link/ID/count), filter state and `possibly_incomplete`.
This uses schema 11/raw JSON and format 6 unchanged; the lifecycle has no new adapter or storage path.
`professions` validates optional display fields and projects scoped latest bags plus latest list per
profession, ordering by capture time/shared sequence. It shows all observed skill lines rather than
inventing a profession classification, and keeps absent lists/counts unknown. If both skill surfaces
report the same name, display deterministically prefers the modern row (which supplies skill IDs),
labels its API/ID and keeps both originals raw; it never fills one API's holes from the other.
Only `views/scan_import`
uses it. Capture/display/unknown rules and the journal choice live in ADDON-11/12.
Reference tuple shapes and filter index 0 come from Blizzard's
[Classic trade skill UI](https://github.com/Gethe/wow-ui-source/blob/classic_era/Interface/AddOns/Blizzard_TradeSkillUI/Vanilla/Blizzard_TradeSkillUI.lua)
and [Classic craft UI](https://github.com/Gethe/wow-ui-source/blob/classic_era/Interface/AddOns/Blizzard_CraftUI/Vanilla/Blizzard_CraftUI.lua);
Forever availability and extra returns require beta evidence, which is retained raw.
API shape evidence: Blizzard's generated
[modern owned API documentation](https://github.com/Gethe/wow-ui-source/blob/live/Interface/AddOns/Blizzard_APIDocumentationGenerated/AuctionHouseDocumentation.lua)
uses 1-based owned indexes and nullable fields;
[Classic auction UI](https://github.com/Gethe/wow-ui-source/blob/classic_era/Interface/AddOns/Blizzard_AuctionUI/Classic/Blizzard_AuctionUI.lua)
reads batch/total, places saleStatus at tuple position 16, and marks 1 as sold awaiting delivery.
These reference sources establish API shape, not Forever beta availability.
`journal_diagnostics` is load-session evidence: rejected events, missing/installed hooks, fired counts.
`journal_errors` counts guarded observation failures by event/hook; these are reported in chat.
Unknown values are absent in Lua/nullable in Python; arbitrary argument tuples never become prices.
The ID uses the snapshot identity encoder and shared sequence. Cap/clear/hook rules are ADDON-12.

CLI/page use `journal.preview_rows` for per-file character/family counts by state; `latest_rows`
queries source + all market keys and returns imported family counts/latest time. The page retains
latest bags/gold and independent bank evidence. `journal.active_auction_rows` reads scoped raw
journal/snapshot JSON to establish known characters, selects owned evidence by capture time/shared
sequence/entry ID, and returns UTC, reported count and client-marked sold count. Missing evidence
shows `active auctions unknown`; explicit empty shows count zero. Legacy counts preserve batch/total;
the page uses reported total when present, and a shorter batch keeps sold count unknown. Missing statuses or incomplete
results retain an unknown sold count. Only the import page calls this projection.
`InputFile.fully_imported` checks scans plus all
non-scan known states and house mismatches; `import_guidance` counts all newly saved records.
Machine comes from OPS-03, stays unchanged on duplicates, and never participates in market joins.
Windows scripts copy the whole account file unchanged. No other view consumes the journal.


## Scan comparison

- `storage.scope_predicate` supplies the source and full `MARKET_KEYS` predicate to price, depth and comparison reads.
- `scan_changes.eligible_scans(db, config)` reads the selected source's completed, non-partial, priced `addon_scans` rows, ordered by finish time and scan ID descending. Finish times are normalized to UTC independently of DuckDB's session timezone.
- `compare_scans(db, config, first_id, second_id, item_ids=None)` validates distinct eligible IDs and orders them chronologically. DuckDB reads `scan_metrics` facts per exact identity, scoped by source, market, scan ID, snapshot ID and metrics version. `market_snapshots` and a name-only `scan_listings` aggregation provide labels, with the same scope; neither supplies numeric metrics. A full outer join returns only item aggregates to Python, never raw listings.
- The result carries earlier/later scan metadata, their time gap, shared `items`, `new` and `vanished`. Each row has item ID/name, earlier/later metric dictionaries (minimum buyout, market value, listings, units), later-minus-earlier changes and a changed flag. A missing side is `None`; unavailable prices and changes are `None`, with integer copper for all valid prices. Optional item IDs filter every list; an empty list matches nothing.
- `views/scan_changes.py` renders UI-06, using `compatible_catalogs` for the item-ID filter, shared context/freshness display and money helpers. The sidebar registers it as **Scan changes**. Existing calculation pages keep their contracts.

## Crafting calculation

- `basis_prices(observations, basis)` turns observed prices into buy and sell unit price maps (CRAFT-04).
- `evaluate_recipe(catalog, recipe_id, buy, auction_cut, sell)` chooses each input's cheapest route recursively. It returns:
  - direct choices
  - the chosen-route shopping list
  - the all-craft expansion
  - cost, net revenue, profit, margin and break-even
- `Decimal` handles the auction-cut rounding.
- `storage.listing_depth` returns listing and unit counts by item for the same analytical snapshot used by `price_observations`. It first checks the scoped `addon_scans` record is complete and priced, then reads `scan_metrics` with the source, full market identity, snapshot ID, scan ID and metrics version. It returns `None` when unavailable, or zero counts for absent requested items. The Crafting view renders these separately from `rank_recipes`; depth never enters calculation or policy inputs (CRAFT-09).
- Catalog discovery supplies `catalog_id` from the selection-file stem. Standalone catalogs default to a header identity (`game_version:rules_version:profession:catalog_version`); combined inputs must have unique identities. Rows carry `catalog_id`, `recipe_id` and `profession`, and `catalog_for_row` resolves details to the original catalog.
- The Crafting view groups unsupported-recipe reasons into one collapsed table and separates catalog
  captions and board explanations into collapsed expanders. Board provenance and freshness remain
  visible. This changes presentation only; board rows and recipe evaluation still use the same paths.
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

1. **Market identity (done, STORY-009).** Configure `scope = "house"`, `server_type`, `faction`, an explicit `environment` (DATA-03) and no realm, for example `forever-us-roleplaying-alliance`. Neutral houses default to a 15% cut.
2. **Price source (done, STORY-010).** There is no TSM or Blizzard feed. A `provider = "addon"` source imports the addon's SavedVariables file: bronze stays byte-for-byte, listings go to `scan_listings`, and item-level prices are derived in the `market_snapshots` shape (rules ADDON-01 to ADDON-06).
3. **Catalog (done, STORY-004).** `config/forever-tailoring.toml` is generated from the saved Forever Tailoring page (CRAFT-08). To cover another profession or more recipes, use **Add or update a profession** on the Recipe catalogs page.
4. **Configuration.** Add the `[[sources]]` entry: market fields, `rules_version`, `provider = "addon"`, `scan_path` and `scan_evidence` (see the disabled example in `config/market.toml`). Other non-TSM feeds get their own adapter producing the same `market_snapshots` columns.

No change to crafting, the Action Board or the views should be needed. If one is, treat it as a design defect.

## Quality gates

Ruff (lint, import order and a complexity limit of 10 per function), mypy (on `brownstone/` and `launch.py`) and pytest with a branch-coverage floor run locally and in CI; configuration is in `pyproject.toml`. `Source` is a `TypedDict`, so mypy checks config key names wherever a function is annotated with it.

## Known design debt

- Batch preflight and per-file reviewed imports parse files repeatedly and retain their bytes in memory. Large retained drop folders increase preview cost; manual cleanup bounds it. Rename completion is local only and cannot guarantee Google Drive's remote visibility or offline availability.

- **Complexity debt:** `scans.parse_lua` (13) exceeds Ruff's limit of 10 and carries `# noqa: C901`. It is kept as one loop deliberately: it runs once per token, about a million times for a 24 MB scan, and splitting it adds a function call to each. Revisit only with a measurement.
- **Coverage gaps** (overall coverage in `status.md` → Quality gates): `views/market.py` 76% (Opportunities with data, which only Retail can supply), `app.py` 93% (configuration and upgrade errors), `views/catalogs.py` 93% (error messages for unreadable selections and failed writes). `sources.py` downloads over the network, which offline tests don't exercise.
- Records other than `Source` (manifests, catalog entries, evaluation results) are plain dicts.
- `views/` is not type-checked.
- `completed_snapshots` reads every manifest on each page load; this is fine at current volumes.
- Re-importing an addon file parses it in full before deduplication can skip its scans: about 0.1 s per schema-2 scan, 0.9 s per schema-1 scan. Scans left in the file add up until `/bscan clear`, and bronze keeps a compressed copy of each distinct file (about 0.5 MB per schema-2 scan).
- Each imported scan adds about 4.7 MB to DuckDB (`scan_listings`, 101,485 rows) and 1 MB of silver. That is now the largest per-scan cost; keeping listings only in silver Parquet and querying them from there would remove it if disk becomes a problem.
- Addon silver, DuckDB and the manifest are not one atomic write, like TSM collections.

## Variant-aware scan reads (STORY-023)

`variants.ITEM_KEYS` defines the within-scan grouping (`item_id, variant_id, variant_state`); null-safe joins preserve base/unresolved observations without pooling them with variants. `scans.item_prices` applies the same keys to names, unit-weighted percentile ranks and minimum prices. `compare_scans` groups/joins on these keys with null-safe variant comparison. Legacy null state shows as `legacy`, matching the other scan's `base` row only when that scan saw only base listings for the item ID (ADDON-08). `item_names.remember_observed_names` takes names only from base or legacy rows. `analysis.rank` returns variant identity with each row. Browse and Scan changes expose identity/state alongside names.

`price_observations` and `listing_depth` retain their catalog item-ID return shape. Default reads accept base rows and historical null fields, but exclude format-3 unresolved/variant rows; explicit `variant_id`/`variant_state` arguments select an exact variant or unresolved pool (never legacy null-state rows) within the same full market/source/snapshot scope. Catalogs have no variant selectors today, so a variant-only output stays missing prices instead of inheriting a different suffix's price. No crafting rules-version check is relaxed.

Tests execute the actual addon under Lua 5.1 through the declared, pinned dev dependency Lupa. Offline WoW stubs exercise both API paths, optional missing/erroring fields, chunking, manual start, timeout/close and item-reference caching, then import the emitted scan. Python coverage measures application code; it does not claim Lua branch coverage or substitute for beta API/tooltip measurements.


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
`storage.listing_depth` retains its catalog compatibility selector and zero counts for absent items;
`scan_changes` preserves the existing name and comparison policies. Stored addon prices remain for
Browse/Opportunities/crafting and TSM compatibility; their numeric calculation is shared, not duplicated.
Rebuild preserves these historical observations rather than rewriting them.

The rebuild currently materializes all eligible listings locally in Polars; no streaming/bounded-memory
claim is made. Derived metrics are not automatically invalidated by unsupported direct SQL edits to
observations: explicitly rebuild after changing stored evidence. Manual writes bypass the structured
key calculation; imports/rebuilds are the supported writers. No dependency was added.


## Today contracts (STORY-025)

Rules and decisions live in `requirements.md` → Today v1. `read_today_evidence` returns
`(observations, listings, metrics, vendor_sell_prices)` for one source and analytical snapshot.
Listings are grouped base/legacy catalog identities with `(quantity, full buyout, unit ceil)` tuples;
metrics retain ADDON-10 counts and p25. Missing listing support is `None`, distinct from an empty
eligible scan's `{}`. No seller strings enter this path. Catalog compatibility retains game/rules
version; storage predicates retain source and every MARKET_KEYS field plus scan/snapshot and item
variant state. No schema changes or migrations are needed.

`build_today` takes catalogs, scoped evidence, `TodaySettings` and the caller's clock. It returns
four capped lists (`craft`, `buy`, `sell`, `below_vendor`), mutually exclusive hidden reason counts,
remaining counts, complete shopping cost, freshness and Today version. Craft rows retain board
routes and recipe/catalog provenance. Recipe evaluation retains `intermediate_steps` for chosen
`craft` branches only, with catalog recipe/item IDs, names, per-execution quantities, craft counts
and depth. `craft_details(row)` projects complete materials from the selected row's existing
`purchases` (no listing quotes), using that catalog's material names, and scales retained intermediate
steps by batch size. Copper costs remain integers; step costs are already in the purchased leaves.
Both detail lists retain stale/actionable state. Materials include the merged Buy list's hidden tail.
Prefix units/buyouts support whole-stack quotes with binary
search for the affordable bound; the most profitable size is then chosen among the bound and each size just
before an input needs another listing. Each selection reserves funds and listing offsets. No per-unit expansion or per-recipe SQL.
Selection rounds re-size remaining candidates against the same remaining resources. Duplicate
output routes are counted and omitted once an output is selected; sell follows the chosen route,
and shopping combines item/route purchases. Evidence state is attached to every result row. Settings I/O is separate from pure calculations; the UI writes only
on Save, to `today_settings.settings_path(data_dir, source_id)` (one file per source in the shared data
directory), and reports invalid or failed reads/writes without hiding the tables. The view wraps the
form in an expander and puts the four lists in tabs. Each table projects decision columns plus State
by default; an evidence toggle reveals its other columns without changing result values. Shared
provenance appears once above the tabs; freshness stays outside collapsed controls (UI-01).
The Craft dataframe supports single-row selection, initially empty. Its widget key fingerprints
plan contents and provenance (excluding continuously changing freshness age), so a changed plan
clears selection. Selected materials appear beneath it, followed by indented catalog craft steps
(STORY-038); detail materials are complete rather than capped at Buy's 10 displayed rows.

Offline fixtures in `test_today.py`, `test_today_data.py` and `test_today_view.py` cover this contract
without discovering local catalogs. Performance verification uses a copied database with current
local catalog selections; aggregate measurements and limitations are in `status.md`.


## Beta evidence report (STORY-042)

`cli.beta_report_main` selects one configured addon source and routes to `beta_report.create_report`.
The configured source supplies authoritative market/house identity for the import check; its data
directory is never opened by the report. `beta_report` uses the pipeline's bounded byte reader and
`scans.read_addon_database` plus the extracted `addon_record_list` helper shared with import. It
validates records independently through `pipeline._validate_scans` or the existing snapshot/journal
summarizers (which also validate professions), so a refused record cannot hide other evidence.
`beta_evidence` contains pure checks and the small `COVERAGE` table; `views.beta_report` renders
Markdown and uses `money.to_gold`. No Streamlit dependency, schema change or addon change.

The only persistent writes are a unique UTC timestamp/UUID folder under ignored `work/beta-reports/`,
containing `report.md` and `report.json`. The JSON keeps every check and entry ID; the Markdown is a
compact reading copy (repeated passes collapse to counts, ID lists are cut at 10, coverage is one table)
so a long play session stays small enough to send for review. Preview, import and duplicate re-import use an exact-byte
input copy and fresh data directory inside `TemporaryDirectory`; bronze is decompressed and checked
against the original bytes. The complete file must import into the selected house, including all
records; empty or other-house files fail this check with the importer's explanation. Unreadable or
changing inputs get exit 2, failed checks exit 1, passes/warnings exit 0.

Loads are **inferred**, not an addon-provided identity. Shared account sequence orders snapshots and
journal entries; a logout snapshot closes a load, identity/login changes and decreasing session
uptime start one. `GetTime` can persist across reload, so it is not a unique load marker. Missing
logout/boundary evidence can merge loads; records with missing sequences fail the sequence check.
Only the latest `journal_diagnostics` exists in the file; earlier inferred loads have null diagnostics.
`journal_errors` is persistent account-wide evidence, not a reliable per-load counter. Neither
missing historical diagnostics nor ambiguous boundaries can be reconstructed without an addon
contract change, which is outside this story.

Money chains compare each before value with the previous after within an inferred load. Consecutive
bags snapshots reconcile gold against signed integer-copper money deltas and per-item slot-unit
changes against signed journal bag deltas, using capture time/shared sequence intervals, separately
for full character/realm/faction identity. Unknown readings/baselines warn instead of inventing zeros.
Residuals are evidence gaps, not classified transactions or ledger balances.

Size estimates are compact typed JSON UTF-8 sizes, explicitly approximate rather than Lua byte
offsets. Scan output is a strict projection of IDs, times and listing counts; owned-list output keeps
only numeric evidence, excluding bidder/owner names. No raw listings, mail arguments or recipe raw
payloads leave the report. Previous-file comparison uses importer canonical record hashes and
source-local type/ID identities, reports additions by full character identity and family (snapshot
kind for snapshots), and fails changed content for an existing ID. Coverage rows list alternative
events/hooks, seen/unseen names and installed hooks: observation confirms capture only, not success
of an economic action, a sale/expiry invoice's meaning, complete containers or full recipe coverage.
