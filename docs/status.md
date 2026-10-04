# Session handoff â€” 2026-10-04

Read requirements.md for product decisions, design.md for architecture and README.md for setup. Update this file after milestones.

## Implemented

- Local raw archive, validated silver Parquet, DuckDB and gold ranking; Streamlit UI and localhost launcher.
- Area 52 realm and US regional commodity sources with independent selection, refresh and freshness.
- Browse market separate from Opportunities; commodity labels do not imply material categories.
- Focused config, sources, normalization, storage and analysis modules; pipeline orchestrates.
- Additive migration and same-market/time/hash analytical deduplication; raw/silver collections still preserved.
- GitHub origin configured. Baseline commit e400ed6 and offline CI exist. User explicitly requested committing and pushing the coverage milestone for cloning to a Mac; Mac setup and a launcher are included in that publication.

## Limitations and recovery

- Discount is not liquidity-adjusted profit. Categories, recipes, quantities, deposit costs and sale speed are not modeled.
- Legacy rows have no source hash and are not retroactively deduplicated. Only known v0.1 Area 52 identity is backfilled; unknown markets stay unclassified.
- Duplicate collections use analytical_snapshot_id from the manifest. Changed content at the same upstream time is retained as a correction; future features must choose one correction per scan.
- Old silver schema remains unchanged. Use schema alignment/union-by-name when combining Parquet history.
- Database writes are transactional, but silver/database/gold are not one atomic operation. Failure after commit needs reconciliation; no automatic replay/rebuild tool yet.
- One writer at a time. Concurrent refresh can fail with a lock; prior completed data remains available.
- GitHub HTTPS verification initially hit a Windows schannel error in this tool environment. Read-only remote verification succeeded using OpenSSL; this repo now has a local OpenSSL setting. The remote had no advertised refs. No push was performed. User uses VS Code for commits/pushes.
- Bundled Python backs this local environment; other machines need normal Python 3.11+. Recreate .venv after relocation.

## Next

Select a profession and sourced catalog/recipes for a small actual crafting chain. Before automation add replay/recovery and choose backup storage. Don't schedule collection or create a generic framework without those decisions.

## Verification

From the project folder: `.venv\Scripts\python.exe -m pytest -p no:cacheprovider`.
Commodity run: `.venv\Scripts\python.exe -m brownstone --market retail-us-commodities`.
Browser: Start Brownstone.cmd. Tests are offline; live ingestion is a separate check.

Latest validation: 18 offline tests pass; live commodity ingestion produced 10,992 rows. Interface checks verified commodity selection and Mageweave browsing.
