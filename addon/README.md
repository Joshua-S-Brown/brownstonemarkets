# Brownstone Scan 0.6.0

A **read-only** auction house scanner, character snapshot recorder and silent economy journal for WoW Forever. It captures listings, seller and variant evidence, and official item-reference data for local market research. Brownstone imports its file through an addon source (see the main README and `docs/requirements.md` → *Addon scans*).

## What it does and doesn't do

- A scan starts only when you click **Brownstone Scan** on the auction house window, or type `/bscan start` while it is open.
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

## Run a scan

1. Log in on the character for the house you want (Alliance at the Roleplaying house for the launch market) and open the auction house.
2. Optional: `/bscan label US Roleplaying Alliance` so the scan carries your own description of where it was taken.
3. Click **Brownstone Scan** (or `/bscan start`). The button shows listing progress, then **Item info answered/total**. Leave the window open to keep the controls visible.
4. When chat prints the final **Item info** summary, click **Reload** (or type `/reload`) to make the game write the file.
5. Repeat once at a neutral auction house with `/bscan label neutral`. Wait 15 minutes between scans.

Commands: `/bscan start | stop | status | label <text> | clear [all]`.

**Keep the file small, in this order:** scan, `/reload` (the game writes scans to the file only then, or on logout), import, and only then `/bscan clear` and `/reload`. The addon keeps every scan until you clear it, and each import reads the whole file. `/bscan clear` refuses while a scan from this session hasn't been written to the file yet (`/bscan clear all` overrides that). Follow the full-import and latest-machine checks under OPS-03 before clearing;
character snapshots and journal entries follow ADDON-11/12 and keep the current login across `/reload`.

### Reload and clear controls (STORY-029)

Version 0.3.1 adds **Clear saved scans** and **Reload** immediately to the left of **Brownstone Scan**, using the same auction-window parent and standard `UIPanelButtonTemplate`. The scan button keeps its existing position; the row extends left with 4-pixel gaps (Clear 140×22, Reload 70×22). Both maintenance buttons are disabled from scan start through the item info pass, including after listing completion; they re-enable when the pass ends or an empty attempt exits. Reload calls `ReloadUI()` directly; clearing never automatically reloads, so the user controls when changes are written.

**Visibility decision:** the controls are available only with the auction house open, like the existing scan button. This keeps one small, contextual row without a persistent screen panel or new commands. For the manual scan → Reload → import → Clear → Reload routine, leave the house open during the import or reopen it afterward; the existing slash commands also work with the house closed.

**Clear decision:** the button shares the protected `/bscan clear` logic and never uses the `all` override. Unsaved session scans refuse immediately with reload/import guidance. Otherwise a standard `StaticPopupDialogs` / `StaticPopup_Show` confirmation names the saved-scan count and reminds you to import into Brownstone first. Cancel or Escape changes nothing; there is no timeout or automatic acceptance. Zero scans still get confirmation, matching the command's harmless empty clear. Accept clears `BrownstoneScanDB.scans` and prunes snapshots/journal under ADDON-11/12, preserves the label/metadata, and prints the existing next-reload reminder. Slash commands retain their existing behaviour, including immediate protected clear and the explicit `clear all` override.

**Pending-confirmation decision:** starting a scan or closing the house dismisses the popup with `StaticPopup_Hide`. The callbacks also refuse during a scan and recheck unsaved scans and the confirmed count at acceptance, protecting against state changes after the dialog opened. If the count changed, click Clear again to review it.

