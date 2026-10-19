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

Nothing in progress; the next story is the top of *Order* under Next. **Regroomed 2026-10-18 (product owner): live starts fresh.** On 4 November the live source begins in an empty `data/` and the beta folder is archived read-only (`requirements.md` → *Product direction*); the live market will differ, so nothing relies on beta prices. The beta data stays in use for building and checking stories until it is archived just before go-live. **Launch plan:** for the first one to two weeks the owner levels characters and scans to build a baseline, rather than trading in a volatile market; trading starts once the app has that history. Next carries Today's money-makers and Team and polish work; launch-week market ideas wait under Later (*Launch week, from the first scan*). Earlier, regroomed 2026-10-17 (product owner): the web app is complete (STORY-081 to STORY-095, NiceGUI retired in STORY-087), and **beta testing is wrapped**: 31 complete scans and the character captures are the data we build on, with no further in-game test sessions before go-live. The work now is making the app as useful as possible on that data; the launch-day checklist and remaining in-game checks wait until after go-live (*Launch-day checklist* under Later). Team's job is set as *what should each character do next, and is it paying off?* (STORY-097, STORY-099; *Is it paying off?* under Later).

**Scanning:** keep the usual routine (scan, `/reload`, import, then `/bscan clear` and `/reload`) whenever you happen to be at the auction house; nothing else is needed (STORY-026 dropped 2026-10-17).

Launch market remains Forever US, Roleplaying, Alliance (`forever-us-roleplaying-alliance`); the beta source is `forever-us-normal-alliance`. Node.js 24 LTS is installed on the Mac; the Windows PC only plays and drops scans (OPS-03).

## Next

**Agreed order (groomed 2026-10-05):** the app is almost all tables today, so user-facing analysis now gets its own lane in Next instead of waiting behind launch preparation. The layers, each building on the one before:
- **Scans** (exists) → **market metrics** (exists; ADDON-10 in `requirements.md`) → **analysis views** (item page, charts, sellers) and the **Today** page (what to buy, craft and sell now).
- An optional AI narration layer can come later. It may only explain those defined metrics, never invent numbers (*Out of scope*).
- Time-of-day and weekday patterns need weeks of live scans (*Market timing* under Later). Everything in Next works on a single scan or a few, so it can be built and tested on beta scans now.

**Order** (regroomed 2026-10-18, product owner: levelling characters and professions comes first, since the first weeks after launch are for levelling and scanning, not trading):
1. STORY-105 sell raw or craft?
2. STORY-106 gold reserve and capital
3. STORY-109 Route and Ledger tidy-up
4. STORY-110 records polish

**Web app lane (decided 2026-10-16, product owner; finished 2026-10-17):** the owner approved the clickable prototype in `docs/prototype/web-app.html` as the direction: an app shell, an inspector that opens records in place, and Today as one route. The rules are UI-18 in `requirements.md` and the structure is *Web app (UI-18)* in `design.md`. Page stories compare their 1280/390 px screenshots with the matching prototype view.

**Pending an in-game beta check:** none. STORY-027's time-left bounds were accepted on 2026-10-16; STORY-044, 071 and 077 were confirmed on 2026-10-15; STORY-031, 032, 033 and 040 on 2026-10-13 (`status.md`).

**Done** (outcomes in `status.md` and `requirements.md`; story text in Git): STORY-006, 015b, 021, 025, 030, 031, 032, 033, 034, 034b, 035, 036, 037, 038, 039, 040, 041, 042, 043, 044, 045, 046, 047, 048, 049, 050, 051, 052, 053, 054, 055, 056, 057, 058, 059, 060, 061, 062, 063, 064, 065, 066, 067, 068, 069, 070, 071, 072, 073, 074, 075, 076, 077, 078, 079, 080, 081, 082, 083, 084, 085, 086, 087, 088, 089, 090, 091, 092, 093, 094, 095, 097, 098, 099, 100, 101, 102, 103, 104, 107, 108, 111, 112 and SPIKE-009/009b.

### STORY-105 — Sell raw or craft?

Moved from *App conveniences* (*Best use of a material*) on 2026-10-18 (grooming). The most common launch-week decision is whether to sell gathered cloth, ore or herbs or craft them on.

