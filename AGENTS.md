# Working on Brownstone Markets

Read the document that fits the task instead of loading all of them:

- `docs/requirements.md`: product direction, rules and open decisions. This is the single home for rules.
- `docs/design.md`: modules, data contracts, extension points (including switching to WoW Forever).
- `docs/backlog.md`: priority and user stories.
- `docs/status.md`: current state, limitations and how to verify. Describe *now*; history belongs in Git.

For a story, don't read `backlog.md`, `requirements.md` or `design.md` whole: print just the story and the rules and design sections it names with `python -m brownstone rules --story STORY-062 UI-17 ADDON-08 --design "Item charts"` (`--section` for a requirements heading, `--list` for every rule ID and heading). The files stay the source; edit rules there.

Explicit user instructions take precedence. When a decision or implementation changes a document, update it there and link from elsewhere rather than restating it.

- WoW Forever is the target. Classic Era Mankrik Alliance is a development stand-in. Retail is regression-only; don't build features for it.
- Preserve raw bytes and provenance. Keep data, environments, logs and credentials out of Git.
- A market (which auction house: `brownstone/markets.py`) is separate from a source (who observed it: `source_id`). Join prices on the full `MARKET_KEYS`, plus `rules_version` for crafting; item ID alone never joins. Never configure `market_id`, which is derived, and never mix sources silently.
- Calculate in integer copper. Display gold using `brownstone/money.py`.
- `brownstone/` must not import NiceGUI or download inside calculations. Display code goes in `views/`.
- Never infer categories from names or commodity status. Never treat missing or zero prices as free.
- Tests stay offline. Cover scope, units, freshness, deduplication and recipe quantities. Finish with `.venv/bin/python -m brownstone gates` passing: ruff, mypy, then `pytest -n auto --cov` at or above the coverage floor. Tests run in parallel, so keep them independent (own `tmp_path`, no fixed ports or shared files). New functions stay within Ruff's complexity limit; never add a `# noqa: C901`.
- Reusable session prompts (handing off a story, reviewing and closing a story, full audit, backlog grooming) are in `docs/prompts/`.
- Schema changes go through a new numbered migration in `storage.py`. Catalog value changes need source evidence.
- Never `pip install` a package ad hoc. Declare it in `pyproject.toml` and pin it in `requirements.lock.txt`: CI installs only from the lock file, so an undeclared package passes locally and fails in CI.
- The user commits and pushes manually. Leave changes uncommitted unless asked.
- Third-party addons for comparison live in ignored `work/addons/`. Borrow ideas freely, but code only from MIT-licensed ones (Journalator, CraftProfit), with a credit comment. Auctioneer is GPL; aux has no licence; TradeSkillMaster and ProfessionMaster are all rights reserved: ideas only. Don't read or use Auctionator (all rights reserved; its authors ask that AI tools not use it).
- The read-only scanning addon (`addon/BrownstoneScan/`, decided in SPIKE-008) only reads. Never add buying, posting, unattended scanning, cloud deployment or scheduled collection without an explicit decision.
