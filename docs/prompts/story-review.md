# Story review prompt

Paste this into a **Claude** session together with the implementation report from `story-handoff.md` (GPT/Codex's 8-part report). Claude checks the uncommitted change, fixes what it can confirm and closes the story. In Claude Code the `/review-story` skill loads this file. Nothing is committed: the user commits.

```text
Review the implementation of <STORY_ID> below, then close it. Follow AGENTS.md. Report briefly at the end.

1. Look up. Print the story and what it names: `python -m brownstone rules --story <STORY_ID> <RULE_ID>... --design "<heading>"`. Don't read backlog.md, requirements.md or design.md whole.
2. Read the change: `git status`, `git diff` and every new file. Treat the report as claims to check, not evidence.
3. Acceptance. For each criterion, find the test that proves it and read it: met (test name) or not met.
4. Rules. Check the change against AGENTS.md, especially:
   - scope: reads go through `storage.scope_predicate` (source plus full MARKET_KEYS), and metrics reads match `metrics_version`;
   - ADDON-08 identity: `item_id, variant_id, variant_state`, never item ID alone;
   - integer copper in calculations, gold only via `money.py` in views;
   - missing or zero prices are gaps, never free or 0;
   - real-data access is read-only, or writes only to a copy of data/.
   - size: flag code or tests the story doesn't need (unused options, helpers with one caller, tests that duplicate others or read source text) as findings and remove them.
5. Gates: `.venv/bin/python -m brownstone gates` (ruff, mypy, parallel tests at or above the coverage floor), plus `/code-review high` on the diff.
6. Real data. Re-run the story's real-data check (its expected numbers) against the configured Forever source, read-only or on a copy of data/, and compare with the report. For a story that changes a web page, compare its 1280 and 390 px screenshots with the matching prototype view (`docs/prototype/web-app.html`, UI-18) and treat unexplained structural gaps as findings; otherwise look at screenshots only where the story asks.
7. Fix confirmed findings and re-run the gates. List plausible but unconfirmed ones for me rather than guessing.
8. Close. Run `python -m brownstone close-story <STORY_ID>` (removes the section, adds it to *Done*, renumbers *Order*), put follow-ups under Later, and update requirements.md, design.md and status.md as `story-closure.md` step 6 says.
9. Hand-off: what changed, findings fixed, findings left for me, files to commit (and any to leave out), and a suggested commit message. Don't commit.

<paste the implementation report here>
```
