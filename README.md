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

Double-click **Open Brownstone App.command** (macOS) or **Open Brownstone App.cmd** (Windows), or run:

```bash
.venv/bin/python launch_nicegui.py
```

Brownstone opens in its own desktop window on a free port at `127.0.0.1`. A second launch
focuses the current window or restarts the launcher's own app if the Python code changed.
If the desktop window cannot open, the launcher explains the browser fallback in one line;
that server stops after five minutes with no connected tabs. Closing the native window stops it.

Choose an experience (WoW Forever first), then a source when several are enabled.
The header opens **Today** (plan and session), **Team** (roster/progression/hiring),
**Market** (items and supply chains), **Stock** (holdings/targets), and **Data** (Import).
Data previews without writing and imports only after explicit review and selection.

For a copied-data browser check:

```bash
.venv/bin/python nicegui_app.py --data-dir /path/to/copied-data --port 8081
```

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

On Windows the file is under the game folder, for example (single quotes keep the backslashes literal in TOML):

```toml
scan_path = 'C:\Program Files (x86)\World of Warcraft\_classic_beta_\WTF\Account\<ACCOUNT>\SavedVariables\BrownstoneScan.lua'
```

After each scan and `/reload`, click **Import addon scan** or run:

```bash
.venv/bin/python -m brownstone --source forever-us-normal-alliance-addon
```

`--input <file>` imports a different file, and `--scan <scan_id>` imports one scan from it. The order matters: scan, `/reload` (the game writes scans to the file only then, or on logout), import, and only then `/bscan clear` and `/reload`. A scan you haven't `/reload`ed is only in game memory, so the addon refuses to clear it, and Brownstone says *Nothing new* if you import before reloading.

## Markets and catalogs

- `config/market.toml` lists sources. Each one is a feed (`source_id`, `provider`, and a URL or, for `provider = "addon"`, a local `scan_path` plus `scan_evidence`) observing one market: game version, region, and realm or Forever server type, plus faction. The file's comments show a Forever example. Freshness and auction cut can be set per source; neutral houses default to 15%. TSM feed URLs follow `https://public-data.tradeskillmaster.com/{game}/{region}/realm/{realm}/items.csv`; slugs are on [TSM Public Pricing Data](https://tradeskillmaster.com/public-data).
- Catalog discovery follows `config/recipe-selections/*.toml`. Pricing requires compatible game and rules versions (CRAFT-01/05).
- Refresh recipes from a profession page saved manually in your browser:

```bash
.venv/bin/python -m brownstone recipes --page /path/to/tailoring.html \
  --selection config/recipe-selections/forever-tailoring.toml \
  --output config/forever-tailoring.toml
```

Review reported changes and update catalog versions under [CRAFT-08](docs/requirements.md#crafting).
TSM refresh uses the collection commands above. There is one app.

## Data on disk

```text
data/bronze/<source>/   exact downloaded or imported bytes (addon scan files gzip-compressed) + manifest JSON (hash, source, times, status)
data/silver/<source>/   validated Parquet per collection (addon: per scan, listings and prices)
data/gold/<source>/     CLI screening output per collection
data/brownstone.duckdb  market_snapshots, addon_scans and scan_listings tables (schema upgrades keep a brownstone.v<N>.backup.duckdb copy)
data/inbox/addon-scans/ addon SavedVariables files copied out of the game, waiting to be imported
```

Data is excluded from Git. Brownstone/data live on the Mac; Windows sends immutable addon
copies through the drop folder (OPS-03). Run one writer, keep data outside live sync, and back
it up separately. See [requirements](docs/requirements.md#operations).
