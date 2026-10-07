"""STORY-017: economy isolation, immutable provenance and the v3 migration boundary."""
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest
from conftest import make_source
from test_scan_changes import import_pair
from test_scans import FINISHED, NOW, addon_source, listing, scan, write_scans

from brownstone.action_board import rank_recipes
from brownstone.analysis import browse, rank, screenable_count
from brownstone.config import build_source
from brownstone.crafting import load_recipe_catalog
from brownstone.markets import MARKET_KEYS, legacy_environment, upgrade_legacy
from brownstone.metrics import rebuild_scan_metrics
from brownstone.pipeline import import_scans, preview_scans
from brownstone.scan_changes import compare_scans, eligible_scans
from brownstone.storage import (
    MIGRATIONS,
    SCHEMA_VERSION,
    completed_snapshots,
    latest_snapshot,
    listing_depth,
    price_observations,
    schema_version,
    upgrade_database,
)

TABLES = ("market_snapshots", "addon_scans", "scan_listings")
BETA_TIME = datetime(2026, 10, 4, 19, tzinfo=UTC)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def old_database(tmp_path):
    """Construct pre-environment bytes; only setup writes the synthetic old manifests."""
    config, path = import_pair(tmp_path)
    config = {**config, "environment": "beta", "market_id": config["market_id"] + "-beta"}
    database = config["data_dir"] / "brownstone.duckdb"
    with duckdb.connect(str(database)) as db:
        for table in TABLES:
            db.execute(f"ALTER TABLE {table} DROP COLUMN environment")
        for table in ("market_snapshots", "addon_scans"):
            db.execute(f"UPDATE {table} SET collected_at=?", [BETA_TIME])
        db.execute("UPDATE schema_info SET value='3'")
        db.execute("""INSERT INTO market_snapshots (source_id, market_id, game_version, region, scope,
            realm, server_type, faction, collected_at, snapshot_id, item_id, min_buyout)
            VALUES ('classic', 'classic-us-mankrik-alliance', 'classic', 'us', 'house', 'mankrik',
                    '', 'alliance', ?, 'classic-old', 1, 42)""", [BETA_TIME])
    for manifest in (config["data_dir"] / "bronze" / config["source_id"]).glob("*.json"):
        record = json.loads(manifest.read_text())
        record.pop("environment")
        record["collected_at"] = BETA_TIME.isoformat()
        manifest.write_text(json.dumps(record))
    return config, path, database


def test_config_requires_forever_environment_and_preserves_other_game_ids(tmp_path):
    beta = addon_source(tmp_path, environment="beta")
    live = addon_source(tmp_path, environment="live")
    assert beta["source_id"] == live["source_id"]  # Economy is market identity, not a naming convention.
    assert beta["market_id"] == live["market_id"] + "-beta"
    assert tuple(beta[k] for k in MARKET_KEYS) != tuple(live[k] for k in MARKET_KEYS)
    shared = dict(data_dir=tmp_path, max_age_hours=24, auction_cut=.05, min_discount=.2, top_n=20)
    entry = {k: v for k, v in live.items() if k not in {"environment", "market_id", "data_dir"}}
    with pytest.raises(ValueError, match="environment.*required for forever"):
        build_source(shared, entry)
    for game, realm, faction, expected in (
        ("classic", "mankrik", "alliance", "classic-us-mankrik-alliance"),
        ("retail", "area-52", "", "retail-us-area-52"),
    ):
        source = make_source(tmp_path, game_version=game, realm=realm, faction=faction)
        assert source["environment"] == "live" and source["market_id"] == expected


@pytest.mark.parametrize("environment", ["", "test", None, 1])
def test_invalid_environment_rejected(tmp_path, environment):
    with pytest.raises(ValueError, match="environment"):
        addon_source(tmp_path, environment=environment)


