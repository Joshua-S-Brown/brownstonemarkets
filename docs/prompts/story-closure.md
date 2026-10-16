# Story closure prompt

Paste this into the **same session** that implemented the story (for a GPT/Codex implementation, use `story-review.md` instead), once you're happy with the behaviour and before you commit. That session already knows the change, so closing there is cheaper than starting a new one. The review step works on the uncommitted diff, so nothing should be committed yet.

```text
Close out this story before I commit. Work through these steps in order and report briefly at the end.

1. Acceptance. Re-read the story and the rules and design sections it names with `python -m brownstone rules --story <STORY_ID> <RULE_ID>... --design "<heading>"` rather than whole files, and check each acceptance criterion against the code and tests. List each one as met (with the evidence: a test name or a command result) or not met. Fix anything not met, or tell me why it shouldn't be.
2. Review. Run /code-review high on the uncommitted changes. Fix confirmed bugs. List anything plausible but unconfirmed for me rather than guessing.
3. Simplify. Run /simplify on the same changes: duplication, reuse of existing helpers, over-complicated code. Keep behaviour identical.
4. Gates. `.venv/bin/python -m brownstone gates` must pass (ruff, mypy, then parallel pytest with coverage at or above the floor), with no new noqa comments and the story's new code covered by tests. Report its summary, including the document headroom.
   Any new package must be declared in pyproject.toml and pinned in requirements.lock.txt.
5. Real data. If the story touches ingestion, storage or calculations, run it against copies of data/brownstone.duckdb and any relevant raw files, never the originals, and report the results.
6. Docs. Bring them in line with the code, each fact in one place:
   - requirements.md: rules and decisions (edit the file; `python -m brownstone rules <RULE_ID>` afterwards shows the rule as a session will read it);
   - design.md: structure and contracts, including the complexity and coverage debt lists if they changed;
   - status.md: current state only, with the expected test count;
   - backlog.md: run `python -m brownstone close-story <STORY_ID>` (removes the section, adds it to *Done*, renumbers *Order*), put follow-ups under Later, and leave other stories alone unless this one changed them;
   - AGENTS.md: only if a working rule changed.
7. Hand-off. Tell me:
   - what changed, in a few lines;
   - anything left open;
   - files to commit, and any to leave out (data, local config, .DS_Store);
   - a suggested commit message.
   Don't commit, and don't send updates to other sessions: the docs are the hand-off.
```
