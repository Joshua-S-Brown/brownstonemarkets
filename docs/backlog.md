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

Nothing in progress; the next story is the top of *Order* under Next. **Regroomed 2026-10-18 (product owner): live starts fresh.** On 4 November the live source begins in an empty `data/` and the beta folder is archived read-only (`requirements.md` → *Product direction*); the live market will differ, so nothing relies on beta prices. The beta data stays in use for building and checking stories until it is archived just before go-live. **Launch plan:** for the first one to two weeks the owner levels characters and scans to build a baseline, rather than trading in a volatile market; trading starts once the app has that history. Next carries Today's money-makers and Team and polish work; launch-week market ideas wait under Later (*Launch week, from the first scan*). **Beta testing is wrapped** (2026-10-17): 31 complete scans and the character captures are the data we build on, with no further in-game sessions before go-live; the launch-day checklist is STORY-114 and remaining in-game checks wait until after go-live. Team's job is set as *what should each character do next, and is it paying off?* (STORY-097, STORY-099; *Is it paying off?* under Later).

**Scanning:** keep the usual routine (scan, `/reload`, import, then `/bscan clear` and `/reload`) whenever you happen to be at the auction house; nothing else is needed (STORY-026 dropped 2026-10-17).

Launch market remains Forever US, Roleplaying, Alliance (`forever-us-roleplaying-alliance`); the beta source is `forever-us-normal-alliance`. Node.js 24 LTS is installed on the Mac; the Windows PC only plays and drops scans (OPS-03).

## Next

**Agreed order (groomed 2026-10-05):** the app is almost all tables today, so user-facing analysis now gets its own lane in Next instead of waiting behind launch preparation. The layers, each building on the one before:
- **Scans** (exists) → **market metrics** (exists; ADDON-10 in `requirements.md`) → **analysis views** (item page, charts, sellers) and the **Today** page (what to buy, craft and sell now).
- An optional AI narration layer can come later. It may only explain those defined metrics, never invent numbers (*Out of scope*).
- Time-of-day and weekday patterns need weeks of live scans (*Market timing* under Later). Everything in Next works on a single scan or a few, so it can be built and tested on beta scans now.

**Order** (regroomed 2026-10-19, product owner: levelling characters and professions comes first, since the first weeks after launch are for levelling and scanning, not trading; no rush on launch day; 2026-10-20: quest/XP capture and gold per hour by activity go first, to compare levelling with crafting from day one):
1. STORY-123 Quest and XP capture
2. STORY-124 Gold and XP per hour by activity
3. STORY-114 Launch-day checklist
4. STORY-115 Cold-start states and evidence unlock
5. STORY-116 Vendor resale
6. STORY-118 Loot names and vendor value in farming
7. STORY-119 Gathering skill-up guide
8. STORY-120 Camp items check
9. STORY-121 First seen and scarcity
10. STORY-122 Full-house load test

**Web app lane (decided 2026-10-16, product owner; finished 2026-10-17):** the owner approved the clickable prototype in `docs/prototype/web-app.html` as the direction: an app shell, an inspector that opens records in place, and Today as one route. The rules are UI-18 in `requirements.md` and the structure is *Web app (UI-18)* in `design.md`. Page stories compare their 1280/390 px screenshots with the matching prototype view.

**Done** (outcomes in `status.md` and `requirements.md`; story text in Git): STORY-006, 015b, 021, 025, 030, 031, 032, 033, 034, 034b, 035, 036, 037, 038, 039, 040, 041, 042, 043, 044, 045, 046, 047, 048, 049, 050, 051, 052, 053, 054, 055, 056, 057, 058, 059, 060, 061, 062, 063, 064, 065, 066, 067, 068, 069, 070, 071, 072, 073, 074, 075, 076, 077, 078, 079, 080, 081, 082, 083, 084, 085, 086, 087, 088, 089, 090, 091, 092, 093, 094, 095, 097, 098, 099, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 117 and SPIKE-009/009b.

### STORY-123 — Quest and XP capture

