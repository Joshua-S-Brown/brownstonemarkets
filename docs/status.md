# Status

Current implementation, limitations and verification. Rules live in [requirements](requirements.md),
contracts in [design](design.md); history and dated beta reports live in Git.

## Implemented

- **Supply chains (STORY-086, STORY-092):** `/app/chains?source=&catalog=&recipe=` explores
  compatible outputs using Market's cached routes. Ranked chips open on the first makeable craft;
  the projection groups all valued Board recipes by team eligibility before the ten-chip cut.
  Name/ID search (only while searching, at most 50 hits) also includes intermediates.
  Buy/vendor/craft overrides use the shared engine; Add to tonight shares Today's tab choices
  and always uses its cheapest routes. Route, Per craft and Batch use shared panels: two columns
  from 1100 px, stacked below. Content-sized cards retain maker/status/held evidence; curved
  quantity edges distinguish chosen paths from unchosen branches, whose cards read *Not on the
  chosen route* with no toggle or units. Chips and wide graphs scroll
  horizontally. The labelled waterfall keeps quantities, costs, missing-price stops and losses
  in its rows. Offline verification: `test_supply_chain.py`, `test_chains_api.py`, Chains Vitest.
  Copied beta scan `20261017T104157Z-ff991e`: Copper Dagger opens at 601c/824c cost/profit;
  Linen Bag 144c/141c (Bolt bought: 195c/90c); ×5 uses 30 Linen Cloth + 15 Coarse Thread,
  720c spend, 705c profit. Sandpaper loses 5,748c. Desktop/mobile prototype comparisons and
  real-data evidence are ignored under `work/story-092/`.

- **Web foundation (STORY-081):** `/app` serves the React shell on plain FastAPI; source-scoped
  `/api/sources`, `/api/search` and `/api/items/{id}` adapt existing read-only projections.
  Routes reuse one explorer build per source until the database, config or hourly bucket
  changes: search under 10 ms, item record about 0.25 s. The build (3–9 s) starts in the
  background when the shell opens. Search shows the 50 closest hits.
  Search opens URL-backed item Overview records and scoped character records; Data opens
  the import sheet. Source evidence loads independently of the potentially slow local/drop
  scan inventory. Light/dark/system themes and bundled fonts work offline; narrow screens use bottom tabs.
  The launcher builds changed web sources, with a recoverable banner on failure or missing Node 24.
  `web/README.md` covers build/schema commands. Gates include the web checks on macOS; Windows
  reports an explicit skip. Market now lives in the web app (STORY-082).

- **Web Market:** `/app/market?source=` uses the shared PageHead, Panels and item badges.
  Three signal cards preview three identities each; more expands in UI-11/removal order, with
  current/typical money, signed percentage, stored history and early units. The grouped grid shows
  base/legacy first (otherwise the first separate identity), with other identities collapsed;
  no prices or supply are combined. Server projections own grouping, filters and sorting:
  absolute percentage gap descending, unknown last. Search reaches every snapshot item.
  Stored history now batches all browsed IDs, including noncatalog items; formerly those histories
  were omitted. Fewer than two priced points show no sparkline. Evidence retains all caveats.
  URL-backed records retain Overview, Price history, Listings, Made from and used in, Our activity;
  exact identity links keep `variant` beside `inspect`. History/ladders/routes retain base/legacy scope.
  Item-only reads remain lazy; a presence socket keeps browser fallback alive while React is connected.
  Legacy Market URLs redirect to the web page.
  Offline checks: `tests/test_market_presentation.py`, `tests/test_web_api.py`, history/flood/removal
  suites and Market/record Vitest tests. Copied Forever beta scan `20261017T104157Z-ff991e` has
  2,904 items / 6,284 identities; the default grid has 788 chain items / 1,248 identities.
  Linen Cloth has 31 stored points. Desktop/mobile comparisons and real-data evidence are ignored
  under `work/story-090/`; no collection or imports ran.

