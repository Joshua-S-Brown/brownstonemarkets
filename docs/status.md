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

- The legacy discount screen is not useful for the current Classic feed because its historical values are zero. Crafting estimates cover only the hand-authored Runecloth Bag proof; broader recipes, listing depth, deposit costs, sale speed and recommended quantities are not modeled.
- Legacy rows have no source hash and are not retroactively deduplicated. Only known v0.1 Area 52 identity is backfilled; unknown markets stay unclassified.
- Duplicate collections use analytical_snapshot_id from the manifest. Changed content at the same upstream time is retained as a correction; future features must choose one correction per scan.
- Old silver schema remains unchanged. Use schema alignment/union-by-name when combining Parquet history.
- Database writes are transactional, but silver/database/gold are not one atomic operation. Failure after commit needs reconciliation; no automatic replay/rebuild tool yet.
- One writer at a time. Concurrent refresh can fail with a lock; prior completed data remains available.
- GitHub HTTPS verification initially hit a Windows schannel error in this tool environment. Read-only remote verification succeeded using OpenSSL; this repo now has a local OpenSSL setting. The remote had no advertised refs. No push was performed. User uses VS Code for commits/pushes.
- Bundled Python backs this local environment; other machines need normal Python 3.11+. Recreate .venv after relocation.

## Next

Implement the **Classic Tailoring Action Board v0.1** in `backlog.md`: add a small sourced set of Classic bags, rank complete estimates by profit and margin, explain material choices and label missing or stale evidence. Demand context, normalized bulk recipe import and replay/rebuild follow in backlog order. Retail remains supported but receives no near-term feature work; Forever waits for reliable pricing.

## Verification

From the project folder: `.venv\Scripts\python.exe -m pytest -p no:cacheprovider`.
Commodity run: `.venv\Scripts\python.exe -m brownstone --market retail-us-commodities`.
Browser: Start Brownstone.cmd. Tests are offline; live ingestion is a separate check.

Latest validation: 26 offline tests pass. Live Mankrik ingestion completed with 5,868 rows and repeated identical downloads reused one analytical snapshot. The preserved response also replayed twice into a temporary database and calculated a 1.5778g Runecloth Bag craft cost versus a 4.5097g observed minimum buyout and 2.7064g estimated profit after the 5% cut. The earlier live commodity ingestion produced 10,992 rows, and Mac setup ingested 18,152 Area 52 rows. Crafting tests cover version separation, Runecloth Bag expansion, buy-versus-craft choice, vendor thread cost, missing prices and cycle rejection.
