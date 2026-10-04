# Brownstone Markets requirements

Accepted product behavior and decisions. This is the single home for rules; other documents link here instead of restating them. Planned work lives in `backlog.md`, architecture in `design.md`, current state in `status.md`.

## Product direction

- **Purpose:** a local WoW market research tool that traces materials through intermediate crafts to finished goods and explains which crafts are worth investigating.
- **Target game:** WoW Forever (beta since 17 September 2026; launches 4 November 2026). It has no public price feed, so the baseline source is our own read-only scanning addon, imported as described under *Addon scans* below.
- **Known Forever market facts** (checked 2026-10-04, mostly third-party; re-verify at launch):
  - Forever has no realms. Each region (US, EU and so on) has one auction house per server type (Normal, PvP, RP, later Hardcore) and faction, plus a neutral house with a 15% cut instead of 5%.
  - Blizzard's API publishes no Forever auction data, and TSM has no Forever data.
  - Existing Forever price sites are fed by players' addon scans. Forever addons reportedly use the modern `C_AuctionHouse` API, which has Retail-style commodities.
  - Forever reuses Classic item IDs: 2,323 of the 2,927 items priced in the 2026-10-04 beta scan are also priced on Classic Era Mankrik under the same IDs. Prices differ (see STORY-012), so this allows explicit comparison, never joining (DATA-03).
  - Sources: [Wikipedia](https://en.wikipedia.org/wiki/World_of_Warcraft:_Forever), [AHledger](https://ahledger.com/wow-forever/auction-house), [WowGuide realms](https://wowguide.net/en/guides/wow-forever-realms-rulesets), [Blizzard API forum: Classic Era auction 404s](https://us.forums.blizzard.com/en/blizzard/t/404-for-all-classic-era-namespace-auction-house-endpoints/54307), [WOW4E_AH_Trader](https://github.com/1nd1v1d/WOW4E_AH_Trader).
- **Development stand-in:** Mankrik Alliance, Classic Era (TSM public realm CSV). Classic is used to build and prove the product, not as the end market. Switching to Forever must be a configuration and catalog change: add a source whose market fields describe the Forever house and whose `rules_version` matches a Forever catalog. It must not require code changes.
- **Retail:** not a product requirement (decided 2026-10-04). Retail sources remain configured only as an ingestion regression check, because they exercise regional scope and upstream timestamps that Classic lacks. No feature work targets Retail. They may be removed when they stop earning their keep.
- **Launch market (decided 2026-10-04):** Forever, US region, Roleplaying server type, Alliance faction. The neutral auction house is a separate, secondary market. The user has beta access, so SPIKE-008 targets the Forever beta directly.
- **Dependable data (decided 2026-10-04):** nothing in the architecture may require a source the user doesn't control.
  - **Baseline source:** the user's own addon scans. Every feature must work with only this.
  - **Optional sources:** other players' aggregated scans (third-party sites, TSM). They may only enrich or cross-check, never be required.
  - **Access rules:** a third-party source is used only through an official export or API whose terms allow it, never by scraping.
  - **Removability:** if an optional source disappears, Brownstone keeps working on the baseline.
- **Addon (decided 2026-10-04, SPIKE-008): build it.** A read-only addon, `addon/BrownstoneScan/`, scans only after a click or slash command at the auction house and never buys, posts, cancels or scans unattended.
  - **Evidence:** on the Forever beta (client 1.60.1, build 70205), one scan of the Alliance Normal-server house in Stormwind used `C_AuctionHouse.ReplicateItems` and saved 101,485 listings in about 10.6 s, in a 24 MB SavedVariables file. A second scan three minutes later got no reply, as the documented 15-minute account-wide throttle predicts. The client has no legacy auction event.
  - **Not measured:** the Roleplaying house (not yet available in the beta), a neutral house (out of reach for now), and whether a slash command alone is accepted without the button click. The button worked.
  - **Scan format STORY-010 ingests:** `BrownstoneScanDB` with a list of scans, each with its own `schema_version`; fields are documented in `addon/README.md`, with a sample at `tests/fixtures/brownstone_scan_sample.lua`. Schema 1 (addon 0.1.0) writes one keyed table per listing. Schema 2 (addon 0.2.0, decided 2026-10-04 to keep the addon light and the file small) writes one `item_id:quantity:buyout:min_bid:bid:flags:name_index` string per listing and each scan's distinct names once; it drops `link` and `unit_buyout`, which Brownstone never used. Both import to identical listings and prices, and a file may hold both. Each scan has a `scan_id`, UTC start and finish, `status` (`completed` or `stopped`), `listing_count` against `reported_count`, client build, region, realm, player faction, auctioneer and zone, and a free-text `label`. Import treats these as evidence of which house it is, never as a market (ADDON-01).
  - **Listing semantics:** Forever's `buyout` is the price of the whole stack (Classic-style), with `quantity` the stack size, and no commodity status is reported. The addon does no pricing: import divides `buyout` by `quantity` itself (ADDON-02). Schema 1's `unit_buyout` was meant to hold that division but was missing on all 28,105 stacked listings of the 2026-10-04 scan; it is only a cross-check, and schema 2 doesn't write it. A listing the client flags as a commodity (per-unit price) rejects the scan, since only stack prices are modeled. A missing `buyout` means no buyout, never free. Listings the client hadn't fully loaded (4,690 in that scan) have an empty `name` and no `link`, but valid item ID, quantity and buyout.
  - **Known costs:** schema 1 takes about 240 bytes per listing (24.8 MB for the 101,485-listing scan); schema 2 about 28 (2.8 MB, parsed in 0.1 s). The addon keeps every scan until `/bscan clear`, which refuses scans not yet written to the file (they exist only in game memory until `/reload` or logout). Brownstone suggests clearing only after an import saved something new; an import with nothing new warns to `/reload` instead (decided 2026-10-04, after a scan was lost by clearing before it was written). Region and realm are generic on the beta and do not identify the house.
- **Recipe data (decided 2026-10-04, STORY-004):** catalogs are generated from Wowhead profession pages that the user saves in a web browser, one page per game version and profession (for example `https://www.wowhead.com/forever/spells/professions/tailoring`). Brownstone never downloads from Wowhead.
  - **Terms:** Wowhead's terms (`wowhead.com/tos` → ZAM Network EULA, last updated 14 May 2025, checked 2026-10-04) grant a personal, non-commercial licence to use the websites "solely for your own internal use". They forbid downloading content with "spiders, robots, crawlers, data mining tools or the like" other than ordinary web browsers, and they allow ZAM's APIs only as documented (the tooltip API is documented for embedding tooltips on web pages). So scripted fetching, including of `nether.wowhead.com` tooltips, is not allowed. Pages saved by hand in a browser are.
  - **Why one page:** a saved profession list page holds every recipe of the profession: reagents, quantities, created item and count, and the skill level it's learned at. It also holds every item it mentions, with name, sell price and buy price. Forever pages also mark each spell as new, updated or unchanged relative to Classic, but Runecloth Bag is marked unchanged despite its new dyes, so the marker isn't trusted for reagents.
  - **Alternatives considered:** reading the in-game Tailoring and trainer windows with the addon would confirm output counts but covers only recipes the character knows. wago.tools has no Forever build. Both stay options for confirmation, not the catalog source.
- **Out of scope:** automated buying, selling or posting, unattended in-game scanning, cloud deployment and AI-generated recommendations without explainable features.

## Rules

### Data integrity
- **DATA-01 Raw preservation:** every download is saved byte-for-byte before validation. Each has a manifest with source, SHA-256, UTC collection time and status, including failures. Raw files are never overwritten. An addon scan file whose bytes (SHA-256) are already in that source's bronze folder is not copied again; the new manifest names the existing file in `bronze_file` (decided 2026-10-04, because scan files are about 24 MB). New addon copies are stored gzip-compressed (`.lua.gz`, decided 2026-10-04 to save disk): the manifest's SHA-256 is of the original bytes, and the copy is checked to decompress to them before it is kept, so preservation stays exact. Earlier `.lua` copies stay as they are.
- **DATA-02 Validation:** required columns, integer copper prices, unique positive item IDs and timestamps that are either all present or all absent. A missing name becomes `Item <ID>`. Zero means unavailable or no listing.
- **DATA-03 Market identity:** a market is one auction house: `game_version + region + scope + realm + server_type + faction`. Item IDs never join across any of these.
  - **Fields:**
    - `scope` is `house` (one auction house) or `region` (a region-wide commodity pool).
    - `realm` names the house where realms exist; `server_type` (normal/pvp/roleplaying/hardcore) names it in realmless Forever. A market uses one or the other, never both.
    - `faction` is alliance, horde, neutral, or blank for cross-faction houses.
  - **`market_id` is derived, never configured** (for example `classic-us-mankrik-alliance`, `forever-us-roleplaying-alliance`), so two sources for one house always agree.
  - **Auction cut:** set per source. Neutral houses default to 15%.
- **DATA-08 Source independence:** a market's identity says *which auction house*. A source's identity (`source_id`, `provider`) says *who observed it*: your addon, TSM or a third-party site. The same market can have several sources. Every manifest and price observation records its source, deduplication is per source, and each source keeps its own data folder. Combining sources follows an explicit, versioned policy, never silent mixing. Until that policy exists (STORY-011), each view reads one selected source.
- **DATA-04 Deduplication:** identical market, scan time and content hash reuse one analytical snapshot. Every raw collection is still recorded with its own manifest. Addon scans deduplicate by `scan_id` per source instead (ADDON-04).
- **DATA-05 Freshness:** age comes from upstream scan time when the source provides it (for addon scans, the scan's finish time). Otherwise it comes from collection time, explicitly labeled as "price age unknown". Stale means older than `max_age_hours` (default 24) or more than 15 minutes in the future. A source may opt out of upstream time only when the entire column is blank (`allow_missing_updated_at`).

### Addon scans (decided 2026-10-04, STORY-010)
- **ADDON-01 House identity:** the configured source defines the market; nothing is derived from a scan. Each scan's player faction must match the market's alliance or horde faction, and must not be from a neutral house. A neutral market needs the client's `neutral = true` or a configured auctioneer. Optional `scan_evidence` (`faction`, `auctioneer`, `zone`, `realm`, `label`) must match exactly. Any mismatch in any selected scan fails the whole import, naming the scan, field, observed and configured values, before anything reaches DuckDB. Beta region and realm are generic and aren't evidence by default.
- **ADDON-02 Stack pricing:** a listing's unit price is `buyout / quantity` in integer copper. When that isn't exact, `unit_buyout` stays empty and `unit_buyout_ceil` rounds up, so a unit's cost is never understated; derived prices use `unit_buyout_ceil`. On the sale side this can overstate a unit by under 1c; the manifest counts such stacks (`nonexact_stacks`). A reported `unit_buyout` (schema 1) that disagrees with the division rejects the scan. A missing or zero `buyout` has no unit price and is never free.
- **ADDON-03 Item prices:** each complete scan writes one `market_snapshots` row per item:
  - `min_buyout`: the cheapest unit price.
  - `market_value`: the quantity-weighted 25th percentile of unit prices (nearest rank, each listed unit counted once). It is the price that buys a quarter of listed supply. It ignores one stray cheap stack, which `min_buyout` already shows, and high listings that never sell, which can dominate a median on thin markets. It is close in spirit to TSM's average of the cheapest 15–30% of units.
  - `recent_value` and `historical_value`: 0 (unavailable), so the discount screen explains it can't run.
  - Items listed only without a buyout get 0/0, so Browse still finds them.
  - Cautious and listed bases (CRAFT-04) use these unchanged.
- **ADDON-04 Deduplication and partial scans:** a scan is identified by `scan_id` per source. Re-importing it is a no-op; the same `scan_id` with different content fails. A scan is partial when `status` isn't `completed` or `listing_count` differs from `reported_count`. Partial scans are stored and labeled, listings included, but never feed prices, because they can miss the cheapest listing. A file with no complete scan leaves prices unchanged. The newest complete scan in a file becomes its snapshot, and the views use the newest observation across imports, so an older file can't replace newer prices.
- **ADDON-05 Time:** a scan's finish time is its observation time. Old scans import, and the board labels them stale. A scan finished more than 15 minutes in the future is rejected as a clock error.
- **ADDON-06 Import is read-only and on demand:** only the **Import addon scan** button or the CLI imports, from the configured `scan_path` (or `--input`). The file is read, never written, watched or polled.

### Money
- **MONEY-01:** store and calculate integer copper only. 1g = 100s = 10,000c.
- **MONEY-02:** display gold. Tables show decimal gold with four places, so one copper is exact and columns sort numerically. Headline figures and prose use `4g 50s 97c`.

### Crafting
- **CRAFT-01 Versioned catalogs:** each catalog declares `game_version`, `rules_version` (the game build's rules, distinct from Forever server types), `catalog_version`, status, and provenance URLs for every item and recipe. Classic and Forever catalogs never share rules implicitly. A catalog used for decisions records verification evidence for every recipe quantity and vendor price. Changing a verified value requires new evidence and a `catalog_version` bump.
- **CRAFT-02 Expansion:** intermediates expand without cycles or double counting. Unsupported cases (cycles, fractional units) are rejected, not approximated.
- **CRAFT-03 Routes:** each input uses its cheapest valid route: buy, craft or vendor. Missing or zero prices are never free. Equal costs resolve deterministically.
- **CRAFT-04 Price bases:**
  - **Cautious** is the default for ranking and labels. It buys inputs at the higher, and sells output at the lower, of minimum buyout and market value. When only one value is positive, that value is used.
  - **Listed** uses minimum buyout only.
  - Every board row shows profit under both bases.
- **CRAFT-05 Action Board:** ranks finished outputs of any catalog compatible with the selected market (same game version and `rules_version`).
  - Shows craft cost, sale price, net revenue after the auction cut, profit and margin, where margin = profit / net revenue.
  - Labels, in precedence order:
    1. **unsupported recipe:** calculation error; the message is shown.
    2. **missing prices**
    3. **stale data**
    4. **potential craft:** profit > 0.
    5. **negative margin:** profit ≤ 0.
  - Sorts by profit or by margin, descending, then the other metric, then recipe ID. Incomplete rows sort last.
  - Policy version is shown.
- **CRAFT-06 Explanation:** for a selected recipe, show:
  - direct inputs with route, unit and total cost, observed prices and source
  - the shopping list for the chosen routes
  - the all-craft materials
  - break-even sale price
  - assumptions, provenance and freshness
- **CRAFT-07 Rounding:** net revenue rounds down to the copper; break-even rounds up. Quantities are per recipe execution.
- **CRAFT-08 Generated catalogs (STORY-004):** a catalog is generated by `python -m brownstone recipes`, or the app's **Recipe catalogs** page through the same code, from one saved page plus a tracked selection file (`config/recipe-selections/<catalog>.toml`), never edited by hand.
  - **One per game version and profession:** named `<prefix>-<profession>`, with prefix `classic-era` or `forever` (for example `forever-leatherworking`). A catalog exists when its selection file does; nothing finds catalogs by file name pattern.
  - **Same version only:** the page's game version and profession must match the selection's. Values never come from another version's page.
  - **No seasonal spells:** Wowhead's Classic pages also list seasonal realms' spells (`seasonId`, 2 = Season of Discovery): 57 of 287 Tailoring and 48 of 204 Enchanting on the 2026-10-04 pages. They are never offered, never added as intermediates, and a selection naming one is refused.
  - **Selection:** lists finished recipes. A reagent made by exactly one usable recipe on the page is added as an intermediate.
  - **One rule for every profession:** a recipe is usable only if it makes a fixed, known quantity (Wowhead lists some transmutes and oils as making 0, meaning unknown) and isn't seasonal. An item that several usable recipes make is always bought, never crafted, and those recipes can't be selected. So a catalog never chooses between recipes, and the app never asks. It changes nothing on the saved Tailoring and Enchanting pages; it exists for Alchemy's transmutes.
  - **Evidence:** every recipe records its Wowhead spell URL, the page URL, the date the page was saved and the page's SHA-256. The saved page is archived byte-for-byte under `data/recipe-sources/` with a manifest.
  - **Vendor materials need evidence:** Wowhead gives a buy price to items no vendor sells (Felcloth, elemental essences, raid gear), so a buy price never makes an item a vendor material. The selection marks vendor items, with evidence or `vendor_verified = false`. The page's buy price is the vendor price; it replaces the sell price × 4 estimate (they differ for Coarse Thread: 10c, not 8c).
  - **Unconfirmed values are marked:** `output_quantity_verified = false` and `vendor_verified = false` stay until confirmed in game, and the recipe view shows them. Forever output counts are unconfirmed: Wowhead's list data says 1 for every Tailoring recipe, but its spell tooltips show "(2)". So a Forever catalog added in the app marks every yield unconfirmed, and any vendor item marked there gets `vendor_verified = false`.
  - **Availability:** a recipe or item may be marked `availability = "post-launch"` with a note. It is display-only; the board still prices it.
  - **Staying current:** after a game update, re-save the page and regenerate. The command lists recipe and vendor price changes for review; a changed value bumps `catalog_version`. In the app, **Regenerate** bumps the minor part of the selection's `catalog_version` (0.1 → 0.2) whenever the catalog file would change, and does nothing when the page reproduces it exactly.
  - **Refresh due:** the app flags a catalog when an enabled market of the same game version uses another `rules_version`, or when its page is older than the selection's `refresh_after_days` (default 30).
  - **Edited, never re-dumped:** the app edits an existing selection file line by line, keeping its comments, and refuses any edit that doesn't read back as chosen. Removing recipes drops notes on items nothing uses any more; the preview lists each one.
  - **Must load:** a catalog the board's loader would reject (for example two recipes making one item) is refused before anything is written.

### Interface
- **UI-01:** browsing saved data never triggers a download or import. Only **Refresh from TSM** (TSM sources) or **Import addon scan** (addon sources) collects, and only for the selected source. Disabled sources (`enabled = false`) are hidden.
- **UI-02:** Browse market finds items regardless of price or discount. Categories are not inferred from names or commodity status.
- **UI-03:** the discount screen (Opportunities) explains when a source cannot support it, for example Classic historical values being zero. Its spread is integer copper: the reference price after the auction cut rounds down, as in CRAFT-07. Search filters the ranked list without renumbering it.
- **UI-04:** an incompatible catalog can be inspected, but is never priced.
- **UI-05:** the launcher reuses a running server only if its code is current. It restarts its own outdated server and never stops a server it did not start.

### Operations
- **OPS-01:** tests are offline and run in CI on macOS and Windows from the lock file, including the UI test, alongside Ruff and mypy. No market data is stored in Git.
- **OPS-02:** database schema changes go through numbered, idempotent migrations.
  - A database newer than the code is refused, never modified.
  - Before migrating, the existing file is copied to `data/brownstone.v<N>.backup.duckdb`.
  - The app upgrades at startup and the pipeline before writing, so read-only views never see an outdated schema.
  - Manifests written before a change are read through an upgrade adapter; they are never edited.

## Not modeled (do not imply otherwise)

Demand, sale likelihood, listing depth (addon listings are stored but no calculation uses them yet), deposits, recommended quantities, vendor stock, reputation discounts, recipe quality/rank, reagent alternatives and multi-yield recipes. The importer rejects variable yields, and an intermediate yielding more than 1 can fail with "Fractional unit costs". Every current catalog recipe yields 1.

## Open decisions

- Useful action thresholds beyond profit > 0.
- Classic regional demand integration (STORY-003).
- Which third-party Forever aggregates, if any, offer a usable export or API (STORY-011).
- Historical storage, backup and scheduling.
- Whether to remove the Retail regression sources. SPIKE-008 found Forever listings are per-stack, not Retail-style per-unit commodities, so the Retail commodity feed is not a close test of Forever's model.

None is approved by default.