@pytest.mark.parametrize("game,collected,expected", [
    ("forever", "2026-11-03T23:59:59Z", "beta"),
    ("forever", "2026-11-04T00:00:00Z", "live"),
    ("forever", "2026-11-04T00:59:59+01:00", "beta"),
    ("forever", "2026-11-04T00:00:00", "live"),
    ("forever", None, "live"),
    ("classic", "2026-10-04T19:00:00Z", "live"),
])
def test_legacy_manifest_boundary_matches_sql(tmp_path, game, collected, expected):
    record = {"game_version": game, "collected_at": collected}
    assert legacy_environment(record) == expected
    with duckdb.connect(":memory:") as db:
        for migration in range(1, 4):
            MIGRATIONS[migration](db)
        db.execute("INSERT INTO market_snapshots (game_version, collected_at) VALUES (?, ?)", [game, collected])
        MIGRATIONS[4](db)
        assert db.execute("SELECT environment FROM market_snapshots").fetchone() == (expected,)


def test_v3_migration_backup_manifest_adapter_and_duplicate_reimport(tmp_path):
    config, path, database = old_database(tmp_path)
    manifests = {p: digest(p) for p in (config["data_dir"] / "bronze" / config["source_id"]).glob("*.json")}
    before_hash = digest(database)
    with duckdb.connect(str(database), read_only=True) as db:
        counts = [db.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in TABLES]
    # Preview before upgrade uses the same adapter, and creates no backup or changed database.
    preview = preview_scans(config, path, now=NOW)
    assert preview.new_ids == [] and all(preview.known)
    assert digest(database) == before_hash
    assert upgrade_database(config["data_dir"])
    backup = database.with_name("brownstone.v3.backup.duckdb")
    assert digest(backup) == before_hash
    with duckdb.connect(str(database)) as db:
        assert schema_version(db) == SCHEMA_VERSION
        for table, count in zip(TABLES, counts, strict=True):
            assert db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == count
            assert db.execute(f"SELECT DISTINCT environment, market_id FROM {table} "
                              "WHERE game_version='forever'").fetchall() == [("beta", config["market_id"])]
        assert db.execute("SELECT environment, market_id, min_buyout FROM market_snapshots "
                          "WHERE source_id='classic'").fetchall() == [("live", "classic-us-mankrik-alliance", 42)]
        # Replay a completed migration, simulating interruption before schema_info was advanced.
        MIGRATIONS[4](db)
        assert [s["scan_id"] for s in eligible_scans(db, config)] == ["new", "old"]
        assert compare_scans(db, config, "old", "new")["items"]
    assert not upgrade_database(config["data_dir"])
    assert digest(backup) == before_hash
    manifest, sid, count = latest_snapshot(config)
    assert manifest["environment"] == "beta" and count == 1 and sid == "my-scans:new"
    assert completed_snapshots({**config, "environment": "live", "market_id": config["market_id"][:-5]}) == []
    assert all(digest(p) == sha for p, sha in manifests.items())
    imported = import_scans(config, path, now=NOW)
    assert {s["outcome"] for s in imported["scans"]} == {"duplicate"}
    with duckdb.connect(str(database), read_only=True) as db:
        assert [db.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in TABLES] == counts


def test_interrupted_v4_migration_keeps_existing_backup_and_does_not_double_suffix(tmp_path):
    config, _, database = old_database(tmp_path)
    backup = database.with_name("brownstone.v3.backup.duckdb")
    backup.write_bytes(database.read_bytes())
    backup_hash = digest(backup)
    with duckdb.connect(str(database)) as db:
        db.execute("ALTER TABLE market_snapshots ADD COLUMN environment VARCHAR")
        db.execute("UPDATE market_snapshots SET environment='beta', market_id=? WHERE game_version='forever'",
                   [config["market_id"]])
    assert upgrade_database(config["data_dir"])
    assert digest(backup) == backup_hash
    with duckdb.connect(str(database)) as db:
        rows = db.execute("SELECT DISTINCT market_id FROM market_snapshots WHERE game_version='forever'").fetchall()
        assert rows == [(config["market_id"],)]


