# Brownstone Markets

A local WoW market research desk. It traces materials through intermediate crafts to finished goods and shows which crafts are worth investigating, with the evidence behind each number.

- **Target game:** WoW Forever, once a reliable price feed exists.
- **Development data:** Mankrik Alliance, Classic Era (TSM public CSV).
- **Pipeline:** TSM CSV → exact raw archive → validated Parquet → DuckDB → crafting Action Board in a local browser app.

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

Before committing, also run `.venv/bin/python -m ruff check .` and `.venv/bin/python -m mypy`. CI runs both.

On Windows, use `py -m venv .venv` and `.venv\Scripts\python.exe` in place of `.venv/bin/python`.

## Run

Double-click **Start Brownstone.command** (macOS) or **Start Brownstone.cmd** (Windows), or run:

```bash
.venv/bin/python launch.py
```

The launcher opens http://127.0.0.1:8501. It reuses a running server only if the code hasn't changed since that server started; otherwise it restarts it.

In the app:

1. Pick a **Data source** in the sidebar.
2. Click **Refresh from TSM** to collect prices. Nothing downloads otherwise.
3. Use the views:
   - **Crafting:** the Action Board and recipe detail.
   - **Browse market:** every observed item.
   - **Opportunities:** a discount screen. It needs historical prices, so it doesn't work on Classic.

All money is shown in gold: decimal in tables, `4g 50s 97c` in summaries.

Command-line collection, which also accepts a saved CSV:

```bash
.venv/bin/python -m brownstone --market classic-us-mankrik-alliance
.venv/bin/python -m brownstone --input path/to/items.csv
```

## Markets and catalogs

- `config/market.toml` lists sources: market identity, feed URL, freshness and auction cut. TSM feed URLs follow `https://public-data.tradeskillmaster.com/{game}/{region}/realm/{realm}/items.csv`; slugs are on [TSM Public Pricing Data](https://tradeskillmaster.com/public-data).
- `config/*-tailoring.toml` are versioned recipe catalogs.
- The Action Board appears when a catalog's `game_version` and `ruleset` match the selected source.

## Data on disk

```text
data/bronze/<market>/   exact downloaded bytes + manifest JSON (hash, source, times, status)
data/silver/<market>/   validated Parquet per collection
data/gold/<market>/     discount-screen output per collection
data/brownstone.duckdb  market_snapshots table
```

Data is excluded from Git, so back up `data/` separately. Run one writer at a time. Validation and freshness rules are in [requirements](docs/requirements.md).
