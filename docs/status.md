# Status

Current implementation, limitations and verification. Rules live in [requirements](requirements.md),
contracts in [design](design.md); history and dated beta reports live in Git.

## Implemented

- **Web foundation (STORY-081):** `/app` serves the React shell beside NiceGUI; source-scoped
  `/api/sources`, `/api/search` and `/api/items/{id}` adapt existing read-only projections.
  Routes reuse one explorer build per source until the database, config or hourly bucket
  changes: search under 10 ms, item record about 0.25 s. The build (3–9 s) starts in the
  background when the shell opens. Search shows the 50 closest hits.
  Search opens URL-backed item Overview records and placeholder character records; Data links
  to the existing review page. Source evidence loads independently of the potentially slow local/drop
  scan inventory. Light/dark/system themes and bundled fonts work offline; narrow screens use bottom tabs.
  The launcher builds changed web sources, with a recoverable banner on failure or missing Node 24.
  `web/README.md` covers build/schema commands. Gates include the web checks on macOS; Windows
  reports an explicit skip. No NiceGUI page has been removed.

- **Item charts (STORY-021):** item Market tab adds stored price/supply history and an
  eligible-scan listing ladder with cumulative-unit steps, sortable prices and separate no-buyout
  counts. Rules: [UI-17](requirements.md#ui-17-item-price-history-and-listing-ladder-story-021);
  contracts: design → Item charts. Offline tests: `tests/test_item_history.py` and
  `tests/ui_trial/test_nicegui_item_history.py`. Forever beta currently has 28 points each for
  Linen Cloth and Bolt of Linen Cloth; newest ladders match 333/7,416/25 and 175/3,080/17
  listings/units/price levels respectively, with no no-buyout listings. Desktop (1280 px) and
  narrow (390 px) Market tabs checked against copied data; charts fit without page overflow.
  The ladder opens zoomed to the cheapest 95% of units, so outlier asks don't flatten it; the
  slider and table still reach every level.

- **Item movements (STORY-034b):** Stock's Items area below Gold shows cached category totals,
  own-character mail, snapshot residuals and expandable entry provenance, using Stock's search.
  Rules: [UI-16](requirements.md#ui-16-item-movements-story-034b); contracts: design → Item ledger.
  Offline tests: `tests/test_item_ledger.py`, `tests/ui_trial/test_nicegui_stock.py`.
  Imported Forever beta: 1,006 movements, 44 baselines/gaps (including bags still loading just
  after a login), three unreadable captures excluded; team 731 units in, 596 out. 67/70 bags and
  10/10 bank pairs have zero residual. The three left: Cicelyna's +4 item 117/+1 item 6948 behind
  an old-addon baseline, and Basilly's −13 and −10 Conjured Water (5350), which vanishes at logout
  with no event. Ten own-mail pairs match; one Linen Bag send stays unmatched because its bag
  update came 20 s after the take. 229 other allocations, no unidentified mail.

- **Gold ledger (STORY-034):** Stock shows scoped per-character/UTC-day category in/out,
  explicit team totals, readable-bags reconciliation and expandable movement provenance.
  Rules: [UI-15](requirements.md#ui-15-gold-ledger-story-034); contracts: design → Gold ledger.
  Offline tests: `tests/test_ledger.py`, `tests/ui_trial/test_nicegui_stock.py`.
  Imported Forever beta: 384 movements, no missing money baselines or unidentified mail;
  seven seller invoices allocate 999c proceeds and 910c refunds; plain mail is 1c/200c/400c.
  All 70 readable snapshot pairs reconcile to zero; three unreadable bags captures are excluded.
  The story's expected initial Basilly 52c pair starts at a zero-slot backpack capture on
  October 8, so ADDON-11/UI-15 excludes it; first readable capture is October 9 at 52c.
  Quests/flights remain other; timing attribution is evidence, not proof of hook success.

- **App:** NiceGUI Today, Team, Market, Stock and Data → Import, with shared light theme,
  URL-only back links for Today item/Team links and Market item chains (STORY-076, UI-07);
  Today tab/view refresh persistence with This session loaded on URL entry,
  wrapping navigation, page information and Save-only Today settings (UI-07/08).
  `Open Brownstone App.command` / `.cmd` calls `launch_nicegui.py`; native window with
  authenticated reuse/restart, loopback browser fallback and idle shutdown.
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
  with held value in profit, purchase gold separate, shared reservation, take/mail lines and held outputs.
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
- **Team:** captured roster/history, recipe evidence, reach estimates and hiring comparison
  (CRAFT-11/13). One board shared across characters/hiring; detail loads on demand.
  STORY-070 chooses a profitable learnable next recipe before other sources and shows the other
  route as an alternative tile ([CRAFT-11](requirements.md#crafting)); the best flows into
  This session; reachable order and Today plans stay unchanged. Source labels, skill-ID-based
  empty states, training payback and consolidated incomplete hire costs follow
  [Team character-card rules](requirements.md#team-character-cards).
  Team and hire cost steps and Team profit columns display money with copper sorting. Offline checks are in
  `test_progression.py`, `test_session_options.py` and the Team/hiring NiceGUI tests;
  `fixtures/today_story070.json` preserves the full Today regression fixture; only its version fields track Today changes.
  On the imported Forever beta scan `20261015T124940Z-2ef70d`, Arille's Cooking best stays
  Tasty Raptor Bites (drop, 194c) with *Or learn now* Spiced Wolf Meat (trainer, −45c); Basilly's
  Tailoring best is Blue Linen Vest (vendor, 479c) with *Pattern worth hunting* Red Linen Robe
  (unverified codes 16/21, 894c). Training costs are unknown. Arille's Fishing and Keenagen's
  Mining show gathering sentences; all nine hire estimates to 300 are incomplete. Checked through
  the native NiceGUI test user against a copy of `data/`; no new evidence imported.
- **Market:** scoped name/ID search, separate variants, catalog chains/bands/team eligibility,
  movement, consecutive-scan removals and flood signals (UI-02/06/09/10/11).
  Item pages lead with a base-item decision summary, scoped holdings and own item farming evidence;
  Summary/Crafting/Market/Identity and evidence tabs retain details. Three removal gaps lead,
  the remainder expand, skipped gaps are counted; market-wide lists stay on home (STORY-078, UI-09).
  UI-11 typical prices use equal-weight UTC daily medians, with days/scans evidence and
  `flood_min_days` history validation (STORY-072; rules in requirements → UI-11).
- **Stock:** readable bags/bank holdings, cautious listed value, Save-only source-local team
  targets and whole-stack buy/wait/unlisted estimates (Stock rules). Unknown bank is explicit.
- **Data/CLI:** TSM ingestion and addon formats 1–4 within account format 6, snapshots/journal,
  bounded read-only preview, reviewed import, exact gzip archive and per-file drops.
  CLI supports collect/import, --preview/--input/--scan, recipes, beta-report, after-play, rules and close-story
  (prints named backlog stories and requirements/design sections; AGENTS.md).
  TSM and recipe refresh use the CLI. Watchlist engine/local files and Today/Import hits remain.
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

- Twenty-five complete Normal Alliance scans and one stopped scan are imported; no RP/neutral scans.
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

Tests are offline; coverage must meet the 88% branch-inclusive floor. CI runs macOS/Windows
from requirements.lock.txt; PowerShell harness skips explicitly when unavailable on macOS.
Windows uses `.venv\Scripts\python.exe`. App/launcher/CLI retirement checks live in
`tests/test_retirement.py`; NiceGUI place/import tests in `tests/ui_trial/`.

### App

Install the lock file and open `Open Brownstone App.command` / `.cmd`.
For real-data verification, copy data/ under ignored work/ and run:

```bash
.venv/bin/python launch_nicegui.py --data-dir /path/to/copied-data
```

Select Forever beta; open Today, Team, Market (Linen Cloth 2589 and Bolt 2996), Stock and Data.
On Today → This session, inspect each character's Farming summary and expand Farming evidence
for all rates, object IDs and excluded stretches. Inspect stale/unknown labels, holdings and source
evidence; preview never writes. A browser check
uses `nicegui_app.py --data-dir /path/to/copied-data --port 8081`.

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
