# Brownstone web foundation

Use Node 24 (`.nvmrc`). Install exactly the lock file, then check and build:

```sh
npm ci
npm run check
npm run build
```

The Python launcher builds automatically when source or lock bytes change. On failure,
the launcher prints the recovery action. Plain FastAPI serves the build at `/app`;
legacy `/?place=...&source=...` URLs redirect there.

`npm run schema` regenerates `src/api/schema.d.ts` from the API application's OpenAPI
contract using the repo's Python environment (`BROWNSTONE_PYTHON` overrides it).
`npm run check` checks currency without changing the file, along with ESLint,
strict TypeScript and offline Vitest tests. Python tests and the full gate command live
at the repository root. Do not edit the generated schema manually.

Queries include the source in their URL and TanStack Query key. Source and scan evidence
load before the separate read-only drop inventory request finishes; an unknown waiting count
is shown as `?`, with checking/error detail in Data. No imports or other writes are exposed.
Future API POSTs must send the `brownstone-token` meta tag value as `X-Brownstone-Token`.
Authenticated launcher endpoints use their own token checks.

Fonts are bundled in `public/fonts`, with their SIL Open Font Licenses. The exact Fontsource
packages in the lock file provide their provenance. No remote font requests occur at runtime.
Theme tokens retain the approved prototype's palette; text variants improve light-theme contrast.
