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
- **Keep scanning.** Sixteen complete scans of the Normal Alliance house are imported (`status.md` → *Limitations*). Take more, at least 15 minutes apart, **at different times of day and on different days**, so the diff and timing work (STORY-018; *Market timing and a daily brief* under Later) has something to start from. The routine: scan, `/reload` (the game writes scans to the file only then, or on logout), import, and only then `/bscan clear` and `/reload`. A Roleplaying or neutral house scan, if reachable, tests house identification. This is a manual habit, not automation.
- **Confirm the Forever catalog's unconfirmed values** (`status.md` → *Limitations*). Learn Bolt of Linen Cloth and check how many it makes: the profession window may show the count on the product icon, and crafting one (2 Linen Cloth) settles it. At a trade supplies vendor, check that Coarse Thread, Fine Thread, Red Dye and Rune Thread are sold, and their prices. Record each result by hand in `config/recipe-selections/forever-tailoring.toml` with the date, then regenerate on the Recipe catalogs page. Also decide whether Runecloth Bag's dyes are really post-launch: both are listed on the beta auction house.
- **Widen the Forever catalogs** (manual, on the Recipe catalogs page): the rest of Tailoring, then the professions you plan to level at launch. The board and Today's *Craft* list only cover catalog recipes, so this is what gives them something to show.
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

