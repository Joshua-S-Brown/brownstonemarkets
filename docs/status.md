# Status

Current implemented state, limitations and how to verify. History, including dated real-data checks
and beta play sessions, lives in Git; keep this file describing *now*.

_Last updated 2026-10-12 (first audit)._

## Implemented

Rules live in `requirements.md` and contracts in `design.md`; each bullet names where.

- **Main app (NiceGUI, UI-07):** Today, Team and Market (both placeholders for STORY-052/055) and
  Data → Import. Start it from `Start Brownstone.command` / `.cmd` or `launch_nicegui.py`
  ([New app](#new-app)). Runs on the Mac only; the Windows PC plays and drops scan files.
- **Old app (Streamlit, UI-01 to UI-06):** unchanged and reachable from
  `Start Brownstone (old app).command` / `.cmd` (`launch.py`). Places: Today (Today plan, All
  recipes), Team (Characters), Market (Browse market, Skill-up demand, Watchlist, Below usual price),
  Data (Import or Refresh from TSM, Recipe catalogs, Scan changes). TSM refresh lives only here.
- **Ingestion:** TSM CSV → bronze/silver/DuckDB/gold with manifests, validation and analytical
  deduplication (DATA-01 to DATA-05). Addon SavedVariables import (ADDON-01 to ADDON-06): read-only
  preview, explicit reviewed import, scan formats 1–4 inside account file format 6, partial scans
  stored but never priced, exact bytes gzip-archived once per SHA-256. Character snapshots and the raw
  event journal share the same non-scan import lifecycle (ADDON-11/12). A second machine's files
  arrive through the read-only drop folder (OPS-03). CLI: `python -m brownstone`, with `--preview`,
  `--input`, `--scan` and the `recipes` and `beta-report` subcommands.
- **Sources:** the Forever beta source `forever-us-normal-alliance-addon` (disabled in the tracked
  `config/market.toml`, enabled with `scan_path`, `machine` and `drop_folder` in the untracked
  `config/market.local.toml`), Mankrik Alliance Classic Era (development stand-in), and Retail Area 52
  and US commodities (regression only). Market identity includes environment (DATA-03).
- **Storage:** schema 11 and metrics version 1; backed-up, idempotent migrations (`design.md` →
  Schema migrations). The local database is at schema 11.
- **Crafting:** twelve generated catalogs. Forever (`forever-beta-1.60`, 1,930 recipes from pages saved
  2026-10-04 to 06): Alchemy 167, Blacksmithing 430, Cooking 129, Enchanting 28, Engineering 205,
  First Aid 31, Leatherworking 511, Mining 17, Tailoring 412. Classic Era: Alchemy 101, Enchanting 12,
  Tailoring 6. One combined Action Board (CRAFT-05), depth display (CRAFT-09), recipe import and the
  Recipe catalogs page (CRAFT-08), learning sources and training costs (STORY-050).
- **Today (`today_version` 5):** funded, supply-reserved plan with Buy/Sell/Below vendor/Queue,
  choices and refill, confidence labels, character eligibility and recorded funds (`requirements.md`
  → Today). The new app shows Craft as cards with Table one toggle away (STORY-054).
- **Other pages:** Characters (STORY-051), Watchlist (STORY-048), Skill-up demand (CRAFT-10), Scan
  changes (UI-06), Browse market and Below usual price (UI-02/03), version-scoped item names (DATA-02),
  market metrics (ADDON-10).
- **Beta evidence report (STORY-042):** private Markdown/JSON reports under ignored
  `work/beta-reports/` ([usage](#beta-evidence-report)).
- **Scanning addon:** `addon/BrownstoneScan/` 0.11.2, file format 6, scan format 4: manual scans with
  the bounded item-info pass, character snapshots, event journal, active auctions, known recipes
  through `C_TradeSkillUI`, reload/clear buttons and the minimap panel. Usage, saved fields and beta
  checklists are in `addon/README.md`.

**Pending in-game beta checks** (checklists in `addon/README.md`): the item-info pass measurement
(STORY-031), snapshots on both machines (STORY-032), the event journal (STORY-033), active auctions
(STORY-040), the panel (STORY-044) and auction deposits (STORY-035). Confirmed on the beta so far:
format-3 scans and the reload/clear buttons (addon 0.3.1), readable logout bags (0.10.0) and the
fresh-login bag baseline (0.10.1), level and profession ranks, and modern known-recipe lists
(0.11.1; the empty first read is refused since 0.11.2).

## Limitations

- **Beta scans:** sixteen complete Normal Alliance scans and one stopped scan are imported, the newest
  `20261011T105714Z-cf2f26`. No Roleplaying or neutral house has been scanned.
- **No sellers on the beta:** the bulk scan API returns no owner names (ADDON-07); STORY-028 is blocked
  on *Seller capture* (Later in `backlog.md`).
- **Forever values still to confirm in game** (shown on the recipe view): every Forever yield is
  `output_quantity_verified = false` (a yield above 1 is unlikely); Coarse Thread, Fine Thread, Red Dye
  and Rune Thread are assumed vendor items; Runecloth Bag and its dyes are marked post-launch although
  both dyes appear on the beta auction house.
- Crafting and Opportunities use one addon scan: no recent or historical values and no discount
  screen. Listing depth is displayed, not used in board calculations.
- Today keeps aggregate-selected routes while quoting whole listings; surplus is uncredited and
  unshared, and the greedy plan is affordable, not a global optimum. Sales speed and volatility are
  not modeled.
- Craft routes stay within each catalog (cross-profession routing is STORY-015b). Multi-yield recipes
  aren't supported (`requirements.md` → *Not modeled*). Required skill levels are display-only.
- On the Classic stand-in, the legacy skill API reports every skill line, so weapon skills and
  languages appear as lines; the Forever client reports professions only.
- Mankrik has no upstream scan time, so its "stale" measures time since download. Classic historical
  values are zero, so the discount screen cannot run on Classic.
- The Recipe catalogs page shows a catalog's game build only when its archived page is on this machine.
- Legacy TSM rows have no source hash and are not retroactively deduplicated.
- Silver, DuckDB and gold are not written atomically. If a run fails after the DuckDB commit, the
  bronze/silver files are the recovery source; there is no replay tool yet (STORY-006).
- Run one writer at a time; a concurrent import or refresh can fail on the DuckDB lock. Google Drive
  can still be downloading a just-synced drop (*Scan file changed while reading*): preview again later.
- The NiceGUI app reads evidence on load: reload it after importing elsewhere.

## Verify

```bash
.venv/bin/python -m pytest -p no:cacheprovider --cov
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy
git diff --check
```

Expected on this Mac: 1,132 passed and one explicit PowerShell-unavailable skip (1,133 run where PowerShell exists, as in Windows CI), offline, at 96.4% branch coverage; `ruff check .` and `mypy` report no issues. CI runs the same
on macOS and Windows from the lock file, with a branch-coverage floor of 88% (`pyproject.toml`).
Windows uses `.venv\Scripts\python.exe`. Live ingestion is a manual check: **Refresh from TSM** in the
old app, or addon preview/import in Data. Real-data checks run on a copy of `data/` under ignored
`work/`, never the original.

### New app

Install `requirements.lock.txt`, then double-click `Start Brownstone.command` / `.cmd` (or run
`launch_nicegui.py`). It opens a native window, focuses it on a second launch when the code is current,
and restarts only the authenticated app it started when the code changed. If the native window can't
start, it prints one line and opens the browser; that server stops after five minutes without a
connected tab. For a copied-data browser check:
`.venv/bin/python nicegui_app.py --data-dir /path/to/copied-data --port 8081`.

### Beta evidence report

After logout or `/reload` has finished writing, run from the repository:

```bash
.venv/bin/python -m brownstone beta-report "/path/to/BrownstoneScan.lua" --source forever-us-normal-alliance-addon
```

Add `--previous "/path/to/earlier/BrownstoneScan.lua"` to report additions since an earlier file. The
command prints the report folder and pass/warn/fail totals; send Claude `report.md` (and `report.json`).
Reports omit listing sellers; keep raw SavedVariables private (ADDON-07). Exit 0 permits warnings,
1 means a check failed, 2 means an input could not be read. A report imports nothing into the real
database and doesn't authorize clearing the addon. Load boundaries are inferred, diagnostics exist only
for the latest load, and serialized sizes are approximate (`design.md` → Beta evidence report).
