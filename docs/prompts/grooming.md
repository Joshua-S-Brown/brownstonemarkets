# Backlog grooming prompt

Use this between stories, when the backlog's Next list is thin or the direction may have shifted (after a launch, a new data source, or a run of feedback). Start a **new session**, commit everything first, and expect a conversation: the session proposes, you decide, and only then does it edit `docs/backlog.md`. It writes no code.

```text
Read AGENTS.md, then docs/requirements.md, docs/backlog.md, docs/status.md and docs/design.md. Also look at
the app's views (app.py, views/) so suggestions fit what the interface does today. Don't write code.

Context to keep in mind:
- WoW Forever is the target. The beta closes on 4 November 2026 and the game launches that day. Classic Era
  (Mankrik) is the development stand-in; Retail is regression-only.
- Prices come from our own read-only addon scans (Forever) and TSM's public CSVs (Classic). There is no Forever
  history yet beyond the scans we take by hand.
- Firm boundaries: the addon only reads; no buying, posting, unattended or scheduled scanning, or cloud
  deployment without an explicit decision; integer copper; never infer categories from names; missing prices
  are never free.

Work through these steps, pausing for my answers where marked:

1. State of play. In a few lines: what's done, what's in progress (check git log and the STORY-014 slices),
   and anything in status.md's Limitations that the backlog doesn't cover yet.

2. Review the backlog. For each Now/Next story: is it still worth doing, still in the right order, and are
   its acceptance criteria testable? Flag stories that should be split, merged, dropped or re-ordered, with
   one line of reasoning each. Pause for my answers.

3. Ideate, grouped by theme. For each idea give: the problem it solves for me as a gold maker, what data it
   needs and whether we have it, rough size (S/M/L), and what it depends on. Themes:
   - Interface: what's confusing or slow today. Known: choosing a data source in the sidebar and then a
     catalog on the page is confusing (noted under STORY-015).
   - Analytics: using what we already store (per-listing scan data, several scans, catalogs for several
     professions) before anything that needs new data.
   - Market forecasting: what is honestly possible with a few hand-taken scans versus after launch, and what
     each would need. Say plainly when an idea needs history we don't have.
   - Anything else: data quality, operations, the launch-day routine, risks before 4 November.
   Keep the list to the strongest ideas, at most about five per theme, and say which you'd do first and why.
   Pause for my picks.

4. Update the docs for what I picked. New stories go in backlog.md in the existing format (user story,
   acceptance criteria, dependencies); ideas I like but don't want scheduled go under Later. Rules or decisions
   go in requirements.md, linked rather than repeated. Don't touch other stories beyond what we agreed.

5. Hand-off: a short summary of what changed, the recommended next story, and a suggested commit message.
   Don't commit.
```
