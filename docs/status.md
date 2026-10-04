# Status

Current implemented state, limitations and how to verify. History lives in Git; keep this file describing *now*.

_Last updated 2026-10-04._

## Implemented

- **Ingestion:** TSM CSV → bronze/silver/DuckDB/gold with manifests, validation and analytical deduplication. Sources: Mankrik Alliance Classic Era (development stand-in), plus Retail Area 52 and US commodities (regression only).
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
- **Storage:** explicit DuckDB schema, version 2, with backed-up, idempotent migrations.
  - The app upgrades the database on startup. On 2026-10-04 the live database went from version 0 to 2, with `data/brownstone.v0.backup.duckdb` kept. All 24,020 rows were kept and the board was unchanged.
  - A dry run on a copy kept all 24,020 rows and split Mankrik's realm and faction correctly. The board gave identical results.
  - Re-importing an old raw file was recognised as a duplicate.
  - Old manifests are read through an adapter and never edited.
- **Quality gates:** CI runs Ruff, mypy and the tests on macOS and Windows from the lock file, including the Streamlit UI test. Config loads into typed, individually validated `Source` records.

- **Scanning addon (SPIKE-008, done):** `addon/BrownstoneScan/` is a read-only addon that scans on a click or `/bscan start` and saves listings to SavedVariables (`schema_version` 1; sample at `tests/fixtures/brownstone_scan_sample.lua`; install and measurements in `addon/README.md`). Verified on the Forever beta, build 70205, interface 16001: one full scan of the Stormwind Alliance Normal house, 101,485 listings in about 10.6 s, 24 MB file, written correctly. Decision and format are in `requirements.md`. Nothing imports scans yet (STORY-010).
  - **Real scan kept** at `data/inbox/addon-scans/BrownstoneScan-forever-beta-2026-10-04.lua`. That's a byte-for-byte copy (SHA-256 `207a2b95…`) of the game's SavedVariables file: scan `20261004T164730Z-c651bd`, Alliance Normal house. It's ignored by Git like all of `data/`, so back it up with `data/`.

## Limitations

- The addon was measured on one beta house only: not the Roleplaying or a neutral house, and `/bscan start` without the button is untested. Beta region and realm values are generic, so scans are identified by auctioneer, zone and label. The `.toc` interface number 16001 may change with beta builds.
- Required skill levels are display-only. Three are sourced: Woolen Bag 80, Mageweave Bag 225, Bolt of Runecloth 250. Three are unconfirmed and marked `required_skill_verified = false`: Runecloth Bag 260, Bolt of Woolen Cloth 75, Bolt of Mageweave 175.
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

Expected: 79 tests pass, offline; `ruff check .` and `mypy` report no issues. Windows uses `.venv\Scripts\python.exe`. Live ingestion is a separate manual check: **Refresh from TSM** in the app.

Last live check (2026-10-04, Mankrik, 5,868 rows), cautious basis:

| Bag | Profit | Label |
| --- | --- | --- |
| Runecloth Bag | 73s 37c | potential craft |
| Woolen Bag | — | negative margin |
| Mageweave Bag | — | negative margin |

On the listed basis, Runecloth Bag shows 2g 50s 69c, because the cheapest Runecloth listing is far below its market value.
