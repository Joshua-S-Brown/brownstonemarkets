# Story handoff prompt

Paste this into a **new** implementation session (GPT/Codex or Claude) to build one backlog story. Replace `STORY-XXX` and the title, and paste the story's notes from the table below into the *Notes* line. Bring the report back to a Claude session for review.

```text
Implement STORY-XXX (<title>) from docs/backlog.md in this repo.

Read AGENTS.md first and follow it. Then read STORY-XXX in docs/backlog.md and the rules it names in docs/requirements.md, plus the matching sections of docs/design.md. Don't restate or change rules beyond what the story asks; record new rules where the story says.

Notes: <story notes from docs/prompts/story-handoff.md>

Add the offline tests the story lists. Finish with `pytest --cov` (at or above the coverage floor), `ruff check .` and `mypy` passing, with no new noqa comments. Don't commit.

Report back with:
1. Summary of the change
2. Files changed
3. Each acceptance criterion with the test that proves it
4. Gate results (pytest/coverage, ruff, mypy)
5. A real-data check against the Forever beta source (config/market.local.toml), using a copy of data/ if anything writes; describe what the page shows
6. Deviations from the story and why
7. Open risks
8. A suggested commit message
```

## Story notes

| Story | Notes |
| --- | --- |
| STORY-027 | Refined 2026-10-13: 12-hour maximum gap and a time-left split, both decided by the owner. New `brownstone/removed_listings.py` reads `scan_listings` under `scope_predicate` and reuses `scan_changes.eligible_scans` and its legacy match rule; no schema change, no new price path. Display extends `views/nicegui_market.py` (look at it and `views/nicegui_theme.py` first); compute an item's removals only when its page opens. The time-left bucket durations are a new rule: cite a source (e.g. the WoW API documentation for `GetAuctionItemTimeLeft`), say whether it is for Classic Era or Forever, and add a beta check if it isn't Forever's. Never call anything *sold*. Keep functions within Ruff's complexity limit. |
| STORY-055 | Rewritten 2026-10-12 as the Market explorer, in the new app. New `brownstone/market_explorer.py` composes existing outputs only (`analysis.browse`, `crafting.material_plan`, `action_board.rank_catalogs`, `today_characters`, `skillups`, `scan_changes`); no new price query. Display in a new `views/nicegui_market.py`, built with `views/nicegui_theme.py` like Today, Team and Data (look at them first); item pages addressable in the URL so a refresh keeps the item. Keep functions within Ruff's complexity limit and add the new view to mypy's files in `pyproject.toml`. Integer copper throughout; same source and full market for both scans. |
