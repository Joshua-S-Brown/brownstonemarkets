# Working on Brownstone Markets

Read docs/requirements.md, docs/design.md and docs/status.md first. Explicit user instructions take precedence. Update scope and handoff docs when decisions change.

- Preserve raw bytes and provenance; exclude data, environments, logs and credentials from Git.
- Maintain game version and market scope. Item ID alone is not a cross-version identity.
- Separate UI, ingestion, normalization, storage and calculations. No Streamlit or downloads in domain calculations.
- Do not infer categories from names/commodity status or treat unavailable prices as free materials.
- Keep tests offline and cover meaningful scope, units, freshness, deduplication and recipe quantities when implemented.
- User handles commits/pushes in VS Code; leave changes reviewable unless instructed otherwise.
- Coverage work does not authorize crafting engine, addon, cloud deployment or scheduled collection.
