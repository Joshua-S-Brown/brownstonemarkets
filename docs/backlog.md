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

Nothing in progress; the next story is the top of *Order* under Next: held materials say what to do and what they're for (STORY-095). Every place is in the web app (STORY-082 to STORY-086), the shared components exist (STORY-089: `web/src/ui`, kit at `/app/kit`) and Today follows the prototype (STORY-088); STORY-090 to STORY-094 bring the remaining pages and records to it.

**Before STORY-081:** done 2026-10-16. Node.js 24 LTS (v24.22.0, npm 11.19.1) is installed on the Mac in `/usr/local/bin`. The Windows PC needs nothing: it only plays and drops scans (OPS-03).


Scan format 3 (STORY-023) and the reload/clear buttons (STORY-029) are accepted on the beta with addon 0.3.1; the measurement record is in `addon/README.md`. Brownstone can now run on our own addon scans alone (STORY-010). Launch market remains Forever US, Roleplaying, Alliance (`forever-us-roleplaying-alliance`); the beta currently offers only Normal servers, so the configured example source is `forever-us-normal-alliance`.

**Through the last full beta testing day, 21 October** (manual, in game):
- **Keep scanning.** Twenty-five complete scans of the Normal Alliance house are imported (`status.md` → *Limitations*). Take more, at least 15 minutes apart, **at different times of day and on different days**, so the diff and timing work (STORY-018; *Market timing and a daily brief* under Later) has something to start from. The routine: scan, `/reload` (the game writes scans to the file only then, or on logout), import, and only then `/bscan clear` and `/reload`. A Roleplaying or neutral house scan, if reachable, tests house identification. This is a manual habit, not automation.
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
  - **Unconfirmed claims** (`requirements.md` → *Product direction*): time from a sale to its gold in the mailbox, The Black Market vendor waits for live (*Later*). Deposits and postage between your own characters were measured on 2026-10-15.

## Next

**Agreed order (groomed 2026-10-05):** the app is almost all tables today, so user-facing analysis now gets its own lane in Next instead of waiting behind launch preparation. The layers, each building on the one before:
- **Scans** (exists) → **market metrics** (exists; ADDON-10 in `requirements.md`) → **analysis views** (item page, charts, sellers) and the **Today** page (what to buy, craft and sell now).
- An optional AI narration layer can come later. It may only explain those defined metrics, never invent numbers (*Out of scope*).
- Time-of-day and weekday patterns need weeks of live scans (*Market timing* under Later). Everything in Next works on a single scan or a few, so it can be built and tested on beta scans now.

