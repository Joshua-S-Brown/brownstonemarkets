# Story handoff prompt

Paste this into a **new** implementation session (GPT/Codex or Claude) to build one backlog story. Replace `STORY-XXX`; everything else the session needs is in the story itself (decisions, evidence, code pointers, expected real-data numbers), so put implementation notes there when refining it, not here. Bring the report back to a Claude session for review.

```text
Implement STORY-XXX from docs/backlog.md in this repo.

Read AGENTS.md first and follow it. Then print the story with `python -m brownstone rules --story STORY-XXX`. Don't read docs/backlog.md, docs/requirements.md or docs/design.md whole: print the rules and design sections the story names with `python -m brownstone rules <RULE_ID>... --design "<heading>"` (`--list` shows every rule ID and heading). Look up any other rule you touch the same way. Don't restate or change rules beyond what the story asks; record new rules where the story says.

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
