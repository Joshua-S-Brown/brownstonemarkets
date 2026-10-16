# Brownstone Markets backlog

Planned product work, in priority order. Rules live in `requirements.md`, architecture in `design.md`, current state in `status.md`; completed work is recorded there and in Git, not here.

- **Now:** the active item, with agreed acceptance criteria.
- **Next:** ordered and ready to start (story plus acceptance criteria).
- **Later:** valuable but unscheduled, often waiting on an item above.

A story ready for handoff names the rule IDs and `design.md` headings it depends on and carries its own implementation notes (code pointers, decisions, expected real-data numbers), so a session needs only the story ID (`docs/prompts/story-handoff.md`) and prints it and the rest with `python -m brownstone rules --story <STORY_ID>`.

## Direction (groomed 2026-10-04)

WoW Forever launches **4 November 2026**; **21 October is the last full beta testing day** (official dates linked in `requirements.md` → *Product direction*). As of 2026-10-04 (sources in `requirements.md`):
- Blizzard's API publishes no Forever auction data, and its Classic Era auction endpoints have returned 404 since late 2024.
- TSM has no Forever data.
- Forever's own price sites are fed by players running scanning addons.

So the dependable path to Forever prices, and to the listing-level inventory that market models need, is our own addon scan. Classic remains the stand-in for everything that only needs aggregate prices.

## Now

Nothing in progress; the next story is the top of *Order* under Next: Team in the web app (STORY-084). Market and Today moved to the web app in STORY-082 and STORY-083.

**Before STORY-081:** done 2026-10-16. Node.js 24 LTS (v24.22.0, npm 11.19.1) is installed on the Mac in `/usr/local/bin`. The Windows PC needs nothing: it only plays and drops scans (OPS-03).


Scan format 3 (STORY-023) and the reload/clear buttons (STORY-029) are accepted on the beta with addon 0.3.1; the measurement record is in `addon/README.md`. Brownstone can now run on our own addon scans alone (STORY-010). Launch market remains Forever US, Roleplaying, Alliance (`forever-us-roleplaying-alliance`); the beta currently offers only Normal servers, so the configured example source is `forever-us-normal-alliance`.

