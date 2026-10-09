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
| STORY-039 | Builds on STORY-038's row selection and existing reserved `purchases`. Re-reserve listings in plan order through the existing ladder code in `brownstone/today.py`; never quote twice. Calculation in `brownstone/`, display in `views/today.py`. The queue's craft order comes from the chosen catalog route; ticks live in Streamlit session state only. New `today_version` for the refill rule. |
| STORY-045 | Display only in `views/scan_import.py`; don't change preview, stale checks, import or the CLI. Small summary helpers may go in `brownstone/` if they need no Streamlit. Keep both the single-file and drop-folder paths. |
| STORY-046 | Rules over values Today already computes; no change to ranking, sizing or which rows appear (apart from the optional Low filter). Every threshold named in `requirements.md` under a new `today_version`. |
| STORY-047 | Two parts: first the generator change (`brownstone/recipe_import.py`: `skillup_colors` and `page_coverage` from the saved page, validated in `crafting.py`), then regenerate catalogs from the archived pages under `data/recipe-sources/` and confirm each diff holds only the new fields and the version bump; then the map in `brownstone/skillups.py` and `views/skillups.py`. Expand intermediates with `material_plan`; no cross-profession chains. Market context is optional and read-only (ADDON-10 metrics). Must be usable before 4 November. |
| STORY-048 | Stored like Today settings (atomic write, ignored file per source); add the pattern to `.gitignore`. Prices via `money.py`, integer copper. Lowest price and units from the newest scan of the selected source only. |
