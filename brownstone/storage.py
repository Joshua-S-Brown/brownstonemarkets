"""DuckDB schema, snapshot loading with deduplication, manifests and scoped price reads."""
import json
import shutil
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb

from . import markets
from .config import ADDON_PROVIDER, MARKET_KEYS, Source
from .freshness import observed_at

SCHEMA_VERSION = 3

# Each migration is frozen once released: a fresh database replays them all, so it ends up
# identical to an upgraded one. Columns stay nullable because v0.1 databases (schema copied
# from Parquet) allowed nulls; normalization rejects nulls where they are not allowed.
_V1_DDL = """CREATE TABLE IF NOT EXISTS market_snapshots (
    item_id BIGINT, item_name VARCHAR,
    market_value BIGINT, min_buyout BIGINT, recent_value BIGINT, historical_value BIGINT,
    updated_at TIMESTAMPTZ, market_id VARCHAR, snapshot_id VARCHAR, collected_at TIMESTAMPTZ,
    game_version VARCHAR, region VARCHAR, scope VARCHAR, realm VARCHAR, source_sha256 VARCHAR)"""


def _migrate_to_1(db):
    db.execute(_V1_DDL)
    # v0.1 tables predate market identity and source hashes.
    for column in ["game_version", "region", "scope", "realm", "source_sha256"]:
        db.execute(f"ALTER TABLE market_snapshots ADD COLUMN IF NOT EXISTS {column} VARCHAR")
    # The only known v0.1 production source was Retail Area 52; other legacy rows stay unclassified.
    db.execute("""UPDATE market_snapshots SET game_version='retail', region='us',
        scope='realm', realm='area-52' WHERE market_id='retail-us-area-52' AND game_version IS NULL""")


def _migrate_to_2(db):
    """Separate market (which auction house) from source (who observed it); add Forever fields.

    Before this, market_id held the source's ID; it becomes the derived market ID, which is the
    same string for every market known at the time. Classic faction moves out of the realm slug.
    """
    for column in ["source_id", "server_type", "faction"]:
        db.execute(f"ALTER TABLE market_snapshots ADD COLUMN IF NOT EXISTS {column} VARCHAR")
    db.execute("UPDATE market_snapshots SET source_id = market_id WHERE source_id IS NULL")
    db.execute("""UPDATE market_snapshots SET
        faction = CASE WHEN game_version = 'classic' AND realm LIKE '%-alliance' THEN 'alliance'
                       WHEN game_version = 'classic' AND realm LIKE '%-horde' THEN 'horde' ELSE '' END,
        realm = CASE WHEN game_version = 'classic' AND realm LIKE '%-alliance' THEN realm[:-10]
                     WHEN game_version = 'classic' AND realm LIKE '%-horde' THEN realm[:-7] ELSE realm END,
        server_type = '',
        scope = CASE WHEN scope = 'realm' THEN 'house' ELSE scope END
        WHERE game_version IS NOT NULL AND faction IS NULL""")
    # Same rule as markets.market_id(); unclassified legacy rows keep their old ID.
    db.execute("""UPDATE market_snapshots SET market_id = concat_ws('-', game_version, region,
        nullif(realm, ''), nullif(server_type, ''), nullif(faction, ''),
        CASE WHEN scope = 'region' THEN 'commodities' END)
        WHERE game_version IS NOT NULL""")


_MARKET_COLUMNS = ("market_id VARCHAR, game_version VARCHAR, region VARCHAR, scope VARCHAR, realm VARCHAR, "
                   "server_type VARCHAR, faction VARCHAR")


