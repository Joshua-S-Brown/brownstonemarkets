# Working on Brownstone Markets

Read the document that fits the task instead of loading all of them:

- `docs/requirements.md`: product direction, rules and open decisions. This is the single home for rules.
- `docs/design.md`: modules, data contracts, extension points (including switching to WoW Forever).
- `docs/backlog.md`: priority and user stories.
- `docs/status.md`: current state, limitations and how to verify. Describe *now*; history belongs in Git.

Explicit user instructions take precedence. When a decision or implementation changes a document, update it there and link from elsewhere rather than restating it.

- WoW Forever is the target. Classic Era Mankrik Alliance is a development stand-in. Retail is regression-only; don't build features for it.
- Preserve raw bytes and provenance. Keep data, environments, logs and credentials out of Git.
- A market is its full identity (`MARKET_KEYS` plus ruleset for crafting). Item ID alone never joins across versions or scopes.
- Calculate in integer copper. Display gold using `brownstone/money.py`.
- `brownstone/` must not import Streamlit or download inside calculations. Display code goes in `views/`.
- Never infer categories from names or commodity status. Never treat missing or zero prices as free.
- Tests stay offline. Cover scope, units, freshness, deduplication and recipe quantities.
- The user commits and pushes manually. Leave changes uncommitted unless asked.
- Don't add addons, automated trading, cloud deployment or scheduled collection without an explicit decision.
