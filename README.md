# Brownstone Markets — Classic crafting research

A small local proof: **TSM public CSV → untouched bronze snapshot → validated silver Parquet → DuckDB → ranked gold CSV/Parquet**.

The active development market is **Mankrik Alliance — Classic Era**. Retail Area 52 and US regional commodity feeds remain supported regression sources, but near-term product work is focused on Classic crafting until reliable WoW Forever pricing exists. Select a source in the sidebar, then use **Browse market**, **Opportunities** or **Crafting**. Refresh affects only the selected source.

The first crafting proof targets **Tailoring**, beginning with Runecloth Bag. Separate Classic Era and WoW Forever catalogs record their ruleset, item and recipe IDs, quantities and provenance. `brownstone/crafting.py` expands Bolt of Runecloth, compares valid buy-versus-craft paths, applies the Rune Thread vendor fallback and rejects missing prices or recipe cycles. Choose **Mankrik Alliance — Classic Era** and **Crafting** in the sidebar to inspect the recipe and, after collecting a snapshot, its live cost estimate. The interface refuses to join catalogs and markets from different game versions.

Track active and planned work in `docs/backlog.md`. Use `docs/requirements.md` for accepted product behavior, `docs/design.md` for architecture and `docs/status.md` for implemented state and handoff. GitHub origin is https://github.com/Joshua-S-Brown/brownstonemarkets.

## Browser interface

The permanent project is now at `C:\Users\brown\Documents\Codex\Projects\brownstone-markets`. Double-click **Start Brownstone.cmd** to open the local interface, or run `.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false` from the project folder. Streamlit is installed in this delivery; for a fresh setup install `.[dev,dashboard]`.

The browser shows the latest completed snapshot, scan age, sortable opportunities, a name/ID search, discount filters and CSV download. **Refresh from TSM** collects and archives a new snapshot. Opening the page or changing filters does not trigger ingestion. The local server must remain running; this is not yet automatic collection. The old copy remains in the original chat output folder because Windows reported that folder was in use. Continue work in this permanent copy.

## Setup

### Clone and run on a Mac

Install Python 3.11+ and Git, then run in Terminal:

```bash
git clone https://github.com/Joshua-S-Brown/brownstonemarkets.git
cd brownstonemarkets
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev,dashboard]'
.venv/bin/python -m pytest -p no:cacheprovider
.venv/bin/python launch.py
```

After setup, you can also double-click `Start Brownstone.command`. The launch script works on both Windows and macOS. Data and Python environments are deliberately excluded from Git: the Mac starts with no saved snapshots. Choose a market in the browser and click **Refresh from TSM** to collect data locally. Python 3.12 is the version tested for this project.

Install Python 3.11+ and Git. In PowerShell, from this project folder:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m brownstone
```

On macOS/Linux use `python3 -m venv .venv`, then `.venv/bin/python` in place of the Windows executable. Activation is optional. This delivery already contains a working local `.venv`; recreate it if you move the folder to another machine. Dependencies are declared in `pyproject.toml`; installed verification versions are recorded in `requirements.lock.txt`. For repeatable setup, install that file before installing the project with `--no-deps`.

## Pick a market

Edit `config/market.toml` to add or change a source. The default is **Mankrik Alliance — Classic Era**. TSM's official URL pattern is:

```text
https://public-data.tradeskillmaster.com/{gameType}/{regionSlug}/realm/{realmSlug}/items.csv
```

Find supported game/region/realm slugs on [TSM Public Pricing Data](https://tradeskillmaster.com/public-data). CSV access requires no key. Retail commodities use a separate regional file. Classic Era uses faction-specific realm feeds; Mankrik Alliance is configured as the Alliance development market. No regional sale-rate dataset is joined yet.

Run a saved TSM CSV without a download:

```powershell
.\.venv\Scripts\python.exe -m brownstone --input path\to\items.csv
```

The same schema and freshness rules apply to local files. `max_age_hours` defaults to 24; increase it deliberately for replaying old data. Configuration data paths resolve relative to the project containing `config/`, independent of the launch directory.

## Files and schema

```text
brownstone/          pipeline and command-line entry point
config/market.toml   source, market, freshness and ranking settings
tests/              schema, quality and end-to-end tests
data/bronze/        exact downloaded bytes + SHA-256/provenance/status JSON
data/silver/        one validated, normalized Parquet per snapshot
data/gold/          one ranked CSV and Parquet per snapshot
data/brownstone.duckdb   persistent market_snapshots table
```

Each run uses a unique UTC collection ID. Repeated identical market/scan/hash observations reuse their earlier analytical snapshot ID; each raw collection is still preserved. Repeated pulls retain separate observations even if TSM hasn't changed its file; don't treat them as distinct upstream scans in later historical analysis. Raw bytes are saved before normalization, including failed validation, and never overwritten. Data and the virtual environment are excluded from Git. Back up `data/` separately.

Required source columns: `itemId,name,marketValue,minBuyout,recent,historical,updatedAt`. Extra columns are accepted but the untouched source retains them. Silver uses `item_id,item_name,market_value,min_buyout,recent_value,historical_value,updated_at,market_id,snapshot_id,collected_at`. Prices remain integer **copper** (10,000 copper = 1 gold). `updated_at` is the upstream scan time; `collected_at` is our UTC retrieval time. The configured Mankrik Classic feed currently supplies a blank `updatedAt` column, so its wholly absent upstream time is preserved as null and freshness is explicitly retrieval-based. Other sources still require upstream time. Missing names receive an `Item <ID>` label and are counted in the manifest. Other required nulls, duplicate/nonpositive item IDs, negative/noninteger prices, malformed/mixed timestamps, empty files, stale scans and scans over 15 minutes in the future fail validation. Zero prices are preserved as unavailable/no listing and excluded from ranking. A failed manifest records the error; inspect it before retrying. Network failures before a response create no snapshot.

## First opportunity ranking

For rows with all four prices positive:

- Reference price = minimum of market value, recent value and historical value.
- Discount = `1 - min_buyout / reference_price`.
- Net spread = `reference_price × (1 - auction_cut) - min_buyout`.
- Keep discounts ≥20% with positive net spread; sort by discount, then spread, then item ID; output the top 20.

The assumed auction cut defaults to 5% and is configurable for the target market. Gold output includes names, item IDs, upstream timestamp, copper values and readable gold amounts. These are screening candidates based on aggregate pricing: no listing quantity, liquidity, sale rate, deposit cost, actual purchase availability or realized profit is inferred. An empty ranking is a valid result. Classic feeds currently report zero historical values, so this older discount screen may legitimately be empty; crafting economics use compatible positive minimum buyouts instead. No addon, scheduler or cloud deployment is included.

## Query DuckDB

From the project directory, start the virtual environment's Python and run:

```python
import duckdb
db = duckdb.connect("data/brownstone.duckdb", read_only=True)
print(db.sql("""
    SELECT market_id, snapshot_id, count(*) AS items, max(updated_at) AS upstream_scan
    FROM market_snapshots GROUP BY ALL ORDER BY snapshot_id DESC
""").fetchall())
db.close()
```

Keep one writer running at a time. Bronze/silver files are the recovery source if a run fails after loading DuckDB; v0.1 does not automatically reconcile partially completed runs. Local collection requires an awake, connected computer. Scheduling and remote snapshot storage can follow after selecting the intended market.

## Git

The repository is on branch `main` with GitHub origin `Joshua-S-Brown/brownstonemarkets`. Local data, environments and credentials remain excluded. Review each milestone before committing and push through the user's normal VS Code workflow unless explicitly requested otherwise.