def _migrate_to_3(db):
    """Addon scans (STORY-010): one row per scan, and its listings. Item prices go to market_snapshots."""
    db.execute(f"""CREATE TABLE IF NOT EXISTS addon_scans (
        source_id VARCHAR NOT NULL, scan_id VARCHAR NOT NULL, snapshot_id VARCHAR NOT NULL, {_MARKET_COLUMNS},
        status VARCHAR, stop_reason VARCHAR, partial BOOLEAN, priced BOOLEAN,
        started_at TIMESTAMPTZ, finished_at TIMESTAMPTZ, listing_count BIGINT, reported_count BIGINT,
        nonexact_stacks BIGINT, item_count BIGINT, api VARCHAR, client_version VARCHAR, client_build VARCHAR,
        player_faction VARCHAR, auctioneer VARCHAR, zone VARCHAR, subzone VARCHAR, realm_name VARCHAR,
        label VARCHAR, scan_sha256 VARCHAR, source_sha256 VARCHAR, collection_id VARCHAR,
        collected_at TIMESTAMPTZ, PRIMARY KEY (source_id, scan_id))""")
    db.execute(f"""CREATE TABLE IF NOT EXISTS scan_listings (
        source_id VARCHAR NOT NULL, scan_id VARCHAR NOT NULL, listing_index BIGINT NOT NULL,
        snapshot_id VARCHAR, {_MARKET_COLUMNS},
        item_id BIGINT, item_name VARCHAR, quantity BIGINT, buyout BIGINT, unit_buyout BIGINT,
        unit_buyout_ceil BIGINT, min_bid BIGINT, bid BIGINT, complete_info BOOLEAN,
        PRIMARY KEY (source_id, scan_id, listing_index))""")


MIGRATIONS = {1: _migrate_to_1, 2: _migrate_to_2, 3: _migrate_to_3}


def _has_table(db, name: str) -> bool:
    return db.execute("SELECT 1 FROM duckdb_tables() WHERE table_name = ?", [name]).fetchone() is not None


def schema_version(db) -> int:
    """The database's recorded schema version; 0 for a v0.1 database or an empty one."""
    if not _has_table(db, "schema_info"):
        return 0
    row = db.execute("SELECT value FROM schema_info WHERE key='schema_version'").fetchone()
    return int(row[0]) if row else 0


def _refuse_newer(version: int) -> None:
    if version > SCHEMA_VERSION:
        raise RuntimeError(f"Database schema {version} is newer than this code supports ({SCHEMA_VERSION})")


def _require_current(db) -> None:
    if schema_version(db) != SCHEMA_VERSION:
        raise RuntimeError("Database schema is out of date; call upgrade_database first")


def ensure_schema(db):
    """Bring the database to SCHEMA_VERSION, running each pending migration once."""
    version = schema_version(db)
    db.execute("CREATE TABLE IF NOT EXISTS schema_info (key VARCHAR PRIMARY KEY, value VARCHAR NOT NULL)")
    _refuse_newer(version)
    for target in range(version + 1, SCHEMA_VERSION + 1):
        MIGRATIONS[target](db)
        db.execute("INSERT OR REPLACE INTO schema_info VALUES ('schema_version', ?)", [str(target)])


def upgrade_database(data_dir: Path, create: bool = False) -> bool:
    """Bring the database to SCHEMA_VERSION before use. Returns True if anything changed.

    DuckDB cannot reliably add a column and update the table in one transaction, so
    migrations run statement by statement. For safety, an existing database is copied to
    ``brownstone.v<N>.backup.duckdb`` first; every migration step is idempotent, and the
    version is recorded only after a migration completes, so a failed upgrade reruns cleanly.
    """
    path = Path(data_dir) / "brownstone.duckdb"
    if not path.exists() and not create:
        return False
    existed = path.exists()
    with duckdb.connect(str(path)) as db:
        version = schema_version(db)
        has_data = _has_table(db, "market_snapshots")
    if version == SCHEMA_VERSION:
        return False
    _refuse_newer(version)
    if existed and has_data:
        backup = path.with_name(f"brownstone.v{version}.backup.duckdb")
        if not backup.exists():
            shutil.copy2(path, backup)
    with duckdb.connect(str(path)) as db:
        ensure_schema(db)
    return True


def load_snapshot(db, silver: Path, frame, config: Source) -> tuple[str, bool]:
    """Insert one silver snapshot unless this source already holds identical content.

    The database must already be at SCHEMA_VERSION (see ``upgrade_database``).
    """
    _require_current(db)
    existing = db.execute("""SELECT snapshot_id FROM market_snapshots
        WHERE source_id=? AND updated_at IS NOT DISTINCT FROM ? AND source_sha256=? LIMIT 1""",
        [config["source_id"], frame["updated_at"][0], frame["source_sha256"][0]]).fetchone()
    if existing:
        return existing[0], False
    db.execute("INSERT INTO market_snapshots BY NAME SELECT * FROM read_parquet(?)", [str(silver)])
    return frame["snapshot_id"][0], True


