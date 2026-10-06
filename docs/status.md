# Status

Current implemented state, limitations and how to verify. History lives in Git; keep this file describing *now*.

_Last updated 2026-10-05._

## Implemented

- **Ingestion:** TSM CSV → bronze/silver/DuckDB/gold with manifests, validation and analytical deduplication. Sources: Mankrik Alliance Classic Era (development stand-in), plus Retail Area 52 and US commodities (regression only).
- **Addon scan import (STORY-010):** a `provider = "addon"` source imports BrownstoneScan SavedVariables through **Preview addon scans** → select new scans → **Import addon scan** (STORY-014), or `python -m brownstone --source <id> [--input file] [--scan ID]`. Rules ADDON-01 to ADDON-06 in `requirements.md`.
  - House evidence is checked against the configured market. Preview lists scans from another house as not importable, with the reasons; importing one (including a CLI import of the whole file) fails. CLI `--scan` validates only selected scans.
  - Stacks are priced per unit, rounded up when inexact. `market_value` is the quantity-weighted 25th percentile.
  - Deduplication is by `scan_id`, and identical file bytes are stored once, gzip-compressed. Partial scans are stored and labeled but not priced. After an import that saved something new and left no file scans unimported, the app and CLI say `/bscan clear` is safe; subsets warn to import the remainder first; scans from another house warn that clearing deletes them; an import with nothing new warns to `/reload` first instead. The addon refuses to clear scans it hasn't written to the file yet.
  - Preview displays IDs, UTC start/finish, status, listing count, import state and partial status. It writes nothing and uses only read-only database queries. Empty selections and duplicates-only previews offer no import. File/configuration/duplicate-state changes invalidate a review before import; reads use the bounds and best-effort detection in ADDON-06. A missing database is created only by an explicit import.
  - Reads scan format 1 (addon 0.1.0) and 2 (addon 0.2.0, compact). Converting the real scan to format 2 gives identical listings and item prices, at 2.8 MB instead of 24.8 MB.
  - The Forever Action Board works from imported scans with no calculation changes.
  - The beta source `forever-us-normal-alliance-addon` is disabled in the tracked `config/market.toml`. On the user's machine, the untracked `config/market.local.toml` enables it and points it at the game's SavedVariables file, to archive beta scans before the beta closes. Classic Mankrik stays the default development source.
- **Recipe import (STORY-004):** `python -m brownstone recipes --page <saved page> --selection config/recipe-selections/<catalog>.toml` generates a catalog from a Wowhead profession page saved in a browser (CRAFT-08). It never downloads. The page is archived under `data/recipe-sources/`, and the command lists recipe and vendor price changes.
  - Pages saved 2026-10-04: Classic Tailoring (287 recipes, SHA-256 `aab9c70c…`) and Forever Tailoring (471 recipes, `9ab28c15…`). Copies are in `data/recipe-sources/wowhead/`, ignored by Git like all of `data/`.
