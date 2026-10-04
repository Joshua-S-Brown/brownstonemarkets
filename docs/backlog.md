# Brownstone Markets backlog

Planned product work, in priority order. Rules live in `requirements.md`, architecture in `design.md`, current state in `status.md`; completed work is recorded there and in Git, not here.

- **Now:** the active item, with agreed acceptance criteria.
- **Next:** ordered and ready to start (story plus acceptance criteria).
- **Later:** valuable but unscheduled, often waiting on an item above.

## Direction (groomed 2026-10-04)

WoW Forever launches **4 November 2026** and its beta is live. As of 2026-10-04 (sources in `requirements.md`):
- Blizzard's API publishes no Forever auction data, and its Classic Era auction endpoints have returned 404 since late 2024.
- TSM has no Forever data.
- Forever's own price sites are fed by players running scanning addons.

So the dependable path to Forever prices, and to the listing-level inventory that market models need, is our own addon scan. Classic remains the stand-in for everything that only needs aggregate prices.

## Now

Nothing active. Next up are SPIKE-008, which needs your in-game time on the beta, and STORY-009, which is code only; they can run in parallel. Launch market: Forever US, Roleplaying, Alliance.

## Next

### SPIKE-008 — Prove an addon can scan the auction house

Time-boxed to about two sessions. Its output is a decision, not production code.

As the product owner, I want to know whether a small in-game addon can capture every listing on an auction house, so that Brownstone can get Forever prices and inventory without depending on TSM.

Acceptance:
- **Prototype:** a minimal addon, written in Lua, the language WoW addons use. A scan starts only from a click at the auction house and records every listing: item, quantity, unit buyout, scan time and which auction house. It writes them to the addon's saved data file (WoW calls this SavedVariables), which the game saves on logout or `/reload`.
- **Run it** on the Forever beta, on the Roleplaying Alliance auction house, and once at a neutral house. Confirm which auction API the client exposes: Forever reportedly uses `C_AuctionHouse` with Retail-style commodities.
- **Record measurements:** scan time for a full house, throttling behaviour, file size, and anything that needs a hardware click.
- **Confirm the rules:** it doesn't automate gameplay, it never buys or posts, and it stays within Blizzard's addon policy.
- **Write up the decision** in `requirements.md`: build the addon or not, plus the listing-level data format STORY-010 will ingest.

### STORY-009 — Model Forever markets

As a gold maker, I want a Forever market to be identified the way the game actually works, and separately from whoever observed it, so that prices from different auction houses never mix and one market can have several sources.

