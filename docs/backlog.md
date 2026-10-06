# Brownstone Markets backlog

Planned product work, in priority order. Rules live in `requirements.md`, architecture in `design.md`, current state in `status.md`; completed work is recorded there and in Git, not here.

- **Now:** the active item, with agreed acceptance criteria.
- **Next:** ordered and ready to start (story plus acceptance criteria).
- **Later:** valuable but unscheduled, often waiting on an item above.

## Direction (groomed 2026-10-04)

WoW Forever launches **4 November 2026**; **21 October is the last full beta testing day** (official dates linked in `requirements.md` → *Product direction*). As of 2026-10-04 (sources in `requirements.md`):
- Blizzard's API publishes no Forever auction data, and its Classic Era auction endpoints have returned 404 since late 2024.
- TSM has no Forever data.
- Forever's own price sites are fed by players running scanning addons.

So the dependable path to Forever prices, and to the listing-level inventory that market models need, is our own addon scan. Classic remains the stand-in for everything that only needs aggregate prices.

## Now

Scan format 3 (STORY-023) and the reload/clear buttons (STORY-029) are accepted on the beta with addon 0.3.1; the measurement record is in `addon/README.md`. Brownstone can now run on our own addon scans alone (STORY-010). Launch market remains Forever US, Roleplaying, Alliance (`forever-us-roleplaying-alliance`); the beta currently offers only Normal servers, so the configured example source is `forever-us-normal-alliance`.