- **Item movements (UI-16):** Ledger's Items area shares name/ID/catalog filters with Restock,
  with filtered team units, character/day/category totals, own-mail links and residuals first.
  Lazy movements retain IDs, machine, allocation/reasons and version; gaps and snapshots are in evidence.
  Offline: `tests/test_item_ledger.py`, `tests/test_ledger_web.py`, Ledger Vitest.
  Copied beta scan `20261016T113727Z-eb77d0`: 1,007 movements, 46 baselines/gaps, 736 units in,
  596 out, 73/76 bags and 10/10 bank pairs without residuals; 11 own-mail rows, one unmatched send.
- **Gold ledger (UI-15, STORY-091):** `/app/ledger?source=` leads with Came in/Went out/Net/Held
  stock tiles, diverging daily bars beside counted, signed category rows, and a By character and day
  disclosure. Items and Restock are panels with tiles before tables; shared filters, targets,
  provenance and reconciliation remain. Days (7/30/all UTC, default 7) persist per tab/source.
  Offline: `tests/test_ledger.py`, `tests/test_ledger_web.py`, Ledger/Chart/Money Vitest.
  Copied beta `20261017T104157Z-ff991e`, All: 421 movements, nine days, 6,592c in / 4,324c out /
  2,268c net; 79/79 bags pairs reconcile. Category counts total 427: six payments each split into
  auction sale and deposit refund. Held stock 10,096c with 29 no-price items.
  Quests/flights remain other; current holdings are independent of the selected movement days.

- **App:** STORY-089 shares prototype component styles and page headings, short keyed character
  links, identity/confidence/signal pills, UTC times, panels, tiles and grid options. `/app/kit`
  previews unknown/zero/variant/error states; it is absent from navigation and search. The shell
  keeps a single-line top bar, icon theme menu and narrow bottom navigation. Search shows captured
  quality and compatible catalog roles, keeping variant keys in tooltips.
  Today, Team, Market and Ledger are web places; Data is a lazy sheet opened from
  the rail, status chip or `?sheet=data`. All legacy places redirect with source; Stock
  redirects to Ledger, Data to Today with the sheet. `brownstone_app.py` serves FastAPI/uvicorn with a pywebview window; `launch_app.py` reuses or restarts it through authenticated endpoints.
  `Open Brownstone App.command` / `.cmd` uses authenticated reuse/restart, native window or browser fallback.
- **Today:** funded whole-listing plan, choices/refill, shopping, sell/whole-silver undercuts,
  queue, confidence, character eligibility and captured funds; today_version 14.
  STORY-080 splits auction/vendor material purchases during batch sizing (requirements → Today),
  retaining holdings-first use, shared listing reservations and separate Buy/Queue lines.
  STORY-069 aligns headline profit with the reserved post quote (explicit cautious fallback),
  formats Today table money in g/s/c with copper sorting, and shows team gold-mail suggestions
  in Queue/copy/tick identity (rules in requirements → Today). This session combines equal tier
  requirements including their sources, compresses empty farming history and shares one farming caveat per page;
  hidden-recipe information leads with ordered plain reasons and retains provenance in Details.
  STORY-068 uses scoped Stock bags/bank holdings along the Board route, including intermediates,
  with held value in profit, purchase gold separate, shared reservation and held outputs.
  Held Queue actions name their allocated outputs and first craft stop; own bags annotate crafts,
  other bags mail, and bank withdrawals keep any onward mail in the bank stop (requirements → Today).
  Capture ages/unknown bank appear on Today; stale held counts add a reason without changing confidence.
  UI-11 high outputs use typical-price sell caps before ranking/sizing, with shared signal badges
  on crafts/Sell/posts; shown-output UI-10 history adds Low confidence for no early removals
  in at least three qualifying gaps (time-left bounds accepted for Forever 2026-10-16). This session
  composes reserved crafts and Team-window unlock costs with flood labels (UI-12)
  and measured journal farming rates and zone/NPC/position-cell farming spots (UI-13).
