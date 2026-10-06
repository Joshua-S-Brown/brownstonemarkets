# Brownstone Scan 0.3.1

A **read-only** auction house scanner for WoW Forever. It captures listings, seller and variant evidence, and official item-reference data for local market research. Brownstone imports its file through an addon source (see the main README and `docs/requirements.md` → *Addon scans*).

## What it does and doesn't do

- A scan starts only when you click **Brownstone Scan** on the auction house window, or type `/bscan start` while it is open.
- It never bids, buys, posts or cancels, and never scans on a timer or unattended. Closing the window stops a running scan, keeping the listings read so far and marking the scan `stopped`.
- It issues one request, `C_AuctionHouse.ReplicateItems()`, which is Blizzard's own full-snapshot call, then reads the result. If the client has only the older Classic API, it falls back to the `QueryAuctionItems` "get all" scan. Each scan records which one it used (`api`).
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
3. Click **Brownstone Scan** (or `/bscan start`). The button shows progress. Leave the window open.
4. When chat says the scan is finished, click **Reload** (or type `/reload`) to make the game write the file.
5. Repeat once at a neutral auction house with `/bscan label neutral`. Wait 15 minutes between scans.

Commands: `/bscan start | stop | status | label <text> | clear [all]`.

**Keep the file small, in this order:** scan, `/reload` (the game writes scans to the file only then, or on logout), import, and only then `/bscan clear` and `/reload`. The addon keeps every scan until you clear it, and each import reads the whole file. `/bscan clear` refuses while a scan from this session hasn't been written to the file yet (`/bscan clear all` overrides that). After an import that saved something new, Brownstone says clearing is safe; if it says *Nothing new*, `/reload` and import again first.

### Reload and clear controls (STORY-029)

Version 0.3.1 adds **Clear saved scans** and **Reload** immediately to the left of **Brownstone Scan**, using the same auction-window parent and standard `UIPanelButtonTemplate`. The scan button keeps its existing position; the row extends left with 4-pixel gaps (Clear 140×22, Reload 70×22). Both new buttons are disabled from scan start until completion or any stop/error/timeout path. Reload calls `ReloadUI()` directly; clearing never automatically reloads, so the user controls when changes are written.

**Visibility decision:** the controls are available only with the auction house open, like the existing scan button. This keeps one small, contextual row without a persistent screen panel or new commands. For the manual scan → Reload → import → Clear → Reload routine, leave the house open during the import or reopen it afterward; the existing slash commands also work with the house closed.

**Clear decision:** the button shares the protected `/bscan clear` logic and never uses the `all` override. Unsaved session scans refuse immediately with reload/import guidance. Otherwise a standard `StaticPopupDialogs` / `StaticPopup_Show` confirmation names the saved-scan count and reminds you to import into Brownstone first. Cancel or Escape changes nothing; there is no timeout or automatic acceptance. Zero scans still get confirmation, matching the command's harmless empty clear. Accept removes only `BrownstoneScanDB.scans`, preserves the label/metadata, and prints the existing next-reload reminder. Slash commands retain their existing behaviour, including immediate protected clear and the explicit `clear all` override.

**Pending-confirmation decision:** starting a scan or closing the house dismisses the popup with `StaticPopup_Hide`. The callbacks also refuse during a scan and recheck unsaved scans and the confirmed count at acceptance, protecting against state changes after the dialog opened. If the count changed, click Clear again to review it.

