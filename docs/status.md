# Status

Current implementation, limitations and verification. Rules live in [requirements](requirements.md),
contracts in [design](design.md); history, story outcomes and dated beta evidence live in Git.

## Implemented

- **Profession advice (STORY-117):** Team's *Take up* fills gaps: the character's own plan, then professions no captured character holds or plans, a different top pick per card in roster order (*suggested for X* after), and *every priced profession is held, planned or suggested* once none remain; gathering options are labelled, never ranked. Rules: *Team character cards*. Copied beta: Lira, Star and Baspion get Leatherworking, Engineering and Alchemy; the rest say every profession is covered.

- **App:** one web app (UI-07, UI-18). `brownstone_app.py` serves FastAPI/uvicorn on loopback with a
  pywebview window or browser fallback; `launch_app.py` reuses or restarts it through authenticated
  endpoints; `Open Brownstone App.command` / `.cmd` call the launcher, which rebuilds changed web
  sources and shows a recoverable banner on build failure or missing Node 24. `/app` serves the React
  shell: Today, Team, Market, Supply chains and Ledger are places, Data is a lazy sheet
  (rail, status chip or `?sheet=data`) and `/app/kit` previews component states outside navigation.
  `/` opens Today. Search (50 closest hits) opens
  URL-backed item, character and profession records; themes and fonts work offline; narrow screens
  use bottom tabs. Each place's API caches one projection per source until the database, config or
  UTC hour changes; a presence socket keeps the browser fallback alive while a tab is connected.
- **Today** (`today_version` 15; rules in requirements → Today): funded whole-listing plan with
  choices/refill, shopping split between auction and vendor, holdings used first along the Board route
  (including intermediates, own-bag/mail/bank stops), Sell with whole-silver undercuts, vendor floor,
  deposits and expiry loss at the saved post duration, Queue with gold-mail suggestions and tick
  identity, confidence, character eligibility, captured funds less the per-source gold reserve, and
  UI-10/11/12/13 signals and farming spots. The web page pairs Route stops with Opportunities plus a
  Level up tab (one card per levelling step, best lever, farming); choices and ticks persist per
  tab/source in sessionStorage and reset only when saved choices are dropped. Settings save through
  the token boundary. Item Overview's *Our move* reuses the Today query.
- **Team** (rules: CRAFT-11/13, requirements → Team character cards): Capital (recorded gold, cautious
  holdings, *at least* total), avatar cards with rank/tier bars and one best action, a profession
  coverage matrix, hiring tables with estimate pills and free-slot suggestions, and an optional
  planned roster from `config/team.local.toml`. Reach costs use captured team stock first, walking
  each window with and without holdings and keeping the further, then cheaper walk. Character
  records show numbered Route stops, profession choices, seven UTC days of ledger totals and
  location-first holdings with exact-identity actions; profession records list one row per catalog
  recipe with a column per holder.
- **Market** (UI-02/06/09/10/11/19): opens on *For our levels* with signal cards, a grouped grid
  (base/legacy first, other identities collapsed, never pooled) and server-side filters/sorting.
  Item records keep Overview, Price history, Listings, Made from and used in (per-unit
  sell/vendor/craft comparison), and Our activity, with removals per comparable gap, removal speed,
  typical prices from equal-weight UTC daily medians and stored history.
- **Supply chains** (CRAFT-12): `/app/chains?source=&catalog=&recipe=` explores compatible outputs
  from Market's cached routes with buy/vendor/craft overrides, Route/Per craft/Batch panels, chosen
  paths first and a labelled cost waterfall; *Add to tonight* shares Today's tab choices.
- **Ledger** (UI-15/16/19): `/app/ledger?source=` shows Came in/Went out/Net/Held stock, daily bars,
  signed categories and a By character and day disclosure over 7/30/all UTC days; Items lists
  movements with residuals first; Restock keeps captures, exact variants, cautious values,
  whole-stack estimates, display-only suggestions and atomically saved targets (`/api/ledger/targets`;
  a damaged file stays unchanged with a 422).
- **Your sales** (UI-14): journal-confirmed posts, deduplicated seller invoices and returned
  attachments feed Today's Sell evidence, a display-only expiry Low reason (`max_expiries`, default 3)
  and Market's Our activity.
- **Data/CLI:** Data's sheet uses `import_review`: GET reads saved evidence, POST reviews game/drop
  files; a source/config-bound opaque review is consumed by import and a process writer lock returns
  409 to a concurrent import. TSM, recipe and other non-addon refreshes stay CLI-only.
- **Storage and sources:** schema 11, metrics version 1, backed-up idempotent migrations. Sources keep
  full market/environment identity and never mix implicitly (DATA-03/08). Local overrides enable the
  `forever-us-normal-alliance-addon` beta; tracked config keeps it disabled. Mankrik Alliance is
  development data; Retail is regression-only.
- **Catalogs:** twelve generated catalogs: nine Forever professions (1,930 recipes) and Classic
  Alchemy/Enchanting/Tailoring. Board policy 0.3, team-aware routes, learning evidence, training costs
  and validated trainer tier levels (`config/tier_levels.toml`, labelled Classic fallback otherwise).
  Generation is offline from saved pages (CRAFT-08). `python -m brownstone skillups --source <id>`
  reports captured colours against the catalog; `--write` records derived picks (CRAFT-10).
