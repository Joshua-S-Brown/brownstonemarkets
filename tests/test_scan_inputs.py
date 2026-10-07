"""Second-machine files: offline inputs only; never use personal paths or real data."""
import gzip
import hashlib
from pathlib import Path

import duckdb
import pytest
from test_scans import FINISHED, NOW, addon_source, listing, scan, write_scans

from brownstone import cli, pipeline
from brownstone.config import build_source, read_sources
from brownstone.drop_files import CONTRACT, ignored_reason, parse_drop_name
from brownstone.pipeline import StalePreviewError, import_scans
from brownstone.scan_inputs import file_rows, import_inputs, latest_rows, preview_inputs
from brownstone.storage import MIGRATIONS, ensure_schema, schema_version, upgrade_database


def inputs(tmp_path):
    own = write_scans(tmp_path / "own.lua", scan("mac", FINISHED, [listing(1, 1, 50)]))
    drop = tmp_path / "drop"
    drop.mkdir()
    config = addon_source(tmp_path / "data", own, machine="mac", drop_folder=drop)
    return config, drop


def dropped(folder, records, name="windows-pc-20261007T004900Z-BrownstoneScan.lua"):
    return write_scans(folder / name, *records)


@pytest.mark.parametrize("example", CONTRACT["examples"], ids=lambda example: example["name"])
def test_shared_drop_naming_examples(example):
    assert bool(parse_drop_name(example["name"])) is example["valid"]


@pytest.mark.parametrize("machine", ["PC", "pc_1", "", "pc space", None, 2, "pc\n"])
def test_machine_validation(tmp_path, machine):
    with pytest.raises(ValueError, match="machine"):
        addon_source(tmp_path, machine=machine)


