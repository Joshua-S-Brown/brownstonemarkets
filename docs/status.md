# Status

Current implemented state, limitations and how to verify. History lives in Git; keep this file describing *now*.

_Last updated 2026-10-04._

## Implemented

- **Ingestion:** TSM CSV → bronze/silver/DuckDB/gold with manifests, validation and analytical deduplication. Sources: Mankrik Alliance Classic Era (development stand-in), plus Retail Area 52 and US commodities (regression only).
- **Addon scan import (STORY-010):** a `provider = "addon"` source imports BrownstoneScan SavedVariables through **Import addon scan** or `python -m brownstone --source <id> [--input file] [--scan ID]`. Rules ADDON-01 to ADDON-06 in `requirements.md`.
  - House evidence is checked against the configured market, and the whole file fails on a mismatch.
  - Stacks are priced per unit, rounded up when inexact. `market_value` is the quantity-weighted 25th percentile.
  - Deduplication is by `scan_id`, and identical file bytes are stored once. Partial scans are stored and labeled but not priced.
  - The Forever Action Board works from imported scans with no calculation changes.
  - Source `forever-us-normal-alliance-addon` is disabled in the tracked `config/market.toml`. On the user's machine, the untracked `config/market.local.toml` enables it and points it at the game's SavedVariables file, to archive beta scans before the beta closes. Classic Mankrik stays the default development source.
- **Crafting:** Classic Tailoring catalog 0.1 with Woolen, Mageweave and Runecloth bags and their bolts. Route costing, cautious and listed price bases, and an Action Board under policy 0.2 with five labels and per-recipe error isolation.
- **Interface:**
  - Crafting opens by default for markets with a compatible catalog. It shows the board, a recipe summary in g/s/c and expandable evidence.
  - Browse market and Opportunities are also available. Opportunities explains when a source can't support it.
  - All money is displayed in gold.
- **Launcher:** `launch.py` (via `Start Brownstone.command` / `.cmd`) restarts its own server when the code has changed.
- **Catalog verification (STORY-007):**
  - All six recipes' reagent and output quantities and all three thread vendor prices match Wowhead Classic. Evidence URLs are recorded per record, and a test pins the verified values.
  - Bolt of Runecloth uses 5 Runecloth.
  - No catalog values changed, so it stays at version 0.1.
- **Markets and sources (STORY-009):**
  - A market is the auction house; a source is the feed that observed it. `market_id` is derived, so several sources can observe one market, each with its own folder and deduplication.
  - Forever houses (server type + faction, no realm) can be configured. Neutral houses default to a 15% cut.
  - The catalog `ruleset` field is now `rules_version`.
  - The CLI uses `--source`; `--market` still works as an alias.
- **Storage:** explicit DuckDB schema, version 3 (`addon_scans` and `scan_listings` added), with backed-up, idempotent migrations. The live `data/brownstone.duckdb` is still at version 2; the app or the first import upgrades it, keeping `brownstone.v2.backup.duckdb`.
  - The app upgrades the database on startup. On 2026-10-04 the live database went from version 0 to 2, with `data/brownstone.v0.backup.duckdb` kept. All 24,020 rows were kept and the board was unchanged.
  - A dry run on a copy kept all 24,020 rows and split Mankrik's realm and faction correctly. The board gave identical results.
  - Re-importing an old raw file was recognised as a duplicate.
  - Old manifests are read through an adapter and never edited.
- **Quality gates:** CI runs Ruff, mypy and the tests on macOS and Windows from the lock file, including the Streamlit UI test. Config loads into typed, individually validated `Source` records.

- **Scanning addon (SPIKE-008, done):** `addon/BrownstoneScan/` is a read-only addon that scans on a click or `/bscan start` and saves listings to SavedVariables (`schema_version` 1; sample at `tests/fixtures/brownstone_scan_sample.lua`; install and measurements in `addon/README.md`). Verified on the Forever beta, build 70205, interface 16001: one full scan of the Stormwind Alliance Normal house, 101,485 listings in about 10.6 s, 24 MB file, written correctly. Decision and format are in `requirements.md`. Scans are imported as described above.
  - **Real scan kept** at `data/inbox/addon-scans/BrownstoneScan-forever-beta-2026-10-04.lua`. That's a byte-for-byte copy (SHA-256 `207a2b95…`) of the game's SavedVariables file: scan `20261004T164730Z-c651bd`, Alliance Normal house. It's ignored by Git like all of `data/`, so back it up with `data/`.

