# Brownstone Markets requirements

Accepted product behavior and decisions. This is the single home for rules; other documents link here instead of restating them. Planned work lives in `backlog.md`, architecture in `design.md`, current state in `status.md`.

## Product direction

- **Purpose:** a local WoW market research tool that traces materials through intermediate crafts to finished goods and explains which crafts are worth investigating.
- **Target game:** WoW Forever. It has no reliable public price feed yet.
- **Development stand-in:** Mankrik Alliance, Classic Era (TSM public realm CSV). Classic is used to build and prove the product, not as the end market. Switching to Forever must be a configuration and catalog change: add a source with the Forever `game_version` and `ruleset`, plus a matching catalog. It must not require code changes.
- **Retail:** not a product requirement (decided 2026-10-04). Retail sources remain configured only as an ingestion regression check, because they exercise regional scope and upstream timestamps that Classic lacks. No feature work targets Retail. They may be removed when they stop earning their keep.
- **Out of scope:** addons, automated buying or selling, cloud deployment, scheduled collection and AI-generated recommendations without explainable features.

## Rules

### Data integrity
- **DATA-01 Raw preservation:** every download is saved byte-for-byte before validation. Each has a manifest with source, SHA-256, UTC collection time and status, including failures. Raw files are never overwritten.
- **DATA-02 Validation:** required columns, integer copper prices, unique positive item IDs and timestamps that are either all present or all absent. A missing name becomes `Item <ID>`. Zero means unavailable or no listing.
- **DATA-03 Market identity:** a market is `market_id + game_version + region + scope + realm`. Item IDs never join across any of these.
- **DATA-04 Deduplication:** identical market, scan time and content hash reuse one analytical snapshot. Every raw collection is still archived.
- **DATA-05 Freshness:** age comes from upstream scan time when the source provides it. Otherwise it comes from collection time, explicitly labeled as "price age unknown". Stale means older than `max_age_hours` (default 24) or more than 15 minutes in the future. A source may opt out of upstream time only when the entire column is blank (`allow_missing_updated_at`).

### Money
- **MONEY-01:** store and calculate integer copper only. 1g = 100s = 10,000c.
- **MONEY-02:** display gold. Tables show decimal gold with four places, so one copper is exact and columns sort numerically. Headline figures and prose use `4g 50s 97c`.

### Crafting
- **CRAFT-01 Versioned catalogs:** each catalog declares `game_version`, `ruleset`, `catalog_version`, status, and provenance URLs for every item and recipe. Classic and Forever catalogs never share rules implicitly.
- **CRAFT-02 Expansion:** intermediates expand without cycles or double counting. Unsupported cases (cycles, fractional units) are rejected, not approximated.
- **CRAFT-03 Routes:** each input uses its cheapest valid route: buy, craft or vendor. Missing or zero prices are never free. Equal costs resolve deterministically.
- **CRAFT-04 Price bases:**
  - **Cautious** is the default for ranking and labels. It buys inputs at the higher, and sells output at the lower, of minimum buyout and market value. When only one value is positive, that value is used.
  - **Listed** uses minimum buyout only.
  - Every board row shows profit under both bases.
- **CRAFT-05 Action Board:** ranks finished outputs of any catalog compatible with the selected market (same game version and ruleset).
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
- **OPS-01:** tests are offline and run in CI on macOS and Windows from the lock file, including the UI test. No market data is stored in Git.

## Not modeled (do not imply otherwise)

Demand, sale likelihood, listing depth, deposits, recommended quantities, vendor stock, reputation discounts, recipe quality/rank and reagent alternatives.

## Open decisions

- Catalog source and import path at scale (STORY-004).
- Useful action thresholds beyond profit > 0.
- Classic regional demand integration (STORY-003).
- Forever price source and launch market.
- Historical storage, backup and scheduling.
- Whether to remove the Retail regression sources.

None is approved by default.