As a gold maker, I want each material compared across selling, vendoring and every craft it feeds, per unit, so that I know its best use at current prices.

Decisions:
- **Per unit of the material:** auction net = `today.undercut_price` on the newest lowest, after the cut; vendor value as in STORY-104; for each compatible catalog recipe using it with a Board row, **craft value** = (the Board's cautious net sale per craft − the Board's cost of the other inputs per craft) ÷ this material's quantity per craft (`crafting.evaluate_recipe`, the same costing as the Board, never a second path). Integer copper, rounded down.
- **Who can craft it:** CRAFT-11 Known/Train now per scoped character; recipes no one can make stay listed and labelled *nobody on the team knows it*.
- Any missing price makes that option unknown with its reason, never 0. Rank known values highest first.
- **Where:** the item record's *Made from and used in* tab leads with *Best use of one unit*; the character record's Holdings action names the best known option (*craft into Bolt of Linen Cloth · +4c a unit over selling*). Today's plan is unchanged.

Acceptance:
- **Compared:** selling, vendoring and each craft per unit, with who can make it, for any item with a consuming recipe.
- **Honest:** unknowns say why; listings are not sales; values come from the newest scan.
- **Offline tests:** craft value with one and several other inputs, an intermediate route, missing prices on each side, quantity above 1, eligibility labels, and Today unchanged.
- **Real data** (copy of `data/`): Linen Cloth (2589) per-unit sell, vendor and Bolt of Linen Cloth values on the beta.
- Depends on STORY-104. Rules: CRAFT-03, CRAFT-04, CRAFT-05, CRAFT-11, UI-09, ADDON-08. Design: *Crafting calculation*, *Market explorer (STORY-055)*, *Team contracts*.

### STORY-106 — Gold reserve and capital

Moved from *Ledger analytics* (*Capital view*) on 2026-10-18 (grooming). At launch gold is the bottleneck, and training and the mount must not be spent on crafts.

As a gold maker, I want to keep a reserve out of Today's budget and see what the company is worth, so that plans never spend money I've set aside.

Decisions:
- **Reserve:** Today settings gain `reserve_copper` (per-source file, `today_settings.py`, default 0). `today_funds.resolve_funds` plans with the captured total minus the reserve, floored at 0, labelled *captured X − reserve Y*. The entered-amount override is unchanged and ignores the reserve.
- **Capital** on Team: captured gold per character plus bags and bank at value (`team_view` holdings `value_copper`), as **at least** where captures are partial or prices unknown. Active auctions (`journal.active_auction_rows` has counts only) and mailboxes are listed as *not valued*, with their counts.
- Bump `today_version` if the Today section requires it.

Acceptance:
- **Reserve:** Today never plans more than captured gold minus the reserve; a reserve above captured gold plans with 0 and says so.
- **Capital:** Team shows gold, holdings value and their total, with what is not valued.
- **Offline tests:** reserve below, equal to and above captured gold; the override; partial captures giving *at least*; unknown prices excluded and counted.
- Depends on nothing. Rules: *Today (today_version 11)* funds, *Team character cards*, UI-15. Design: *Today contracts*, *Team contracts*, *Stock contracts*.

### STORY-109 — Route and Ledger tidy-up

Merges *One mailbox stop per holder* and *Route and Ledger tidy-up* from Later (2026-10-18 grooming).

As a gold maker, I want a Route without repeated stops and notes and a Ledger that leads with what needs attention, so that I can follow them quickly at the mailbox.

Acceptance:
- **One mailbox stop per holder:** gold mail joins the holder's material mailbox stop and uses STORY-095's *Cicelyna: mail …* wording.
- **Postage note once:** *postage is unconfirmed* appears once per Route, not on every mailbox step.
- **Ledger:** gold reconciliation shows pairs with an unexplained amount by default; the rest are on demand with their count.
- **Linen Bag check:** explain why the beta Route plans *Craft 5 × Linen Bag · needs 45 · you're 32* for Basilly, and fix the plan if it schedules a recipe the character can't make yet.
- **Offline tests:** stop merging with material and gold mail, gold-only and material-only holders, the single note, the default filter and its count, and the skill check.
- **Real data** (copy of `data/`): beta Route stop count before and after; Ledger pairs shown by default.
- Depends on nothing. Rules: UI-12, UI-15, *Today (today_version 11)*. Design: *This session (STORY-063)*, *Gold ledger contracts*.

