import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest
from conftest import make_source

from brownstone.analysis import browse
from brownstone.config import build_source, read_sources
from brownstone.markets import market_id, upgrade_legacy
from brownstone.normalization import normalize
from brownstone.pipeline import run
from brownstone.storage import SCHEMA_VERSION, completed_snapshots, ensure_schema

HEADER = "itemId,name,marketValue,minBuyout,recent,historical,updatedAt\n"


def ore_csv(tmp_path):
    source = tmp_path / "items.csv"
    source.write_text(HEADER + f"1,Test Ore,10000,9500,10000,10000,{datetime.now(UTC).isoformat()}\n")
    return source


def columns(db):
    return [row[:2] for row in db.execute("DESCRIBE market_snapshots").fetchall()]


def test_market_scopes_and_dedup(tmp_path):
    source = ore_csv(tmp_path)
    for config in [make_source(tmp_path / "data", source_id="house-test"),
                   make_source(tmp_path / "data", source_id="commodity-test", scope="region", realm="")]:
        result, _ = run(config, source)
        assert result.is_empty()  # Browse must still find this item.
        run(config, source)
    with duckdb.connect(str(tmp_path / "data/brownstone.duckdb")) as db:
        assert db.execute("SELECT count(*) FROM market_snapshots").fetchone()[0] == 2
        sid = db.execute("SELECT snapshot_id FROM market_snapshots WHERE scope='region'").fetchone()[0]
        assert browse(db, sid, config, "Ore")["item_id"].to_list() == [1]
        assert browse(db, sid, config, "1").height == 1
        assert browse(db, sid, config, "missing").is_empty()
    manifests = [json.loads(p.read_text()) for p in (tmp_path / "data/bronze").rglob("*.json")]
    assert sum(m["new_observation"] for m in manifests) == 2


def test_two_sources_share_a_market_but_keep_separate_data(tmp_path):
    source = ore_csv(tmp_path)
    tsm = make_source(tmp_path / "data", source_id="tsm-feed")
    mine = make_source(tmp_path / "data", source_id="my-scans", provider="third-party")
    assert tsm["market_id"] == mine["market_id"] == "retail-us-area-52"
    run(tsm, source)
    run(mine, source)  # Identical bytes from a different observer are a separate observation.
    with duckdb.connect(str(tmp_path / "data/brownstone.duckdb")) as db:
        rows = db.execute("SELECT source_id, market_id FROM market_snapshots ORDER BY source_id").fetchall()
    assert rows == [("my-scans", "retail-us-area-52"), ("tsm-feed", "retail-us-area-52")]
    assert {p.name for p in (tmp_path / "data/bronze").iterdir()} == {"tsm-feed", "my-scans"}
    [manifest] = completed_snapshots(mine)
    assert (manifest["source_id"], manifest["provider"]) == ("my-scans", "third-party")


def test_source_config():
    sources = read_sources(Path(__file__).resolve().parents[1] / "config/market.toml")
    assert [s["source_id"] for s in sources] == [
        "classic-us-mankrik-alliance", "retail-us-area-52", "retail-us-commodities",
        "forever-us-normal-alliance-addon",
    ]
    # Pre-split source IDs equal their derived market IDs, so existing data folders stay put.
    assert [s["market_id"] for s in sources[:3]] == [s["source_id"] for s in sources[:3]]
    addon = sources[3]
    assert (addon["market_id"], addon["provider"], addon["enabled"]) == (
        "forever-us-normal-alliance-beta", "addon", False)
    assert addon["scan_path"].is_absolute() and "source_url" not in addon
    assert [s["scope"] for s in sources] == ["house", "house", "region", "house"]
    mankrik = sources[0]
    assert (mankrik["realm"], mankrik["faction"], mankrik["server_type"]) == ("mankrik", "alliance", "")
    assert mankrik["allow_missing_updated_at"] is True
    assert sources[2]["realm"] == ""


