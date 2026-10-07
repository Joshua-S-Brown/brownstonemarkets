"""DuckDB schema, snapshot loading with deduplication, manifests and scoped price reads."""
import json
import shutil
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb

from . import markets, metrics
from .config import ADDON_PROVIDER, MARKET_KEYS, Source
from .freshness import observed_at
from .item_names import remember_local_catalog_names, remember_observed_names

SCHEMA_VERSION = 8

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


# Frozen official launch boundary: docs/requirements.md, Product direction / Official dates.
_V4_FOREVER_LAUNCH = "2026-11-04T00:00:00+00:00"


def _migrate_to_4(db):
    """Separate beta/live economies; listings inherit the stored parent scan's collection time."""
    for table in ("market_snapshots", "addon_scans", "scan_listings"):
        db.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS environment VARCHAR")
        collected = ("(SELECT s.collected_at FROM addon_scans s "
                     "WHERE s.source_id=scan_listings.source_id AND s.scan_id=scan_listings.scan_id)"
                     if table == "scan_listings" else "collected_at")
        db.execute(f"""UPDATE {table} SET environment =
            CASE WHEN game_version='forever' AND {collected} < ?::TIMESTAMPTZ
                 THEN 'beta' ELSE 'live' END WHERE environment IS NULL""", [_V4_FOREVER_LAUNCH])
        # Derive instead of appending blindly: a crash after this statement cannot double the suffix.
        db.execute(f"""UPDATE {table} SET market_id = concat_ws('-', game_version, region,
            nullif(realm, ''), nullif(server_type, ''), nullif(faction, ''),
            CASE WHEN scope='region' THEN 'commodities' END, 'beta')
            WHERE environment='beta'""")


# NULL, blank and any generated placeholder are absent, even when the placeholder's ID is wrong.
_V5_DDL = ("""CREATE TABLE IF NOT EXISTS item_names (
    game_version VARCHAR NOT NULL, item_id BIGINT NOT NULL, item_name VARCHAR NOT NULL,
    origin_rank INTEGER NOT NULL, observed_at TIMESTAMPTZ NOT NULL, evidence VARCHAR NOT NULL,
    PRIMARY KEY (game_version, item_id))""",
           """CREATE OR REPLACE MACRO loaded_item_name(name) AS
    CASE WHEN trim(name) != '' AND NOT regexp_full_match(trim(name), 'Item [0-9]+') THEN trim(name) END""",
           *(f"""CREATE OR REPLACE VIEW named_{table} AS
    SELECT p.* REPLACE (coalesce(loaded_item_name(p.item_name), n.item_name,
        'Item ' || p.item_id::VARCHAR) AS item_name)
    FROM {table} p LEFT JOIN item_names n USING (game_version, item_id)"""
             for table in ("market_snapshots", "scan_listings")))
# Backfill every stored price and listing; listings take their parent scan's time, matched on every
# schema-5 market key. Same winner policy as item_names._remember, frozen here.
_V5_BACKFILL = """INSERT INTO item_names
    SELECT game_version, item_id, loaded_item_name(item_name), 1, observed_at, evidence FROM (
        SELECT *, row_number() OVER (PARTITION BY game_version, item_id
            ORDER BY observed_at DESC, loaded_item_name(item_name), evidence) AS choice
        FROM (
            SELECT game_version, item_id, item_name,
                coalesce(updated_at, collected_at, TIMESTAMPTZ '1970-01-01') AS observed_at,
                concat_ws(':', source_id, snapshot_id, 'price') AS evidence
            FROM market_snapshots
            UNION ALL
            SELECT l.game_version, l.item_id, l.item_name,
                coalesce(s.finished_at, s.collected_at, TIMESTAMPTZ '1970-01-01'),
                concat_ws(':', l.source_id, l.scan_id, 'listing', l.listing_index)
            FROM scan_listings l LEFT JOIN addon_scans s ON s.source_id=l.source_id AND s.scan_id=l.scan_id
                AND s.market_id IS NOT DISTINCT FROM l.market_id
                AND s.game_version IS NOT DISTINCT FROM l.game_version AND s.region IS NOT DISTINCT FROM l.region
                AND s.scope IS NOT DISTINCT FROM l.scope AND s.realm IS NOT DISTINCT FROM l.realm
                AND s.server_type IS NOT DISTINCT FROM l.server_type
                AND s.faction IS NOT DISTINCT FROM l.faction AND s.environment IS NOT DISTINCT FROM l.environment
        ) candidates
        WHERE game_version IS NOT NULL AND item_id > 0 AND loaded_item_name(item_name) IS NOT NULL
    ) WHERE choice=1
    ON CONFLICT (game_version, item_id) DO NOTHING"""