def test_single_scan_queries_filter_environment_even_with_same_market_and_snapshot_id(tmp_path):
    config, _ = import_pair(tmp_path)
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        # Deliberately identical source, market_id, snapshot, item and times: environment must do the filtering.
        db.execute("""INSERT INTO market_snapshots BY NAME SELECT * REPLACE
            ('beta' AS environment, 9999 AS min_buyout, 20000 AS market_value,
             20000 AS recent_value, 20000 AS historical_value) FROM market_snapshots""")
        sid = "my-scans:new"
        assert browse(db, sid, config, "1")["min_buyout"].to_list() == [120]
        assert screenable_count(db, sid, config) == 0
        assert rank(db, sid, config).is_empty()
        beta = {**config, "environment": "beta"}  # Same market_id proves both fields are checked.
        assert screenable_count(db, sid, beta) == 5
        assert rank(db, sid, beta).height == 5
        assert price_observations(db, config, sid, [1])[1]["min_buyout"] == 120
        db.execute("INSERT INTO scan_listings BY NAME SELECT * REPLACE ('beta' AS environment, "
                   "listing_index+100 AS listing_index, 999 AS quantity) FROM scan_listings")
        assert listing_depth(db, config, sid, [1]) == {1: {"listings": 1, "units": 2}}


def test_multi_scan_queries_isolate_same_source_house_item_and_time(tmp_path):
    config, _ = import_pair(tmp_path)
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        # New scan keys are necessary because per-source scan IDs deliberately stay stable.
        for table in TABLES:
            extra = ", listing_index+100 AS listing_index" if table == "scan_listings" else ""
            scan_key = ", scan_id||'-beta' AS scan_id" if table != "market_snapshots" else ""
            db.execute(f"""INSERT INTO {table} BY NAME SELECT * REPLACE
                ('beta' AS environment, market_id||'-beta' AS market_id,
                 snapshot_id||'-beta' AS snapshot_id{scan_key}{extra}) FROM {table}""")
        rebuild_scan_metrics(db)
        beta = {**config, "environment": "beta", "market_id": config["market_id"] + "-beta"}
        assert [s["scan_id"] for s in eligible_scans(db, config)] == ["new", "old"]
        assert [s["scan_id"] for s in eligible_scans(db, beta)] == ["new-beta", "old-beta"]
        live_diff = compare_scans(db, config, "old", "new")
        beta_diff = compare_scans(db, beta, "old-beta", "new-beta")
        assert live_diff["items"] == beta_diff["items"]
        with pytest.raises(ValueError, match="distinct complete"):
            compare_scans(db, config, "old", "new-beta")


def test_config_environment_change_cannot_relabel_an_imported_scan(tmp_path):
    config, path = import_pair(tmp_path)
    beta = {**config, "environment": "beta", "market_id": config["market_id"] + "-beta"}
    with pytest.raises(ValueError, match="different market.*separate source_id"):
        preview_scans(beta, path, now=NOW)
    with pytest.raises(ValueError, match="different market.*separate source_id"):
        import_scans(beta, path, now=NOW)
    # Identical bytes in a separately configured beta source import normally; scan evidence is unchanged.
    beta["source_id"] = "beta-observer"
    imported = import_scans(beta, path, now=NOW)
    assert {s["outcome"] for s in imported["scans"]} == {"imported"}


def test_unselected_scan_from_another_environment_does_not_fail_a_selected_import(tmp_path):
    config, path = import_pair(tmp_path)
    beta = {**config, "environment": "beta", "market_id": config["market_id"] + "-beta"}
    write_scans(path, scan("old", FINISHED - 3600, [listing(1, 2, 200)]),
                scan("fresh", FINISHED + 60, [listing(1, 1, 99)]))
    manifest = import_scans(beta, path, scan_ids=["fresh"], now=NOW)
    assert manifest["status"] == "complete" and manifest["remaining_unimported"] == 1
    assert [s["outcome"] for s in manifest["scans"]] == ["imported"]


def test_crafting_rejects_cross_environment_snapshot(tmp_path):
    config = addon_source(tmp_path, environment="beta")
    catalog = load_recipe_catalog(Path(__file__).resolve().parents[1] / "config/forever-tailoring.toml")
    with pytest.raises(ValueError, match="different market"):
        rank_recipes(catalog, {}, config, {**config, "environment": "live",
                                          "collected_at": NOW.isoformat()}, now=NOW)