- **Recipe catalogs page (STORY-014 Slice 2):** the app's **Recipe catalogs** view shows the catalogs of the sidebar experience (WoW Forever or Classic Era); there is no separate switch on the page, and Retail shows that it has no catalogs. It lists that version's catalogs, found by their selection files whatever the profession (the Crafting view loads them the same way), and the professions with none yet. Each row shows catalog version, recipe count, the page's save date, game build and SHA-256, the count of unconfirmed values (listed in an expander), and **Refresh due** (CRAFT-08).
  - **Update a profession:** start from the catalog's archived page (when it is on this machine) or upload a newly saved one. Add or remove recipes, change vendor marks and the rules version. **Preview changes** shows the recipe and vendor price diff, any selection notes that would be removed, the edited selection file and the new version, and writes nothing; **Regenerate** archives the page, writes the selection file (edited line by line, comments kept) and the catalog. Choices that reproduce the catalog exactly offer nothing to write.
  - **Add a profession:** pick the profession, follow the Wowhead link to save the page in your browser, upload it, choose recipes and optional vendor items (marked unconfirmed), then **Preview catalog** and **Create catalog**.
  - **Choosing recipes:** a searchable list of every recipe the page offers, plus **Add all matching** and **Remove all matching** for a name and skill range (intermediates are added automatically). Choosing all of Classic or Forever Tailoring is possible this way.
  - **Items several recipes make** (Alchemy's transmuted essences) are always bought, and their recipes aren't offered; recipes Wowhead lists as making 0 are never used either (CRAFT-08). The Add tab's count says how many recipes each reason leaves out.
  - A page from another game version or profession is refused. After a write the page lists the changed tracked files and never commits. Generation goes through the same `prepare_catalog` as `python -m brownstone recipes`.
  - The Add tab says how many of the page's recipes can be chosen and why the rest can't: no item made (enchants on gear), no fixed yield on Wowhead (Classic Enchanting's 7 oils list 0), or seasonal. The 2026-10-04 pages offer 226 of 287 Classic Tailoring, 413 of 471 Forever Tailoring, 101 of 132 Classic Alchemy, 167 of 202 Forever Alchemy and 12 of 204 Classic Enchanting recipes. The Alchemy and Enchanting catalogs, added in the app, hold every offered recipe; the Tailoring catalogs are deliberately small subsets (6 and 7 recipes, chosen in their selection files).
  - Checked on the real config and archive: all five catalogs regenerate from their archived pages unchanged (no bump, no tracked file written) and show builds 1.15.8 (67156) and 1.60.1 (70205); a preview takes 8–31 ms. Classic Enchanting holds no Season of Discovery recipes.
- **Crafting:** five generated catalogs: Classic and Forever Tailoring and Alchemy, and Classic Enchanting. Every compatible catalog shares one Action Board with a Profession column and filter (STORY-015a). Recipe costs and details stay within their own catalog, including duplicate recipe IDs and shared outputs. Cautious and listed price bases, policy 0.2, five labels, per-recipe error isolation and per-catalog parse isolation (a catalog that fails to load is named and left off the board) are preserved. Incompatible catalogs explain their rules mismatch, offer unpriced inspection and link to Recipe catalogs.
- **Scan changes (STORY-018):** compare any two distinct eligible addon scans of the selected source and market; defaults to the newest two scan IDs. Displays per-unit prices, listing/unit counts, changes, separate new/vanished lists, compatible-catalog item filtering, UTC finish times, gap and freshness. Missing listings, no buyout and no market value have distinct labels. Eligibility and display rules are in UI-06 (`requirements.md`). Market scope includes environment (DATA-03).
- **Market depth (STORY-019):** Crafting shows output listing/unit counts and a direct-input depth summary on each board row, and the same counts in recipe inputs and shopping lists. Counts come from the exact priced scan. Missing listings and unavailable depth have distinct labels; depth is display-only (CRAFT-09 in `requirements.md`).
- **Interface:**
  - The sidebar Classic/Forever experience choice resolves the source and market together; every view follows them, including Recipe catalogs, and each page names the experience, source and market under its title. If an experience has several enabled sources, the sidebar asks for a source and shows nothing until one is chosen (today only Retail, with Area 52 and region commodities). The database upgrade runs on browsing for the selected source when a database exists; Preview never migrates.
  - Crafting opens by default for markets with a compatible catalog. It shows the board, a recipe summary in g/s/c and expandable evidence.
  - Browse market, Opportunities, Recipe catalogs and Scan changes are also available. Opportunities explains when a source can't support it.
  - All money is displayed in gold.
- **Launcher:** `launch.py` (via `Start Brownstone.command` / `.cmd`) restarts its own server when the code has changed.
- **Catalogs:**
  - **Classic Era 0.2:** Woolen, Mageweave and Runecloth bags with their bolts. Regenerated from the saved page with the same quantities, roles and vendor prices hand-verified in STORY-007 (a test pins them). It now has all six skill levels from the page: Bolt of Woolen Cloth 75, Woolen Bag 80, Bolt of Mageweave 175, Mageweave Bag 225, Bolt of Runecloth 250, Runecloth Bag 260.
  - **Forever beta 0.1** (`forever-beta-1.60`): Linen, Red Linen and Woolen bags with Linen and Woolen bolts, plus Runecloth Bag and its bolt, marked post-launch. It replaces the hand-typed file, which had two errors: Bolt of Runecloth takes 5 Runecloth, not 4, and Runecloth Bag also takes 4 Magenta Dye and 2 Cerulean Dye.
- **Markets and sources (STORY-009):**
  - A market is the auction house; a source is the feed that observed it. `market_id` is derived, so several sources can observe one market, each with its own folder and deduplication.
  - Forever houses (server type + faction, no realm) can be configured. Neutral houses default to a 15% cut.
  - The catalog `ruleset` field is now `rules_version`.
  - The CLI uses `--source`; `--market` still works as an alias.
- **Beta/live identity (STORY-017):** implemented under DATA-03 in `requirements.md`. The tracked Forever source is explicitly beta, with its source ID unchanged. Every price, scan and listing carries environment; Browse, Opportunities, crafting, depth, Scan changes, manifest selection and import deduplication all enforce it. Page captions show the derived beta market ID.
- **Item names (STORY-022):** Browse/search, Opportunities and Scan changes resolve missing labels through version-scoped names collected from scans, TSM rows and catalogs; crafting and board depth already use catalog labels. Name policy lives in DATA-02 (`requirements.md`). Stored observations and archives remain unchanged.
- **Storage:** code supports schema 5 with backed-up, idempotent migrations (see `design.md` → Schema migrations). The original local `data/brownstone.duckdb` remains at version 4, untouched by this work; the next app startup for any selected source or explicit import upgrades it and creates the version-4 backup. Earlier backups remain intact. Old manifests are adapted only in memory.
- **Quality gates:** CI runs Ruff (including a complexity limit of 10), mypy and the tests with a branch-coverage floor of 88% (93.77% today) on macOS and Windows from the lock file, including the Streamlit UI test. One function, the scan parser's hot loop, is exempt from the complexity limit and listed as debt in `design.md`. Config loads into typed, individually validated `Source` records.

- **Scanning addon (SPIKE-008, done):** `addon/BrownstoneScan/` is a read-only addon that scans on a click or `/bscan start` and saves listings to SavedVariables (`schema_version` 1; sample at `tests/fixtures/brownstone_scan_sample.lua`; install and measurements in `addon/README.md`). Verified on the Forever beta, build 70205, interface 16001: one full scan of the Stormwind Alliance Normal house, 101,485 listings in about 10.6 s, 24 MB file, written correctly. Decision and format are in `requirements.md`. Scans are imported as described above.
  - **Real scan kept** at `data/inbox/addon-scans/BrownstoneScan-forever-beta-2026-10-04.lua`. That's a byte-for-byte copy (SHA-256 `207a2b95…`) of the game's SavedVariables file: scan `20261004T164730Z-c651bd`, Alliance Normal house. It's ignored by Git like all of `data/`, so back it up with `data/`.

## Limitations

- **Beta scans so far:** four complete Normal Alliance scans (16:47Z, 17:46Z and 22:54Z on 2026-10-04, and 20:34Z on 2026-10-05) and one stopped scan, all from the beta and identified separately from the live house by schema 4 (DATA-03). The last two are addon 0.2.0; the newest has 97,239 listings of 3,059 items and is kept in bronze as a 517 KB `.lua.gz`.
- The addon was measured on one beta house only: not the Roleplaying or a neutral house, and `/bscan start` without the button is untested. Beta region and realm values are generic, so scans are identified by auctioneer, zone and label. The `.toc` interface number 16001 may change with beta builds.
- Required skill levels are display-only.
- The Recipe catalogs page shows a catalog's game build only when its archived page is on this machine (`data/` isn't in Git). Regenerating records the uploaded file's name as the manifest's `original_name`, as the CLI does.
- Craft routes remain local to each catalog; routing across professions is STORY-015b.
- **Forever values still to confirm in game** (shown on the recipe view):
  - **Output counts:** every recipe keeps Wowhead's list value of 1, marked `output_quantity_verified = false`, because its spell tooltips show "(2)". Craft one Bolt of Linen Cloth on the beta and count.
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

Expected: 308 tests pass, offline; `ruff check .` and `mypy` report no issues. Windows uses `.venv\Scripts\python.exe`. Live ingestion is a separate manual check: **Refresh from TSM** in the app.

Scan preview verification: `tests/test_scan_preview.py` covers mixed new/duplicate/partial/empty scans, UTC metadata, missing data directories, no preview writes, old-schema read-only preview, shared time/listing validation, other-house scans listed but not selectable, ID conflicts, exact-byte archives, empty/unknown/duplicate selections, configuration/file/duplicate-state invalidation (including the final writer check), bounded reads, deterministic read changes, unreadable/truncated/malformed files, partial pricing, commit-failure rollback/failed manifests and shared CLI subset guidance, including an unselected malformed entry. AppTest in `tests/test_app.py` covers preview → selection → subset import, duplicates-only reminders, empty selections, retryable errors, stale reviews, other-house rows, the result replacing the reviewed table, page-load upgrade of an existing addon database and source/configuration switching, while retaining the TSM and existing-page regressions.

Real-data preview/import was checked on 2026-10-05 against temporary copies of the database and a 51 MB schema-1 scan file (about 2–3 s per preview or import; originals unchanged).

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