def _migrate_to_5(db):
    """Derived names and named read views; observations remain byte-for-byte unchanged."""
    for statement in _V5_DDL:
        db.execute(statement)
    # A rerun after a partial upgrade recomputes the same winners, so existing rows stay.
    db.execute(_V5_BACKFILL)


_V6_LISTING_COLUMNS = {"seller": "VARCHAR", "time_left": "BIGINT", "quality": "BIGINT",
                       "level": "BIGINT", "level_type": "VARCHAR", "required_level": "BIGINT",
                       "item_link": "VARCHAR", "variant_id": "VARCHAR", "variant_state": "VARCHAR"}


def _migrate_to_6(db):
    """Richer scans and variant-aware prices; no guessing or rewriting old observations."""
    # Views must be rebound after adding columns; DuckDB freezes SELECT * at view creation.
    for table in ("market_snapshots", "scan_listings"):
        db.execute(f"DROP VIEW IF EXISTS named_{table}")
    for column, dtype in _V6_LISTING_COLUMNS.items():
        db.execute(f"ALTER TABLE scan_listings ADD COLUMN IF NOT EXISTS {column} {dtype}")
    for column in ("variant_id", "variant_state"):
        db.execute(f"ALTER TABLE market_snapshots ADD COLUMN IF NOT EXISTS {column} VARCHAR")
    for column, dtype in {"format_version": "BIGINT", "duration_seconds": "DOUBLE",
                          "availability_json": "VARCHAR"}.items():
        db.execute(f"ALTER TABLE addon_scans ADD COLUMN IF NOT EXISTS {column} {dtype}")
    db.execute(f"""CREATE TABLE IF NOT EXISTS scan_items (
        source_id VARCHAR NOT NULL, scan_id VARCHAR NOT NULL, item_id BIGINT NOT NULL,
        snapshot_id VARCHAR, {_MARKET_COLUMNS}, environment VARCHAR,
        class_id BIGINT, subclass_id BIGINT, item_level BIGINT, max_stack_size BIGINT,
        vendor_sell_copper BIGINT, PRIMARY KEY (source_id, scan_id, item_id))""")
    for statement in _V5_DDL[2:]:
        db.execute(statement)


# Frozen schema only: derived-data initialization/rebuild lives in metrics.py.
def _migrate_to_7(db):
    """Versioned aggregate facts with exact share/coverage numerators and denominators."""
    db.execute("""CREATE TABLE IF NOT EXISTS scan_metrics (
        metric_key VARCHAR PRIMARY KEY, metrics_version BIGINT NOT NULL, source_id VARCHAR NOT NULL,
        market_id VARCHAR, game_version VARCHAR, region VARCHAR, scope VARCHAR, realm VARCHAR,
        server_type VARCHAR, faction VARCHAR, environment VARCHAR,
        scan_id VARCHAR NOT NULL, snapshot_id VARCHAR NOT NULL, item_id BIGINT NOT NULL,
        variant_id VARCHAR, variant_state VARCHAR,
        min_buyout BIGINT, unit_buyout_p10 BIGINT, unit_buyout_p25 BIGINT, unit_buyout_median BIGINT,
        units BIGINT, listings BIGINT, priced_units BIGINT, largest_stack_units BIGINT,
        seller_known_listings BIGINT, seller_known_units BIGINT, seller_count BIGINT, top_seller_units BIGINT)
        """)