- **Your sales (STORY-073, UI-14):** journal-confirmed posts, deduplicated seller invoices and
  expired/cancelled attachments feed Today's Sell/card evidence and display-only expiry Low reason.
  Market item Summary lists per-character outcomes and scoped unidentified invoices; beta reports
  list every attempt, invoice match/reason, return and observed/gross/deposit/cut money evidence.
  `max_expiries` defaults to 3 with source overrides. Tests use sanitized beta record shapes in
  `tests/fixtures/sales`; run `pytest tests/test_sales.py` plus the required full gates below.
  The imported beta journal matches all seven expected identified invoices and all story item totals;
  18 attempts include 17 confirmed posts and one refused post. Sale-mail delay remains provisional;
  return prefixes currently require enUS.
- **Tier levels (STORY-079):** This session and hiring share validated trainer evidence from
  `config/tier_levels.toml`; missing Forever tiers carry the UI-12 Classic fallback label.
  Beta reports list captured Apprentice/Journeyman/Expert/Artisan services with level, skill,
  copper cost and provenance for review. Offline checks cover zero/positive/unknown levels,
  Classic scope, source-aware merging, hiring, malformed tables and report output.
- **Today web (STORY-083/088):** `/app/today` pairs compact Route stops with Opportunities
  (stacked below 1100px), plus a Level up tab. Adjacent character/place stops merge; item links,
  confidence tips and line evidence keep the complete Queue readable. Opportunities adds five
  unplanned Board rows with reasons/history and a lazy best Level up lever that focuses its card.
  Level up shows one card per levelling step; tiers, extra recipes and missing prices expand on
  each card, a no-step list keeps reasons, and farming follows. Reset notices require dropped
  saved choices/ticks; refused batches explain the maximum that fits.
  The complete Queue supplies stop lines, copy/totals and tick identity; choices and ticks persist
  per tab/source in sessionStorage. Item Overview's Our move shares the Today query and adjusts
  crafts/refill, including crafts excluded earlier in the session. Settings save through the token boundary to the existing source file.
  Native Today URLs and Team return links redirect to the web page; the old Today renderer is retired.
  Offline coverage moved to `test_today_web*.py`, `test_today_session_words.py` and Today Vitest tests.
  On copied beta data, scan `20261016T113727Z-eb77d0`: 13 Queue lines match NiceGUI verbatim,
  including quantities, gold mail, deposits and copy text. Shopping 1,825c, deposits 411c,
  expected profit 2,583c, captured team funds 1,939c. All five characters' This session options match.
