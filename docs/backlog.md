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

Nothing active in code. Brownstone can now run on our own addon scans alone (STORY-010). Launch market remains Forever US, Roleplaying, Alliance (`forever-us-roleplaying-alliance`); the beta currently offers only Normal servers, so the configured example source is `forever-us-normal-alliance`.

Recently completed: STORY-014 Slice 2, the Recipe catalogs page, 2026-10-04; STORY-004, recipe import from saved Wowhead pages, 2026-10-04; STORY-010, addon scan import, 2026-10-04; SPIKE-008, addon scan prototype, 2026-10-04 (see `status.md`).

**Before the beta closes on 4 November** (manual, in game):
- **Keep scanning.** Three complete scans of the Normal Alliance house are imported (16:47Z, 17:46Z and 22:54Z on 2026-10-04; the last is addon 0.2.0). Take more, at least 15 minutes apart, **at different times of day and on different days**, so the diff and timing work (STORY-018; *Market timing and a daily brief* under Later) has something to start from. The routine: scan, `/reload` (the game writes scans to the file only then, or on logout), import, and only then `/bscan clear` and `/reload`. A Roleplaying or neutral house scan, if reachable, tests house identification. This is a manual habit, not automation.
- **Confirm the Forever catalog's unconfirmed values** (`status.md` → *Limitations*). Learn Bolt of Linen Cloth and check how many it makes: the profession window may show the count on the product icon, and crafting one (2 Linen Cloth) settles it. At a trade supplies vendor, check that Coarse Thread, Fine Thread, Red Dye and Rune Thread are sold, and their prices. Record each result by hand in `config/recipe-selections/forever-tailoring.toml` with the date, then regenerate on the Recipe catalogs page. Also decide whether Runecloth Bag's dyes are really post-launch: both are listed on the beta auction house.
- **If any yield is more than 1,** *Multi-yield costing* (Later) moves to the top of Next: the Forever board's costs are wrong until it exists.

## Next

**Before launch**, in this order: STORY-017 to STORY-011a. **After launch:** the rest.

### STORY-017 — Keep beta and live data apart

As a gold maker, I want beta scans never to be treated as the live market, so that launch-day prices, comparisons and history aren't silently mixed with a beta economy that doesn't carry over.

**Why first:** the beta source derives `market_id = forever-us-normal-alliance`, exactly what a live Normal Alliance source would derive. Only `rules_version` differs, and that guards crafting, not market joins. The views take the newest observation, so the first live scan would replace beta prices, but anything that reads several scans (STORY-018, history) would join them. It is cheapest to fix before any live data exists.

Acceptance:
- **Decide and record** in `requirements.md` how a beta house is told apart from the live one (*Open decisions*). Beta and live never join on item ID (DATA-03).
- **Existing beta data keeps its provenance.** Any schema change is a numbered migration with a backup (OPS-02). The 2026-10-04 scans end up identified as beta and can still be imported again as duplicates.
- **Tests** cover: a beta and a live source for the same house get different market identities, and single-scan and multi-scan reads never combine them.

### STORY-016 — Back up local data

As the product owner, I want a tested backup of `data/`, so that the beta scans, which can't be retaken after 4 November, survive a disk failure or a bad migration.

Acceptance:
- **Decide and record** in `requirements.md` where backups go (a location you control, such as a second disk) and when to take them, for example after each import session and before every migration or launch step.
- **One documented procedure** that refuses to run while a writer holds the DuckDB lock, copies `data/` to a dated folder, and verifies the copy: file count, and SHA-256 of every bronze file.
- **Restore tested once:** restored into a fresh folder, the app opens it and the Forever board matches the original.
- Bronze is the irreplaceable part. Derived data becomes rebuildable with STORY-006.

### STORY-015a — One market choice, catalogs combined

Split from STORY-015 at grooming (2026-10-04); cross-profession routing is STORY-015b.

As a gold maker, I want to pick only a market and see every compatible catalog on one board, so that I'm not choosing a data source in the sidebar and then a catalog on the page (feedback 2026-10-04).