New on 2026-10-20 (product owner, top of Order): to answer *is levelling worth more than crafting early on?*, the app must see quest rewards and experience. Today quest money lands in UI-15's **other** (*quests and flights have no event*), and XP isn't recorded at all, only level from bags.

As a gold maker levelling several characters, I want the addon to record each quest's rewards and how my experience grows, so that the app can compare gold and XP per hour from questing and killing with my crafting and auction time.

Decisions (2026-10-20, product owner: capture now, before launch, so the first live week is measured):
- **Read-only, event-driven,** like ADDON-12: no requests, timers or actions. Addon version bumps to 0.13.0; account format stays 6 if the new families fit the existing `journal` entry shape, otherwise 7 with older formats readable.
- **Quests (family `quest`):** guarded `QUEST_TURNED_IN(questID, xpReward, moneyReward)` journals the raw arguments, quest name if already loaded (`QuestUtils_GetQuestName` or `C_QuestLog.GetTitleForQuestID`, guarded; missing stays missing, never requested), zone via `journal.zone()`, level and XP after. A guarded `hooksecurefunc("GetQuestReward", ...)` records the chosen reward index; at turn-in, guarded `GetNumQuestRewards`/`GetQuestItemLink("reward"|"choice", i)`/`GetQuestItemInfo` record reward item links and quantities while the quest frame still holds them. A negative `moneyReward` is a quest cost, kept as reported. Pattern from Journalator's `QuestsClassic.lua` (MIT; credit comment if code is borrowed).
- **XP (family `xp`), checkpoints not per kill:** the 10,000-entry journal cap (ADDON-12 *Cap*) can't take an entry per kill during levelling. Keep in memory the XP gained since the last checkpoint, split into *quest* (the turn-in's `xpReward`) and *other* (kills, exploration, everything else; never guessed further), from guarded `PLAYER_XP_UPDATE("player")` with `UnitXP`, `UnitXPMax` and `GetXPExhaustion` (rested). Journal one checkpoint at each level-up, zone change (`ZONE_CHANGED_NEW_AREA`), quest turn-in and logout/reload, carrying level, XP, XP max, rested, and the quest/other XP gained since the previous checkpoint, with the previous checkpoint's ID. Level-ups split the gain correctly across the level boundary (XP max differs per level). Unknown values stay missing.
- **Import:** the new families import, preview and deduplicate like other journal entries (ADDON-12 *Clear/import*), house checks unchanged, raw bytes preserved. Data shows scoped counts and latest time per family.
- **Ledger:** a positive `PLAYER_MONEY` movement within one second after a `QUEST_TURNED_IN` whose `moneyReward` equals the delta becomes **quest reward** (UI-15 item 8 changes; `ledger_version` 2). Unmatched stays **other**. Quest costs match the same way as **quest cost**.

Acceptance:
- **Addon:** quest turn-ins and XP checkpoints recorded as above, silent in normal play; missing APIs counted in `/bscan status` like other journal events; a long session stays well under the cap (estimate entries per hour in the hand-off).
- **Import and Data:** both families import and show; older files import unchanged.
- **Ledger:** quest rewards and costs categorised; other categories unchanged; reconciliation unchanged.
- **Offline tests:** addon Lua tests for turn-in recording (with and without loaded name, reward choice, negative money), XP checkpoints (kills, quest XP, level boundary, rested, reload/logout, missing APIs); importer fixtures for the new families (dedupe, conflict, other house); ledger matching (exact, unmatched, two quests in one second, a cost). Extend existing addon, journal and ledger tests before adding files.
- **In game after launch** (no rehearsal needed now): one session confirms the events fire on Forever; record the result in `status.md`.
- Depends on nothing. Rules: ADDON-12, ADDON-11 (session/clear), ADDON-13, UI-15, DATA-01, OPS-03. Design: *Character evidence*, *Gold ledger contracts*.

### STORY-124 — Gold and XP per hour by activity

New on 2026-10-20 (product owner, top of Order). Replaces *Is it paying off?* under Later (first version) and absorbs *Tonight's debrief*.

