# Working on Brownstone Markets

Use the project documents according to the task instead of loading all of them by default:

- `docs/requirements.md` for product scope, accepted decisions and requirement changes.
- `docs/design.md` for architecture or data-contract changes.
- `docs/backlog.md` for priority, user stories and selecting the next feature.
- `docs/status.md` for implemented state, limitations, verification and session handoff.

Explicit user instructions take precedence. Update the relevant document when a decision or implementation changes it.

- Preserve raw bytes and provenance; exclude data, environments, logs and credentials from Git.
- Maintain game version and market scope. Item ID alone is not a cross-version identity.
- Separate UI, ingestion, normalization, storage and calculations. No Streamlit or downloads in domain calculations.
- Do not infer categories from names/commodity status or treat unavailable prices as free materials.
- Keep tests offline and cover meaningful scope, units, freshness, deduplication and recipe quantities when implemented.
- User handles commits/pushes in VS Code; leave changes reviewable unless explicitly instructed to commit or push.
- Coverage work does not authorize crafting engine, addon, cloud deployment or scheduled collection.