## Limitations

- The addon was measured on one beta house only: not the Roleplaying or a neutral house, and `/bscan start` without the button is untested. Beta region and realm values are generic, so scans are identified by auctioneer, zone and label. The `.toc` interface number 16001 may change with beta builds.
- Required skill levels are display-only. Three are sourced: Woolen Bag 80, Mageweave Bag 225, Bolt of Runecloth 250. Three are unconfirmed and marked `required_skill_verified = false`: Runecloth Bag 260, Bolt of Woolen Cloth 75, Bolt of Mageweave 175.
- Addon prices come from one scan: no history, so no recent or historical values and no discount screen. Listing depth is stored but not yet used in calculations.
- The real beta scan has thin high-level Tailoring coverage, because most beta characters are low level; low-tier bags and cloth are well listed. Runecloth Bag has no listings, so its board row shows missing prices, and Runecloth has two listings, which carry no loaded name.
- Mankrik has no upstream scan time, so price age is unknown and "stale" only measures time since download.
- Classic historical values are zero, so the discount screen cannot run on Classic.
- Not modeled: see `requirements.md` → *Not modeled*.
- Legacy rows have no source hash and are not retroactively deduplicated. Changed content at the same upstream time is kept as a correction.
- Silver, DuckDB and gold are not written atomically. If a run fails after the DuckDB commit, the bronze/silver files are the recovery source. There is no replay tool yet (STORY-006).
- Run one writer at a time; a concurrent refresh can fail on the DuckDB lock.

## Verify

```bash
.venv/bin/python -m pytest -p no:cacheprovider
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy
```

Expected: 111 tests pass, offline; `ruff check .` and `mypy` report no issues. Windows uses `.venv\Scripts\python.exe`. Live ingestion is a separate manual check: **Refresh from TSM** in the app.

Last live check (2026-10-04, Mankrik, 5,868 rows), cautious basis:

| Bag | Profit | Label |
| --- | --- | --- |
| Runecloth Bag | 73s 37c | potential craft |
| Woolen Bag | — | negative margin |
| Mageweave Bag | — | negative margin |

On the listed basis, Runecloth Bag shows 2g 50s 69c, because the cheapest Runecloth listing is far below its market value.

Addon import dry run (2026-10-04, on copies of `data/brownstone.duckdb` at version 2 and the real scan file; originals unchanged):

- **Timings:** the 24 MB file parses in 0.88 s. Unit and item prices take 0.05 s. The full import takes 1.22 s, including bronze copy, migration 2→3 and DuckDB load. A re-import takes 0.97 s and skips both scans as duplicates without copying the bytes again.
- **Scan `20261004T164730Z-c651bd`:** completed, imported. 101,485 listings (702,427 units), 28,105 of them stacks, giving 2,927 items. Non-exact stacks: 0. 4 listings had no buyout.
- **Scan `20261004T165015Z-02d971`:** stopped (throttled), 0 listings. Recorded as `empty`, not priced.
- **Existing data:** all 24,020 existing rows kept. Database 2.1 MB → 6.8 MB.

| Item | Listings / units | Min buyout | Market value |
| --- | --- | --- | --- |
| Runecloth (14047, shown as `Item 14047`) | 2 / 4 | 2g 55s | 2g 55s |
| Bolt of Runecloth | 35 / 142 | 86s 95c | 87s |
| Runecloth Bag | none | — | — |
| Rugged Leather | 19 / 110 | 5s | 5s |
| Wool Cloth | 99 / 2,652 | 83c | 84c |
| Mageweave Cloth | 79 / 203 | 35s 94c | 43s 94c |

The Forever Action Board labels Runecloth Bag **missing prices**, because there's no bag listing. Its cautious craft cost is 4g 95s, buying bolts (87s) rather than crafting them from 2g 55s Runecloth.