**Beta check passed 2026-10-06** (build 1.60.1.70235): interface **16001** matches the client; the three-button row sits above the auction window without overlap; Reload writes the file, and Clear refused while a just-finished scan was unsaved. Chat confirmations are hard to see at small window sizes. Escape on the popup was not separately exercised in game. The standard popup contract is visible in the [Classic client UI source](https://github.com/Gethe/wow-ui-source/blob/classic/Interface/AddOns/Blizzard_StaticPopup/StaticPopup.lua).

**Updating the addon:** copy the new `BrownstoneScan` folder over the old one and `/reload`. Scans saved by an older version stay in their format and still import.

## Where the data goes

After `/reload` or logout:

```
<Forever folder>/WTF/Account/<ACCOUNT NAME>/SavedVariables/BrownstoneScan.lua
```

It holds one table, `BrownstoneScanDB`, with `schema_version` and a `scans` list. Addon 0.3.1 writes the unchanged format 3; scans written by 0.1.0/0.2.0 keep formats 1/2 and still import. Capture rules, APIs, variant identity and beta limits live in `docs/requirements.md` → ADDON-08/09. Each scan has:

| Field | Meaning |
| --- | --- |
| `schema_version`, `scan_id` | Format version (1, 2 or 3) and a unique ID (UTC start time plus random suffix). |
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
| `listing_format`, `names` | Formats 2/3: the field order of each listing, and distinct item names. |
| `sellers`, `level_types`, `links` | Format 3: distinct original strings, indexed per listing; sellers stay local (ADDON-07). |
| `items` | Format 3: one table per item ID with nullable official reference observations (ADDON-09). |
| `listings` | One entry per auction, below. |

**Format 3 listings** extend format 2 in this exact order:

```text
item_id:quantity:buyout:min_bid:bid:flags:name_index:seller_index:time_left:quality:level:level_type_index:link_index
```

For example, `"6538:1:500:0:0:1:1:1:4:2:10:1:1"`. The four text indexes point into `names`, `sellers`, `level_types`, `links`; index 0 means missing. Missing time-left, quality or level is an **empty field**, not zero. A reported quality or level of zero remains zero. The full original listing link is retained for every available listing, including plain items, so future parsers can inspect all evidence. Seller uses the API's full name when present, otherwise its owner name. `required_level` is derived during import only for level type `REQ_LEVEL` or Classic's `REQ_LEVEL_ABBR` (record the actual value in the beta). A time left outside 1–4, quality outside 0–8 or negative level is imported as missing and counted under `listing_out_of_range`; the scan is not rejected.

`items` is an array of keyed tables: `item_id`, `class_id`, `subclass_id`, `item_level`, `max_stack_size`, `vendor_sell_copper`. Unavailable fields are omitted by Lua and become null in import. These are one lookup attempt per ID per scan, not variant stat summaries. A reported vendor sell price of zero is distinct from missing.

Import stores the new listing fields, raw link, variant identity/resolution, base-item observations and availability counts. Formats 1/2 keep every new field null. Format 1 links survive in the raw archive but are not retrospectively classified. Browse, Opportunities and Scan changes show variant ID/state (`legacy` for formats 1/2); catalog crafting/depth uses only base rows in format 3. See ADDON-08 for exact grouping and legacy behavior.

**Format 2 listings** are one string each, `item_id:quantity:buyout:min_bid:bid:flags:name_index`, for example `"2589:20:700:0:0:1:3"`. Prices are integer copper as the client reported them, and `0` means none (no buyout or no bid). `flags` adds 1 when the client had loaded the item's details (`complete_info`) and 2 when it reports a commodity (Brownstone rejects those scans, since only stack prices are modeled). `name_index` points into the scan's `names` list (1 is the first name), or is `0` when the client hadn't loaded the name. Names are kept per listing because one item ID can carry several random-suffix names ("of the Monkey", "of the Eagle"). About 28 bytes per listing.

**Format 1 listings** (addon 0.1.0) are tables with `item_id`, `name` (empty until the client has loaded the item), `link` (missing until loaded), `quantity`, `buyout`, `unit_buyout` (copper per unit, or missing), `min_bid`, `bid` (only when someone has bid), `commodity` (only when the client says) and `complete_info`. About 240 bytes per listing.

Prices are integer copper. A missing `buyout` means the listing has no buyout; it is never zero or free. On the Forever beta (first scan, 2026-10-04) `buyout` is the price of the **whole stack**, not per unit, and `commodity` is never reported. Brownstone divides `buyout` by `quantity` itself, rounding up when inexact; format 1's `unit_buyout` is only a cross-check, and format 2 doesn't write it. A listing the client hasn't fully loaded has no name and `complete_info` false; its item ID, quantity and buyout are still valid.

A hand-written example is in `tests/fixtures/brownstone_scan_sample.lua`.

## Measurement checklist

Keep results and SavedVariables files locally. Format 3 files contain seller names and must not be shared, uploaded or sent to an external service (ADDON-07). Availability summaries contain counts only.

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

Accepted 2026-10-06 (record below). Repeat it for any later scan-format change. Every baseline and candidate measurement must name the exact addon version used (including 0.3.1 if these controls are installed). The format-3 capture contract and ADDON-09 limits are unchanged; do not label 0.3.1 measurements as 0.3.0. Record versions alongside the local aggregate report; older scans do not carry a per-scan addon version, so use the installed version and retained file provenance rather than guessing.

1. **Baseline:** using 0.2.0, take one complete scan at the same house, `/reload`, retain a local single-scan file, import it, then `/bscan clear` and `/reload`. If an existing 0.2.0 file has exactly one scan, it can be the baseline. Record build, house, listing count, duration and uncompressed file bytes.
2. **Update and capture:** copy the current addon over the installed addon, `/reload`, confirm it loads and `/bscan status` works. At least 15 minutes after the preceding scan, click the scan button with the house open. Record lag/errors and finished vs reported count. `/reload`, retain the local single-scan file, then Preview/Import in Brownstone. Confirm completed format 3, official reference data and separate variant rows. Try `/bscan start` on another manually initiated scan; closing the house during reading should save only a partial scan and no prices.
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
                                                         scan_details.item_frame(record),
                                                         scans.optional_out_of_range(record))}
    results.append(result)
    print(json.dumps(result, indent=2))
if len(results) == 2:
    old, new = results
    if old["duration_seconds"] and new["duration_seconds"] is not None:
        print("Duration ratio:", new["duration_seconds"] / old["duration_seconds"])
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
