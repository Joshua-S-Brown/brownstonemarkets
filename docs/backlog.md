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
- **Prepare a beta character for the character-data tests** (added 2026-10-06): level one **gathering** profession (Mining or Herbalism) and one **crafting** profession that uses it, far enough to gather, craft, post, sell, let something expire and cancel. Keep a little gold to buy and vendor with. This is what STORY-032 and STORY-033 are tested on.
- **Test the new addon builds in game** once STORY-031 to STORY-033 and STORY-040 are ready (aim: by 13 October, leaving a week of beta). Each run records what actually happened, so it can be preserved as a test fixture before the beta closes:
  - **Item info pass (STORY-031):** after a scan, how many items still lack vendor price, item level and stack size, against the 0.3.1 numbers.
  - **Snapshots (STORY-032):** gold and bags written on logout and on `/reload`; bank only after opening the bank; two characters on the same account. With a new character (added 2026-10-07: no spare bags yet), test the backpack, any equipped bags, the main bank and one bank bag slot if you can buy it. That bank bag must appear in the bank snapshots (taken when you open the bank) and never in the logout snapshot of your bags. Whatever you can't test yet moves to *Snapshot coverage* under Later.
  - **Event journal (STORY-033):** buy from the auction house, post, cancel, let one expire, sell one; open the mailbox and take the invoice and the returned item; craft; gather; buy and sell at a vendor; send mail between your own characters. Note which events fired and with what values.
  - **Active auctions (STORY-040):** open the Auctions tab before posting, after posting, after a cancel and after a sale, and note whether the list arrives without opening the tab.
  - **Unconfirmed claims** (`requirements.md` → *Known Forever market facts*): time from a sale to its gold in the mailbox; the deposit charged for a few posts of known vendor price and duration (STORY-035); whether the Black Market vendor exists, where, and its prices (STORY-036); the postage for mail to your own characters, with and without attached items and gold (added 2026-10-06: moving materials to the character with the right profession may cost something per mail).

## Next

**Agreed order (groomed 2026-10-05):** the app is almost all tables today, so user-facing analysis now gets its own lane in Next instead of waiting behind launch preparation. The layers, each building on the one before:
- **Scans** (exists) → **market metrics** (exists; ADDON-10 in `requirements.md`) → **analysis views** (item page, charts, sellers) and the **Today** page (what to buy, craft and sell now).
- An optional AI narration layer can come later. It may only explain those defined metrics, never invent numbers (*Out of scope*).
- Time-of-day and weekday patterns need weeks of live scans (*Market timing* under Later). Everything in Next works on a single scan or a few, so it can be built and tested on beta scans now.

**Order:**
1. STORY-031 item info pass (addon; beta, small)
2. STORY-032 character snapshots: gold, bags, bank (addon + import; beta)
3. STORY-037 a second machine's files (implemented and reviewed; first Windows round trip passed 2026-10-07)
4. STORY-033 event journal (addon; beta)
5. STORY-040 your active auctions (addon; beta; must be testable by 13 October)
6. STORY-038 Today craft details (Brownstone; works on existing scans)
7. STORY-039 choose and adjust the Today plan (Brownstone; after STORY-038)
8. STORY-035 auction deposits (needs a beta check)
9. STORY-034 movement ledger and reconciliation (Brownstone; can follow the beta, built on its fixtures)
10. STORY-036 vendor price ceilings
11. STORY-027 removed listings
12. STORY-015b crafting across professions
13. STORY-021 item page and charts
14. STORY-026 scan coverage and rhythm
15. STORY-028 sellers and supply chains (blocked: see *Seller capture* under Later)
16. STORY-006 replay

STORY-030 and STORY-025 are implemented and pending review; review them alongside the above.

**Added 2026-10-06 (product owner, after using Today on real data):** STORY-038 and STORY-039 follow the beta-capture stories because they need no game access and work on scans already taken. Character gold and inventory (STORY-032) and the second machine (STORY-037) are needed soon for multiple characters, so STORY-037 moves up to follow STORY-032: both machines will be played in the beta, and the journal (STORY-033) is most useful once both machines' files come in; *Restock* under Later is what lets Today use them.

