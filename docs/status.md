# Session handoff — 2026-10-04

This file records implemented state and verification. Use `backlog.md` for planned work, `requirements.md` for accepted behavior, `design.md` for architecture and README.md for setup.

## Implemented

- Local raw archive, validated silver Parquet, DuckDB and gold ranking; Streamlit UI and localhost launcher.
- Area 52 realm and US regional commodity sources with independent selection, refresh and freshness.
- Browse market separate from Opportunities; commodity labels do not imply material categories.
- Focused config, sources, normalization, storage and analysis modules; pipeline orchestrates.
- Additive migration and same-market/time/hash analytical deduplication; raw/silver collections still preserved.
- GitHub origin configured. Baseline commit e400ed6 and offline CI exist. User explicitly requested committing and pushing the coverage milestone for cloning to a Mac; Mac setup and a launcher are included in that publication.
- Tailoring is the first crafting slice. Separate provenance-bearing Classic Era and Forever catalogs record Runecloth Bag and Bolt of Runecloth; calculation code expands intermediates, chooses buy versus craft, uses vendor fallback and rejects missing prices.
- The Crafting workspace exposes the catalog, direct recipe and expanded base materials. It prevents profit calculation when the selected market game version does not match the catalog. Mankrik Alliance Classic Era is configured as the Alliance-heavy development market, with a separately sourced Classic catalog.
- The live Mankrik feed contains 5,868 rows and all Runecloth Bag materials, but supplies a blank `updatedAt` column. The source-specific policy preserves upstream time as unknown, labels freshness from collection time and uses null-safe content deduplication; Retail validation remains strict.

## Limitations and recovery

- The legacy discount screen is not useful for the current Classic feed because historical values are zero. The Action Board covers three representative bags, not the complete profession. Listing depth, deposits, demand, sale speed and recommended quantities are not modeled. Vendor stock and reputation discounts are assumptions.
- Legacy rows have no source hash and are not retroactively deduplicated. Only known v0.1 Area 52 identity is backfilled; unknown markets stay unclassified.
- Duplicate collections use analytical_snapshot_id from the manifest. Changed content at the same upstream time is retained as a correction; future features must choose one correction per scan.
- Old silver schema remains unchanged. Use schema alignment/union-by-name when combining Parquet history.
- Database writes are transactional, but silver/database/gold are not one atomic operation. Failure after commit needs reconciliation; no automatic replay/rebuild tool yet.
- One writer at a time. Concurrent refresh can fail with a lock; prior completed data remains available.
- GitHub HTTPS verification initially hit a Windows schannel error in this tool environment. Read-only remote verification succeeded using OpenSSL; this repo now has a local OpenSSL setting. The remote had no advertised refs. No push was performed. User uses VS Code for commits/pushes.
- Bundled Python backs this local environment; other machines need normal Python 3.11+. Recreate .venv after relocation.

## Classic Tailoring Action Board v0.1 — complete

- STORY-001 and STORY-002 implemented for Mankrik Alliance Classic Era. The default Classic Crafting view ranks Woolen Bag, Mageweave Bag and Runecloth Bag by profit or margin, with complete economics and conservative missing/stale/negative/potential labels.
- Catalog version 0.1 records sourced representative coverage and verification date. Classic Runecloth bolt was corrected from four to five cloth using the Classic recipe source; one bag now expands to 25 Runecloth, two Rugged Leather and one Rune Thread. Forever remains a separate unchanged proof.
- Detail shows direct ingredients, unit/total buy/craft/vendor choices, all-craft expanded quantities, selected-route shopping costs, break-even output price and catalog/snapshot source, hash, analytical identity and freshness assumptions.
- Calculations and policy remain outside Streamlit. Scoped storage reads and policy checks enforce the full Mankrik Alliance Classic identity. Retail configuration, browsing, ranking and ingestion remain supported.
- All changes are uncommitted for user review; no live collection, scheduling, bulk catalog import or deployment was performed.

## Next

No active milestone. STORY-003 (separate compatible regional demand context) is the next backlog candidate; normalized recipe import, broader catalog coverage and replay/rebuild follow. Retail remains supported; Forever waits for reliable pricing.

## Verification

From the project folder: `.venv\Scripts\python.exe -m pytest -p no:cacheprovider`.
Commodity run: `.venv\Scripts\python.exe -m brownstone --market retail-us-commodities`.
Browser: Start Brownstone.cmd. Tests are offline; live ingestion is a separate check.

Latest validation: **42 offline tests pass** using `.venv/bin/python -m pytest -p no:cacheprovider`. Tests cover ranking by both metrics, deterministic ties, market/version isolation, freshness boundaries and future timestamps, missing/zero prices, recipe quantities, vendor versus buy/craft routes, multi-output units, selected shopping costs and copper rounding. Streamlit AppTest exercises an isolated saved Classic snapshot, margin reordering, calculation detail and switching back to Retail browsing. The prior 26-test ingestion/deduplication/launcher regression suite still passes. No live download is needed for these checks.

Historical live validation: the prior Mankrik ingestion contained 5,868 rows and identical downloads reused one analytical snapshot. The earlier 1.5778g Runecloth Bag cost and 2.7064g profit used the now-corrected four-cloth Classic bolt recipe and must not be reused as valid Classic estimates. Earlier Retail ingestion observed 10,992 commodity rows and 18,152 Area 52 rows. Raw bytes and manifests remain untouched.
