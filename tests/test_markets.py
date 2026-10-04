import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest

from brownstone.analysis import browse
from brownstone.config import read_sources
from brownstone.pipeline import run


def test_market_scopes_and_dedup(tmp_path):
    source = tmp_path / "items.csv"
    source.write_text("itemId,name,marketValue,minBuyout,recent,historical,updatedAt\n" +
        f"1,Test Ore,10000,9500,10000,10000,{datetime.now(UTC).isoformat()}\n")
    base = dict(data_dir=tmp_path / "data", max_age_hours=24, source_url="https://example.com/items.csv",
                auction_cut=.05, min_discount=.2, top_n=20, game_version="retail", region="us")
    for scope, market, realm in [("realm", "realm-test", "area-52"), ("region", "commodity-test", "")]:
        config = {**base, "scope": scope, "market_id": market, "realm": realm}
        result, _ = run(config, source)
        assert result.is_empty()  # Browse must still find this item.
        run(config, source)
    with duckdb.connect(str(tmp_path / "data/brownstone.duckdb")) as db:
        assert db.execute("SELECT count(*) FROM market_snapshots").fetchone()[0] == 2
        sid = db.execute("SELECT snapshot_id FROM market_snapshots WHERE scope='region'").fetchone()[0]
        assert browse(db, sid, "Ore")["item_id"].to_list() == [1]
        assert browse(db, sid, "1").height == 1
        assert browse(db, sid, "missing").is_empty()
    manifests = [json.loads(p.read_text()) for p in (tmp_path / "data/bronze").rglob("*.json")]
    assert sum(m["new_observation"] for m in manifests) == 2


def test_source_config():
    sources = read_sources(Path(__file__).resolve().parents[1] / "config/market.toml")
    assert [s["market_id"] for s in sources] == [
        "classic-us-mankrik-alliance", "retail-us-area-52", "retail-us-commodities",
    ]
    assert [s["scope"] for s in sources] == ["realm", "realm", "region"]
    assert sources[2]["realm"] == ""
    assert sources[0]["game_version"] == "classic"
    assert sources[0]["realm"] == "mankrik-alliance"
    assert sources[0]["allow_missing_updated_at"] is True


def test_legacy_database_migration(tmp_path):
    from brownstone.normalization import normalize
    source = tmp_path / "items.csv"
    now = datetime.now(UTC)
    source.write_text("itemId,name,marketValue,minBuyout,recent,historical,updatedAt\n" +
        f"1,Test Ore,10000,9500,10000,10000,{now.isoformat()}\n")
    config = dict(data_dir=tmp_path / "data", market_id="retail-us-area-52", max_age_hours=24,
                  source_url="https://example.com/items.csv", auction_cut=.05, min_discount=.2, top_n=20,
                  game_version="retail", region="us", scope="realm", realm="area-52")
    config["data_dir"].mkdir()
    old = normalize(source.read_bytes(), config["market_id"], "legacy", now, 24)
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        db.register("legacy_frame", old.to_arrow())
        db.execute("CREATE TABLE market_snapshots AS SELECT * FROM legacy_frame")
    run(config, source)
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        assert db.execute("SELECT count(*) FROM market_snapshots").fetchone()[0] == 2
        identity = db.execute("SELECT game_version,scope,realm FROM market_snapshots "
                              "WHERE snapshot_id='legacy'").fetchone()
        assert identity == ("retail", "realm", "area-52")


def test_fresh_database_matches_legacy_schema_and_records_version(tmp_path):
    from brownstone.storage import SCHEMA_VERSION, ensure_schema
    source = tmp_path / "items.csv"
    source.write_text("itemId,name,marketValue,minBuyout,recent,historical,updatedAt\n" +
        f"1,Test Ore,10000,9500,10000,10000,{datetime.now(UTC).isoformat()}\n")
    config = dict(data_dir=tmp_path / "data", market_id="retail-us-area-52", max_age_hours=24,
                  source_url="https://example.com/items.csv", auction_cut=.05, min_discount=.2, top_n=20,
                  game_version="retail", region="us", scope="realm", realm="area-52")
    run(config, source)
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        columns = [row[:2] for row in db.execute("DESCRIBE market_snapshots").fetchall()]
        assert db.execute("SELECT value FROM schema_info").fetchone() == (str(SCHEMA_VERSION),)
        ensure_schema(db)  # Idempotent.
        db.execute("UPDATE schema_info SET value='99'")
        with pytest.raises(RuntimeError, match="newer"):
            ensure_schema(db)
    # Parquet-derived v0.1 schema plus identity columns: what existing databases contain.
    assert columns == [
        ("item_id", "BIGINT"), ("item_name", "VARCHAR"), ("market_value", "BIGINT"), ("min_buyout", "BIGINT"),
        ("recent_value", "BIGINT"), ("historical_value", "BIGINT"), ("updated_at", "TIMESTAMP WITH TIME ZONE"),
        ("market_id", "VARCHAR"), ("snapshot_id", "VARCHAR"), ("collected_at", "TIMESTAMP WITH TIME ZONE"),
        ("game_version", "VARCHAR"), ("region", "VARCHAR"), ("scope", "VARCHAR"), ("realm", "VARCHAR"),
        ("source_sha256", "VARCHAR")]
