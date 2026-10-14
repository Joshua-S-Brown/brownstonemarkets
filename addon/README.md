# Brownstone Scan 0.12.2

A **read-only** auction house scanner, character snapshot recorder and silent economy journal for WoW Forever. It captures listings, seller and variant evidence, and official item-reference data for local market research. Brownstone imports its file through an addon source (see the main README and `docs/requirements.md` → *Addon scans*).

## What it does and doesn't do

- A scan starts only when you click **Brownstone Scan** on the auction house window, **Start scan** in the panel, or type `/bscan start` while the house is open.
- It never bids, buys, posts or cancels, and never scans on a timer or unattended. Closing the window during listing reading saves a `stopped` scan. Once listings have been saved, closing the window leaves its item info pass running.
- It issues one auction-house request, `C_AuctionHouse.ReplicateItems()`, which is Blizzard's own full-snapshot call, then reads the result. If the client has only the older Classic API, it falls back to the `QueryAuctionItems` "get all" scan. Each scan records which one it used (`api`).
- It only records what the client reports. Brownstone does all pricing (per-unit division, rounding, market value) after import, so the addon stays small and does as little as possible in game.
- The server allows one full scan per 15 minutes per account. If nothing comes back within 30 seconds the attempt stops with a throttling message. Attempts that read zero listings are not saved; partial scans with some listings are, marked `stopped`.