As a gold maker, I want to see what an hour of each kind of play earns per character and level band, so that I know whether questing, farming or crafting and the auction house is the better use of my time, and when that changes.

Decisions:
- **Sessions:** a play session is one login (ADDON-11 `sessions` marker, reloads included) to that character's last journal entry before the next login. Minutes come from the journal's own times; no `RequestTimePlayed`. Sessions with gaps longer than `idle_minutes` (UI-13's setting) count only active stretches.
- **Activities** from evidence, never names:
  - **Market time:** minutes with an auction, mailbox, merchant, trainer or crafting window observed open (ADDON-12 window flags), merged where they overlap.
  - **World time:** the rest of active session time (questing, killing, gathering, travel; not split further).
- **Gold:** UI-15 movements by category per session: *world gold* = quest reward + coin loot + vendor sale; *market gold* = auction sale + deposit refund − auction deposit − auction purchase − vendor purchase − training; mail between own characters excluded. Each shown in copper with its categories; **other** shown separately, never assigned.
- **Loot value:** items gained in world time (UI-16 gathered/looted and quest reward items) valued at the cautious after-cut price, else vendor price, labelled *value if sold, not gold* and kept separate from gold.
- **XP** (needs STORY-123; *XP not captured* before it): quest XP and other XP per session, XP per hour of world time, levels gained.
- **Views:** the character record gets *Is it paying off?*: last session (the nightly debrief: minutes, gold by category, loot value, XP, levels) and per level band of five levels (1–5, 6–10, …): world gold/hour, loot value/hour, XP/hour, market gold/hour. Team gets one summary row per character and a team total. Today's Level up links to it.
- **Honesty:** own past sessions, not a promise; launch competition differs; market gold per hour includes sales of items gathered or crafted earlier (no cost basis yet: *Lots and cost basis* under Later). Thin evidence (under 30 minutes in a band) says so.

Acceptance:
- Sessions, active minutes and window minutes from journal evidence as above; overlapping windows counted once.
- Gold per hour by activity from UI-15 categories; loot value separate and labelled; XP when captured.
- Per-session and per-band views in the character record and a Team summary; Today Level up link.
- **Offline tests:** session boundaries (reload, idle gap, two characters), window minute merging, category grouping and the excluded own mail, loot valuation (auction, vendor, none), XP with and without STORY-123 evidence, level bands, thin-evidence label. Extend ledger, item-ledger and Team tests before adding files.
- **Real data:** the beta copy's characters per session and band (XP shows *not captured*); report Arille's and Baspion's world against market gold per hour.
- Compare the record and Team at 1280 and 390 px with the prototype (UI-18).
- Depends on STORY-123 for quest and XP figures; everything else works on today's evidence. Rules: UI-15, UI-16, UI-13, ADDON-11, ADDON-12, *Team character cards*, MONEY-01/02. Design: *Gold ledger contracts*, *Item ledger contracts*, *Farming (STORY-065, STORY-074, STORY-075, STORY-077)*, *Team contracts*.

### STORY-114 — Launch-day checklist

Moved from Later (*Launch-day checklist*, STORY-020a/020b) at the 2026-10-19 grooming. Product owner: no rush on launch day; the first one to two weeks are for levelling and scanning, so the checklist can be followed calmly over the first evening, not raced.

As a gold maker, I want a short, tested checklist for 4 November, so that the switch to the live game is calm and nothing is missed.

Acceptance:
- **A short checklist** in `docs/launch.md`, linked from `status.md`, in the order you would do it: install or update the addon and check that it loads (the `.toc` interface number may change); first scan, `/reload`, import, clear; and
  - **fresh start** (decided 2026-10-18): stop the app, copy the beta `data/` to a dated read-only archive folder, start with an empty `data/`, and enable only the live source (the Classic and Retail stand-ins go with the archive); `work/beta-corpus/` keeps the corpus check working;
  - adding and enabling the live Roleplaying Alliance source in `config/market.local.toml`, with its own `source_id`, `environment = "live"`, the live game folder's `scan_path` and its `rules_version` (DATA-03);
  - re-saving each Forever Wowhead page and regenerating. If the live `rules_version` differs from the beta's, every Forever catalog stays inspection-only until regenerated (*Refresh due* flags it);
  - copying `config/team.local.toml` names onto the live characters once created.
- **Checked** on data copies where it can be (archive, empty start, source switch, regenerate); live-house checks happen at launch.
- **After launch, no deadline:** the in-game checks the beta left open (sale-to-mailbox delay, crafting tier levels, yellow skill-up chances; `status.md` → *Limitations*) and the facts under *Product direction*, each with where to record the answer.
- Depends on nothing. Rules: OPS-01, OPS-03, DATA-03, CRAFT-01, CRAFT-08. Design: *Switching to WoW Forever*.

### STORY-115 — Cold-start states and evidence unlock

Merges *Cold-start states* and *Evidence unlock strip* from Later (*Launch week, from the first scan*) at the 2026-10-19 grooming.

As a gold maker starting from an empty `data/`, I want every page to say what it is still waiting for, so that a missing signal on 4 to 6 November reads as *not yet*, not as a broken app or a quiet market.

Context: UI-11's typical price needs three priced UTC days, so cheap/high flags, overshoots, price warnings and Today's typical-based confidence have no basis on the first days; UI-10/UI-19 removal speed needs qualifying scan gaps; UI-17 history needs several scans.

Acceptance:
- **Waiting states:** each signal that lacks its minimum evidence says so with counts, e.g. *typical needs 3 priced days, 1 so far*, *removal speed needs 2 scans within 12 hours*, never a blank, zero or *steady*. Covers Market (cards, grid signal, Left early, item page), Today (Opportunities evidence, price warnings, confidence reasons) and Team where it shows these signals.
- **Unlock strip:** one line on Market and Today: *live since 4 Nov · 6 scans over 2 days · price signals unlock tomorrow*, from the source's eligible scans only (DATA-08, full MARKET_KEYS). It disappears once every signal has its minimum.
- **Today still plans from one scan:** with one complete scan, the funded plan, Route and Level up work; only the typical-based parts wait.
- **Offline tests** at 0, 1, 2 and 3 priced UTC days and with and without qualifying gaps: each waiting message and count, the strip's text and its disappearance, and that a single scan still yields a plan. Extend the existing flood, removal-speed and Today tests before adding files.
- **Real data:** a copy of `data/` cut to its first scan, then its first two days, shows the waiting states; the full beta corpus shows none (`python -m api.beta_check check` headlines unchanged).
- Compare Market and Today at 1280 and 390 px with the prototype (UI-18) for the strip and waiting text.
- Depends on nothing. Rules: UI-10, UI-11, UI-17, UI-19, DATA-05, *Today (today_version 15)* (Confidence, Price warnings). Design: *Flood signals (STORY-064/072)*, *Removal speed (STORY-062)*, *Today contracts*, *Web app (UI-18)*.

### STORY-116 — Vendor resale

New at the 2026-10-19 grooming, from using the app on the beta copy. Product owner: unsure it is more than a convenience, so it stays modest and honest.

As a gold maker, I want to see vendor goods that the auction house lists well above their vendor price, so that I can pick up a few on the way past a vendor when it is worth the bag space.

Evidence (beta copy, 2026-10-19): the journal holds 431 vendor-list entries covering 294 items with a plain gold price (ADDON-12 *Vendor lists*). Against the newest scan, 29 unlimited-stock items list at 1.5× or more of their vendor unit price, e.g. Mild Spices (2678) 2c vs 63c lowest, Red Dye (2604) 50c vs 5s, an item at 10s vs 21s with 26 listings.

Decisions:
- **Vendor price:** the lowest captured unit price (`price_copper / quantity`) for the base item, from vendor lists of the selected source and full market, with unlimited stock only (`stock == -1`); limited stock, extended cost and missing prices are excluded. Name the vendor NPC, zone and capture time. Standing discounts are not modelled; a capture at Friendly or better says *price at your standing*.
- **Gain:** per unit, lowest positive auction unit price minus 1c undercut (Today's Sell step), after the cut (`money.after_cut`), minus the vendor price and the deposit for one post where known (*Auction deposits*); unknown deposit makes the gain unknown, never deposit-free.
- **Honesty:** listings are not sales. Each row shows listings, units and, when UI-19 has it, units removed early; rows without removal evidence say *no sales evidence yet*. Rank by gain × min(units removed early, 20) when removal evidence exists, otherwise list after those by gain. No forecast, no quantity advice beyond *a few*.
- **Where:** a short list on Market (*Vendor resale*, top five, more on demand) and a line on the item page. Not in Today's plan or budget.

Acceptance:
- Only unlimited-stock captured vendor prices from the same source and full market; never catalog vendor prices or another source's.
- Gain in integer copper after cut and deposit; unknown deposit or price means no row, never a free or zero value.
- Removal evidence shown and used for order as above; *no sales evidence yet* otherwise.
- **Offline tests:** limited stock and extended cost excluded; bundle quantity divides; lowest price across captures; scope (other source/market ignored); gain with and without deposit; order with and without removal evidence; empty states (no vendor captures, no scan).
- **Real data:** the beta copy lists the items above with their vendors; report the top five.
- Compare Market at 1280 and 390 px with the prototype (UI-18).
- Depends on nothing. Rules: ADDON-12 (Vendor lists), *Today (today_version 15)* (Sell, Auction deposits, Below vendor), UI-19, UI-09, MONEY-01/02, DATA-08. Design: *Market explorer (STORY-055)*, *Beta evidence report*, *Removal speed (STORY-062)*.

### STORY-118 — Loot names and vendor value in farming

New at the 2026-10-19 grooming, from using the app on the beta copy.

As a gold maker, I want farming rows to name every looted item and value it at its vendor price when it has no auction price, so that grey loot counts toward gold per hour.

Today: `farming.valued` names a row only from UI-11 signals and values it only from auction sell prices, so Lira's rows read *Item 1367 · no price per hour*. The loot capture already holds the link name (*Ragged Leather Boots*) and `vendor_sell_copper` 2 (ADDON-12 *Discovery context*); farming spots already use loot vendor prices, only the per-item rows don't.

Acceptance:
- **Name:** item rows use DATA-02's resolved name, falling back to the loot link's name for that game version, then *Item N*.
- **Value:** with no positive auction price, value units per hour at the newest positive vendor sell price (scan item info, then loot capture), labelled *vendor*; auction value still wins when higher after the cut. Missing both stays *no price*, never zero.
- **Offline tests:** link-name fallback, vendor-only value and label, auction beating vendor, neither price. Extend `tests/test_farming*.py`.
- **Real data:** Lira's and Star's rows on the beta copy show names and vendor values.
- Depends on nothing. Rules: UI-13, ADDON-12 (Discovery context), DATA-02 (Item names), MONEY-01. Design: *Farming (STORY-065, STORY-074, STORY-075, STORY-077)*.

### STORY-119 — Gathering skill-up guide

New at the 2026-10-19 grooming (idea seen in ForeverArtisan; ideas only, all rights reserved).

As a gold maker levelling Mining, Herbalism or Skinning, I want to know which nodes or skins still give skill-ups at my rank and where I have gathered them, so that Level up has a step for gathering professions instead of *Gathering is an option here*.

Decisions:
- **Evidence first:** each node or skinnable level's required skill and colour bands come from saved Forever Wowhead pages (object/NPC pages or the profession page), archived like CRAFT-08 sources, never from Classic assumptions or names. Without evidence for a node, it isn't shown. If the saved pages don't carry this, the story stops at a short evidence report and a decision for the owner.
- **Step:** on Level up, a gathering card per character: the current rank, which evidenced nodes still give skill-ups (orange/yellow/green), and the owner's own UI-13 spots for them (zone, cell, units per hour), labelled *your own past sessions, not a promise*.

Acceptance:
- Only evidenced thresholds; unknown nodes say *skill-up range unknown*.
- **Offline tests:** band placement by rank, unknown evidence, no farming history, several characters.
- **Real data:** Arille Mining 48, Baspion Mining 9 on the beta copy.
- Depends on nothing. Rules: UI-13, CRAFT-10, CRAFT-11, CRAFT-08 (source evidence), UI-12. Design: *Farming (STORY-065, STORY-074, STORY-075, STORY-077)*, *Skill-up map contracts*, *Recipe import*.

### STORY-120 — Camp items check

New at the 2026-10-19 grooming. Forever adds Camping: profession camp objects from skill 20 give group buffs around a campfire ([Warcraft Tavern](https://www.warcrafttavern.com/forever/guides/camping/)), a likely launch demand wave. Guides are third-party and beta-era.

As a gold maker, I want to know whether our catalogs include the camp-item recipes, so that Today, Team and Level up can price them like any other craft.

Acceptance:
- **Check** each saved Forever profession page for camp-item recipes (and Blueprint recipes): list them per profession with spell IDs, required skill, reagents and whether the selection includes them.
- **If missing:** add the trainer-learnable ones to the selections and regenerate (CRAFT-08), with catalog version bumps and source evidence; drop-only Blueprints stay out unless the owner picks them.
- **Report** in the story hand-off: recipes added, any page that needs re-saving.
- **Offline tests:** only if selections or the generator change.
- Depends on nothing. Rules: CRAFT-01, CRAFT-08. Design: *Recipe import*.

### STORY-121 — First seen and scarcity

Merges *First seen* and *Scarcity board* from Later (*Launch week, from the first scan*) at the 2026-10-19 grooming.

As a gold maker in launch week, I want to see items appearing for the first time and the catalog items nobody is listing, so that I can be first to market as the population levels.

Acceptance:
- **First seen:** items in the newest eligible scan that no earlier eligible scan of the source listed, grouped by catalog skill band (CRAFT-10), with listings, units and lowest price. Works from the second scan; with one scan, says so.
- **Scarcity:** catalog materials and outputs with zero or at most `scarcity_listings` (default 2) listings in the newest scan that a team character can gather (has the gathering profession) or craft (Known/Train now), with the cautious cost to make where known. Never inferred from names; gathering link needs evidence (STORY-119's or catalog `raw_material`).
- Both on Market as short lists, items opening their records. Listings are not demand.
- **Offline tests:** first-seen with 1, 2 and 3 scans and variant identities (ADDON-08); scarcity thresholds, team eligibility, no catalog.
- **Real data:** beta copy lists for its newest scan.
- Compare Market at 1280 and 390 px with the prototype (UI-18).
- Depends on nothing (STORY-119 improves the gathering link). Rules: UI-06, UI-09, CRAFT-10, CRAFT-12, ADDON-08. Design: *Scan comparison*, *Market explorer (STORY-055)*.

### STORY-122 — Full-house load test

Moved from Later (*Launch week, from the first scan*) at the 2026-10-19 grooming. The live Roleplaying house may hold 5 to 10 times the beta's listings.

As a gold maker, I want proof that import, Market and Today stay fast on a full live house, so that launch week isn't slowed by the app.

Acceptance:
- **Synthetic scan** generated in the test (not committed data): 5× and 10× the newest beta scan's listings and items, same shape (formats, variants, no-buyout listings).
- **Measured:** preview, import, metrics, Market grid first page, item page and Today load, each with a budget recorded in `design.md` (*Quality gates* or *Known design debt*) from a first measurement; a marked slow test that is skipped by default and run by hand.
- **Fix only what breaks the budget**, measuring before and after.
- Depends on nothing. Rules: ADDON-04, ADDON-06, ADDON-10. Design: *Quality gates*, *Market metrics layer (STORY-024)*, *Market explorer (STORY-055)*.

## Later

**Ideas from the 2026-10-19 grooming** (not scheduled; the product owner asked for bolder ideas after using the app on the beta copy):
- **Follow the levelling wave:** UI-19 removal speed grouped by catalog skill band (CRAFT-10), so the market's current buying moves from band to band are visible (*Linen and Copper moving; Wool starting*): what to gather and level next. Needs a week of live scans. M.
- **Which gatherer feeds the team:** for each uncovered gathering profession, the share of the team's reach material bill (CRAFT-11 buys) it would supply, with the item-to-profession link from evidence, never names. Extends STORY-117. M.
- **Keep, post or vendor in game:** the decision in the bag tooltip. Needs Brownstone to write a file the addon reads, which *In-game plan list* under *Deferred* rules out today; a product decision, after launch.
- **Polish pass:** when every line is Low confidence, say it once; round displayed expected units (*≈ 70*, not *≈ 69.7508*); Opportunities' negative *Vendor value* reads *vendoring loses X*; collapse repeated *Not enough farming history* rows; open on the only enabled source. S.

**Holdings per target** (found in the STORY-113 review, 2026-10-19; needs an owner decision): STORY-113 compares with and without holdings once per profession window, and every target slices the kept walk. A target reached early can then cost more than with its own stock: on the copied beta, Basilly's Heavy Linen Gloves went from 0c (all held) to 1,215c and the linen shirts and robe from 30c to 1,245c, because the window's walk buys the whole Linen listing first. The note also always cites the whole window (*these 25 points*), even on Blue Linen Vest at 24 points, and repeats on every target. Options: compare per target (a second walk per target prefix), or keep the window rule and say on short targets that stock covers them alone.

**Captured colours: remaining gaps** (found in the STORY-098 review, 2026-10-18; revisit with live captures after go-live): the copied beta has only 26 learned recipes, so captures fill two colour gaps (Smelt Copper, Copper Rod) and no hire or window-25 path becomes complete; starter, training and price evidence still block costs. Four learned recipes contradict their Wowhead colours and await owner review (`python -m brownstone skillups --source forever-us-normal-alliance-addon`). The catalog's `required_skill` 25 for Smelt Copper also looks wrong for Forever (learned and orange at rank 3). `--write` updates only existing picks; a derived intermediate with no pick of its own is listed, not written (adding a pick would make it a selected recipe), so capturing intermediates' colours needs a decision.

**Farming routes with a node addon** (idea from the product owner, 2026-10-19; not scheduled, after go-live): when STORY-112 says *or farm ≈ H h*, help pick where and how. A node addon such as Gatherer shows ore and herb nodes on the map and minimap; our farming capture (UI-13, STORY-074/075) already records what each loot window gave, when, and a map-percent position cell. Together they could rank spots and routes by measured value per hour, e.g. *Copper Ore: 3 cells in Elwynn, about N nodes per hour on your own runs*, and show how a route's real yield compares with its node count.
- **First, check:** whether Gatherer (or an alternative) loads on Forever, and whether its SavedVariables hold node positions we can read as data. Gatherer comes from the Auctioneer authors, so treat it like Auctioneer: ideas only, no code, until its licence is checked (AGENTS.md).
- **Our side stays read-only:** the app reads both files; it draws nothing in game. Map or minimap display stays with the node addon, since BrownstoneScan only reads (SPIKE-008).
- **Honest limits:** rates are the owner's own past runs, not a promise; launch respawn competition differs from beta; cells are coarse (`farming_cell_percent`), so *route* means an ordered set of cells, not a path. Needs enough gathering stretches per spot after launch.

**Lots and cost basis** (deferred from STORY-034 on 2026-10-15): which purchase each sold or crafted unit came from, for realised profit. Needs STORY-034b's item movements and a rule for held stock of unknown cost.

**Launch week, from the first scan** (ideas from the 2026-10-18 grooming, not scheduled). With a fresh start, UI-11's typical needs three priced UTC days, so cheap/high flags, overshoots and Today's confidence have no basis on 4 to 6 November, and removal speed needs scan gaps. These would make the first week useful (cold-start states, the unlock strip, first seen, scarcity and the load test became STORY-115, 121 and 122 on 2026-10-19):
- **Since-launch trend:** per item, first-seen price, lowest so far and change across scans, to answer *sell now or wait?* before a typical exists. Descriptive, never a forecast. M.
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
