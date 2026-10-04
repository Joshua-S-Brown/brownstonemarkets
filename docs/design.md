# Brownstone design

How the system is built. Rules and their rationale live in `requirements.md`; this document covers structure, data contracts and extension points.

## Data flow

```text
TSM CSV ──download──▶ bronze (exact bytes + manifest JSON)
        ──normalize─▶ silver (validated Parquet, one per collection)
        ──load──────▶ DuckDB market_snapshots (deduplicated analytical snapshots)
        ──rank──────▶ gold (discount-screen CSV/Parquet per collection)

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
  config.py             market.toml loading/validation; MARKET_KEYS
  sources.py            HTTP download
  normalization.py      CSV → validated frame
  pipeline.py           orchestration of one collection
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
| Market | `market_id, game_version, region, scope, realm` (+ `ruleset` for crafting) | Defined per `[[sources]]` entry in `config/market.toml` |
| Collection | `snapshot_id` (UTC time + random suffix) | Bronze CSV + manifest; manifest records `analytical_snapshot_id` |
| Analytical snapshot | market + upstream scan time + SHA-256 | Repeated identical content reuses the earlier ID |
| Price observation | analytical snapshot + market identity + item ID | Integer copper: `min_buyout, market_value, recent_value, historical_value` |
| Catalog | `game_version, ruleset, catalog_version` | TOML; items with role and provenance, recipes with inputs and output quantity |

The `market_snapshots` table is created from the first silver file's schema, and identity columns are added by additive migration. An explicit DDL and schema version are planned before STORY-004/006.

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

1. Add a `[[sources]]` entry with `game_version = "forever"`, the Forever `ruleset`, region, scope and the feed URL.
2. Bring `config/forever-tailoring.toml` to the same ruleset and verification standard as the Classic catalog.
3. If the feed is not TSM CSV, add an adapter in `sources.py` / `normalization.py` that produces the same silver columns.

No change to crafting, the Action Board or the views should be needed. If one is, treat it as a design defect.

## Known design debt

- Configuration and records are plain dicts. A small typed `Source`/`Market` model would catch key typos.
- DuckDB schema is implicit (see above).
- `completed_snapshots` reads every manifest on each page load; this is fine at current volumes.
- No linter or type checker yet.