def test_forever_market_needs_no_realm_and_neutral_houses_cost_more():
    shared = dict(data_dir=Path("data"), max_age_hours=24, auction_cut=.05, min_discount=.2, top_n=20)
    forever = dict(source_id="my-forever-scans", provider="addon", scan_path="BrownstoneScan.lua",
                   game_version="forever", environment="live", region="us", scope="house", server_type="roleplaying")
    alliance = build_source(shared, {**forever, "faction": "alliance"})
    assert alliance["market_id"] == "forever-us-roleplaying-alliance"
    assert alliance["realm"] == "" and alliance["auction_cut"] == .05
    neutral = build_source(shared, {**forever, "faction": "neutral"})
    assert neutral["market_id"] == "forever-us-roleplaying-neutral"
    assert neutral["auction_cut"] == .15
    assert build_source(shared, {**forever, "faction": "neutral", "auction_cut": .1})["auction_cut"] == .1


@pytest.mark.parametrize("overrides,match", [
    ({"realm": "", "server_type": ""}, "realm or"),
    ({"server_type": "roleplaying"}, "not both"),
    ({"scope": "region"}, "no realm"),
    ({"faction": "goblin"}, "faction"),
    ({"server_type": "casual", "realm": ""}, "server_type"),
    ({"market_id": "anything"}, "derived"),
    ({"source_id": "Has Spaces"}, "source_id"),
])
def test_market_validation(tmp_path, overrides, match):
    with pytest.raises(ValueError, match=match):
        make_source(tmp_path, **overrides)


def test_legacy_manifest_is_read_in_current_shape_without_editing_the_file(tmp_path):
    legacy = {"snapshot_id": "old", "market_id": "classic-us-mankrik-alliance", "status": "complete",
              "collected_at": "2026-10-04T13:55:52+00:00", "game_version": "classic", "region": "us",
              "scope": "realm", "realm": "mankrik-alliance"}
    upgraded = upgrade_legacy(legacy)
    assert {k: upgraded[k] for k in ("source_id", "market_id", "scope", "realm", "faction", "server_type")} == {
        "source_id": "classic-us-mankrik-alliance", "market_id": "classic-us-mankrik-alliance",
        "scope": "house", "realm": "mankrik", "faction": "alliance", "server_type": ""}
    assert legacy["realm"] == "mankrik-alliance"  # The original record is untouched.
    config = make_source(tmp_path / "data", source_id="classic-us-mankrik-alliance", game_version="classic",
                         realm="mankrik", faction="alliance")
    folder = tmp_path / "data/bronze/classic-us-mankrik-alliance"
    folder.mkdir(parents=True)
    (folder / "old.json").write_text(json.dumps(legacy))
    [manifest] = completed_snapshots(config)
    assert manifest["market_id"] == config["market_id"] and manifest["legacy"]
    assert json.loads((folder / "old.json").read_text()) == legacy