**Through the last full beta testing day, 21 October** (manual, in game):
- **Keep scanning.** Seven complete scans of the Normal Alliance house are imported; dates and counts are in `status.md` → *Limitations*. Take more, at least 15 minutes apart, **at different times of day and on different days**, so the diff and timing work (STORY-018; *Market timing and a daily brief* under Later) has something to start from. The routine: scan, `/reload` (the game writes scans to the file only then, or on logout), import, and only then `/bscan clear` and `/reload`. A Roleplaying or neutral house scan, if reachable, tests house identification. This is a manual habit, not automation.
- **Confirm the Forever catalog's unconfirmed values** (`status.md` → *Limitations*). Learn Bolt of Linen Cloth and check how many it makes: the profession window may show the count on the product icon, and crafting one (2 Linen Cloth) settles it. At a trade supplies vendor, check that Coarse Thread, Fine Thread, Red Dye and Rune Thread are sold, and their prices. Record each result by hand in `config/recipe-selections/forever-tailoring.toml` with the date, then regenerate on the Recipe catalogs page. Also decide whether Runecloth Bag's dyes are really post-launch: both are listed on the beta auction house.
- **Widen the Forever catalogs** (manual, on the Recipe catalogs page): the rest of Tailoring, then the professions you plan to level at launch. The board and Today's *Craft* list only cover catalog recipes, so this is what gives them something to show.
- **If any yield is more than 1** (now unlikely: Wowhead's "(2)" is an effect number, not a count; see `requirements.md` → CRAFT-08), *Multi-yield costing* (Later) moves to the top of Next: the Forever board's costs are wrong until it exists.

## Next

**Agreed order (groomed 2026-10-05):** the app is almost all tables today, so user-facing analysis now gets its own lane in Next instead of waiting behind launch preparation. The layers, each building on the one before:
- **Scans** (exists) → **market metrics** (exists; ADDON-10 in `requirements.md`) → **analysis views** (item page, charts, sellers) and the **Today** page (what to buy, craft and sell now).
- An optional AI narration layer can come later. It may only explain those defined metrics, never invent numbers (*Out of scope*).
- Time-of-day and weekday patterns need weeks of live scans (*Market timing* under Later). Everything in Next works on a single scan or a few, so it can be built and tested on beta scans now.

**Order:**
1. STORY-025 Today
2. STORY-027 removed listings
3. STORY-015b crafting across professions
4. STORY-021 item page and charts
5. STORY-026 scan coverage and rhythm
6. STORY-028 sellers and supply chains (blocked: see *Seller capture* under Later)
7. STORY-006 replay

**Reordered 2026-10-06 (product owner):** Today comes first because it is the first page that answers what to do. STORY-027 and STORY-015b follow because they unblock Today's biggest gaps: sales speed, and chains such as ore → bars → armor (*Today, later versions* under Later). The launch runbook (STORY-020a/b) moved to Later.

STORY-016 (backup) is deferred to Later (product owner, 2026-10-06).

STORY-011a is a bounded research task for any convenient gap. Tailoring yield and vendor checks run alongside all of this; a confirmed multi-yield requirement takes priority.

**Archive care meanwhile:** nothing required; migrations copy the database first (OPS-02). The tested backup procedure is STORY-016, deferred to Later; its destination is still an open decision. Market isolation is implemented; see DATA-03 in `requirements.md`.

### STORY-021 — Item page and charts

Extended at grooming (2026-10-05) with time-series and ladder charts, the app's first charts.

As a gold maker, I want one page per item that explains its price, so that I can see the listings behind a number, how it has moved, and what I craft with it.

Acceptance:
- **Pick an item** from Browse, the board, Scan changes or Today; the chosen item stays selected when switching views.
- **The page shows:**
  - a time-series chart of lowest and typical price and units listed across this source's scans, with each point's scan time (UTC and local)
  - the listing ladder in the chosen scan as a chart and table (quantity, unit price, cumulative units)
  - the catalogs that make or use it, with profession and role, and its board rows
  - freshness (DATA-05)
- **Charts never invent data:** a scan where the item was absent is a gap, never zero, and every point names its scan.
- **The same rules:** one source at a time, missing never zero, and no categories inferred. It reads ADDON-10 metrics and the stored listings.
- Depends on the implemented market metrics layer (ADDON-10). Links to the *Value-add chart* (Later) once that exists.

### STORY-025 — Today: what to craft, buy and sell now

Implemented and pending review; rules and decisions: `requirements.md` → *Today (version 1)*.

Reshaped with the product owner 2026-10-06: rank by total gold for the effort, sized to your funds, instead of a list of deals. No sniping: nothing here depends on catching a listing within minutes.

As a gold maker, I want the app to open on a short plan of what to craft, buy and sell right now, sized to the gold I have, so that my time in game goes to the biggest worthwhile gains and not to copper.

Acceptance:
- **Opening page.** Today is the first view for every source (decided 2026-10-06).
- **Your settings,** at the top, remembered between sessions in a local file that Git ignores:
  - **Gold available,** typed as gold, silver and copper (`12g 50s`, `75s`, `1g 5s 20c`). Add a parser to `money.py`; a bare number without a unit is rejected with a hint rather than guessed. Stored as integer copper.
  - **Minimum gain worth doing,** either a fixed amount or *scaled*: the larger of a fixed minimum and a percentage of gold available. Starting values: scaled, 1% of gold available, at least 10s. So 50s available → 10s minimum, 100g → 1g, 1,000g → 10g. The minimum grows with your funds, which moves the page towards bigger-ticket crafts as you get richer. Both values are adjustable on the page.
  - **Most crafts per item,** starting at 5. It stands in for sales speed, which no data supports yet, so you don't flood a market.
- **1. Craft today:** profitable recipes from compatible catalogs, ranked by **total profit for the batch**, not margin.
  - Batch size is the smallest of: crafts the listed materials allow, crafts gold available pays for, and most crafts per item.
  - Material cost is bought listing by listing from the scan for the whole batch, so cost rises as cheap listings run out. Vendor materials use the vendor price. Profit uses the board's existing cautious sale price and auction cut.
  - Hidden: batches whose profit is below the minimum gain, and recipes where one craft costs more than gold available. A count of hidden rows, with the reason, is shown.
  - Each row shows profit per craft and per batch, batch size and what limited it, total material cost, and the output's competition (see *Sell*).
- **2. Buy for these crafts:** one shopping list for the Craft rows shown, per material: units, total cost listing by listing, and the highest unit price you'd pay. A material is marked *cheap now* when that average is below its own 25th-percentile price in the scan (informational only; it never changes the ranking).
  - **Below vendor price,** as a small aside: listings priced under what a vendor pays, a certain gain, shown only when the total gain clears the minimum.
- **3. Sell:** for each Craft row's output: lowest competing listing, listings and units listed, the price that undercuts the lowest listing and the profit at that price. Mark it **thin** when fewer than 3 listings exist or one stack holds half or more of the units listed.
- **Every row shows its evidence:** the numbers behind it and the scan time. Rows are capped at 10 per list, with a count of the rest.
- **Rules versioned** in `requirements.md` as a new rule set (*Today*, version 1) with every threshold above. No hidden scoring and no AI.
- **Honest:**
  - A scan older than the board's freshness limit puts a banner at the top and marks every row *stale*, never actionable. Beta scans will show this; the page must still be inspectable for testing.
  - Missing prices never become recommendations. Nothing is called a sale or a forecast.
  - With a TSM source (no individual listings), depth-based parts say *not available for this source*. Batch size then uses gold available and most crafts per item only.
- **Tested offline** with fixtures: money parsing (units, rejection, round trip), the minimum-gain modes, each batch limit, listing-by-listing cost across several listings, hidden-row counts, the thin flag, stale banners and a TSM source.
- Depends on the implemented market metrics (ADDON-10) and the crafting board. Absorbs *Cost from the listing ladder*, *Suggested craft quantity limited by input depth*, *Undercut-aware sale price* and *Thin-market flag* (formerly *Inventory-aware economics* under Later). Extensions that need more data are under *Today, later versions* (Later).

### STORY-026 — Scan coverage and your play rhythm

As a gold maker, I want to see when I've scanned and when I usually play, so that I know which times are covered and when it's worth making time to log in.

Acceptance:
- **Coverage grid:** scans by hour and weekday in local time for the selected source, with counts and gaps.
- **Your rhythm:** the hours and days you usually scan, from scan times only.
- **What's missing:** which slots need scans before timing claims can be made, with the thresholds recorded in `requirements.md`.
- Works on beta scans now. Depends on nothing (uses `addon_scans`). Feeds *Plan ahead* under Later.

### STORY-027 — Removed listings between scans

Moved from *Demand from your own scans* (Later) at grooming (2026-10-05).

As a gold maker, I want to see which listings disappeared between two scans, so that I have some evidence of what moves, since the game shows no sales.

Acceptance:
- **Matching:** listings present in one scan and gone from the next, matched on item, quantity and buyout, plus seller and time left when STORY-023 provides them. Time left separates expiry from an early disappearance.
- **Honest labels:** always *removed*, never *sold*. Scans carry no auction ID, so a sale, a cancellation and an expiry can look the same; it's an upper bound on sales.
- **Only consecutive scans** within a maximum gap recorded in `requirements.md`.
- Shown per item (on the item page) and as a list, and usable by Today as evidence: it is the first step towards replacing Today's fixed *most crafts per item* with sales speed.
- Depends on the implemented market metrics layer (ADDON-10); better with STORY-023.

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

### STORY-015b — Crafting across professions

Split from STORY-015 at grooming (2026-10-04). Builds on the combined board in `status.md` (STORY-015a, implemented). It pays off once there are catalogs that feed each other (for example Leatherworking or Mining for Tailoring); today's Tailoring, Alchemy and Enchanting catalogs share few materials.

As a gold maker, I want the board to cost recipes using every profession I have a catalog for, so that a Tailoring recipe can use Leatherworking's Rugged Leather or a smelted bar at its real crafted cost instead of only the auction price.

Acceptance:
- **One recipe graph.** Intermediates from other professions resolve across a market's compatible catalogs, with the cheapest valid buy, craft or vendor route still per CRAFT-03. Decide, and record in `requirements.md`, what happens when two professions make the same item, such as choosing the cheapest valid route and showing which profession it came from.
- **Your professions.** An optional list of the professions you actually have restricts craft routes to those. Anything else is bought or flagged, never assumed craftable.
- **Board filters** by tier or skill range, and name, so large catalogs stay usable.
- **Same rules.** Missing prices are never free, unsupported recipes are isolated per row, and the policy version is shown. Tests cover a cross-profession chain.

## Later

**Optional client-version cutover guard:** investigate whether recorded client versions can flag a misconfigured beta/live source during STORY-020b and first live imports. Source configuration remains authoritative (DATA-03); STORY-017 adds no client-version evidence checks.

These are grouped by what unblocks them.

**Seller capture** (found 2026-10-06; blocks STORY-028 and seller matching in STORY-027): the Forever beta's bulk scan returns no seller names (ADDON-07). Left blocked until after go-live (product owner, 2026-10-06): check whether live scans return seller names. Only if they don't, decide between another read-only way of getting them (such as per-item searches, at the cost of many more auction-house requests and a longer scan) and dropping or reshaping STORY-028.

**Today, later versions** (captured 2026-10-06 with the product owner; each extends STORY-025 once its data exists):
- **Sales speed instead of a fixed cap:** replace *most crafts per item* with how many units of the output disappear between scans. Needs STORY-027 and a few weeks of live scans; label it removed, not sold.
- **Stockpile:** materials below their own multi-day typical price, worth buying ahead for recipes you craft often, with a holding limit tied to gold available. Needs price history across days (*History chain*), so after launch.
- **Volatility:** how much an item's typical price swings across scans, shown as a risk note and used to demote unstable crafts. Needs the same history.
- **Restock:** what you hold in bags and bank, so *Buy* skips it and *Sell* includes it. Needs *Your own character's data* (a decision).
- **Whole chains:** ore → bars → armor across professions, with the gain at each stage (sell bars or craft on). Needs STORY-015b.
- **Gold per hour:** if the scaled minimum gain feels wrong in play, try a time-based minimum instead. Decide after using version 1.

**Demand from your own scans** (needs repeated scans and STORY-018; optional sources from STORY-011b can add more data points):
- *Removed listings* is now STORY-027 in Next.
- **Did the board hold up?** Whether "potential craft" rows were still profitable at the next scan. A tiny check is possible with beta scans; it means something after one to two weeks of live scans.

**Market timing and a daily brief** (requested 2026-10-04; needs post-launch history, not beta scans (STORY-017)). The goal is to know when to buy and sell each kind of item (materials, crafted goods, equipment), and to open the app to a short list of the day's priorities without being online all day.
- **Honest limits:** scans happen only when you are at the auction house, so hour-of-day and weekday patterns are sampled at your playtimes. A pattern is shown only with its coverage (scans per hour and weekday), and claimed only where coverage is enough. Weekday effects such as the weekly reset need at least four weeks. Optional sources (STORY-011b) could fill hours you don't scan.
- **Steps** (each needs the one before):
  1. **Scan coverage:** now STORY-026 in Next.
  2. **Timing profile:** per item, and for groups by catalog role (material, intermediate, finished; never inferred from names), price and supply by hour and weekday, with a confidence label. A weekday chart overlays price against supply (units listed, never called demand or volume sold). "Cheapest to buy" and "best to sell" windows only where coverage supports them.
  3. **Daily brief:** STORY-025 (*Today*) is its rule-based first version on the newest scan. This step adds the timing profile's advice: what to buy now or hold, and what to post now or wait on, each with its coverage.
  4. **Plan ahead** (requested 2026-10-05): next-day planning, not only right now.
     - **When to log in:** suggested sessions that combine your usual play times (STORY-026) with the hours the timing profile marks as best to buy or sell, and how much each session is worth on current evidence.
     - **Key times and milestones:** a calendar of known events entered by hand, each with its source (weekly reset, maintenance, holidays, patch days, launch-week phases). Their effect on prices is shown only once enough scans cover them.
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
- **Best use of a material:** for an item such as Linen or Wool Cloth, compare selling it with each craft it feeds, at current prices.
- **Value-add chart** (suggested 2026-10-04): in the recipe explanation, a tier-by-tier waterfall from raw materials through intermediates to the finished item. It shows cost added and the sale value at each tier where it's listed (an unlisted tier shows no value, never zero), so you can see where the margin is made. It draws from the existing `crafting.py` calculation, never a second costing path in SQL. Cross-profession chains wait for STORY-015b.

**Your own character's data** (suggested 2026-10-05; needs a decision because it reads beyond the auction house, though still read-only):
- **Your auctions and sold-auction mail:** real sales and prices for your own listings, the only true sales data available. It would calibrate *Removed listings* (STORY-027).
- **Bags and bank:** what you hold, so Today's *Sell* list includes it and *Buy* skips what you already have.
- **Known recipes and skill:** limits the board to what you can actually craft (compare STORY-015b's list of your professions).

**AI narration** (suggested 2026-10-05; after STORY-025; reads ADDON-10 metrics): a plain-language summary of Today and the item page that explains only defined metrics and rule results, cites every number, and never invents one or recommends without explainable features (*Out of scope*). Needs a decision about which model runs it and what data leaves this machine.

**Addon follow-ups** (any time, none urgent):
- Scan the Roleplaying house once the beta offers it, and a neutral house when reachable, to confirm house identification and the 15% cut market.
- Check whether `/bscan start` works without the button click.

**Recipe coverage** (unblocked by STORY-004):
- **More recipes and professions:** added in the app on the Recipe catalogs page and shown together on the board (`status.md`); routing across professions is STORY-015b.
- **Multi-yield costing:** if an in-game check shows a recipe makes more than 1, build whole crafts, round unit costs up to the copper, and show leftovers without crediting them. Keep the shopping list and the all-craft materials consistent. Until then the calculator can reject such intermediates with "Fractional unit costs" (`requirements.md` → *Not modeled*). **Moves to the top of Next if the Bolt of Linen Cloth check finds a yield above 1.**
- **Skill-up demand map:** from the catalogs' skill levels and quantities, which materials levelling crafters will need at each skill band. A reasoned expectation for stocking up before launch, not a forecast.
- **In-game recipe reader (optional):** the addon could read the Tailoring window (reagents, `GetTradeSkillNumMade`) and the trainer list (required skill) to confirm Wowhead values automatically. This widens the read-only addon and needs its own decision.

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
  - re-checking *Known Forever market facts* in `requirements.md`
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