def test_local_only_config_merges_paths_and_requires_machine(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    base = config_dir / "market.toml"
    base.write_text('''data_dir = "data"
max_age_hours = 24
auction_cut = 0.05
min_discount = 0.2
top_n = 20
[[sources]]
source_id = "addon"
provider = "addon"
game_version = "classic"
region = "us"
scope = "house"
realm = "mankrik"
faction = "alliance"
scan_path = "own.lua"
''')
    local = config_dir / "market.local.toml"
    local.write_text('[sources.addon]\nmachine = "mac"\ndrop_folder = "drop"\n')
    source = read_sources(base, local)[0]
    assert source["drop_folder"] == tmp_path / "drop" and source["machine"] == "mac"
    base.write_text(base.read_text() + 'drop_folder = "drop"\n')
    with pytest.raises(ValueError, match="only in market.local"):
        read_sources(base, local)
    with pytest.raises(ValueError, match="requires"):
        source = dict(addon_source(tmp_path))
        source.pop("machine")
        source.pop("market_id")
        data_dir = source.pop("data_dir")
        build_source({"data_dir": data_dir}, source)


def test_two_machines_one_market_exact_collections_duplicates_cleanup(tmp_path):
    config, folder = inputs(tmp_path)
    win = dropped(folder, [scan("win", FINISHED + 1, [listing(2, 1, 99)], status="stopped")])
    raw = {config["scan_path"]: config["scan_path"].read_bytes(), win: win.read_bytes()}
    reviewed = preview_inputs(config, NOW)
    assert not config["data_dir"].exists()
    assert latest_rows(reviewed)[0]["Fully imported"] is False
    results = import_inputs(config, reviewed, now=NOW)
    assert len(results) == 2 and all(r["status"] == "imported" for r in results)
    for result in results:
        manifest = result["manifest"]
        path = Path(result["file"])
        assert manifest["original_file_name"] == path.name
        assert manifest["machine"] == result["machine"]
        archive = config["data_dir"] / "bronze/my-scans" / manifest["bronze_file"]
        assert gzip.decompress(archive.read_bytes()) == raw[path]
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        counts = db.execute("SELECT count(DISTINCT market_id), count(DISTINCT machine) FROM addon_scans").fetchone()
        assert counts == (1, 2)
        assert db.execute("SELECT priced FROM addon_scans WHERE scan_id='win'").fetchone() == (False,)
    current = preview_inputs(config, NOW)
    assert all(f.fully_imported for f in current.files)
    assert latest_rows(current)[0]["Fully imported"] is True
    assert import_inputs(config, current, now=NOW) == []  # unattended runs never re-archive imported files
    again = import_inputs(config, current, [str(f.path) for f in current.files], NOW)
    assert all(r["manifest"]["scans"][0]["outcome"] == "duplicate" for r in again)
    assert all(path.read_bytes() == data for path, data in raw.items())


def test_unreadable_other_house_ignored_beside_good_and_latest_status(tmp_path, monkeypatch):
    config, folder = inputs(tmp_path)
    good = dropped(folder, [scan("win", FINISHED, [listing(2, 1, 80)])])
    bad = dropped(folder, [scan("bad", FINISHED, [])], "windows-pc-20261007T005000Z-BrownstoneScan.lua")
    other = dropped(folder, [scan("horde", FINISHED, [], faction={"player": "Horde"})],
                    "horde-pc-20261007T004900Z-BrownstoneScan.lua")
    truncated = folder / "broken-20261007T004900Z-BrownstoneScan.lua"
    truncated.write_bytes(b"BrownstoneScanDB = {")
    for name in ("copy.partial", "x (1).lua", "notes.txt"):
        (folder / name).write_text("ignored")
    original = pipeline._read_scan_bytes

    def unreadable(path):
        if path == bad:
            raise PermissionError("still syncing")
        return original(path)

    monkeypatch.setattr(pipeline, "_read_scan_bytes", unreadable)
    preview = preview_inputs(config, NOW)
    rows = file_rows(preview)
    assert any("still syncing" in r["Status"] for r in rows)
    assert len([f for f in preview.files if f.ignored]) == 3
    assert any("Horde" in reason for reason in
               next(f for f in preview.files if f.path == other).preview.mismatches[0])
    results = import_inputs(config, preview, now=NOW)
    assert {r["file"] for r in results} == {str(config["scan_path"]), str(good)}
    latest = {r["Machine"]: r for r in latest_rows(preview_inputs(config, NOW))}
    assert not latest["windows-pc"]["Fully imported"] and not latest["horde-pc"]["Fully imported"]
    assert "Partial" in ignored_reason("x.tmp") and "Conflict" in ignored_reason("x conflict.lua")


def test_same_scan_duplicate_and_conflict_across_files(tmp_path):
    config, folder = inputs(tmp_path)
    mac_record = scan("mac", FINISHED, [listing(1, 1, 50)])
    dropped(folder, [mac_record])
    conflict = dropped(folder, [scan("mac", FINISHED, [listing(1, 1, 51)])],
                       "windows-pc-20261007T005000Z-BrownstoneScan.lua")
    results = import_inputs(config, preview_inputs(config, NOW), now=NOW)
    assert results[1]["manifest"]["scans"][0]["outcome"] == "duplicate"
    assert results[2]["status"] == "error" and "conflict" in results[2]["error"]
    preview = preview_inputs(config, NOW)
    assert "conflict" in next(f for f in preview.files if f.path == conflict).error
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        assert db.execute("SELECT machine FROM addon_scans").fetchall() == [("mac",)]


@pytest.mark.parametrize("change", ["file", "config", "inventory", "database"])
def test_batch_review_invalidates_before_any_archive(tmp_path, change):
    config, folder = inputs(tmp_path)
    reviewed = preview_inputs(config, NOW)
    if change == "file":
        config["scan_path"].write_bytes(config["scan_path"].read_bytes() + b"\n")
    elif change == "config":
        config["machine"] = "different"
    elif change == "inventory":
        (folder / "notes.txt").write_text("new entry")
    else:
        import_scans(config, now=NOW)
    before = sorted(tmp_path.rglob("*.json"))
    with pytest.raises(StalePreviewError):
        import_inputs(config, reviewed, now=NOW)
    assert sorted(tmp_path.rglob("*.json")) == before


def test_missing_folder_invalid_selection_and_changed_file_during_batch(tmp_path, monkeypatch):
    config, folder = inputs(tmp_path)
    folder.rmdir()
    assert "Drop folder unreadable" in preview_inputs(config, NOW).files[-1].error
    folder.mkdir()
    with pytest.raises(ValueError, match="Select only"):
        import_inputs(config, preview_inputs(config, NOW), ["unknown"], NOW)
    with pytest.raises(ValueError, match="Unknown scan IDs"):
        import_inputs(config, preview_inputs(config, NOW), now=NOW, scan_ids=["unknown"])
    from brownstone import scan_inputs
    original = scan_inputs.preview_scans
    calls = 0

    def changing(*args):
        nonlocal calls
        calls += 1
        if calls == 3:
            config["scan_path"].write_bytes(config["scan_path"].read_bytes() + b"\n")
        return original(*args)

    monkeypatch.setattr(scan_inputs, "preview_scans", changing)
    results = import_inputs(config, preview_inputs(config, NOW), now=NOW)
    assert results[0]["status"] == "error" and "File changed" in results[0]["error"]
    assert not config["data_dir"].exists()


def test_schema9_backup_replay_and_legacy_missing_machine(tmp_path):
    config = addon_source(tmp_path / "data")
    import_scans(config, now=NOW)
    path = config["data_dir"] / "brownstone.duckdb"
    with duckdb.connect(str(path)) as db:
        db.execute("ALTER TABLE addon_scans DROP COLUMN machine")
        db.execute("UPDATE schema_info SET value='8' WHERE key='schema_version'")
        before = db.execute("SELECT * FROM addon_scans ORDER BY ALL").fetchall()
    old_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    assert upgrade_database(config["data_dir"])
    backup = config["data_dir"] / "brownstone.v8.backup.duckdb"
    assert hashlib.sha256(backup.read_bytes()).hexdigest() == old_hash
    with duckdb.connect(str(path)) as db, duckdb.connect() as fresh:
        ensure_schema(fresh)
        assert db.execute("DESCRIBE addon_scans").fetchall() == fresh.execute("DESCRIBE addon_scans").fetchall()
        assert schema_version(db) == 9
        assert db.execute("SELECT * EXCLUDE(machine) FROM addon_scans ORDER BY ALL").fetchall() == before
        assert db.execute("SELECT machine FROM addon_scans").fetchall() == [(None,), (None,)]
        MIGRATIONS[9](db)
        ensure_schema(db)
        assert db.execute("SELECT * EXCLUDE(machine) FROM addon_scans ORDER BY ALL").fetchall() == before
    assert not upgrade_database(config["data_dir"])
    assert hashlib.sha256(backup.read_bytes()).hexdigest() == old_hash


def test_cli_batch_preview_import_subset_and_input_override(tmp_path, monkeypatch, capsys):
    from test_scans import finished_now
    config, folder = inputs(tmp_path)
    write_scans(config["scan_path"], scan("mac", finished_now(), [listing(1, 1, 50)]))
    drop = dropped(folder, [scan("win", finished_now(), [listing(2, 1, 80)])])
    monkeypatch.setattr(cli, "read_sources", lambda *args: [config])
    monkeypatch.setattr("sys.argv", ["brownstone", "--preview"])
    cli.main()
    assert "windows-pc" in capsys.readouterr().out and not config["data_dir"].exists()
    monkeypatch.setattr("sys.argv", ["brownstone", "--scan", "win"])
    cli.main()
    assert "imported" in capsys.readouterr().out
    monkeypatch.setattr("sys.argv", ["brownstone", "--preview", "--input", str(config["scan_path"])])
    cli.main()
    assert "mac mac: new" in capsys.readouterr().out
    monkeypatch.setattr("sys.argv", ["brownstone", "--preview", "--input", str(drop)])
    cli.main()
    assert "windows-pc win: duplicate" in capsys.readouterr().out  # --input keeps the drop's machine
    monkeypatch.setattr("sys.argv", ["brownstone"])
    cli.main()
    assert "Fully imported': True" in capsys.readouterr().out


def test_batch_scan_subset_leaves_remaining_and_other_house(tmp_path):
    config, folder = inputs(tmp_path)
    dropped(folder, [scan("one", FINISHED, [listing(1, 1, 50)]), scan("two", FINISHED, []),
                     scan("horde", FINISHED, [], faction={"player": "Horde"})])
    result = import_inputs(config, preview_inputs(config, NOW), now=NOW, scan_ids=["one"])[0]["manifest"]
    assert result["remaining_unimported"] == 1 and result["other_house"] == 1
    assert not preview_inputs(config, NOW).latest()[0].fully_imported


def test_drop_cannot_contain_database_and_nonaddon_rejects_provenance(tmp_path):
    for invalid in ("", None):
        with pytest.raises(ValueError, match="non-empty"):
            addon_source(tmp_path, drop_folder=invalid)
    with pytest.raises(ValueError, match="outside"):
        addon_source(tmp_path / "drop/data", drop_folder=tmp_path / "drop")
    source = dict(addon_source(tmp_path))
    source.update(provider="tsm", source_url="https://example.test/prices")
    source.pop("market_id")
    data_dir = source.pop("data_dir")
    with pytest.raises(ValueError, match="addon sources only"):
        build_source({"data_dir": data_dir}, source)


def test_external_duplicate_state_change_during_batch_is_stale(tmp_path, monkeypatch):
    from brownstone import scan_inputs
    config, folder = inputs(tmp_path)
    reviewed = preview_inputs(config, NOW)
    original = scan_inputs.preview_scans
    calls = 0

    def external_import(*args):
        nonlocal calls
        calls += 1
        if calls == 2:  # After batch preflight, before this file's writer check.
            import_scans(config, now=NOW)
        return original(*args)

    monkeypatch.setattr(scan_inputs, "preview_scans", external_import)
    result = import_inputs(config, reviewed, now=NOW)[0]
    assert result["status"] == "error" and "Imported scans changed" in result["error"]
    assert len(list((config["data_dir"] / "bronze/my-scans").glob("*.json"))) == 1
