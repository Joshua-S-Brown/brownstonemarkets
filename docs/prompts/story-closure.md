# Story closure prompt

Paste this into the **same session** that implemented the story, once you're happy with the behaviour and before you commit. That session already knows the change, so closing there is cheaper than starting a new one. The review step works on the uncommitted diff, so nothing should be committed yet.

```text
Close out this story before I commit. Work through these steps in order and report briefly at the end.

1. Acceptance. Re-read the story in docs/backlog.md and check each acceptance criterion against the code and tests. List each one as met (with the evidence: a test name or a command result) or not met. Fix anything not met, or tell me why it shouldn't be.
2. Review. Run /code-review high on the uncommitted changes. Fix confirmed bugs. List anything plausible but unconfirmed for me rather than guessing.
3. Simplify. Run /simplify on the same changes: duplication, reuse of existing helpers, over-complicated code. Keep behaviour identical.
4. Gates. These must all pass:
   - .venv/bin/python -m pytest -p no:cacheprovider --cov, at or above the coverage floor, with the story's new code covered by tests;
   - .venv/bin/python -m ruff check ., with no new noqa comments;
   - .venv/bin/python -m mypy.
   Any new package must be declared in pyproject.toml and pinned in requirements.lock.txt.
5. Real data. If the story touches ingestion, storage or calculations, run it against copies of data/brownstone.duckdb and any relevant raw files, never the originals, and report the results.
6. Docs. Bring them in line with the code, each fact in one place:
   - requirements.md: rules and decisions;
   - design.md: structure and contracts, including the complexity and coverage debt lists if they changed;
   - status.md: current state only, with the expected test count;
   - backlog.md: remove the finished story, put follow-ups under Later, and leave other stories alone unless this one changed them;
   - AGENTS.md: only if a working rule changed.
7. Hand-off. Tell me:
   - what changed, in a few lines;
   - anything left open;
   - files to commit, and any to leave out (data, local config, .DS_Store);
   - a suggested commit message.
   Don't commit, and don't send updates to other sessions: the docs are the hand-off.
```
