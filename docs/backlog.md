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

Nothing in progress; the next story is the top of *Order* under Next: a profession for every empty slot (STORY-099). Regroomed 2026-10-17 (product owner): the web app is complete (STORY-081 to STORY-095, NiceGUI retired in STORY-087), and **beta testing is wrapped**: 31 complete scans and the character captures are the data we build on, with no further in-game test sessions before go-live. The work now is making the app as useful as possible on that data; the launch-day checklist and remaining in-game checks wait until after go-live (*Launch-day checklist* under Later). Team's job is set as *what should each character do next, and is it paying off?* (STORY-097, STORY-099; *Is it paying off?* under Later).

**Scanning:** keep the usual routine (scan, `/reload`, import, then `/bscan clear` and `/reload`) whenever you happen to be at the auction house; nothing else is needed (STORY-026 dropped 2026-10-17).

Launch market remains Forever US, Roleplaying, Alliance (`forever-us-roleplaying-alliance`); the beta source is `forever-us-normal-alliance`. Node.js 24 LTS is installed on the Mac; the Windows PC only plays and drops scans (OPS-03).

## Next

**Agreed order (groomed 2026-10-05):** the app is almost all tables today, so user-facing analysis now gets its own lane in Next instead of waiting behind launch preparation. The layers, each building on the one before:
- **Scans** (exists) → **market metrics** (exists; ADDON-10 in `requirements.md`) → **analysis views** (item page, charts, sellers) and the **Today** page (what to buy, craft and sell now).
- An optional AI narration layer can come later. It may only explain those defined metrics, never invent numbers (*Out of scope*).
- Time-of-day and weekday patterns need weeks of live scans (*Market timing* under Later). Everything in Next works on a single scan or a few, so it can be built and tested on beta scans now.

**Order** (regroomed 2026-10-17, product owner):
1. STORY-099 a profession for every empty slot
2. STORY-062 sales speed and suggested stock levels (refine first)
3. STORY-100 a Market front page worth reading
4. STORY-006 replay (before launch)
5. STORY-101 frozen beta test corpus
6. STORY-102 beta prices as a launch-week reference
7. STORY-011a survey third-party scan sources
8. STORY-028 sellers and supply chains (blocked: see *Seller capture* under Later)

**Web app lane (decided 2026-10-16, product owner; finished 2026-10-17):** the owner approved the clickable prototype in `docs/prototype/web-app.html` as the direction: an app shell, an inspector that opens records in place, and Today as one route. The rules are UI-18 in `requirements.md` and the structure is *Web app (UI-18)* in `design.md`. Page stories compare their 1280/390 px screenshots with the matching prototype view.

**Pending an in-game beta check:** none. STORY-027's time-left bounds were accepted on 2026-10-16; STORY-044, 071 and 077 were confirmed on 2026-10-15; STORY-031, 032, 033 and 040 on 2026-10-13 (`status.md`).

**Done** (outcomes in `status.md` and `requirements.md`; story text in Git): STORY-015b, 021, 025, 030, 031, 032, 033, 034, 034b, 035, 036, 037, 038, 039, 040, 041, 042, 043, 044, 045, 046, 047, 048, 049, 050, 051, 052, 053, 054, 055, 056, 057, 058, 059, 060, 061, 063, 064, 065, 066, 067, 068, 069, 070, 071, 072, 073, 074, 075, 076, 077, 078, 079, 080, 081, 082, 083, 084, 085, 086, 087, 088, 089, 090, 091, 092, 093, 094, 095, 097, 098 and SPIKE-009/009b.

### STORY-099 — A profession for every empty slot

Added 2026-10-17. On the beta Lira, Cicelyna and Raaem end with *Learn a profession to see what's in reach*, while CRAFT-13 already prices every profession for a rank-one hire.

As the owner, I want each character with a free profession slot to get a suggested profession, so that every roster card ends in an action.

