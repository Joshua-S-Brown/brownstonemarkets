# Brownstone Markets requirements

Authoritative scope across sessions. Read with design.md and status.md. Explicit new user instructions take precedence; record changes here.

## Accepted decisions

Brownstone is a local WoW market research tool that should eventually trace materials through intermediate crafts to finished products. Retail is approved for development; Classic/Forever remains a target when reliable supported data exists. Keep version-specific item and recipe rules separate. The user wants intentional design, reusable Python analysis and a browser interface.

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
| UI-01 | Browse separately from scoring | Name/ID searches find below-threshold and unavailable-price items |
| UI-02 | Explain screening assumptions | Conservative reference, positive prices, configurable cut; no profit guarantee |
| UI-03 | Local launcher | Start or reuse localhost server with readable startup failures |
| OPS-01 | Repeatable validation | Offline tests, GitHub test workflow, no market archives in Git |

The commodity browser is not yet a categorized materials browser. Commodities include ingredients, crafted materials and finished consumables. Do not infer categories from feed or names. Browsing saved data does not trigger collection.

## Planned requirements

- CAT-01: Sourced versioned item catalog, class/subclass, provenance and explicit unknowns.
- CAT-02: Ingredient/intermediate/output roles may overlap; categories need metadata or recipe evidence.
- CRAFT-01: Versioned recipes with inputs, outputs, quantities, profession, source and ruleset.
- CRAFT-02: Trace what uses an item and what an output requires. Expand intermediate crafts without cycles or double counting.
- CRAFT-03: Buy-versus-craft costs with yield/fee assumptions; missing/stale costs invalidate or qualify estimates rather than becoming zero.
- CRAFT-04: Quality, rank and reagent alternatives require explicit rules for the chosen version. Start with simple supported recipes.
- ANALYSIS-01: Liquidity from regional statistics where available, separated from realm prices. No invented sale rates.
- ANALYSIS-02: History-based movement, discount frequency, volatility and recovery using distinct scans with explicit minimum sample counts.
- ANALYSIS-03: Explain scores through features and policy versions; backtests must avoid future-data leakage.
- OPS-02: Collection independent of UI after recovery/storage decisions. Roughly match upstream refresh cadence.
- OPS-03: Backups/sync outside Git with retention and recovery documented. Personal transactions remain a separate future dataset.

## Scope limits and next slice

This milestone does not implement crafting, categories, addons, AI scoring, automatic trading, cloud deployment or scheduling. Next, choose one profession/expansion and reliable catalog/recipe source, then prove a few actual recipes end to end: material search → price/history → uses → crafting quantities/cost. Validate missing-data behavior before generalizing.

Open decisions: first profession/expansion, catalog/recipe source/access, variant rules, target Classic market, historical storage and scheduling. None is silently approved.
