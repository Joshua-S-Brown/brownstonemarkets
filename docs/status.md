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
- **Storage:** explicit DuckDB schema, version 1, with ordered one-time migrations. Your existing database migrates on its next Refresh; a dry run on a copy kept all 24,020 rows.
- **Quality gates:** CI runs Ruff, mypy and the tests on macOS and Windows from the lock file, including the Streamlit UI test. Config loads into typed, individually validated `Source` records.

## Limitations

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

Expected: 64 tests pass, offline; `ruff check .` and `mypy` report no issues. Windows uses `.venv\Scripts\python.exe`. Live ingestion is a separate manual check: **Refresh from TSM** in the app.

Last live check (2026-10-04, Mankrik, 5,868 rows), cautious basis:

| Bag | Profit | Label |
| --- | --- | --- |
| Runecloth Bag | 73s 37c | potential craft |
| Woolen Bag | — | negative margin |
| Mageweave Bag | — | negative margin |

On the listed basis, Runecloth Bag shows 2g 50s 69c, because the cheapest Runecloth listing is far below its market value.