### STORY-110 — Records polish

Merges *Holdings as item rows*, *Chosen-route column placement*, *Plain identity labels* and *Shorter removal history* from Later (2026-10-18 grooming).

As a gold maker, I want records that scan at a glance on the Mac and phone, so that I spend less time reading them.

Acceptance:
- **Holdings as rows:** the character record's *Bags and bank* lays each stack out as a row (item, units, unit value, total, action), readable at 390 px.
- **Chosen route first:** Supply chains places columns from the chosen path first, then unchosen-only nodes, so no chosen edge crosses an empty column.
- **Plain identity labels:** *base* and *unresolved* read as *variant* or *unidentified link* only where an item has more than one identity; identities stay separate (ADDON-08).
- **Shorter removal history:** the item page summarises removed-early and could-have-expired totals over comparable gaps, with each gap on demand.
- **Offline tests:** Vitest for each; layout ordering for chosen and unchosen paths; identity labels with one and several identities.
- Compare 1280 and 390 px screenshots with the prototype (UI-18).
- Depends on nothing. Rules: UI-18, ADDON-08, UI-10, UI-16. Design: *Web app (UI-18)*, *Team recipe graph (STORY-015b)*, *Removed listings (STORY-027)*.

## Later

**Captured colours: remaining gaps** (found in the STORY-098 review, 2026-10-18; revisit with live captures after go-live): the copied beta has only 26 learned recipes, so captures fill two colour gaps (Smelt Copper, Copper Rod) and no hire or window-25 path becomes complete; starter, training and price evidence still block costs. Four learned recipes contradict their Wowhead colours and await owner review (`python -m brownstone skillups --source forever-us-normal-alliance-addon`). The catalog's `required_skill` 25 for Smelt Copper also looks wrong for Forever (learned and orange at rank 3). `--write` updates only existing picks; a derived intermediate with no pick of its own is listed, not written (adding a pick would make it a selected recipe), so capturing intermediates' colours needs a decision.

**Holdings can raise a reach cost** (found in the STORY-112 review, 2026-10-19; needs a product decision): the per-point cash-greedy walk (CRAFT-11 *Reach from holdings*) does not guarantee the cheapest window. On the copied beta, Basilly's Tailoring 32→57 costs 1,559c with holdings and 1,514c without: both still buy the same whole 81-unit Linen listing (1,215c), and holdings steer early points to recipes that add 50c training. Options: compare the walk with and without holdings and show the cheaper, or look ahead before spending held stock. The Team, character and Today pages all show the greedy figure today.

