# Status

Current implemented state, limitations and how to verify. History lives in Git; keep this file describing *now*.

_Last updated 2026-10-09._

## Implemented

- **Today confidence (STORY-046, implemented and reviewed 2026-10-08):** Today v3 labels Craft rows
  High/Medium/Low with visible reasons, carried to Sell and Queue (including merged purchases).
  Rules and named thresholds: `requirements.md` → Today; contract: `design.md` → Today contracts.
  The default-off session Craft filter counts *low confidence* without changing reservations,
  shopping, Sell or Queue. Confidence age transitions preserve queue ticks. Offline boundaries,
  retained route markers, cumulative material share, plan invariance and AppTest checks cover this.
  Forever beta check (2026-10-08, copy of `data/`, saved settings 25g, scaled 1%, 10s floor, cap 5):
  fresh scan `20261009T003454Z-95a884` (observed 2026-10-09 00:34:59 UTC) gives **High 0, Medium 2,
  Low 8** over 10 rows. Reasons: unconfirmed yield 10, few listings 8, thin 7, unconfirmed vendor
  price 4, material share >75% 1, >40% 1. Every Forever yield is unconfirmed, so no Forever row can be
  High until yields are counted in game; thin outputs are the main Low cause.

- **Skill-up demand map (STORY-047, implemented, pending review):** Skill-ups follows Recipe catalogs.
  Compatible professions default to all; session controls adjust crafts per recipe and post-launch
  inclusion. Direct/raw totals lead, profession totals follow and bands are collapsed. Catalog
  regeneration adds page coverage and skill-up evidence without changing existing values; older
  catalogs still load. Market context reads the newest selected-source snapshot and remains visible
  when stale. Contracts/rules: `design.md` → Skill-up map, `requirements.md` → CRAFT-08/CRAFT-10.
  Offline synthetic saved-page, calculation, scoped market and AppTest checks cover the story.
  Real beta validation and limitations: [below](#skill-up-map-real-data-check-story-047).

- **Beta play sessions (Windows):** on 2026-10-08 (addon 0.9.0) the logout bags snapshot was empty
  (0 slots, 0 copper, level 1), so addon **0.10.0** saves the newest readable read from that login, and
  Brownstone treats 0-slot backpack snapshots as unreadable (ADDON-11, ADDON-12). The 2026-10-09 session
  (0.10.0; Basilly and Cicelyna: loot, a trainer, crafts, mail, bank and an Ironforge scan) confirmed it:
  logout and `/reload` bags were readable and snapshot gold matched the money chain. Crafting 5 Bolt of
  Linen Cloth and 1 Linen Bag, and buying 3 Coarse Thread at 10c, confirmed those catalog values (Forever
  Tailoring catalog 0.4). Failed mail sends were journaled as `MAIL_FAILED`, never as sends. Every fresh
  login's first bag entry had listed the whole bag as gains; addon **0.10.1** sets that baseline from the
  first settled bag update instead (rule beside the journal baselines in `requirements.md`). The scan was
  first skipped as another house because the source pinned Stormwind's zone and auctioneer; Alliance cities
  share one house, so only faction is now scan evidence, and the scan is imported. **0.10.1 confirmed in game
  (2026-10-09, Windows, Keenagen):** the first bag entry after login was `baseline_missing`; after
  `/bscan clear` and `/reload` the next entries were real changes (4 shots fired, then +1 Chipped Claw
  looted), and the two logout snapshots differ by exactly those 3 units. Beta report: no failures and no
  bag residual warnings.

- **Brownstone panel (STORY-044, implemented; pending in-game beta check):** addon **0.9.0**
  adds a draggable minimap coin and `/bscan panel`, opening a movable Escape-closeable
  panel with status, existing guarded actions and the manual routine. Only the minimap
  angle is saved in `ui`; formats **6/4** stay unchanged. Offline Lua tests cover controls,
  scan/item-pass disabled states, counts/cap warning, angle restoration and no capture on
  open. A Brownstone regression proves UI state leaves preview/import/report evidence unchanged
  while retaining exact-byte provenance. Usage/check: `addon/README.md` → Panel; contract:
  [ADDON-13](requirements.md#addon-13-brownstone-panel-story-044). Client layout, drag and
  Escape behavior still need the play check. The icon assumes the stock circular minimap;
  custom minimap shapes/resizing may affect placement (`/bscan panel` remains available).

- **Beta evidence report (STORY-042):** Brownstone-only CLI produces private Markdown/JSON evidence
  under ignored `work/beta-reports/`, with shared import validation, isolated exact-byte import
  round trip, diagnostics/coverage, character summaries, integer residuals and optional prior-file
  comparison. No addon, live data or input writes. Usage and limits: [below](#beta-evidence-report-story-042).

- **Active auctions (STORY-040, implemented, pending review and in-game beta):** addon **0.7.0**
  passively reads cached modern/legacy owned lists on guarded owned-update events, records changed
  raw lists in the existing auction journal, and suppresses unchanged lists within each load.
  Format **6** and schema **11** stay unchanged. Shared import preserves bytes/provenance and counts
  auction-family entries; the import page shows latest observed UTC/count/client-marked sold per
  scoped character, or *active auctions unknown*. Offline modern/legacy Lua and import/page tests
  cover empty/missing values, deduplication, silence, forbidden requests and rejected registration.
  No real owned-list recording has been supplied. Client API support, full-list delivery, status
  fields and arrival without opening the Auctions tab remain pending. Legacy cached results can
  be paged: all available batch rows and reported batch/total counts are preserved, but no reader
  requests uncached pages. Partial results retain unknown sold counts. Run the active-auctions beta
  checklist in `addon/README.md` by 13 October; preserve fixtures before 21 October. Rules: ADDON-12.

- **Event journal (STORY-033, implemented and reviewed 2026-10-07, pending in-game measurement):** addon
  **0.7.0**, account-wide format **6**, guarded event listeners/secure post-hooks, raw arguments,
  shared snapshot sequence, money/bag changes, mailbox states and last-observed send drafts.
  Schema **11** stores scoped raw character journal evidence. Snapshots and entries share non-scan
  preview, stale/conflict checks, batch commits, Fully imported and import guidance. CLI/page
  preview aggregates character/family/state; the import page alone shows imported counts/latest time.
  Capture/cap/clear/event/hook rules are [ADDON-12](requirements.md#addon-12-event-journal-story-033).
  Offline Lua/Python/page tests cover capture families/hooks, missing APIs, dedup/conflicts, cap,
  overflow versioning and session-safe clear. **Pending on Forever beta on both machines:** actual
  event/hook availability and argument layouts, loot sender GUID, mail draft timing/invoice values,
  gathering/crafting/vendor/auction reconciliation evidence and normal-session sizes/reload cost.
  Real journal recordings have not yet been supplied. Follow `addon/README.md` → Event journal beta
  checklist by 13 October; preserve recordings/fixtures before 21 October. No transaction interpretation.

- **Character snapshots (STORY-032, implemented and reviewed; pending the in-game beta check):** addon **0.7.0** writes
  account-wide file format **6**, preserving scan format 4. Guarded logout/reload and bank open/close
  reads retain gold, occupied slots, raw links and container/event evidence for each character.
  Initial-login markers survive confirmed reloads; clear preserves snapshots from the current login
  and retains everything if the signal is unknown. Rules are ADDON-11 in `requirements.md`.
  Schema **10** adds scoped character parents/slots without modifying old observations. Snapshots-only
  and mixed files use the same preview, drop folder, transactional importer, bronze collection and
  Fully imported status. CLI/page expose snapshot states; the import page shows latest bags/gold and
  independent bank time/counts/machine per character. No other view uses holdings.
  Offline Lua tests cover modern/legacy containers, two characters, missing APIs, rejected events and
  reload-safe clear; Python/UI tests cover duplicates/conflicts, other houses, old files, migration,
  stale reviews, CLI, snapshots-only files and overlapping drops. **In-game checks remain pending on
  both Mac and Windows:** event registration/firing, logout/reload bag availability, bank-close
  readability, container IDs/coverage, login/reload flags and the updated scan/clear routine. Exact
  steps and evidence to record are in `addon/README.md` → Character snapshots beta checklist.

- **Second-machine files (STORY-037, implemented and reviewed):** configured machine provenance, optional local-only read-only Drive inbox, independent per-file previews/imports and exact-byte collections, ignored/error reasons, latest-drop/full-import cleanup evidence, CLI `--preview` and file selection in the import page. Schema 9 adds nullable scan machine; historical rows stay missing. Windows has a manual PowerShell script, double-click wrapper and ignored settings file with an example. Setup is in `addon/README.md`; rules are OPS-03 and contracts are in `design.md`. First real Windows → Drive → Mac round trip passed 2026-10-07 (one beta scan, imported as `windows-pc`). Drive can still be downloading a just-synced file, which shows as *Scan file changed while reading*; preview again after a minute.

- **Ingestion:** TSM CSV → bronze/silver/DuckDB/gold with manifests, validation and analytical deduplication. Sources: Mankrik Alliance Classic Era (development stand-in), plus Retail Area 52 and US commodities (regression only).
- **Addon scan import (STORY-010):** a `provider = "addon"` source imports BrownstoneScan SavedVariables through **Preview addon scans** → select new scans → **Import addon scan** (STORY-014), or `python -m brownstone --source <id> [--input file] [--scan ID]`. Rules ADDON-01 to ADDON-06 in `requirements.md`.
  - House evidence is checked against the configured market. Preview lists scans from another house as not importable, with the reasons; importing one (including a CLI import of the whole file) fails. CLI `--scan` validates only selected scans.
  - Stacks are priced per unit, rounded up when inexact. `market_value` is the quantity-weighted 25th percentile.
  - Deduplication is by `scan_id`, and identical file bytes are stored once, gzip-compressed. Partial scans are stored and labeled but not priced. After an import that saved something new and left no file scans unimported, the app and CLI say `/bscan clear` is safe; subsets warn to import the remainder first; scans from another house warn that clearing deletes them; an import with nothing new warns to `/reload` first instead. The addon refuses to clear scans it hasn't written to the file yet.
  - STORY-045: Preview shows one short summary per file with new scans or character records, counts already-imported files, and puts Import directly below the summary. Details contains the existing preview tables, notes and selection; it opens on the problems named in ADDON-06/STORY-045, including drops the selection would leave not fully imported, and stays open for the rest of that review. Imported character data stays in its own collapsed expander. Cleanup is a count of fully imported drops for manual deletion, hidden at zero; after import, each latest-drop machine (or the local file's machine) gets one conditional clear-guidance line. Empty local files are quiet when another input is readable. Preview displays IDs, UTC start/finish, status, listing count, import state and partial status in Details. It writes nothing and uses only read-only database queries. Empty selections and duplicates-only previews offer no import. File/configuration/duplicate-state changes invalidate a review before import; reads use the bounds and best-effort detection in ADDON-06. A missing database is created only by an explicit import.
  - Reads scan formats 1, 2, 3 and 4; older scans keep new fields null (ADDON-08/09). Converting the real scan to format 2 gives identical listings and item prices, at 2.8 MB instead of 24.8 MB.
  - The Forever Action Board works from imported scans with no calculation changes.
  - The beta source `forever-us-normal-alliance-addon` is disabled in the tracked `config/market.toml`. On the user's machine, the untracked `config/market.local.toml` enables it and points it at the game's SavedVariables file, to archive beta scans before the beta closes. Classic Mankrik stays the default development source.
- **Recipe import (STORY-004):** `python -m brownstone recipes --page <saved page> --selection config/recipe-selections/<catalog>.toml` generates a catalog from a Wowhead profession page saved in a browser (CRAFT-08). It never downloads. The page is archived under `data/recipe-sources/`, and the command lists recipe and vendor price changes.
  - Pages saved 2026-10-04: Classic Tailoring (287 recipes, SHA-256 `aab9c70c…`) and Forever Tailoring (471 recipes, `9ab28c15…`). Copies are in `data/recipe-sources/wowhead/`, ignored by Git like all of `data/`.
- **Recipe catalogs page (STORY-014 Slice 2):** the app's **Recipe catalogs** view shows the catalogs of the sidebar experience (WoW Forever or Classic Era); there is no separate switch on the page, and Retail shows that it has no catalogs. It lists that version's catalogs, found by their selection files whatever the profession (the Crafting view loads them the same way), and the professions with none yet. Each row shows recipe and item counts, catalog version, the page's save date, game build and SHA-256, the count of unconfirmed values (listed in an expander), and **Refresh due** (CRAFT-08).
  - **Add or update a profession** is one numbered flow: **1. Profession** lists existing catalogs as *update (N recipes)* and the rest as *new catalog*; **2. Saved page** (an update can start from the catalog's archived page, when it is on this machine); **3. Recipes**, vendor marks and rules version; **4. Review and save**, which follows every choice live and writes nothing. The review gives recipe and item counts before and after, the recipes added and removed by name, every recipe and vendor price change, selection notes that would be removed and the selection file. **Save catalog** archives the page and writes the selection file (edited line by line, comments kept) and the catalog; its key carries a fingerprint of the choices and the files on disk, so a click on a review that has since changed writes nothing. Choices that reproduce the catalog exactly show *Nothing to save*.
  - After saving, a toast and a banner confirm it, the table reloads and the saved profession stays selected.
  - **Choosing recipes:** a searchable list of every recipe the page offers, plus **Add all matching** and **Remove all matching** for a name and skill range (intermediates are added automatically). Choosing all of Classic or Forever Tailoring is possible this way.
  - **Items several recipes make** (Alchemy's transmuted essences) are always bought, and their recipes aren't offered; recipes Wowhead lists as making 0 are never used either (CRAFT-08). The recipe step's count says how many recipes each reason leaves out.
  - A page from another game version or profession is refused. After a write the page lists the changed tracked files and never commits. Generation goes through the same `prepare_catalog` as `python -m brownstone recipes`.
  - The recipe step says how many of the page's recipes can be chosen and why the rest can't: no item made (enchants on gear), no fixed yield on Wowhead (Classic Enchanting's 7 oils list 0), or seasonal. The 2026-10-04 pages offer 226 of 287 Classic Tailoring, 413 of 471 Forever Tailoring, 101 of 132 Classic Alchemy, 167 of 202 Forever Alchemy and 12 of 204 Classic Enchanting recipes. The Alchemy and Enchanting catalogs, added in the app, hold every offered recipe; Classic Tailoring is a deliberately small subset (6 recipes); Forever Tailoring holds 412 recipes from the page saved 2026-10-06.
  - Checked on the real config and archive: all five catalogs regenerate from their archived pages unchanged (no bump, no tracked file written) and show builds 1.15.8 (67156) and 1.60.1 (70205); a preview takes 8–31 ms. Classic Enchanting holds no Season of Discovery recipes.
- **Crafting:** twelve generated catalogs. Forever (1,930 recipes, pages saved 2026-10-04 to 2026-10-06): Alchemy 167, Blacksmithing 430, Cooking 129, Enchanting 28, Engineering 205, First Aid 31, Leatherworking 511, Mining 17, Tailoring 412. Classic Era: Alchemy 101, Enchanting 12, Tailoring 6. Every compatible catalog shares one Action Board with a Profession column and filter (STORY-015a). Recipe costs and details stay within their own catalog, including duplicate recipe IDs and shared outputs. Cautious and listed price bases, policy 0.2, five labels, per-recipe error isolation and per-catalog parse isolation (a catalog that fails to load is named and left off the board) are preserved. Incompatible catalogs explain their rules mismatch, offer unpriced inspection and link to Recipe catalogs.
- **Today (STORY-025, pending review):** settings persist per source in ignored local JSON; a funded,
  supply-reserved craft plan ranks whole-stack batch profit, with a merged shopping list, output
  competition/undercut evidence and independent below-vendor aside. Every list caps at 10 and counts
  the rest; hidden recipes show reasons. Stale data stays inspectable with a warning and every row
  non-actionable. TSM labels listing-dependent evidence unavailable. Rules and decisions are in
  `requirements.md` → Today; contracts are in `design.md` → Today contracts.
- **Today craft details (STORY-038, implemented and reviewed):** selecting a Craft row shows
  its complete reserved material purchases, required/purchased units, route, cost and highest unit
  price, plus indented chosen catalog intermediate steps and batch quantities. No row starts selected;
  changed plan contents/provenance clear selection. Materials reconcile exactly in copper with the
  craft and full merged shopping cost, including Buy's hidden tail; stale details remain inspect-only.
  Details reuse the reserved purchases of the current chosen plan.
- **Choose the Today plan (STORY-039, implemented and reviewed 2026-10-08):** Craft controls start ticked,
  allow exact batch edits, and re-reserve listings in plan order. Refill defaults on; turning it off
  keeps the ticked plan. Source-scoped session choices reset on scan/settings/evidence changes, with
  a note; invalid exact choices are dropped rather than resized. Queue lists complete auction/vendor
  buys, catalog crafts in dependency order, then posts, with copper totals matching Buy/Sell. Queue
  ticks are session-only and do not change numbers; Copy as text exposes the checklist and totals.
  Rules are in `requirements.md` → Today; no database, addon, catalog or settings schema change.
- **Scan changes (STORY-018):** compare any two distinct eligible addon scans of the selected source and market; defaults to the newest two scan IDs. Displays per-unit prices, listing/unit counts, changes, separate new/vanished lists, compatible-catalog item filtering, UTC finish times, gap and freshness. Missing listings, no buyout and no market value have distinct labels. Eligibility and display rules are in UI-06 (`requirements.md`). Market scope includes environment (DATA-03).
- **Market depth (STORY-019):** Crafting shows output listing/unit counts and a direct-input depth summary on each board row, and the same counts in recipe inputs and shopping lists. Counts come from the exact priced scan. Missing listings and unavailable depth have distinct labels; depth is display-only (CRAFT-09 in `requirements.md`).
- **Interface:**
  - The sidebar experience choice lists WoW Forever first (so it opens by default) and resolves the source and market together; every view follows them, including Recipe catalogs, and each page names the experience, source and market under its title. If an experience has several enabled sources, the sidebar asks for a source and shows nothing until one is chosen (today only Retail, with Area 52 and region commodities). The database upgrade runs on browsing for the selected source when a database exists; Preview never migrates.
  - STORY-030 is implemented, pending review: the sidebar's source metadata and configuration hint are
    in collapsed Source details. Today opens by default (STORY-025, pending review), with a settings
    summary, an expander that opens for zero gold or unreadable settings, and Craft/Buy/Sell/Below vendor
    tabs plus the session Queue tab (STORY-039). Decision columns lead each table; per-tab toggles expose evidence columns. Shared provenance
    appears on the page, while freshness warnings and stale State columns remain visible.
  - Crafting groups unsupported recipes in one collapsed table, catalog captions in Catalogs on this
    board, and board explanations in How to read this board. Board provenance and freshness stay visible;
    recipe summaries in g/s/c and expandable recipe evidence retain their existing behavior. UI rules
    and the layout choices are in `requirements.md` → UI-01 and Today → Evidence and honesty.
  - Browse market, Opportunities, Recipe catalogs, Skill-ups and Scan changes are also available. Opportunities explains when a source can't support it.
  - All money is displayed in gold.
- **Launcher:** `launch.py` (via `Start Brownstone.command` / `.cmd`) restarts its own server when the code has changed.
- **Catalogs:**
  - **Classic Era:** Tailoring 0.3 (six representative bag/bolt recipes); Alchemy and Enchanting 0.2. Tailoring retains the quantities, roles and vendor prices hand-verified in STORY-007.
  - **Forever beta** (`forever-beta-1.60`): Tailoring 0.3; Alchemy, Blacksmithing, Cooking, Enchanting, Engineering, First Aid, Leatherworking and Mining 0.2. Catalogs are generated from archived pages; selection coverage and unconfirmed yields/vendor values remain visible. All twelve catalogs were regenerated for STORY-047; parsed comparisons confirmed only `skillup_colors`, `page_coverage` and `catalog_version` changed. Selection files changed only their version.
- **Markets and sources (STORY-009):**
  - A market is the auction house; a source is the feed that observed it. `market_id` is derived, so several sources can observe one market, each with its own folder and deduplication.
  - Forever houses (server type + faction, no realm) can be configured. Neutral houses default to a 15% cut.
  - The catalog `ruleset` field is now `rules_version`.
  - The CLI uses `--source`; `--market` still works as an alias.
- **Beta/live identity (STORY-017):** implemented under DATA-03 in `requirements.md`. The tracked Forever source is explicitly beta, with its source ID unchanged. Every price, scan and listing carries environment; Browse, Opportunities, crafting, depth, Scan changes, manifest selection and import deduplication all enforce it. Page captions show the derived beta market ID.
- **Item names (STORY-022):** Browse/search, Opportunities and Scan changes resolve missing labels through version-scoped names collected from scans, TSM rows and catalogs; crafting and board depth already use catalog labels. Name policy lives in DATA-02 (`requirements.md`). Stored observations and archives remain unchanged.
- **Storage:** code supports schema 10 with backed-up, idempotent migrations (see `design.md` → Schema migrations). The local `data/brownstone.duckdb` remains at version 9 (metrics_version 1); STORY-032 schema-10 verification used copies only. Upgrades run at app startup or explicit import and preserve a backup of the starting schema; migration verification for STORY-023 uses only copied databases. Earlier backups remain intact. Old manifests are adapted only in memory.
- **Market metrics (STORY-024):** schema 7 stores versioned facts from the shared `metrics.py`
  calculator at scan import. Definitions and evidence limits live in ADDON-10 (`requirements.md`).
  Existing databases backfill outside frozen migration DDL on startup/import, retrying unfinished
  initialization. `rebuild_scan_metrics(db)` recomputes from stored listings transactionally;
  scoped readers expose facts, exact shares/coverage and threshold supply without seller names.
  Board depth and Scan changes use stored facts. Addon item prices use the same calculator;
  historical price observations remain preserved. No new dashboard or trading policy is introduced.
- **Quality gates:** CI runs Ruff (including a complexity limit of 10), mypy and the tests with a branch-coverage floor of 88% (96.08% in the current macOS run: 898 passed, one PowerShell-unavailable skip) on macOS and Windows from the lock file, including the Streamlit UI test. One function, the scan parser's hot loop, is exempt from the complexity limit and listed as debt in `design.md`. Config loads into typed, individually validated `Source` records.

- **Scanning addon:** `addon/BrownstoneScan/` is version **0.10.1**, writing account-wide file format **6** and scan format **4**. The bounded scan-owned item info pass (STORY-031) is implemented and reviewed, pending beta measurement; its rules are ADDON-09 and its checklist/fields are in `addon/README.md`. It records richer listing evidence and one official item-reference observation per ID per scan; capture/variant/measurement rules are ADDON-08/09 in `requirements.md`. Formats 1/2/3 remain readable with unchanged raw bytes/hashes; formats 1/2 keep richer reference fields null. Schema migration 8 retains first-pass reference columns, adds separate pass values/provenance and an effective-reference view without rewriting historical observations. Read-only preview validates reference observations too, before any write. Import records first-pass, pass-added and effective availability, pass counters and listing duration locally; pass duration stays in raw evidence. Today reads effective vendor references with the same source/full-market/scan/snapshot scope.
  - Prices, Scan changes and explicit depth reads separate variants and unresolved evidence. Browse, Opportunities and Scan changes display identity and resolution state (`legacy` for formats 1/2). Scan changes match a legacy item to a format-3 base row only when the format-3 scan has only base listings for it, so plain goods compare across the 0.2.0/0.3.0 boundary. Out-of-range optional listing values are stored as missing and counted rather than rejecting the scan; `required_level` accepts `REQ_LEVEL` and `REQ_LEVEL_ABBR`; the Forever beta reports the latter. Catalog crafting reads base rows, with existing historical reads retained; format-3 unresolved/variant-only prices cannot fill a base catalog item.
  - **Offline verified:** shipped Lua executes under Lua 5.1 with modern and legacy WoW stubs, including missing/erroring optional APIs, seller fallback, one reference lookup per ID, manual start, timeout and partial close. Delayed/synchronous answers, failed requests/answers, timeout and late events, missing API/rejected event, house close during the pass, pre-pass save and reload-mid-pass import, first-pass preservation and maintenance guards are verified. Resulting scans import; mixed formats 1–4, raw archive bytes, deduplication, variant prices/scope/depth/comparison, migration backup/replay and reference nulls are tested. Lupa is a declared, pinned dev dependency; Python coverage does not measure Lua branches.
  - **Reload and Clear saved scans buttons** sit beside the scan button on the auction house window, with Clear protected like `/bscan clear` and both disabled during a scan; behaviour and decisions are in `addon/README.md` → *Reload and clear controls*.
  - **Beta accepted 2026-10-06** (build 70235, addon 0.3.1): complete format-3 scans imported and deduplicated, duration 1.23× and bytes per listing 1.92× the 0.2.0 baseline (within ADDON-09), suffix variants priced separately, buttons placed and working. Measurements and availability counts are in `addon/README.md` → *Format-3 beta checklist*.
  - Existing beta scans remain preserved under ignored `data/` (including the byte-for-byte 0.1.0 scan archive). Seller-bearing format-3 files stay local under ADDON-07.

## Limitations

- **Beta scans so far:** seven complete Normal Alliance scans (16:47Z, 17:46Z and 22:54Z on 2026-10-04, 20:34Z on 2026-10-05, and 16:16Z, 20:17Z and 20:32Z on 2026-10-06) and one stopped scan, all from the beta and identified separately from the live house by schema 4 (DATA-03). The three from 22:54Z on 2026-10-04 to 16:16Z on 2026-10-06 are addon 0.2.0; the last two are addon 0.3.1, format 3, the newest with 88,329 listings.
- **No sellers on the beta:** its bulk scan API returns no owner names, so format-3 scans have no seller data (ADDON-07). STORY-028 is blocked on *Seller capture* (Later in `backlog.md`).
- Addon **0.4.0 has not been measured in game**; event/cache timing, interruption persistence, added duration, bytes per listing and reload lag remain pending. Earlier addon versions have been measured on one beta house only, not the Roleplaying or a neutral house. In game, `/bscan start` without the button, closing the house mid-scan and Escape on the clear popup are untested (all covered offline). Beta region and realm values are generic, so scans are identified by auctioneer, zone and label. The `.toc` interface number 16001 may change with beta builds.
- Required skill levels are display-only.
- The Recipe catalogs page shows a catalog's game build only when its archived page is on this machine (`data/` isn't in Git). Regenerating records the uploaded file's name as the manifest's `original_name`, as the CLI does.
- Craft routes remain local to each catalog; routing across professions is STORY-015b.
- **Forever values still to confirm in game** (shown on the recipe view):
  - **Output counts:** every recipe keeps Wowhead's list value of 1, marked `output_quantity_verified = false` until counted in game. The "(2)" in Wowhead's spell tooltips turned out to be the effect number, not a count (2026-10-06), so a yield above 1 is unlikely. Craft one Bolt of Linen Cloth on the beta and count to confirm.
  - **Vendor items:** Coarse Thread, Fine Thread, Red Dye and Rune Thread are assumed sold by vendors (`vendor_verified = false`); check a Forever trade supplies vendor.
  - **Availability:** Runecloth Bag and its two dyes are marked post-launch, but the 2026-10-04 17:46Z scan has both dyes on the beta auction house (Magenta 44 units, Cerulean 261).
- Multi-yield recipes aren't supported (see `requirements.md` → *Not modeled*). Every current recipe makes 1.
- Crafting and Opportunities use one addon scan: no recent or historical values and no discount screen. Scan changes compares saved scans without deriving historical price metrics. Listing depth is displayed, but not used in calculations.
- The real beta scan has thin high-level Tailoring coverage, because most beta characters are low level; low-tier bags and cloth are well listed. Runecloth Bag has no listings, so its board row shows missing prices.
- Mankrik has no upstream scan time, so price age is unknown and "stale" only measures time since download.
- Classic historical values are zero, so the discount screen cannot run on Classic.
- Not modeled: see `requirements.md` → *Not modeled*.
- Legacy rows have no source hash and are not retroactively deduplicated. Changed content at the same upstream time is kept as a correction.
- Silver, DuckDB and gold are not written atomically. If a run fails after the DuckDB commit, the bronze/silver files are the recovery source. There is no replay tool yet (STORY-006).
- Run one writer at a time; a concurrent refresh can fail on the DuckDB lock.

## Verify

```bash
.venv/bin/python -m pytest -p no:cacheprovider --cov
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy
git diff --check
```

Expected: 779 tests pass and one explicit PowerShell-unavailable skip on this Mac; 780 tests run where PowerShell exists (Windows CI), offline; `ruff check .` and `mypy` report no issues. Windows uses `.venv\Scripts\python.exe`. Live ingestion is a separate manual check: **Refresh from TSM** in the app.

Scan preview verification: `tests/test_scan_preview.py` covers mixed new/duplicate/partial/empty scans, UTC metadata, missing data directories, no preview writes, old-schema read-only preview, shared time/listing validation, other-house scans listed but not selectable, ID conflicts, exact-byte archives, empty/unknown/duplicate selections, configuration/file/duplicate-state invalidation (including the final writer check), bounded reads, deterministic read changes, unreadable/truncated/malformed files, partial pricing, commit-failure rollback/failed manifests and shared CLI subset guidance, including an unselected malformed entry. AppTest in `tests/test_app.py` covers preview → selection → subset import, duplicates-only reminders, empty selections, retryable errors, stale reviews, other-house rows, the result replacing the reviewed table, page-load upgrade of an existing addon database and source/configuration switching, while retaining the TSM and existing-page regressions.

Real-data preview/import was checked on 2026-10-05 against temporary copies of the database and a 51 MB schema-1 scan file (about 2–3 s per preview or import; originals unchanged).

STORY-031 real-data verification (2026-10-06, copies under ignored `work/story-031/`): schema 7→8
preserved 66,089 prices, 668,109 listings, 8 scan rows, 6,116 references and 31,071 metrics.
The schema-7 backup matches the pre-upgrade copy byte for byte; two migration replays preserve
all observations and leave historical provenance null. Today evidence matches across seven
complete scans. The archived two-scan format-3 file yields two duplicates; removing only those
scans inside the copy and importing again yields two fresh imports with identical captured
scan/listing/reference/metric and price evidence (new collection IDs/times are expected).
Migration took 0.161 s; duplicate import took 0.722 s. Original database/archive hashes stayed
unchanged. The aggregate report/script and raw/database copies remain ignored; no beta result
is claimed. Full game checks remain in `addon/README.md` → *Format-4 beta checklist*.

STORY-024 verification (2026-10-06, local copy only): schema 6→7 preserved all 49,964 price
observations, 491,661 listings, 6 scan rows and the empty reference table. Five complete scans
produce 14,946 metric rows; every minimum/25th percentile agrees with the corresponding stored
item prices (zero sentinels normalized to null), and every listing count/unit total agrees with
baseline listing aggregation and the depth reader. Zero mismatches. All 14,946 historical seller
measure/coverage sets remain null. Two rebuilds match the initial backfill exactly; migration-7
replay leaves rows unchanged. The schema-6 backup equals the pre-upgrade copy byte for byte and
remains unchanged after replay. The original database SHA-256 remains
`16d6a31b26bb6a9596fe9d74a1f38914502e2b1117ecb512cb5df0654fd8134a`.
Aggregate-only verification script, report and copied databases are under ignored `work/story-024/`.
No real format-3 seller/variant availability is claimed; offline fixtures cover it. Tests cover
weighted odd/even percentile ranks, stacks/rounding/no buyout, strict thresholds, seller coverage,
exact variant/legacy separation, every source/market/scan/snapshot field, deterministic rebuild,
import/rebuild rollback, schema-7 interrupted-backfill retry and schema-6 backup/replay/layout.
Rebuild currently materializes eligible listings locally; memory-bounded scaling remains a limitation.

STORY-023 real-data verification (local copies): migration 5→6 took 75 ms and preserved all 46,923 price observations, 413,930 listings and 5 scan rows from the preserved database backup. All six historical scan comparisons and price/depth reads across four complete scans matched the pre-story reader results. Migration replay kept data unchanged; the schema-5 backup equalled the pre-upgrade copy. Re-importing the archived 0.2.0 scan returned one duplicate in 219 ms. The live database and archive SHA-256 stayed unchanged during this check. The local verification script, report and copies are under ignored `work/story-023/`. These are software checks; the beta measurements are in `addon/README.md`.

Item-name verification: `tests/test_item_names.py` covers later-loaded names, catalog-only names, placeholders/blank names excluded, unknown and separate game versions, shared labels without mixed prices across sources/houses/environments, observed/catalog precedence, newest loaded names and lexical ties, older imports, TSM timestamps and collection-time fallback, partial listings, Browse/search and Opportunities, Scan changes (a scan's own loaded name before newer lookup names), padded names trimmed, catalog-labelled board depth, migration backfill/replay/backup and unchanged observation rows. Malformed catalogs, including ones missing IDs, remain isolated; the app seeds catalog labels only into an existing database.

On a copy of the schema-4 real database (2026-10-05), migration 4→5 plus catalog seeding named 625 of the 1,140 Forever items that had placeholders, leaving 515 of 3,384 items unnamed. Classic remains 2 unnamed of 5,868; Retail remains 242 of 29,150. Runecloth's three Forever price rows now display Runecloth using catalog evidence; none had a loaded price-row name. All four 166-row Forever boards (including depth), all six Scan changes comparisons (apart from names) and all other Browse/Opportunities values across seven snapshot/source contexts were identical. Stored observation tables and a migration replay were identical too. The version-4 backup equals the original copy. All 98 original files under `data/` retained their SHA-256; the database hash before/after is `e0f3fca9411cacf667ebfbd8235502b29b250273a4932020e9d5a73a3996f372`. Timings for this run: migration/catalog seed 149 ms, replay 68 ms, four boards 37→40 ms, six comparisons 67→130 ms, all Browse/Opportunities reads 21→42 ms. Verification script, reports and database copies are under ignored `work/story-022/`, excluded from commits.

Beta/live verification: `tests/test_environments.py` covers explicit configuration, unchanged live IDs, launch-boundary and timezone classification, v3 migration/backup/replay, old-manifest resolution without edits, duplicate re-import, full-scope single/multi-scan reads, same-key scope conflicts, CSV deduplication, CLI and app startup from either beta or Classic. Existing per-market-key depth and Scan changes tests include environment; preview tests cover environment changes invalidating a review.

On temporary real-data copies (2026-10-05), migration 3→4 kept all counts: 8,846 Forever prices, 4 scans and 316,691 listings became beta; 5,868 Classic, 18,152 Retail house and 10,998 Retail commodity prices became live with unchanged IDs. The 166-row Forever board and all three comparisons were identical before/after. The archived 2026-10-04 file returned two duplicates with no new database rows. Original database, input file and 19 bronze-manifest SHA-256 checks passed; copies were deleted. Migration took 81 ms, board read 13 ms, three comparisons 34 ms, preview 1.03 s and duplicate import 1.24 s.

Scan comparison verification: `tests/test_scan_changes.py` covers price and supply changes, unchanged/new/vanished items, absent versus no-buyout prices, weighted historical prices, exact scan/snapshot IDs, every source/market field, partial/incomplete/unpriced exclusions, duplicate imports, newest-two defaults and item-ID filters. AppTest covers scan selection, compatible catalog filtering (including name collisions and incompatible item IDs), UTC times/gap, context, absent/no-buyout labels and unavailable comparisons.

On a temporary read-only copy of the three imported Normal Alliance scans, full comparisons returned the following counts. Changed means any price or supply metric differs; times include eligibility queries, SQL aggregation and per-item result construction. The original database's SHA-256 stayed unchanged.

| Earlier scan | Later scan | Changed | Unchanged | New | Vanished | Query time |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `20261004T174645Z-0076af` | `20261004T225430Z-31f52b` | 2,575 | 193 | 208 | 175 | 11.06 ms |
| `20261004T164730Z-c651bd` | `20261004T225430Z-31f52b` | 2,613 | 136 | 227 | 178 | 10.76 ms |
| `20261004T164730Z-c651bd` | `20261004T174645Z-0076af` | 2,234 | 631 | 78 | 62 | 10.41 ms |

Depth verification: `tests/test_depth.py` covers source and every market field, exact scan selection, partial scans, duplicate imports, stack units and listings without a buyout. The Crafting UI tests cover multiple compatible catalogs, duplicate recipe IDs and own-catalog details, rules-mismatch inspection, shared experience/source selection, addon outputs with and without listings, direct inputs and TSM unavailable depth. On a copy of the real database, scan `20261004T225430Z-31f52b` returns Linen Bag 1,429 listings / 1,429 units and Runecloth Bag 0 / 0 in about 3 ms; all four Tailoring rows and policy 0.2 are identical before and after the query.

Last live check (2026-10-04, Mankrik, 5,868 rows), cautious basis:

| Bag | Profit | Label |
| --- | --- | --- |
| Runecloth Bag | 73s 37c | potential craft |
| Woolen Bag | — | negative margin |
| Mageweave Bag | — | negative margin |

On the listed basis, Runecloth Bag shows 2g 50s 69c, because the cheapest Runecloth listing is far below its market value.

Addon import dry run (2026-10-04, on copies of `data/brownstone.duckdb` at version 2 and the real scan file; originals unchanged):

- **Timings:** the 24 MB file parses in 0.88 s. Unit and item prices take 0.05 s. The full import takes 1.22 s, including bronze copy, migration 2→3 and DuckDB load. A re-import takes 0.97 s and skips both scans as duplicates without copying the bytes again.
- **Scan `20261004T164730Z-c651bd`:** completed, imported. 101,485 listings (702,427 units), 28,105 of them stacks, giving 2,927 items. Non-exact stacks: 0. 4 listings had no buyout.
- **Scan `20261004T165015Z-02d971`:** stopped (throttled), 0 listings. Recorded as `empty`, not priced.
- **Existing data:** all 24,020 existing rows kept. Database 2.1 MB → 6.8 MB.

| Item | Listings / units | Min buyout | Market value |
| --- | --- | --- | --- |
| Runecloth (14047) | 2 / 4 | 2g 55s | 2g 55s |
| Bolt of Runecloth | 35 / 142 | 86s 95c | 87s |
| Runecloth Bag | none | — | — |
| Rugged Leather | 19 / 110 | 5s | 5s |
| Wool Cloth | 99 / 2,652 | 83c | 84c |
| Mageweave Cloth | 79 / 203 | 35s 94c | 43s 94c |

The Forever Action Board labels Runecloth Bag **missing prices**, because there's no bag listing. Its cautious craft cost is 4g 95s, buying bolts (87s) rather than crafting them from 2g 55s Runecloth.

Forever Tailoring rows (2026-10-04, on a copy of `data/brownstone.duckdb`; the original was unchanged). Source `forever-us-normal-alliance-addon`, scan `20261004T174645Z-0076af` (observed 17:46Z), cautious basis. Depth is listings / units in that scan:

| Rank | Bag | Label | Craft cost | Sale | Profit (cautious / listed) | Bag depth | Input depth |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Red Linen Bag | potential craft | 4s 30c | 6s | 1s 40c / 1s 80c | 471 / 471 | Linen Cloth 482 / 24,029; Bolt of Linen 214 / 3,069 |
| 2 | Linen Bag | potential craft | 2s 40c | 3s | 45c / 75c | 1,374 / 1,374 | Linen Cloth 482 / 24,029 |
| 3 | Woolen Bag | potential craft | 7s 30c | 8s | 30c / 84c | 173 / 173 | Wool Cloth 266 / 5,593; Bolt of Woolen 27 / 161 |
| 4 | Runecloth Bag (post-launch) | missing prices | 24g 47s 6c | — | — | none | Bolt of Runecloth 37 / 152; Magenta Dye 29 / 44; Cerulean Dye 111 / 261; Rugged Leather 24 / 129 |

All three low-tier bags craft their bolts (2 Linen Cloth at 35c, 3 Wool Cloth at 70c) and buy thread and dye from vendors. Runecloth Bag would buy its bolts (87s); the dyes alone cost 19g 52s 6c.


### Today real-data verification (2026-10-06)

Calculated using **copies** of each source's database and current local catalog selections; no
original database writes or seller-name reads. Settings: 100g available, scaled 1% / 10s floor
(1g effective minimum), cap 5. Timings include opening the copy and evidence reads; copying files
and catalog discovery are excluded. Both newest snapshots were fresh at verification time; stale
and future-date handling is verified separately with offline fixtures.

| Source / evidence | Craft | Buy | Sell | Below vendor | Rest (craft / buy / sell / aside) | Read / calculate / total |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| Forever beta, scan `20261006T203259Z-ea00ed` | 10 | 10 | 10 | 0 | 23 / 14 / 0 / 0 | 0.0628 / 0.0898 / 0.1526 s |
| Classic TSM, snapshot `20261004T135552051172Z_8b24dbea` | 6 | 10 | 6 | 0 | 0 / 7 / 0 / 0 | 0.2294 / 0.0057 / 0.2350 s |

Forever hidden: missing prices 1,389; unsupported recipes 79; insufficient listed materials 7;
one craft exceeds remaining funds 63; below minimum gain 273. Top batches: Barbaric Bracers,
5 crafts, 32g 87s 70c estimated batch profit (cap); Azure Gustwoven Hood, 5, 19g 67s 97c (cap);
Frost Oil, 4, 17g 57s 33c (more crafts lower profit: a fifth is affordable but earns less).
With 10,000g and a 1,000-craft cap, the Forever calculation takes 0.28 s.

Classic hidden: missing prices 12; unsupported recipes 1; one craft exceeds remaining funds 78;
below minimum gain 13. Top batches: Elixir of Frost Power, 5, 11g 28s 20c (cap);
Major Troll's Blood Potion, 5, 8g 91s 15c (cap); Major Rejuvenation Potion, 5, 6g 48s 40c (cap).
TSM has no listing-dependent estimates; its costs and batch quantities use aggregate prices.

Today v1 retains aggregate-selected routes while quoting actual whole listings; it does not search
alternate routes after cheap supply is exhausted. Whole-stack surplus is uncredited and unshared.
The greedy plan is affordable, not a global optimum. Below-vendor evidence is an independent aside,
restricted to base/legacy identities with an observed scan vendor-sell reference. Missing reference
prices are omitted. Sales speed, stockpile, volatility, character inventory/recipes, cross-profession
routes and automated actions remain outside STORY-025 (see backlog → Today, later versions).


STORY-037 verification: `tests/test_scan_inputs.py` covers shared naming examples, machine/local-only config,
read-only previews, two-machine same-market imports, per-file archives, partial pricing, duplicate/conflicting
IDs, ignored/unreadable/truncated/other-house files, latest-drop cleanup, stale reviews and schema-9
backup/replay/legacy nulls. CLI preview/subsets and explicit input remain covered; `tests/test_app.py`
exercises file selection, machine/UTC rows, ignored files, fresh cleanup evidence and stale import rejection.
`tests/test_windows_drop.py` invokes the shipped PowerShell harness with disposable files where available;
macOS visibly skips it, and Windows CI runs it. The harness tests shared names, byte equality, no-op duplicates,
process/missing/invalid guards, hash failure and no-overwrite collisions without Pester.

On copies under ignored `work/story-037/`, migration 8→9 preserves 10 scans, 825,631 listings, 81,757 prices,
12,135 item references, 46,739 metrics and 39,299 item names. All historical machines remain null;
the schema-8 backup equals the original copied database byte-for-byte, and migration replay is idempotent.
A copied 0.4.0 beta file named `windows-pc-20261007T004900Z-BrownstoneScan.lua` previews as duplicate
`20261007T004900Z-9dc790`, fully imported; preview leaves the copied database unchanged. The originals
remain unchanged: database SHA-256 `46dc059c0f8bdf4cc2a0ef2e55531d4d0915845f58bf148e2d00030c4f7ea425`;
input SHA-256 `a576e621c93eaae2eab2f6153f284b54984c2455088c308164df774a8cfa9632`.
Real Drive folder, real SavedVariables and original `data/` were never written for these checks.
Drive streaming/offline files and sync delays can cause retryable file errors; naming completion only
protects the local copy, not remote sync ordering. Preview memory and repeated parsing grow with retained
files; manual cleanup is necessary. Successful files commit independently of failed files.


## Beta evidence report (STORY-042)

After logout or `/reload` has finished writing, run from the repository:

```bash
.venv/bin/python -m brownstone beta-report "/path/to/BrownstoneScan.lua" --source forever-us-normal-alliance-addon
# For additions since a retained earlier file, append:
# --previous "/path/to/earlier/BrownstoneScan.lua"
```

The command prints an absolute report folder followed by pass/warn/fail totals. Send Claude the
folder's `report.md` (and `report.json` for structured checking); these omit listing sellers. Keep
raw SavedVariables private under ADDON-07. Exit 0 permits warnings, exit 1 means a check failed,
exit 2 means an input could not be read. Reports do not import the session into your real database
or authorize clearing the addon: use the existing import/cleanup workflow separately.

`tests/test_beta_report.py` covers clean evidence, shared readers/formats 1–6, refused records and
malformed lists continuing independently, required fields/IDs/sequences/time bounds, money chains,
gold and bag residuals with missing/incomplete baselines, overflow/skipped counts, diagnostics and
error counters, level/skill surfaces and profession names/frequency/incomplete causes, inferred
loads, coverage, exact bronze round trips, comparisons/conflicts, seller/bidder exclusion, exit
codes, unique folders and absence of writes outside report/temporary directories.

Current limits: load boundaries are inferred, historical diagnostics are unavailable, and journal
error counters cannot be assigned to loads. Checklist observation does not prove an action
succeeded or establish invoice semantics. Serialized sizes are approximations. A scan from another house is named as a *scan house* warning and left out of the round trip. Real files on this
machine currently provide formats 1–4 only, including two Windows drops; genuine format-5/6
snapshot/journal/profession evidence remains pending play. Synthetic formats 5/6 exercise the full
report/import path offline. Details of module boundaries and reconciliation are in
[design.md](design.md#beta-evidence-report-story-042).

Current real-file verification: 16 copied inputs (genuine formats 1–4, two Windows drops and the
game-file backup), with a fresh temporary copy of `data/`. All 13 nonempty files pass the exact-byte
import round trip. Three cleared files fail with the importer's no-scans/reload guidance; all files
have the same 20 expected warnings for missing diagnostics and character-checklist capture in
older formats. Totals: 112 pass, 320 warn, 3 fail; end-to-end run 55.998 seconds. All 171 original
file hashes and the complete fresh data copy are unchanged. Private per-file results, timings and
every warning/failure are in ignored `work/beta-reports/verification/real-results.json`; no genuine
format-5/6 in-game recording is claimed.

STORY-038 real-data check (2026-10-07, read-only existing database): Forever beta Normal Alliance,
source `forever-us-normal-alliance-addon`, scan `20261007T185956Z-a4a84f`, existing saved settings
25g / scaled 1% with 10s floor / cap 5. Today selects 9 crafts; all reserved details reconcile to
249,991c shopping total. Barbaric Bracers (`forever-leatherworking`, recipe 23399), batch 5,
costs 111,728c: Ruined Leather Scraps 2,400 required / 2,409 purchased / 31,404c; Cured Heavy Hide
10 / 17 / 35,649c; Raptor Hide 5 / 18 / 5,310c; Small Lustrous Pearl 20 / 20 / 19,399c;
Large Fang 20 / 20 / 19,966c. All five routes are auction purchases. Highest unit prices are
17c, 2,097c, 295c, 1,099c and 1,000c respectively. The retained catalog chain is Heavy Leather
40 crafts/units → Medium Leather 200 → Light Leather 800, at depths 1/2/3. Evidence was fresh
at 21:45 UTC. No database migration, import or settings write was needed.


### STORY-039 Forever beta verification (2026-10-08)

Loaded the enabled Forever beta source through `config/market.local.toml`, copied the complete
453 MB data directory to a temporary directory, and ran calculations and the actual Streamlit page
against that copy. Original data/settings were not written. Scan `20261007T185956Z-a4a84f` was fresh
during the first check; the final rerun crossed the 24-hour freshness limit and correctly showed
the stale banner, inspect-only table states and queue caption. Saved settings: 25g, scaled 1% with 10s floor (25s minimum), cap 5.

The page renders Craft, Buy, Sell, Below vendor and Queue with no exceptions.
Default: 9 crafts, 15 complete shopping rows (10 displayed, 5 beyond the cap), 37 queue lines;
gold needed 24g 99s 91c and expected profit at undercut 90g 65s 89c. Top crafts are Barbaric
Bracers (5, cautious profit 36g 32s 72c), Frost Oil (5, 18g 22s 20c) and Bronze Dory
(5, 12g 4s 59c). Unticking Barbaric Bracers with refill off leaves 8 crafts, 28 queue lines,
13g 79s 95c needed and 54g 35s 90c expected profit at undercut. Default refill adds Thick Murloc
Armor and Raptor Hide Harness: 10 crafts, 42 queue lines, 24g 98s 23c needed and 78g 63s 90c
expected profit at undercut. Queue gold reconciles exactly with full shopping cost in all cases.
Refill-added controls, queue ticking across reruns and Copy as text were exercised on the page.
No live game action, download or import was performed.

Review check (2026-10-08, Claude, live browser on a scratch copy of the project and data; the real
database SHA-256 was unchanged): default, untick-with-refill and refill-off totals reproduce the figures
above exactly. Re-ticking Barbaric Bracers drops the two refill rows with a note and restores the default
totals. Bronze Dory at batch 2 shows its lower real profit (4g 80s 62c) and refill spends the freed gold.
Queue ticks and the Copy as text block persist across reruns while the scan is stale; Limited by keeps
the real reason on unchanged rows; refill off reports the crafts left out (71); the server log shows no
Session State warning.

## Skill-up map real-data check (STORY-047)

Checked 2026-10-08 using `config/market.local.toml`'s enabled Forever beta source
`forever-us-normal-alliance-addon`, market `forever-us-normal-alliance-beta`. Read-only DuckDB
connection; database SHA-256 unchanged. N=5, default post-launch exclusion (one recipe).
Newest snapshot/scan: `20261007T185956Z-a4a84f`, observed 2026-10-07 19:00:04 UTC; stale at the
24-hour limit. All market columns remained visible; absent items had zero listed units and blank prices.

| Profession | Catalog / page usable | Unknown skill-up range | No item on page | Raw expansion errors |
| --- | ---: | ---: | ---: | ---: |
| alchemy | 167 / 167 | 13 | 15 | 5 |
| blacksmithing | 430 / 431 | 97 | 65 | 1 |
| cooking | 129 / 129 | 15 | 3 | 0 |
| enchanting | 28 / 30 | 6 | 200 | 2 |
| engineering | 205 / 207 | 12 | 20 | 30 |
| first-aid | 31 / 31 | 18 | 0 | 2 |
| leatherworking | 511 / 512 | 46 | 78 | 32 |
| mining | 17 / 17 | 11 | 1 | 0 |
| tailoring | 412 / 413 | 107 | 50 | 0 |

Top ten raw materials in combined totals (units), after the review marked Forever leather tiers
`raw_material`:

- Runecloth (14047): 28,060.
- Mageweave Cloth (4338): 16,010.
- Thorium Bar (12359): 11,250.
- Silk Cloth (4306): 10,310.
- Rugged Leather (8170): 7,645.
- Thick Leather (4304): 5,535.
- Fel Leather (248825): 4,950.
- Mithril Bar (3860): 4,450.
- Bronze Bar (2841): 4,095.
- Rune Thread (14341): 3,990.

Tailoring 50–74 tables contained 42 recipes, 18 direct and 18 raw material rows; raw Linen Cloth was
1,240 units (9,908 listed, 0.003g lowest), raw Wool Cloth 765 (3,956 listed, 0.0077g lowest).
All 42 yields were marked unconfirmed; two recipe ranges were unknown. Cerulean Dye's existing
item post-launch marker remained visible; the toggle excludes recipes marked post-launch, not
recipes whose inputs carry that item marker.

Limitations found by this check: 72 recipes have fractional intermediate craft counts at N = 5 (expansion
checks all N crafts together, so Silver Contact's yield of 5 divides evenly) and contribute no raw units; their direct units remain visible and the page warns above totals. Before the review,
Leatherworking's conversion chains expanded high-tier leather back to 17,179,425 Ruined Leather Scraps;
the selection now marks Light to Rugged Leather `raw_material` (CRAFT-08), so raw totals stop there.
Totals remain an all-recipe expectation, not a gathering recommendation or launch forecast.
The 107 unknown Tailoring ranges include page colour arrays containing zero; validity remains
strict rather than interpreting zero. Saved pages are October 4 (Alchemy) or October 6 (other Forever
professions). Full check output is local-only under ignored `work/story047/real-data.json`.
