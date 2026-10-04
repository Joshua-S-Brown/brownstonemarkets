# Brownstone design

How the system is built. Rules and their rationale live in `requirements.md`; this document covers structure, data contracts and extension points.

## Data flow

```text
TSM CSV ──download──▶ bronze (exact bytes + manifest JSON)
        ──normalize─▶ silver (validated Parquet, one per collection)
        ──load──────▶ DuckDB market_snapshots (deduplicated analytical snapshots)
        ──rank──────▶ gold (discount-screen CSV/Parquet per collection)

SavedVariables .lua ──copy──▶ bronze (exact bytes, stored once per SHA-256, + manifest JSON)
        ──parse/check─▶ scans (Lua subset parser, house evidence, stack unit prices)
        ──silver──────▶ per scan: _scan, _listings and, if complete, _prices Parquet
        ──load────────▶ DuckDB addon_scans + scan_listings + market_snapshots (complete scans only)

catalog TOML ──load──▶ crafting / action_board ◀── price_observations (DuckDB)
```

Raw bytes are written before validation, so failures stay inspectable. DuckDB writes are transactional, but silver, DuckDB and gold together are not one atomic operation (see `status.md` for recovery).

## Modules

```text
app.py                  Streamlit entry: sidebar, Refresh, view dispatch
views/                  Streamlit only; display, no calculations
  common.py             snapshot loading, freshness display, gold columns
  crafting.py           Action Board and recipe explanation
  market.py             Browse market and Opportunities
brownstone/             importable without Streamlit
  config.py             market.toml (+ untracked market.local.toml overrides) → list[Source] (typed, validated)
  markets.py            market identity: MARKET_KEYS, derived market_id, validation, legacy upgrade
  sources.py            HTTP download
  scans.py              BrownstoneScan SavedVariables: parse, validate, house check, unit and item prices
  normalization.py      CSV → validated frame
  pipeline.py           orchestration of one collection: run (TSM CSV) or import_scans (addon)
  storage.py            DuckDB load/dedup, manifests, scoped price reads
  analysis.py           browse and discount screen queries
  freshness.py          the one staleness policy
  money.py              copper ↔ gold display helpers
  crafting.py           catalog loading, expansion, route costs, price bases
  action_board.py       ranking and label policy (versioned)
launch.py               local server launcher with code-fingerprint restart
```

Dependencies point inward: `app.py` → `views/` → `brownstone`. Domain modules (`crafting`, `action_board`, `freshness`, `money`) do no I/O and take the clock as a parameter. The `dashboard` extra (Streamlit) is needed only for `app.py` and `views/`.

## Data contracts

| Entity | Identity | Notes |
| --- | --- | --- |
| Market | `game_version, region, scope, realm, server_type, faction` → derived `market_id` | One auction house. Crafting also needs the source's `rules_version` |
| Source | `source_id` (+ `provider`, `source_url`) | One feed observing one market; a `[[sources]]` entry; names its data folders |
| Collection | `snapshot_id` (UTC time + random suffix) | Bronze CSV + manifest with source and market identity; manifest records `analytical_snapshot_id` |
| Analytical snapshot | source + upstream scan time + SHA-256 | Repeated identical content from the same source reuses the earlier ID |
| Price observation | analytical snapshot + source + market identity + item ID | Integer copper: `min_buyout, market_value, recent_value, historical_value` |
| Addon scan | `source_id, scan_id` → `snapshot_id = <source_id>:<scan_id>` | `addon_scans`: status, `partial`, `priced`, times, counts, `nonexact_stacks`, client, house evidence, scan and file SHA-256. Its import manifest lists every scan with an outcome (`imported`, `duplicate`, `partial (not priced)`, `empty`); `scan_id`, `updated_at` and `analytical_snapshot_id` name the newest complete scan, and status is `no_complete_scan` when there is none |
| Listing | `source_id, scan_id, listing_index` + market identity | `scan_listings`: `item_id, item_name, quantity, buyout` (whole stack), `unit_buyout` (exact only), `unit_buyout_ceil`, `min_bid, bid, complete_info` |
| Catalog | `game_version, rules_version, catalog_version` | TOML; items with role and provenance, recipes with inputs and output quantity. Optional evidence: recipe `verified_at` / `verification_url`, item `vendor_price_source_url` |

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
- `rank_recipes` checks that the catalog, market and snapshot are compatible, then:
  - evaluates every finished output under both bases
  - labels and sorts the rows (CRAFT-05)
  - isolates per-recipe errors so one bad recipe doesn't hide the others

## Switching to WoW Forever

1. **Market identity (done, STORY-009).** Configure `scope = "house"`, `server_type`, `faction` and no realm, for example `forever-us-roleplaying-alliance`. Neutral houses default to a 15% cut.
2. **Price source (done, STORY-010).** There is no TSM or Blizzard feed. A `provider = "addon"` source imports the addon's SavedVariables file: bronze stays byte-for-byte, listings go to `scan_listings`, and item-level prices are derived in the `market_snapshots` shape (rules ADDON-01 to ADDON-06).
3. **Catalog (STORY-004).** Generate `config/forever-tailoring.toml` with the recipe importer to the same verification standard as the Classic catalog.
4. **Configuration.** Add the `[[sources]]` entry: market fields, `rules_version`, `provider = "addon"`, `scan_path` and `scan_evidence` (see the disabled example in `config/market.toml`). Other non-TSM feeds get their own adapter producing the same `market_snapshots` columns.

No change to crafting, the Action Board or the views should be needed. If one is, treat it as a design defect.

## Quality gates

Ruff (lint and import order) and mypy (on `brownstone/` and `launch.py`) run locally and in CI; configuration is in `pyproject.toml`. `Source` is a `TypedDict`, so mypy checks config key names wherever a function is annotated with it.

## Known design debt

- Records other than `Source` (manifests, catalog entries, evaluation results) are plain dicts.
- `views/` is not type-checked.
- `completed_snapshots` reads every manifest on each page load; this is fine at current volumes.
- Re-importing an addon file parses it in full (about 1 s for 24 MB) before deduplication can skip its scans.
- Addon silver, DuckDB and the manifest are not one atomic write, like TSM collections.
