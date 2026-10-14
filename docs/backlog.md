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

Nothing in progress; the next story is the top of *Order* under Next.


Scan format 3 (STORY-023) and the reload/clear buttons (STORY-029) are accepted on the beta with addon 0.3.1; the measurement record is in `addon/README.md`. Brownstone can now run on our own addon scans alone (STORY-010). Launch market remains Forever US, Roleplaying, Alliance (`forever-us-roleplaying-alliance`); the beta currently offers only Normal servers, so the configured example source is `forever-us-normal-alliance`.

**Through the last full beta testing day, 21 October** (manual, in game):
- **Keep scanning.** Sixteen complete scans of the Normal Alliance house are imported (`status.md` → *Limitations*). Take more, at least 15 minutes apart, **at different times of day and on different days**, so the diff and timing work (STORY-018; *Market timing and a daily brief* under Later) has something to start from. The routine: scan, `/reload` (the game writes scans to the file only then, or on logout), import, and only then `/bscan clear` and `/reload`. A Roleplaying or neutral house scan, if reachable, tests house identification. This is a manual habit, not automation.
- **Confirm the Forever catalog's unconfirmed values** (`status.md` → *Limitations*). Learn Bolt of Linen Cloth and check how many it makes: the profession window may show the count on the product icon, and crafting one (2 Linen Cloth) settles it. Buy your crafting reagents (thread, dye, flux, vials, spices) from a trade-supplies vendor rather than the auction house when you need them: the addon records each purchase, and Claude confirms the marked vendor prices from it. Also decide whether Runecloth Bag's dyes are really post-launch: both are listed on the beta auction house.
- **Widen the Forever catalogs** (manual saved pages and `python -m brownstone recipes`): the rest of Tailoring, then the professions you plan to level at launch. The board and Today's *Craft* list only cover catalog recipes, so this is what gives them something to show.
- **If any yield is more than 1** (now unlikely: Wowhead's "(2)" is an effect number, not a count; see `requirements.md` → CRAFT-08), *Multi-yield costing* (Later) moves to the top of Next: the Forever board's costs are wrong until it exists.
- **Prepare a beta character for the character-data tests** (added 2026-10-06): level one **gathering** profession (Mining or Herbalism) and one **crafting** profession that uses it, far enough to gather, craft, post, sell, let something expire and cancel. Keep a little gold to buy and vendor with. This is what STORY-032 and STORY-033 are tested on.
- **Test the new addon builds in game** once STORY-031 to STORY-033 and STORY-040 are ready (aim: by 13 October, leaving a week of beta). Each run records what actually happened, so it can be preserved as a test fixture before the beta closes:
  - **Item info pass (STORY-031):** after a scan, how many items still lack vendor price, item level and stack size, against the 0.3.1 numbers.
  - **Snapshots (STORY-032):** gold and bags written on logout and on `/reload`; bank only after opening the bank; two characters on the same account. With a new character (added 2026-10-07: no spare bags yet), test the backpack, any equipped bags, the main bank and one bank bag slot if you can buy it. That bank bag must appear in the bank snapshots (taken when you open the bank) and never in the logout snapshot of your bags. Whatever you can't test yet moves to *Snapshot coverage* under Later.
  - **Event journal (STORY-033):** buy from the auction house, post, cancel, let one expire, sell one; open the mailbox and take the invoice and the returned item; craft; gather; buy and sell at a vendor; send mail between your own characters. Note which events fired and with what values.
  - **Active auctions (STORY-040):** open the Auctions tab before posting, after posting, after a cancel and after a sale, and note whether the list arrives without opening the tab.
  - **Professions (STORY-041):** open each profession window (Mining and Engineering on the new character; Tailoring and Enchanting on the druid), learn one new recipe and open the window again, gain a skill point, then log out.
  - **Who checks (added 2026-10-07, product owner):** the product owner only plays: gathering, crafting, posting, mailing and logging out. Claude checks every session's file with the STORY-042 report and says what is confirmed, missing or wrong. Nobody reads the addon file by hand.
  - **Unconfirmed claims** (`requirements.md` → *Known Forever market facts*): time from a sale to its gold in the mailbox; the deposit charged for a few posts of known vendor price and duration (STORY-035); whether the Black Market vendor exists, where, and its prices (STORY-036); the postage for mail to your own characters, with and without attached items and gold (added 2026-10-06: moving materials to the character with the right profession may cost something per mail).

## Next

**Agreed order (groomed 2026-10-05):** the app is almost all tables today, so user-facing analysis now gets its own lane in Next instead of waiting behind launch preparation. The layers, each building on the one before:
- **Scans** (exists) → **market metrics** (exists; ADDON-10 in `requirements.md`) → **analysis views** (item page, charts, sellers) and the **Today** page (what to buy, craft and sell now).
- An optional AI narration layer can come later. It may only explain those defined metrics, never invent numbers (*Out of scope*).
- Time-of-day and weekday patterns need weeks of live scans (*Market timing* under Later). Everything in Next works on a single scan or a few, so it can be built and tested on beta scans now.

**Order** (regroomed 2026-10-13 after Claude's player walkthrough of the beta data, and 2026-10-14 after the addon comparison):
1. STORY-078 an item page you can read (replaces the item-page half of STORY-021)
2. STORY-035 auction deposits (deposit, refund and cut evidence captured 2026-10-13, in `status.md`: refine first)
3. STORY-073 your own sale rate (refine first)
4. STORY-069 Today in player terms
5. STORY-070 Team's next recipe you can actually learn
6. STORY-062 sales speed and suggested stock levels (after STORY-027 and enough scans; refine first)
7. STORY-034 movement ledger and reconciliation (Brownstone; can follow the beta, built on its fixtures)
8. STORY-036 vendor price ceilings (after STORY-071)
9. STORY-021 item charts and listing ladder (inside STORY-078's layout)
10. STORY-026 scan coverage and rhythm
11. STORY-028 sellers and supply chains (blocked: see *Seller capture* under Later)
12. STORY-006 replay

**Pending an in-game beta check:** STORY-071 and STORY-077 (time-critical: before 21 October), STORY-044 and STORY-027 (checklist in `addon/README.md` → *Last beta play session*). STORY-031, 032, 033 and 040 were confirmed on 2026-10-13 (`status.md`).

**Done** (outcomes in `status.md` and `requirements.md`; story text in Git): STORY-015b, 025, 030, 031, 032, 033, 037, 038, 039, 040, 041, 042, 043, 045, 046, 047, 048, 049, 050, 051, 052, 053, 054, 055, 056, 057, 058, 059, 060, 061, 063, 064, 065, 066, 067, 068, 072, 074, 075, 076 and SPIKE-009/009b.

### STORY-068 — Use what the team holds

Implemented; current behavior is in `status.md` and Today in `requirements.md`. Acceptance text retained until the next commit.

Promoted from *Restock* (Later) on 2026-10-13 after the walkthrough: Basilly held 8 Bolts of Linen Cloth, but Today bought 19 Linen Cloth to make 5 more. Refined 2026-10-14. Mailbox holdings, CRAFT-11's reach cost and choosing a different route because of holdings are split off to *Today, later versions* (Later).

As a player, I want Today to use what my characters already hold before buying, so that I don't spend gold on materials sitting in my bags.

Acceptance:
- **Holdings** are Stock's (`stock.holdings`): the newest readable bags and bank capture per character in the selected source and full market, base ADDON-08 identity only (variants and unresolved links never count). An unknown bank adds nothing and is labelled *bank not captured*, never treated as empty. A capture older than `max_age_hours` is still used, with its age shown and a confidence reason *held count from a stale capture* (the level is unchanged). Holdings are read in `load_today` and passed to `build_today` as data, like `character_data`; nothing loads inside the calculation.
- **Whose holdings:** with one character selected, only that character's holdings (as with funds); with *Our team*, every scoped character's.
- **Held before bought, along the chosen route:** the Board's route is unchanged (CRAFT-03). Sizing a batch takes the route's materials from holdings first, then the listing ladder or vendor as now. This applies to purchased materials and to the route's crafted intermediates: a held Bolt of Linen Cloth replaces one Bolt craft and its two Linen Cloth. Go top-down (an intermediate before its own inputs). Use only as many held units of an intermediate as leave a whole number of its crafts (CRAFT-02's fractional rule is unchanged).
- **Shared across the plan:** holdings are used up in plan order, like reserved listings. A later craft sees only what earlier crafts left, and an adjusted batch (`choices`) re-reserves them the same way.
- **Never free:** a held unit costs what selling it would earn, the CRAFT-04 cautious sell price after the cut, rounded down. Without a sell price, it costs the route's unit cost for that item. Batch cost and profit include this; **gold needed** and the shopping list don't. Batch sizing therefore checks funds against gold spent only, and the batch sizes it compares include the craft counts where any holding runs out.
- **Showing it:** a craft's materials list held units as **held** with their value (*worth Xs if sold*). *Buy* leaves them out. The Queue starts with *take* lines, grouped by character and place (*Basilly: take 8 Bolt of Linen Cloth from the bank*). A held unit on a character other than the crafter (the row's `made_by`) adds *Basilly mails 8 Bolt of Linen Cloth to Arille*, with postage uncharged and unconfirmed (the existing mail note). Allocation order: the crafter's bags, then bank, then other characters by name, bags before bank.
- **Held outputs:** when the team holds units of a planned output, *Sell* and the Queue's post line show them beside the batch (*post 5 crafted + 2 held*, naming who holds them) at the same post price. Their value is shown separately and is not added to the craft's profit.
- **Unchanged:** routes, prices, funds, Stock targets and This session (STORY-063 stays independent of holdings). Today's results change, so `TODAY_VERSION` increases.
- **Offline tests:** held leaf material lowers gold needed and keeps profit honest (held value counted); held intermediate replaces its subtree, including the whole-craft limit on an intermediate making more than one; holdings used up in plan order across two crafts and through an adjusted batch; selected character vs *Our team*; variant and unresolved slots ignored; unknown bank; stale capture reason; missing sell price uses route cost (never zero); mail and take lines with allocation order; held outputs in *Sell*; the chosen batch matches a brute-force search over every size from 1 to `max_crafts` on fixtures with holdings; no holdings gives exactly today's plan apart from `today_version`.
- **Real data:** on a copy of the Forever beta data, the Linen Cloth case: Basilly's bolts appear as held in the craft that uses them and gold needed falls. Report the before and after.
- **Docs:** the held rule under Today in `requirements.md` (next to *Routes/batches*); remove Stock's *stock changes no Today plan* sentence as it applies to holdings (targets still change nothing); `design.md` for the data flow; `status.md`.

### STORY-069 — Today in player terms

Added 2026-10-13 from the walkthrough. Small presentation fixes; no calculation changes.

As a player, I want Today's numbers and steps to read the same way everywhere, so that I can act on them without decoding them.

Acceptance:
- **One profit:** a craft shows the same expected profit on the summary tile, its card, *Sell* and *This session* (at the post price; currently the card and *This session* show the profit at the cautious sale price, 32s 89c, and the tile shows it at the undercut, 28s 14c). The other figure stays in the evidence, labelled.
- **Money and words in tables:** *Sell*, *Shopping list* and *Queue* show copper amounts with `money.py` (no gold decimals such as 0.2814) and yes/no or a label instead of true/false.
- **Mail step:** when the crafter's own gold doesn't cover their purchases, the Queue names who mails how much gold to whom, from the captured gold per character. Postage is uncharged and unconfirmed, as now.
- ***This session* duplicates:** one *level X to N to train Journeyman* step per character listing every profession it unlocks; characters without farming history show one short line, with the caveats shown once per page instead of per character; correct singular/plural (*1 stretch*).
- **Hidden recipes:** the *why?* dialog leads with a plain summary (*1,298 need a profession nobody has · 441 need more skill · …*); scope, versions and snapshot IDs move into an expandable *Details*.
- **Offline tests** for each; UI tests through the existing NiceGUI harness.

### STORY-070 — Team's next recipe you can actually learn

Added 2026-10-13 from the walkthrough. Arille's best next Cooking recipe was Peace Tea, which needs a recipe drop (Low confidence), while trainer and quest recipes were within reach.

Acceptance:
- **Best next recipe** prefers recipes the character can learn from a trainer, vendor or quest, then drops and unknown sources; within each, the current CRAFT-11 order. The full list keeps every recipe, with its source.
- **Gathering professions** (Mining, Herbalism, Skinning, Fishing) with no craftable catalog recipe in reach say *levels by gathering* instead of an empty *No data available* table.
- **Profession comparison:** when every cost to 300 is incomplete, say so once at the top instead of on every row.
- **Training payback** (added 2026-10-14 from CraftProfit): beside each recipe that needs training, how many crafts at its current per-craft profit pay back the training cost (rounded up); *never* when the profit is zero or negative, *unknown* when the cost or profit is.
- Today's plan, ranking and versions unchanged.

### STORY-071 — Vendor price lists (addon, read-only)

Added 2026-10-14 from the addon comparison (aux and CraftProfit both record a vendor's full list when it opens). Today we only learn a vendor price when we buy something, so catalog vendor prices stay *unconfirmed* (the reason White Linen Shirt was Medium confidence) and STORY-036 has little to work with. **Time-critical:** it needs one beta play session before 21 October.

As the owner, I want every vendor I open to record what it sells and for how much, so that Brownstone can confirm vendor prices without me buying anything.

Acceptance:
- **Addon capture (read-only):** while a merchant window is open, record each merchant item: link and item ID, price and quantity per purchase, available stock (unlimited or a number), whether it costs something other than gold (extended cost; such items are kept as evidence but never used as a gold price), plus the vendor's NPC ID from its GUID and the zone (`journal.zone()`). Follow `journal.trainerServices`/`journal.trainerRead`: the list can load after `MERCHANT_SHOW`, so save a later read only while the window is open, non-empty and different from the last saved list. Bounded counts, `safe`/`readAll` calls, no clicks, purchases or automation. Bump the addon version.
- **Reputation:** prices can include a reputation discount, so record the player's standing with the vendor (`UnitReaction` on the open NPC) with the list. A price seen at a discount never confirms a full price.
- **Brownstone:** imports these entries through the existing journal (family `vendor`; no schema change) and adds a *vendor prices* section to the STORY-042 beta report: per item, each vendor, zone, price, stock and standing, and whether it confirms, contradicts or adds to the catalog's marked vendor price. Catalog values change only through the existing confirmation path, with this evidence cited (AGENTS.md).
- **Offline tests:** Lua tests in `addon/BrownstoneScan/test_addon.py` for the late-loading list, unchanged list not re-saved, extended cost and limited stock; Python tests for import scope and the report's confirm/contradict/new cases.
- **Beta check** (play actions only, added to `addon/README.md` → *Last beta play session*): open a trade-supplies vendor, a general goods vendor and one other vendor, without buying.
- **Docs:** the capture in `requirements.md` under the ADDON journal rules; `design.md`; `status.md`.

### STORY-072 — Typical price from one point per day

Implemented; current behavior is in `status.md` and UI-11 in `requirements.md`. Acceptance text retained until the next commit.

Added 2026-10-14 from the addon comparison: aux, Auctioneer and CraftProfit all collapse many scans into one point per time period before taking a typical price. UI-11 takes the median over every eligible scan, so an evening with six scans outweighs the other days. This matters more once STORY-067 caps Today's sale prices at the typical price.

Acceptance:
- **Daily points:** for each UTC day in the window, the day's point is the median of that day's eligible scans' lowest positive buyouts for the identity (ADDON-08 rules unchanged). The typical price is the median of the daily points. Daily points use earlier eligible scans only: the newest scan is never part of its own typical price, as now.
- **Enough history:** `flood_min_days` (default **3** distinct days) replaces `flood_min_scans`; the window stays `flood_window_days`. Config validation and inheritance as for the other flood settings; an old `flood_min_scans` setting is rejected with a message naming the replacement.
- **Shown:** evidence says *N days, M scans* instead of *N earlier scans*. Market, *This session* and Today (after STORY-067) all use the new value; nothing else changes.
- **Version:** if STORY-067 is done, `TODAY_VERSION` increases again.
- **Offline tests:** six scans on one day and one on each of two others give three equal-weight points; two days are *too few days*; integer copper; variants never pooled.
- **Real-data check:** on the Forever beta source, list the items whose label changes (cheap, typical, high, too few) and why.
- **Docs:** UI-11 in `requirements.md`, `design.md`, `status.md`.

### STORY-073 — Your own sale rate

Added 2026-10-14 from the addon comparison (Journalator's *sale rate*: sold against expired and cancelled per item, with the average sale price). Our journal already records posts, invoices and returned mail; nothing shows them. It's the only direct proof that something sells, and it fills in by itself from launch. **Refine first.**

Proposed acceptance (to confirm when refined):
- Per item and character: units posted, sold (from seller invoices), expired and cancelled (from returned mail), sale rate and average sale price after the cut, in integer copper; shown on Today's *Sell* rows and the Market item page.
- **Matching invoices to items** (proposed 2026-10-14; TSM does the same with its *sale hints*): a seller invoice carries the item's name but no link. Match it to the same character's own post or active auction (STORY-040) with the same name, stack size and buyout, within the auction's longest duration; the post's link supplies the item ID. No match, or more than one item matching, stays *unidentified* and never counts toward any item. The name only narrows candidates; the item ID comes from a link. Check what the beta capture actually holds first.
- **Stop after repeated expiries** (from TSM's *max expires*): an item that expired or was cancelled N times in a row for you (`max_expiries`, proposed default 3) with no sale in between gets a Today label *expired 3 times running* and a Low confidence reason.
- This is the first slice of STORY-034's ledger; build it so the ledger can reuse it.

### STORY-075 — Farming spot capture: coin, position and vendor value (addon, read-only)

Implemented and confirmed in game on 2026-10-14; outcome in `status.md` and UI-13. Acceptance text retained until the next commit. Positions and coin (0.12.4: 30 of 30 windows positioned, 15 of 15 coin loots matched) and loot-time vendor prices (0.12.5: Broken Fang 6c, Chipped Claw 4c and others, none of which the scans price). The two-camp game check was dropped: positions vary between windows, and the split is offline-tested. Added 2026-10-14. Follows STORY-074, and STORY-071's addon change, to avoid two version bumps at once. It can be checked on Classic Era as well as the beta, since nothing here is Forever-specific.

As the owner, I want each loot window to record where I stood, which slots were coin and what each item sells to a vendor for, so that farming spots separate two camps of the same mob and value grey items and coin properly.

Acceptance:
- **Addon capture (read-only):** `journal.zone()` adds the player's map position (`C_Map.GetPlayerMapPosition(map_id, "player")`, x and y as raw fractions; omitted when nil, for example in instances). `journal.lootSources()` adds each slot's `GetLootSlotType` (item, coin or currency) and quantity, and the item's vendor sell price from `GetItemInfo`'s sell price return when the client has it cached (omitted, never zero, when not). Bounded, `safe`/`readAll`, no clicks or automation. Bump the addon version.
- **Brownstone:** coin slots replace STORY-074's money-change inference where present. If both exist, the money change is the amount and the slot type is the evidence. A loot-time vendor sell price fills in for items the scan's item info lacks, preferring the scan's value when both exist and reporting any disagreement. A spot gains an optional position cell: x and y rounded down to 5% of the map (`farming_cell_percent`, default 5, a config setting read like `farming_idle_minutes`), taken from the median of the stretch's loot positions. Two stretches against the same mob in different cells become separate spots. No position means zone and mob only, as STORY-074.
- **Display:** the spot shows *around 45, 70* (cell centre, map percent). No map artwork. A simple scatter of loot positions on a 0–100 grid can come later.
- **Beta report:** the STORY-042 report counts loot windows with positions, coin slots and vendor prices.
- **Offline tests:** Lua tests in `addon/BrownstoneScan/test_addon.py` for a nil position, a coin slot, an uncached sell price and the slot cap. Python tests for the cell rounding, the median, the split of one mob into two spots, and the preference between the scan's vendor price and the loot-time one.
- **Check in game** (play actions only, in `addon/README.md` → *Last beta play session*): loot mobs with coin and a grey item (positions and coin confirmed 2026-10-14; the vendor price awaits 0.12.5).
- **Docs:** the capture in `requirements.md` under the ADDON journal rules and UI-13; `design.md`; `status.md`.

### STORY-076 — Back to where I was

Implemented; current behavior is in `status.md` and UI-07 in `requirements.md`. Acceptance text retained until the next commit.

Added 2026-10-14 from play feedback: opening Copper Ore from *This session* → *Farming* goes to its Market page, and getting back means clicking Today, then *This session* again. The desktop window has no browser back button.

As a player, I want a back link on any page I reached from another, so that drilling into an item doesn't lose my place.

Refined 2026-10-14 against the code: Team and Stock have no links to Market items today, and Today's *Today plan* / *This session* view is kept in tab storage, not the URL.

Acceptance:
- **Linking places (as they exist now):** Today to a Market item (*This session* cards, including Farming, and the *Today plan* craft cards and tables), Today's *This session* character name to Team, and Market item to item. Team and Stock gain no new links in this story.
- **Back link:** each of those links carries where it came from in the URL: place, Today tab and Today view. The destination shows *← Back to Today · This session* (or *Today · Plan*, *Market · Linen Cloth*: the place, then the tab, view or item it came from) at the top. Clicking it returns there with the same source. The character doesn't travel in the URL: Today's comes from its saved settings and Team's from its selection, and the back link never changes either. Pages opened directly (place tabs, a typed URL) show no back link, and neither does a place tab clicked from a page that had one.
- **Today's view in the URL:** Today reads its view (*Today plan* or *This session*) from the URL, so a back link and a refresh both reopen *This session*, loaded, not just with its toggle set. Changing the toggle updates the URL without reloading, as the tab already does. Without the parameter Today behaves as now.
- **Chains:** after item-to-item links, the back link returns to the place you started from, not the previous item. Nothing is stored outside the URL. Unknown or invalid origin values show no back link, never an error.
- **Unchanged:** the place tabs, URLs that already work, and refresh keeping your place (UI-07).
- **Offline tests** through the existing NiceGUI harness (`tests/ui_trial/`): back links from Today *This session* (a Farming item and the character link to Team) and from a *Today plan* table, landing on *This session* loaded; an item-to-item chain returning to the start; no back link on direct pages or after a place tab; an invalid origin; refresh keeping both the back link and Today's view.
- **Docs:** UI-07 in `requirements.md`; `status.md`.

### STORY-077 — Mob names (addon, read-only)

Implemented in addon 0.12.6; current behavior is in `status.md` and ADDON-12/UI-13 in `requirements.md`. Awaiting the in-game check (`addon/README.md` → *Last beta play session*, step 7).

Added 2026-10-14 from play feedback: farming spots say *NPC 475*; the Wowhead link works, but the app should say *Kobold Tunneler*. Loot only gives the mob's ID (from its GUID). Best done before 21 October so a beta session confirms it; names don't change at launch.

As a player, I want farming spots to name the mob, so that I know what to go and kill without opening Wowhead.

Acceptance:
- **Addon capture (read-only):** on `LOOT_OPENED`, when `UnitGUID("target")` is a Creature GUID that is one of the window's loot sources, save it with `UnitName("target")` on the loot record. Save nothing when the target is missing, a player, or not a source of this window (no guessing from the mouse or the nearest unit). `safe` calls, no clicks. Bump the addon version.
- **Brownstone:** a name per NPC ID from the newest such record in scope; names are display only and never decide anything (AGENTS.md). Farming spots and *also looted* show *Kobold Tunneler (NPC 475)*, still linking to Wowhead; without a captured name, *NPC 475* as now.
- **Beta report:** the STORY-042 report counts loot windows with a captured name and lists NPC IDs still unnamed.
- **Offline tests:** Lua tests in `tests/test_addon.py` for a matching target, a target that isn't a source, a player target and no target; Python tests for the newest name winning, scope, and the fallback.
- **Check in game** (play actions only, in `addon/README.md` → *Last beta play session*): kill and loot a few mobs as usual (you normally have the mob targeted when you loot it).
- **Docs:** the capture under the ADDON journal rules and UI-13 in `requirements.md`; `design.md`; `status.md`.

### STORY-078 — An item page you can read

Added 2026-10-14 from play feedback on Linen Cloth: the Market item page is one long column. It opens with the crowding rules and every scan-by-scan removal block (15 for Linen Cloth), puts *Made from* and *Used in* below them, and ends with market-wide flood lists about other items. It's hard to answer *what should I do with this item?* This story replaces the item-page half of STORY-021; that story keeps the charts and listing ladder, built into this layout.

As a player, I want an item's page to answer the useful questions first, so that I can decide whether to buy, sell, craft with or farm it.

Acceptance:
- **Summary first,** in one card: price now and typical with the UI-11 label (cheap, high, contested, thin), units listed, vendor buy and sell price, what the team holds (Stock's holdings) and the best use in our catalogs (its top *Used in* craft by profit, or its own craft when it's an output). Each figure keeps its evidence on demand.
- **Where to get it:** your own farming evidence for the item (UI-13 rows and spots: zone, mob, rate per hour and position, newest first), or *not gathered yet*. Always a link to Wowhead's item page for drop sources and places you haven't farmed. Wowhead's drop data isn't imported (no source evidence; CRAFT-08 covers only saved recipe pages).
- **Sections as tabs or headed panels,** in this order: *Summary* · *Crafting* (made from, used in, team eligibility, skill-up demand) · *Market* (crowding and overshoot, removals) · *Identity and evidence*. Removals show the newest three gaps with *show all*; skipped gaps are counted, not listed.
- **Off the item page:** the market-wide lists (*Flood signals in our chains*, *Removed early in our chains*, *What moved since the last scan*) stay on the Market home page only.
- **Rules unchanged:** every label, rule and number stays as now (UI-09, UI-10, UI-11); only the layout and the summary/farming composition are new. The item stays in the URL (STORY-076's back link works).
- **UI-08 checklist** on screenshots of Linen Cloth, an item with no listings, and a crafted output.
- **Offline tests:** the summary's figures and fallbacks (no price, no holdings, not in a catalog), farming evidence for an item and *not gathered yet*, the section order, the removals cut to three with the skipped count, and market-wide lists absent from the item page.
- **Docs:** UI-09 in `requirements.md`; `status.md`.

### STORY-034 — Movement ledger and reconciliation

Added 2026-10-06. Built in Brownstone from STORY-032/033 evidence; can be finished after the beta closes.

As a gold maker, I want one ledger of every item and gold movement across my characters, so that I can see what I actually made, what sells and what I hold.

Acceptance:
- **One movement table:** time, character, machine, item or gold, signed quantity, reason (auction buy, post, sale, expiry, cancel, deposit, mail in and out, craft in and out, vendor buy and sell, gathered) and links to the journal entry it came from. Every other view (profit, holdings, sell-through) is derived from it. The rules mapping events to movements are recorded in `requirements.md` with a version, like ADDON-10.
- **Sales from the mailbox:** an invoice is the only proof of a sale. A listing that vanishes is still only *removed* (STORY-027).
- **Reconciliation:** between two snapshots of a character, actual change minus recorded movements is the residual. A positive item residual is *gathered or looted*; negative is *used or destroyed*; a gold residual is *other income or spending* (quests, repairs, training), kept apart from trading profit. Residuals are shown, never hidden, so a missing journal shows up.
- **Integer copper,** all characters kept separate unless summed explicitly, and the 5% (or 15% neutral) cut taken from invoices, not assumed.
- **Offline tests** from beta fixtures: a full buy → craft → post → sale cycle, an expiry, a mail between characters and a gathering residual.
- **Across machines** (moved from STORY-037): mail between characters on different machines appears once as sent and once as received; a missing drop shows as an unmatched mail.
- **Known gold categories** (added 2026-10-14 from Journalator): gold in and out by category (auction sales and purchases, deposits, vendor, repairs, training, flights, quests, mail) by day and character, from the events the journal already records. Only what no event explains stays in the *other* residual.
- **Sale rate:** reuse STORY-073's per-item results rather than computing them again.

### STORY-035 — Auction deposits

Added 2026-10-06.

As a gold maker, I want Today's *Sell* list to show the deposit for posting and what an expiry would lose, so that profit at undercut isn't overstated for cheap or slow items.

Acceptance:
- **Formula from evidence:** the beta tests under *Now* record the deposit for a few posts of known vendor price, stack size and duration. The formula is recorded in `requirements.md` with that evidence; if it can't be confirmed, deposits stay *not modeled*.
- **Shown, not ranked:** Today's *Sell* shows the deposit for the planned post and the loss if it expires. Ranking stays on batch profit (the deposit is refunded on a sale) until sell-through data exists (STORY-034).
- Needs the item's vendor price (STORY-031); missing vendor price shows *deposit unknown*, never zero.
- **Formula to test** (added 2026-10-14 from aux, a Classic addon): deposit = vendor sell price × 5% (25% neutral) × stack size, rounded down, × hours ÷ 2 for the duration. The 2026-10-10 post below already contradicts it (100c against about 3c), which points to a minimum deposit on Forever; test both against all captured posts.

**Beta evidence so far (2026-10-10):** one post: 5 Linen Cloth (vendor 13c) cost a **100c** deposit, more than a Classic-style formula gives (`PostCommodity` with duration argument 3; money went 145c → 45c; status 1 *sold* 30 s later, no invoice mail captured yet). **Next play session** (play actions only; Claude checks the file): post an item worth more to a vendor (a stack of 5 and a single, for example Bolt of Linen Cloth or a crafted shirt) once at each of the three durations; post one more stack of Linen Cloth at the shortest duration; then open the mailbox after the sale and take the gold. That separates a minimum from the per-vendor-value rate and duration, and times the sale-to-mail delay.

### STORY-036 — Vendor price ceilings

Added 2026-10-06. Waits for the in-game check under *Now*. Trade-supplies reagents in every Forever catalog were marked as vendor items on 2026-10-13 from the saved pages' buy prices, unconfirmed except Coarse Thread (`status.md` → *Limitations*); this story confirms them and adds the caps.

As a gold maker, I want items a vendor sells at a fixed price to be capped at that price, so that the board never values them above it or suggests buying them for more.

Acceptance:
- **Vendor items with evidence:** each confirmed vendor item (regular trade goods, and the Black Market vendor's list if it exists) is marked as a vendor item with its price and where it was seen, per CRAFT-08. Unconfirmed claims are never entered.
- **Buying:** already capped by CRAFT-03's cheapest route; Today's *Buy* never lists an auction purchase above the vendor price.
- **Selling:** a sale value above the vendor price is capped at it, with a label, and the rule is recorded in `requirements.md`.
- **Limited stock** (if the vendor has any) is noted, since vendor stock is otherwise *not modeled*.

### STORY-044 — Brownstone panel from a minimap button

Added 2026-10-07 (product owner: "it would be a lot easier to just hit those as needed", wanted before the next play session). Addon only, plus one Brownstone regression test. **Reverses the STORY-029 visibility decision** (`addon/README.md` → *Reload and clear controls*: controls only with the auction house open, no persistent panel); the auction-house button row stays as it is.

As the product owner, I want a minimap button that opens a small panel with the Brownstone buttons and the routine written on it, so that I don't have to remember slash commands or open the auction house to reload and clear.

Acceptance:
- **Minimap button:** a small round button on the minimap edge, made with the client's own frame API (no third-party library such as LibDBIcon). Left-click toggles the panel; the tooltip says "Brownstone Scan" and "Click: open panel. Drag: move". Dragging moves it around the minimap edge; its angle is saved in a new `BrownstoneScanDB.ui` table (`minimap_angle`, a number). `/bscan panel` also toggles the panel, so it works if another addon hides minimap buttons.
- **Panel:** a small movable window (Escape closes it) with a title, a status block, the buttons and the routine. It is a convenience view only: it captures nothing new and never clicks anything itself.
  - **Status**, refreshed when the panel opens and after each panel action: saved scans in the file and how many from this session aren't written yet; character snapshots; journal entries as `N / 10,000`, highlighted from 8,000, with the skipped count when the overflow marker exists; whether this login's time is known (when it isn't, Clear keeps everything, as today).
  - **Buttons:** *Reload* (same function and guard as the existing Reload button); *Clear saved data* (the same confirmation popup and every existing guard: refuses with unsaved scans or during a scan or item info pass, never uses the `all` override); *Status* (prints the existing `/bscan status` output to chat); *Start scan*, enabled only while the auction house is open and no scan or item pass is running, calling the existing start. Reload, Clear and Start are disabled exactly when the auction-house buttons are.
  - **Routine** in short plain text: "1. Play. 2. Reload (or log out) so the game writes the file. 3. Import on the computer. 4. Clear, then Reload. Clear keeps this login's journal and snapshots; they import again harmlessly as duplicates."
- **Unchanged:** file format 6, scan format 4, every record and its fields, the journal, snapshot and clear rules (ADDON-11, ADDON-12), the auction-house buttons and the slash commands. The addon stays read-only: no buying, posting, unattended scanning or timers that act. Addon version becomes **0.9.0** (toc, `ADDON_VERSION`, README title).
- **Brownstone:** preview, import and `beta-report` ignore the `ui` table; a test proves a format-6 file with `ui` imports and reports exactly as without it.
- **Offline tests** in the existing Lua harness (`tests/test_addon.py`, `tests/fixtures/addon_harness.lua`): the panel's buttons call the same functions as the auction-house buttons (Clear refuses with an unsaved scan, shows the popup otherwise; Reload calls `ReloadUI`; Start is disabled with the house closed and during a scan); the status numbers, the 8,000 highlight and the overflow skipped count; the saved angle survives a reload; `/bscan panel` toggles; opening the panel adds no journal entry, snapshot or scan.
- **Docs:** `addon/README.md` gets a short *Panel* section (replacing the visibility decision) and an in-game check written as play actions only: click the minimap button, open and close the panel, drag the button and reload, press each button once. `requirements.md` records the panel as a convenience view with the existing guards; `status.md` describes the current state.

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

### STORY-026 — Scan coverage and your play rhythm

As a gold maker, I want to see when I've scanned and when I usually play, so that I know which times are covered and when it's worth making time to log in.

Acceptance:
- **Coverage grid:** scans by hour and weekday in local time for the selected source, with counts and gaps.
- **Your rhythm:** the hours and days you usually scan, from scan times only.
- **What's missing:** which slots need scans before timing claims can be made, with the thresholds recorded in `requirements.md`.
- Works on beta scans now. Depends on nothing (uses `addon_scans`). Feeds *Plan ahead* under Later.

### STORY-062 — Sales speed and suggested stock levels

Added 2026-10-13 (product owner: "turnover, how fast items sell in the market is really kind of the point… I don't know how else you determine how much stock or inventory you keep"). Brownstone only. Needs STORY-027 and enough consecutive scans: refine the minimum before handoff with the beta's scan count. Draft.

As the owner, I want to see how fast each item moves on the auction house and a suggested stock level from it, so that targets come from evidence instead of guesses.

Acceptance:
- **Removal rate** per item from STORY-027: units removed per hour across consecutive scan pairs within the maximum gap, as a median with the number of scan pairs it rests on. Always *removed*, an upper bound on sales, never *sold*. Too few pairs says so instead of a number.
- **Turnover:** listed units divided by the removal rate (how long today's supply would last), shown beside it.
- **Suggested target** in STORY-061: removal rate × the days of cover the owner chooses (one setting), capped at a share of typical listed supply so we never plan to hold more than the market moves. Shown next to the manual target, never replacing it.
- **Shown** on the Market explorer's item page (STORY-055) and in Stock (STORY-061).
- Feeds *Sales speed instead of a fixed cap* (Later) for Today, which stays a separate story.

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

## Later

**Optional client-version cutover guard:** investigate whether recorded client versions can flag a misconfigured beta/live source during STORY-020b and first live imports. Source configuration remains authoritative (DATA-03); STORY-017 adds no client-version evidence checks.

These are grouped by what unblocks them.

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
- *Removed listings* (STORY-027) is implemented; the time-left beta check is pending above.
- **Did the board hold up?** Whether "potential craft" rows were still profitable at the next scan. A tiny check is possible with beta scans; it means something after one to two weeks of live scans.

**Market timing and a daily brief** (requested 2026-10-04; needs post-launch history, not beta scans (STORY-017)). The goal is to know when to buy and sell each kind of item (materials, crafted goods, equipment), and to open the app to a short list of the day's priorities without being online all day.
- **Honest limits:** scans happen only when you are at the auction house, so hour-of-day and weekday patterns are sampled at your playtimes. A pattern is shown only with its coverage (scans per hour and weekday), and claimed only where coverage is enough. Weekday effects such as the weekly reset need at least four weeks. Optional sources (STORY-011b) could fill hours you don't scan.
- **Steps** (each needs the one before):
  1. **Scan coverage:** now STORY-026 in Next.
  2. **Timing profile:** per item, and for groups by catalog role (material, intermediate, finished; never inferred from names), price and supply by hour and weekday, with a confidence label. A weekday chart overlays price against supply (units listed, never called demand or volume sold). "Cheapest to buy" and "best to sell" windows only where coverage supports them.
  3. **Daily brief:** STORY-025 (*Today*) is its rule-based first version on the newest scan. This step adds the timing profile's advice: what to buy now or hold, and what to post now or wait on, each with its coverage.
  4. **Plan ahead** (requested 2026-10-05): next-day planning, not only right now.
     - **When to log in:** suggested sessions that combine your usual play times (STORY-026) with the hours the timing profile marks as best to buy or sell, and how much each session is worth on current evidence.
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
- **Market for our levels** (walkthrough 2026-10-13): Market's front-page lists were dominated by Wool, Silk and Mithril-level items while the team was level 1–8. Filter or order them by the skill bands the team can reach (Team's window), with the full lists one click away.
- **Plain identity labels** (walkthrough 2026-10-13): *base* and *unresolved* tags, and items listed twice under each, mean nothing to a player. Say *variant* or *unidentified link* only where it matters, keeping identities separate (ADDON-08).
- **Shorter removal history** (walkthrough 2026-10-13): an item page lists every scan gap, mostly zeros. Summarise (removed early and could-have-expired totals over the comparable gaps), with each gap on demand.
- **Vendor value as a floor** (2026-10-14, from CraftProfit's *vendor net* and TSM's posting rules): for leveling crafts whose auction market is flooded, show what the output fetches from a vendor (vendor sell price × output − cost) beside the auction profit. *Sell* never suggests a post price at or below the vendor price ÷ (1 − cut); it says *vendor it instead*.
- **Buy a pattern to level cheaper** (2026-10-14, from ProfessionMaster): when a recipe item listed on the auction house would make a CRAFT-11 reach path cheaper including its price, show it as an option. Today such recipes are excluded as *needs pattern or other source*.
- **Green recipes when much cheaper** (2026-10-14, from ProfessionMaster): allow a green recipe in a reach path only when every orange and yellow option costs more than twice as much per point, labelled as uncertain.
- **Confirm skill-up colours from our own captures** (2026-10-14): the addon already records each recipe's difficulty in the profession window at the captured rank. Compare that with the catalog's colour ranks to confirm or contradict the Classic estimates on Forever, as evidence for the catalog (ProfessionMaster ships a Forever recipe table, but it's all rights reserved, so we gather our own).
- **Mail and auction expiry warnings** (2026-10-14, from TSM's task list): items or gold in a captured mailbox close to its 30-day expiry, and your auctions about to end.
- **Vendor the junk** (walkthrough 2026-10-13): Stock showed 20 of 43 held items with no price, mostly vendor trash. Suggest vendoring held items with a vendor price and no auction price, using captured vendor prices only.
- **Best use of a material:** for an item such as Linen or Wool Cloth, compare selling it with each craft it feeds, at current prices.
- **Value-add chart** (suggested 2026-10-04): in the recipe explanation, a tier-by-tier waterfall from raw materials through intermediates to the finished item. It shows cost added and the sale value at each tier where it's listed (an unlisted tier shows no value, never zero), so you can see where the margin is made. It draws from the existing `crafting.py` calculation, never a second costing path in SQL. Cross-profession chains wait for STORY-015b.

**Your own character's data** (approved 2026-10-06; capture is STORY-032/033 and the ledger STORY-034 in Next). Once those exist:
- **Known recipes and skill:** moved to Next on 2026-10-07 as STORY-041 (capture) and STORY-043 (Today); 2026-10-09 added STORY-049 (Forever capture), STORY-051 (Characters) and STORY-052 (progression; *what can I learn next*). Still here: the Action Board filtered to what you can make.
- **Profession page** (added 2026-10-09, product owner): drill into one profession: every catalog recipe by skill band, with each character's status (known, train now, not yet), how it's learned, profit from the newest scan and its materials; linking to the item page (STORY-021). Builds on STORY-043, STORY-050 and STORY-052.
- **Calibrate removed listings:** your own sales from invoices show how many *removed* listings (STORY-027) were real sales.

**Ledger analytics** (from the 2026-10-06 design notes; each needs STORY-034 and some weeks of your own sales):
- **Sell-through and fill chance:** for each of your posts, its premium over the lowest price at posting, and whether and when it sold. Start with simple buckets (how often posts at 0–5%, 5–15% … above the lowest sold within their duration); more refined models only once there is enough data.
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
- **Mail between your own characters:** count postage as a cost in the ledger (STORY-034), and when a plan moves materials to the character with the right profession, include that postage. The amount is a beta check under *Now*.

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
