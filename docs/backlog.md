# Brownstone Markets backlog

This is the single view of planned product work. `requirements.md` records accepted behavior and constraints, `design.md` records architecture, and `status.md` records what is already implemented. Move a story here when its priority changes; do not use the README or chat history as a competing backlog.

## Workflow

- **Now**: one active milestone with agreed acceptance criteria.
- **Next**: ordered candidates that are ready after the active milestone.
- **Later**: valuable work that is intentionally not scheduled.
- A story moves to `status.md` when implemented and verified.
- Add durable behavior to `requirements.md` when a story is accepted or clarified.

Suggested story format:

> As a `<user>`, I want `<capability>` so that `<outcome>`.
>
> Acceptance: observable conditions that prove the story is complete.

## Completed

- STORY-001/002 — Classic Tailoring Action Board (2026-10-04).
- Review follow-up (2026-10-04): cautious price basis, money standard, configuration-driven board, single freshness policy, split interface, launcher restart, cross-platform CI, documentation rewrite.

Details are in `status.md` and Git history; rules are in `requirements.md`.

## Now

No active milestone. STORY-007 is a small prerequisite before acting on board results; STORY-003 is the next feature candidate.

## Next

### STORY-007 — Verify the representative Classic catalog

As a gold maker, I want the recipe quantities and vendor prices behind the board checked against Classic Era sources so that a data-entry error does not change the ranking.

Acceptance:

- For each of the three bags and their bolts, confirm recipe ID, output quantity and every reagent quantity against a Classic Era recipe (spell) page; record the checked URL and date on the recipe.
- Confirm Fine Thread, Silken Thread and Rune Thread vendor prices against a Classic Era item or vendor page; add a separate vendor-price source URL per thread instead of reusing the item link.
- Use spell pages for recipe provenance and item pages for item provenance consistently.
- Record discrepancies and corrections in `status.md`; bump `catalog_version` if any value changes.

### STORY-003 — Add demand context

Ingest compatible Classic regional item statistics separately from realm prices. Show sale rate and sold-per-day as demand context with independent timestamps and provenance; do not present them as guaranteed sales.

### STORY-004 — Normalize the recipe catalog

Create versioned DuckDB item, recipe, input and output tables plus a repeatable, provenance-bearing import path. Preserve the hand-authored proof as a fixture and do not bulk-import until source licensing, version identity and validation are understood.

### STORY-005 — Expand Classic Tailoring coverage

Import the remaining supported Classic Tailoring recipes after the normalized catalog path is proven. Provide profession, category and name filters without loading the full catalog into the interface at once.

### STORY-006 — Replay and rebuild local data

Reprocess preserved bronze snapshots and rebuild derived storage deterministically after schema or validation changes. Keep the original bytes and manifests immutable.

## Later

- Build history-based price movement, volatility and confidence after enough distinct observations exist.
- Backtest ranking policies without future-data leakage.
- Automate collection and choose backup/retention storage independently of Git.
- Activate WoW Forever when a reliable compatible price feed and launch market exist. Follow `design.md` → *Switching to WoW Forever*.
- Technical debt: typed `Source`/`Market` model, explicit DuckDB DDL with a schema version (before STORY-004/006), Ruff and mypy in CI.
- Decide whether to remove the Retail regression sources.
- Evaluate addon or personal transaction ingestion as a separate privacy-sensitive data source.
- Consider alerts only after opportunity and confidence policies are stable.

## Explicitly out of scope for now

- Automated buying, selling or in-game actions.
- AI-generated trade recommendations without explainable features.
- Cloud deployment or scheduling before replay, recovery and storage decisions.