I checked the API against [warcraft.wiki.gg](https://warcraft.wiki.gg/wiki/API_C_AuctionHouse.ReplicateItems) (Retail documentation; Forever's client isn't documented yet, which is why the scan records `api` and falls back). Not yet confirmed on Forever: whether `ReplicateItems` needs a hardware click, and whether commodity and house-faction calls exist. The scan records what it finds; see the checklist.

## Install

1. Find the Forever client folder: Battle.net → Forever → gear icon → **Show in Finder**. It is a folder next to the other game versions, such as `/Applications/World of Warcraft/`, containing an `Interface` subfolder (Classic Era's is `_classic_era_`). I couldn't verify Forever's folder name from this machine, so use the one that holds Forever's own `Interface` and `WTF` folders.
2. Copy the `addon/BrownstoneScan` folder into `<Forever folder>/Interface/AddOns/` (confirmed on the beta: `/Applications/World of Warcraft/_classic_beta_/Interface/AddOns/`; create `AddOns` if it's missing), so the file is `.../Interface/AddOns/BrownstoneScan/BrownstoneScan.toc`.
3. **Set the interface number.** The beta build 1.60.1 reported `16001`, which the `.toc` now uses. If a later build changes it: In game, run:
   ```
   /dump select(4, GetBuildInfo())
   ```
   Open `BrownstoneScan.toc` and replace the number in the first line, `## Interface: 16001`, with that number. Restart the client (or `/reload`). If the AddOns list still shows "out of date", tick **Load out of date AddOns**.

## Last beta play session (by 21 October)

Play actions only; Claude checks the file afterwards with the beta report and says what is confirmed,
missing or wrong. One session of about an hour covers it, most important first. Skip anything the
game doesn't offer and carry on.

**Before you start:** commit and push on the Mac, then on Windows close WoW, `git pull`, copy
`addon/BrownstoneScan` into `_classic_beta_/Interface/AddOns/` as in step 1 of *Windows scans to the
Mac*, and start the game. Log in fresh (not just `/reload`).

Done on 2026-10-13: everything in the earlier checklists except the items below. Install **0.12.3**
first (it reads trainer and vendor lists after they load), then:

1. **Vendor lists:** open a trade-supplies vendor, a general goods vendor and one other vendor, without buying.
2. **Trainers (tier levels):** open the trainer for each profession you have once, then close it.
3. **Time-left labels (STORY-027):** post three cheap items at 2h, 8h and 24h and scan right away.
   Scan again about 35 minutes later, about 2h 10m later, and once more 8 or more hours later.
4. **Yellow skill-ups:** craft about 20 of one cheap recipe while it is yellow.
5. **Panel (STORY-044):** start one scan from the minimap panel, and use its reload and clear buttons once.
6. `/reload`, log out and run the drop script.

## Run a scan

1. Log in on the character for the house you want (Alliance at the Roleplaying house for the launch market) and open the auction house.
2. Optional: `/bscan label US Roleplaying Alliance` so the scan carries your own description of where it was taken.
3. Click **Brownstone Scan** (or `/bscan start`). The button shows listing progress, then **Item info answered/total**. Leave the window open to keep the controls visible.
4. When chat prints the final **Item info** summary, click **Reload** (or type `/reload`) to make the game write the file.
5. Repeat once at a neutral auction house with `/bscan label neutral`. Wait 15 minutes between scans.

Commands: `/bscan start | stop | status | panel | label <text> | clear [all]`.

**Keep the file small, in this order:** scan, `/reload` (the game writes scans to the file only then, or on logout), import, and only then `/bscan clear` and `/reload`. The addon keeps every scan until you clear it, and each import reads the whole file. `/bscan clear` refuses while a scan from this session hasn't been written to the file yet (`/bscan clear all` overrides that). Follow the full-import and latest-machine checks under OPS-03 before clearing;
character snapshots and journal entries follow ADDON-11/12 and keep the current login across `/reload`.

### Reload and clear controls (STORY-029)

Version 0.3.1 adds **Clear saved scans** and **Reload** immediately to the left of **Brownstone Scan**, using the same auction-window parent and standard `UIPanelButtonTemplate`. The scan button keeps its existing position; the row extends left with 4-pixel gaps (Clear 140×22, Reload 70×22). Both maintenance buttons are disabled from scan start through the item info pass, including after listing completion; they re-enable when the pass ends or an empty attempt exits. Reload calls `ReloadUI()` directly; clearing never automatically reloads, so the user controls when changes are written.

**Visibility:** the auction-house row stays in place. The [Panel](#panel-story-044) also makes maintenance controls available with the house closed.

**Clear decision:** the button shares the protected `/bscan clear` logic and never uses the `all` override. Unsaved session scans refuse immediately with reload/import guidance. Otherwise a standard `StaticPopupDialogs` / `StaticPopup_Show` confirmation names the saved-scan count and reminds you to import into Brownstone first. Cancel or Escape changes nothing; there is no timeout or automatic acceptance. Zero scans still get confirmation, matching the command's harmless empty clear. Accept clears `BrownstoneScanDB.scans` and prunes snapshots/journal under ADDON-11/12, preserves the label/metadata, and prints the existing next-reload reminder. Slash commands retain their existing behaviour, including immediate protected clear and the explicit `clear all` override.

**Pending-confirmation decision:** starting a scan or closing the house dismisses the popup with `StaticPopup_Hide`. The callbacks also refuse during a scan and recheck unsaved scans and the confirmed count at acceptance, protecting against state changes after the dialog opened. If the count changed, click Clear again to review it.

**Beta check passed 2026-10-06** (build 1.60.1.70235): interface **16001** matches the client; the three-button row sits above the auction window without overlap; Reload writes the file, and Clear refused while a just-finished scan was unsaved. Chat confirmations are hard to see at small window sizes. Escape on the popup was not separately exercised in game. The standard popup contract is visible in the [Classic client UI source](https://github.com/Gethe/wow-ui-source/blob/classic/Interface/AddOns/Blizzard_StaticPopup/StaticPopup.lua).

**Updating the addon:** copy the new `BrownstoneScan` folder over the old one and `/reload`. Scans saved by an older version stay in their format and still import.

### Panel (STORY-044)

Version **0.9.0** adds a coin button on the minimap edge. Left-click it (or type
`/bscan panel`) to toggle a small movable Brownstone Scan window; Escape or its close
button closes it. Drag the minimap button around the edge; its angle is restored
from `BrownstoneScanDB.ui.minimap_angle` after reload. The window's position is not saved.

The panel shows saved and unwritten session scan counts, character snapshot count,
journal count/cap (amber from 8,000), overflow skipped count and login-time availability.
Status refreshes on opening and after panel actions, including accepted Clear; press
**Status** to refresh it and print the existing `/bscan status` chat output. **Reload**,
**Clear saved data** and **Start scan** call the existing controls, with their existing
guards and confirmation. Start is available only with the house open. The panel's
routine is a reminder; opening it captures nothing and never performs an action for you.
The authoritative convenience-view contract is in [ADDON-13](../docs/requirements.md#addon-13-brownstone-panel-story-044);
capture and clear rules remain in ADDON-11/12 and the controls above.

**In-game check (pending):**

1. Click the minimap coin to open the panel; close it with Escape, open it again,
   and close it with the window's close button.
2. Open it with `/bscan panel`, move the window, then close and reopen it with the minimap button.
3. Drag the minimap coin to another edge position and `/reload`; open the panel again.
4. With the house closed, press **Status**, then **Reload** once. Open the panel again.
5. After importing the latest file on the computer, press **Clear saved data** once,
   accept its confirmation, then Reload.
6. Open the house and panel; press **Start scan** once. Leave the house open through
   the item info pass; watch the scan and maintenance buttons disable, then re-enable.

## Where the data goes

After `/reload` or logout:

```
<Forever folder>/WTF/Account/<ACCOUNT NAME>/SavedVariables/BrownstoneScan.lua
```

It holds one account-wide table, `BrownstoneScanDB`, with `schema_version`, `scans`, `snapshots`, `sessions`,
`snapshot_sequence`, `journal`, `journal_diagnostics` and `ui` (minimap angle only). Addon **0.12.2** writes file format **6** and unchanged scan format **4**; older scans retain formats 1/2/3 and still import in mixed files. Capture rules, APIs, variant identity and beta limits live in `docs/requirements.md` → ADDON-08/09. Each scan has:

| Field | Meaning |
| --- | --- |
| `schema_version`, `scan_id` | Format version (1, 2, 3 or 4) and a unique ID (UTC start time plus random suffix). |
| `started_at`, `finished_at` (+ `_utc`) | Unix seconds and ISO UTC text. `duration_seconds` is the elapsed game time. |
| `status`, `stop_reason` | `completed`, or `stopped` with a reason (window closed, timeout, user stop, error). A stopped scan is partial. |
| `listing_count`, `reported_count` | Listings saved vs the count the server reported. Equal means complete. |
| `api` | `modern` (`ReplicateItems`) or `legacy` (`QueryAuctionItems`). |
| `client` | `GetBuildInfo()` values: version, build, build date, interface number, plus locale and project ID. |
| `region`, `realm` | `GetCurrentRegion()` ID and name; `GetRealmName()` (Forever has no realms, so expect a generic value). |
| `faction` | The player's faction; `house` and `neutral` only when the client can say, with `neutral_source` showing how (`undetermined` otherwise). |
| `house` | Auctioneer NPC name and GUID, zone and subzone. Use these to tell houses apart when `neutral` is undetermined. |
| `label` | Your `/bscan label` text. It is a note, not a market ID. |
| `errors` | Messages about anything that went wrong. |
| `listing_format`, `names` | Formats 2/3/4: the field order of each listing, and distinct item names. |
| `sellers`, `level_types`, `links` | Formats 3/4: distinct original strings, indexed per listing; sellers stay local (ADDON-07). |
| `items` | Formats 3/4: one table per item ID with nullable official reference observations (ADDON-09). |
| `listings` | One entry per auction, below. |

**Format 3/4 listings** extend format 2 in this exact order:

```text
item_id:quantity:buyout:min_bid:bid:flags:name_index:seller_index:time_left:quality:level:level_type_index:link_index
```

For example, `"6538:1:500:0:0:1:1:1:4:2:10:1:1"`. The four text indexes point into `names`, `sellers`, `level_types`, `links`; index 0 means missing. Missing time-left, quality or level is an **empty field**, not zero. A reported quality or level of zero remains zero. The full original listing link is retained for every available listing, including plain items, so future parsers can inspect all evidence. Seller uses the API's full name when present, otherwise its owner name. `required_level` is derived during import only for level type `REQ_LEVEL` or Classic's `REQ_LEVEL_ABBR` (record the actual value in the beta). A time left outside 1–4, quality outside 0–8 or negative level is imported as missing and counted under `listing_out_of_range`; the scan is not rejected.

`items` is an array of keyed tables: `item_id`, `class_id`, `subclass_id`, `item_level`, `max_stack_size`, `vendor_sell_copper`. Unavailable fields are omitted by Lua and become null in import. These are one lookup attempt per ID per scan, not variant stat summaries. A reported vendor sell price of zero is distinct from missing.

### Format-4 item info pass (STORY-031)

The original `items` array and packed listings remain unchanged. Immediately after listings are
saved in `BrownstoneScanDB.scans`, a separate scan-owned pass requests incomplete item references.
The capture bounds and lifecycle rules are ADDON-09 in `docs/requirements.md`.

```lua
item_pass = {
    total = 0,
    requested = 0,
    received = 0,
    failed = 0,
    timed_out = 0,
    cached = 0,
    wait_limit_seconds = 20,
    duration_seconds = 0,
    status = "running",
    api = "C_Item.RequestLoadItemDataByID",
    -- reason = "request API missing", -- optional, omitted when not applicable
    items = {
        -- { item_id = 2589, item_level = 5, max_stack_size = 20, vendor_sell_copper = 2 },
    },
}
```

- `total`: distinct first-pass IDs lacking at least one of the three reference fields.
- `requested`: actual request attempts, at most once per ID; exceptions count as failed attempts.
- `received`: unique successful `GET_ITEM_INFO_RECEIVED` answers for pending requests, even if
  the guarded info reader still supplies no additional fields.
- `failed`: request exceptions or unique `success=false` answers. No retries.
- `timed_out`: attempted requests still unanswered when the pass ends (including explicit stop).
- `cached`: IDs whose missing fields were all readable when the pass reached them (typically loaded
  while listings were read, whose answers the pass could not yet hear), recorded without a request.
  IDs not reached before the deadline are `total - requested - cached`, separate from timed-out requests.
- `wait_limit_seconds`: the bound chosen by this addon version; `duration_seconds`: elapsed pass
  time, updated each frame and at termination. Scan `duration_seconds` still measures listing
  collection; add pass duration when comparing the full wait. A stalled frame can report elapsed
  duration above the bound; no answer at/after the deadline is accepted.
- `status`: `running`, `completed`, `timeout`, `skipped`, or `stopped`. This never changes scan
  `status`, `partial`, listing counts or pricing eligibility. `skipped` records `reason` for a
  missing request API or rejected event registration; `stopped` is an explicit `/bscan stop`.
- `api`: the request API name. Answers use `C_Item.GetItemInfo` or global `GetItemInfo`, returns
  4/8/11. Event registration and reads/requests are guarded with `pcall`.
- `items`: only IDs gaining at least one value, with `item_id` and available gained fields among
  `item_level`, `max_stack_size`, `vendor_sell_copper`. Missing and previously reported fields are
  omitted; import rejects a pass row that repeats a first-pass value. Values are integer references/copper; zero stays reported, never replaced. No links.

Import stores first-pass values and separate `pass_*` columns. `pass_fields_json` lists fields
actually filled by the pass. The effective view takes a first-pass value when present, including
zero, otherwise the pass value. Historical provenance remains null. Availability's existing
`item_available` stays first-pass; format 4 also records `item_first_available`, `item_pass_added`,
`item_effective_available` (per field), and `item_pass` counters (total/requested/received/failed/timed_out/cached).

Manual `/reload` or logout during the pass still writes the saved scan and values already gathered.
On next login a persisted `running` pass is retained without resuming requests. Prefer waiting for
the final summary before reload/import: importing an interrupted scan and later a changed version
of the same scan ID remains a content conflict under the existing deduplication rule. Reload/Clear
buttons and even `/bscan clear all` refuse (with a message) while the pass is active; the unsaved-session guard
remains afterward. Closing and reopening the house does not restart or cancel the pass.

## Windows scans to the Mac (STORY-037)

Brownstone and its `data/` folder stay on the Mac. Windows needs only WoW, Google Drive for desktop
and this repository clone. The rules are OPS-03 in `docs/requirements.md`.

1. Close WoW. In the Windows repository folder, run `git pull` to get the current addon and scripts.
   Copy the whole `addon/BrownstoneScan` folder into your game's
   `_classic_beta_/Interface/AddOns/` folder. You should see
   `Interface/AddOns/BrownstoneScan/BrownstoneScan.toc`, not another nested BrownstoneScan folder.
   Replace the installed addon files when you update the repository. Start the game and confirm
   BrownstoneScan is enabled on the character selection screen.
2. Install Google Drive for desktop from Google's website and sign in to the same account on
   both machines. Create a dedicated folder such as `BrownstoneDrops` inside My Drive. Use the
   folder visible in File Explorer on Windows and Finder on the Mac. Mark this folder **Available
   offline** on both machines, and wait for Drive to finish syncing. Never put Brownstone's
   database or `data/` folder there. Keep the folder private.
3. In `tools/windows/`, copy `drop-settings.example.json` to `drop-settings.local.json`. Enable
   **File name extensions** in File Explorer so the name does not end in `.json.txt`. Open the
   copy in Notepad and fill in all three values:
   - `saved_variables`: the full path to your account's
     `_classic_beta_/WTF/Account/ACCOUNT/SavedVariables/BrownstoneScan.lua`.
   - `drop_folder`: the full local Windows path to the dedicated Google Drive folder.
   - `machine`: a stable label such as `windows-pc`, using lowercase letters, digits and hyphens.
   In JSON, use two backslashes for each Windows path separator, as in the example, or use `/`.
   Save the file. It is ignored by Git because these paths can identify your account. No Python,
   Pester or extra packages are needed for the Windows script.
4. On the Mac, add these lines to your existing untracked `config/market.local.toml`. Merge into
   the existing source table instead of creating a second copy of that table:

   ```toml
   [sources.forever-us-normal-alliance-addon]
   enabled = true
   machine = "mac"
   scan_path = "/PATH/TO/WTF/Account/ACCOUNT/SavedVariables/BrownstoneScan.lua"
   drop_folder = "/PATH/TO/Google Drive/My Drive/BrownstoneDrops"
   ```

   Use the real local paths only in this file, especially if the Drive path contains your email.
   Keep the existing house evidence settings; Windows and Mac scans must match the selected house.
5. After a Windows scan finishes (including its item pass), **log out and close WoW**. Double-click
   `tools/windows/drop-scans.cmd`. Its window stays open so you can read the result. A successful
   run prints **Verified drop** with a filename such as
   `windows-pc-20261007T004900Z-BrownstoneScan.lua`. **Nothing new** means it did not copy anything
   because the bytes match the latest drop for that machine. Errors require correction and another
   run; they never authorize clearing. The script only reads your SavedVariables file.
6. Wait for Drive to finish syncing, then on the Mac click **Preview addon scans**. Find the file,
   its `windows-pc` label, UTC drop time, and scans marked New or Already imported. Partial copies,
   conflict copies and unrelated files show an ignored reason. A syncing/offline or malformed file
   shows its own error; other readable files can still be imported. Choose the files to import and
   click **Import addon scan**. Each file becomes its own exact-byte archived collection.
7. Check **Fully imported** for that file and the **Latest drop** row for `windows-pc`. Both must
   be true. Another-house scans require import into the appropriate source before clearing. For
   a command-line check on the Mac, run:

   ```bash
   .venv/bin/python -m brownstone --source forever-us-normal-alliance-addon --preview
   ```

   Ordinary CLI import archives only files with new scans; `--scan ID` limits IDs and `--input FILE` reads one file (a drop keeps its machine). To archive a duplicate-only file, select it on the page.
   Re-preview should mark imported scans Already imported/duplicate. Only after the latest drop
   is fully imported, and only if you have not played on Windows since making that drop, use
   `/bscan clear` on Windows next session, then `/reload`. If you played since, log out, make and
   import another drop first. Never clear solely because the copy script said Nothing new.
8. You may delete fully imported drops by hand in Drive to save space; Brownstone never removes
   them. Keep the latest drop until after the next-session clear check. Bronze on the Mac preserves
   the exact bytes. Do not delete partial/error/other-house drops on the strength of an older
   machine's successful import.

Drive streaming placeholders may be unavailable offline or still syncing. Make files available offline,
wait for sync, and preview again after any change. A file Drive is still downloading shows *Scan file changed while reading*; wait a minute and preview again. A local rename does not guarantee the Mac has
received the completed file yet. The first real round trip passed on 2026-10-07.

## Character snapshots: format 5 (STORY-032)

Install **BrownstoneScan 0.8.0 on both the Mac and Windows PC**, replacing the whole installed
`Interface/AddOns/BrownstoneScan` folder while WoW is closed. The `.toc` remains account-wide
`## SavedVariables: BrownstoneScanDB`; do not create per-character SavedVariables files.
Existing scan records remain formats 1–4. Windows copies the same whole account file with the
existing drop script; no script/settings change is needed.

The authoritative capture and clear rules are [ADDON-11](../docs/requirements.md#addon-11-character-snapshots-story-032).
The added file fields are:

| Field | Evidence |
| --- | --- |
| `snapshots` | Array of independent bags or bank observations, including snapshots without scans. |
| `snapshot_id`, `sequence` | Length-prefixed character/realm + kind + Unix seconds + persistent account sequence; numeric order for same-second observations. |
| `character`, `realm`, `faction`, `kind` | Exact character/realm strings, player faction, `bags` or `bank`. |
| `captured_at`, `captured_at_utc`, `addon_version`, `client` | Unix seconds, UTC text, current addon version, client build evidence. |
| `gold_copper` | Bags only: nullable integer copper from `GetMoney`; a reported zero remains zero. |
| `slots` | Occupied slots: `container_id`, `slot`, nullable `item_id`, `count`, exact `item_link`. |
| `containers` | Reported container IDs, nullable sizes, `slots_readable = false` on reader errors; unknown never means empty. |
| `event`, `fired_events`, `rejected_events`, `container_api` | Trigger, fired counts this runtime, guarded-registration failures, modern/legacy reader. |
| `read_event`, `unreadable_read` | 0.10.0, only when the logout read was unreadable: the event of the saved read, and what the logout read returned. |
| `login_at`, `world_signal` | Login marker and actual initial-login/reloading-UI arguments (missing arguments omitted). |
| `sessions` | Character/realm-keyed persisted login markers, initial-login evidence and reload-seen flag. |
| `snapshot_sequence` | Account-wide monotonic same-second discriminator, retained when clearing. |

Gold/bags are read at `PLAYER_LOGOUT`; bank only at open/close, never by logout with a closed bank.
Since **0.10.0**, when the logout read finds no readable backpack (the client already stopped answering),
the newest readable read from this login is saved instead, with `read_event` and the logout's values
in `unreadable_read` ([ADDON-11](../docs/requirements.md#addon-11-character-snapshots-story-032)).
Modern `C_Container` readers fall back to legacy globals. Slot evidence is kept without resolving
variants yet. Preview/import uses the existing addon source, exact-byte archive and file inventory.
The import page's latest-character table reports gold in gold and independently timed bags/bank,
counts and machine. Incomplete container coverage has unknown totals. **Fully imported** now covers
both scans and snapshots, including snapshot-only files. New/duplicate/other-house snapshot rows
appear beside scans in page and CLI previews. All matching snapshots in a selected file import;
`--scan` restricts scans only. Character data does not yet change Today.

## Event journal: format 6 (STORY-033)

Install **0.8.0** on both machines. The account-wide file now also holds `journal` and
`journal_diagnostics`; scans keep format 4 and existing snapshots keep their contract.
The capture, candidate event/hook list, cap and clear rules are
[ADDON-12](../docs/requirements.md#addon-12-event-journal-story-033). Storage/import contracts
are in [design.md](../docs/design.md#character-snapshots).

Each journal entry has `entry_id`, the shared `sequence`, `event`, `family`, `arguments` (`n`
counts all arguments, including missing positions), capture Unix/UTC time, nullable session time,
character/realm/faction, addon version, login marker and observed `windows`. Money adds
`before_copper`/`after_copper`; settled bags add `item_changes` (item ID → signed count) or
`baseline_missing`. Mail states contain `inbox.counts`, message index, counted raw header/invoice
returns and attachment info/link. A send hook includes its recipient/subject/body arguments and
`draft_is_last_observed` plus the last observed draft's money/COD/items/time. This draft may be
missing or stale: a post-hook runs after the game function, which may already clear the draft.
Do not read a hook as success or invent values where the client returned none.
Since **0.10.0** the sell-junk button (`C_MerchantFrame.SellAllJunkItems`) and trainer purchases
(`BuyTrainerService`, `TRAINER_SHOW`/`TRAINER_CLOSED`) are recorded as family `vendor`.

`journal_diagnostics` holds this load's rejected events, missing/installed hooks and fired counts.
`journal_errors` counts observation failures reported in chat; these do not interrupt a game call.
A hook can become installed after a UI addon loads; missing diagnostics refresh then. Routine
logging is silent; explicit `/bscan status` reports journal count/cap and missing hooks. The addon
never performs an economy action or opens/takes mail. Window flags mean observed event state;
an absent flag is unknown. Inbox comparisons and bag/money baselines reset on addon reload. Since **0.10.1** a fresh login sets no bag baseline until its first settled bag update, which records `baseline_missing` (rule: `docs/requirements.md` → journal baselines).
The single overflow marker has `event = JOURNAL_OVERFLOW`, cumulative `skipped` and a fresh ID
on each update. Compare versions rather than summing their skipped counts.

Preview lists one journal row per character/family with new/duplicate/other-house counts, alongside
snapshot/scan tables. Import displays saved counts/latest UTC time per character/family. A file with
only entries is valid; all matching non-scan records import when the file is selected, even with
`--scan`. Fully imported includes journal entries. Duplicate-only import still says **Nothing new:
/reload first**. Follow OPS-03 before clear, then verify current-login entries survived the write.

### Real recordings for replay (STORY-006)

Every file the drop script copies (`windows-pc-<UTC time>-BrownstoneScan.lua` in the drop folder) is an
unchanged, immutable recording of the account file. Keep them: STORY-006 builds its replay fixture from
them. They can contain other players' names (ADDON-07), so they stay private and are never committed;
a committed fixture is a small, anonymized extract.

### Removed listings time-left beta check (STORY-027) — pending

UI-10 in `docs/requirements.md` uses Classic Era's legacy auction time-left bounds; Forever's
raw 1–4 capture alone does not establish their durations. In the Forever beta, record client build,
date, API family and the auction UI's time-left tooltip text for buckets 1–4. Check short (<30 min),
medium (30 min–2 h), long (2–12 h), very long (>12 h), especially the 30-minute, 2-hour and 12-hour
transitions. Use manually observed listings with known posting/expiry times where possible;
retain raw scans and local evidence. Compare `GetReplicateItemTimeLeft` (or the guarded legacy API
if available) with the UI labels; never request unattended scans. Record any different Forever
bounds in UI-10 before interpreting removed-early counts as timing evidence. No exact expiry or
sale can be confirmed from disappearance alone.
