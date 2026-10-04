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

## Completed — Classic Tailoring Action Board v0.1

STORY-001 (rank crafting opportunities) and STORY-002 (explain each calculation) are implemented and verified on 2026-10-04. Completion evidence and limitations live in `status.md`; durable behavior is recorded in `requirements.md`.

## Now

No active milestone. The next ready candidate is STORY-003; implementation is not yet scheduled.

## Next

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
- Activate WoW Forever only when a reliable compatible price feed and launch market scope exist.
- Evaluate addon or personal transaction ingestion as a separate privacy-sensitive data source.
- Consider alerts only after opportunity and confidence policies are stable.

## Explicitly out of scope for now

- Automated buying, selling or in-game actions.
- AI-generated trade recommendations without explainable features.
- Cloud deployment or scheduling before replay, recovery and storage decisions.