**Reordered 2026-10-06 (product owner, after reviewing outside design notes):** reading your own character's data is approved (`requirements.md` → *Product direction*). Everything that must be captured in game moves to the top, because the beta closes after 21 October and its behaviour (event names, mail contents, deposits) has to be observed there before launch. The addon side records raw evidence first (STORY-032, STORY-033) and Brownstone interprets it later (STORY-034), so nothing is lost if the interpretation is wrong. Earlier: Today came first because it is the first page that answers what to do; STORY-027 and STORY-015b unblock its biggest gaps (sales speed; chains such as ore → bars → armor). The launch runbook (STORY-020a/b) is in Later.

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

### STORY-036 — Vendor price ceilings

Added 2026-10-06. Waits for the in-game check under *Now*.

As a gold maker, I want items a vendor sells at a fixed price to be capped at that price, so that the board never values them above it or suggests buying them for more.

Acceptance:
- **Vendor items with evidence:** each confirmed vendor item (regular trade goods, and the Black Market vendor's list if it exists) is marked as a vendor item with its price and where it was seen, per CRAFT-08. Unconfirmed claims are never entered.
- **Buying:** already capped by CRAFT-03's cheapest route; Today's *Buy* never lists an auction purchase above the vendor price.
- **Selling:** a sale value above the vendor price is capped at it, with a label, and the rule is recorded in `requirements.md`.
- **Limited stock** (if the vendor has any) is noted, since vendor stock is otherwise *not modeled*.

### STORY-037 — A second machine's files

**Implemented and reviewed.** The first real round trip passed on 2026-10-07: a Windows beta scan went through the drop script and Google Drive and was imported on the Mac as `windows-pc`.

Added 2026-10-06; refined 2026-10-07 for implementation. Decisions are under OPS-03 in `requirements.md`: Google Drive drop folder (installed and signed in on both machines), Windows scans accepted, Brownstone and `data/` only on the Mac, and the Windows PC has the repository cloned.

As a gold maker who plays characters on both the Mac and the Windows PC, I want both machines' addon files in Brownstone, so that scans now, and character data and the ledger later, cover every character.

Acceptance:
- **Machine names, never inferred:** every addon input carries a machine name from configuration: `machine` for the Mac's own `scan_path`, and the name embedded in each dropped file's name. Lowercase letters, digits and hyphens only. A machine is provenance, not part of `MARKET_KEYS`: scans from both machines of the same house are one market.
- **Drop folder setting:** an optional `drop_folder` on the addon source, set only in the untracked `config/market.local.toml` (the Google Drive path contains the account email). Without it, everything behaves as today. Brownstone only reads the drop folder: it never writes, renames or deletes files there.
- **Windows drop script** in the repository (for example `tools/windows/`), PowerShell with a double-click `.cmd` wrapper, needing nothing installed. Its settings (SavedVariables path, drop folder, machine name) live in an untracked local file next to it, with a tracked example. It:
  - refuses while the game is running (the game writes the file only on logout or `/reload`) and when the source file is missing;
  - copies the file to `<machine>-<UTC time>-BrownstoneScan.lua`, writing a temporary name first and renaming when complete, so Drive never syncs a half-written file under the final name;
  - never overwrites, verifies the copy's SHA-256 against the source, and says *nothing new* without copying when the bytes match that machine's latest drop;
  - only reads the SavedVariables file.
- **Preview and import on the Mac** (app and CLI):
  - Preview lists the Mac's own file plus every dropped file matching the naming pattern, each with machine, drop time and its scans (new, duplicate, other house). Other files (partial copies, Drive conflict copies such as `name (1).lua`, unrelated files) are listed as ignored, with the reason.
  - A file that can't be read (still syncing, Drive offline, truncated) is reported on its own row and doesn't block the other files.
  - Each imported file is archived byte-for-byte in bronze as its own collection, with its machine and original file name in the manifest. Every imported scan is stored with its machine (a new numbered migration; scans imported before this story keep machine missing, never guessed).
  - The existing rules apply unchanged per file: house evidence, invalidation of a reviewed preview, scan-ID/hash deduplication and conflicts, partial scans unpriced.
- **Clean-up guidance:** for each dropped file, whether every scan in it is imported, so it can be deleted from the drop folder by hand. For each machine, the latest drop and whether it is fully imported, with the reminder that `/bscan clear` on that machine is safe only if you haven't played there since that drop.
- **Docs:** Windows setup in `addon/README.md` (installing the addon from the repository, Drive for desktop, the script's settings, and the routine: log out → run the script → import on the Mac → clear in game next session); the rules in `requirements.md`; contracts in `design.md`; current state in `status.md`.
- **Offline tests:** naming and ignored files, machine validation, two machines' scans of the same house in one market, duplicate and conflicting scan IDs across files, an unreadable drop beside a good one, other-house drops, clean-up status, the migration (backup, replay, missing machine for older scans), CLI and the import page. The script's tests run where PowerShell is available (Windows CI) and are skipped elsewhere, with the skip visible.
- **Moved out:** the mail cross-check between characters on different machines needs the event journal; it is now part of STORY-034.

### STORY-040 — Your active auctions

**Implemented, pending review.**

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

### STORY-038 — Today craft details

Added 2026-10-06 (product owner feedback on Today). Display of what the plan already calculates; no change to sizing, ranking or Today's rules.

As a gold maker, I want to pick a craft on Today and see exactly what it needs, so that I know what to buy for that item without working it out from the merged shopping list.

Acceptance:
- **Select a row** in the Craft tab (Streamlit row selection); a details table appears under it. Nothing is selected by default, and the selection clears when the plan changes.
- **Materials for that craft only:** each material for the selected batch with route (auction house or vendor), required units, purchased units, cost and highest unit price, from the same reserved listings the plan used. The rows sum exactly to the craft's material cost, in integer copper.
- **Intermediate steps** the catalog route uses (for example thread → bolt → armor) appear as indented steps with their own quantities, so the chain is visible. Nothing beyond the catalog's own routes (cross-profession chains stay STORY-015b).
- **Unchanged:** the Buy tab's merged list, staleness labels (*stale — inspect only* still shows) and the 10-row limit.
- **Offline tests:** per-craft materials add up to the craft's cost and to the merged Buy list across crafts; a vendor route; an intermediate step; stale evidence.

### STORY-039 — Choose and adjust the Today plan

Added 2026-10-06 (product owner feedback on Today). Depends on STORY-038.

As a gold maker, I want to tick the crafts I'll actually make and change their batch sizes, so that Buy and Sell match what I'm really going to do.

Acceptance:
- **Choose:** each Craft row has a tick box (all ticked by default) and an editable batch size, at least 1 and at most the row's feasible size under Today's rules (funds, listed supply, per-item cap).
- **Recalculate:** Buy, Sell and the shopping total use only ticked crafts at their chosen sizes, re-reserving listings in plan order, so the list stays payable and cheap listings aren't counted twice.
- **Freed gold:** by default, gold freed by unticking or shrinking a craft goes to the next-best crafts under the existing greedy rules. A toggle keeps the plan to exactly what was ticked instead. Record the rule in `requirements.md` → *Today* with a new `today_version`.
- **Kept for the session only** and per source; choices reset when the scan or settings change, and nothing is written to disk unless a later decision says so.
- **Honest numbers:** a smaller batch than the profit-best size shows its lower profit; a choice that is no longer feasible after a new scan is dropped with a note, never silently resized.
- **Offline tests:** untick with and without refill, a shrunk and a grown batch, infeasible sizes rejected, and reserved listings never shared between crafts.

STORY-016 (backup) is deferred to Later (product owner, 2026-10-06).

STORY-011a is a bounded research task for any convenient gap. Tailoring yield and vendor checks run alongside all of this; a confirmed multi-yield requirement takes priority.

**Archive care meanwhile:** nothing required; migrations copy the database first (OPS-02). The tested backup procedure is STORY-016, deferred to Later; its destination is still an open decision. Market isolation is implemented; see DATA-03 in `requirements.md`.

### STORY-030 — Less text, less scrolling

Implemented, pending review.

Ad hoc, added by the product owner on 2026-10-06 after reviewing Today on real data. Display only: no calculation, ranking, storage, schema or addon change. Stays in Streamlit; a React front end is not planned.

As a gold maker, I want each page to show the decision first and keep explanations and provenance one click away, so that I can use the app without scrolling past text I have already read.

Acceptance:
- **Sidebar is navigation and actions only:** the experience choice (and the source choice when an experience has several), the Refresh from TSM or addon import controls, and the View list. Source ID, label, market ID, feed type and the `market.toml` hint move into a collapsed **Source details** expander in the sidebar. Every page still names its experience, source and market under the title (`show_context`); update UI-01 in `requirements.md`, which currently also requires them in the sidebar.
- **Today:**
  - **Settings collapse to one summary line** (gold available, minimum batch gain, most crafts per item) with the existing form inside an expander or popover. It opens on its own when gold available is 0c or the settings file couldn't be read. Validation, the per-source settings file, save-only writes and error messages are unchanged.
  - **Craft, Buy, Sell and Below vendor are tabs** instead of stacked sections. Each tab keeps its "N more" count; the Craft tab keeps the hidden-reason counts and the Buy tab keeps the whole-shopping-list total.
  - **Tables show decision columns first.** Craft: item, profession, batch, limited by, material cost, batch profit, profit per craft, thin. Buy: material, route, required units, purchased units, cost, highest unit price, cheap now. Sell: output, batch, lowest competing unit, listings, units, undercut unit, profit at undercut, thin. Below vendor: item, units, cost, vendor pays per unit, gain. Everything else (catalog, recipe, availability, evidence notes, recipe source, listings counts not listed above, p25, provenance) stays one click away, for example a "Show evidence columns" toggle or an expander per tab.
  - **Provenance shown once, staleness never hidden.** Source, market, snapshot/scan, evidence time and time basis are identical on every row, so they appear once on the page. When the evidence is stale or future-dated the banner stays, and every table still shows a State column reading *stale — inspect only*. Update the Today *Evidence and honesty* bullet in `requirements.md` to match.
  - **One caption line** for rules and provenance (Today version, cautious price, auction cut, source, snapshot/scan). The TSM *not available for this source* notice stays, shown only for TSM.
- **Crafting:**
  - **Recipes that can't be evaluated** appear in one collapsed expander, "N recipes could not be evaluated", holding a table (output, profession, catalog, reason) instead of one warning box per recipe (79 on the Forever beta).
  - **The per-catalog caption lines** (one per compatible catalog) move into one collapsed "Catalogs on this board (N)" expander.
  - **The board's explanatory captions** (coverage, depth meaning, margin and label rules) move into one collapsed "How to read this board" expander. One provenance caption stays visible (policy, snapshot, source, SHA-256 prefix).
- **Unchanged:** freshness captions and stale warnings (DATA-05), every value, label, ranking and column's meaning, and the other pages (Browse market, Opportunities, Recipe catalogs, Scan changes), apart from the shared sidebar.
- **Tested offline** with AppTest: the sidebar shows no source or market caption outside its expander, and each page still names them; Today renders four tabs, the settings summary, and the form opened when gold is 0c or settings are corrupt; stale Today tables still show *stale — inspect only*; Crafting with several unsupported recipes renders one expander and no per-recipe warnings. Update existing tests that read sidebar captions or Today's stacked layout.
- **Docs:** `requirements.md` (UI-01 and Today's evidence bullet), `status.md` (Interface, test count), `design.md` only if a view's structure description changes.

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

**Snapshot coverage** (added 2026-10-07; needs a character with more bags and bank slots, possibly after go-live): STORY-032's checks that a new beta character can't reach. Every equipped bag slot full; several bank bags, including the last bank bag slot; the keyring and any reagent containers the client has; a full bank compared item by item; and bank-close reads with many bags open. Use the checklist in `addon/README.md` (*All containers* and *Bank open and close*) and record the client's `container_layout` values. Until then, container coverage is confirmed only for the containers actually tested.

**Today, later versions** (captured 2026-10-06 with the product owner; each extends STORY-025 once its data exists):
- **Sales speed instead of a fixed cap:** replace *most crafts per item* with how many units of the output disappear between scans. Needs STORY-027 and a few weeks of live scans; label it removed, not sold.
- **Stockpile:** materials below their own multi-day typical price, worth buying ahead for recipes you craft often, with a holding limit tied to gold available. Needs price history across days (*History chain*), so after launch.
- **Volatility:** how much an item's typical price swings across scans, shown as a risk note and used to demote unstable crafts. Needs the same history.
- **Restock:** what you hold in bags and bank, so *Buy* skips it and *Sell* includes it. Needs STORY-032 (and STORY-037 for characters on the Windows PC); pairs with STORY-039's chosen plan.
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
- **Known recipes and skill:** the addon reads your profession window, so the board shows only what you can craft (compare STORY-015b's list of your professions). Also checks catalog quantities against the game and flags mismatches (replaces *In-game recipe reader* under *Recipe coverage*).
- **Calibrate removed listings:** your own sales from invoices show how many *removed* listings (STORY-027) were real sales.

**Ledger analytics** (from the 2026-10-06 design notes; each needs STORY-034 and some weeks of your own sales):
- **Sell-through and fill chance:** for each of your posts, its premium over the lowest price at posting, and whether and when it sold. Start with simple buckets (how often posts at 0–5%, 5–15% … above the lowest sold within their duration); more refined models only once there is enough data.
- **Gold per minute of auction time:** expected profit net of the auction cut and expected deposit losses, per minute you spend at the auction house. Replaces *Gold per hour* under *Today, later versions* if the scaled minimum gain feels wrong.
- **Cost basis:** lots per item (gathered, bought, crafted, vendor), first in first out. Two values per lot: what you paid (zero for gathered), for *what did I actually make?*; and what it would sell for now (depth-aware, after the cut, capped at any vendor price), for *craft it or sell it raw?*. Farming judged separately from trading, as gold per hour.
- **Capital view:** gold across all characters, holdings at market value, gold tied up in listings and mail, and net worth. A **reserve** you set (mount, training, spending) is kept back; Today's *Gold available* could then default to cash minus reserve instead of being typed in.
- **How well the plan worked:** planned against actual buy and sale prices, how often Today's rows were done, and realized margin per craft.

**Strategy ideas for the next grooming** (product owner, 2026-10-06; not scheduled; the session proposes, the product owner decides). The aim is to beat other gold makers on decisions, not speed: no sniping or undercut wars, and the addon stays read-only and manual. Several build on items above; say which data each needs and whether we will have it.
- **Crowding without seller names:** while scans carry no sellers (*Seller capture*), measure how contested a market is from what we do have: listing count, the share of units in the largest stack, and how often the lowest price changes between scans. Steers away from crowded markets and towards steady, quiet ones that guides don't cover.
- **Buy the overshoots:** early economies swing as gatherers and guide-followers flood the same items. Flag materials well below, and outputs well above, their own recent typical price. Extends *Stockpile* and *Volatility* above and needs the same history.
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
- **Skill-up demand map:** from the catalogs' skill levels and quantities, which materials levelling crafters will need at each skill band. A reasoned expectation for stocking up before launch, not a forecast.
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
