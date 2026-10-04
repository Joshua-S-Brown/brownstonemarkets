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

Nothing active. Brownstone can now run on our own addon scans alone (STORY-010). Launch market remains Forever US, Roleplaying, Alliance (`forever-us-roleplaying-alliance`); the beta currently offers only Normal servers, so the configured example source is `forever-us-normal-alliance`.

Recently completed: STORY-010, addon scan import, 2026-10-04; SPIKE-008, addon scan prototype, 2026-10-04 (see `status.md`).

**Time-sensitive, before the beta closes:** take several more scans, at least 15 minutes apart and ideally a few hours apart, and import each copy of the file. Bronze keeps them after the beta ends. Repeated scans are the only data for *Demand from your own scans*, and a Roleplaying or neutral house scan, if reachable, tests house identification. This is a manual habit at the auction house, not automation.

## Next

### STORY-011 — Optional third-party scan sources

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
- **Forever beta Tailoring.** The importer produces a Forever beta Tailoring catalog for review, from the first tier up. Beta listings are concentrated in low-level goods: the 2026-10-04 scan had 1,378 Linen Bag and 301 Woolen Bag listings but no Runecloth Bag. Low-tier bags are what the board can exercise before launch. Profession, category and name filters keep large catalogs usable.
- **Rebuildable.** Imports are cached and reproducible; no live network access in tests.

### STORY-003 — Classic demand context

As a gold maker, I want to see how often an item sells, so that a profitable craft isn't one that never sells.

Acceptance:
- **Separate data.** TSM's Classic regional file is ingested as its own source and never mixed with realm prices. Its columns are `avgSalePrice, saleRate, soldPerDay` (feasibility confirmed 2026-10-04).
- **Shown with care.** The board shows sold-per-day and sale rate with their own timestamp, labeled as context, not a promise to sell.
- **Forever caveat.** Nothing equivalent exists for Forever yet. A later demand estimate from repeated scans (see Later) should replace or check this.

### STORY-013 — Import straight from the game folder

As a gold maker, I want to click one button after a scan without copying files around, so that importing is part of the scan habit.

Already possible: `scan_path` can point at the game's own SavedVariables file (`<WoW>/_classic_beta_/WTF/Account/<account>/SavedVariables/BrownstoneScan.lua`). Import reads it without writing, stores identical bytes in bronze once, and skips scans already imported. No copy into `data/inbox/` is needed; bronze is the archive.

Acceptance:
- **Find the file.** Offer the SavedVariables files found under the usual WoW install folders (macOS `/Applications/World of Warcraft/_*_/`, Windows `C:\Program Files (x86)\World of Warcraft\_*_\`), one per account. The user confirms the choice, and it is saved as `scan_path` in the untracked `config/market.local.toml`, never the tracked config, because the path contains the account folder name. Nothing is searched on startup.
- **Preview before import.** Show what the file holds and what import would do: new, already imported and partial scans, with times and listing counts. If nothing is new, say so and import nothing, so no manifest or bronze copy is written.
- **Safe reads.** A file being rewritten by the game (`/reload` or logout) fails cleanly and can be retried. The game folder is never written, watched or polled, and import still happens only on a click (ADDON-06).

### STORY-012 — Compare a market with a reference market

As a gold maker, I want to see an item's price on Forever next to its price on Classic Era, so that I can sanity-check Forever prices and spot import errors, especially in the first weeks after launch.

Acceptance:
- **Explicit pairing.** The user picks two configured sources, each a different market. Items pair on item ID only inside this view, and the view is labeled as a comparison of different markets. Nothing from it feeds crafting, the board or any price basis (DATA-03, DATA-08).
- **Shown with care.** Each side shows its own source, scan time and freshness, plus the ratio between them. Items missing or unpriced on either side are listed, never treated as zero.
- **Evidence for the idea:** on 2026-10-04, 2,323 of 2,927 priced Forever beta items were also priced on Mankrik. Common materials were within about 0.5–2× (Linen Cloth 38c vs 32c), but scarce high-level ones diverged widely (Runecloth 2g 55s vs 10s 75c). The median ratio was 0.32.

### STORY-006 — Replay and rebuild local data

As the product owner, I want derived data rebuildable from the raw archive, so that schema changes and validation fixes never strand old scans.

Acceptance:
- **Deterministic rebuild.** One command rebuilds silver and DuckDB from bronze into a fresh database without modifying bronze. Running it twice gives identical results.
- **Every source.** Covers TSM CSVs and addon scans (bronze `.lua` files; silver already holds per-scan listings and prices).
- **Documented.** It's the recovery procedure for partial runs referenced in `status.md`.

## Later

These are grouped by what unblocks them.

**Inventory-aware economics** (unblocked: `scan_listings` holds every listing):
- **Cost from the listing ladder:** what N units actually cost when bought listing by listing.
- **Undercut-aware sale price.**
- **A suggested craft quantity limited by input depth.**

**Demand from your own scans** (needs repeated scans; optional sources from STORY-011 can add more data points): estimate sell-through from listings that disappear between scans. This is Forever's substitute for TSM sale rates.

**History chain** (each step needs the one before):
1. Replay (STORY-006).
2. A storage and backup decision.
3. Routine scanning. An addon scan needs you at the auction house, so this is a habit, not a scheduler.
4. History, volatility and confidence features.
5. Backtesting the ranking policies.
6. Alerts.

**Addon follow-ups** (any time, none urgent):
- Scan the Roleplaying house once the beta offers it, and a neutral house when reachable, to confirm house identification and the 15% cut market.
- Check whether `/bscan start` works without the button click.
- Reduce file size (shorter field names or keeping fewer scans) if several scans make loading slow. Import parses the 24 MB file in about 0.9 s, so this isn't pressing.
- Find out why the 2026-10-04 scan has no `unit_buyout` on any of its 28,105 stacked listings, although every one divides exactly. The importer doesn't depend on it (it divides `buyout` by `quantity` itself), but the addon's documented behaviour and the file disagree.
- Item names: 4,690 listings arrived before the client loaded the item, and some items (Runecloth, 14047) appear only that way, so Browse shows `Item <ID>`. Crafting uses catalog names, so it's unaffected.

**Other professions:** after STORY-004 proves the importer.

## Out of scope

- Buying, posting or any automated in-game action. The addon only reads.
- Unattended or scheduled in-game scanning.
- AI-generated recommendations without explainable features.
- Cloud deployment before replay, recovery and storage decisions.