Acceptance:
- **The market is the only choice.** The sidebar picks the source; the Crafting view has no catalog selector. The board lists the recipes of every catalog with the same `game_version` and `rules_version`, with a Profession column and a profession filter. Game versions are never mixed.
- **Each recipe is costed within its own catalog**, as today. If two catalogs make the same item, both rows are shown with their profession, and nothing chooses between them (that rule is STORY-015b's).
- **Nothing compatible:** the view names the catalogs that exist for that game version and why they don't match (`rules_version`), and points to the Recipe catalogs page. Incompatible catalogs stay inspectable, never priced (UI-04).
- **Same rules:** missing prices are never free, errors are isolated per row, and the policy version is shown. A Streamlit test covers a market with two compatible catalogs.

### STORY-018 — What changed between scans

As a gold maker, I want to see what moved between two scans of a market, so that I can tell what changed since I last looked without comparing tables by hand.

Acceptance:
- **Prices for any snapshot,** not only the newest, for one source and market at a time (DATA-08).
- **Diff view.** Pick two complete scans (default: the newest two). For each item, show minimum buyout, market value, listings and units in each scan, and the change. Items new and vanished since the earlier scan are listed separately. A filter limits the list to catalog items.
- **Honest labels.** An item absent from a scan is "not listed", never zero. Both scan times and the gap between them are shown.
- **Tests** with fixture scans cover new, vanished, unchanged and changed items, and show that partial scans can't be chosen.
- Unblocks *Removed listings*, *Did the board hold up?* and *Market timing* (Later).

### STORY-019 — Market depth on the board

As a gold maker, I want the Action Board to show how deep the market is for each output and input, so that a profit on one listing doesn't look as solid as a profit on a thousand.

Acceptance:
- **Display only:** listings and units in the priced scan for each output and each direct input, from `scan_listings`. Calculations, labels and ranking don't change (`requirements.md` → *Not modeled*).
- **The recipe view** shows the same for each input row.
- **Sources without listings** (TSM) show depth as unavailable, never zero.
- **Tests** cover an addon market with and without listings for an output.

### STORY-014 — Scan import preview

Shrunk at grooming (2026-10-04). Slice 2, the Recipe catalogs page, is done (`status.md`). Finding the file in the game folder and the in-game confirmation UI moved to Later.

As a gold maker, I want to see what an import will do before it runs, so that I know which scans are new, which are duplicates and which are partial before anything is written.

Acceptance:
- **Preview.** On a click, read the configured `scan_path` and list each scan: ID, times, status, listing count, and whether it is new, already imported or partial. Nothing is written.
- **Choose.** Optionally pick which new scans to import, matching `--scan`. If nothing is new, say so with the `/reload` reminder and offer no import.
- **Safe reads.** A file the game is rewriting (`/reload` or logout) fails cleanly and can be retried. The file is never written, watched or polled (ADDON-06).
- **Exactly what was shown.** The import recomputes the preview and uses the same code as the CLI. Tests cover the preview offline; a Streamlit test covers preview → import.

### STORY-020 — Launch-day runbook

As a gold maker, I want a short, tested checklist for 4 November, so that the switch to the live game is quick and nothing is missed.

Acceptance:
- **A runbook** in `docs/`, linked from `status.md`, covering:
  - backing up before and after (STORY-016)
  - adding and enabling the live Roleplaying Alliance source in `config/market.local.toml`, with its `rules_version`
  - checking that the addon loads (the `.toc` interface number may change)
  - the first scan, `/reload` and import
  - re-saving each Forever Wowhead page and regenerating. If the live `rules_version` differs from the beta's, every Forever catalog stays inspection-only until regenerated (*Refresh due* flags it).
  - re-checking *Known Forever market facts* in `requirements.md`
- **Rehearsed on the beta** before it closes, with each step timed.
- Depends on STORY-016 and STORY-017.

### STORY-012 — Compare a market with a reference market

As a gold maker, I want to see an item's price on Forever next to its price on Classic Era, so that I can sanity-check Forever prices and spot import errors, especially in the first weeks after launch.

Acceptance:
- **Explicit pairing.** The user picks two configured sources, each a different market. Items pair on item ID only inside this view, and the view is labeled as a comparison of different markets. Nothing from it feeds crafting, the board or any price basis (DATA-03, DATA-08).
- **Shown with care.** Each side shows its own source, scan time and freshness, plus the ratio between them. Items missing or unpriced on either side are listed, never treated as zero.
- **Evidence for the idea:** on 2026-10-04, 2,323 of 2,927 priced Forever beta items were also priced on Mankrik. Common materials were within about 0.5–2× (Linen Cloth 38c vs 32c), but scarce high-level ones diverged widely (Runecloth 2g 55s vs 10s 75c). The median ratio was 0.32.

### STORY-011a — Survey third-party scan sources

Split from STORY-011 at grooming (2026-10-04); ingestion is STORY-011b under Later.

As a gold maker, I want to know whether any trustworthy third-party Forever scan source can be used, so that I can plan around it rather than guess.

Acceptance:
- **Survey and record.** Check AHledger, Booty Bay Broker and TSM for an official export or API and terms that allow personal use. Record the result in `requirements.md`, closing that open decision. No code.
- If a source qualifies, STORY-011b moves to Next.

### STORY-021 — Item page

As a gold maker, I want one page per item that explains its price, so that I can see the listings behind a number, how it has moved, and what I craft with it.

Acceptance:
- **Pick an item** from Browse or the board.
- **The page shows:**
  - the listing ladder in the chosen scan (quantity, unit price, cumulative units)
  - its prices in each scan of this source
  - the catalogs that make or use it, with profession and role
- **The same rules:** one source at a time, missing never zero, and no categories inferred.
- Depends on STORY-018 (prices for any snapshot).

### STORY-006 — Replay and rebuild local data

As the product owner, I want derived data rebuildable from the raw archive, so that schema changes and validation fixes never strand old scans.

Acceptance:
- **Deterministic rebuild.** One command rebuilds silver and DuckDB from bronze into a fresh database without modifying bronze. Running it twice gives identical results.
- **Every source.** Covers TSM CSVs and addon scans (bronze `.lua` and `.lua.gz` files; silver already holds per-scan listings and prices).
- **Documented.** It's the recovery procedure for partial runs referenced in `status.md`. Backup is STORY-016.

### STORY-015b — Crafting across professions

Split from STORY-015 at grooming (2026-10-04). Depends on STORY-015a. It pays off once there are catalogs that feed each other (for example Leatherworking or Mining for Tailoring); today's Tailoring, Alchemy and Enchanting catalogs share few materials.

As a gold maker, I want the board to cost recipes using every profession I have a catalog for, so that a Tailoring recipe can use Leatherworking's Rugged Leather or a smelted bar at its real crafted cost instead of only the auction price.

Acceptance:
- **One recipe graph.** Intermediates from other professions resolve across a market's compatible catalogs, with the cheapest valid buy, craft or vendor route still per CRAFT-03. Decide, and record in `requirements.md`, what happens when two professions make the same item, such as choosing the cheapest valid route and showing which profession it came from.
- **Your professions.** An optional list of the professions you actually have restricts craft routes to those. Anything else is bought or flagged, never assumed craftable.
- **Board filters** by tier or skill range, and name, so large catalogs stay usable.
- **Same rules.** Missing prices are never free, unsupported recipes are isolated per row, and the policy version is shown. Tests cover a cross-profession chain.

## Later

These are grouped by what unblocks them.

**Inventory-aware economics** (unblocked: `scan_listings` holds every listing; STORY-019 shows depth first):
- **Cost from the listing ladder:** what N units actually cost when bought listing by listing, and the most you can buy below a price.
- **Undercut-aware sale price.**
- **A suggested craft quantity limited by input depth.**
- **Thin-market flag:** few listings, a wide gap between minimum buyout and market value, or most units in one stack. Thresholds need a decision.

**Demand from your own scans** (needs repeated scans and STORY-018; optional sources from STORY-011b can add more data points):
- **Removed listings:** listings that disappear between scans, matched on item, quantity and buyout. Scans carry no auction ID, so a sale, a cancellation and an expiry look the same. It is an upper bound on sales, labeled *removed*, never *sold*. This is Forever's substitute for TSM sale rates.
- **Did the board hold up?** Whether "potential craft" rows were still profitable at the next scan. A tiny check is possible with beta scans; it means something after one to two weeks of live scans.

**Market timing and a daily brief** (requested 2026-10-04; needs post-launch history, not beta scans (STORY-017)). The goal is to know when to buy and sell each kind of item (materials, crafted goods, equipment), and to open the app to a short list of the day's priorities without being online all day.
- **Honest limits:** scans happen only when you are at the auction house, so hour-of-day and weekday patterns are sampled at your playtimes. A pattern is shown only with its coverage (scans per hour and weekday), and claimed only where coverage is enough. Weekday effects such as the weekly reset need at least four weeks. Optional sources (STORY-011b) could fill hours you don't scan.
- **Steps** (each needs the one before):
  1. **Scan coverage:** scans by hour and weekday, and gaps, so you can deliberately fill them in a few sessions a week.
  2. **Timing profile:** per item, and for groups by catalog role (material, intermediate, finished; never inferred from names), price and supply by hour and weekday, with a confidence label. "Cheapest to buy" and "best to sell" windows only where coverage supports them.
  3. **Daily brief:** one page of today's priorities, each with its evidence and confidence: profitable crafts with depth, inputs below their own recent median, outputs above it, and what the timing profile says to buy or hold. It can start rule-based on the newest scan and STORY-018, and gain timing as history grows.

**History chain** (each step needs the one before):
1. Replay (STORY-006).
2. A storage decision (backup is STORY-016).
3. Routine scanning. An addon scan needs you at the auction house, so this is a habit, not a scheduler. *Scan coverage* above helps.
4. History, volatility and confidence features: per-item trend and spread need about ten or more scans over a week or more, so not before mid-November.
5. Backtesting the ranking policies.
6. Alerts.

**Classic demand context** (was STORY-003 in Next; moved at grooming, 2026-10-04, because it serves the stand-in, not Forever):
- TSM's Classic regional file is ingested as its own source and never mixed with realm prices. Its columns are `avgSalePrice, saleRate, soldPerDay` (feasibility confirmed 2026-10-04).
- The board shows sold-per-day and sale rate with their own timestamp, labeled as context, not a promise to sell.
- *Removed listings* (above) is the Forever equivalent and should replace or check it.

**STORY-011b — Third-party scan ingestion** (only if STORY-011a finds a qualifying source):
- **Separate source.** A qualifying feed is ingested as its own source for the same market, with raw preservation and provenance like every other source.
- **Visible and optional.** The board shows which source each price came from. Disabling the source leaves everything working on your own scans.
- **Cross-check.** Where both sources cover an item, show how far apart they are, as a data-quality signal.

**App conveniences** (moved from STORY-014 at grooming, 2026-10-04):
- **Find the scan file:** on a click, offer the SavedVariables files under the usual WoW install folders, one per account, and save the choice as `scan_path` in the untracked `config/market.local.toml`. Your path is already set, so this only helps a new machine or account.
- **In-game confirmations:** tick off values checked in game (a yield, a vendor and its price, a post-launch decision) with a date, written to the selection file, then Regenerate. For now there are only a few, edited by hand.
- **Browse filters:** items used or made by any catalog (membership, not names) and a minimum listing count.
- **Best use of a material:** for an item such as Linen or Wool Cloth, compare selling it with each craft it feeds, at current prices.

**Addon follow-ups** (any time, none urgent):
- Scan the Roleplaying house once the beta offers it, and a neutral house when reachable, to confirm house identification and the 15% cut market.
- Check whether `/bscan start` works without the button click.
- Item names: 4,690 listings arrived before the client loaded the item, and some items (Runecloth, 14047) appear only that way, so Browse shows `Item <ID>`. Crafting uses catalog names, so it's unaffected. Fix: take an item's name from any scan of the same game version where it loaded.

**Recipe coverage** (unblocked by STORY-004):
- **More recipes and professions:** added in the app on the Recipe catalogs page, and combined on the board by STORY-015a and STORY-015b.
- **Multi-yield costing:** if an in-game check shows a recipe makes more than 1, build whole crafts, round unit costs up to the copper, and show leftovers without crediting them. Keep the shopping list and the all-craft materials consistent. Until then the calculator can reject such intermediates with "Fractional unit costs" (`requirements.md` → *Not modeled*). **Moves to the top of Next if the Bolt of Linen Cloth check finds a yield above 1.**
- **Skill-up demand map:** from the catalogs' skill levels and quantities, which materials levelling crafters will need at each skill band. A reasoned expectation for stocking up before launch, not a forecast.
- **In-game recipe reader (optional):** the addon could read the Tailoring window (reagents, `GetTradeSkillNumMade`) and the trainer list (required skill) to confirm Wowhead values automatically. This widens the read-only addon and needs its own decision.

## Out of scope

- Buying, posting or any automated in-game action. The addon only reads.
- Unattended or scheduled in-game scanning.
- AI-generated recommendations without explainable features.
- Cloud deployment before replay, recovery and storage decisions.
