# Brownstone Scan (SPIKE-008 prototype)

A minimal, **read-only** auction house scanner. It answers one question: can an addon capture every listing on a WoW Forever auction house? Brownstone imports its file through an addon source (see the main README and `docs/requirements.md` → *Addon scans*).

## What it does and doesn't do

- A scan starts only when you click **Brownstone Scan** on the auction house window, or type `/bscan start` while it is open.
- It never bids, buys, posts or cancels, and never scans on a timer or unattended. Closing the window stops a running scan, keeping the listings read so far and marking the scan `stopped`.
- It issues one request, `C_AuctionHouse.ReplicateItems()`, which is Blizzard's own full-snapshot call, then reads the result. If the client has only the older Classic API, it falls back to the `QueryAuctionItems` "get all" scan. Each scan records which one it used (`api`).
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
4. When chat says the scan is finished, type `/reload` to make the game write the file.
5. Repeat once at a neutral auction house with `/bscan label neutral`. Wait 15 minutes between scans.

Commands: `/bscan start | stop | status | label <text> | clear`.

## Where the data goes

After `/reload` or logout:

```
<Forever folder>/WTF/Account/<ACCOUNT NAME>/SavedVariables/BrownstoneScan.lua
```

It holds one table, `BrownstoneScanDB`, with `schema_version` and a `scans` list. Each scan has:

| Field | Meaning |
| --- | --- |
| `schema_version`, `scan_id` | Format version and a unique ID (UTC start time plus random suffix). |
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
| `listings` | One entry per auction, below. |

Listing fields: `item_id`, `name` (empty until the client has loaded the item), `link` (missing until loaded), `quantity`, `buyout` (copper, as the client reported it), `unit_buyout` (copper per unit, or missing), `min_bid`, `bid` (only when someone has bid), `commodity` (only when the client says; absent on the beta) and `complete_info` (false when the client hadn't yet loaded the item's details).

Prices are integer copper. A missing `buyout` means the listing has no buyout; it is never zero or free. On the Forever beta (first scan, 2026-10-04) `buyout` is the price of the **whole stack**, not per unit, and `commodity` is never reported. `unit_buyout` is meant to be `buyout / quantity` when that divides exactly, otherwise missing. In the 2026-10-04 scan it is missing on every stacked listing, although all of them divide exactly (an open follow-up). Brownstone divides `buyout` by `quantity` itself, rounding up when inexact, and only cross-checks `unit_buyout`. A listing the client hasn't fully loaded has an empty `name`, no `link` and `complete_info = false`; its item ID, quantity and buyout are still valid.

A hand-written example is in `tests/fixtures/brownstone_scan_sample.lua`.

## Measurement checklist

Fill in after each run and send me the SavedVariables file (or its first scan) too.

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
