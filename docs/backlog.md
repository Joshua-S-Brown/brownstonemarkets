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

Recently completed: STORY-004, recipe import from saved Wowhead pages, 2026-10-04; STORY-010, addon scan import, 2026-10-04; SPIKE-008, addon scan prototype, 2026-10-04 (see `status.md`).

**First, once:** install addon 0.2.0 (copy `addon/BrownstoneScan` over the old folder), take one scan, `/reload`, import it and check it succeeds; see `status.md` → *Limitations*. Then `/bscan clear` and `/reload` after each successful import.

**Time-sensitive, before the beta closes:** take several more scans, at least 15 minutes apart and ideally a few hours apart, and import each copy of the file. Bronze keeps them after the beta ends. Repeated scans are the only data for *Demand from your own scans*, and a Roleplaying or neutral house scan, if reachable, tests house identification. This is a manual habit at the auction house, not automation.

**Also on the beta, once:** confirm the Forever catalog's unconfirmed values (`status.md` → *Limitations*). Craft one Bolt of Linen Cloth and count the bolts made. At a trade supplies vendor, check that Coarse Thread, Fine Thread, Red Dye and Rune Thread are sold, and their prices. Record each result in the selection file (`config/recipe-selections/forever-tailoring.toml`) with the date, then regenerate. Also decide whether Runecloth Bag's dyes are really post-launch: both are listed on the beta auction house.

## Next

### STORY-014 — App command centre

Absorbs STORY-013 (one-click import from the game folder).

As a gold maker, I want every routine Brownstone action available as a button in the app, so that I never have to look up or type a command.

**Why first:** the beta closes on 4 November, and until then the routine is frequent: scan, import, confirm recipe values in-game, regenerate the catalog. Today, import exists as a button, but pointing it at the game folder means hand-editing `config/market.local.toml`. Recipe regeneration and the in-game confirmations are CLI- or editor-only. The CLI stays, for scripting.

**Principles** (all slices):
- **One explicit button per action.** Never a free-form command box.
- **Preview before every write.** A preview writes nothing. Writing happens only on a separate click, and the app then lists which tracked files changed, so you can review and commit them yourself.
- **No background work.** Browsing never imports, downloads or searches the disk (UI-01, ADDON-06).
- **Same code paths.** Buttons call the same `brownstone` functions as the CLI, so behaviour can't drift between the two.