- **Team (STORY-091):** `/app/team?source=` shows avatar cards with rank/tier bars and one best
  action, other steps/reasons in Tips and records, a profession coverage matrix and hiring/holder
  tables with estimate pills. The release-only look-ahead sits in the roster header and persists
  per tab/source; caveats live in the evidence footer. CharacterName links open full-key records.
  `team_view` owns shared shaping; `/api/team` caches one board per source/window until database,
  configuration or hour changes. Hire tier details load on demand. Holdings retain exact variants.
  Rules: [CRAFT-11/13](requirements.md#crafting), [Team character cards](requirements.md#team-character-cards).
  Offline: Team/CharacterRecord Vitest, `test_team_web.py`, progression/hiring/session-options suites.
  Copied beta `20261017T104157Z-ff991e`, window 25: eight characters, three learning actions;
  Arille Blacksmithing 31/75, Mining 48/75, Cooking 2/75, Fishing 3/75; Basilly Tailoring 32/75.
  Arille's best action is Cloudy Skyforged Chain, +19 points, 9,050c per craft. Nine hire rows,
  all estimates incomplete; Fishing/Herbalism/Skinning retain no-catalog Tips. Comparisons retain
  CRAFT-11's reachable window; only new-hire profits are at 300 (CRAFT-13).
  1280/390 px Team/Ledger comparisons with the prototype are in ignored `work/story-091/`.
  No collection/import ran. Training, gathering income, demand and tier-fee limits remain labelled.

- **Inspector records (STORY-093):** prototype-width item/character panels use three persistent facts,
  scrolling tabs, UTC times and evidence footers. Item Overview pairs stored prices/typical with supply
  bars, vendor/deposit/holdings facts and best-use/farming panels. Character records show profession
  bars, projected known-recipe totals, four-column reachable recipes, location-first holdings and
  distinct history series with All readings. Offline: ItemDetails/ItemCharts/CharacterRecord Vitest,
  character projection and web API tests. Copied Forever beta `20261017T104157Z-ff991e` matches
  STORY-093's Linen Cloth and Arille figures; comparisons at 1280/390 px are in ignored
  `work/story-093/`. No collection/import ran; unknown bank remains a lower bound.

- **Market:** scoped name/ID search, separate variants, catalog chains/bands/team eligibility,
  movement, consecutive-scan removals and flood signals (UI-02/06/09/10/11).
  Item pages lead with a base-item decision summary, scoped holdings and own item farming evidence;
  Web record tabs and the evidence footer retain details. Three removal gaps lead,
  the remainder expand, skipped gaps are counted; market-wide lists stay on home (STORY-078, UI-09).
  UI-11 typical prices use equal-weight UTC daily medians, with days/scans evidence and
  `flood_min_days` history validation (STORY-072; rules in requirements → UI-11).
- **Stock:** Ledger's Restock retains readable bags/bank captures, exact variants, cautious
  listed values and whole-stack estimates. Target drafts save atomically through `/api/ledger/targets`;
  damaged files remain unchanged with a 422 explanation. Today is unaffected. Copied beta: 10 capture
  chips, 37 items held, 4,363c listed value excluding 19 no-price items. A copied Linen Cloth target
  of 200 at 30c/unit matches NiceGUI: held 11, short at most 189, buy 189, whole stacks 206, cost 4,120c.
- **Data/CLI:** Data's sheet uses `import_review`; GET reads saved evidence, POST review explicitly
  reads game/drop files. A server-held source/config-bound opaque review is consumed before import;
  a non-blocking process writer lock returns 409 for a concurrent import. Selection shaping uses cached
  bytes; source switches discard reviews on both sides. Successful imports invalidate all source queries.
  Imported evidence loads on demand; CLI refresh remains for non-addon sources. Offline coverage:
  `tests/test_data_web.py`, Data Vitest and existing scan/import tests. Copied real-drop subset matches CLI:
  72,338 listings, 8,097 prices, two character snapshots and five journal records, equal manifest evidence
  and stored rows apart from collection identity/time. Real-source preview is read-only; current drops
  are duplicates. Native Stock/Data views and rule tests moved to API/Vitest after beta comparison.
  TSM/recipe refresh remains CLI-only; watchlist engine/local files and Today/Import hits remain.
- **Storage:** schema 11, metrics version 1, backed-up idempotent migrations. Sources retain
  full market/environment identity and never mix implicitly (DATA-03/08).
- **Catalogs:** twelve generated catalogs; nine Forever professions (1,930 recipes) and Classic
  Alchemy/Enchanting/Tailoring. Board policy 0.3, team-aware graph routes (CRAFT-12), learning
  evidence and training costs. Generation is offline from manually saved pages (CRAFT-08).
- **Sources:** local overrides enable `forever-us-normal-alliance-addon` beta; tracked config
  keeps it disabled. Mankrik Alliance is development data; Retail is regression-only.
- **Addon:** 0.12.8 (0.12.7 stopped re-saving vendor lists when only the player moves; 0.12.8 waits 120 s for the
  server and keeps failed scan starts in `scan_timing`; install before the next play), account format 6/scan format 4. Usage, capture fields and remaining game
  checks live in [addon README](../addon/README.md). App retirement does not alter addon/data.

## Limitations

- Thirty-one complete Normal Alliance scans (4–17 October) and one stopped scan are imported; no RP/neutral scans.
  Bulk API supplies no sellers (ADDON-07), blocking seller analysis.
- Catalog yields/availability still need game evidence; no multi-yield support.
  Bolt of Linen Cloth's yield of 1 was confirmed on 2026-10-15 (17 crafts, 34 Linen Cloth).
  The 39 marked vendor items and eight new unlimited items are confirmed against that day's
  25 vendor lists; bundle unit prices are corrected (CRAFT-08). Limited-stock items remain
  unmarked. Recipe profits and Today's posts respect vendor ceilings (CRAFT-04).
  Runecloth Bag/dye post-launch flags need review; both dyes appear on beta listings.
- Hiring cost walks complete only for Tailoring, Alchemy and Blacksmithing. Other catalogs lack
  starter learning evidence or put Smelt Copper at skill 25; gaps remain unknown.
- Farming requires loot-source context (addon 0.11.3+); older unmatched messages supply no rate.
  Short stretches remain excluded evidence; measured beta rates do not promise launch respawns.
  Valuation uses Today's loaded prices, preferring newest-scan vendor sell values over loot-time fallback
  and reporting disagreements. Addon 0.12.4 captures raw positions and slot types/quantities; 0.12.5 adds cached
  vendor values (0.12.4 called a `GetItemInfo` global the Forever client lacks, saving none); UI-13 adds median position cells and explicit-slot coin valuation. Older captures
  keep zone/NPC-only spots and unavailable coin. Positions and coin were confirmed on the beta on 2026-10-14
  (all 15 coin loots matched), and 0.12.5 loot-time vendor values on 2026-10-14 (grey items the scans don't price). Coin without a nearby matching money delta stays unavailable.
  Addon 0.12.6 captures matching targeted mob names; UI-13 displays the newest scoped name beside
  its NPC ID in spots and evidence, with NPC-only fallback. The beta report counts named windows
  and lists unnamed NPC IDs. Confirmed on the beta on 2026-10-15 (7 of 29 windows named, no NPC ID unnamed).
  Other unpriced gathered items are counted and excluded; spot evidence includes all item values.
- Listings are not sales/demand/forecasts. Removed-listing time-left bounds match Forever
  (12 hours accepted 2026-10-16). Tier requirements without trainer evidence use the labelled UI-12
  fallback; crafting tiers and yellow skill-up chances remain unconfirmed. Deposits (13 posts) and postage
  are measured (requirements → Product direction). Today models deposits under requirements → Today (v11): Sell and Queue show
  refundable posting gold and expiry loss at the saved 2/8/24-hour duration, including held outputs;
  deposits do not reserve funds or reduce ranked profit. Neutral/missing evidence stays unknown.
  Postage in plans and sale speed remain backlog work.
  A gold-only mail recorded the previous draft's items and no gold, so the ledger (STORY-034) uses money
  changes. Each profession window event saves the full recipe list: 25 MB of the 29.6 MB 2026-10-15 file.
- Today fixes aggregate routes before whole-stack sizing; surplus uncredited/unshared, greedy plan
  affordable but no global optimum. Rows using a held item compare every feasible size up to the 1,000-craft cap;
  large caps cost those rows more calculation time than the breakpoint search other rows keep. Cross-profession routes need scoped Known/Train now evidence.
- TSM lacks listing depth; Mankrik lacks upstream time (age is since collection) and historical
  discount prices. Legacy TSM rows have no source hash or retrospective deduplication.
- Bronze/silver/DB/gold are not jointly atomic; failed post-commit runs need preserved evidence
  for recovery; replay is pending. Run one writer. Synced drops can change during read: retry.
- App reads on load: reload after imports elsewhere. Native clipboard/appearance and phone-width
  behavior still need manual checks. Vendor lists, trainer lists, mob names and the panel
  were confirmed on 2026-10-15. A scan 46 minutes after the last answered one got no reply within 30 s and
  was wrongly blamed on the hourly limit (2026-10-15, not saved; 0.12.8 records the next one). Remaining in-game checks (addon README → *Last beta play session*):
  the sale-to-mailbox delay, crafting tier levels and yellow skill-up chances.
  On 2026-10-15 own posts read bucket 2 at 1 h 35 m left, 1 at 26 and 29 min, 3 at 7 h 35 m and 4 at
  21 h 40 m; two 24-hour posts read 4 at 15 h 19 m (scan `20261015T191236Z-8f626c`) and 3 at 8 h 52 m
  (`20261016T013929Z-6005ec`), so the 3/4 transition lies between; accepted as 12 hours on 2026-10-16. Expired 2- and 24-hour posts were mailed back within 6 s of expiry. Seller invoices (`GetInboxInvoiceInfo`
  4 price, 6 deposit, 7 cut, 11 count) paid price + deposit − ⌊5%⌋ on all four sales; expiries returned
  the items without the deposit. A sale mail's days left dates its arrival (09:07 UTC 2026-10-16, opened 2 h 31 m later), but that sale fell between scans 7 h 28 m apart, so the sale-to-mailbox delay stays unknown. Item pass measured
  2026-10-13: 5.9 s listing read, 0.34 s pass, 1,590 of 1,909 requests answered, none timed out.

## Verify

```bash
.venv/bin/python -m brownstone gates
git diff --check
```

`gates` runs ruff, mypy, `pytest -n auto --cov` (pytest-xdist), then `npm run check` in web/ on macOS;
it stops at the first failure and prints
tests, coverage, time and the bytes left under the document size guards. Opt-in pre-commit hook (ruff and
mypy only): `git config core.hooksPath tools/git-hooks`.

Expected: 1,963 Python tests pass (one platform skip), plus 103 Vitest tests.
Tests are offline; coverage must meet the 88% branch-inclusive floor. CI runs macOS/Windows
from requirements.lock.txt; PowerShell harness skips explicitly when unavailable on macOS.
Windows uses `.venv\Scripts\python.exe`. App/launcher/CLI retirement checks live in
`tests/test_retirement.py`; legacy redirect tests in `tests/ui_trial/`.

### App

Install the lock file and open `Open Brownstone App.command` / `.cmd`.
For real-data verification, copy data/ under ignored work/ and run:

```bash
.venv/bin/python launch_app.py --data-dir /path/to/copied-data
```

Select Forever beta; open Today, Team, Market (Linen Cloth 2589 and Bolt 2996), Ledger and the Data sheet.
On Today → This session, inspect each character's Farming summary and expand Farming evidence
for all rates, object IDs and excluded stretches. Inspect stale/unknown labels, holdings and source
evidence; preview never writes. A browser check
uses `brownstone_app.py --data-dir /path/to/copied-data --port 8081`.

### After a play session

Once the drop has arrived, one command imports new drops through the normal import, runs the beta
report on each machine's latest drop (and the local file) that changed, and prints only what is new,
resolved or failing since the previous run, then eligible scans and the pending in-game checks from
the addon README:

```bash
.venv/bin/python -m brownstone after-play
```

The previous run's state is `work/after-play/state.json`; delete it to see everything again. Exit 1
means a failed check or import. Reports land in `work/beta-reports` as below.

### Beta report

For one file, after logout/reload finishes writing:

```bash
.venv/bin/python -m brownstone beta-report "/path/to/BrownstoneScan.lua" --source forever-us-normal-alliance-addon
```

Optional --previous compares earlier bytes. Outputs private work/beta-reports report.md/json;
0 permits warnings, 1 failed check, 2 unreadable input. Keep raw files private (ADDON-07).
Isolated roundtrip never imports into real data or authorizes clear; inferred load boundaries,
latest-only diagnostics and approximate serialized sizes limit reconciliation.