- **Replay:** `python -m brownstone rebuild --output work/rebuilt-data` replays every configured
  source's bronze manifests (`.lua` and `.lua.gz`) into fresh silver and DuckDB with recorded times,
  identities, hashes and selections. Invalid collections are listed and rolled back (exit 1); no
  downloads or bronze writes occur; results are deterministic.
- **Addon:** 0.12.8, account format 6 / scan format 4. Usage, capture fields and pending game checks
  live in the [addon README](../addon/README.md).

## Limitations

- Beta evidence: 31 complete Normal Alliance scans (4–17 October) and one stopped scan; no RP or
  neutral scans. Live starts fresh (requirements → Product direction). The bulk API supplies no
  sellers (ADDON-07), blocking seller analysis.
- Catalog yields and availability need game evidence; no multi-yield support. Limited-stock vendor
  items stay unmarked; Runecloth Bag and dye post-launch flags need review.
- Hiring cost walks complete only for Tailoring, Alchemy and Blacksmithing; other catalogs lack starter
  learning evidence or put Smelt Copper at skill 25, so their gaps stay unknown.
- Farming needs loot-source context (addon 0.11.3+); older captures keep zone/NPC-only spots and
  unavailable coin. Measured beta rates do not promise launch respawns.
- Listings are not sales, demand or forecasts. Crafting tier levels, yellow skill-up chances and the
  sale-to-mailbox delay are unconfirmed. Postage in plans is backlog work.
- Today fixes aggregate routes before whole-stack sizing; surplus is uncredited and unshared, and the
  greedy plan is affordable but not a global optimum. Rows using a held item compare every size up to
  the 1,000-craft cap, which costs them more time than the breakpoint search.
- TSM lacks listing depth; Mankrik lacks upstream time (age is since collection) and historical
  discount prices. Legacy TSM rows have no source hash or retrospective deduplication.
- Bronze/silver/DB/gold writes are not jointly atomic. To recover: stop the app and other writers, run
  the replay command above into a new directory (`--config` for another configuration), inspect every
  reported failure, then replace `data/silver/` and `data/brownstone.duckdb` with the output's,
  keeping the old files and the original bronze. Gold screening exports are not rebuilt. Backup is
  STORY-016. Run one writer; synced drops can change during a read, so retry.
- The app reads on load: reload after importing elsewhere. Native clipboard/appearance and
  phone-width behaviour need manual checks. Each profession window event saves the full recipe list,
  most of a day's SavedVariables size.

## Verify

```bash
.venv/bin/python -m brownstone gates
git diff --check
```

`gates` runs ruff, mypy, `pytest -n auto --cov` (pytest-xdist), then `npm run check` in web/ on macOS;
it stops at the first failure and prints tests, coverage, time and the bytes left under the document
size guards. Opt-in pre-commit hook (ruff and mypy only): `git config core.hooksPath tools/git-hooks`.
Expected: 2,044 Python tests pass (one platform skip), plus the Vitest suite. Tests are offline;
coverage must meet the 88% branch-inclusive floor. CI runs macOS/Windows from requirements.lock.txt.
Windows uses `.venv\Scripts\python.exe`. Retirement checks live in `tests/test_retirement.py`; launcher
tests in `tests/test_launch_app.py`.

### App

Install the lock file and open `Open Brownstone App.command` / `.cmd`. For real-data checks, copy
data/ under ignored work/ and run `.venv/bin/python launch_app.py --data-dir /path/to/copied-data`
(browser check: `brownstone_app.py --data-dir /path/to/copied-data --port 8081`). Select the Forever
beta and open Today, Team, Market (Linen Cloth 2589, Bolt 2996), Ledger and the Data sheet; inspect
stale/unknown labels, holdings and source evidence. Preview never writes.

### Frozen beta corpus

Default real-data regression check (offline, current code/catalogs, temporary replay):

```bash
.venv/bin/python -m api.beta_check check work/beta-corpus/2026-10-18/
```

Exit 0 matches, 1 lists headline differences, 2 means invalid inputs or a hash failure. Explain
legitimate differences before `check <corpus-dir> --accept`, which replaces only expected.json. The
ignored corpus was made with `python -m api.beta_check freeze <new-dir>`, which refuses existing
destinations and never writes the data directory. Contract: [Beta corpus check](design.md#beta-corpus-check-story-101).

### After a play session

```bash
.venv/bin/python -m brownstone after-play
```

Imports new drops through the normal import, runs the beta report on each machine's changed latest
drop (and the local file) and prints only what is new, resolved or failing since the previous run,
then eligible scans and the pending in-game checks. State: `work/after-play/state.json` (delete it
to see everything again). Exit 1 means a failed check or import.

### Beta report

For one file, after logout/reload finishes writing:

```bash
.venv/bin/python -m brownstone beta-report "/path/to/BrownstoneScan.lua" --source forever-us-normal-alliance-addon
```

`--previous` compares earlier bytes. Writes private `work/beta-reports` report.md/json; exit 0 permits
warnings, 1 a failed check, 2 unreadable input. Keep raw files private (ADDON-07). The isolated
roundtrip never imports into real data or authorizes clear.