def _legacy_database(path, rows):
    """A v0.1 database: schema copied from Parquet, no identity columns, no schema_info."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(path)) as db:
        for i, (old_id, extra) in enumerate(rows):
            frame = normalize((HEADER + f"1,Test Ore,10000,9500,10000,10000,{datetime.now(UTC).isoformat()}\n")
                              .encode(), old_id, f"legacy-{i}", datetime.now(UTC), 24)
            db.register("legacy_frame", frame.to_arrow())
            if i == 0:
                db.execute("CREATE TABLE market_snapshots AS SELECT * FROM legacy_frame")
            else:
                db.execute("INSERT INTO market_snapshots BY NAME SELECT * FROM legacy_frame")
            if extra:
                for column in extra:
                    db.execute(f"ALTER TABLE market_snapshots ADD COLUMN IF NOT EXISTS {column} VARCHAR")
                db.execute(f"UPDATE market_snapshots SET {', '.join(f'{k}=?' for k in extra)} "
                           f"WHERE snapshot_id='legacy-{i}'", list(extra.values()))


def test_legacy_database_migrates_to_markets_and_sources(tmp_path):
    database = tmp_path / "data/brownstone.duckdb"
    _legacy_database(database, [
        ("retail-us-area-52", None),  # v0.1: no identity columns at all.
        ("classic-us-mankrik-alliance", dict(game_version="classic", region="us", scope="realm",
                                             realm="mankrik-alliance")),
        ("retail-us-commodities", dict(game_version="retail", region="us", scope="region", realm="")),
        ("mystery", None),  # Unknown legacy market stays unclassified.
    ])
    with duckdb.connect(str(database)) as db:
        ensure_schema(db)
        rows = db.execute("""SELECT snapshot_id, source_id, market_id, scope, realm, server_type, faction
            FROM market_snapshots ORDER BY snapshot_id""").fetchall()
    assert rows == [
        ("legacy-0", "retail-us-area-52", "retail-us-area-52", "house", "area-52", "", ""),
        ("legacy-1", "classic-us-mankrik-alliance", "classic-us-mankrik-alliance", "house", "mankrik", "",
         "alliance"),
        ("legacy-2", "retail-us-commodities", "retail-us-commodities", "region", "", "", ""),
        ("legacy-3", "mystery", "mystery", None, None, None, None),
    ]


def test_fresh_and_migrated_databases_are_identical_and_versioned(tmp_path):
    run(make_source(tmp_path / "fresh"), ore_csv(tmp_path))
    legacy = tmp_path / "legacy/brownstone.duckdb"
    _legacy_database(legacy, [("retail-us-area-52", None)])
    with duckdb.connect(str(tmp_path / "fresh/brownstone.duckdb")) as fresh, duckdb.connect(str(legacy)) as old:
        ensure_schema(old)
        assert columns(fresh) == columns(old)
        assert fresh.execute("SELECT value FROM schema_info").fetchone() == (str(SCHEMA_VERSION),)
        ensure_schema(fresh)  # Idempotent.
        fresh.execute("UPDATE schema_info SET value='99'")
        with pytest.raises(RuntimeError, match="newer"):
            ensure_schema(fresh)
        assert [name for name, _ in columns(old)][-4:] == ["source_id", "server_type", "faction", "environment"]


def test_market_id_derivation_matches_pre_split_ids():
    assert market_id(dict(game_version="classic", region="us", scope="house", realm="mankrik",
                          faction="alliance")) == "classic-us-mankrik-alliance"
    assert market_id(dict(game_version="retail", region="us", scope="house", realm="area-52")) == "retail-us-area-52"
    assert market_id(dict(game_version="retail", region="us", scope="region")) == "retail-us-commodities"


def test_startup_upgrade_runs_once_and_ignores_missing_database(tmp_path):
    from brownstone.storage import upgrade_database
    assert not upgrade_database(tmp_path / "nothing-here")
    _legacy_database(tmp_path / "data/brownstone.duckdb", [("retail-us-area-52", None)])
    assert upgrade_database(tmp_path / "data")
    assert (tmp_path / "data/brownstone.v0.backup.duckdb").exists()  # Copied before migrating.
    assert not upgrade_database(tmp_path / "data")


def test_interrupted_migration_reruns_cleanly(tmp_path):
    from brownstone.storage import MIGRATIONS
    database = tmp_path / "data/brownstone.duckdb"
    _legacy_database(database, [("classic-us-mankrik-alliance", dict(game_version="classic", region="us",
                                                                     scope="realm", realm="mankrik-alliance"))])
    with duckdb.connect(str(database)) as db:
        for version in sorted(MIGRATIONS):  # Every migration twice, as if a first attempt died part-way.
            MIGRATIONS[version](db)
            MIGRATIONS[version](db)
        assert db.execute("SELECT market_id, realm, faction FROM market_snapshots").fetchall() == [
            ("classic-us-mankrik-alliance", "mankrik", "alliance")]


def test_data_dir_is_shared_never_per_source(tmp_path):
    from brownstone.config import build_source
    shared = dict(data_dir=tmp_path, max_age_hours=24, auction_cut=.05, min_discount=.2, top_n=20)
    entry = dict(source_id="x", provider="tsm", source_url="https://example.com/items.csv", game_version="retail",
                 region="us", scope="house", realm="area-52", data_dir="elsewhere")
    with pytest.raises(ValueError, match="data_dir is shared"):
        build_source(shared, entry)