def test_manifest_adapter_preserves_explicit_environment_after_launch(tmp_path):
    source = addon_source(tmp_path, environment="beta")
    record = {**source, "collected_at": NOW.isoformat()}
    assert upgrade_legacy(record)["environment"] == "beta"
    assert upgrade_legacy(record)["market_id"] == source["market_id"]


@pytest.mark.parametrize("selected", ["beta", "classic"])
def test_app_startup_migrates_v3_for_any_selected_source(tmp_path, monkeypatch, selected):
    from streamlit.testing.v1 import AppTest

    config, _, database = old_database(tmp_path)
    classic = make_source(config["data_dir"], game_version="classic", realm="mankrik", faction="alliance",
                          rules_version="classic-era")
    source = config if selected == "beta" else classic
    monkeypatch.setattr("brownstone.config.read_sources", lambda *args: [source])
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run()
    assert not at.exception and any("upgraded" in t.value for t in at.toast)
    with duckdb.connect(str(database), read_only=True) as db:
        assert schema_version(db) == SCHEMA_VERSION
    assert database.with_name("brownstone.v3.backup.duckdb").exists()
    if selected == "beta":
        for view in ("Crafting", "Browse market", "Opportunities", "Scan changes"):
            at.radio[0].set_value(view).run()
            assert not at.exception and not at.error
            assert any(config["market_id"] in caption.value for caption in at.caption)


def test_cli_migrates_v3_and_reimports_only_duplicates(tmp_path, monkeypatch, capsys):
    import sys

    from brownstone.cli import main

    config, path, _ = old_database(tmp_path)
    cfg = tmp_path / "config/market.toml"
    cfg.parent.mkdir()
    cfg.write_text(
        'data_dir = "data"\nmax_age_hours = 24\nauction_cut = 0.05\nmin_discount = 0.2\ntop_n = 20\n'
        '[[sources]]\nsource_id = "my-scans"\nprovider = "addon"\nmachine = "mac"\ngame_version = "forever"\n'
        'environment = "beta"\nregion = "us"\nscope = "house"\nserver_type = "roleplaying"\nfaction = "alliance"\n'
        f'scan_path = "{path}"\n')
    monkeypatch.setattr("brownstone.cli.import_scans",
                        lambda source, path, ids: import_scans(source, path, ids, now=NOW))
    monkeypatch.setattr(sys, "argv", ["brownstone", "--config", str(cfg), "--source", config["source_id"]])
    main()
    output = capsys.readouterr().out
    assert output.count("duplicate") == 2
    assert config["market_id"] in output and "Nothing new" in output


def test_csv_dedup_and_manifest_selection_use_full_environment(tmp_path):
    from test_markets import ore_csv

    from brownstone.pipeline import run

    csv = ore_csv(tmp_path)
    configs = [make_source(tmp_path / "data", game_version="forever", realm="", server_type="normal",
                           faction="alliance", environment=environment) for environment in ("beta", "live")]
    for config in configs:
        run(config, csv)
        run(config, csv)
        assert len(completed_snapshots(config)) == 2
        assert latest_snapshot(config)[0]["environment"] == config["environment"]
    with duckdb.connect(str(tmp_path / "data/brownstone.duckdb"), read_only=True) as db:
        assert db.execute("SELECT environment, count(*) FROM market_snapshots "
                          "GROUP BY environment ORDER BY environment").fetchall() == [("beta", 1), ("live", 1)]


@pytest.mark.parametrize("environment", ["", "invalid", None, "beta"])
def test_non_forever_explicit_environment_is_also_validated(tmp_path, environment):
    with pytest.raises(ValueError, match="environment"):
        make_source(tmp_path, environment=environment)


def test_incomplete_pre_launch_manifest_is_skipped_not_fatal(tmp_path):
    source = addon_source(tmp_path, environment="beta")
    record = {"source_id": source["source_id"], "game_version": "forever", "market_id": "kept",
              "collected_at": BETA_TIME.isoformat()}
    assert upgrade_legacy(record) == {**record, "environment": "beta"}
    folder = tmp_path / "bronze" / source["source_id"]
    folder.mkdir(parents=True)
    (folder / "incomplete.json").write_text(json.dumps({**record, "status": "complete"}))
    assert completed_snapshots(source) == []
