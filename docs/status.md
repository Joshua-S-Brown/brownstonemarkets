# Status

Current implementation, limitations and verification. Rules live in [requirements](requirements.md),
contracts in [design](design.md); history and dated beta reports live in Git.

## Implemented

- **App:** NiceGUI Today, Team, Market, Stock and Data → Import, with shared light theme,
  URL-only back links for Today item/Team links and Market item chains (STORY-076, UI-07);
  Today tab/view refresh persistence with This session loaded on URL entry,
  wrapping navigation, page information and Save-only Today settings (UI-07/08).
  `Open Brownstone App.command` / `.cmd` calls `launch_nicegui.py`; native window with
  authenticated reuse/restart, loopback browser fallback and idle shutdown.
- **Today:** funded whole-listing plan, choices/refill, shopping, sell/whole-silver undercuts,
  queue, confidence, character eligibility and captured funds; today_version 10.
  STORY-068 uses scoped Stock bags/bank holdings along the Board route, including intermediates,
  with held value in profit, purchase gold separate, shared reservation, take/mail lines and held outputs.
  Capture ages/unknown bank appear on Today; stale held counts add a reason without changing confidence.
  UI-11 high outputs use typical-price sell caps before ranking/sizing, with shared signal badges
  on crafts/Sell/posts; shown-output UI-10 history adds Low confidence for no early removals
  in at least three qualifying gaps (Classic time-left assumptions pending Forever confirmation). This session
  composes reserved crafts and Team-window unlock costs with flood labels (UI-12)
  and measured journal farming rates and zone/NPC/position-cell farming spots (UI-13).
- **Team:** captured roster/history, recipe evidence, reach estimates and hiring comparison
  (CRAFT-11/13). One board shared across characters/hiring; detail loads on demand.
- **Market:** scoped name/ID search, separate variants, catalog chains/bands/team eligibility,
  movement, consecutive-scan removals and flood signals (UI-02/06/09/10/11).
  UI-11 typical prices use equal-weight UTC daily medians, with days/scans evidence and
  `flood_min_days` history validation (STORY-072; rules in requirements → UI-11).
- **Stock:** readable bags/bank holdings, cautious listed value, Save-only source-local team
  targets and whole-stack buy/wait/unlisted estimates (Stock rules). Unknown bank is explicit.
- **Data/CLI:** TSM ingestion and addon formats 1–4 within account format 6, snapshots/journal,
  bounded read-only preview, reviewed import, exact gzip archive and per-file drops.
  CLI supports collect/import, --preview/--input/--scan, recipes and beta-report.
  TSM and recipe refresh use the CLI. Watchlist engine/local files and Today/Import hits remain.
- **Storage:** schema 11, metrics version 1, backed-up idempotent migrations. Sources retain
  full market/environment identity and never mix implicitly (DATA-03/08).
- **Catalogs:** twelve generated catalogs; nine Forever professions (1,930 recipes) and Classic
  Alchemy/Enchanting/Tailoring. Board policy 0.3, team-aware graph routes (CRAFT-12), learning
  evidence and training costs. Generation is offline from manually saved pages (CRAFT-08).
- **Sources:** local overrides enable `forever-us-normal-alliance-addon` beta; tracked config
  keeps it disabled. Mankrik Alliance is development data; Retail is regression-only.
- **Addon:** 0.12.6, account format 6/scan format 4. Usage, capture fields and remaining game
  checks live in [addon README](../addon/README.md). App retirement does not alter addon/data.

## Limitations

- Twenty-three complete Normal Alliance scans and one stopped scan are imported; no RP/neutral scans.
  Bulk API supplies no sellers (ADDON-07), blocking seller analysis.
- Catalog yields/vendor marks/availability still need game evidence; no multi-yield support.
  Vendor prices remain unconfirmed except Coarse Thread. Runecloth Bag/dye post-launch flags
  need review; both dyes appear on beta listings.
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
  and lists unnamed NPC IDs. This new capture still needs an in-game check.
  Other unpriced gathered items are counted and excluded; spot evidence includes all item values.
- Listings are not sales/demand/forecasts. Removed-listing time-left bounds are Classic assumptions,
  pending Forever confirmation. Tier levels 10/20/35 and yellow skill-up chances are unconfirmed.
  Deposits, sale speed, postage, ledger and suggested stock targets remain backlog work.
- Today fixes aggregate routes before whole-stack sizing; surplus uncredited/unshared, greedy plan
  affordable but no global optimum. Rows using a held item compare every feasible size up to the 1,000-craft cap;
  large caps cost those rows more calculation time than the breakpoint search other rows keep. Cross-profession routes need scoped Known/Train now evidence.
- TSM lacks listing depth; Mankrik lacks upstream time (age is since collection) and historical
  discount prices. Legacy TSM rows have no source hash or retrospective deduplication.
- Bronze/silver/DB/gold are not jointly atomic; failed post-commit runs need preserved evidence
  for recovery; replay is pending. Run one writer. Synced drops can change during read: retry.
- App reads on load: reload after imports elsewhere. Native clipboard/appearance and phone-width
  behavior still need manual checks. Remaining in-game checks (addon README → *Last beta play
  session*): vendor lists (0.12.3 captures prices/stock/standing on opening; existing beta data
  has no lists yet; STORY-071 report section is empty until a vendor is opened), trainer tier levels
  (0.12.2 reads the list after it loads; 0.11.3 saved empty lists),
  removed-listing time-left bounds, yellow skill-up chances and the panel. Item pass measured
  2026-10-13: 5.9 s listing read, 0.34 s pass, 1,590 of 1,909 requests answered, none timed out.

## Verify

```bash
.venv/bin/python -m pytest --cov
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy
git diff --check
```

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

### Beta report

After logout/reload finishes writing:

```bash
.venv/bin/python -m brownstone beta-report "/path/to/BrownstoneScan.lua" --source forever-us-normal-alliance-addon
```

Optional --previous compares earlier bytes. Outputs private work/beta-reports report.md/json;
0 permits warnings, 1 failed check, 2 unreadable input. Keep raw files private (ADDON-07).
Isolated roundtrip never imports into real data or authorizes clear; inferred load boundaries,
latest-only diagnostics and approximate serialized sizes limit reconciliation.
