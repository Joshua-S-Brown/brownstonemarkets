"""Read-only preparation and exactly reviewed imports, using deterministic race simulations."""
import gzip
import os
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest
from test_scans import COMPLETE, FINISHED, NOW, STOPPED, addon_source, listing, scan, write_scans

from brownstone import pipeline
from brownstone.pipeline import StalePreviewError, import_guidance, import_scans, preview_scans


def tree(folder):
    return {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob("*") if p.is_file()}


def test_preview_mixed_new_duplicate_partial_empty_and_utc_without_writes(tmp_path):
    path = write_scans(tmp_path / "scan.lua", scan("full", FINISHED, [listing(1, 1, 50)]),
                       scan("partial", FINISHED, [listing(2, 1, 20)], status="stopped"),
                       scan("empty", FINISHED, []))
    config = addon_source(tmp_path / "absent/data", path)
    before = tree(tmp_path)
    preview = preview_scans(config, now=NOW)
    assert tree(tmp_path) == before
    assert preview.new_ids == ["full", "partial", "empty"]
    assert [s["partial"] for s in preview.summaries] == [False, True, False]
    assert [s["listing_count"] for s in preview.summaries] == [1, 1, 0]
    assert preview.summaries[0]["finished_at"].isoformat() == "2026-11-04T18:20:00+00:00"
    assert preview.summaries[0]["started_at"].timestamp() == FINISHED - 10
    subset = import_scans(config, scan_ids=["partial"], now=NOW, reviewed=preview)
    assert subset["status"] == "no_complete_scan" and subset["remaining_unimported"] == 2
    assert "Everything" not in import_guidance(subset) and "type /bscan clear" not in import_guidance(subset)
    before = tree(tmp_path)
    mixed = preview_scans(config, now=NOW)
    assert mixed.new_ids == ["full", "empty"] and mixed.known[1] is not None
    assert mixed.summaries[1]["partial"]
    assert tree(tmp_path) == before
    imported = import_scans(config, scan_ids=mixed.new_ids, now=NOW, reviewed=mixed)
    assert imported["remaining_unimported"] == 0 and "Everything" in import_guidance(imported)
    assert not preview_scans(config, now=NOW).new_ids


@pytest.mark.parametrize("change", ["bytes", "source", "evidence", "destination", "market", "environment", "duplicate"])
def test_stale_review_fails_before_writes(tmp_path, change):
    config = addon_source(tmp_path / "data")
    path = write_scans(tmp_path / "scan.lua", scan("s", FINISHED, [listing(1, 1, 50)]))
    config["scan_path"] = path
    reviewed = preview_scans(config, now=NOW)
    if change == "bytes":
        path.write_bytes(path.read_bytes() + b"\n")
    elif change == "source":
        config["source_id"] = "other"
    elif change == "evidence":
        config["scan_evidence"]["label"] = "different"
    elif change == "destination":
        config["data_dir"] = tmp_path / "elsewhere"
    elif change == "environment":
        config["environment"] = "beta"
        config["market_id"] += "-beta"
    elif change == "market":
        config["rules_version"] = "changed"
    else:
        import_scans(config, now=NOW)
    before = tree(tmp_path)
    with pytest.raises(ValueError):
        import_scans(config, scan_ids=["s"], now=NOW, reviewed=reviewed)
    assert tree(tmp_path) == before


def test_read_change_detection_and_bound_are_deterministic(tmp_path, monkeypatch):
    config = addon_source(tmp_path / "absent")
    real_signature = pipeline._file_signature
    calls = 0

    def changed(stat):
        nonlocal calls
        calls += 1
        return (*real_signature(stat)[:-1], calls)

    monkeypatch.setattr(pipeline, "_file_signature", changed)
    with pytest.raises(ValueError, match="changed while reading"):
        preview_scans(config, now=NOW)
    assert not config["data_dir"].exists()
    monkeypatch.setattr(pipeline, "_file_signature", real_signature)
    monkeypatch.setattr(pipeline, "MAX_SCAN_BYTES", 10)
    with pytest.raises(ValueError, match="read limit"):
        preview_scans(config, now=NOW)


def test_descriptor_and_path_stats_are_never_compared_with_each_other(tmp_path, monkeypatch):
    """Windows: fstat and stat can report different device/file IDs for one unchanged file."""
    config = addon_source(tmp_path / "data")
    path = write_scans(tmp_path / "scan.lua", scan("s", FINISHED, [listing(1, 1, 50)]))
    real_fstat = pipeline.os.fstat

    def windows_fstat(fd):
        stat = real_fstat(fd)
        return SimpleNamespace(st_dev=stat.st_dev + 1, st_ino=stat.st_ino + 1, st_size=stat.st_size,
                               st_mtime_ns=stat.st_mtime_ns, st_ctime_ns=stat.st_ctime_ns + 1)

    monkeypatch.setattr(pipeline.os, "fstat", windows_fstat)
    assert preview_scans(config, path, now=NOW).new_ids == ["s"]
    assert import_scans(config, path, now=NOW)["status"] == "complete"
    other = write_scans(tmp_path / "other.lua", scan("t", FINISHED, [listing(1, 1, 60)]))
    real_open = Path.open

    def replaced_before_open(self, *args, **kwargs):
        if self == path and other.exists():
            os.replace(other, path)
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", replaced_before_open)
    with pytest.raises(ValueError, match="changed while reading"):
        preview_scans(config, path, now=NOW)


