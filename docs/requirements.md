# Brownstone Markets requirements

Accepted product behavior and decisions. This is the single home for rules; other documents link here instead of restating them. Planned work lives in `backlog.md`, architecture in `design.md`, current state in `status.md`.

## Product direction

- **Purpose:** a local WoW market research tool that traces materials through intermediate crafts to finished goods and explains which crafts are worth investigating.
- **Target game:** WoW Forever (beta since 17 September 2026; launches 4 November 2026). It has no public price feed, so the planned source is our own read-only scanning addon (SPIKE-008, STORY-010).
- **Known Forever market facts** (checked 2026-10-04, mostly third-party; re-verify at launch):
  - Forever has no realms. Each region (US, EU and so on) has one auction house per server type (Normal, PvP, RP, later Hardcore) and faction, plus a neutral house with a 15% cut instead of 5%.
  - Blizzard's API publishes no Forever auction data, and TSM has no Forever data.
  - Existing Forever price sites are fed by players' addon scans. Forever addons reportedly use the modern `C_AuctionHouse` API, which has Retail-style commodities.
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
  - **Scan format STORY-010 ingests:** `BrownstoneScanDB` with `schema_version` 1 and a list of scans; fields are documented in `addon/README.md`, with a sample at `tests/fixtures/brownstone_scan_sample.lua`. Each scan has a `scan_id`, UTC start and finish, `status` (`completed` or `stopped`), `listing_count` against `reported_count`, client build, region, realm, player faction, auctioneer and zone, and a free-text `label`. Importing must treat `label`, auctioneer and zone as evidence of which house it is, never as a configured `market_id`.
  - **Listing semantics:** Forever's `buyout` is the price of the whole stack (Classic-style), with `quantity` the stack size, and no commodity status is reported. `unit_buyout` is present only when `buyout / quantity` is an exact copper amount, about three in four stacked listings. A missing `buyout` means no buyout, never free. Listings the client hadn't fully loaded have an empty `name` and no `link`, but valid item ID, quantity and buyout. STORY-010 must decide how to price stacks with no exact unit price.
  - **Known costs:** about 240 bytes per listing, so a full scan is large and loads slowly if several accumulate. Region and realm are generic on the beta and do not identify the house.
- **Out of scope:** automated buying, selling or posting, unattended in-game scanning, cloud deployment and AI-generated recommendations without explainable features.

## Rules

### Data integrity
- **DATA-01 Raw preservation:** every download is saved byte-for-byte before validation. Each has a manifest with source, SHA-256, UTC collection time and status, including failures. Raw files are never overwritten.
- **DATA-02 Validation:** required columns, integer copper prices, unique positive item IDs and timestamps that are either all present or all absent. A missing name becomes `Item <ID>`. Zero means unavailable or no listing.
- **DATA-03 Market identity:** a market is one auction house: `game_version + region + scope + realm + server_type + faction`. Item IDs never join across any of these.
  - **Fields:**
    - `scope` is `house` (one auction house) or `region` (a region-wide commodity pool).
    - `realm` names the house where realms exist; `server_type` (normal/pvp/roleplaying/hardcore) names it in realmless Forever. A market uses one or the other, never both.
    - `faction` is alliance, horde, neutral, or blank for cross-faction houses.
  - **`market_id` is derived, never configured** (for example `classic-us-mankrik-alliance`, `forever-us-roleplaying-alliance`), so two sources for one house always agree.
  - **Auction cut:** set per source. Neutral houses default to 15%.
- **DATA-08 Source independence:** a market's identity says *which auction house*. A source's identity (`source_id`, `provider`) says *who observed it*: your addon, TSM or a third-party site. The same market can have several sources. Every manifest and price observation records its source, deduplication is per source, and each source keeps its own data folder. Combining sources follows an explicit, versioned policy, never silent mixing. Until that policy exists (STORY-011), each view reads one selected source.
- **DATA-04 Deduplication:** identical market, scan time and content hash reuse one analytical snapshot. Every raw collection is still archived.
- **DATA-05 Freshness:** age comes from upstream scan time when the source provides it. Otherwise it comes from collection time, explicitly labeled as "price age unknown". Stale means older than `max_age_hours` (default 24) or more than 15 minutes in the future. A source may opt out of upstream time only when the entire column is blank (`allow_missing_updated_at`).

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

### Interface
- **UI-01:** browsing saved data never triggers a download. Only **Refresh from TSM** collects, and only for the selected source.
- **UI-02:** Browse market finds items regardless of price or discount. Categories are not inferred from names or commodity status.
- **UI-03:** the discount screen (Opportunities) explains when a source cannot support it, for example Classic historical values being zero.
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

Demand, sale likelihood, listing depth, deposits, recommended quantities, vendor stock, reputation discounts, recipe quality/rank and reagent alternatives.

## Open decisions

- Catalog source and import path at scale (STORY-004).
- Useful action thresholds beyond profit > 0.
- Classic regional demand integration (STORY-003).
- Which third-party Forever aggregates, if any, offer a usable export or API (STORY-011).
- Historical storage, backup and scheduling.
- Whether to remove the Retail regression sources. SPIKE-008 found Forever listings are per-stack, not Retail-style per-unit commodities, so the Retail commodity feed is not a close test of Forever's model.

None is approved by default.
