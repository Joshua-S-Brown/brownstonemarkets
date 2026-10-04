# Full project audit prompt

Use this at milestones: every 3–5 stories, and before the WoW Forever launch on 4 November 2026. Start a **new session** with a strong model (Opus) and commit everything first, so the audit's changes are reviewable on their own.

```text
Read AGENTS.md, docs/design.md (including Known design debt) and docs/status.md. Then audit the whole codebase: brownstone/, views/, app.py, launch.py, addon/ and tests/.

Look for, ranked by impact:
1. Bugs and data risks: wrong market or source joins, prices treated as free, rounding outside integer copper, freshness mistakes, and migrations or imports that could lose or duplicate data.
2. Duplication: logic repeated across modules that should share one helper, and views doing calculations that belong in brownstone/.
3. Complexity debt: the functions listed in design.md with # noqa: C901. Refactor the ones where splitting clearly helps readability, remove their noqa, and keep behaviour identical, with tests proving it.
4. Performance at real sizes: 24 MB scan files, about 100,000 listings per scan, several scans, and the TSM CSVs. Measure before changing anything.
5. Test gaps: run pytest --cov and cover the risky untested paths. Raise the fail_under floor in pyproject.toml if coverage rises.
6. Docs drift: anything in AGENTS.md, README.md or docs/ that no longer matches the code. Keep AGENTS.md short (rules and pointers only), and make sure each fact lives in one place.
7. Dead code, unused config and stale comments.

Rules:
- Fix only clear, low-risk findings. List everything else for me with file:line, the impact and a suggested fix.
- No behaviour or scope changes without asking.
- Run anything touching real data against copies only.
- At the end: pytest --cov at or above the floor, ruff check . and mypy must pass, and the docs must be updated.
- Leave everything uncommitted. Give me a summary, the list of open findings and a suggested commit message.
```