**Order** (regroomed 2026-10-13 after Claude's player walkthrough of the beta data, 2026-10-14 after the addon comparison, and 2026-10-15):
1. STORY-095 held materials say what to do and what they're for
2. STORY-090 Market that leads with what moved
3. STORY-091 Team and Ledger as the prototype drew them
4. STORY-092 Supply chains as the prototype drew it
5. STORY-093 item and character records as the prototype drew them
6. STORY-094 Level up as the prototype drew it
7. STORY-087 retire NiceGUI
8. STORY-062 sales speed and suggested stock levels (STORY-027's time-left bounds accepted 2026-10-16; refine first)
9. STORY-026 scan coverage and rhythm
10. STORY-028 sellers and supply chains (blocked: see *Seller capture* under Later)
11. STORY-006 replay

**Web app lane (decided 2026-10-16, product owner):** NiceGUI still felt like stacked, scrolling containers rather than an application. The owner approved the clickable prototype in `docs/prototype/web-app.html` (open it in a browser; its figures are examples) as the direction: an app shell, an inspector that opens records in place, and Today as one route. The rules are UI-18 in `requirements.md` and the structure is *Web app (UI-18)* in `design.md`. Each story moves one place and removes its NiceGUI view, so the app works at every step and launch never waits on the whole migration. Each web story keeps calculations, `today_version` and rules unchanged unless it says otherwise. Its real-data check is a side-by-side comparison with the NiceGUI page on the same source and scan: same numbers, same evidence.

**Pending an in-game beta check:** none. STORY-027's time-left bounds were accepted on 2026-10-16; STORY-044, 071 and 077 were confirmed on 2026-10-15; STORY-031, 032, 033 and 040 on 2026-10-13 (`status.md`).

**Done** (outcomes in `status.md` and `requirements.md`; story text in Git): STORY-015b, 021, 025, 030, 031, 032, 033, 034, 034b, 035, 036, 037, 038, 039, 040, 041, 042, 043, 044, 045, 046, 047, 048, 049, 050, 051, 052, 053, 054, 055, 056, 057, 058, 059, 060, 061, 063, 064, 065, 066, 067, 068, 069, 070, 071, 072, 073, 074, 075, 076, 077, 078, 079, 080, 081, 082, 083, 084, 085, 086, 088, 089 and SPIKE-009/009b.

### STORY-095 — Held materials say what to do and what they're for

Added 2026-10-17 from the owner's first look at the STORY-088 Today. The Route opens with *take* steps that give no instruction: *Baspion · bags: Take 7 × Linen Cloth*, *Take 6 × Rough Stone*. For bags these aren't actions at all: the items are already in the bags. Each take is grouped by item in `today_holdings.queue_lines`, which drops which craft the units are for. The real action is either nothing (the crafter already holds them), a mail (another character holds them; that mail line comes several stops later), or a bank withdrawal. The plan already knows each allocation's craft: every row's `held_allocations` lists holder, location, units and recipient.

On the current beta copy (17 Oct, with Baspion):
- **Copper Dagger ×3 (Arille)** uses 6 Rough Stone from Baspion's bags and 6 Copper Bar from Arille's own bags.
- **White Linen Robe ×5 (Basilly)** uses 8 Bolt of Linen Cloth from Basilly's own bags and 7 from Cicelyna's.
- **Linen Bag ×5 (Basilly)** uses 7 Bolt from Cicelyna, and Linen Cloth from Baspion (7), Cicelyna (3) and Keenagen (6).

UI-18 presentation and the Queue wording only. Allocation, reservations, costs and the held-unit valuation rule are unchanged.

As the owner, I want every held-material step to say what to do and which craft it feeds, so that I never wonder what *take* means.

Acceptance:
- **No step for what's already in place:** units in the crafter's own bags are not a Queue step. The craft line says so instead (*Craft 3 × Copper Dagger · uses 6 Copper Bar you hold*), and the crafter's take stop disappears.
- **Mail is the action for another character's bags:** no separate take line. The mail line is the step and names its purpose: *Baspion: mail 6 Rough Stone to Arille, for Copper Dagger*. A holder's mails stay together in one mailbox stop, in today's order.
- **Bank is a real step:** units in a bank keep a take step, worded *Take 8 Bolt of Linen Cloth out of the bank, for White Linen Robe*. When they're for someone else, the step adds *then mail them to Basilly* and the mail line follows in the same stop.
- **Purpose:** each held step names the crafts it feeds, by output name, and the step number of the first craft (*for Linen Bag (step 9)*). Use the allocations' crafts, not a guess by item. An item feeding two crafts names both (*for White Linen Robe and Linen Bag*).
- **Queue text and ticks:** *Copy as text* uses the same wording. The Queue identity changes with the wording, so existing ticks reset once through the existing path. No `today_version` change unless the Today rules require it; if they do, say so under Deviations.
- **Rule:** `requirements.md` → Today → *Held materials* replaces *Queue starts with take lines by character/place…* with the new behaviour: no step for the crafter's own bags; mail as the step for other bags; bank takes; purpose named. It has 123 bytes of headroom, so rewrite that sentence in place and trim the bullet by at least as much as you add.
- **Offline tests:**
  - own-bags units become a craft-line note with no step;
  - another holder's bags give one mail step, no take step, with its purpose;
  - a bank take for self and a bank take for another (take then mail, same stop);
  - one item feeding two crafts;
  - Queue order otherwise unchanged;
  - copy text matching the Route;
  - allocations, costs and reservations byte-for-byte unchanged (compare `build_today` results before and after, minus the line text).
- **Real data:** beta copy of the current `data/`.
  - Route expectation: no *bags* take stops; Baspion's mailbox stop shows *mail 7 Linen Cloth to Basilly, for Linen Bag* and *mail 6 Rough Stone to Arille, for Copper Dagger*; Arille's Copper Dagger line says it uses 6 Copper Bar you hold.
  - The step count drops by the take lines removed. Planned profit and spend are unchanged from the same copy before the change.
  - Screenshots at 1280 and 390 px.
- Depends on STORY-088. Rules: Today (*Held materials*, *Queue*, *Presentation (UI-18)*), UI-18. Design: *Today contracts*.

### STORY-090 — Market that leads with what moved

Added 2026-10-16 after the owner walk-through. Market's data is right but the page doesn't answer *What is the market telling me?* at a glance: the signal cards show bare percentages with no price or trend, *Left early* leads with ammunition (6,929 Crafted Heavy Shot), and the grid opens alphabetically (*Accurate Scope*, *Anti-Venom*…) with most items listed twice (*base* and *unresolved*), 1,204 rows over 41 pages, and a *Stored lowest* column that is empty on the beta copy. Presentation only: UI-09, UI-11 and ADDON-08 selection and ordering rules are unchanged. Built with STORY-089's components.

As the owner, I want Market to show me what moved and why it matters to our chains, so that I can spot a buy or a sell in seconds.

Acceptance:
- **Head:** `PageHead` with the scan, item count and age (*779 listed now of 2,290 items in our chains* stays as the subtitle's fact).
- **Signal cards:** *Cheaper than usual*, *Dearer than usual* and *Left early* as three `Panel`s like the prototype: the top three rows each (UI-11's existing order and selection), *N more* expanding to the rest. Each row: `ItemLink` with badge, price now and typical (`Money`), the signed % vs typical, and a sparkline from UI-17 stored history when it has two or more points. *Left early* rows show units and its caption *bought or cancelled; an upper bound on sales*. Rows outside our chains are marked so.
- **Grid:** one row per item: the base (or legacy) identity is the row; other identities of the same item sit under it, collapsed behind *+N variants/unresolved*, each still its own row with its own prices when opened (ADDON-08: never pooled, never summed). Default sort is the absolute gap to typical, largest first, unknown gaps last; columns as the prototype: Item, Lowest, Typical, vs typical, history sparkline (replacing *Stored lowest*: if the column is empty because of a bug, say so in the report and fix it or drop it), Listings, Units, Signal (`SignalPill`). Filter chips (*All in our chains*, *Materials*, *Crafts and intermediates*, *With a signal*) and a name-or-ID filter in the grid's panel header. Sorting and grouping happen in `brownstone`/`api` projections, not the web.
- **Caveat:** *Listings are supply, not sales* once in the subtitle; the rest of today's caveats move to the page's evidence footer.
- **Offline tests:** grouping keeps identities separate (prices and units per identity unchanged, none summed); default sort with unknown gaps last; cards' three-plus-more with UI-11 order kept; sparkline absent below two points.
- **Docs:** UI-09's presentation sentence describes the grouped grid and cards; trim `requirements.md` by at least as much as you add. `status.md` → *Market*.
- **Real data:** beta copy, scan `20261016T113727Z-eb77d0`: report the item-row count against the 1,204 identity rows, the top three of each card, and the first ten grid rows; open Linen Cloth's record from the grid. Screenshots at 1280 and 390 px beside the prototype's Market.
- Depends on STORY-089. Rules: UI-09, UI-11, UI-17, ADDON-08, UI-18. Design: *Web app (UI-18)*.

### STORY-091 — Team and Ledger as the prototype drew them

Added 2026-10-16 after the owner walk-through. Team reads as text: no skill bars, profession coverage as a sentence list, *Cost to 300* and *Instead of a new hire* as paragraphs, a look-ahead slider and a caveat paragraph before the answer, and the best line on the page (*Blacksmithing: Cloudy Skyforged Wristguards · +19 points · 4s 5c*) in plain text. Ledger's summary and chart are decent, but zeros print as coin-coloured *0c*, categories are lowercase, and a long per-character table dominates where the prototype has four tiles and a *By category* panel beside the chart. Presentation only, built with STORY-089's components.

As the owner, I want Team and Ledger to answer their questions in the first screen, so that I can see who should do what, and where our gold went, without reading.

Acceptance:
- **Team roster:** cards like the prototype: initials avatar, name (`CharacterName`), level, last seen and gold; each profession as a skill bar (rank of the tier maximum, with a marker at the next tier); one *next step* line per card (the best one, styled as an action); the other next steps and *incomplete* reasons in the card's `Tip` and record. Characters with no profession say *Learn a profession to see what's in reach* as an action line.
- **Team coverage:** a matrix (professions × characters, rank in each covered cell, *Not covered* pill in the last column), not a list. Gathering professions without a catalog keep their note in a `Tip`.
- **Team hiring:** *If we add a character* and *Instead of a new hire* as tables (profession, best per craft at 300, team holder, estimate *Complete*/*Incomplete* pill with its reason in a `Tip`). The look-ahead slider moves into its panel header; the caveat paragraph moves to the evidence footer.
- **Ledger summary:** four `Tile`s: *Came in*, *Went out*, *Net* (caption: *N of M bags pairs reconcile*) and *Held stock* (caption: *at listed prices · N no-price items*), for the selected days.
- **Ledger flow:** the daily chart as the prototype's diverging bars (in above, out below the axis), and beside it a *By category* panel: capitalised category names, signed money, and each category's movement count (add the count to `ledger_view`'s category rows, with a test). Zero shows muted, not coin-coloured. The per-character/day table moves behind a *By character and day* disclosure using `CharacterName`.
- **Ledger Items and Restock:** each a `Panel` with its tiles first and its tables after, keeping STORY-085's filters, provenance and evidence.
- **Offline tests:** skill bar maths (rank/maximum, unknown maximum shows no bar), matrix cells from Team's existing coverage data, hiring table rows, category counts, zero muted, the disclosure keeping the per-character table.
- **Docs:** `requirements.md` → UI-18 or the Team/Ledger rules only where wording names the old layout (trim as much as you add); `status.md` → *Team* and *Ledger*.
- **Real data:** beta copy, scan `20261016T113727Z-eb77d0`: Team shows 5 characters, Arille's Blacksmithing 31/75 and Mining 48/75 bars, Basilly's Tailoring 32/75, and Arille's next step *Cloudy Skyforged Wristguards +19 points 4s 5c*; Ledger with *All* days shows in 5,878c, out 4,079c, net 1,799c, 76 of 76 pairs, and STORY-085's category totals with counts. Screenshots at 1280 and 390 px beside the prototype's Team and Ledger.
- Depends on STORY-089. Rules: UI-15, UI-16, UI-18, CRAFT-11, *Stock*. Design: *Web app (UI-18)*, *Stock contracts*.

### STORY-092 — Supply chains as the prototype drew it

Added 2026-10-16 from the STORY-086 review's usability pass on the beta copy. The engine, numbers and Add to tonight are right (Linen Bag 156c/34c; forcing Bolt to buy gives 180c/10c; Add to tonight puts Linen Bag in Today's route). But the page:
- opens on Azure Skyforged Pauldrons, which nobody on the team can make: all ten ranked chips are top Board profits, none from the team's professions at its ranks;
- has ten chips that fill the whole first screen at 390 px;
- draws fixed 360 px node cards, so a three-material route like Linen Bag needs about two screens of mostly empty card;
- draws a waterfall of unlabelled bars above a separate text list;
- puts Batch and Add to tonight below the fold, in one long column.

Presentation and ordering only: no costing change. Built with STORY-089's components.

As a gold maker, I want the route, its margin and the batch on one screen, starting from something we can make, so that I can decide buy-or-craft without scrolling.

Acceptance:
- **Starting point:** ranked chips put crafts the team can make tonight first (any character Known or Train now, from the same `recipe_status` evidence the nodes show), then the rest marked *no one on the team can make this yet* with the reason in a `Tip`. The page opens on the first makeable one; with none, it opens on the first ranked and says so. Ordering within each group stays the Board's. Chips scroll horizontally on narrow screens (one row), with the search beside them.
- **Layout:** the prototype's two columns at 1100 px and wider: the route `Panel` on the left; *Per craft* and *Batch* `Panel`s stacked on the right. Narrower: route, then Per craft, then Batch. `PageHead` with the basis and scan in the eyebrow and the forcing note as a muted line.
- **Nodes:** cards size to their content (the prototype's ~210 × 110 px), with name, unit cost, the route toggle (or *Vendor* / *Auction House · N listings*), maker and held count; team recipe status in a `Tip`, not an open list. Edges are curves with ×N labels, solid along the chosen craft path and dashed into unchosen branches, as in the prototype. The output node says *Sells at* with the sale price and an *Output* pill.
- **Waterfall:** one list of rows, each with its label, quantity × unit cost and signed amount, and a bar inside the row scaled to the sale price; the profit row is a total row. No separate unlabelled chart. A missing price still stops it at that row with its reason.
- **Batch:** the slider with the number shown big beside it, leaf quantities, spend and profit, and *Add to tonight* as the panel's primary action. The result names Today's reason in plain words.
- **UI-08 and UI-18 screenshots:** 1280 and 390 px beside the prototype's Supply chains; the route, Per craft and Batch for Linen Bag fit in one screen at 1280×860.
- **Offline tests:** makeable-first ordering, keeping the Board order within each group; the opening choice with and without a makeable craft; waterfall rows summing to profit as now; edge styles for chosen and unchosen branches; layout breakpoints in Vitest.
- **Real data:** beta copy, scan `20261016T113727Z-eb77d0`: the first chip is a craft Basilly or Arille can make (report which), Linen Bag and Sandpaper match STORY-086's numbers, and the 1280 px screenshot shows the whole Linen Bag answer without scrolling.
- Depends on STORY-086 and STORY-089. Rules: CRAFT-03, CRAFT-12, UI-08, UI-18. Design: *Web app (UI-18)*.

### STORY-093 — Item and character records as the prototype drew them

Added 2026-10-16 from the full owner review of the inspector records against the prototype's `ItemInspector` and `CharInspector`. Both records hold the right evidence but read as dumps.
- **Item record:**
  - seven large tiles push the tabs down, and the tabs wrap onto two lines;
  - the subtitle says *Quality 1 · base-item Overview* on every tab;
  - Price history plots three similar-coloured lines on two unlabelled axes;
  - Listings' scan picker shows *2026-10-16T11:37:31.000Z UTC*;
  - Our activity prints *newest sale 2026-10-11T10:56:31.000Z*, and its holdings line ends in a stray *·*;
  - Used in reads *1 units per craft · potential craft*.
- **Character record:**
  - Professions prints *Window list: 2026-10-15T10:54:16+00:00 · window list + seen crafted* and a stray *observed*;
  - Path's seven-column table is crushed into the record, wrapping *Cloudy Skyforged Wristguards* a few letters per line;
  - Holdings opens with a raw capture dump (*Snapshot id 6:Arille18:…*, *Age hours 38.006*, *Partial no*) before the items;
  - History's chart uses one colour for every series, and its table leads with ISO times and a *Sequence* column.

Presentation only, built with STORY-089's components. Every fact stays reachable, the evidence in footers and tips.

As the owner, I want a record to tell me what an item or character is and what to do with it at a glance, so that clicking a name is worth it.

Acceptance:
- **Shared:** the record panel keeps the prototype's width at 1280 px and goes full-screen under 600 px. Its header is the badge or avatar, name and one muted line (item: role from compatible catalogs, *Material*, *Craft* or *Intermediate*, and the ID; character: level, last seen and machine), then a three-fact strip, then tabs on one line (scrolling on narrow screens), then the tab body, then an evidence footer. Times use STORY-089's `UtcTime`.
- **Item Overview:** facts *Lowest*, *Typical* and *Listings · units*, plus the UI-11 signal as a `SignalPill` in the header. Then the stored-history price line with *typical* as a dashed reference and units as bars, as the prototype draws it. Then a key-value list: where to get it, vendor buy and sell, the post deposit, and team holdings with the *at least* rule. *Best use* and farming spots follow as panels, with NPC names where known and *NPC N* only in evidence. The fixed subtitle bug: the header never names the tab.
- **Item tabs:** Price history gets one colour per series with a legend, labelled axes (unit price; units listed) and `UtcTime` ticks. Listings' scan picker uses `UtcTime`. Made from and used in shows profession names capitalised, *N units per craft* (singular and plural), the Board's action label in words (*potential craft* becomes the UI-09 wording, unchanged in meaning), and STORY-086's *Open in Supply chains* link. Our activity: `UtcTime`, no trailing separators, sales as a small table (character, sold of posted, each after cut, newest).
- **Character Professions:** facts *Gold*, *Professions* and *Known recipes*. Each profession is a `skillbar` with *N points before this tier caps*. The window-list and seen-crafted evidence moves into a `Tip`.
- **Character Path:** per profession, the best next recipe as a highlighted row (recipe, skill needed, cost to reach, earns per craft, where learned), then the other reachable recipes as a compact list with at most four columns (recipe, skill, cost to reach, earns per craft). Points, confidence and where learned sit in each row's `Tip`. No column narrower than its longest word.
- **Character Holdings:** items first, grouped by location (bags, bank) with units and `Identity` pills, *at least* where a location is unknown or partial. Each capture's metadata (snapshot, age, machine, partial, excluded) goes to the evidence footer.
- **Character History:** one colour per series with a legend and `UtcTime` axis ticks. The table goes behind *All readings* with `UtcTime` and no *Sequence* column (that moves to evidence).
- **Offline tests:** header facts for item and character, the subtitle not naming the tab, unit pluralisation, Path rows within four columns, Holdings ordering before evidence, distinct series colours, and no ISO timestamp in rendered record text (Vitest fixtures).
- **Real data:** beta copy, scan `20261016T113727Z-eb77d0`.
  - Linen Cloth 2589: lowest 20c, typical 20c, 219 listings · 5,538 units, *contested*, held at least 11.
  - Arille: Blacksmithing 31/75, Mining 48/75; Path's best next recipe is Cloudy Skyforged Wristguards (skill 50, 4s 5c to reach, 92s 50c per craft); Holdings has 75 bag units and an unknown bank.
  - Screenshots at 1280 and 390 px beside the prototype's item and character records.
- Depends on STORY-089. Rules: UI-09, UI-11, UI-13, UI-14, UI-17, UI-18, CRAFT-11, ADDON-08. Design: *Web app (UI-18)*.

### STORY-094 — Level up as the prototype drew it

Added 2026-10-17 from the STORY-088 review. Today's Route and Opportunities now follow the prototype, but Level up is still a long text column: each character's `→` lines, then every tier with every recipe and its evidence disclosure, below the fold. The prototype's Level up view (`docs/prototype/web-app.html` → Today → *Level up*, the `LevelUp` component and `.lvl-grid`) gives one card per character and profession instead:
- the profession and rank, and an *about +N skill* pill;
- *Make N* with the recipe as an `ItemLink`;
- the skill-up colour band (orange, yellow, green, grey) with *you are at N* marked;
- *Materials* and *Net after selling* in copper, and a one-line note.

Presentation only, built with STORY-089's components (`Panel`, `CharacterName` avatar, `SkillBand`, `Money`, `ItemLink`). UI-12, UI-13, CRAFT-10 and CRAFT-11 numbers are unchanged.

As a gold maker, I want each character's best levelling step as one card, so that I can see who should level what tonight without reading a list.

Acceptance:
- **Cards:** `.lvl-grid` of cards, one per character and profession that has a next step: avatar and name, profession and rank (`rank / tier maximum`), and an *about +N skill* pill from the existing UI-12 points estimate. Then *Make N* `ItemLink`, the `SkillBand` with the four colour ranges and the character's rank marked, *Materials* (`Money`), *Net after selling* (signed `Money`, *unknown* when a price is missing) and the existing note (*Sells for a profit while it levels*, *uses held …*, *a small loss*) where Level up has one. Characters or professions without a valued step get a short card saying why (*no valued recipe in reach*, *learn a profession*).
- **Detail stays reachable:** the current tier list (each *Reach N* group with its recipes, *N with missing prices* and evidence) moves behind *All tiers and recipes* on each card. Farming rates and the *your own past sessions, not a promise* caveat stay, the caveat once in the panel header.
- **Order:** cards in the order UI-12 already ranks next steps across the team; the STORY-088 *Biggest lever* card links to the matching card.
- **UI-08 and UI-18 screenshots:** 1280 and 390 px beside the prototype's Level up view; at 1280×860 the first row of cards is above the fold.
- **Offline tests:** card per character and profession, the band marker at the rank, missing price as *unknown* never 0, the no-step card, tiers behind the disclosure, and ranking order.
- **Real data:** beta copy, scan `20261016T113727Z-eb77d0`. Arille's Blacksmithing card shows 31 / 75 and *Cloudy Skyforged Wristguards* with +19 points for 4s 5c; Basilly's Tailoring card shows 32 / 75 and *Blue Linen Vest* with +23 points for 14s 43c (Team's next steps on the same load). Keenagen's Mining card says *no valued recipe in reach*.
- Depends on STORY-088 and STORY-089. Rules: UI-12, UI-13, CRAFT-10, CRAFT-11, UI-18. Design: *Web app (UI-18)*.

### STORY-087 — Retire NiceGUI

Added 2026-10-16. Last web story: once every place is in the web app.

As the owner, I want one app on one stack, so that nothing is maintained twice.

Acceptance:
- **Server:** a plain FastAPI app on uvicorn (`brownstone_app.py` or similar) replaces `nicegui_app.py`, keeping loopback binding, the launch token, the pywebview window, browser fallback, idle shutdown and UI-05's restart rule. `nicegui` leaves `pyproject.toml` and `requirements.lock.txt`; `fastapi`, `uvicorn` and `pydantic` are declared directly.
- **Docs:** UI-07's NiceGUI rules are replaced by UI-18 (keep its URL and back-link rules there), UI-08 7's NiceGUI clause goes, and *App and modules* describes the web app. `requirements.md` and `design.md` end below their current ceilings, and the ceilings in `brownstone/gates.py` drop to match.
- **Tests:** `tests/ui_trial` is gone; `test_retirement.py` checks NiceGUI is absent; coverage settings name `api` instead of `views` and NiceGUI entries.
- **Real data:** a full play-evening walk-through on the beta or live source (import, Today route, Market, Team, Ledger), with screenshots.
- Depends on STORY-082 to STORY-086 and STORY-088 to STORY-094. Rules: UI-05, UI-07, UI-08, UI-18, OPS-01. Design: *App and modules*, *Web app (UI-18)*, *Quality gates*.

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

**Biggest lever across characters** (found in the STORY-088 review, 2026-10-17): Today's lever card takes the first character whose Level up options include a *Level …* step, read from the option text. With one levelling step on the beta that is right, but with several it is not the team's best. Have UI-12 return a structured best next step (character, profession, cost, unlocked profit per craft) and rank it there, so the web neither parses text nor picks by character order.

**Lots and cost basis** (deferred from STORY-034 on 2026-10-15): which purchase each sold or crafted unit came from, for realised profit. Needs STORY-034b's item movements and a rule for held stock of unknown cost.

**Optional client-version cutover guard:** investigate whether recorded client versions can flag a misconfigured beta/live source during STORY-020b and first live imports. Source configuration remains authoritative (DATA-03); STORY-017 adds no client-version evidence checks.

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
  - re-checking the confirmed and unconfirmed facts under *Product direction* in `requirements.md`
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
