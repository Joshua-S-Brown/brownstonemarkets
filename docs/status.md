# Status

Current implemented state, limitations and how to verify. History, including dated real-data checks
and beta play sessions, lives in Git; keep this file describing *now*.

_Last updated 2026-10-13 (STORY-015b)._

## Implemented

Rules live in `requirements.md` and contracts in `design.md`; each bullet names where.

- **Main app (NiceGUI, UI-07):** Today, Team (roster and progression), Market (item explorer and scan movement) and
  Data → Import. Start it from `Start Brownstone.command` / `.cmd` or `launch_nicegui.py`
  ([New app](#new-app)). Shared light theme, wrapping header navigation, page information dialogs
  and Today settings behind the gear (STORY-060, UI-08). Native text selection is enabled.
  Runs on the Mac only; the Windows PC plays and drops scan files.
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
  Team-aware graph routes across compatible professions (STORY-015b, CRAFT-12; board policy 0.3)
  feed Today/Queue, Team reach, Market and This session. Competing makers resolve by cost/catalog;
  a field one catalog omits takes another's recorded value; differing values warn and stay buy-only. Verify with `tests/test_recipe_graph.py` and
  `tests/ui_trial/test_nicegui_recipe_graph.py`.
- **Today (`today_version` 6):** funded, supply-reserved plan with Buy/Sell/Below vendor/Queue,
  choices and refill, confidence labels, character eligibility and recorded funds (`requirements.md`
  → Today). The new app shows Plan cards with Table one toggle away, status chips, summary tiles and
  helpful empty-state reasons; Shopping list, Sell, Queue and Extras retain their existing evidence.
  Provenance and hidden counts are in the ⓘ dialog; fixed/scaled settings retain Save-only behaviour.
- **This session (STORY-063, UI-12):** a fixed toggle under Today's title; one card per scoped
  character with next-step lines (craft, level a profession, level the character for the next tier,
  train, gather), details folded underneath: reserved crafts with plain flood labels and profession
  costs grouped by reach at Team's remembered window. Cheap-material portion, incomplete reasons and
  caps remain explicit; tier levels are Classic Era's, unconfirmed on Forever. Links open Team and Market.
  Session composition preserves the displayed Today plan. Farming awaits STORY-065. Verify with
  `tests/test_session_options.py` and `tests/ui_trial/test_nicegui_session.py`.
- **Team (STORY-052, CRAFT-11):** shared character cards with Next step lines, a scoped character
  choice and 5–100-point window that updates on release, summary tiles, reachable recipes,
  profession comparison and per-point material/training estimates on demand.
  Current Action Board profit, reused Today statuses/confidence, incomplete reasons and cap guidance;
  yellow chances remain an unconfirmed Classic assumption. Streamlit Characters is unchanged.
- **Market explorer (STORY-055, UI-09):** name/ID search across the newest scoped snapshot;
  addressable item pages with prices, listings/units, vendor references, made-from routes and nested
  quantities, used-in recipes sorted by Board profit, team eligibility and skill-up bands. Compatible
  catalogs only; unknown prices stay unknown, variants stay separate. Trial movement shows at most
  ten distinct chain items from the newest two eligible scans, with comparison evidence on demand.
  Verify offline with `tests/test_market_explorer.py` and `tests/ui_trial/test_nicegui_market.py`;
  on copied Forever data check Linen Cloth (2589), Bolt of Linen Cloth (2996) and the movement section.
- **Removed listings (STORY-027, UI-10):** Market shows the newest qualifying consecutive pair's
  top ten catalog-chain items by units removed early; item pages lazily show at most ten qualifying
  pairs, skipped long gaps, early/possible-expiry/unknown counts and units, excluded no-buyout counts
  and matching evidence. Read-only listing multisets, full scope and variant/legacy identity retained.
  Verify with `tests/test_removed_listings.py` and `tests/ui_trial/test_nicegui_market.py`.
  Classic Era time-left bounds require the Forever in-game confirmation in `addon/README.md`.
- **Flood signals (STORY-064, UI-11):** Market's contested-chain and cheap/high overshoot lists
  link to lazy item evidence, including listing/units/stack share, lowest-buyout churn, typical price,
  history count, catalog roles, configured thresholds/window and scan freshness. Short history and
  missing prices remain explicit; variants stay separate. Verify with `tests/test_flood_signals.py`
  and `tests/ui_trial/test_nicegui_market.py`; real-data inspection uses copied Forever beta data.
- **Other pages:** Characters (STORY-051), Watchlist (STORY-048), Skill-up demand (CRAFT-10), Scan
  changes (UI-06), Browse market and Below usual price (UI-02/03), version-scoped item names (DATA-02),
  market metrics (ADDON-10).
- **Beta evidence report (STORY-042):** private Markdown/JSON reports under ignored
  `work/beta-reports/` ([usage](#beta-evidence-report)).
- **Scanning addon:** `addon/BrownstoneScan/` 0.11.3, file format 6, scan format 4: manual scans with
  the bounded item-info pass, character snapshots, event journal, active auctions, known recipes
  through `C_TradeSkillUI`, reload/clear buttons and the minimap panel. Usage, saved fields and beta
  checklists are in `addon/README.md`.

**Pending in-game beta checks** (checklists in `addon/README.md`): the item-info pass measurement
(STORY-031), snapshots on both machines (STORY-032), the event journal (STORY-033), active auctions
(STORY-040), the panel (STORY-044), removed-listing time-left bounds (STORY-027) and auction deposits
(STORY-035). Confirmed on the beta so far:
format-3 scans and the reload/clear buttons (addon 0.3.1), readable logout bags (0.10.0) and the
fresh-login bag baseline (0.10.1), level and profession ranks, and modern known-recipe lists
(0.11.1; the empty first read is refused since 0.11.2).

## Limitations

- **Beta scans:** eighteen complete Normal Alliance scans and one stopped scan are imported, the newest
  `20261013T003719Z-89214e`. No Roleplaying or neutral house has been scanned.
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
- Forever vendor reagents (threads, dyes, bleach, salt, fluxes, vials, wood, rods, stocks, ink,
  parchment, spices, flour, drinks, nightcrawlers) are marked in every catalog with the saved pages'
  buy prices, `vendor_verified = false` except Coarse Thread; coal, Elemental Flux, Imbued Vial and
  seasonal items are not marked (STORY-036 confirms).
- Cross-profession routes require scoped Known/Train now team evidence (CRAFT-12); without it
  costs remain catalog-local. Mail postage remains unconfirmed and uncharged. Multi-yield recipes
  aren't supported (`requirements.md` → *Not modeled*). Team infers no character-level tier requirement; This session uses Classic Era's (10/20/35), unconfirmed on Forever until trainer evidence from addon 0.11.3 is checked.
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

Expected on this Mac: 1,343 passed and one explicit PowerShell-unavailable skip (1,344 run where
PowerShell exists, as in Windows CI), offline, at 96.50% coverage with branches enabled;
`ruff check .` and `mypy` report no issues. CI runs the same
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

STORY-060's desktop comparison screenshots are under ignored `work/story-060/`; the app is now the
design reference (the mockups are in Git history). Native clipboard use and switching macOS appearance still need a manual
check. A phone-width screenshot remains unverified because the browser viewport override did not apply.

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