# Frozen first-pass columns stay intact. Effective references are resolved only in this view.
def _migrate_to_8(db):
    for field in ("item_level", "max_stack_size", "vendor_sell_copper"):
        db.execute(f"ALTER TABLE scan_items ADD COLUMN IF NOT EXISTS pass_{field} BIGINT")
    db.execute("ALTER TABLE scan_items ADD COLUMN IF NOT EXISTS pass_fields_json VARCHAR")
    db.execute("""CREATE OR REPLACE VIEW effective_scan_items AS
        SELECT * EXCLUDE (item_level, max_stack_size, vendor_sell_copper),
        coalesce(item_level, pass_item_level) AS item_level,
        coalesce(max_stack_size, pass_max_stack_size) AS max_stack_size,
        coalesce(vendor_sell_copper, pass_vendor_sell_copper) AS vendor_sell_copper
        FROM scan_items""")


MIGRATIONS = {1: _migrate_to_1, 2: _migrate_to_2, 3: _migrate_to_3, 4: _migrate_to_4, 5: _migrate_to_5,
              6: _migrate_to_6, 7: _migrate_to_7, 8: _migrate_to_8}


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
    metrics.initialize_metrics(db)


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
        with duckdb.connect(str(path)) as db:
            metrics.initialize_metrics(db)
        return False
    _refuse_newer(version)
    if existed and has_data:
        backup = path.with_name(f"brownstone.v{version}.backup.duckdb")
        if not backup.exists():
            shutil.copy2(path, backup)
    with duckdb.connect(str(path)) as db:
        ensure_schema(db)
        remember_local_catalog_names(db)
    return True


def load_snapshot(db, silver: Path, frame, config: Source) -> tuple[str, bool]:
    """Insert one silver snapshot unless this source already holds identical content.

    The database must already be at SCHEMA_VERSION (see ``upgrade_database``).
    """
    _require_current(db)
    predicate, scope = scope_predicate(config)
    existing = db.execute(f"""SELECT snapshot_id FROM market_snapshots
        WHERE {predicate} AND updated_at IS NOT DISTINCT FROM ? AND source_sha256=? LIMIT 1""",
        [*scope, frame["updated_at"][0], frame["source_sha256"][0]]).fetchone()
    remember_local_catalog_names(db)
    if existing:
        return existing[0], False
    db.execute("INSERT INTO market_snapshots BY NAME SELECT * FROM read_parquet(?)", [str(silver)])
    remember_observed_names(db, frame["snapshot_id"][0])
    return frame["snapshot_id"][0], True


def known_scan(db, config: Mapping[str, Any], scan_id: str) -> dict | None:
    """Dedup per source/scan, refusing reuse of that stable key for a different market.

    Preview can read schema 3 without migrating: adapt the stored row exactly as a manifest.
    """
    cursor = db.execute("SELECT * FROM addon_scans WHERE source_id=? AND scan_id=?",
                        [config["source_id"], scan_id])
    row = cursor.fetchone()
    if row is None:
        return None
    record = markets.upgrade_legacy(dict(zip([c[0] for c in cursor.description], row, strict=True)))
    if any(record.get(key) != config[key] for key in MARKET_KEYS):
        raise ValueError(f"Scan {scan_id} belongs to a different market; use a separate source_id")
    return {key: record[key] for key in ("snapshot_id", "scan_sha256", "priced", "item_count")}