def known_scan(db, source_id: str, scan_id: str) -> dict | None:
    """The stored record of a scan from this source, if it was imported before."""
    row = db.execute("""SELECT snapshot_id, scan_sha256, priced, item_count FROM addon_scans
        WHERE source_id=? AND scan_id=?""", [source_id, scan_id]).fetchone()
    if row is None:
        return None
    return dict(zip(("snapshot_id", "scan_sha256", "priced", "item_count"), row, strict=True))


def load_scan(db, scan: Path, listings: Path, prices: Path | None) -> None:
    """Insert one new addon scan from its silver files: the scan row, its listings and, when the scan
    is complete, its item prices. Callers check ``known_scan`` first; a repeat insert fails on the key."""
    _require_current(db)
    db.execute("INSERT INTO addon_scans BY NAME SELECT * FROM read_parquet(?)", [str(scan)])
    db.execute("INSERT INTO scan_listings BY NAME SELECT * FROM read_parquet(?)", [str(listings)])
    if prices is not None:
        db.execute("INSERT INTO market_snapshots BY NAME SELECT * FROM read_parquet(?)", [str(prices)])


def completed_snapshots(config: Source) -> list[dict]:
    """A source's completed manifests, newest observation first, in the current shape.

    Ordered by upstream scan time when known, else collection time, so importing an older scan
    after a newer one never replaces newer prices.

    Manifests written before the market/source split are upgraded in memory; files are never edited.
    """
    records = []
    folder = Path(config["data_dir"]) / "bronze" / config["source_id"]
    for path in folder.glob("*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("status") == "complete":
                records.append(markets.upgrade_legacy(record))
        except (OSError, ValueError):
            continue
    return sorted(records, key=lambda r: (observed_at(r), datetime.fromisoformat(r["collected_at"])), reverse=True)


def latest_snapshot(config: Source) -> tuple[dict | None, str | None, int]:
    """Newest completed manifest and the analytical snapshot ID its prices live under."""
    manifests = completed_snapshots(config)
    if not manifests:
        return None, None, 0
    latest = manifests[0]
    return latest, latest.get("analytical_snapshot_id", latest["snapshot_id"]), len(manifests)


def scope_predicate(config: Mapping[str, Any]) -> tuple[str, list[Any]]:
    """SQL predicate and parameters for one source and the entire market identity."""
    keys = ("source_id", *MARKET_KEYS)
    return " AND ".join(f"{key}=?" for key in keys), [config[key] for key in keys]


def price_observations(db, config: Mapping[str, Any], snapshot_id: str, item_ids) -> dict[int, dict]:
    """Read unit copper prices with the source and entire market identity, never item ID alone."""
    if not item_ids:
        return {}
    predicates, scope = scope_predicate(config)
    placeholders = ", ".join("?" for _ in item_ids)
    rows = db.execute(
        f"SELECT item_id, min_buyout, market_value FROM market_snapshots WHERE snapshot_id=? "
        f"AND {predicates} AND item_id IN ({placeholders})",
        [snapshot_id, *scope, *item_ids],
    ).fetchall()
    return {item_id: {"min_buyout": listed, "market_value": market}
            for item_id, listed, market in rows}


def listing_depth(db, config: Mapping[str, Any], snapshot_id: str,
                  item_ids: list[int]) -> dict[int, dict[str, int]] | None:
    """Listing counts and units in the exact priced scan, including listings without a buyout.

    None means depth is unavailable (TSM, or no matching complete priced addon scan).
    In a matching scan, an absent item has zero listings and units: it was not listed.
    No counts from another source, market or snapshot can fill a missing item.
    """
    if config["provider"] != ADDON_PROVIDER:
        return None
    predicates, scope = scope_predicate(config)
    parameters = [snapshot_id, *scope]
    scan = db.execute(
        f"SELECT scan_id FROM addon_scans WHERE snapshot_id=? AND {predicates} "
        "AND status='completed' AND NOT partial AND priced", parameters,
    ).fetchone()
    if scan is None:
        return None
    if not item_ids:
        return {}
    placeholders = ", ".join("?" for _ in item_ids)
    rows = db.execute(
        f"SELECT item_id, count(*), sum(quantity) FROM scan_listings WHERE snapshot_id=? "
        f"AND {predicates} AND scan_id=? AND item_id IN ({placeholders}) GROUP BY item_id",
        [*parameters, scan[0], *item_ids],
    ).fetchall()
    depth = {item_id: {"listings": 0, "units": 0} for item_id in item_ids}
    depth.update({item_id: {"listings": listings, "units": units} for item_id, listings, units in rows})
    return depth