**Is it paying off?** (groomed 2026-10-17; the second half of Team's job): profit by activity (crafting, farming, vendoring, auction) per character, in total and per hour played, from the gold ledger (UI-15), item movements (UI-16), farming rates (UI-13) and journal session times. Shown in the character record and as a Team summary. Needs a rule for attributing a crafted sale's profit to the crafting activity and for what counts as time played.

**Farming routes with a node addon** (idea from the product owner, 2026-10-19; not scheduled, after go-live): when STORY-112 says *or farm ≈ H h*, help pick where and how. A node addon such as Gatherer shows ore and herb nodes on the map and minimap; our farming capture (UI-13, STORY-074/075) already records what each loot window gave, when, and a map-percent position cell. Together they could rank spots and routes by measured value per hour, e.g. *Copper Ore: 3 cells in Elwynn, about N nodes per hour on your own runs*, and show how a route's real yield compares with its node count.
- **First, check:** whether Gatherer (or an alternative) loads on Forever, and whether its SavedVariables hold node positions we can read as data. Gatherer comes from the Auctioneer authors, so treat it like Auctioneer: ideas only, no code, until its licence is checked (AGENTS.md).
- **Our side stays read-only:** the app reads both files; it draws nothing in game. Map or minimap display stays with the node addon, since BrownstoneScan only reads (SPIKE-008).
- **Honest limits:** rates are the owner's own past runs, not a promise; launch respawn competition differs from beta; cells are coarse (`farming_cell_percent`), so *route* means an ordered set of cells, not a path. Needs enough gathering stretches per spot after launch.

**Lots and cost basis** (deferred from STORY-034 on 2026-10-15): which purchase each sold or crafted unit came from, for realised profit. Needs STORY-034b's item movements and a rule for held stock of unknown cost.

**Launch-day checklist** (STORY-020a and STORY-020b merged and moved to Later on 2026-10-17, product owner: no rehearsal; when it launches, it launches. Write it when go-live is near or after it):

As a gold maker, I want a short, tested checklist for 4 November, so that the switch to the live game is quick and nothing is missed.

Acceptance:
- **A short checklist** in `docs/`, linked from `status.md`, with: install or update the addon and check that it loads (the `.toc` interface number may change), first scan, `/reload`, import, clear; and
  - a copy of `data/` before and after (a dated folder copy until STORY-016 is picked up)
  - adding and enabling the live Roleplaying Alliance source in `config/market.local.toml`, with its own `source_id`, `environment = "live"`, the live game folder's `scan_path` and its `rules_version` (DATA-03)
  - re-saving each Forever Wowhead page and regenerating. If the live `rules_version` differs from the beta's, every Forever catalog stays inspection-only until regenerated (*Refresh due* flags it).
  - re-checking the confirmed and unconfirmed facts under *Product direction* in `requirements.md`
  - **fresh start** (decided 2026-10-18): stop the app, move the beta `data/` to a dated read-only archive folder, start with an empty `data/`, and enable only the live source (the Classic and Retail stand-ins go with the archive). `work/beta-corpus/` keeps the corpus check working.
- **Checked** on data copies where it can be; live-house checks happen at launch.
- **Post-launch in-game checks** that the beta left open: the sale-to-mailbox delay, crafting tier levels and yellow skill-up chances (`status.md` → *Limitations*).
- Rules: OPS-01, DATA-03, CRAFT-01, CRAFT-08. Design: *Switching to WoW Forever*.

**Launch week, from the first scan** (ideas from the 2026-10-18 grooming, not scheduled). With a fresh start, UI-11's typical needs three priced UTC days, so cheap/high flags, overshoots and Today's confidence have no basis on 4 to 6 November, and removal speed needs scan gaps. These would make the first week useful:
- **Cold-start states:** every page says what it is waiting for (*typical needs 3 priced days, 1 so far*; *removal speed needs scan gaps*) and Today still plans from one scan; tested offline at 0, 1, 2 and 3 days of scans. M.
- **Evidence unlock strip:** one line on Market and Today: *live since 4 Nov · 6 scans over 2 days · price signals unlock tomorrow*. S.
- **Full-house load test:** a synthetic scan 5 to 10 times the beta's size, proving import, the Market grid and Today stay fast. A code test, not an in-game rehearsal. M.
- **First seen:** items listed for the first time in the newest scan, grouped by catalog skill band, so a new levelling wave (Iron Ore appearing) is visible. Works from the second scan. S.
- **Since-launch trend:** per item, first-seen price, lowest so far and change across scans, to answer *sell now or wait?* before a typical exists. Descriptive, never a forecast. M.
- **Scarcity board:** catalog materials and outputs with no or very few listings that the team can gather or craft, to be first to market. M.
- **Market price index:** a basket of catalog materials over time showing whether the market is still cooling. M.
- **Launch-premium sells:** rank held items by how far today's price sits above the since-launch low. Needs *Since-launch trend*. S.

**Optional client-version cutover guard:** investigate whether recorded client versions can flag a misconfigured beta/live source during the launch-day checklist and first live imports. Source configuration remains authoritative (DATA-03); STORY-017 adds no client-version evidence checks.

These are grouped by what unblocks them.

**Black Market vendor** (moved from STORY-036 on 2026-10-15; check during live, once the owner reaches it): whether it exists, where, and its prices (claimed in `requirements.md` → *Product direction*). If it does, open it with the addon; STORY-036's rules then mark its unlimited items.

**STORY-011a — Survey third-party scan sources** (moved to Later on 2026-10-18: player-fed sites carry Forever data only after launch; survey in the first live week): check AHledger, Booty Bay Broker and TSM for an official export or API and terms that allow personal use, and record the result in `requirements.md`, closing that open decision. No code. If a source qualifies, STORY-011b moves to Next.

**STORY-028 — Sellers and their supply chains** (moved to Later on 2026-10-18; blocked by *Seller capture* below): as a gold maker, I want to see who supplies each market and which crafting chains they focus on, so that I can choose chains with less competition and expect undercuts.
- **Per item:** sellers by share of units listed, their prices against the lowest and typical price, and how that changes between scans.
- **Per seller:** what they list, grouped by catalog chain (materials, intermediates and outputs by catalog membership, never names), how much, and how often they repost.
- **Per chain:** how concentrated supply is (the share held by the top sellers), so crowded and open chains are visible.
- **Private:** seller names stay on this machine, as recorded in STORY-023's decision. Depends on the market metrics layer (ADDON-10).

**Seller capture** (found 2026-10-06; blocks STORY-028): the Forever beta's bulk scan returns no seller names (ADDON-07). Left blocked until after go-live (product owner, 2026-10-06): check whether live scans return seller names. Only if they don't, decide between another read-only way of getting them (such as per-item searches, at the cost of many more auction-house requests and a longer scan) and dropping or reshaping STORY-028.

**Snapshot coverage** (added 2026-10-07; needs a character with more bags and bank slots, possibly after go-live): STORY-032's checks that a new beta character can't reach. Every equipped bag slot full; several bank bags, including the last bank bag slot; the keyring and any reagent containers the client has; a full bank compared item by item; and bank-close reads with many bags open. Play those actions, then Claude checks the client's `container_layout` values in the dropped file. Until then, container coverage is confirmed only for the containers actually tested.

**Today, later versions** (captured 2026-10-06 with the product owner; each extends STORY-025 once its data exists):
- **Sales speed instead of a fixed cap:** replace *most crafts per item* with how many units of the output disappear between scans. Needs STORY-027 and a few weeks of live scans; label it removed, not sold.
- **Stockpile:** materials below their own multi-day typical price, worth buying ahead for recipes you craft often, with a holding limit tied to gold available. Needs price history across days (*History chain*), so after launch.
- **Volatility:** how much an item's typical price swings across scans, shown as a risk note and used to demote unstable crafts. Needs the same history.
- **Restock:** moved to Next on 2026-10-13 as STORY-068.
- **Mailbox holdings** (split from STORY-068, 2026-10-14): count items in each character's last captured inbox (the journal's `MAIL_SHOW`/`MAIL_INBOX_UPDATE` state) as held after bags and bank, with *take from the mailbox* in the Queue. Needs a rule against counting an item twice when it was taken into bags after the inbox was read.
- **Reach cost from holdings:** moved to Next on 2026-10-18 as STORY-112.
- **Routes that use holdings** (split from STORY-068): choose a different route because of what is held (craft bolts from held Linen Cloth when the Board's route buys bolts). STORY-068 only uses holdings along the Board's route.
- **Whole chains:** ore → bars → armor across professions, with the gain at each stage (sell bars or craft on). Routing exists (CRAFT-12).
- **Gold per hour:** if the scaled minimum gain feels wrong in play, try a time-based minimum instead. Decide after using version 1.

**Demand from your own scans** (needs repeated scans and STORY-018; optional sources from STORY-011b can add more data points):
- *Removed listings* (STORY-027) is implemented; its Forever time-left bounds were accepted on 2026-10-16.
- **Did the board hold up?** Whether "potential craft" rows were still profitable at the next scan. A measured basis for Today's confidence labels; with the fresh start (2026-10-18) it waits for one to two weeks of live scans.

**Market timing and a daily brief** (requested 2026-10-04; needs post-launch history, not beta scans (STORY-017)). The goal is to know when to buy and sell each kind of item (materials, crafted goods, equipment), and to open the app to a short list of the day's priorities without being online all day.
- **Honest limits:** scans happen only when you are at the auction house, so hour-of-day and weekday patterns are sampled at your playtimes. A pattern is shown only with its coverage (scans per hour and weekday), and claimed only where coverage is enough. Weekday effects such as the weekly reset need at least four weeks. Optional sources (STORY-011b) could fill hours you don't scan.
- **Steps** (each needs the one before):
  1. **Scan coverage:** dropped as a story (2026-10-17: the owner scans when playing, not at other times). Each timing pattern shows how many scans per hour and weekday it rests on instead.
  2. **Timing profile:** per item, and for groups by catalog role (material, intermediate, finished; never inferred from names), price and supply by hour and weekday, with a confidence label. A weekday chart overlays price against supply (units listed, never called demand or volume sold). "Cheapest to buy" and "best to sell" windows only where coverage supports them.
  3. **Daily brief:** STORY-025 (*Today*) is its rule-based first version on the newest scan. This step adds the timing profile's advice: what to buy now or hold, and what to post now or wait on, each with its coverage.
  4. **Plan ahead** (requested 2026-10-05): next-day planning, not only right now.
     - **When to log in:** suggested sessions that combine your usual play times (from scan times) with the hours the timing profile marks as best to buy or sell, and how much each session is worth on current evidence.
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

**STORY-011b — Third-party scan ingestion** (only if STORY-011a finds a qualifying source):
- **Separate source.** A qualifying feed is ingested as its own source for the same market, with raw preservation and provenance like every other source.
- **Visible and optional.** The board shows which source each price came from. Disabling the source leaves everything working on your own scans.
- **Cross-check.** Where both sources cover an item, show how far apart they are, as a data-quality signal.

**App conveniences** (moved from STORY-014 at grooming, 2026-10-04):
- **Find the scan file:** on a click, offer the SavedVariables files under the usual WoW install folders, one per account, and save the choice as `scan_path` in the untracked `config/market.local.toml`. Your path is already set, so this only helps a new machine or account.
- **In-game confirmations:** tick off values checked in game (a yield, a vendor and its price, a post-launch decision) with a date, written to the selection file, then Regenerate. For now there are only a few, edited by hand.
- **Browse filters:** items used or made by any catalog (membership, not names) and a minimum listing count.
- **Buy a pattern to level cheaper** (2026-10-14, from ProfessionMaster): when a recipe item listed on the auction house would make a CRAFT-11 reach path cheaper including its price, show it as an option. Today such recipes are excluded as *needs pattern or other source*.
- **Green recipes when much cheaper** (2026-10-14, from ProfessionMaster): allow a green recipe in a reach path only when every orange and yellow option costs more than twice as much per point, labelled as uncertain.
- **Mail and auction expiry warnings** (2026-10-14, from TSM's task list): items or gold in a captured mailbox close to its 30-day expiry, and your auctions about to end.
- **Value-add chart** (suggested 2026-10-04): in the recipe explanation, a tier-by-tier waterfall from raw materials through intermediates to the finished item. It shows cost added and the sale value at each tier where it's listed (an unlisted tier shows no value, never zero), so you can see where the margin is made. It draws from the existing `crafting.py` calculation, never a second costing path in SQL. Cross-profession chains wait for STORY-015b.

**Your own character's data** (approved 2026-10-06; capture is STORY-032/033 and the gold ledger STORY-034, all done). Once those exist:
- **Known recipes and skill:** moved to Next on 2026-10-07 as STORY-041 (capture) and STORY-043 (Today); 2026-10-09 added STORY-049 (Forever capture), STORY-051 (Characters) and STORY-052 (progression; *what can I learn next*). Still here: the Action Board filtered to what you can make.
- **Calibrate removed listings:** your own sales from invoices show how many *removed* listings (STORY-027) were real sales.

**Ledger analytics** (from the 2026-10-06 design notes; each needs STORY-034 and some weeks of your own sales):
- **Sell-through and fill chance:** for each of your posts, its premium over the lowest price at posting, and whether and when it sold, and at which duration (to recommend STORY-035's post duration). Start with simple buckets (how often posts at 0–5%, 5–15% … above the lowest sold within their duration); more refined models only once there is enough data.
- **Gold per minute of auction time:** expected profit net of the auction cut and expected deposit losses, per minute you spend at the auction house. Replaces *Gold per hour* under *Today, later versions* if the scaled minimum gain feels wrong.
- **Cost basis:** lots per item (gathered, bought, crafted, vendor), first in first out. Two values per lot: what you paid (zero for gathered), for *what did I actually make?*; and what it would sell for now (depth-aware, after the cut, capped at any vendor price), for *craft it or sell it raw?*. Farming judged separately from trading, as gold per hour.
- **Capital view, the rest:** STORY-106 covers gold, holdings and the reserve; still to do is valuing gold tied up in listings and mail, which needs active auctions projected item by item (the journal keeps counts only).
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