**Beta check passed 2026-10-06** (build 1.60.1.70235): interface **16001** matches the client; the three-button row sits above the auction window without overlap; Reload writes the file, and Clear refused while a just-finished scan was unsaved. Chat confirmations are hard to see at small window sizes. Escape on the popup was not separately exercised in game. The standard popup contract is visible in the [Classic client UI source](https://github.com/Gethe/wow-ui-source/blob/classic/Interface/AddOns/Blizzard_StaticPopup/StaticPopup.lua).

**Updating the addon:** copy the new `BrownstoneScan` folder over the old one and `/reload`. Scans saved by an older version stay in their format and still import.

## Where the data goes

After `/reload` or logout:

```
<Forever folder>/WTF/Account/<ACCOUNT NAME>/SavedVariables/BrownstoneScan.lua
```

It holds one account-wide table, `BrownstoneScanDB`, with `schema_version`, `scans`, `snapshots`, `sessions`,
`snapshot_sequence`, `journal` and `journal_diagnostics`. Addon **0.6.0** writes file format **6** and unchanged scan format **4**; older scans retain formats 1/2/3 and still import in mixed files. Capture rules, APIs, variant identity and beta limits live in `docs/requirements.md` → ADDON-08/09. Each scan has:

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

### Format-4 beta checklist — pending

Use the same house with similar listing counts, record the client build and addon **0.4.0**, and
compare against **0.3.1** (1,192/3,066 items had all three reference values).

1. Record first-pass, pass-added and effective availability for vendor sell price, item level and
   max stack size, with item denominators; record cached/requested/received/failed/timed_out and unsent IDs.
   Listing-link availability should be unchanged by the pass. There is no assumed success threshold.
2. Record listing duration, pass duration and total elapsed wait; check requests arrive across
   frames, progress advances, one final summary appears, and no repeat or later callback occurs.
3. Compare original uncompressed single-scan bytes per listing against 0.3.1; record raw bytes and
   listing counts, not gzip size. Record client lag and `/reload` lag. ADDON-09's older format-3
   measurement limits remain documented there; do not claim a new format-4 beta result offline.
4. Close the house during the pass, reopen it and confirm progress/disabled Reload and Clear,
   including the existing unsaved-scan clear guard after completion. Stop explicitly in another
   run and confirm scan completion remains intact. Observe timeout counts if answers do not arrive.
5. In a separate run type `/reload` mid-pass, and separately log out mid-pass. Inspect/import the
   file: listings are saved, gathered pass values survive, status may be `running`, and no pass
   resumes after login. Compare hashes/first-pass arrays before and after; record actual event timing.
6. Import a normal completed format-4 scan, inspect availability and a pass-supplied vendor reference
   in Today; import again and confirm duplicate. Preserve local beta evidence; keep seller data local.

No game access was available for implementation. These beta measurements remain explicitly pending.

Import stores the new listing fields, raw link, variant identity/resolution, base-item observations and availability counts. Formats 1/2 keep every new field null. Format 1 links survive in the raw archive but are not retrospectively classified. Browse, Opportunities and Scan changes show variant ID/state (`legacy` for formats 1/2); catalog crafting/depth uses only base rows in formats 3/4. See ADDON-08 for exact grouping and legacy behavior.

**Format 2 listings** are one string each, `item_id:quantity:buyout:min_bid:bid:flags:name_index`, for example `"2589:20:700:0:0:1:3"`. Prices are integer copper as the client reported them, and `0` means none (no buyout or no bid). `flags` adds 1 when the client had loaded the item's details (`complete_info`) and 2 when it reports a commodity (Brownstone rejects those scans, since only stack prices are modeled). `name_index` points into the scan's `names` list (1 is the first name), or is `0` when the client hadn't loaded the name. Names are kept per listing because one item ID can carry several random-suffix names ("of the Monkey", "of the Eagle"). About 28 bytes per listing.

**Format 1 listings** (addon 0.1.0) are tables with `item_id`, `name` (empty until the client has loaded the item), `link` (missing until loaded), `quantity`, `buyout`, `unit_buyout` (copper per unit, or missing), `min_bid`, `bid` (only when someone has bid), `commodity` (only when the client says) and `complete_info`. About 240 bytes per listing.

Prices are integer copper. A missing `buyout` means the listing has no buyout; it is never zero or free. On the Forever beta (first scan, 2026-10-04) `buyout` is the price of the **whole stack**, not per unit, and `commodity` is never reported. Brownstone divides `buyout` by `quantity` itself, rounding up when inexact; format 1's `unit_buyout` is only a cross-check, and format 2 doesn't write it. A listing the client hasn't fully loaded has no name and `complete_info` false; its item ID, quantity and buyout are still valid.

A hand-written example is in `tests/fixtures/brownstone_scan_sample.lua`.

## Measurement checklist

Keep results and SavedVariables files locally. Formats 3/4 can contain seller names and must not be shared, published or sent to external processing (ADDON-07; OPS-03 permits the private Drive drop transport). Availability summaries contain counts only.

| | Roleplaying Alliance | Neutral |
| --- | --- | --- |
| Date, character, faction | | |
| Interface number (`/dump select(4, GetBuildInfo())`) | | |
| `api` recorded (`modern` / `legacy`) | | |
| Final `status` and `stop_reason` | | |
| Full scan time (`duration_seconds`) | | |
| `listing_count` vs `reported_count` | | |
| SavedVariables file size | | |
| Throttling (message, wait before it worked) | | |
| Errors or Lua error popups (paste text) | | |
| Needed a hardware click? (did `/bscan start` work, or only the button?) | | |
| `/reload` freeze time or lag during the scan | | |
| `neutral` / `neutral_source` values | | |
| Listings missing `name` or `link`, roughly what share | | |
| Do `quantity` and `buyout` look per-unit for commodities and per-stack for gear? | | |
| Anything surprising | | |

If the client prints "No auction API found", run `/dump C_AuctionHouse` and `/dump QueryAuctionItems` and send the output.

## Format-3 beta checklist (STORY-023)

Accepted 2026-10-06 (record below). Repeat it for any later scan-format change. Every baseline and candidate measurement must name the exact addon version used (including 0.3.1 if these controls are installed). The listing capture contract and original format-3 measurement limits remain in ADDON-09; do not label 0.3.1 measurements as 0.3.0. Record versions alongside the local aggregate report; older scans do not carry a per-scan addon version, so use the installed version and retained file provenance rather than guessing.

1. **Baseline:** using 0.2.0, take one complete scan at the same house, `/reload`, retain a local single-scan file, import it, then `/bscan clear` and `/reload`. If an existing 0.2.0 file has exactly one scan, it can be the baseline. Record build, house, listing count, duration and uncompressed file bytes.
2. **Update and capture:** copy the current addon over the installed addon, `/reload`, confirm it loads and `/bscan status` works. At least 15 minutes after the preceding scan, click the scan button with the house open. Record lag/errors and finished vs reported count. `/reload`, retain the local single-scan file, then Preview/Import in Brownstone. Confirm the installed format version, official reference data and separate variant rows. Try `/bscan start` on another manually initiated scan; closing the house during reading should save only a partial scan and no prices.
3. **Availability and limits:** run the local summary below against baseline/candidate files. Record each available/total count, including sellers, links, required-level type (the raw `level_types` values), all five item-reference fields, unresolved links and `listing_out_of_range`. Record reload lag. Compare duration and bytes per listing against ADDON-09's limits; missing remains null, and reported zero quality/level/vendor values remain zero.
4. **Variant tooltips/links:** look for Willow Robe (6538) Monkey/Bear/Eagle and Primal Wraps (15010) Whale/Bear, or equivalent currently listed suffix gear. Compare tooltips for different suffixes and multiple listings of the same suffix. Inspect actual payloads: observed bonus IDs are listed in ADDON-08; the traditional suffix field was empty. Confirm different stats have different stored keys/prices, while identical stat modifications with different viewer/context/modifier-28 provenance retain the same key. Check Linen Cloth as a plain base item. Record any unexpected fields or equal keys with different stats before relying on those prices.
5. **Preserve:** re-import the same file and confirm duplicates. Retain the files and measurement record locally; only after a successful import, `/bscan clear` and `/reload`. A complete format-3 beta import, accepted timing/size results and tooltip confirmation are required to close STORY-023.

To inspect a full modern listing link after a manual scan, replace `INDEX` with its zero-based replicate index (legacy uses `GetAuctionItemLink("list", INDEX)` with one-based indexing):

```lua
/run local l=C_AuctionHouse.GetReplicateItemLink(INDEX);print(l and l:match("|H(item:[^|]+)|h"))
```

This reads the captured list; it does not start a scan. Record item-link payloads/tooltips locally, without seller names in shared reports.

**Local availability/size summary** (run from the repository; replace both file paths). This reads files without writing or migrating a database and prints only aggregate measurements. It requires one scan per file so saved-file size is comparable. Gzip archive inputs are measured after decompression.

```bash
.venv/bin/python - /path/to/baseline-0.2.0.lua /path/to/candidate-0.3.1.lua <<'PY'
import gzip
import json
import sys
from pathlib import Path
from brownstone import scan_details, scans

results = []
for filename in sys.argv[1:]:
    raw = Path(filename).read_bytes()
    if raw.startswith(b"\x1f\x8b"):
        raw = gzip.decompress(raw)
    records = scans.read_saved_variables(raw)
    if len(records) != 1:
        raise SystemExit("Use a single-scan file for each measurement.")
    record = records[0]
    summary = scans.summarize(record)
    if summary["partial"] or not summary["listing_count"]:
        raise SystemExit("Both measurements need a complete, nonempty scan.")
    result = {"format": record["schema_version"], "scan_id": record["scan_id"],
              "duration_seconds": scan_details.duration(record), "file_bytes": len(raw),
              "bytes_per_listing": len(raw) / summary["listing_count"],
              "availability": scan_details.availability(scans.listing_frame(record),
                                                         scan_details.reference_frame(record),
                                                         scans.optional_out_of_range(record), record)}
    result["pass_duration_seconds"] = record.get("item_pass", {}).get("duration_seconds", 0)
    result["full_duration_seconds"] = (result["duration_seconds"] + result["pass_duration_seconds"]
                                       if result["duration_seconds"] is not None else None)
    results.append(result)
    print(json.dumps(result, indent=2))
if len(results) == 2:
    old, new = results
    if old["duration_seconds"] and new["duration_seconds"] is not None:
        print("Listing duration ratio:", new["duration_seconds"] / old["duration_seconds"])
        print("Full duration ratio:", new["full_duration_seconds"] / old["full_duration_seconds"])
    print("Bytes/listing ratio:", new["bytes_per_listing"] / old["bytes_per_listing"])
PY
```

| Acceptance measurement | Result |
| --- | --- |
| Beta date/build/house, baseline and candidate addon versions and scan IDs | 2026-10-06, client 1.60.1 build 70235, Normal Alliance house (Stormwind, Trade District); house check passed. Baseline **0.2.0** `20261006T161637Z-2a4d09`; candidate **0.3.1** `20261006T201752Z-f2a29a`. A second 0.3.1 scan, `20261006T203259Z-ea00ed`, gave consistent results. |
| Complete format-3 scan imported; duplicate verified | Both 0.3.1 scans completed (88,119/88,119 and 88,329/88,329) and imported without errors. Re-import shows *Nothing new*; preview reports both as already imported with identical content. |
| New-field availability (attach local aggregate report) | Of 88,119 listings: **seller 0**, time left 88,119, level 88,119, quality/level type/link 82,059, required level 73,749; quality out of range 6,060 (stored missing). Of 3,066 items: class/subclass 3,066, item level/stack/vendor price 1,192. Level types seen: `REQ_LEVEL_ABBR`, `SLOT_ABBR`, `SKILL_ABBR`. **Sellers:** `GetReplicateItemInfo` returns no owner (values 14/15 absent in `/dump`), even for the 82,059 fully loaded listings; see ADDON-07. Report kept locally under `work/story-023/beta/`. |
| Duration ratio and uncompressed bytes/listing ratio vs ADDON-09 | Duration 6.90 s → 8.49 s, **1.23×** (limit 2×). File 2,178,443 B / 77,731 → 4,729,786 B / 88,119; bytes per listing 28.0 → 53.7, **1.92×** (limit 4×). Pass. |
| Scan/reload lag, errors; button and slash command | No scan errors and no client error reports. Lag was not timed; none was noticed. Scan, Reload and Clear were used through the buttons. `/bscan start` without the button and closing the house mid-scan were not exercised in game (both are covered offline). |
| Different suffix tooltips separated; same stats/provenance variants equivalent | Willow Robe (6538): 20 suffixes, each its own key; *of Intellect* and *of Magic* at 12,900 copper versus 500 for the rest, matching the in-game listings. Primal Wraps (15010): 14 suffixes, each its own key. No key holds two names of the same item (3,589 item/key pairs). The same name appears under several keys only for different enchants (for example Battering Hammer of Healing with enchant 723) or bonus IDs (*of the Physician*, 12748/12749; not tooltip-compared). Links differing only in modifier 28 share a key. |
| Plain item base; missing/unsupported links unresolved | Linen Cloth (2589): 601 listings, all base. 72,259 base, 7,920 variant and 7,940 unresolved listings, including the 6,060 without a loaded link. |


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

Install **BrownstoneScan 0.6.0 on both the Mac and Windows PC**, replacing the whole installed
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
| `login_at`, `world_signal` | Login marker and actual initial-login/reloading-UI arguments (missing arguments omitted). |
| `sessions` | Character/realm-keyed persisted login markers, initial-login evidence and reload-seen flag. |
| `snapshot_sequence` | Account-wide monotonic same-second discriminator, retained when clearing. |

Gold/bags are read at `PLAYER_LOGOUT`; bank only at open/close, never by logout with a closed bank.
Modern `C_Container` readers fall back to legacy globals. Slot evidence is kept without resolving
variants yet. Preview/import uses the existing addon source, exact-byte archive and file inventory.
The import page's latest-character table reports gold in gold and independently timed bags/bank,
counts and machine. Incomplete container coverage has unknown totals. **Fully imported** now covers
both scans and snapshots, including snapshot-only files. New/duplicate/other-house snapshot rows
appear beside scans in page and CLI previews. All matching snapshots in a selected file import;
`--scan` restricts scans only. Character data does not yet change Today.

### Character snapshots beta checklist — Mac and Windows, pending

Repeat the capture checks on **each machine**, using **0.6.0**, before relying on this evidence.
Use two characters on the **same account**. Preserve all before/after files privately; do not clear
unimported evidence. Character data stays private under the same transport rules as scans.

1. **Install and initial login:** with WoW closed, replace the addon folder on the Mac. On Windows,
   use the repository containing these changes (after they have been committed/pushed and pulled)
   or copy the same 0.6.0 folder directly. Confirm the AddOns version and `/bscan status`. Log in
   afresh after installation, rather than installing only via `/reload`, to establish a login marker.
   Record OS/machine label, addon version, date, character, realm, faction, client version/build and
   `/dump select(4, GetBuildInfo())`. Record every rejected event from status. Check the `.toc` interface
   number against the build. Do not assume event names are supported because the addon loaded.
2. **Bank unknown:** choose a character whose bank has never been recorded, or, after importing all
   prior evidence, start a new login and clear old snapshots. Before opening the bank, `/bscan status`
   should say *bank unknown*. Log out; check that a bags snapshot exists and there is no bank snapshot
   for that character. Record money from the game and expected occupied bags/slots for comparison.
3. **Logout and reload bags separately:** log in, note gold and a few known stacks/links, then `/reload`.
   Inspect the SavedVariables file after writing finishes: `event = PLAYER_LOGOUT`, gold in copper,
   character/realm/faction, UTC time, addon version and complete occupied slots. Repeat with normal
   logout/exit. Compare expected and stored IDs/counts/links; record which event fired and any missing
   bags, Lua errors, write/reload lag or unavailable APIs. If logout events cannot still read bags,
   retain the evidence and report it; event timing is unconfirmed on Forever.
4. **All containers:** inspect backpack, equipped bags and every supported keyring/reagent bag.
   Record `Enum.BagIndex`, `NUM_BAG_SLOTS`, `NUM_TOTAL_EQUIPPED_BAG_SLOTS`, `NUM_BANKBAGSLOTS` and
   available container constants using read-only `/dump` calls, and compare them with each snapshot's
   `container_layout`. In particular, confirm that the first bank bag (container 5 when four bags are
   equipped) appears in bank snapshots and never in bag snapshots. Compare stored IDs/sizes/occupied slots with the UI. Empty slots
   must be absent. For unavailable values, confirm omission/null rather than zero. Record which
   modern `C_Container` or legacy globals exist and their actual tuple/table behavior; do not infer
   support from a modern client's documentation.
5. **Bank open and close separately:** note known bank stacks, open the bank, run `/bscan status`,
   then close it and run status again; `/reload` to write. Expect two bank IDs, each with its own UTC
   time and `BANKFRAME_OPENED`/`BANKFRAME_CLOSED`. Compare main bank, bank bags and reagent bank
   IDs/counts/links. Specifically record whether close still permits reads, returns zero sizes or
   loses slot data, and whether any bank access happened with the UI closed. An inaccessible main
   bank is unknown, not empty. Compare snapshot `containers`, `slots` and event counters, keeping
   both raw observations. Close-event availability is a beta check, not an offline guarantee.
6. **Login versus reload and clear:** open/close the bank, `/reload`, retain the file and login marker,
   then `/bscan clear` and `/reload` within the same login. All snapshots captured since that login
   must remain, with unchanged IDs/content; scans already written should be emptied. Inspect
   `world_signal` and `sessions`: initial login should be `(true, false)`, reload `(false, true)`,
   with identical `login_at`. A world transition (any flags) must not reset it. Record actual
   flags. If either signal is absent/unexpected, clearing must retain all snapshots; report the
   warning and flags instead of assuming a new login. `clear all` must still retain current-session
   snapshots. A fresh login after importing prior evidence should prune older snapshots; if its
   bank record was pruned, in-game status is *bank unknown* while Brownstone retains the imported
   bank time. Test the confirmed Clear button too. Test unsaved-scan refusal and the existing
   scan → `/reload` → import → clear routine with snapshots present.
7. **Two characters:** log out of the first and into the second on the same account. Repeat bags
   capture and bank open/close. Both characters must appear in the single account file, with
   distinct IDs and login markers. Retain both before any next-login clear.
8. **Mac import:** wait for the write to finish, then Preview addon scans in Brownstone. Compare
   snapshot characters/times/kinds/counts/machine and new/duplicate/other-house states with the
   file; import it and inspect the latest-character table. Check gold, bags time, separate bank
   time/counts and *bank unknown* where appropriate. Preview again: duplicate IDs and Fully imported
   (when every record belongs to this source). A character from another faction/configured realm
   must be *other house*, block Fully imported and stay out of this source's character table.
   Do not alter the source's house evidence to bypass the mismatch.
9. **Windows round trip:** after both characters' captures, log out and **close WoW**, run
   `tools/windows/drop-scans.cmd`, wait for Drive sync, then preview/import on the Mac. Confirm
   `windows-pc` provenance, every character's snapshots, exact-byte bronze collection and both
   file/latest-drop Fully imported status. Repeat another drop that overlaps prior snapshots;
   unchanged IDs must be duplicates, newly captured IDs new, with earlier stored machine retained.
   Include a snapshots-only file (no scan needed). CLI check on the Mac:

   ```bash
   .venv/bin/python -m brownstone --source forever-us-normal-alliance-addon --preview
   ```

   Follow OPS-03 before next-session clear: latest drop fully imported, nothing played since that
   drop. Current-login snapshots remain even when clear is allowed. The drop script's *Nothing new*
   does not authorize clearing. Delete only fully imported drops by hand, preserving local evidence.
10. **Record results:** retain a private row per OS/character/action with build/addon version, exact
    initial/reload flags and login times, rejected/fired events, API shape/container IDs/sizes,
    expected versus stored copper/item/slot/link values, bank open/close availability, snapshot IDs,
    preview/import outcomes, machine/drop UTC, timing/lag and Lua errors. State failures explicitly;
    offline stubs cannot confirm these Forever beta behaviors. Keep raw files private for diagnosis.

## Event journal: format 6 (STORY-033)

Install **0.6.0** on both machines. The account-wide file now also holds `journal` and
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

`journal_diagnostics` holds this load's rejected events, missing/installed hooks and fired counts.
`journal_errors` counts observation failures reported in chat; these do not interrupt a game call.
A hook can become installed after a UI addon loads; missing diagnostics refresh then. Routine
logging is silent; explicit `/bscan status` reports journal count/cap and missing hooks. The addon
never performs an economy action or opens/takes mail. Window flags mean observed event state;
an absent flag is unknown. Inbox comparisons and bag/money baselines reset on addon reload.
The single overflow marker has `event = JOURNAL_OVERFLOW`, cumulative `skipped` and a fresh ID
on each update. Compare versions rather than summing their skipped counts.

Preview lists one journal row per character/family with new/duplicate/other-house counts, alongside
snapshot/scan tables. Import displays saved counts/latest UTC time per character/family. A file with
only entries is valid; all matching non-scan records import when the file is selected, even with
`--scan`. Fully imported includes journal entries. Duplicate-only import still says **Nothing new:
/reload first**. Follow OPS-03 before clear, then verify current-login entries survived the write.

### Event journal beta checklist — Mac and Windows, pending; aim by 13 October

Use a new character with one gathering profession and one crafting profession that uses it, a
little gold, and a second character on the **same account/realm/faction** for mail. Start a fresh
login so the login marker is known. Repeat on each machine. Keep recordings private and do not
clear evidence until the latest drop is fully imported. Enable Lua error reporting through the
client's settings or `/console scriptErrors 1`; record errors, including errors that interrupt a
hook or event handler. Do not change the candidate list simply to hide rejected/missing APIs.

For **every row below**, note OS/machine, build/interface/addon version, character/realm/faction,
action/time, journal IDs and shared sequences, events fired **and rejected**, missing/installed
hooks and actual hook arguments (including nil positions), before/after copper and bags, open
windows, mailbox counts/headers/invoices/attachments where relevant, Lua errors and lag.
Save a file before/after each family using `/reload` or logout; note journal/overflow counts,
file bytes and reload duration. Record unavailable values explicitly, never as zero.

| Family | Manual actions in game | Evidence to compare in the file |
| --- | --- | --- |
| Baselines/money/bags | Login, `/reload`, wait without changes, split a stack, move it, then acquire/remove one item and spend/receive a few copper. Open/close the bank. | PLAYER_MONEY before/after; BAG_UPDATE_DELAYED deltas across carried bags; no entry for a split/move or unchanged totals; windows; missing-baseline evidence if unreadable; snapshots/journal interleaved sequences. |
| Auction | Buy a cheap item; post two small stacks, cancel one, allow one short auction to expire, and arrange for an actual player to buy another. Bid and get outbid if practical. | Global or C_AuctionHouse hook names/arguments, purchase/post/cancel events, deposits and money changes, bag changes, owned-list events. Identify hook attempts versus actual success; preserve rejected/missing event/function names. Sold/expired/cancelled/outbid evidence arrives by mail, not inferred from a missing auction. |
| Mail/invoices/returns | Open the mailbox, refresh unchanged inbox, manually open sold/expired/cancelled/outbid mail, take gold and returned items, close/reopen. | One state per changed inbox; every header: sender, subject, money, COD, days, item count, read flag; invoice type/item/other player/bid/buyout/deposit/cut; attachment info/link; take hooks and money/bag deltas. Opening marks read and can legitimately change the state. Nil invoice fields stay missing. |
| Send/receive mail | Attach a small item and a little gold; send to your other character. Also exercise COD if affordable. Log into recipient; receive/take the mail manually. | MAIL_SEND_INFO_UPDATE draft money/COD/attachments/time, SendMail recipient arguments and last-observed draft, success/failure events, sender gold/bag changes; recipient headers and take hooks/deltas. Check whether draft APIs update before send and whether they clear afterward. Never assume successful delivery from the post-hook. |
| Craft | Open the crafting window, make one inexpensive recipe (and a short batch), then close it. If possible interrupt/fail one craft, and close the window during a batch. Cast a combat spell afterwards. | DoTradeSkill/DoCraft/C_TradeSkillUI.CraftRecipe arguments, one UNIT_SPELLCAST_SUCCEEDED per successful craft while the window was open (none for the interrupted craft, combat spells or other units), consumed/created item deltas and window context. Note whether batch crafts after closing the window still finish. Check quantities against the actual recipe without interpreting journal transactions yet. |
| Vendor | Buy one cheap reagent, sell one expendable item, repair damaged gear if available; close merchant. | BuyMerchantItem/SellCursorItem/global or C_Container.UseContainerItem/RepairAllItems arguments, merchant events, money/bag changes. Container use outside a merchant should not log as a sale; post-hook does not assert success. |
| Gathering/loot | Gather one node/herb, loot one mob, then join a group where someone else loots. Close the loot window. | Own loot-window events, bag gains and CHAT_MSG_LOOT raw arguments (gathering casts are not recorded); argument 12 must match own GUID. Other/ambiguous loot chat is omitted. Record if Forever omits that GUID; bag/window evidence should still capture own gains. |
| Clear/transport | Open mailbox before clear; `/reload`, import, clear and `/reload` within this login. Then logout/drop/import, fresh login/clear. | Current-login IDs/content survive both clear forms and the button; old records prune only with known login. Confirm no false fully-imported state, exact bronze bytes, machine, overlapping-drop duplicates and entry counts. Unknown login keeps all. Existing scan clear protections still work. |
| Cap/size | Measure a normal 30–60 minute economy session with the above actions. For cap testing use a separate disposable SavedVariables copy populated with offline stub records, never your only recording. Add a few manual economy actions at the cap, reload/drop twice. | Count and bytes before/after, CPU/lag/reload time; one overflow marker, cumulative skipped increment and changing ID; one problem message; earlier entries untouched. Current-login marker survives clear; old-session prune creates space. Restore the normal file only with WoW closed after preserving/importing the test copy. |

**Measurements pending:** no real 0.6.0 journal recording has been supplied. Fill a private
measurement row per family and a normal-session row (elapsed minutes, entries by family, file
bytes, bytes attributable to journal, skipped count, reload seconds, build, machine, errors).
Record actual API support and failures before 21 October; offline tests do not establish beta support.

### Preserve a real recording as a replay fixture before 21 October

1. `/reload` or log out and **close WoW**; wait for writing to finish. Copy the entire account
   SavedVariables file, unchanged, to an immutable private path such as
   `data/inbox/event-journal/mac-20261013T180000Z-BrownstoneScan.lua`. Windows uses the existing drop
   script; retain the dropped file locally too. Never edit the original game file to make it pass.
2. Record SHA-256 and bytes (`shasum -a 256 <private-copy>` and `wc -c <private-copy>` on Mac;
   `Get-FileHash -Algorithm SHA256 <private-copy>` on Windows). Keep the action/measurement log next
   to this private copy with the build, expected changes, actual hook arguments and error text.
3. Treat that immutable file as the **real replay fixture**: point an addon source at its copy and
   an isolated `work/` data directory, preview and import twice with the CLI. Compare family counts,
   raw JSON, IDs, scope, first-import versus duplicate outcomes and exact decompressed bronze bytes.
   Repeat with two overlapping recordings to check duplicates; do not import altered same-ID content.
4. For a committed regression test, select the smallest representative entries per family using
   `scans.read_addon_records(copy.read_bytes())`, plus related snapshots, and the actual assertions
   from the action log. Keep a private provenance note mapping them to raw-file hash/entry IDs.
   Anonymize character/realm/recipient/body/link identifiers in a **derived** fixture only, regenerate
   its length-prefixed IDs consistently, and label it derived from the measured recording. Retain
   the unchanged recording privately. Add it under `tests/fixtures/` with a replay test in
   `tests/test_journal.py`; never commit the full raw account file, private log or personal paths.
5. Run `.venv/bin/pytest --cov`, `.venv/bin/ruff check .`, `.venv/bin/mypy` and `git diff --check`.
   Record results and measurements here; real-recording acceptance stays pending until this is done.