Acceptance:
- **Suggestion per free slot:** run CRAFT-13's rank-one comparison for that character (its free primary slots; Cooking, First Aid and Fishing take none) and show the best profession by its existing sort, with best per craft at the window, cost to reach it, and what it would feed for the current team (*What it feeds*). Professions the team already covers are shown, labelled, not hidden.
- **Card and record:** the roster card's action reads *Take up Tailoring: best within 25 points earns X per craft*; the record's Next tab (STORY-097) lists the top three.
- **Honest gaps:** incomplete estimates keep their pill and reasons; no suggestion when every option has no profit, saying why.
- **Offline tests:** free-slot counting with two primaries, one, or only secondaries; ordering matches CRAFT-13; incomplete stays incomplete.
- **Real data:** copied beta, three characters with free slots get a suggestion; report each.
- Depends on STORY-097 (Next tab) and works better after STORY-098. Rules: CRAFT-13, CRAFT-11, *Team character cards*, UI-18. Design: *Team contracts*.

### STORY-062 — Sales speed and suggested stock levels

Added 2026-10-13 (product owner: "turnover, how fast items sell in the market is really kind of the point… I don't know how else you determine how much stock or inventory you keep"). Brownstone only. Needs STORY-027 and enough consecutive scans: refine the minimum before handoff with the beta's 31 complete scans. Draft.

As the owner, I want to see how fast each item moves on the auction house and a suggested stock level from it, so that targets come from evidence instead of guesses.

