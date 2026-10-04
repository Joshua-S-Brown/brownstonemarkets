# Brownstone design and delivery roadmap

## Objective

Follow materials from their market prices through intermediate crafts to saleable products. Explain purchasing and crafting opportunities using observed prices, historical behavior and liquidity. Retail is an acceptable development market; Classic remains a target. Do not assume prices, recipe rules or item identifiers are interchangeable across game versions.

## Immediate findings

The current Area 52 source is a Retail non-commodity realm feed. Retail commodities have a separate regional feed. The missing materials are a coverage gap, not an intentional category filter. The first score is a discount screen, not a profit or liquidity model. Extreme discounts can favor illiquid finished goods. Categories cannot be inferred reliably from names or from commodity status: a commodity can be a finished consumable, and a material can also be a crafted intermediate.

## Delivery order

1. Establish GitHub source control and a baseline commit. Keep data, local environments, logs and credentials out of Git. Add CI using the offline tests; do not download live markets inside CI tests.
2. Complete market coverage: realm items plus regional commodities. Add explicit game version, region, scope, realm and source timestamps. Compare schemas from live feeds before accepting them. Never join markets by item ID alone.
3. Add a sourced item catalog: version, item ID, name, class/subclass and trade flags. Allow unknown categories. Keep metadata separate from changing price observations. Distinguish raw materials, intermediates and finished goods through recipe relationships and curated roles, with provenance.
4. Demonstrate one profession and a small set of actual recipes. Store recipe inputs and outputs with quantities, source/version and assumptions. Answer what uses a material, what a product requires, and buy-versus-craft costs. Handle missing prices and recipe cycles explicitly.
5. Improve analysis: regional sale statistics where available, history-based features, liquidity and confidence alongside price spreads. Keep feature calculation separate from ranking policy. Backtest only after sufficient distinct upstream scans exist.
6. Automate collection and backup after replay/recovery and scan deduplication work. Choose snapshot storage separately from the code repository. Scheduling must operate independently of the browser UI.

## Core data contracts

| Entity | Key / purpose |
| --- | --- |
| Item | game version + item ID; descriptive metadata and provenance |
| Market | game version + region + scope + optional realm; commodity scope is regional in Retail |
| Snapshot | source + upstream scan time + content hash; collected_at tracks retrieval separately |
| Price observation | snapshot + market + versioned item identity; integer copper and availability |
| Recipe | game version + recipe ID + ruleset/version; profession, source and effective version |
| Recipe input | recipe + input item + role/slot; required quantity and permitted alternatives |
| Recipe output | recipe + output item; quantity or yield assumptions |
| Analytical feature | observation/window + feature definition/version; liquidity, discount, volatility |

Use ordinary relational tables in DuckDB and Parquet first. Recipe input/output tables represent a graph without a graph database. Recipe availability, rank/quality, optional reagents and variable yields require explicit handling when the chosen game version needs them; reject unsupported cases rather than implying precision. Intermediate crafting costs must preserve units and avoid counting the same material twice.

## Code boundaries

The current single pipeline module is a v0.1 proof. Extract focused modules as the next feature touches them:

```text
brownstone/
  sources/       TSM downloads and later catalog/recipe adapters
  transforms/    parsing, normalization and quality rules
  storage/       snapshots, manifests, database loads and replay
  catalog/       item metadata and category/role mapping
  crafting/      recipe traversal, quantities and cost calculations
  analysis/      reusable features and ranking policies
  pipeline.py    orchestration only
app.py           display and user-triggered actions
```

Dependencies flow from interface to orchestration to domain functions and storage/adapters. Domain calculations do not import Streamlit or fetch URLs. Avoid shared mutable configuration and premature plugin frameworks. A new feature gets a narrow module, a documented input/output contract and tests for important behavior.

## Next milestone acceptance

- Both Retail feeds appear with their correct market scope and independently reported freshness.
- A material can be searched and its market observed, even if it does not meet the discount threshold.
- Materials and finished commodities are not mislabeled merely because they share a feed.
- Existing price history remains queryable; schema changes use an explicit migration/rebuild path.
- Repeating a scan does not inflate historical feature sample counts.
- The UI can browse market inventory separately from ranked opportunities.
- A few real, sourced recipes show end-to-end quantities and missing-data behavior before broader imports.

## Open decisions

Repository confirmed: Joshua-S-Brown/brownstonemarkets; user handles commits and pushes. Retail development data approved. Still open: first profession/expansion, catalog/recipe source and access, ongoing snapshot storage. Implemented coverage status is in status.md; recipe acceptance belongs to the next milestone.