**Slice 1 — Scan import from the game folder** (was STORY-013):
- **Find the file.** On a click, offer the SavedVariables files found under the usual WoW install folders (macOS `/Applications/World of Warcraft/_*_/`, Windows `C:\Program Files (x86)\World of Warcraft\_*_\`), one per account. The confirmed choice is saved as `scan_path` (and `enabled`) in the untracked `config/market.local.toml`, never the tracked config, because the path contains the account folder name.
- **Preview.** Before importing, show new, already-imported and partial scans, with times and listing counts. Optionally pick which scans to import, matching `--scan`. If nothing is new, say so and write nothing.
- **Safe reads.** A file being rewritten by the game (`/reload` or logout) fails cleanly and can be retried. The game folder is never written, watched or polled.

**Slice 2 — Recipe catalogs page, for every profession and game version:**
- **One catalog per game version and profession**, for example Forever Tailoring, Classic Tailoring and Forever Leatherworking. The page lists every catalog that exists, plus which professions don't have one yet.
- **Status for each catalog:**
  - catalog version and recipe count
  - the archived Wowhead page's save date, game build and SHA-256
  - the outstanding unconfirmed values (yield, vendor status and price, post-launch flags)
  - a **refresh due** flag when the page predates the market's current `rules_version` or a configurable age
- **Add a profession.** Pick the game version and profession. The app shows the exact Wowhead page to save (for example `wowhead.com/forever/spells/professions/leatherworking`) as a link for you to save in your browser; Brownstone still never downloads from Wowhead. Upload the saved page, choose the recipes (all of them, or filtered by name and skill range, with intermediates added automatically as today), then preview and create the selection file and catalog.
- **Update a profession.** Upload a newly saved page for an existing catalog. It's archived byte-for-byte as the CLI does. **Preview changes** shows the recipe and vendor-price diff and writes nothing; **Regenerate** writes the catalog and bumps its version.
- **Never across versions.** Uploading a page whose game version or profession doesn't match the chosen catalog is refused. A Classic page never fills a Forever catalog.
- **Any profession counts.** Catalogs are found by their selection files, not by a `*-tailoring` file name (today `app.py` only loads Tailoring).

**Slice 3 — In-game confirmations:**
- Tick off values checked on the beta (the yield you saw, a vendor confirmed with its price, a post-launch decision), each with a date. This writes to the selection file and offers Regenerate. It replaces hand-editing for the *Also on the beta, once* list under Now.

Acceptance:
- **No CLI or hand-editing** is needed for routine scan import, adding or refreshing any profession's catalog for either game version, or in-game confirmations.
- **Every write is previewed first** and happens only on an explicit click. Afterwards the app lists changed tracked files and never commits.
- **Personal paths stay out of Git.** They live only in `market.local.toml`.
- **Tests cover the logic** behind each button offline: discovery, preview and dry run, and the selection-file writes. Streamlit tests cover the preview → confirm flow.

### STORY-015 — Crafting across professions

Follows STORY-014. More catalogs only help if the board uses them together.

As a gold maker, I want the board to cost recipes using every profession I have a catalog for, so that a Tailoring recipe can use Leatherworking's Rugged Leather or a smelted bar at its real crafted cost instead of only the auction price.

Acceptance:
- **Combine catalogs per market.** For a market, use every catalog with the same `game_version` and `rules_version` together. Never mix game versions.
- **One recipe graph.** Intermediates from other professions resolve across catalogs, with the cheapest valid buy, craft or vendor route still per CRAFT-03. Today a catalog allows one recipe per output item; define what happens when two professions make the same item, such as choosing the cheapest valid route and showing which profession it came from.
- **Your professions.** An optional list of the professions you actually have restricts craft routes to those. Anything else is bought or flagged, never assumed craftable.
- **Board filters** by profession, tier or skill range, and name, so large catalogs stay usable.
- **Same rules.** Missing prices are never free, unsupported recipes are isolated per row, and the policy version is shown. Tests cover a cross-profession chain.

### STORY-011 — Optional third-party scan sources

As a gold maker, I want to add other players' Forever scans when a trustworthy one exists, so that I have broader coverage than my own scans without relying on it.

Acceptance:
- **Survey and record.** Check AHledger, Booty Bay Broker and TSM for an official export or API and terms that allow personal use. Record the result in `requirements.md`. If none qualifies, this story closes with no code.
- **Separate source.** A qualifying feed is ingested as its own source for the same market, with raw preservation and provenance like every other source.
- **Visible and optional.** The board shows which source each price came from. Disabling the source leaves everything working on your own scans.
- **Cross-check.** Where both sources cover an item, show how far apart they are, as a data-quality signal.

### STORY-003 — Classic demand context

As a gold maker, I want to see how often an item sells, so that a profitable craft isn't one that never sells.

Acceptance:
- **Separate data.** TSM's Classic regional file is ingested as its own source and never mixed with realm prices. Its columns are `avgSalePrice, saleRate, soldPerDay` (feasibility confirmed 2026-10-04).
- **Shown with care.** The board shows sold-per-day and sale rate with their own timestamp, labeled as context, not a promise to sell.
- **Forever caveat.** Nothing equivalent exists for Forever yet. A later demand estimate from repeated scans (see Later) should replace or check this.

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
- Item names: 4,690 listings arrived before the client loaded the item, and some items (Runecloth, 14047) appear only that way, so Browse shows `Item <ID>`. Crafting uses catalog names, so it's unaffected.

**Recipe coverage** (unblocked by STORY-004):
- **More recipes and professions:** handled in the app by STORY-014 (add or refresh any profession for either game version) and combined on the board by STORY-015.
- **Multi-yield costing:** if an in-game check shows a recipe makes more than 1, build whole crafts, round unit costs up to the copper, and show leftovers without crediting them. Keep the shopping list and the all-craft materials consistent. Until then the calculator can reject such intermediates with "Fractional unit costs" (`requirements.md` → *Not modeled*).
- **In-game recipe reader (optional):** the addon could read the Tailoring window (reagents, `GetTradeSkillNumMade`) and the trainer list (required skill) to confirm Wowhead values automatically. This widens the read-only addon and needs its own decision.

## Out of scope

- Buying, posting or any automated in-game action. The addon only reads.
- Unattended or scheduled in-game scanning.
- AI-generated recommendations without explainable features.
- Cloud deployment before replay, recovery and storage decisions.