**Order:**
1. STORY-055 Market explorer (Brownstone; medium-large; in the new app)
2. STORY-064 flood signals: crowding and overshoots (Brownstone; medium; ready for launch on 4 November)
3. STORY-063 launch weeks: where to spend play time (Brownstone; medium; refine before handoff, after STORY-064)
4. STORY-061 stock on hand and targets (Brownstone; medium; new Stock place; needs STORY-032's beta check for bank evidence)
5. STORY-062 sales speed and suggested stock levels (after STORY-027 and enough scans; refine first)
6. STORY-059 should we add a character? (Brownstone; medium; refine before handoff, after STORY-052)
7. STORY-035 auction deposits (needs a beta check)
8. STORY-034 movement ledger and reconciliation (Brownstone; can follow the beta, built on its fixtures)
9. STORY-036 vendor price ceilings
10. STORY-015b crafting across professions
11. STORY-021 item page and charts (would live in the Market explorer)
12. STORY-026 scan coverage and rhythm
13. STORY-028 sellers and supply chains (blocked: see *Seller capture* under Later)
14. STORY-006 replay

**Pending an in-game beta check:** STORY-031, STORY-032, STORY-033, STORY-040, STORY-044 and STORY-027 (checklists in `addon/README.md`).

**Done** (outcomes in `status.md` and `requirements.md`; story text in Git): STORY-025, 030, 037, 038, 039, 041, 042, 043, 045, 046, 047, 048, 049, 050, 051, 052, 053, 054, 056, 057, 058, 060 and SPIKE-009/009b.

**Added 2026-10-12 (product owner, after SPIKE-009b: "instead of migrating all the pages… what do we really need?"):** NiceGUI becomes the app, but only for what running the business needs. Four places move, each a story: **Today** (STORY-058, then STORY-054's cards), **Team**: the employee roster, their skills and where to invest (STORY-052, then STORY-059), **Market**: an explorer for browsing materials, crafts and supply chains, plus what moved since the last scan, kept for now to judge its use (STORY-055), and **Data**: Import (STORY-058). Everything else (All recipes, Watchlist, Below usual price, Scan changes, Recipe catalogs) stays in the Streamlit app, which is kept, unchanged and reachable, but gets no new features. The new app is built for WoW Forever; Classic stays development test data with no features of its own (`requirements.md` → *Interface*). This supersedes the Streamlit placements in STORY-053 for future work.

**Added 2026-10-11 (product owner, after using the app end to end: "a lot of hopping around… I don't know what materials go to what… Characters doesn't help me know how to progress… no idea what the point of Watchlist or Opportunities is"):** the data and calculations are connected, but each story added its own page around one kind of data, so the owner assembles the answer by hopping between pages. The app is reorganised around the three questions of running the business, decided with the product owner:
1. **Today: what should our company do today?** One card per craft, with why, what to buy for it and where to sell (STORY-054).
2. **Team: how do we progress our employees?** Each character with its next step per profession (STORY-052, moved onto the Team page).
3. **Market: what are the market indicators, and how do they affect our strategy?** One brief that ties what moved to what it means for our plan (STORY-055).

STORY-053 sets up the navigation first, so each later story has a home. New feature stories wait behind these four. Display and wiring only unless a story says otherwise: no change to calculations, ranking or `today_version`.

### STORY-055 — Market explorer

**Implemented; pending owner review.** Rules: `requirements.md` → UI-09; contracts: `design.md` → Market explorer.

Added 2026-10-11 as *Market brief*; **rewritten 2026-10-12** (product owner: "the broader views of the materials and crafting market and supply chains… so that I can browse certain things and explore the data myself"; on what moved since the last scan: "keep it for now and I'll see how useful it is"). Brownstone only; read-only over values already computed. Built in the new app's Market place (after STORY-058). Supply chains here mean materials → crafts → outputs from our catalogs, not sellers (STORY-028).

As the owner, I want to look up any item and see where it sits in our crafting: what it costs, what it's used for and what it makes, so that I can explore the market myself instead of only reading Today's answer.

Acceptance:
- **Find any item** of the newest snapshot of the selected source and full market, by name or ID, regardless of price (UI-02). The page states the snapshot's UTC time and freshness once.
- **An item's page** shows, from that snapshot: lowest buyout and market value per unit, listings and units, and the item's vendor buy and sell price when known. Then its place in the chain, from compatible catalogs (UI-04) only:
  - **Made from:** if a catalog recipe makes it, its materials with quantities and current cost by CRAFT-03's cheapest route, intermediates indented (`crafting.material_plan`), and its profit per craft from the Action Board rows (`action_board.rank_catalogs`), with the board's reason when it isn't valued.
  - **Used in:** every catalog recipe that consumes it, with quantity per craft, that recipe's output and profit per craft, sorted by profit per craft. Who on the team can make each (STORY-043 statuses), Unknown marked.
  - **Skill-up demand:** the bands where levellers need it (STORY-047's map), if any.
  Every item named in a chain opens its own page in one click, so you can walk the chain in either direction.
- **What moved since the last scan** (kept on trial; the owner will judge its use): a section comparing the newest two complete scans of the same source and full market (UI-06's rules), listing at most 10 items whose lowest buyout or units changed most, limited to items in our catalogs' chains, each with its change in copper and units and a link to its page. With one scan, it says *no earlier scan*. A TSM source says it has no scan comparison.
- **Honest labels:** listings, not sales or demand; no forecast; missing prices never free or zero; stale evidence labelled.
- **Presentation** follows the rest of the new app (STORY-060): replace the Market placeholder, use `views/nicegui_theme.py` (chips, tiles, cards, badges, empty states, dialogs) and pass UI-08. Status chips at the top (snapshot age with Stale badge, items in our chains); the header ⓘ opens a dialog with snapshot ID and time, source, market and catalogs used. The open item is in the URL (`item=<id>`), so refresh and the browser's back button keep it.
- **Calculation** in a new `brownstone/market_explorer.py` (no NiceGUI or Streamlit) composing existing outputs: `analysis` browse queries, `crafting`, `action_board.rank_catalogs`, `today_characters`, `skillups`, `scan_changes`. No second pricing path. Display in a new `views/nicegui_market.py`.
- **Offline tests (NiceGUI user fixture where it's display):** search by name and ID; an item with made-from, used-in and skill-up sections; an item in no catalog (price only, says so); a missing price (never free); walking from a material to an output and back; what-moved with two scans, one scan, and a TSM source; scoping (another source's snapshot never used); a stale snapshot.
- **Real-data check:** on the Forever beta source: Linen Cloth's used-in list, Bolt of Linen Cloth's made-from, and what moved across the two newest scans.
- **Docs:** a *Market explorer* rule in `requirements.md`, `design.md`, `status.md`.

### STORY-059 — Should we add a character?

Added 2026-10-12 (product owner: "or if I need to get another character with a different profession stack"). Brownstone only. Draft: refine with the product owner before handoff; depends on STORY-052.

As the owner, I want to compare what our team can make now with what one more character, or a profession change, would add, so that I know whether to invest in a new employee and with which professions.

To refine: which professions and ranks a new character is assumed to reach (and by when); how its profit is shown when nobody on the team has the profession (catalog recipes priced on the current snapshot, with STORY-052's cost-to-reach estimate from rank 1); whether profession pairs that feed each other (gathering → crafting) are scored together; honest labels (current prices, no sales speed, Unknown never assumed). Built in the new app's Team place.

### STORY-031 — Item info pass after a scan

**Implemented and reviewed (2026-10-06); pending beta measurement.** Added 2026-10-06; final rule in `requirements.md` → ADDON-09.

As a gold maker, I want each scan to carry vendor price, item level and stack size for every item listed, so that *Below vendor* and deposits (STORY-035) have item references for more than a third of items. Listing links and variant identity are unchanged by this pass.

Acceptance:
- **After reading listings,** the addon asks the client to load each item ID still missing reference fields, listens for the client's item-loaded event, and records the answers that arrive. One request per item, a bounded wait (a value recorded in ADDON-09), a progress message, and the scan is saved even if the wait runs out. The listings already read are never re-read or changed; a separate per-item observation records which values came from the second pass.
- **Read-only and manual,** like every scan; nothing runs on a timer after the scan finishes.
- **Measured on the beta** against addon 0.3.1 (1,192 of 3,066 items had a vendor price): availability, extra time and file size, recorded in `addon/README.md`.
- **Import** accepts the new format version, keeps older formats readable, and tests stay offline (Lua stubs with delayed item info).

### STORY-032 — Character snapshots: gold, bags and bank

**Implemented and reviewed (2026-10-07); pending the in-game beta check.** Added 2026-10-06; refined 2026-10-07 for implementation. Must be testable in game by 13 October (*Now*), so the beta can confirm it on both machines before it closes after 21 October.

As a gold maker, I want the addon to record what each of my characters holds, so that Today can count what I already have and the ledger can reconcile what changed between sessions.

Acceptance:
- **Gold and bags** for the logged-in character are recorded when you log out or `/reload` (the game writes the file right after), with character name, realm, faction, UTC time and addon version. Gold is integer copper. Nothing to remember to do by hand. Which logout event still reads bags correctly is a **beta check**: register guarded (as the scan does) and record what fired.
- **Bank** contents can be read only while the bank is open, so they're recorded each time you open (and again when you close) the bank, and each bank snapshot carries its own time. A character whose bank was never opened has *bank unknown*, never empty.
- **Per slot:** container ID, slot, item ID, count and the item link bytes as reported, so ADDON-08 variants can be resolved later; empty slots are not recorded. Reagent bags, keyring or other containers the client reports are recorded as reported, with their container IDs. Missing values stay missing, never zero.
- **One account-wide file** (added 2026-10-07): snapshots go in the existing account-wide `BrownstoneScanDB` (`## SavedVariables`, never `SavedVariablesPerCharacter`), so the Windows drop script (STORY-037) carries every character on that account without changes. The file's `schema_version` goes up; Brownstone keeps reading every older version.
- **Read-only:** container and money APIs are only read. No buying, moving, sorting or mail.
- **Clearing keeps the current session:** `/bscan clear` removes only snapshots recorded before this character's current login; a `/reload` doesn't start a new login (record the login time in the file, with the client's initial-login versus reload signal as a beta check). Scans keep their existing rule (written scans are cleared; unwritten ones refuse unless `clear all`), so the Mac routine *scan → /reload → import → clear* still empties them. Record the rule in `requirements.md` → ADDON rules. A cleared file shows *bank unknown* in game; Brownstone keeps using the latest imported bank snapshot with its own time.
- **Import:**
  - A new kind of addon record, imported through the same addon source, preview and drop folder (STORY-037), and preserved in the same bronze collection as the file's scans (DATA-01). A file with snapshots but no scans is valid input; *no scans* is no longer an error when snapshots are present.
  - Each snapshot has an ID made from character, realm and time; it deduplicates across overlapping drops, and the same ID with different content is a conflict, as for scans (ADDON-04).
  - Stored with source, machine (from the file, STORY-037), character, realm and faction, never pooled across characters unless a view asks. A character whose realm or faction doesn't match the source's house evidence counts as *other house*, like scans. A new numbered migration.
  - Preview (page and CLI) lists each file's snapshots per character as new, duplicate or other house, beside its scans. **Fully imported** counts snapshots as well as scans.
- **Seen in Brownstone:** a read-only table on the addon import page, per character: latest bags time and gold, latest bank time (or *bank unknown*), item and slot counts, machine. No other views; Today using holdings is *Restock* under Later.
- **Offline tests** with Lua stubs: each container type, unknown bank, two characters, a snapshots-only file, duplicate and conflicting snapshots across overlapping drops, other-house characters, a clear that keeps the current session's snapshots across a `/reload`, older file versions still importing, the migration, CLI and the import page.

### STORY-033 — Event journal: what you bought, posted, sold, crafted and mailed

**Implemented and reviewed (2026-10-07); pending the in-game beta check.** Spellcasts narrowed to successful crafts at review (ADDON-12).

Added 2026-10-06; refined 2026-10-07 for implementation. Captures raw evidence only; meaning is STORY-034. Must be testable in game by 13 October (*Now*).

As a gold maker, I want the addon to note each auction, mail, craft and vendor event as it happens, so that Brownstone can later work out what I bought, sold and made, and at what cost.

Acceptance:
- **A journal of raw entries** in the addon file. Each entry: event or hook name, its arguments as reported (missing stays missing), Unix seconds with UTC text, session time (`GetTime()`), character, realm, faction and addon version. The entry ID is the length-prefixed character and realm (as in snapshots), time and the **same persistent account sequence snapshots use**, so journal entries and snapshots sort together for STORY-034's reconciliation.
- **Two generic observations** carry most of the meaning, so per-event parsing isn't needed to capture it:
  - **Money change:** on `PLAYER_MONEY`, copper before and after (integer copper).
  - **Bag change:** after bags settle (`BAG_UPDATE_DELAYED`), the per-item count change across carried bags since the last observation (item ID → signed count), with which windows were open (bank, mailbox, merchant, auction house, trade skill, loot). Baseline taken at login and `/reload`; no entry when nothing changed.
  Crafts, loot, gathering, vendor trades and mail taken show up as these changes next to the event that caused them.
- **Context read at the moment** (read-only APIs):
  - **Mailbox:** on opening and on each inbox change, every message header (sender, subject, money, COD, item count, days left, read flag) and, for auction mail, the invoice (type, item, other player, bid, buyout, deposit, cut). Record an inbox state only when it differs from the last one recorded this session, to keep the file small.
  - **Your own actions:** observe the functions you call (secure post-hooks: taking mail money and items, sending mail with its recipient, money and attached items, posting, bidding or buying out, cancelling, vendor buying, selling and repairing, crafting) and record their arguments. The addon never calls these itself.
  - **Own events only:** spellcasts and loot from `player` only; other players' loot lines in a group are not recorded.
- **Covers** auction house purchases, posts and cancels; mailbox invoices (sold, expired, cancelled, outbid), returned items and gold taken; mail sent and received; crafts; vendor buys, sells and repairs; loot and gathering. The event and hook list is a **beta discovery**: register guarded, record which ones the client rejects (as the scan does), and record what fired in each beta test under *Now*.
- **Bounded size:** a cap on journal entries (a value recorded in the rule). At the cap the addon stops adding entries, keeps one overflow marker with the number it skipped, and says so in chat; it never drops entries silently. A normal session's size is measured on the beta and recorded in `addon/README.md`.
- **One account-wide file** (added 2026-10-07): the journal goes in the existing account-wide `BrownstoneScanDB`, like scans and snapshots, so the Windows drop script carries it unchanged. The file format goes up; every older format stays importable. Overlapping drops repeat entries, so import deduplicates by entry ID; the same ID with different content is a conflict.
- **Clearing keeps the current session** (added 2026-10-07): `/bscan clear` removes only journal entries from before the current login, using STORY-032's login marker and the same prune (unknown login keeps everything); scans keep their own rule (ADDON-11). Events recorded since login (for example opening the mailbox before typing the command) are never lost, so the Windows routine *log in → clear → reload → play → log out → drop* is safe in any order within the session. Clearing is still safe only when that machine's latest drop is fully imported (OPS-03).
- **Never acts, and stays silent:** the addon only listens and reads (`requirements.md` → *Observing your own actions*). No automatic mail opening, taking, looting, buying, posting, cancelling or crafting; hooks only observe calls you made. Logging prints nothing to chat in normal play; only problems (a rejected event, the size cap) are reported.
- **Import:**
  - Snapshots and journal entries share **one path for non-scan records** (preview state, stale-review check, conflicts, Fully imported, import guidance counting new records), generalized from STORY-032's snapshot fields rather than a third parallel set.
  - Preserved byte-for-byte in the same bronze collection (DATA-01); stored raw per character with source, full market identity and machine, through a new numbered migration. Not interpreted yet.
  - Preview (page and CLI) shows, per file and character, journal entry counts as new, duplicate or other house, by event family; not one row per entry.
  - **Seen in Brownstone:** on the addon import page, per character, the number of imported entries by family and the latest entry time. No other views.
- **Offline tests** with Lua stubs for each event family and hook, money and bag changes (including no-change), mailbox state deduplication, the size cap and its overflow marker, a clear after events in the current session (they survive), duplicate and conflicting entries across two drops, older file formats, the migration, CLI and the import page. Real beta recordings are saved as fixtures before 21 October (the in-game checklist in `addon/README.md` says how).

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

### STORY-035 — Auction deposits

Added 2026-10-06.

As a gold maker, I want Today's *Sell* list to show the deposit for posting and what an expiry would lose, so that profit at undercut isn't overstated for cheap or slow items.

Acceptance:
- **Formula from evidence:** the beta tests under *Now* record the deposit for a few posts of known vendor price, stack size and duration. The formula is recorded in `requirements.md` with that evidence; if it can't be confirmed, deposits stay *not modeled*.
- **Shown, not ranked:** Today's *Sell* shows the deposit for the planned post and the loss if it expires. Ranking stays on batch profit (the deposit is refunded on a sale) until sell-through data exists (STORY-034).
- Needs the item's vendor price (STORY-031); missing vendor price shows *deposit unknown*, never zero.

**Beta evidence so far (2026-10-10):** one post: 5 Linen Cloth (vendor 13c) cost a **100c** deposit, more than a Classic-style formula gives (`PostCommodity` with duration argument 3; money went 145c → 45c; status 1 *sold* 30 s later, no invoice mail captured yet). **Next play session** (play actions only; Claude checks the file): post an item worth more to a vendor (a stack of 5 and a single, for example Bolt of Linen Cloth or a crafted shirt) once at each of the three durations; post one more stack of Linen Cloth at the shortest duration; then open the mailbox after the sale and take the gold. That separates a minimum from the per-vendor-value rate and duration, and times the sale-to-mail delay.

### STORY-036 — Vendor price ceilings

Added 2026-10-06. Waits for the in-game check under *Now*.

As a gold maker, I want items a vendor sells at a fixed price to be capped at that price, so that the board never values them above it or suggests buying them for more.

Acceptance:
- **Vendor items with evidence:** each confirmed vendor item (regular trade goods, and the Black Market vendor's list if it exists) is marked as a vendor item with its price and where it was seen, per CRAFT-08. Unconfirmed claims are never entered.
- **Buying:** already capped by CRAFT-03's cheapest route; Today's *Buy* never lists an auction purchase above the vendor price.
- **Selling:** a sale value above the vendor price is capped at it, with a label, and the rule is recorded in `requirements.md`.
- **Limited stock** (if the vendor has any) is noted, since vendor stock is otherwise *not modeled*.

### STORY-040 — Your active auctions

**Implemented and reviewed (2026-10-07); pending the in-game beta check.**

Added 2026-10-07 (product owner). Must be testable in game by 13 October (*Now*), with STORY-031 to STORY-033. Captures raw evidence only; meaning is STORY-034.

As a gold maker, I want the addon to record my own active auctions whenever the game shows them to me, so that every item can be followed through its whole cycle: crafted or bought, posted, still listed, then sold, expired or cancelled and taken from the mailbox.

Why: the journal (STORY-033) records the post and cancel calls and the mailbox invoices, but not what is actually listed. A post call is an attempt, not proof; the owned list confirms it, shows what is still up between sessions, and shows sold auctions waiting for their mail.

Acceptance:
- **Read when the client reports the list, never requested.** On the client's owned-auctions update (`OWNED_AUCTIONS_UPDATED` with `C_AuctionHouse` on Forever; `AUCTION_OWNED_LIST_UPDATE` with the legacy API on the Classic stand-in), read the complete list with read-only APIs. The addon never calls `C_AuctionHouse.QueryOwnedAuctions`, `GetOwnerAuctionItems` or any other request: the game's own UI asks for the list when you open the Auctions tab (or post or cancel). Whether it arrives without opening the tab is a **beta check**. Register guarded, like every journal event.
- **One journal entry per changed list,** family `auction`, in the existing journal (same ID, sequence, cap and clear rules as ADDON-12): the API used, the count the client reported, and per auction every value it returns as reported (auction ID, item ID, item link, quantity, status such as sold and waiting for mail, time left, bid, buyout, bidder). Missing stays missing, never zero; money in integer copper. Record a list only when it differs from the last one recorded this session, as for the mailbox.
- **Empty is not unknown:** a list the client reported with zero auctions is recorded (you have nothing listed). A character whose list was never observed has *active auctions unknown*, never none.
- **Never acts, and stays silent:** no posting, cancelling, bidding or requests; nothing in chat in normal play.
- **Import:** no new storage path or migration; entries go through STORY-033's shared non-scan import and are counted by family in the preview. The addon version goes up; the file format goes up only if import needs it (record which in ADDON-12).
- **Seen in Brownstone:** on the addon import page, per character, the latest observed active-auction list: time (UTC), number of auctions, and how many the client marked sold, or *active auctions unknown*. No other views; interpretation is STORY-034.
- **Offline tests** with Lua stubs for the modern and legacy APIs: a list with several auctions including a sold one, an unchanged list (no new entry), a changed list, an empty list, missing values, no request functions ever called, a rejected event, and the import page's latest row and unknown case.
- **Checklist** in `addon/README.md`: open the Auctions tab before posting, post two small stacks, open it again, cancel one, open it again, and after a sale (before and after taking the mail) open it again. Note whether the list arrived without the tab, and save the recordings as fixtures before 21 October.

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

### STORY-061 — Stock on hand and targets

Added 2026-10-13 (product owner: "see how much I have as well as set targets per material, see what's short, and have kind of a price factor"). Brownstone only; read-only over imported snapshots and the newest scan. No change to Today's plan, ranking or `today_version` (Today skipping what you hold stays *Restock* under Later). Built in the new app as a new **Stock** place between Market and Data (a UI-07 change, recorded there).

As the owner, I want to see every material our team holds, what it's worth today, and which materials are below the stock I want to keep, so that I restock the right things at a price I accept.

Acceptance:
- **Holdings:** every item in the latest readable bags and bank snapshot of each character of the selected source and full market (STORY-032's `character_snapshots.latest_data`), units per character and location, total per item, each location with its capture time and age. A bank never opened is *bank unknown* and never counted as zero; an unreadable bag is excluded and said so. Search by name or ID; a filter for items in our catalogs' chains.
- **Value at today's prices** from the newest complete scan of the same source and full market: units × cautious unit price (`requirements.md` → Cautious), labelled *at listed prices, not what it would sell for*. A missing price shows *no price* and is left out of totals, never zero; the total says how many items it excludes. Stale scans labelled.
- **Targets per item:** the owner sets target units for the whole team per item, with an optional **buy limit**: either a fixed most-per-unit in copper, or a percentage of the item's market value in the same scan (ADDON-03). Stored per source in `data/stock_targets.<source_id>.local.json` like the watchlist (validated, one entry per item ID, Save-only, a rejected save keeps the last saved targets). Only items with an item ID; names are never guessed.
- **What's short:** for each target, held, short (target − held, never negative), and the cost to fill it by walking the scan's listings cheapest first (the same depth-aware ladder Today uses), split into units **within the buy limit** (buy now) and above it (wait). Fewer listed units than short is said, never priced. An item with *bank unknown* for any character shows its shortfall as *at most*.
- **Presentation** (UI-08, `views/nicegui_theme.py`): status chips (characters and capture ages, scan age), tiles (items held, value at listed prices, items short, cost to fill within limits), then a table of short items first; holdings and evidence on demand; ⓘ dialog with snapshot, captures and the price rule.
- **Calculation** in a new `brownstone/stock.py` (no NiceGUI or Streamlit), integer copper, composing existing readers and the purchase ladder; display in a new `views/nicegui_stock.py`.
- **Offline tests:** holdings across two characters and bank/bags; bank unknown; unreadable bags; scoping (another source's or house's snapshot never used); missing and stale prices; targets save, reject and survive reload; shortfall with fixed and percentage limits; too few listings; *at most* with unknown bank.
- **Real-data check:** on the Forever beta source, the three characters' holdings and a target for one material.
- **Docs:** a *Stock* rule in `requirements.md` (and UI-07's places), `design.md`, `status.md`.

### STORY-062 — Sales speed and suggested stock levels

Added 2026-10-13 (product owner: "turnover, how fast items sell in the market is really kind of the point… I don't know how else you determine how much stock or inventory you keep"). Brownstone only. Needs STORY-027 and enough consecutive scans: refine the minimum before handoff with the beta's scan count. Draft.

As the owner, I want to see how fast each item moves on the auction house and a suggested stock level from it, so that targets come from evidence instead of guesses.

Acceptance (to refine):
- **Removal rate** per item from STORY-027: units removed per hour across consecutive scan pairs within the maximum gap, as a median with the number of scan pairs it rests on. Always *removed*, an upper bound on sales, never *sold*. Too few pairs says so instead of a number.
- **Turnover:** listed units divided by the removal rate (how long today's supply would last), shown beside it.
- **Suggested target** in STORY-061: removal rate × the days of cover the owner chooses (one setting), capped at a share of typical listed supply so we never plan to hold more than the market moves. Shown next to the manual target, never replacing it.
- **Shown** on the Market explorer's item page (STORY-055) and in Stock (STORY-061).
- Feeds *Sales speed instead of a fixed cap* (Later) for Today, which stays a separate story.

### STORY-064 — Flood signals: crowding and overshoots

Added 2026-10-13 (product owner: "when the game launches, I may need to consider market saturation as everyone's leveling up their professions"). Promoted from *Strategy ideas* (Later): *Crowding without seller names* and *Buy the overshoots*. Brownstone only; read-only over saved scans and the market metrics layer (ADDON-10); no schema change. Must be ready for launch on 4 November; it is built and tested on beta scans. Refine the thresholds with the product owner before handoff.

As the owner, I want to see which markets are flooded or crashed right now, so that in the first weeks I buy cheap materials and avoid crafting into crowded markets.

Acceptance (to refine):
- **Crowding per item** from the newest scan and the scans before it, all from the same source and full market: listing count, units listed, the share of units in the largest stack, and how often the lowest buyout changed across recent consecutive scans (STORY-027's pairs and 12-hour gap). It is labelled *contested*, *steady* or *thin* by thresholds recorded in `requirements.md`, and the numbers behind the label are shown. Seller names are not available (ADDON-07); we never guess them.
- **Overshoots:** an item's lowest buyout or market value against its own recent typical price (the median over the scans in a window recorded in `requirements.md`). Flag materials well **below** (cheap to buy, e.g. for profession levelling) and outputs well **above** (worth selling into). Show how many scans it rests on; too few says so instead of flagging. Launch-day history is short, so the window and the minimum number of scans are explicit settings, not hidden.
- **Honest labels:** listings, not sales; no forecast; missing prices never zero; variants never pooled (ADDON-08); stale evidence labelled.
- **Shown** on the Market explorer's item page and as two short lists in the Market place (most contested chain items; biggest overshoots both ways), each linking to the item page.
- **Calculation** in a new `brownstone/` module composing `scan_metrics` reads and STORY-027's pairs; display in `views/nicegui_market.py`.
- **Offline tests** for each label, each threshold boundary, too few scans, variants, scoping and stale evidence. **Real-data check** on the Forever beta source.

### STORY-063 — Launch weeks: where to spend play time

Added 2026-10-13 (product owner: "I need to figure out how to spend those first couple weeks effectively… whether it's using cheap mats to improve my professions or getting my characters leveled… or farming certain materials to sell or to craft myself"). Brownstone only. Draft: refine with the product owner before handoff, after STORY-064. It ties together answers that today sit on separate pages.

As the owner, I want the main ways to spend a play session compared side by side on current evidence, so that I use my gaming time well in the first weeks when markets swing.

To refine:
- **The four activities:**
  - **Crafting to sell:** Today's plan.
  - **Levelling a profession:** STORY-052's cost to reach the next useful recipes, cheaper when STORY-064 flags its materials below typical.
  - **Farming a material:** its sale value per hour at current prices. The gathering rate is the owner's estimate for now and is labelled as one; the ledger (STORY-034) could measure it later.
  - **Levelling a character:** which recipes or professions it unlocks, valued only as what those recipes would earn on current prices, never invented.
- **One comparison** per session length the owner chooses, using STORY-064's flood signals to demote crowded outputs and promote overshot materials, and STORY-027's removals where they exist.
- **Honest limits:** early launch evidence is thin and moves fast, so each activity shows what it rests on and its age. No forecast. The owner decides; the page only orders the options.
- **Where it lives:** probably Today (a *This session* view) or Team; decide while refining.
- **Open:** whether to compare one character or the whole team, and how to value levelling that only pays off later.

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

**Seller capture** (found 2026-10-06; blocks STORY-028): the Forever beta's bulk scan returns no seller names (ADDON-07). Left blocked until after go-live (product owner, 2026-10-06): check whether live scans return seller names. Only if they don't, decide between another read-only way of getting them (such as per-item searches, at the cost of many more auction-house requests and a longer scan) and dropping or reshaping STORY-028.

**Snapshot coverage** (added 2026-10-07; needs a character with more bags and bank slots, possibly after go-live): STORY-032's checks that a new beta character can't reach. Every equipped bag slot full; several bank bags, including the last bank bag slot; the keyring and any reagent containers the client has; a full bank compared item by item; and bank-close reads with many bags open. Use the checklist in `addon/README.md` (*All containers* and *Bank open and close*) and record the client's `container_layout` values. Until then, container coverage is confirmed only for the containers actually tested.

**Today, later versions** (captured 2026-10-06 with the product owner; each extends STORY-025 once its data exists):
- **Sales speed instead of a fixed cap:** replace *most crafts per item* with how many units of the output disappear between scans. Needs STORY-027 and a few weeks of live scans; label it removed, not sold.
- **Stockpile:** materials below their own multi-day typical price, worth buying ahead for recipes you craft often, with a holding limit tied to gold available. Needs price history across days (*History chain*), so after launch.
- **Volatility:** how much an item's typical price swings across scans, shown as a risk note and used to demote unstable crafts. Needs the same history.
- **Restock:** what you hold in bags and bank, so *Buy* skips it and *Sell* includes it. Needs STORY-032 (and STORY-037 for characters on the Windows PC); pairs with STORY-039's chosen plan.
- **Whole chains:** ore → bars → armor across professions, with the gain at each stage (sell bars or craft on). Needs STORY-015b.
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
- **In-game plan list (`PlanData.lua`):** Brownstone would write a plan file into the addon folder for an in-game to-do tab that ticks itself off. Deferred: Today on a second screen covers it, and it would make Brownstone write into the game folder (`requirements.md` → *Product direction*). If revived, the file is written only by Brownstone and read by the addon on `/reload`; it could also carry an "imported through" marker so the addon never clears what Brownstone hasn't imported.
- **Capital allocation by optimisation (linear programming):** Today's greedy funded plan is honest and affordable. Revisit with sales speed and fill chance.
- **Disenchanting outputs:** random results conflict with *Not modeled* (variable yields).
- **Price forecasting with machine learning:** too little history and too much change after launch.
- **Anomaly alerts** stay the last step of the *History chain*.

**AI narration** (suggested 2026-10-05; after STORY-025; reads ADDON-10 metrics): a plain-language summary of Today and the item page that explains only defined metrics and rule results, cites every number, and never invents one or recommends without explainable features (*Out of scope*). Needs a decision about which model runs it and what data leaves this machine.

**Addon follow-ups** (any time, none urgent):
- Scan the Roleplaying house once the beta offers it, and a neutral house when reachable, to confirm house identification and the 15% cut market.
- Check whether `/bscan start` works without the button click.

**Recipe coverage** (unblocked by STORY-004):
- **More recipes and professions:** added in the app on the Recipe catalogs page and shown together on the board (`status.md`); routing across professions is STORY-015b.
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
