# Brownstone Markets requirements

Authoritative accepted product behavior across sessions. Use `backlog.md` for planned stories, `design.md` for architecture and `status.md` for implemented state. Explicit new user instructions take precedence; record durable decisions here.

## Accepted decisions

Brownstone is a local WoW market research tool that traces materials through intermediate crafts to finished products. Mankrik Alliance Classic Era is the active development market. Existing Retail support remains intact but is not a near-term product focus. WoW Forever remains a future target when reliable pricing becomes available. Keep version-specific item and recipe rules separate. The user wants intentional design, reusable Python analysis and a browser interface.

The first crafting slice is **Tailoring**, beginning with **Runecloth Bag** and its Bolt of Runecloth intermediate. Forever is a separate, evolving ruleset; recipe records require build/ruleset and provenance rather than inheriting Classic Era data silently. Demand is a hypothesis to test after launch, not an assumed input to profitability. Mankrik Alliance Classic Era is the selected development market for the end-to-end crafting workflow; its catalog and observations remain explicitly Classic rather than being relabeled as Forever.

Project: C:\Users\brown\Documents\Codex\Projects\brownstone-markets.
Repository: https://github.com/Joshua-S-Brown/brownstonemarkets.
The user handles commits/pushes in VS Code; leave development changes reviewable unless instructed otherwise. Data, local environments and credentials stay outside Git.

## Current requirements and acceptance

| ID | Requirement | Acceptance |
| --- | --- | --- |
| DATA-01 | Preserve raw bytes and provenance | Unique bronze CSV and JSON with hash, source, UTC times and failure status |
| DATA-02 | Normalize both Retail feeds | Required columns validated, copper integers, missing-name labels, zero means unavailable |
| DATA-03 | Preserve market identity | Explicit game_version, region, scope, realm; commodities are US regional, not Area 52 prices |
| DATA-04 | Independent freshness | Selected feed reports its scan age; refresh affects that source only |
| DATA-05 | Distinct analytical observations | Same market/time/hash reuses analytical snapshot; raw collections remain archived |
| DATA-06 | Preserve v0.1 history | Additive DuckDB migration; known Area 52 identity backfilled; old Parquet untouched |
| DATA-07 | Honest source-specific freshness | Mankrik's wholly absent upstream time stays null and uses labeled collection freshness; unexpected or mixed nulls fail |
| CRAFT-01 | Versioned recipe proof | Classic and Forever Runecloth Bag catalogs retain separate ruleset and provenance identities |
| CRAFT-02 | Expand intermediates | Runecloth Bag expands through Bolt of Runecloth without cycles or double counting |
| CRAFT-03 | Conservative recipe costs | Choose cheapest valid buy/craft/vendor route; missing prices invalidate estimates |
| CRAFT-05 | Classic Tailoring Action Board v0.1 | Rank the sourced representative Woolen, Mageweave and Runecloth bag subset for Mankrik Alliance Classic Era; preserve Retail support |
| CRAFT-06 | Explain costs and evidence | Direct quantities, cheapest valid buy/craft/vendor unit and total costs, all-craft expansion, selected-route shopping list, break-even unit output price, catalog and snapshot provenance |
| CRAFT-07 | Conservative ranking and freshness | Profit or margin descending, incomplete last, deterministic recipe-ID ties; potential craft / negative margin / missing prices / stale data; collection fallback explicitly labeled |
| UI-01 | Browse separately from scoring | Name/ID searches find below-threshold and unavailable-price items |
| UI-02 | Explain screening assumptions | Conservative reference, positive prices, configurable cut; no profit guarantee |
| UI-03 | Local launcher | Start or reuse localhost server with readable startup failures |
| UI-04 | Inspect recipes without compatible prices | Crafting view shows direct and expanded materials, version/ruleset/status and provenance; profit remains unavailable on a version mismatch |
| OPS-01 | Repeatable validation | Offline tests, GitHub test workflow, no market archives in Git |

The commodity browser is not yet a categorized materials browser. Commodities include ingredients, crafted materials and finished consumables. Do not infer categories from feed or names. Browsing saved data does not trigger collection.

When a specifically configured source such as Mankrik Classic supplies an entirely blank upstream timestamp column, preserve `updated_at` as unknown and label freshness as retrieval-based. Mixed or unexpectedly missing timestamps remain invalid; never present collection time as an upstream scan time.

## Planned requirements

- CAT-01: Sourced versioned item catalog, class/subclass, provenance and explicit unknowns.
- CAT-02: Ingredient/intermediate/output roles may overlap; categories need metadata or recipe evidence.
- CRAFT-04: Quality, rank and reagent alternatives require explicit rules for the chosen version. Start with simple supported recipes.
- ANALYSIS-01: Liquidity from regional statistics where available, separated from realm prices. No invented sale rates.
- ANALYSIS-02: History-based movement, discount frequency, volatility and recovery using distinct scans with explicit minimum sample counts.
- ANALYSIS-03: Explain scores through features and policy versions; backtests must avoid future-data leakage.
- OPS-02: Collection independent of UI after recovery/storage decisions. Roughly match upstream refresh cadence.
- OPS-03: Backups/sync outside Git with retention and recovery documented. Personal transactions remain a separate future dataset.

## Action Board policy v0.1

The board is restricted to Classic Era, US, realm scope, Mankrik Alliance. Item IDs never join across versions or scopes. The catalog is a hand-authored representative subset, version 0.1, with recipe/item provenance and verification date; it is not the complete profession. Classic Bolt of Runecloth uses five Runecloth (25 per bag); the separate Forever proof retains its own rules.

Economics use one saved analytical snapshot of unit minimum buyouts and the configured auction cut (default 5%). Net revenue rounds down to copper, break-even output unit price rounds up, and margin is estimated profit divided by net revenue. Cost covers one recipe execution; output quantity scales revenue. Positive complete fresh profit is labeled potential craft; zero or negative profit uses negative margin. Missing prices take precedence over stale data. Estimates older than the configured 24-hour default or more than 15 minutes future-dated cannot be labeled potential craft. Unknown upstream time uses explicitly labeled collection age and does not establish upstream observation age.

Rank by profit descending by default or margin descending, then the other metric, then recipe ID; incomplete results sort last. Cheapest valid positive buy/craft/vendor routes win (equal-cost choices use a deterministic method ordering). Missing/zero prices never become free inputs. Vendor prices are undiscounted single-unit catalog assumptions; reputation discounts and stock availability are not modeled. All-craft expansion and the shopping list for chosen routes are displayed separately so purchased bolts are not double-counted. Sale likelihood, demand, listing depth, deposits and recommended quantities are not modeled.

## Scope limits and next slice

This project does not implement addons, automatic trading, cloud deployment or scheduling. The **Classic Tailoring Action Board v0.1** (STORY-001 and STORY-002) is complete. Next candidates are separate Classic regional demand context, normalized recipe import and catalog expansion in backlog order. Do not claim sale likelihood or recommended quantity until compatible demand data is modeled.

Open decisions: scalable catalog source/import, useful action thresholds, Classic regional demand integration, Forever price source and launch scope, historical storage and scheduling. None is silently approved.