@pytest.mark.parametrize("content", [b"", b"BrownstoneScanDB = {", b"nonsense", b"\xff"])
def test_bad_files_are_read_only_and_retryable(tmp_path, content):
    path = tmp_path / "broken.lua"
    path.write_bytes(content)
    config = addon_source(tmp_path / "data", path)
    before = tree(tmp_path)
    with pytest.raises(ValueError):
        preview_scans(config, now=NOW)
    assert tree(tmp_path) == before


def test_missing_and_unreadable_files_do_not_create_data(tmp_path, monkeypatch):
    config = addon_source(tmp_path / "data", tmp_path / "missing.lua")
    with pytest.raises(FileNotFoundError):
        preview_scans(config, now=NOW)
    unreadable = write_scans(tmp_path / "unreadable.lua", scan("s", FINISHED, [listing(1, 1, 50)]))
    monkeypatch.setattr(Path, "open", lambda *args, **kwargs: (_ for _ in ()).throw(PermissionError("Unreadable")))
    with pytest.raises(PermissionError):
        preview_scans(config, unreadable, now=NOW)
    assert not config["data_dir"].exists()


def test_conflict_and_shared_house_future_listing_validation(tmp_path):
    config = addon_source(tmp_path / "data")
    import_scans(config, now=NOW)
    records = pipeline.scans.read_saved_variables(config["scan_path"].read_bytes())
    records[0]["label"] = "changed"
    path = write_scans(tmp_path / "conflict.lua", *records)
    before = tree(tmp_path)
    with pytest.raises(ValueError, match="conflict.*different content"):
        preview_scans(config, path, now=NOW)
    assert tree(tmp_path) == before
    for record, message in [
        (scan("future", FINISHED + 7200, []), "future"),
        (scan("invalid", FINISHED, [listing(1, 0, 50)]), "quantity"),
    ]:
        path = write_scans(tmp_path / "invalid.lua", record)
        with pytest.raises(ValueError, match=message):
            preview_scans(config, path, now=NOW)


def test_review_import_preserves_exact_bytes_and_partial_leaves_newest_prices(tmp_path):
    config = addon_source(tmp_path / "data")
    reviewed = preview_scans(config, now=NOW)
    manifest = import_scans(config, scan_ids=[COMPLETE], now=NOW, reviewed=reviewed)
    raw = config["data_dir"] / "bronze/my-scans" / manifest["bronze_file"]
    assert gzip.decompress(raw.read_bytes()) == reviewed.raw
    assert manifest["remaining_unimported"] == 1
    reviewed = preview_scans(config, now=NOW)
    manifest = import_scans(config, scan_ids=[STOPPED], now=NOW, reviewed=reviewed)
    assert manifest["status"] == "no_complete_scan"
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb"), read_only=True) as db:
        assert db.execute("SELECT DISTINCT snapshot_id FROM market_snapshots").fetchall() == [(f"my-scans:{COMPLETE}",)]


def test_empty_unknown_and_duplicate_selection_write_nothing(tmp_path):
    config = addon_source(tmp_path / "data")
    preview = preview_scans(config, now=NOW)
    for selected in [[], ["unknown"]]:
        with pytest.raises(ValueError):
            import_scans(config, scan_ids=selected, now=NOW, reviewed=preview)
    assert not config["data_dir"].exists()
    import_scans(config, now=NOW)
    preview = preview_scans(config, now=NOW)
    before = tree(tmp_path)
    with pytest.raises(StalePreviewError, match="only new"):
        import_scans(config, scan_ids=[COMPLETE], now=NOW, reviewed=preview)
    assert tree(tmp_path) == before


def test_final_duplicate_guard_rejects_race_before_archive(tmp_path, monkeypatch):
    config = addon_source(tmp_path / "data")
    import_scans(config, scan_ids=[COMPLETE], now=NOW)
    preview = preview_scans(config, now=NOW)
    original = pipeline._known_scans
    calls = 0

    def changed(db, source, summaries):
        nonlocal calls
        calls += 1
        known = original(db, source, summaries)
        if calls == 2:  # the recompute, then the writer transaction
            known[1] = {"scan_sha256": summaries[1]["scan_sha256"], "snapshot_id": "elsewhere"}
        return known

    monkeypatch.setattr(pipeline, "_known_scans", changed)
    before = tree(tmp_path)
    with pytest.raises(StalePreviewError, match="Imported scans changed"):
        import_scans(config, scan_ids=[STOPPED], now=NOW, reviewed=preview)
    assert calls == 2 and tree(tmp_path) == before