def load_scan(db, scan: Path, listings: Path, prices: Path | None, items: Path | None = None) -> None:
    """Insert one new addon scan from its silver files: the scan row, its listings and, when the scan
    is complete, its item prices. Callers check ``known_scan`` first; a repeat insert fails on the key."""
    _require_current(db)
    db.execute("INSERT INTO addon_scans BY NAME SELECT * FROM read_parquet(?)", [str(scan)])
    db.execute("INSERT INTO scan_listings BY NAME SELECT * FROM read_parquet(?)", [str(listings)])
    if items is not None:
        db.execute("INSERT INTO scan_items BY NAME SELECT * FROM read_parquet(?)", [str(items)])
    if prices is not None:
        db.execute("INSERT INTO market_snapshots BY NAME SELECT * FROM read_parquet(?)", [str(prices)])
    snapshot_id = db.execute("SELECT snapshot_id FROM read_parquet(?)", [str(scan)]).fetchone()[0]
    row = db.execute("SELECT source_id, scan_id FROM read_parquet(?)", [str(scan)]).fetchone()
    metrics.store_scan_metrics(db, row[0], row[1])
    remember_observed_names(db, snapshot_id)


def completed_snapshots(config: Source) -> list[dict]:
    """A source's completed manifests, newest observation first, in the current shape.

    Ordered by upstream scan time when known, else collection time, so importing an older scan
    after a newer one never replaces newer prices.

    Manifests written before the market/source split are upgraded in memory; files are never edited.
    """
    records = []
    identity: Mapping[str, Any] = config
    folder = Path(config["data_dir"]) / "bronze" / config["source_id"]
    for path in folder.glob("*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("status") == "complete":
                upgraded = markets.upgrade_legacy(record)
                if all(upgraded.get(key) == identity[key] for key in ("source_id", *MARKET_KEYS)):
                    records.append(upgraded)
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


def _variant_predicate(variant_id: str | None, state: str | None) -> tuple[str, list]:
    if variant_id is None and state is None:
        # Keep legacy catalog reads; v3 unresolved evidence never feeds a base-item calculation.
        return "variant_id IS NULL AND (variant_state IS NULL OR variant_state='base')", []
    # Explicit reads are exact: legacy (null-state) rows never answer for a format-3 state.
    return "variant_id IS NOT DISTINCT FROM ? AND variant_state=?", [
        variant_id, state or "variant"]


def price_observations(db, config: Mapping[str, Any], snapshot_id: str, item_ids,
                       variant_id: str | None = None, variant_state: str | None = None) -> dict[int, dict]:
    """Read unit copper prices with the source and entire market identity, never item ID alone."""
    if not item_ids:
        return {}
    predicates, scope = scope_predicate(config)
    placeholders = ", ".join("?" for _ in item_ids)
    item_predicate, item_scope = _variant_predicate(variant_id, variant_state)
    rows = db.execute(
        f"SELECT item_id, min_buyout, market_value FROM market_snapshots WHERE snapshot_id=? "
        f"AND {predicates} AND item_id IN ({placeholders}) "
        f"AND {item_predicate}",
        [snapshot_id, *scope, *item_ids, *item_scope],
    ).fetchall()
    return {item_id: {"min_buyout": listed, "market_value": market}
            for item_id, listed, market in rows}


def listing_depth(db, config: Mapping[str, Any], snapshot_id: str,
                  item_ids: list[int], variant_id: str | None = None,
                  variant_state: str | None = None) -> dict[int, dict[str, int]] | None:
    """Stored metric counts and units in the exact priced scan, including listings without a buyout.

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
    item_predicate, item_scope = _variant_predicate(variant_id, variant_state)
    rows = db.execute(
        f"SELECT item_id, listings, units FROM scan_metrics WHERE snapshot_id=? "
        f"AND {predicates} AND scan_id=? AND item_id IN ({placeholders}) "
        f"AND {item_predicate} AND metrics_version=?",
        [*parameters, scan[0], *item_ids, *item_scope, metrics.METRICS_VERSION],
    ).fetchall()
    depth = {item_id: {"listings": 0, "units": 0} for item_id in item_ids}
    depth.update({item_id: {"listings": listings, "units": units} for item_id, listings, units in rows})
    return depth