**Through the last full beta testing day, 21 October** (manual, in game):
- **Keep scanning.** Twenty-five complete scans of the Normal Alliance house are imported (`status.md` → *Limitations*). Take more, at least 15 minutes apart, **at different times of day and on different days**, so the diff and timing work (STORY-018; *Market timing and a daily brief* under Later) has something to start from. The routine: scan, `/reload` (the game writes scans to the file only then, or on logout), import, and only then `/bscan clear` and `/reload`. A Roleplaying or neutral house scan, if reachable, tests house identification. This is a manual habit, not automation.
- **Confirm the Forever catalog's unconfirmed values** (`status.md` → *Limitations*). Learn Bolt of Linen Cloth and check how many it makes: the profession window may show the count on the product icon, and crafting one (2 Linen Cloth) settles it. Buy your crafting reagents (thread, dye, flux, vials, spices) from a trade-supplies vendor rather than the auction house when you need them: the addon records each purchase, and Claude confirms the marked vendor prices from it. Also decide whether Runecloth Bag's dyes are really post-launch: both are listed on the beta auction house.
- **Widen the Forever catalogs** (manual saved pages and `python -m brownstone recipes`): the rest of Tailoring, then the professions you plan to level at launch. The board and Today's *Craft* list only cover catalog recipes, so this is what gives them something to show.
- **If any yield is more than 1** (now unlikely: Wowhead's "(2)" is an effect number, not a count; see `requirements.md` → CRAFT-08), *Multi-yield costing* (Later) moves to the top of Next: the Forever board's costs are wrong until it exists.
- **Prepare a beta character for the character-data tests** (added 2026-10-06): level one **gathering** profession (Mining or Herbalism) and one **crafting** profession that uses it, far enough to gather, craft, post, sell, let something expire and cancel. Keep a little gold to buy and vendor with. This is what STORY-032 and STORY-033 are tested on.
- **Test the new addon builds in game** once STORY-031 to STORY-033 and STORY-040 are ready (aim: by 13 October, leaving a week of beta). Each run records what actually happened, so it can be preserved as a test fixture before the beta closes:
  - **Item info pass (STORY-031):** after a scan, how many items still lack vendor price, item level and stack size, against the 0.3.1 numbers.
  - **Snapshots (STORY-032):** gold and bags written on logout and on `/reload`; bank only after opening the bank; two characters on the same account. With a new character (added 2026-10-07: no spare bags yet), test the backpack, any equipped bags, the main bank and one bank bag slot if you can buy it. That bank bag must appear in the bank snapshots (taken when you open the bank) and never in the logout snapshot of your bags. Whatever you can't test yet moves to *Snapshot coverage* under Later.
  - **Event journal (STORY-033):** buy from the auction house, post, cancel, let one expire, sell one; open the mailbox and take the invoice and the returned item; craft; gather; buy and sell at a vendor; send mail between your own characters. Note which events fired and with what values.
  - **Active auctions (STORY-040):** open the Auctions tab before posting, after posting, after a cancel and after a sale, and note whether the list arrives without opening the tab.
  - **Professions (STORY-041):** open each profession window (Mining and Engineering on the new character; Tailoring and Enchanting on the druid), learn one new recipe and open the window again, gain a skill point, then log out.
  - **Who checks (added 2026-10-07, product owner):** the product owner only plays: gathering, crafting, posting, mailing and logging out. Claude checks every session's file with the STORY-042 report and says what is confirmed, missing or wrong. Nobody reads the addon file by hand.
  - **Unconfirmed claims** (`requirements.md` → *Product direction*): time from a sale to its gold in the mailbox, The Black Market vendor waits for live (*Later*). Deposits and postage between your own characters were measured on 2026-10-15.

## Next

**Agreed order (groomed 2026-10-05):** the app is almost all tables today, so user-facing analysis now gets its own lane in Next instead of waiting behind launch preparation. The layers, each building on the one before:
- **Scans** (exists) → **market metrics** (exists; ADDON-10 in `requirements.md`) → **analysis views** (item page, charts, sellers) and the **Today** page (what to buy, craft and sell now).
- An optional AI narration layer can come later. It may only explain those defined metrics, never invent numbers (*Out of scope*).
- Time-of-day and weekday patterns need weeks of live scans (*Market timing* under Later). Everything in Next works on a single scan or a few, so it can be built and tested on beta scans now.

**Order** (regroomed 2026-10-13 after Claude's player walkthrough of the beta data, 2026-10-14 after the addon comparison, and 2026-10-15):
1. STORY-085 Ledger and Data in the web app
2. STORY-086 Supply chains
3. STORY-087 retire NiceGUI
4. STORY-062 sales speed and suggested stock levels (STORY-027's time-left bounds accepted 2026-10-16; refine first)
5. STORY-026 scan coverage and rhythm
6. STORY-028 sellers and supply chains (blocked: see *Seller capture* under Later)
7. STORY-006 replay

**Web app lane (decided 2026-10-16, product owner):** NiceGUI still felt like stacked, scrolling containers rather than an application. The owner approved the clickable prototype in `docs/prototype/web-app.html` (open it in a browser; its figures are examples) as the direction: an app shell, an inspector that opens records in place, and Today as one route. The rules are UI-18 in `requirements.md` and the structure is *Web app (UI-18)* in `design.md`. Each story moves one place and removes its NiceGUI view, so the app works at every step and launch never waits on the whole migration. Each web story keeps calculations, `today_version` and rules unchanged unless it says otherwise. Its real-data check is a side-by-side comparison with the NiceGUI page on the same source and scan: same numbers, same evidence.

**Pending an in-game beta check:** none. STORY-027's time-left bounds were accepted on 2026-10-16; STORY-044, 071 and 077 were confirmed on 2026-10-15; STORY-031, 032, 033 and 040 on 2026-10-13 (`status.md`).

**Done** (outcomes in `status.md` and `requirements.md`; story text in Git): STORY-015b, 021, 025, 030, 031, 032, 033, 034, 034b, 035, 036, 037, 038, 039, 040, 041, 042, 043, 044, 045, 046, 047, 048, 049, 050, 051, 052, 053, 054, 055, 056, 057, 058, 059, 060, 061, 063, 064, 065, 066, 067, 068, 069, 070, 071, 072, 073, 074, 075, 076, 077, 078, 079, 080, 081, 082, 083, 084 and SPIKE-009/009b.

### STORY-085 — Ledger and Data in the web app

Added 2026-10-16; refined 2026-10-16 after the STORY-084 review. Stock becomes Ledger (`navigation.QUESTIONS['Ledger']`: *Where did our gold and goods go?*) and Data → Import becomes a sheet. UI-15, UI-16, the Stock rules and ADDON-06 are unchanged: this changes where they are shown, not what they compute.

As the owner, I want gold flow, holdings and restocking in one Ledger, and imports from a sheet, so that money questions have one home and importing never takes me away from what I'm doing.

Acceptance:
- **Ledger page:** `/app/ledger?source=` (the rail's Ledger and ⌘K's Ledger place open it). A day selector (*Last 7 UTC days* default, *Last 30*, *All*, ending on today's UTC day) is kept per tab and source in `sessionStorage` like Team's window, not in the URL. Summary strip for the selected days: team gold in, out and net; *N of M bags pairs reconcile* (UI-15 rule 9, pairs whose later capture is in the range; unknown residuals counted separately); cautious held value from Stock with its *at listed prices* label and no-price count (held value ignores the day range). Then: a daily team in/out chart (Recharts, a table when there are no days); team totals by UI-15 category; per character, UTC day and category in/out; gold reconciliation; Items (UI-16 team units in/out, per character/day/category, own-character mail with *sent, not yet received* / *received, no send recorded*, bags and bank residuals first, *possibly incomplete* labels); Restock (below).
- **Search and filters:** one name-or-item-ID search and *Our catalog chains only* switch filter Items and Restock together, as Stock's controls do now (`stock.filter_rows` and the same catalog-chain set). Filtering and every total, count and sort are computed in `brownstone`, never in `api/` or the web.
- **Movement provenance:** each category row (gold and items) opens its movements on demand: UTC time, machine, entry ID, signed copper or units, allocation parts, reasons, and `ledger_version` / `item_ledger_version`. Baselines/gaps, excluded counts, match windows and before/after snapshot IDs are in the evidence footer through `Evidence`. Character names link to the STORY-084 character record by the full `(name, realm, faction)` key; own-mail counterparties too. Item names use `ItemLink`: UI-16 movements are integer item IDs without variants (base link); Restock rows keep their exact ADDON-08 identity (variant link).
- **Restock:** Stock's capture chips (character, location, age, empty, partly readable, excluded unreadable captures), tiles (items held, value at listed prices, items short, cost to fill within limits), the restock table with short items first (held, target, short with *at most*, buy now, wait, unlisted, buy cost, fill cost or *insufficient listings*, value) and holdings by character and location on demand. Target and purchase evidence (limit text, effective limit, *Market value missing · buy limit unknown · wait*, whole-stack units, above-limit cost) is on demand per row.
- **Targets:** *Set stock targets* opens a dialog with a fresh draft of the saved entries; Update and Remove change only the draft; Save sends the whole list to `POST /api/ledger/targets?source=` (`{entries: [{item_id, target_units, buy_copper, buy_percent}]}`), which validates with `stock.Entry`/`stock.save_entries` and atomically replaces the file. A rejected save returns 422 with the reason and keeps the last saved file, including when the existing file is damaged (the damaged file is preserved and explained). Names come from `stock` results only, never guessed from text. Success invalidates the Ledger query; Today is unaffected.
- **Partial failure:** gold, items and stock load independently: each failure shows in its own area with Stock's existing wording and the others still render (the three `nicegui_stock` failure tests move to the API).
- **Ledger API:** `GET /api/ledger?source=&days=7|30|all&q=&chains=` and `GET /api/ledger/movements?source=&ledger=gold|items&name=&realm=&faction=&day=&category=`. One load of `ledger.load`, `item_ledger.load` and `stock.load_stock` per source, reused until the database, config, hourly bucket or the source's targets file changes (add the targets file's stamp to the cache key); search, days and lazy movements filter that cached load. Integer copper and integer units, null for unknown; types from the regenerated `schema.d.ts`.
- **Data sheet:** opened from the rail's Data badge, the data-status chip, and `?sheet=data` on any `/app` page (removed from the URL when closed; `placeURL('Data')` and Today's *Open Data* links use it). Contents, from `import_review` as now: saved-evidence chips; the ⓘ details (source, market, scan path, machine, drop folder, partial and best-effort notes); *Check for new scans*; the reviewed result (New / Up to date badge, summary or input summary, problems including *Selection differs from the default*, file status and clear lines, Import); Details (scan, journal and character preview tables, files and latest drops, the clear reminder, the scan-ID or file selection); messages; watchlist hits after a successful import; *What's imported* (`holdings_sections`) loaded only when opened. A non-addon source shows only the CLI refresh line.
- **Data API:** `GET /api/data?source=` (chips, details, provider: reads saved evidence only), `GET /api/data/imported?source=` (*What's imported*), `POST /api/data/review?source=` and `POST /api/data/import?source=`. The review is a POST, not the earlier draft's GET: it reads the game file and drop folder, which ADDON-06 allows only on an explicit click, and a GET would be refetched on focus or retry. The server keeps the reviewed `ScanPreview`/`InputPreview` (its exact bytes) in memory, one per source, bound to the source's configuration; a new review replaces it. The review response carries an opaque `review_id`, the default selection and the choices. Import takes `{review_id, selected}`, consumes the review before writing (as `ImportPage.collect` does) and calls `scan_inputs.import_inputs` or `pipeline.import_scans` with `reviewed=`. An unknown, replaced or other-configuration `review_id` returns 409 *Review out of date: check for new scans again*. A second import while one runs in this process returns 409 *Another import is running* (a non-blocking lock around the writer); the database's own writer check still applies across processes. Stale-preview and other import failures return 200 with `import_review.import_failure` messages and no review, as Data shows them now; the drop-folder flow returns a fresh review with the default selection after import. Move `nicegui_import.watchlist_hits`'s database read into `brownstone` (for example `import_review.watchlist_hits(config, catalogs)` returning text or an error line).
- **After import:** a successful import invalidates every query for the source and the shell's `/api/sources` inventory (the waiting badge), so Today, Team, Market and Ledger reload; server caches already rebuild on the database stamp. Switching source discards the sheet's review on the client and the server (UI-07: a review never crosses sources).
- **Shaping moves first:** `views/nicegui_stock.py` and `views/nicegui_import.py` compute values a view must not: `capture_text`'s states, `table_row`'s *at most* and insufficient-listings choices, `limit_text`'s limit kind, `items_answer`'s per-filter `item_ledger.team` totals, zero-residual pair counts and residual-first sort, `items_section`'s filter, the gold reconciliation count, and Import's *new* test, selection-differs test and file choices. Move them into `brownstone` (a new `ledger_view.py`, and `import_review` for Data) as pure functions returning values, not text, with offline tests; the API and both views use them until the NiceGUI views go.
- **Retire:** after the side-by-side check, `views/nicegui_stock.py`, `views/nicegui_import.py`, `tests/ui_trial/test_nicegui_stock.py` and `tests/ui_trial/test_nicegui_polish.py` go, the three import tests leave `tests/ui_trial/test_nicegui_app.py`, and its place test becomes a redirect test. Every NiceGUI place now redirects with the same source: Stock → `/app/ledger`, Data → `/app/today?sheet=data`, and `/` without a place → `/app/today`; `views/nicegui_common.py` and any unused `nicegui_theme` helpers go, and `pyproject.toml`'s mypy list drops removed files. The NiceGUI server itself stays for STORY-087. Nothing is removed 28 October–5 November unless the web page was used in a real play session (UI-18).
- **Web conventions (from STORY-082–084):** evidence through `web/src/ui/Evidence.tsx`; money through `Money` (unknown, never 0c); `ItemLink`, pills and tips from `ui/parts`; `DataGrid` sorting on integer copper and units; the Ledger place, the chart and the Data sheet's review are lazy-loaded so `npm run build` stays without the chunk-size warning. Writes use `post` with the launch token.
- **Docs:** `requirements.md` has 72 bytes and `design.md` 4 bytes under their size guards; each edit must trim at least as much as it adds in the same section. UI-15 rule 10 and UI-16 rule 10 say Ledger instead of Stock; the Stock rule's *UI-08 presentation* bullet and UI-07's Data sentence become UI-18 wording (Ledger strip and sheet), and UI-18 records the day selector and the server-held review. `design.md` → *Stock contracts*' `nicegui_stock` paragraph describes `api/ledger.py` and `ledger_view`, and *Scan import preview*'s last sentences describe `api/data.py`'s review registry and lock. Update `status.md` → *Stock*, *Gold ledger*, *Item movements*, *App* and *Data/CLI*, and the expected test count.
- **Offline tests:** the moved helpers; day ranges at UTC midnight boundaries (a movement at 23:59:59 and 00:00:00) and *All*; search and chains filtering totals, not only rows; lazy movements for one category row; partial failures; target save, refusal with a damaged file kept, and cache invalidation on save; review/import: a subset import matching the CLI's stored records, an obsolete or other-source `review_id`, a stale preview after the file changes, a concurrent second import (409), a preview error, a non-addon source, the drop-folder fresh review and rejected-file cleanup lines, and watchlist hits; `?sheet=data` opening and closing; source switch discarding the review. Each `nicegui_stock`, `nicegui_polish` and import ui_trial test that tests a rule moves to an API or Vitest test (moved, not dropped). No test reads a real game file or drop folder.
- **Real data (Ledger):** on the beta source with a copy of `data/`, scan `20261016T113727Z-eb77d0`, compare with the NiceGUI Stock page before removing it. Expected with *All* days (read 2026-10-16): gold 385 movements, team in 5,878c, out 4,079c, net 1,799c; 76 of 76 bags pairs reconcile; no excluded money baselines; three unreadable bags captures excluded. Categories in/out: auction sale 1,094/0, deposit refund 916/0, vendor sale 1,197/0, mail in 601/0, coin loot 181/0, other 1,889/110, auction deposit 0/1,338, training 0/1,205, mail out 0/1,111, vendor purchase 0/236, repairs 0/61, auction purchase 0/18. Items: 1,007 movements, 46 baselines/gaps, team 736 units in and 596 out; bags 73/76 and bank 10/10 pairs without residuals; 11 own-mail rows, one *sent, not yet received*. Stock: 10 captures, 37 items held, 4,363c at listed prices excluding 19 no-price items, no targets saved. Set one target on the copy (for example Linen Cloth 2589) and compare the restock row with NiceGUI on the same copy. If newer evidence was imported before you start, compare with NiceGUI on the same copy and explain each difference.
- **Real data (Data):** the configured drops are currently all duplicates (latest `mac` drop and `windows-pc` drops fully imported), so: (1) on the real source, *Check for new scans* in the sheet must match `python -m brownstone --source forever-us-normal-alliance-addon --preview` (read-only) and NiceGUI Data's review; (2) copy two real drop files into a temporary drop folder and import one of them through the API into an empty copy of the data directory, and the same file through the CLI into a second empty copy: manifests, scan and record counts and stored rows must match. Never import into the real `data/`. Screenshots at 1280 and 390 px of Ledger (with an open movement row and the targets dialog) and the open sheet with a review.
- Depends on STORY-081 and STORY-084. Rules: UI-15, UI-16, ADDON-06, OPS-03, UI-07, UI-08, UI-18, *Stock* and *Watchlist* (`requirements.md` → Interface). Design: *Stock contracts*, *Gold ledger contracts*, *Item ledger contracts*, *Scan import preview*, *Multiple input files (STORY-037)*, *Web app (UI-18)*.

### STORY-086 — Supply chains

Added 2026-10-16. A new place: the prototype's recipe graph. Built after the moves, so it adds a feature rather than delaying them.

As a gold maker, I want to follow a craft back to its raw materials and see where the margin is made, so that I can choose between buying and crafting each step.

Acceptance:
- **Graph:** for a chosen output (the ranked crafts first, then search), the CRAFT-03/CRAFT-12 route as columns from raw materials to the output, with quantities on the edges, each node's unit cost and route (buy, craft by whom, vendor, held), and the team's ability to make each step. Cross-profession steps show the other character.
- **Buy or craft:** each intermediate shows both costs where both exist, the chosen route highlighted. Switching a step recalculates through the existing route functions with that step forced; if the engine can't force a route yet, add that option to `crafting` with tests, never a second costing path (*Value-add chart*, Later).
- **Per craft:** a waterfall from sale price through the cut and each leaf material to profit, all in copper; a missing price stops the waterfall with the reason, never zero.
- **Batch:** a slider (1 to the Today craft cap) showing leaf quantities, spend and profit, without listing-depth claims beyond CRAFT-09.
- **Add to tonight:** adds the craft to Today's choices through STORY-083's choices endpoint.
- **Offline tests:** forced routes, a missing price, a cross-profession route, a vendor ceiling (CRAFT-04) and choice handoff.
- **Real data:** Linen Bag and Blue Linen Vest routes match the Market record's *Made from* costs; screenshots at 1280 and 390 px.
- Depends on STORY-082 and STORY-083. Rules: CRAFT-03, CRAFT-04, CRAFT-09, CRAFT-12, UI-18. Design: *Crafting calculation*, *Team recipe graph (STORY-015b)*, *Web app (UI-18)*.

### STORY-087 — Retire NiceGUI

Added 2026-10-16. Last web story: once every place is in the web app.

As the owner, I want one app on one stack, so that nothing is maintained twice.

Acceptance:
- **Server:** a plain FastAPI app on uvicorn (`brownstone_app.py` or similar) replaces `nicegui_app.py`, keeping loopback binding, the launch token, the pywebview window, browser fallback, idle shutdown and UI-05's restart rule. `nicegui` leaves `pyproject.toml` and `requirements.lock.txt`; `fastapi`, `uvicorn` and `pydantic` are declared directly.
- **Docs:** UI-07's NiceGUI rules are replaced by UI-18 (keep its URL and back-link rules there), UI-08 7's NiceGUI clause goes, and *App and modules* describes the web app. `requirements.md` and `design.md` end below their current ceilings, and the ceilings in `brownstone/gates.py` drop to match.
- **Tests:** `tests/ui_trial` is gone; `test_retirement.py` checks NiceGUI is absent; coverage settings name `api` instead of `views` and NiceGUI entries.
- **Real data:** a full play-evening walk-through on the beta or live source (import, Today route, Market, Team, Ledger), with screenshots.
- Depends on STORY-082 to STORY-086 (STORY-086 may follow if the owner prefers). Rules: UI-05, UI-07, UI-08, UI-18, OPS-01. Design: *App and modules*, *Web app (UI-18)*, *Quality gates*.

### STORY-026 — Scan coverage and your play rhythm

As a gold maker, I want to see when I've scanned and when I usually play, so that I know which times are covered and when it's worth making time to log in.

Acceptance:
- **Coverage grid:** scans by hour and weekday in local time for the selected source, with counts and gaps.
- **Your rhythm:** the hours and days you usually scan, from scan times only.
- **What's missing:** which slots need scans before timing claims can be made, with the thresholds recorded in `requirements.md`.
- Works on beta scans now. Depends on nothing (uses `addon_scans`). Feeds *Plan ahead* under Later.

### STORY-062 — Sales speed and suggested stock levels

Added 2026-10-13 (product owner: "turnover, how fast items sell in the market is really kind of the point… I don't know how else you determine how much stock or inventory you keep"). Brownstone only. Needs STORY-027 and enough consecutive scans: refine the minimum before handoff with the beta's scan count. Draft.

As the owner, I want to see how fast each item moves on the auction house and a suggested stock level from it, so that targets come from evidence instead of guesses.

Acceptance:
- **Removal rate** per item from STORY-027: units removed per hour across consecutive scan pairs within the maximum gap, as a median with the number of scan pairs it rests on. Always *removed*, an upper bound on sales, never *sold*. Too few pairs says so instead of a number.
- **Turnover:** listed units divided by the removal rate (how long today's supply would last), shown beside it.
- **Suggested target** in STORY-061: removal rate × the days of cover the owner chooses (one setting), capped at a share of typical listed supply so we never plan to hold more than the market moves. Shown next to the manual target, never replacing it.
- **Shown** on the Market explorer's item page (STORY-055) and in Stock (STORY-061).
- Feeds *Sales speed instead of a fixed cap* (Later) for Today, which stays a separate story.

### STORY-028 — Sellers and their supply chains

As a gold maker, I want to see who supplies each market and which crafting chains they focus on, so that I can choose chains with less competition and expect undercuts.

Acceptance:
- **Per item:** sellers by share of units listed, their prices against the lowest and typical price, and how that changes between scans.
- **Per seller:** what they list, grouped by catalog chain (materials, intermediates and outputs by catalog membership, never names), how much, and how often they repost.
- **Per chain:** how concentrated supply is (the share held by the top sellers), so crowded and open chains are visible.
- **Private:** seller names stay on this machine, as recorded in STORY-023's decision.
- Depends on seller capture, which the beta's bulk scan does not provide (*Seller capture* under Later), and the implemented market metrics layer (ADDON-10).

### STORY-011a — Survey third-party scan sources

Split from STORY-011 at grooming (2026-10-04); ingestion is STORY-011b under Later.

As a gold maker, I want to know whether any trustworthy third-party Forever scan source can be used, so that I can plan around it rather than guess.

Acceptance:
- **Survey and record.** Check AHledger, Booty Bay Broker and TSM for an official export or API and terms that allow personal use. Record the result in `requirements.md`, closing that open decision. No code.
- If a source qualifies, STORY-011b moves to Next.

### STORY-006 — Replay and rebuild local data

As the product owner, I want derived data rebuildable from the raw archive, so that schema changes and validation fixes never strand old scans.

Acceptance:
- **Deterministic rebuild.** One command rebuilds silver and DuckDB from bronze into a fresh database without modifying bronze. Running it twice gives identical results.
- **Every source.** Covers TSM CSVs and addon scans (bronze `.lua` and `.lua.gz` files; silver already holds per-scan listings and prices).
- **Documented.** It's the recovery procedure for partial runs referenced in `status.md`. Backup is STORY-016.

## Later

**Lots and cost basis** (deferred from STORY-034 on 2026-10-15): which purchase each sold or crafted unit came from, for realised profit. Needs STORY-034b's item movements and a rule for held stock of unknown cost.

**Optional client-version cutover guard:** investigate whether recorded client versions can flag a misconfigured beta/live source during STORY-020b and first live imports. Source configuration remains authoritative (DATA-03); STORY-017 adds no client-version evidence checks.

These are grouped by what unblocks them.

**Black Market vendor** (moved from STORY-036 on 2026-10-15; check during live, once the owner reaches it): whether it exists, where, and its prices (claimed in `requirements.md` → *Product direction*). If it does, open it with the addon; STORY-036's rules then mark its unlimited items.

**Seller capture** (found 2026-10-06; blocks STORY-028): the Forever beta's bulk scan returns no seller names (ADDON-07). Left blocked until after go-live (product owner, 2026-10-06): check whether live scans return seller names. Only if they don't, decide between another read-only way of getting them (such as per-item searches, at the cost of many more auction-house requests and a longer scan) and dropping or reshaping STORY-028.

**Snapshot coverage** (added 2026-10-07; needs a character with more bags and bank slots, possibly after go-live): STORY-032's checks that a new beta character can't reach. Every equipped bag slot full; several bank bags, including the last bank bag slot; the keyring and any reagent containers the client has; a full bank compared item by item; and bank-close reads with many bags open. Play those actions, then Claude checks the client's `container_layout` values in the dropped file. Until then, container coverage is confirmed only for the containers actually tested.

**Today, later versions** (captured 2026-10-06 with the product owner; each extends STORY-025 once its data exists):
- **Sales speed instead of a fixed cap:** replace *most crafts per item* with how many units of the output disappear between scans. Needs STORY-027 and a few weeks of live scans; label it removed, not sold.
- **Stockpile:** materials below their own multi-day typical price, worth buying ahead for recipes you craft often, with a holding limit tied to gold available. Needs price history across days (*History chain*), so after launch.
- **Volatility:** how much an item's typical price swings across scans, shown as a risk note and used to demote unstable crafts. Needs the same history.
- **Restock:** moved to Next on 2026-10-13 as STORY-068.
- **Mailbox holdings** (split from STORY-068, 2026-10-14): count items in each character's last captured inbox (the journal's `MAIL_SHOW`/`MAIL_INBOX_UPDATE` state) as held after bags and bank, with *take from the mailbox* in the Queue. Needs a rule against counting an item twice when it was taken into bags after the inbox was read.
- **Reach cost from holdings** (split from STORY-068): CRAFT-11's cost to reach a skill uses holdings first and walks the listing ladder for the whole quantity (80 Linen Cloth costs more than 80 × the cheapest), as Today does.
- **Routes that use holdings** (split from STORY-068): choose a different route because of what is held (craft bolts from held Linen Cloth when the Board's route buys bolts). STORY-068 only uses holdings along the Board's route.
- **Whole chains:** ore → bars → armor across professions, with the gain at each stage (sell bars or craft on). Routing exists (CRAFT-12).
- **Gold per hour:** if the scaled minimum gain feels wrong in play, try a time-based minimum instead. Decide after using version 1.

**Demand from your own scans** (needs repeated scans and STORY-018; optional sources from STORY-011b can add more data points):
- *Removed listings* (STORY-027) is implemented; its Forever time-left bounds were accepted on 2026-10-16.
- **Did the board hold up?** Whether "potential craft" rows were still profitable at the next scan. A tiny check is possible with beta scans; it means something after one to two weeks of live scans.

**Market timing and a daily brief** (requested 2026-10-04; needs post-launch history, not beta scans (STORY-017)). The goal is to know when to buy and sell each kind of item (materials, crafted goods, equipment), and to open the app to a short list of the day's priorities without being online all day.
- **Honest limits:** scans happen only when you are at the auction house, so hour-of-day and weekday patterns are sampled at your playtimes. A pattern is shown only with its coverage (scans per hour and weekday), and claimed only where coverage is enough. Weekday effects such as the weekly reset need at least four weeks. Optional sources (STORY-011b) could fill hours you don't scan.
- **Steps** (each needs the one before):
  1. **Scan coverage:** now STORY-026 in Next.
  2. **Timing profile:** per item, and for groups by catalog role (material, intermediate, finished; never inferred from names), price and supply by hour and weekday, with a confidence label. A weekday chart overlays price against supply (units listed, never called demand or volume sold). "Cheapest to buy" and "best to sell" windows only where coverage supports them.
  3. **Daily brief:** STORY-025 (*Today*) is its rule-based first version on the newest scan. This step adds the timing profile's advice: what to buy now or hold, and what to post now or wait on, each with its coverage.
  4. **Plan ahead** (requested 2026-10-05): next-day planning, not only right now.
     - **When to log in:** suggested sessions that combine your usual play times (STORY-026) with the hours the timing profile marks as best to buy or sell, and how much each session is worth on current evidence.
     - **Key times and milestones:** a calendar of known events entered by hand, each with its source (weekly reset, maintenance, holidays, patch days, launch-week phases, raid unlocks such as one claimed for 9 December, once sourced). Their effect on prices is shown only once enough scans cover them.
     - **Tomorrow's plan:** what to buy tonight for tomorrow's crafts, and which listings will expire before your next usual session (needs time left, STORY-023).

**History chain** (each step needs the one before):
1. Replay (STORY-006).
2. A storage decision (backup is STORY-016).
3. Routine scanning. An addon scan needs you at the auction house, so this is a habit, not a scheduler. *Scan coverage* above helps.
4. History, volatility and confidence features: per-item trend and spread need about ten or more scans over a week or more, so not before mid-November.
   - **Stockpile safety** (suggested 2026-10-04): which materials are safe to hold. Plots relative volatility (coefficient of variation, so cheap and expensive items compare) against the *Removed listings* rate. The window is a number of scans, not days, and each point shows its scan count. Items are catalog materials or a chosen list, never picked by name. Unit-count changes between scans aren't turnover, because new postings offset sales.
5. Backtesting the ranking policies.
6. Alerts.

**Classic demand context** (was STORY-003 in Next; moved at grooming, 2026-10-04, because it serves the stand-in, not Forever):
- TSM's Classic regional file is ingested as its own source and never mixed with realm prices. Its columns are `avgSalePrice, saleRate, soldPerDay` (feasibility confirmed 2026-10-04).
- The board shows sold-per-day and sale rate with their own timestamp, labeled as context, not a promise to sell.
- *Removed listings* (STORY-027) is the Forever equivalent and should replace or check it.

**STORY-012 — Compare a market with a reference market** (moved from Next at grooming, 2026-10-05: its own evidence shows Forever and Classic prices diverge too much for a strong sanity check, and it targets the first weeks after launch):

As a gold maker, I want to see an item's price on Forever next to its price on Classic Era, so that I can sanity-check Forever prices and spot import errors, especially in the first weeks after launch.

Acceptance:
- **Explicit pairing.** The user picks two configured sources, each a different market. Items pair on item ID only inside this view, and the view is labeled as a comparison of different markets. Nothing from it feeds crafting, the board or any price basis (DATA-03, DATA-08).
- **Shown with care.** Each side shows its own source, scan time and freshness, plus the ratio between them. Items missing or unpriced on either side are listed, never treated as zero.
- **Evidence for the idea:** on 2026-10-04, 2,323 of 2,927 priced Forever beta items were also priced on Mankrik. Common materials were within about 0.5–2× (Linen Cloth 38c vs 32c), but scarce high-level ones diverged widely (Runecloth 2g 55s vs 10s 75c). The median ratio was 0.32.

**STORY-011b — Third-party scan ingestion** (only if STORY-011a finds a qualifying source):
- **Separate source.** A qualifying feed is ingested as its own source for the same market, with raw preservation and provenance like every other source.
- **Visible and optional.** The board shows which source each price came from. Disabling the source leaves everything working on your own scans.
- **Cross-check.** Where both sources cover an item, show how far apart they are, as a data-quality signal.

**App conveniences** (moved from STORY-014 at grooming, 2026-10-04):
- **Find the scan file:** on a click, offer the SavedVariables files under the usual WoW install folders, one per account, and save the choice as `scan_path` in the untracked `config/market.local.toml`. Your path is already set, so this only helps a new machine or account.
- **In-game confirmations:** tick off values checked in game (a yield, a vendor and its price, a post-launch decision) with a date, written to the selection file, then Regenerate. For now there are only a few, edited by hand.
- **Browse filters:** items used or made by any catalog (membership, not names) and a minimum listing count.
- **Market for our levels** (walkthrough 2026-10-13): Market's front-page lists were dominated by Wool, Silk and Mithril-level items while the team was level 1–8. Filter or order them by the skill bands the team can reach (Team's window), with the full lists one click away.
- **Plain identity labels** (walkthrough 2026-10-13): *base* and *unresolved* tags, and items listed twice under each, mean nothing to a player. Say *variant* or *unidentified link* only where it matters, keeping identities separate (ADDON-08).
- **Shorter removal history** (walkthrough 2026-10-13): an item page lists every scan gap, mostly zeros. Summarise (removed early and could-have-expired totals over the comparable gaps), with each gap on demand.
- **Vendor value as a floor** (2026-10-14, from CraftProfit's *vendor net* and TSM's posting rules): for leveling crafts whose auction market is flooded, show what the output fetches from a vendor (vendor sell price × output − cost) beside the auction profit. *Sell* never suggests a post price at or below the vendor price ÷ (1 − cut); it says *vendor it instead*.
- **Buy a pattern to level cheaper** (2026-10-14, from ProfessionMaster): when a recipe item listed on the auction house would make a CRAFT-11 reach path cheaper including its price, show it as an option. Today such recipes are excluded as *needs pattern or other source*.
- **Green recipes when much cheaper** (2026-10-14, from ProfessionMaster): allow a green recipe in a reach path only when every orange and yellow option costs more than twice as much per point, labelled as uncertain.
- **Confirm skill-up colours from our own captures** (2026-10-14): the addon already records each recipe's difficulty in the profession window at the captured rank. Compare that with the catalog's colour ranks to confirm or contradict the Classic estimates on Forever, as evidence for the catalog (ProfessionMaster ships a Forever recipe table, but it's all rights reserved, so we gather our own).
- **Mail and auction expiry warnings** (2026-10-14, from TSM's task list): items or gold in a captured mailbox close to its 30-day expiry, and your auctions about to end.
- **Vendor the junk** (walkthrough 2026-10-13): Stock showed 20 of 43 held items with no price, mostly vendor trash. Suggest vendoring held items with a vendor price and no auction price, using captured vendor prices only.
- **Best use of a material:** for an item such as Linen or Wool Cloth, compare selling it with each craft it feeds, at current prices.
- **Value-add chart** (suggested 2026-10-04): in the recipe explanation, a tier-by-tier waterfall from raw materials through intermediates to the finished item. It shows cost added and the sale value at each tier where it's listed (an unlisted tier shows no value, never zero), so you can see where the margin is made. It draws from the existing `crafting.py` calculation, never a second costing path in SQL. Cross-profession chains wait for STORY-015b.

**Your own character's data** (approved 2026-10-06; capture is STORY-032/033 and the gold ledger STORY-034, all done). Once those exist:
- **Known recipes and skill:** moved to Next on 2026-10-07 as STORY-041 (capture) and STORY-043 (Today); 2026-10-09 added STORY-049 (Forever capture), STORY-051 (Characters) and STORY-052 (progression; *what can I learn next*). Still here: the Action Board filtered to what you can make.
- **Profession page** (added 2026-10-09, product owner): drill into one profession: every catalog recipe by skill band, with each character's status (known, train now, not yet), how it's learned, profit from the newest scan and its materials; linking to the item page (STORY-021). Builds on STORY-043, STORY-050 and STORY-052.
- **Calibrate removed listings:** your own sales from invoices show how many *removed* listings (STORY-027) were real sales.

**Ledger analytics** (from the 2026-10-06 design notes; each needs STORY-034 and some weeks of your own sales):
- **Sell-through and fill chance:** for each of your posts, its premium over the lowest price at posting, and whether and when it sold, and at which duration (to recommend STORY-035's post duration). Start with simple buckets (how often posts at 0–5%, 5–15% … above the lowest sold within their duration); more refined models only once there is enough data.
- **Gold per minute of auction time:** expected profit net of the auction cut and expected deposit losses, per minute you spend at the auction house. Replaces *Gold per hour* under *Today, later versions* if the scaled minimum gain feels wrong.
- **Cost basis:** lots per item (gathered, bought, crafted, vendor), first in first out. Two values per lot: what you paid (zero for gathered), for *what did I actually make?*; and what it would sell for now (depth-aware, after the cut, capped at any vendor price), for *craft it or sell it raw?*. Farming judged separately from trading, as gold per hour.
- **Capital view:** gold across all characters, holdings at market value, gold tied up in listings and mail, and net worth. A **reserve** you set (mount, training, spending) is kept back; Today's *Gold available* could then default to cash minus reserve instead of being typed in.
- **How well the plan worked:** planned against actual buy and sale prices, how often Today's rows were done, and realized margin per craft.

**Strategy ideas for the next grooming** (product owner, 2026-10-06; not scheduled; the session proposes, the product owner decides). The aim is to beat other gold makers on decisions, not speed: no sniping or undercut wars, and the addon stays read-only and manual. Several build on items above; say which data each needs and whether we will have it.
- **Crowding** and **Buy the overshoots:** moved to Next on 2026-10-13 as STORY-064.
- **Demand waves as the population levels:** leveling gear, bags and profession-leveling materials first, end-game consumables later. Show each wave from consistent scans instead of guessing from guides (*Market timing* above).
- **Spread across many markets:** prefer several modest, steady markets over one contested one, for example a cap on how much of one market's supply Today plans to add. Needs sales speed (STORY-027, then the ledger).
- **Average cost and procurement:** what each item in inventory cost on average, and buying below that average to drive it down. Decide whether *Cost basis* (FIFO lots, under *Ledger analytics*) also shows a weighted average, and combine it with *Market timing*'s cheapest-to-buy windows.
- **Your own postings:** each active auction with when it was posted, at what price against the lowest at the time, and what sold, when (day and hour) and how fast. The journal (STORY-033) records posts and invoices, and STORY-040 records the active auctions themselves (decided 2026-10-07).
- **Mail between your own characters:** the ledger (STORY-034) already counts postage in **mail out**; still to do: when a plan moves materials to the character with the right profession, include that postage. The amount is a beta check under *Now*.

**Deferred** (2026-10-06, from the same notes; revisit only with new evidence or a decision):
- **In-game plan list (`PlanData.lua`):** Brownstone would write a plan file into the addon folder for an in-game to-do tab that ticks itself off. Deferred: Today on a second screen covers it, and it would make Brownstone write into the game folder (`requirements.md` → *Product direction*). If revived, the file is written only by Brownstone and read by the addon on `/reload`; it could also carry an "imported through" marker so the addon never clears what Brownstone hasn't imported. **Still deferred (2026-10-14, product owner):** the out-of-game app is preferred. In-game profit tags and to-do lists, as in CraftProfit, ProfessionMaster and TSM, would also need files carried back from the Mac to the Windows PC, which only ever sends scans one way. Revisit only if switching screens gets in the way after launch.
- **Capital allocation by optimisation (linear programming):** Today's greedy funded plan is honest and affordable. Revisit with sales speed and fill chance.
- **Disenchanting outputs:** random results conflict with *Not modeled* (variable yields).
- **Price forecasting with machine learning:** too little history and too much change after launch.
- **Anomaly alerts** stay the last step of the *History chain*.

**AI narration** (suggested 2026-10-05; after STORY-025; reads ADDON-10 metrics): a plain-language summary of Today and the item page that explains only defined metrics and rule results, cites every number, and never invents one or recommends without explainable features (*Out of scope*). Needs a decision about which model runs it and what data leaves this machine.

**Addon follow-ups** (any time, none urgent):
- Scan the Roleplaying house once the beta offers it, and a neutral house when reachable, to confirm house identification and the 15% cut market.
- Check whether `/bscan start` works without the button click.

**Recipe coverage** (unblocked by STORY-004):
- **More recipes and professions:** generated with the recipes CLI and used together by the app (`status.md`); routing across professions is CRAFT-12.
- **Multi-yield costing:** if an in-game check shows a recipe makes more than 1, build whole crafts, round unit costs up to the copper, and show leftovers without crediting them. Keep the shopping list and the all-craft materials consistent. Until then the calculator can reject such intermediates with "Fractional unit costs" (`requirements.md` → *Not modeled*). **Moves to the top of Next if the Bolt of Linen Cloth check finds a yield above 1.**
- **Skill-up demand map:** now STORY-047 in Next (2026-10-08).
- **In-game recipe reader:** now part of *Known recipes and skill* under *Your own character's data* (reading your own character's data was approved 2026-10-06).

**Launch runbook** (moved from Next, product owner 2026-10-06): beta and live are separate markets (DATA-03), so launch needs no data migration or cutover rehearsal. Do both parts in the week before 4 November, when the steps are current.

**STORY-020a — Rehearse the launch-day in-game steps**

Split from STORY-020 at grooming (2026-10-05) so the part that needs the beta isn't blocked by STORY-016.

As a gold maker, I want the in-game half of the launch checklist rehearsed while the beta is still up, so that launch day has no surprises.

Acceptance:
- **A draft runbook** in `docs/`, linked from `status.md`, with the in-game steps: install or update the addon and check that it loads (the `.toc` interface number may change), first scan, `/reload`, import, clear.
- **Walked through once** while the beta is still up if convenient (by 21 October); no step timings needed.
- **Placeholders** for the steps STORY-020b completes.
- Depends on nothing; uses the current addon (0.3.1).

**STORY-020b — Finish the launch-day runbook**

The rest of STORY-020, split at grooming (2026-10-05). Finished one or two days before 4 November.

As a gold maker, I want a short, tested checklist for 4 November, so that the switch to the live game is quick and nothing is missed.

Acceptance:
- **Completes STORY-020a's runbook** with:
  - backing up before and after (STORY-016)
  - adding and enabling the live Roleplaying Alliance source in `config/market.local.toml`, with its own `source_id`, `environment = "live"`, the live game folder's `scan_path` and its `rules_version` (DATA-03)
  - re-saving each Forever Wowhead page and regenerating. If the live `rules_version` differs from the beta's, every Forever catalog stays inspection-only until regenerated (*Refresh due* flags it).
  - re-checking the confirmed and unconfirmed facts under *Product direction* in `requirements.md`
- **Checked** using archived scans and data copies: the backup, restore and source-cutover steps work end to end. Live-house checks happen at launch.
- Depends on STORY-016 (deferred; its backup steps wait for it) and STORY-020a.

**STORY-016 — Back up local data**

Deferred from Next by the product owner (2026-10-06).

As the product owner, I want a tested backup of `data/`, so that the beta scans, which can't be retaken after beta testing ends, survive a disk failure or a bad migration.

Acceptance:
- **Decide and record** in `requirements.md` where backups go (a location you control, such as a second disk) and when to take them, for example after each import session and before every migration or launch step.
- **One documented procedure** that refuses to run while a writer holds the DuckDB lock, copies `data/` to a dated folder, and verifies the copy: file count, and SHA-256 of every bronze file.
- **Restore tested once:** restored into a fresh folder, the app opens it and the Forever board matches the original.
- Bronze is the irreplaceable part. Derived data becomes rebuildable with STORY-006.

## Out of scope

- Buying, posting or any automated in-game action. The addon only reads.
- Unattended or scheduled in-game scanning.
- AI-generated recommendations without explainable features.
- Cloud deployment before replay, recovery and storage decisions.