def test_preview_of_older_database_does_not_migrate_but_import_does(tmp_path):
    from brownstone.storage import MIGRATIONS
    config = addon_source(tmp_path / "data")
    config["data_dir"].mkdir()
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        MIGRATIONS[1](db)
        MIGRATIONS[2](db)
        db.execute("CREATE TABLE schema_info (key VARCHAR PRIMARY KEY, value VARCHAR)")
        db.execute("INSERT INTO schema_info VALUES ('schema_version', '2')")
    before = tree(tmp_path)
    reviewed = preview_scans(config, now=NOW)
    assert reviewed.new_ids == [COMPLETE, STOPPED] and tree(tmp_path) == before
    assert import_scans(config, scan_ids=iter([COMPLETE]), now=NOW, reviewed=reviewed)["status"] == "complete"
    assert (config["data_dir"] / "brownstone.v2.backup.duckdb").exists()


def test_cli_subset_guidance_and_unselected_invalid_house_stay_compatible(tmp_path, monkeypatch, capsys):
    from test_scans import finished_now

    from brownstone import cli
    path = write_scans(tmp_path / "cli.lua", scan("keep", finished_now(), [listing(1, 1, 50)]),
                       scan("unselected", finished_now(), [], faction={"player": "Horde"}))
    config = addon_source(tmp_path / "data", path)
    monkeypatch.setattr(cli, "read_sources", lambda *args: [config])
    monkeypatch.setattr("sys.argv", ["brownstone", "--scan", "keep"])
    cli.main()
    output = capsys.readouterr().out
    # The other-house scan can never be imported here, so it doesn't block guidance but warns against clearing.
    assert "1 record(s) in this file are from another auction house" in output
    assert "remain unimported" not in output and "type /bscan clear" not in output
    # Explicitly selected CLI validation still leaves unrelated scans alone.


def test_cli_subset_ignores_an_unselected_malformed_entry(tmp_path):
    path = write_scans(tmp_path / "cli.lua", scan("keep", FINISHED, [listing(1, 1, 50)]),
                       {"schema_version": 1, "status": "completed"})
    manifest = import_scans(addon_source(tmp_path / "data", path), scan_ids=["keep"], now=NOW)
    assert manifest["status"] == "complete"
    assert manifest["remaining_unimported"] == 1 and "Don't /bscan clear" in import_guidance(manifest)


def test_preview_lists_other_house_scans_and_imports_the_matching_ones(tmp_path):
    path = write_scans(tmp_path / "mixed.lua", scan("ours", FINISHED, [listing(1, 1, 50)]),
                       scan("horde", FINISHED, [listing(2, 1, 50)], faction={"player": "Horde"}))
    config = addon_source(tmp_path / "data", path)
    before = tree(tmp_path)
    preview = preview_scans(config, now=NOW)
    assert tree(tmp_path) == before
    assert preview.new_ids == ["ours"]
    assert not preview.mismatches[0] and any("Horde" in reason for reason in preview.mismatches[1])
    with pytest.raises(StalePreviewError, match="only new"):
        import_scans(config, scan_ids=["horde"], now=NOW, reviewed=preview)
    assert tree(tmp_path) == before
    manifest = import_scans(config, scan_ids=preview.new_ids, now=NOW, reviewed=preview)
    assert (manifest["remaining_unimported"], manifest["other_house"]) == (0, 1)
    assert "another auction house" in import_guidance(manifest)
    assert "type /bscan clear" not in import_guidance(manifest)
    assert not preview_scans(config, now=NOW).new_ids
    with pytest.raises(ValueError, match="does not match"):  # Selecting it explicitly still fails (ADDON-01).
        import_scans(config, scan_ids=["horde"], now=NOW)


def test_reviewed_commit_failure_records_failed_manifest_and_rolls_back(tmp_path, monkeypatch):
    import json

    config = addon_source(tmp_path / "data")
    import_scans(config, scan_ids=[COMPLETE], now=NOW)
    preview = preview_scans(config, now=NOW)
    real_connect = duckdb.connect

    class FailedCommit:
        def __init__(self, connection):
            self.connection = connection

        def __getattr__(self, name):
            return getattr(self.connection, name)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.connection.close()

        def commit(self):
            raise RuntimeError("Simulated commit failure")

    def connect(*args, **kwargs):
        connection = real_connect(*args, **kwargs)
        return connection if kwargs.get("read_only") else FailedCommit(connection)

    monkeypatch.setattr(duckdb, "connect", connect)
    with pytest.raises(RuntimeError, match="commit failure"):
        import_scans(config, scan_ids=[STOPPED], now=NOW, reviewed=preview)
    manifests = [json.loads(p.read_text()) for p in (config["data_dir"] / "bronze/my-scans").glob("*.json")]
    assert any(m["status"] == "failed" and "commit failure" in m["error"] for m in manifests)
    assert preview_scans(config, now=NOW).new_ids == [STOPPED]
