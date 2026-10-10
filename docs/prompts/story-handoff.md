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
| STORY-043 | Reworked 2026-10-09: statuses Known / Train now / Not yet / Unknown. Matching rule by IDs only, recorded under a new `today_version`. Read STORY-049's real beta evidence first (Claude's review notes in `status.md`) to see which IDs the client reports. Calculation in `brownstone/`, display in `views/today.py`; ranking and sizing unchanged within the filtered set. |
| STORY-045 | Display only in `views/scan_import.py`; don't change preview, stale checks, import or the CLI. Small summary helpers may go in `brownstone/` if they need no Streamlit. Keep both the single-file and drop-folder paths. |
| STORY-046 | Rules over values Today already computes; no change to ranking, sizing or which rows appear (apart from the optional Low filter). Every threshold named in `requirements.md` under a new `today_version`. |
| STORY-047 | Two parts: first the generator change (`brownstone/recipe_import.py`: `skillup_colors` and `page_coverage` from the saved page, validated in `crafting.py`), then regenerate catalogs from the archived pages under `data/recipe-sources/` and confirm each diff holds only the new fields and the version bump; then the map in `brownstone/skillups.py` and `views/skillups.py`. Expand intermediates with `material_plan`; no cross-profession chains. Market context is optional and read-only (ADDON-10 metrics). Must be usable before 4 November. |
| STORY-048 | Calculation in a new `brownstone/watchlist.py`, display in `views/watchlist.py`, plus small panels in `views/today.py` and `views/scan_import.py`. Store like Today settings (`brownstone/today_settings.py`: atomic `.tmp` write, ignored file per source); add the pattern to `.gitignore`. Reuse `today_data.read_skillup_market`, `metrics.units_below_price` and `freshness.py` rather than a new price query; parse money with `money.parse_money`, integer copper. Newest snapshot of the selected source and full market only. Don't change Today's numbers or the import. Take a screenshot of the page for the report if you can. |
| STORY-049 | Addon first: a guarded `C_TradeSkillUI` reader beside STORY-041's legacy `professions.window` in `addon/BrownstoneScan/BrownstoneScan.lua`; keep the legacy path and its tests. Function names in the story are candidates, not facts: guard every call and record which exist (API inventory). Only `learned == true` is known. The *seen crafted* projection reads existing journal entries in `brownstone/`. Checklist in play actions only; the product owner plays, Claude checks the file. |
| STORY-050 | Generator change in `brownstone/recipe_import.py` (fields from the saved page's `source` and `trainingcost`), validated in `crafting.py`; then regenerate every catalog from `data/recipe-sources/` and confirm each diff holds only the new fields and the version bump. Record the source-code table with its evidence in `requirements.md` → CRAFT-08. |
| STORY-051 | Brownstone only, from imported snapshots and journals. Calculation in a new `brownstone/characters.py` built on the existing `character_snapshots` and `professions` projections (refactor them into data plus display shaping; the addon import page's tables stay unchanged); display in `views/characters.py`. Scope by source and full market keys; never pool sources. Unknown is never 0. Don't assume tier level requirements. Make it visual with Streamlit 1.65 and Altair only: no new packages, no HTML/CSS injection. Take a screenshot of the page for the report if you can. |
| STORY-052 | Reuse Today's per-craft profit rules and STORY-047's `skillup_colors`; don't add a second pricing path. Estimates are labelled as such; missing prices make an estimate incomplete, never free. Rules in a new CRAFT entry in `requirements.md`. |