Acceptance:
- **Market separate from source** (DATA-08). Today `market_id` is really a source ID, used in folder paths, the database and manifests. Split it into a market identity (which auction house) and a source identity (who observed it), with a schema migration that keeps existing Classic and Retail data intact.
- **Identity covers the new shape.** Forever has no realms: each region has one auction house per server type (Normal, PvP, RP, later Hardcore) and faction (Alliance, Horde, Neutral).
- **No forced realm.** A Forever source can be configured without inventing a realm. Existing Classic and Retail identities keep working, with a schema migration if one is needed.
- **Fix the naming clash.** Our `ruleset` (a catalog's game-rules version, for example `forever-beta-1.60`) is separated from Forever's server types; one of them is renamed.
- **Per-house auction cut.** The neutral house takes 15% instead of 5%, and a test covers it.
- **Recorded in the docs.** `requirements.md` (DATA-03) and the design data contracts are updated.

### STORY-010 — Ingest addon scans

Depends on SPIKE-008's decision.

As a gold maker, I want my own auction house scans imported, so that I see how many units are listed at each price, not just the cheapest.

Acceptance:
- **Raw preservation.** Importing a SavedVariables file preserves its bytes, provenance and a hash in bronze, exactly like a TSM download.
- **Listing-level storage.** A new listings table stores quantity and unit buyout per listing, keyed to the market and scan.
- **Same price view.** Item-level prices are derived in the same shape the board already reads (`min_buyout`, plus a median or market-value equivalent), so crafting works on Forever with no calculation changes.
- **Deduplication.** Re-importing the same scan is a no-op, and partial scans are labeled as partial.
- **Tests** run on a checked-in sample scan file.

### STORY-011 — Optional third-party scan sources

Depends on STORY-009. It can come before or after STORY-010.

As a gold maker, I want to add other players' Forever scans when a trustworthy one exists, so that I have broader coverage than my own scans without relying on it.

Acceptance:
- **Survey and record.** Check AHledger, Booty Bay Broker and TSM for an official export or API and terms that allow personal use. Record the result in `requirements.md`. If none qualifies, this story closes with no code.
- **Separate source.** A qualifying feed is ingested as its own source for the same market, with raw preservation and provenance like every other source.
- **Visible and optional.** The board shows which source each price came from. Disabling the source leaves everything working on your own scans.
- **Cross-check.** Where both sources cover an item, show how far apart they are, as a data-quality signal.

### STORY-004 — Import recipes for any game version

As a gold maker, I want recipe catalogs generated from a public source instead of typed by hand, so that I can cover whole professions on Classic now and on Forever at launch.

Acceptance:
- **Allowed and recorded.** Check the source's terms of use and record them before importing. Wowhead's tooltip data has the reagents and quantities; it's the source used for STORY-007.
- **Same catalog shape.** The importer writes a catalog with the current structure and per-recipe provenance. Its output matches the hand-verified Classic catalog exactly (a test enforces this) and fills in the three unconfirmed skill levels.
- **Forever beta Tailoring.** The importer produces a Forever beta Tailoring catalog for review. Profession, category and name filters keep large catalogs usable.
- **Rebuildable.** Imports are cached and reproducible; no live network access in tests.

### STORY-003 — Classic demand context

As a gold maker, I want to see how often an item sells, so that a profitable craft isn't one that never sells.

Acceptance:
- **Separate data.** TSM's Classic regional file is ingested as its own source and never mixed with realm prices. Its columns are `avgSalePrice, saleRate, soldPerDay` (feasibility confirmed 2026-10-04).
- **Shown with care.** The board shows sold-per-day and sale rate with their own timestamp, labeled as context, not a promise to sell.
- **Forever caveat.** Nothing equivalent exists for Forever yet. A later demand estimate from repeated scans (see Later) should replace or check this.

### STORY-006 — Replay and rebuild local data

As the product owner, I want derived data rebuildable from the raw archive, so that schema changes and validation fixes never strand old scans.

Acceptance:
- **Deterministic rebuild.** One command rebuilds silver and DuckDB from bronze into a fresh database without modifying bronze. Running it twice gives identical results.
- **Every source.** Covers TSM CSVs and, once STORY-010 exists, addon scans.
- **Documented.** It's the recovery procedure for partial runs referenced in `status.md`.

## Later

These are grouped by what unblocks them.

**Inventory-aware economics** (after STORY-010):
- **Cost from the listing ladder:** what N units actually cost when bought listing by listing.
- **Undercut-aware sale price.**
- **A suggested craft quantity limited by input depth.**

**Demand from your own scans** (after STORY-010 plus repeated scans; optional sources from STORY-011 can add more data points): estimate sell-through from listings that disappear between scans. This is Forever's substitute for TSM sale rates.

**History chain** (each step needs the one before):
1. Replay (STORY-006).
2. A storage and backup decision.
3. Routine scanning. An addon scan needs you at the auction house, so this is a habit, not a scheduler.
4. History, volatility and confidence features.
5. Backtesting the ranking policies.
6. Alerts.

**Other professions:** after STORY-004 proves the importer.

## Out of scope

- Buying, posting or any automated in-game action. The addon only reads.
- Unattended or scheduled in-game scanning.
- AI-generated recommendations without explainable features.
- Cloud deployment before replay, recovery and storage decisions.
