# Brownstone Markets

A local WoW market research desk. It traces materials through intermediate crafts to finished goods and shows which crafts are worth investigating, with the evidence behind each number.

- **Target game:** WoW Forever, priced from our own read-only scanning addon (`addon/BrownstoneScan/`).
- **Development data:** Mankrik Alliance, Classic Era (TSM public CSV).
- **Pipeline:** TSM CSV or addon scan file → exact raw archive → validated Parquet → DuckDB → crafting Action Board in a local browser app.

Project documents: [requirements](docs/requirements.md) · [design](docs/design.md) · [backlog](docs/backlog.md) · [status](docs/status.md).

## Setup (macOS)

Requires Python 3.11+ (3.12 is tested) and Git.

```bash
git clone https://github.com/Joshua-S-Brown/brownstonemarkets.git
cd brownstonemarkets
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m pytest -p no:cacheprovider
```

Before committing, also run `.venv/bin/python -m ruff check .`, `.venv/bin/python -m mypy` and `.venv/bin/python -m pytest -p no:cacheprovider --cov` (coverage report; fails below the floor in `pyproject.toml`). CI runs all three.

On Windows, use `py -m venv .venv` and `.venv\Scripts\python.exe` in place of `.venv/bin/python`.

## Run

Double-click **Start Brownstone.command** (macOS) or **Start Brownstone.cmd** (Windows), or run:

```bash
.venv/bin/python launch.py
```

The launcher opens http://127.0.0.1:8501. It reuses a running server only if the code hasn't changed since that server started; otherwise it restarts it.

In the app:

1. Pick a **Data source** in the sidebar.
2. Click **Refresh from TSM** to collect prices, or **Import addon scan** for an addon source. Nothing downloads or imports otherwise.
3. Use the views:
   - **Crafting:** the Action Board and recipe detail.
   - **Browse market:** every observed item.
   - **Opportunities:** a discount screen. It needs historical prices, so it doesn't work on Classic.

All money is shown in gold: decimal in tables, `4g 50s 97c` in summaries.

Command-line collection, which also accepts a saved CSV:

```bash
.venv/bin/python -m brownstone --source classic-us-mankrik-alliance
.venv/bin/python -m brownstone --input path/to/items.csv
```

Addon scans: create `config/market.local.toml` (ignored by Git, so your account folder name stays private) that enables the source and points it at the game's file:

```toml
[sources.forever-us-normal-alliance-addon]
enabled = true
scan_path = "/Applications/World of Warcraft/_classic_beta_/WTF/Account/<ACCOUNT>/SavedVariables/BrownstoneScan.lua"
```

After each scan and `/reload`, click **Import addon scan** or run:

```bash
.venv/bin/python -m brownstone --source forever-us-normal-alliance-addon
```

`--input <file>` imports a different file, and `--scan <scan_id>` imports one scan from it.

## Markets and catalogs

- `config/market.toml` lists sources. Each one is a feed (`source_id`, `provider`, and a URL or, for `provider = "addon"`, a local `scan_path` plus `scan_evidence`) observing one market: game version, region, and realm or Forever server type, plus faction. The file's comments show a Forever example. Freshness and auction cut can be set per source; neutral houses default to 15%. TSM feed URLs follow `https://public-data.tradeskillmaster.com/{game}/{region}/realm/{realm}/items.csv`; slugs are on [TSM Public Pricing Data](https://tradeskillmaster.com/public-data).
- `config/*-tailoring.toml` are versioned recipe catalogs.
- The Action Board appears when a catalog's `game_version` and `rules_version` match the selected source.

## Data on disk

```text
data/bronze/<source>/   exact downloaded or imported bytes + manifest JSON (hash, source, times, status)
data/silver/<source>/   validated Parquet per collection (addon: per scan, listings and prices)
data/gold/<source>/     discount-screen output per collection
data/brownstone.duckdb  market_snapshots, addon_scans and scan_listings tables (schema upgrades keep a brownstone.v<N>.backup.duckdb copy)
data/inbox/addon-scans/ addon SavedVariables files copied out of the game, waiting to be imported
```

Data is excluded from Git, so back up `data/` separately. Run one writer at a time. Validation and freshness rules are in [requirements](docs/requirements.md).
