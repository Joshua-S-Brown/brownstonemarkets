"""Additive migration and distinct upstream observations in DuckDB."""
import json
from pathlib import Path
import duckdb


def load_snapshot(db, silver, frame, config):
    db.execute("CREATE TABLE IF NOT EXISTS market_snapshots AS SELECT * FROM read_parquet(?) LIMIT 0", [str(silver)])
    for column in ["game_version", "region", "scope", "realm", "source_sha256"]:
        db.execute(f"ALTER TABLE market_snapshots ADD COLUMN IF NOT EXISTS {column} VARCHAR")
    # The only known v0.1 production source was Retail Area 52.
    db.execute("""UPDATE market_snapshots SET game_version='retail', region='us',
        scope='realm', realm='area-52' WHERE market_id='retail-us-area-52' AND game_version IS NULL""")
    existing = db.execute("""SELECT snapshot_id FROM market_snapshots
        WHERE market_id=? AND updated_at IS NOT DISTINCT FROM ? AND source_sha256=? LIMIT 1""",
        [config["market_id"], frame["updated_at"][0], frame["source_sha256"][0]]).fetchone()
    if existing:
        return existing[0], False
    db.execute("INSERT INTO market_snapshots BY NAME SELECT * FROM read_parquet(?)", [str(silver)])
    return frame["snapshot_id"][0], True


def completed_snapshots(config):
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
