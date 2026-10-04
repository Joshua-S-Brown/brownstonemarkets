import json
from datetime import datetime, timezone
import duckdb
from brownstone.analysis import browse
from brownstone.pipeline import run
from brownstone.config import read_config
from pathlib import Path


def test_market_scopes_and_dedup(tmp_path):
    source = tmp_path / "items.csv"
    source.write_text("itemId,name,marketValue,minBuyout,recent,historical,updatedAt\n" +
        f"1,Test Ore,10000,9500,10000,10000,{datetime.now(timezone.utc).isoformat()}\n")
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
    config = read_config(Path(__file__).resolve().parents[1] / "config/market.toml")
    assert [s["scope"] for s in config["sources"]] == ["realm", "region"]
    assert config["sources"][1]["realm"] == ""


def test_legacy_database_migration(tmp_path):
    from brownstone.normalization import normalize
    source = tmp_path / "items.csv"
    now = datetime.now(timezone.utc)
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
        assert db.execute("SELECT game_version,scope,realm FROM market_snapshots WHERE snapshot_id='legacy'").fetchone() == ("retail", "realm", "area-52")
