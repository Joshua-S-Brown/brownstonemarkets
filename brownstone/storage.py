"""DuckDB schema, snapshot loading with deduplication, manifests and scoped price reads."""
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .config import MARKET_KEYS, Source

SCHEMA_VERSION = 1

# Columns stay nullable so databases created by v0.1 (schema copied from Parquet) match
# fresh ones exactly; normalization already rejects nulls where they are not allowed.
MARKET_SNAPSHOTS_DDL = """CREATE TABLE IF NOT EXISTS market_snapshots (
    item_id BIGINT, item_name VARCHAR,
    market_value BIGINT, min_buyout BIGINT, recent_value BIGINT, historical_value BIGINT,
    updated_at TIMESTAMPTZ, market_id VARCHAR, snapshot_id VARCHAR, collected_at TIMESTAMPTZ,
    game_version VARCHAR, region VARCHAR, scope VARCHAR, realm VARCHAR, source_sha256 VARCHAR)"""


def _migrate_to_1(db):
    db.execute(MARKET_SNAPSHOTS_DDL)
    # v0.1 tables predate market identity and source hashes.
    for column in ["game_version", "region", "scope", "realm", "source_sha256"]:
        db.execute(f"ALTER TABLE market_snapshots ADD COLUMN IF NOT EXISTS {column} VARCHAR")
    # The only known v0.1 production source was Retail Area 52; other legacy rows stay unclassified.
    db.execute("""UPDATE market_snapshots SET game_version='retail', region='us',
        scope='realm', realm='area-52' WHERE market_id='retail-us-area-52' AND game_version IS NULL""")


MIGRATIONS = {1: _migrate_to_1}


def ensure_schema(db):
    """Bring the database to SCHEMA_VERSION, running each pending migration once."""
    db.execute("CREATE TABLE IF NOT EXISTS schema_info (key VARCHAR PRIMARY KEY, value VARCHAR NOT NULL)")
    row = db.execute("SELECT value FROM schema_info WHERE key='schema_version'").fetchone()
    version = int(row[0]) if row else 0
    if version > SCHEMA_VERSION:
        raise RuntimeError(f"Database schema {version} is newer than this code supports ({SCHEMA_VERSION})")
    for target in range(version + 1, SCHEMA_VERSION + 1):
        MIGRATIONS[target](db)
        db.execute("INSERT OR REPLACE INTO schema_info VALUES ('schema_version', ?)", [str(target)])


def load_snapshot(db, silver: Path, frame, config: Source) -> tuple[str, bool]:
    ensure_schema(db)
    existing = db.execute("""SELECT snapshot_id FROM market_snapshots
        WHERE market_id=? AND updated_at IS NOT DISTINCT FROM ? AND source_sha256=? LIMIT 1""",
        [config["market_id"], frame["updated_at"][0], frame["source_sha256"][0]]).fetchone()
    if existing:
        return existing[0], False
    db.execute("INSERT INTO market_snapshots BY NAME SELECT * FROM read_parquet(?)", [str(silver)])
    return frame["snapshot_id"][0], True


def completed_snapshots(config: Source) -> list[dict]:
    records = []
    folder = Path(config["data_dir"]) / "bronze" / config["market_id"]
    for path in folder.glob("*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("status") == "complete":
                records.append(record)
        except (OSError, ValueError):
            continue
    return sorted(records, key=lambda r: r["collected_at"], reverse=True)


def latest_snapshot(config: Source) -> tuple[dict | None, str | None, int]:
    """Newest completed manifest and the analytical snapshot ID its prices live under."""
    manifests = completed_snapshots(config)
    if not manifests:
        return None, None, 0
    latest = manifests[0]
    return latest, latest.get("analytical_snapshot_id", latest["snapshot_id"]), len(manifests)


def price_observations(db, config: Mapping[str, Any], snapshot_id: str, item_ids) -> dict[int, dict]:
    """Read unit copper prices with the entire market identity, never item ID alone."""
    if not item_ids:
        return {}
    predicates = " AND ".join(f"{key}=?" for key in MARKET_KEYS)
    placeholders = ", ".join("?" for _ in item_ids)
    rows = db.execute(
        f"SELECT item_id, min_buyout, market_value FROM market_snapshots WHERE snapshot_id=? "
        f"AND {predicates} AND item_id IN ({placeholders})",
        [snapshot_id, *[config[key] for key in MARKET_KEYS], *item_ids],
    ).fetchall()
    return {item_id: {"min_buyout": listed, "market_value": market}
            for item_id, listed, market in rows}
