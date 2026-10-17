# Full project audit prompt

Use this at milestones: every 3–5 stories, and before the WoW Forever launch on 4 November 2026. Start a **new session** with a strong model (Opus) and commit everything first, so the audit's changes are reviewable on their own.

```text
Read AGENTS.md, docs/design.md (including Known design debt) and docs/status.md. For requirements, start from `python -m brownstone rules --list` and print the rules each module relies on with `python -m brownstone rules <RULE_ID>...`; read docs/requirements.md whole only for the docs-bloat step. Then run `git describe --tags --match 'audit-*' --abbrev=0`. If a tag exists, run `git diff --stat <that tag>..HEAD` and review those changes line by line first, since that is where new risk is; if none exists, this is the first audit and everything is new. Then audit the whole codebase: brownstone/, views/, brownstone_app.py, launch_app.py, addon/ and tests/. Unchanged code still gets read, because duplication, layering and docs drift only show across modules.

This audit's main goal is to cut bloat: less code, fewer tests and shorter docs for the same behaviour. Report the line counts of brownstone/, views/, tests/ and docs/ before and after.

Look for, ranked by impact:
1. Bugs and data risks: wrong market or source joins, prices treated as free, rounding outside integer copper, freshness mistakes, and migrations or imports that could lose or duplicate data.
2. Duplication: logic repeated across modules that should share one helper, views doing calculations that belong in brownstone/, and display logic repeated across views/today_rows.py that should live once in views/today_rows.py.
3. Dead code: functions, parameters, config keys, settings fields and branches nothing reaches, code left over from spikes and trials (SPIKE-009/009b), and stale comments. Prove each is unused (grep, coverage) before removing it.
4. Test bloat: tests that duplicate each other, test the same path through two apps, test framework behaviour rather than ours, or carry large inline fixtures that a shared helper could build. Merge or remove them without losing coverage of scope, units, freshness, deduplication and recipe quantities. Coverage must stay at or above the floor.
5. Docs bloat: status.md must describe now, so move history out (Git has it); requirements.md holds each rule once; design.md holds structure and contracts, not narrative; backlog.md drops finished stories' full text where the docs already record the outcome. Keep AGENTS.md short (rules and pointers only), and make sure each fact lives in one place. Check that what remains matches the code.
6. Complexity debt: the exemptions listed in design.md. Refactor where splitting clearly helps readability and keep behaviour identical, with tests proving it.
7. Performance at real sizes: 24 MB scan files, about 100,000 listings per scan, several scans, and the TSM CSVs. Measure before changing anything.

Rules:
- Fix only clear, low-risk findings. List everything else for me with file:line, the impact and a suggested fix.
- No behaviour or scope changes without asking. There is one app (UI-07 in docs/requirements.md); don't remove or add places, list any you think should change as a finding for me to decide.
- Run anything touching real data against copies only.
- At the end: `.venv/bin/python -m brownstone gates` must pass and the docs must be updated.
- Leave everything uncommitted. Give me a summary, the before/after line counts, the list of open findings, a suggested commit message, and the tag to create after I commit: `git tag audit-<YYYY-MM-DD>`.
```