Acceptance:
- **Removal rate** per item from STORY-027: units removed per hour across consecutive scan pairs within the maximum gap, as a median with the number of scan pairs it rests on. Always *removed*, an upper bound on sales, never *sold*. Too few pairs says so instead of a number.
- **Turnover:** listed units divided by the removal rate (how long today's supply would last), shown beside it.
- **Suggested target** beside Ledger's stock targets (STORY-061): removal rate × the days of cover the owner chooses (one setting), capped at a share of typical listed supply so we never plan to hold more than the market moves. Shown next to the manual target, never replacing it.
- **Shown** on the Market explorer's item page (STORY-055) and beside held stock and targets in Ledger (STORY-061).
- Feeds *Sales speed instead of a fixed cap* (Later) for Today, which stays a separate story.

### STORY-100 — A Market front page worth reading

Added 2026-10-17; merges *One card row per item* and *Market for our levels* from Later. On the copied beta scan `20261017T104157Z-ff991e`, *Dearer than usual* opens with Raw Winter Squid at +4,185.7% (9s against 21c typical, 4 listings) and spends two of three rows on it (*base* and *unresolved*); *Cheaper than usual* does the same with Bright Yellow Shirt. The grid's top rows are thin outliers at the team's levels nobody can use.

As the owner, I want Market's front cards and default list to show items I can act on, so that the page tells me something in a glance.

Acceptance:
- **One row per item** on the front cards: the largest identity, labelled, as UI-09's movement does (decide this in UI-11 and check, per ADDON-08, whether identical base/unresolved rows are the same listings seen twice).
- **Minimum evidence** for *Cheaper* and *Dearer*: a listings and units floor recorded in UI-11 (proposal: at least 5 listings and 10 units); items below it stay in the grid with their thin label.
- **For our levels:** a default filter or ordering by the skill bands the team can reach (Team's window), with *All in our chains* one click away; never inferred from names.
- **Unchanged:** prices, metrics, flood labels and calculations.
- **Offline tests:** one row per item with identities kept separate in data; the floor excludes thin rows from cards only; the level filter uses catalog skill bands.
- **Real data:** copied beta, report the three rows of each card before and after, and the default grid's count. Screenshots at 1280 and 390 px beside the prototype's Market view.
- Depends on nothing. Rules: UI-09, UI-11, ADDON-08, CRAFT-11, UI-18. Design: *Market explorer (STORY-055)*, *Flood signals (STORY-064/072)*, *Web app (UI-18)*.

### STORY-006 — Replay and rebuild local data

As the product owner, I want derived data rebuildable from the raw archive, so that schema changes and validation fixes never strand old scans.

Acceptance:
- **Deterministic rebuild.** One command rebuilds silver and DuckDB from bronze into a fresh database without modifying bronze. Running it twice gives identical results.
- **Every source.** Covers TSM CSVs and addon scans (bronze `.lua` and `.lua.gz` files; silver already holds per-scan listings and prices).
- **Documented.** It's the recovery procedure for partial runs referenced in `status.md`. Backup is STORY-016.
- Groomed 2026-10-17: do before launch, so a schema change after 4 November never strands live scans. Rules: DATA-01, DATA-02, DATA-04. Design: *Data contracts*, *Schema migrations*.

### STORY-101 — Frozen beta test corpus

Added 2026-10-17. Beta testing is wrapped; its data is the only real data we have until live scans build up. Not a backup (STORY-016 stays deferred).

As the owner, I want a frozen copy of the beta data and one command that re-checks its known numbers, so that changes made after the beta closes are still tested against real play.

Acceptance:
- **Corpus:** a dated copy of the current `data/` under ignored `work/`, with a manifest (file count, SHA-256 of every bronze file, scan count, character count, newest scan ID). Never in Git.
- **One command** (`python -m brownstone beta-check <corpus>`, read-only) prints the headline numbers each place shows today: scans and newest scan, Market items and chain count, Today route steps and planned profit, Team characters, Ledger net and reconciled pairs, and compares them with an expected file saved beside the corpus. Differences are listed, not failed silently.
- **Story reviews use it:** `docs/prompts/story-review.md` step 6 names it as the default real-data check once the beta is closed.
- **Offline tests:** the command on a small synthetic corpus; a changed expected value is reported; the corpus is opened read-only.
- Depends on nothing. Rules: DATA-01, OPS-01. Design: *Beta evidence report*, *Quality gates*.

### STORY-102 — Beta prices as a launch-week reference

Added 2026-10-17; replaces STORY-012 (Forever against Classic) under Later. On launch day the live market has no typical prices; the beta's do exist. They are a different market (DATA-03), so they may only be shown, labelled, never used.

As the owner, I want to see an item's beta typical price beside its live price in the first weeks, so that I can tell a bargain or a mispriced listing from noise before live history exists.

Acceptance:
- **Explicit pairing:** in config, a live source names one reference source (the beta). Items pair on full identity inside this view only; the view says *beta reference, a different market*. Nothing from it feeds crafting, Today, the Board, flood labels or any price basis (DATA-03, DATA-08).
- **Shown with care:** the Market item record's Overview and the grid show *beta typical* and the ratio beside the live price, with the beta's newest scan time. Items missing or unpriced on either side say so, never 0.
- **Fades out:** once the live item has its own typical price from enough scans (ADDON-10's threshold), the reference moves behind evidence on demand.
- **Offline tests:** no calculation reads the reference; missing on either side; the switch to evidence once live typical exists.
- **Real data:** pair the beta source with a copy of itself under a test `source_id` to check the wiring; the live check happens after go-live.
- Depends on the live source being configured after go-live (*Launch-day checklist* under Later); buildable now. Rules: DATA-03, DATA-08, ADDON-10, UI-09, UI-18. Design: *Market metrics layer (STORY-024)*, *Market explorer (STORY-055)*.

### STORY-011a — Survey third-party scan sources

Split from STORY-011 at grooming (2026-10-04); ingestion is STORY-011b under Later.

As a gold maker, I want to know whether any trustworthy third-party Forever scan source can be used, so that I can plan around it rather than guess.

Acceptance:
- **Survey and record.** Check AHledger, Booty Bay Broker and TSM for an official export or API and terms that allow personal use. Record the result in `requirements.md`, closing that open decision. No code.
- If a source qualifies, STORY-011b moves to Next.

### STORY-028 — Sellers and their supply chains

As a gold maker, I want to see who supplies each market and which crafting chains they focus on, so that I can choose chains with less competition and expect undercuts.

Acceptance:
- **Per item:** sellers by share of units listed, their prices against the lowest and typical price, and how that changes between scans.
- **Per seller:** what they list, grouped by catalog chain (materials, intermediates and outputs by catalog membership, never names), how much, and how often they repost.
- **Per chain:** how concentrated supply is (the share held by the top sellers), so crowded and open chains are visible.
- **Private:** seller names stay on this machine, as recorded in STORY-023's decision.
- Depends on seller capture, which the beta's bulk scan does not provide (*Seller capture* under Later), and the implemented market metrics layer (ADDON-10).

## Later

**Captured colours: remaining gaps** (found in the STORY-098 review, 2026-10-18): the copied beta has only 26 learned recipes, so captures fill two colour gaps (Smelt Copper, Copper Rod) and no hire or window-25 path becomes complete; starter, training and price evidence still block costs. Four learned recipes contradict their Wowhead colours and await owner review (`python -m brownstone skillups --source forever-us-normal-alliance-addon`). The catalog's `required_skill` 25 for Smelt Copper also looks wrong for Forever (learned and orange at rank 3). `--write` updates only existing picks; a derived intermediate with no pick of its own is listed, not written (adding a pick would make it a selected recipe), so capturing intermediates' colours needs a decision.

**Chosen-route column placement** (found in the STORY-092 review, 2026-10-17): Supply chains places each card at its deepest column across chosen *and* unchosen branches, so an item the chosen route uses directly can be pushed right by an unchosen path that also reaches it, leaving its solid edge to cross an empty column. Lay out columns from the chosen path first and only then place unchosen-only nodes.

**Biggest lever across characters** (found in the STORY-088 review, 2026-10-17): Today's lever card takes the first character whose Level up options include a *Level …* step, read from the option text. With one levelling step on the beta that is right, but with several it is not the team's best. Have UI-12 return a structured best next step (character, profession, cost, unlocked profit per craft) and rank it there, so the web neither parses text nor picks by character order.

**One mailbox stop per holder** (found in the STORY-095 review, 2026-10-17): on the beta Route, Cicelyna and Baspion each get two mailbox stops, one for material mail and a later one for gold mail, and gold mail still reads *Cicelyna mails 8s 87c to Arille* rather than STORY-095's *Cicelyna: mail …*. Fold gold mail into the holder's material mailbox stop and share the wording.

**Route and Ledger tidy-up** (groomed 2026-10-17; with *Biggest lever across characters* and *One mailbox stop per holder* above): the beta Route opens with five mailbox steps that each repeat *postage is unconfirmed*; show that note once. Ledger's gold reconciliation lists 61 pairs, nearly all 0c actual, 0c recorded, 0c unexplained; show pairs with an unexplained amount by default and the rest on demand. Also check why the beta Route plans *Craft 5 × Linen Bag · needs 45 · you're 32* for Basilly: whether earlier crafts in that step reach 45 or the plan schedules a recipe the character can't make yet.

**Holdings as item rows** (found in the STORY-097 review, 2026-10-17): the character record's Holdings tab shows each stack as a run-on text line (*Shiny Red Apple · 16 units · 49c / unit · 7s 84c total · sell*), where the prototype's *Bags and bank* uses item rows with the count on the right. Lay stacks out as rows (item, units, unit value, total, action) so 17 stacks scan at 390 px.

**Is it paying off?** (groomed 2026-10-17; the second half of Team's job): profit by activity (crafting, farming, vendoring, auction) per character, in total and per hour played, from the gold ledger (UI-15), item movements (UI-16), farming rates (UI-13) and journal session times. Shown in the character record and as a Team summary. Needs a rule for attributing a crafted sale's profit to the crafting activity and for what counts as time played.

**Lots and cost basis** (deferred from STORY-034 on 2026-10-15): which purchase each sold or crafted unit came from, for realised profit. Needs STORY-034b's item movements and a rule for held stock of unknown cost.

**Launch-day checklist** (STORY-020a and STORY-020b merged and moved to Later on 2026-10-17, product owner: no rehearsal; when it launches, it launches. Write it when go-live is near or after it):

As a gold maker, I want a short, tested checklist for 4 November, so that the switch to the live game is quick and nothing is missed.

Acceptance:
- **A short checklist** in `docs/`, linked from `status.md`, with: install or update the addon and check that it loads (the `.toc` interface number may change), first scan, `/reload`, import, clear; and
  - a copy of `data/` before and after (a dated folder copy until STORY-016 is picked up)
  - adding and enabling the live Roleplaying Alliance source in `config/market.local.toml`, with its own `source_id`, `environment = "live"`, the live game folder's `scan_path` and its `rules_version` (DATA-03)
  - re-saving each Forever Wowhead page and regenerating. If the live `rules_version` differs from the beta's, every Forever catalog stays inspection-only until regenerated (*Refresh due* flags it).
  - re-checking the confirmed and unconfirmed facts under *Product direction* in `requirements.md`
  - turning on STORY-102's beta reference for the live source
- **Checked** on data copies where it can be; live-house checks happen at launch.
- **Post-launch in-game checks** that the beta left open: the sale-to-mailbox delay, crafting tier levels and yellow skill-up chances (`status.md` → *Limitations*).
- Rules: OPS-01, DATA-03, CRAFT-01, CRAFT-08. Design: *Switching to WoW Forever*.

**Optional client-version cutover guard:** investigate whether recorded client versions can flag a misconfigured beta/live source during the launch-day checklist and first live imports. Source configuration remains authoritative (DATA-03); STORY-017 adds no client-version evidence checks.

These are grouped by what unblocks them.

**Black Market vendor** (moved from STORY-036 on 2026-10-15; check during live, once the owner reaches it): whether it exists, where, and its prices (claimed in `requirements.md` → *Product direction*). If it does, open it with the addon; STORY-036's rules then mark its unlimited items.

**Seller capture** (found 2026-10-06; blocks STORY-028): the Forever beta's bulk scan returns no seller names (ADDON-07). Left blocked until after go-live (product owner, 2026-10-06): check whether live scans return seller names. Only if they don't, decide between another read-only way of getting them (such as per-item searches, at the cost of many more auction-house requests and a longer scan) and dropping or reshaping STORY-028.

**Snapshot coverage** (added 2026-10-07; needs a character with more bags and bank slots, possibly after go-live): STORY-032's checks that a new beta character can't reach. Every equipped bag slot full; several bank bags, including the last bank bag slot; the keyring and any reagent containers the client has; a full bank compared item by item; and bank-close reads with many bags open. Play those actions, then Claude checks the client's `container_layout` values in the dropped file. Until then, container coverage is confirmed only for the containers actually tested.

**Today, later versions** (captured 2026-10-06 with the product owner; each extends STORY-025 once its data exists):
- **Sales speed instead of a fixed cap:** replace *most crafts per item* with how many units of the output disappear between scans. Needs STORY-027 and a few weeks of live scans; label it removed, not sold.
- **Stockpile:** materials below their own multi-day typical price, worth buying ahead for recipes you craft often, with a holding limit tied to gold available. Needs price history across days (*History chain*), so after launch.
- **Volatility:** how much an item's typical price swings across scans, shown as a risk note and used to demote unstable crafts. Needs the same history.
- **Restock:** moved to Next on 2026-10-13 as STORY-068.
- **Mailbox holdings** (split from STORY-068, 2026-10-14): count items in each character's last captured inbox (the journal's `MAIL_SHOW`/`MAIL_INBOX_UPDATE` state) as held after bags and bank, with *take from the mailbox* in the Queue. Needs a rule against counting an item twice when it was taken into bags after the inbox was read.
- **Reach cost from holdings** (split from STORY-068): CRAFT-11's cost to reach a skill uses holdings first and walks the listing ladder for the whole quantity (80 Linen Cloth costs more than 80 × the cheapest), as Today does.
- **Routes that use holdings** (split from STORY-068): choose a different route because of what is held (craft bolts from held Linen Cloth when the Board's route buys bolts). STORY-068 only uses holdings along the Board's route.
- **Whole chains:** ore → bars → armor across professions, with the gain at each stage (sell bars or craft on). Routing exists (CRAFT-12).
- **Gold per hour:** if the scaled minimum gain feels wrong in play, try a time-based minimum instead. Decide after using version 1.

**Demand from your own scans** (needs repeated scans and STORY-018; optional sources from STORY-011b can add more data points):
- *Removed listings* (STORY-027) is implemented; its Forever time-left bounds were accepted on 2026-10-16.
- **Did the board hold up?** Whether "potential craft" rows were still profitable at the next scan. Possible now on the 31 beta scans (groomed 2026-10-17) as a measured basis for Today's confidence labels; it means more after one to two weeks of live scans.

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
- **Plain identity labels** (walkthrough 2026-10-13): *base* and *unresolved* tags, and items listed twice under each, mean nothing to a player. Say *variant* or *unidentified link* only where it matters, keeping identities separate (ADDON-08).
- **Shorter removal history** (walkthrough 2026-10-13): an item page lists every scan gap, mostly zeros. Summarise (removed early and could-have-expired totals over the comparable gaps), with each gap on demand.
- **Vendor value as a floor** (2026-10-14, from CraftProfit's *vendor net* and TSM's posting rules): for leveling crafts whose auction market is flooded, show what the output fetches from a vendor (vendor sell price × output − cost) beside the auction profit. *Sell* never suggests a post price at or below the vendor price ÷ (1 − cut); it says *vendor it instead*.
- **Buy a pattern to level cheaper** (2026-10-14, from ProfessionMaster): when a recipe item listed on the auction house would make a CRAFT-11 reach path cheaper including its price, show it as an option. Today such recipes are excluded as *needs pattern or other source*.
- **Green recipes when much cheaper** (2026-10-14, from ProfessionMaster): allow a green recipe in a reach path only when every orange and yellow option costs more than twice as much per point, labelled as uncertain.
- **Mail and auction expiry warnings** (2026-10-14, from TSM's task list): items or gold in a captured mailbox close to its 30-day expiry, and your auctions about to end.
- **Best use of a material:** for an item such as Linen or Wool Cloth, compare selling it with each craft it feeds, at current prices.
- **Value-add chart** (suggested 2026-10-04): in the recipe explanation, a tier-by-tier waterfall from raw materials through intermediates to the finished item. It shows cost added and the sale value at each tier where it's listed (an unlisted tier shows no value, never zero), so you can see where the margin is made. It draws from the existing `crafting.py` calculation, never a second costing path in SQL. Cross-profession chains wait for STORY-015b.

**Your own character's data** (approved 2026-10-06; capture is STORY-032/033 and the gold ledger STORY-034, all done). Once those exist:
- **Known recipes and skill:** moved to Next on 2026-10-07 as STORY-041 (capture) and STORY-043 (Today); 2026-10-09 added STORY-049 (Forever capture), STORY-051 (Characters) and STORY-052 (progression; *what can I learn next*). Still here: the Action Board filtered to what you can make.
- **Profession page** (added 2026-10-09, product owner): drill into one profession: every catalog recipe by skill band, with each character's status (known, train now, not yet), how it's learned, profit from the newest scan and its materials; linking to the item page (STORY-021). Builds on STORY-043, STORY-050 and STORY-052.
- **Calibrate removed listings:** your own sales from invoices show how many *removed* listings (STORY-027) were real sales.

**Ledger analytics** (from the 2026-10-06 design notes; each needs STORY-034 and some weeks of your own sales):
- **Sell-through and fill chance:** for each of your posts, its premium over the lowest price at posting, and whether and when it sold, and at which duration (to recommend STORY-035's post duration). Start with simple buckets (how often posts at 0–5%, 5–15% … above the lowest sold within their duration); more refined models only once there is enough data.
- **Gold per minute of auction time:** expected profit net of the auction cut and expected deposit losses, per minute you spend at the auction house. Replaces *Gold per hour* under *Today, later versions* if the scaled minimum gain feels wrong.
- **Cost basis:** lots per item (gathered, bought, crafted, vendor), first in first out. Two values per lot: what you paid (zero for gathered), for *what did I actually make?*; and what it would sell for now (depth-aware, after the cut, capped at any vendor price), for *craft it or sell it raw?*. Farming judged separately from trading, as gold per hour.
- **Capital view:** gold across all characters, holdings at market value, gold tied up in listings and mail, and net worth. A **reserve** you set (mount, training, spending) is kept back; Today's *Gold available* could then default to cash minus reserve instead of being typed in.
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
