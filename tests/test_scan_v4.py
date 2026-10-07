"""Bounded scan-owned item-pass validation, effective references and frozen schema 8."""
import gzip
import json
from pathlib import Path

import duckdb
import pytest
from test_scan_v3 import rich
from test_scans import FINISHED, NOW, addon_source, listing, packed, scan, write_scans

from brownstone import scan_details, scans
from brownstone.markets import MARKET_KEYS
from brownstone.pipeline import import_scans, preview_scans
from brownstone.storage import MIGRATIONS, SCHEMA_VERSION, ensure_schema, schema_version, upgrade_database
from brownstone.today import build_today
from brownstone.today_data import read_today_evidence
from brownstone.today_settings import TodaySettings


def enriched():
    record = rich("enriched")
    record["schema_version"] = 4
    # 6538 answered a request; 2589 had loaded during listing reads and was read without one.
    del record["items"][0]["max_stack_size"]
    record["item_pass"] = {"total": 2, "requested": 1, "received": 1, "failed": 0, "timed_out": 0, "cached": 1,
                           "wait_limit_seconds": 20, "duration_seconds": 3.5, "status": "completed",
                           "api": "C_Item.RequestLoadItemDataByID", "items": [
                               {"item_id": 6538, "max_stack_size": 1},
                               {"item_id": 2589, "item_level": 5, "max_stack_size": 20, "vendor_sell_copper": 100}]}
    return record


def test_v4_mixed_import_raw_effective_precedence_provenance_counts_and_dedup(tmp_path):
    records = [scan("v1", FINISHED - 90, [listing(1, 1, 1)]),
               packed(scan("v2", FINISHED - 60, [listing(1, 1, 1)])), rich(), enriched()]
    path = write_scans(tmp_path / "mixed.lua", *records)
    path.write_text(path.read_text().replace('["schema_version"] = 1,', '["schema_version"] = 4,', 1))
    config = addon_source(tmp_path / "data", path)
    assert preview_scans(config, now=NOW).new_ids == [r["scan_id"] for r in records]
    result = import_scans(config, now=NOW)
    archive = config["data_dir"] / "bronze/my-scans" / result["bronze_file"]
    assert gzip.decompress(archive.read_bytes()) == path.read_bytes()
    measured = result["scans"][-1]["availability"]
    references = scan_details.reference_frame(enriched())
    assert measured == scan_details.availability(scans.listing_frame(enriched()), references, scan=enriched())
    assert measured["item_first_available"]["vendor_sell_copper"] == 1
    assert measured["item_pass_added"]["vendor_sell_copper"] == 1
    assert measured["item_effective_available"]["vendor_sell_copper"] == 2
    assert measured["item_pass"] == {"total": 2, "requested": 1, "received": 1, "failed": 0, "timed_out": 0,
                                     "cached": 1}
    assert scan_details.effective_frame(references)["vendor_sell_copper"].to_list() == [0, 100]
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        assert db.execute("SELECT item_level, max_stack_size, vendor_sell_copper, pass_item_level, "
                          "pass_vendor_sell_copper, pass_fields_json FROM scan_items "
                          "WHERE scan_id='enriched' AND item_id=6538").fetchone() == (
                              15, None, 0, None, None, '["max_stack_size"]')
        assert db.execute("SELECT item_level, max_stack_size, vendor_sell_copper FROM effective_scan_items "
                          "WHERE scan_id='enriched' ORDER BY item_id").fetchall() == [(5, 20, 100), (15, 1, 0)]
        assert db.execute("SELECT pass_fields_json FROM scan_items WHERE scan_id='rich'").fetchall() == [
            (None,), (None,)]
        stored = db.execute("SELECT availability_json FROM addon_scans WHERE scan_id='enriched'").fetchone()[0]
        assert json.loads(stored) == measured
        assert json.loads(db.execute("SELECT pass_fields_json FROM scan_items WHERE scan_id='enriched' "
                                     "AND item_id=2589").fetchone()[0]) == list(scan_details.PASS_FIELDS)
        before = {t: db.execute(f"SELECT * FROM {t} ORDER BY ALL").fetchall()
                  for t in ("scan_items", "scan_listings", "market_snapshots", "scan_metrics", "addon_scans")}
    assert {r["outcome"] for r in import_scans(config, now=NOW)["scans"]} == {"duplicate"}
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        assert all(db.execute(f"SELECT * FROM {t} ORDER BY ALL").fetchall() == rows for t, rows in before.items())


@pytest.mark.parametrize("field,value", [
    ("requested", True), ("received", -1), ("failed", 1.5), ("timed_out", "1"), ("total", 1),
    ("received", 3), ("cached", None), ("cached", 2), ("cached", 0),
    ("duration_seconds", float("nan")), ("duration_seconds", -1),
    ("wait_limit_seconds", True), ("status", "unknown"), ("api", "other"), ("reason", 1),
    ("items", [{"item_id": 2589, "vendor_sell_copper": -1}]),
    ("items", [{"item_id": 2589, "vendor_sell_copper": 1.5}]),
    ("items", [{"item_id": 2589, "vendor_sell_copper": True}]),
    ("items", [{"item_id": 0, "vendor_sell_copper": 1}]),
    ("items", [{"item_id": 2589, "max_stack_size": 0}]),
    ("items", [{"item_id": 2589}]), ("items", [{"item_id": 2589, "class_id": 2}]),
    ("items", [{"item_id": 2589, "vendor_sell_copper": 1}] * 2), ("items", ["bad"]), ("items", None),
    ("items", [{"item_id": 6538, "vendor_sell_copper": 1}]),
    ("items", [{"item_id": 6538, "max_stack_size": 1, "item_level": 50}]),
    ("items", {"item_id": 2589}),
])
def test_malformed_item_pass_rejected(field, value):
    record = enriched()
    record["item_pass"][field] = value
    with pytest.raises(ValueError):
        scan_details.reference_frame(record)


@pytest.mark.parametrize("value", [None, [], "bad", {}])
def test_missing_or_bad_item_pass_table_rejected(value):
    record = enriched()
    record["item_pass"] = value
    with pytest.raises(ValueError, match="item_pass"):
        scan_details.reference_frame(record)


def test_pass_membership_and_received_count_rejected_before_any_preview_write(tmp_path):
    record = enriched()
    record["item_pass"]["items"][1]["item_id"] = 999999
    config = addon_source(tmp_path / "data", write_scans(tmp_path / "bad.lua", record))
    with pytest.raises(ValueError, match="no listing"):
        preview_scans(config, now=NOW)
    assert not config["data_dir"].exists()
    record = enriched()
    record["item_pass"].update(received=0, failed=1)
    with pytest.raises(ValueError, match="exceed received"):
        scan_details.reference_frame(record)


@pytest.mark.parametrize("key", ["source_id", *MARKET_KEYS, "snapshot_id", "scan_id"])
def test_today_pass_vendor_price_and_scope(tmp_path, key):
    record = enriched()
    config = addon_source(tmp_path / "data", write_scans(tmp_path / "pass.lua", record))
    import_scans(config, now=NOW)
    snapshot = {**config, "snapshot_id": "my-scans:enriched", "updated_at": NOW.isoformat()}
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        observations, ladders, metrics, vendors = read_today_evidence(db, config, snapshot["snapshot_id"], [2589])
        assert vendors == {2589: 100}
        result = build_today([], observations, config, snapshot, TodaySettings(10000, 1, "fixed"),
                             now=NOW, listings=ladders, metrics=metrics, vendor_prices=vendors)
        assert result["below_vendor"][0]["item_id"] == 2589
        db.execute(f"UPDATE scan_items SET {key}='other' WHERE scan_id='enriched'")
        assert read_today_evidence(db, config, snapshot["snapshot_id"], [2589])[3] == {}


def test_migration8_backup_replay_layout_and_historical_null_provenance(tmp_path):
    path = tmp_path / "brownstone.duckdb"
    with duckdb.connect(str(path)) as db:
        db.execute("CREATE TABLE schema_info (key VARCHAR PRIMARY KEY, value VARCHAR NOT NULL)")
        for target in range(1, 8):
            MIGRATIONS[target](db)
        db.execute("INSERT INTO schema_info VALUES ('schema_version', '7')")
        db.execute("INSERT INTO scan_items (source_id, scan_id, item_id, vendor_sell_copper) "
                   "VALUES ('source','old',1,0)")
        before = db.execute("SELECT * FROM scan_items").fetchall()
    raw = path.read_bytes()
    assert upgrade_database(tmp_path)
    assert (tmp_path / "brownstone.v7.backup.duckdb").read_bytes() == raw
    with duckdb.connect(str(path)) as db, duckdb.connect() as fresh:
        assert schema_version(db) == SCHEMA_VERSION
        assert db.execute("SELECT * FROM scan_items").fetchall() == [(*before[0], None, None, None, None)]
        MIGRATIONS[8](db)
        MIGRATIONS[8](db)
        ensure_schema(fresh)
        assert db.execute("DESCRIBE scan_items").fetchall() == fresh.execute("DESCRIBE scan_items").fetchall()
        assert db.execute("DESCRIBE effective_scan_items").fetchall() == fresh.execute(
            "DESCRIBE effective_scan_items").fetchall()
        assert db.execute("SELECT vendor_sell_copper, pass_fields_json FROM effective_scan_items").fetchall() == [
            (0, None)]
    assert not upgrade_database(tmp_path)
    assert (tmp_path / "brownstone.v7.backup.duckdb").read_bytes() == raw


def test_format4_fixture():
    path = Path(__file__).parent / "fixtures/brownstone_scan_v4.lua"
    record = scans.read_saved_variables(path.read_bytes())[0]
    assert record == enriched()


def test_empty_pass_and_missing_values_stay_missing_with_empty_provenance():
    record = enriched()
    record["item_pass"].update(total=2, requested=2, received=2, cached=0, items={})
    references = scan_details.reference_frame(record)
    assert references["pass_fields_json"].to_list() == ["[]", "[]"]
    assert scan_details.effective_frame(references)["vendor_sell_copper"].to_list() == [0, None]
    assert scan_details.pass_availability(record, references)["item_pass_added"]["vendor_sell_copper"] == 0
    record["item_pass"].update(received=1)
    with pytest.raises(ValueError, match="unanswered"):
        scan_details.reference_frame(record)


def test_item_pass_change_preserves_existing_scan_id_hash_conflict(tmp_path):
    record = enriched()
    config = addon_source(tmp_path / "data", write_scans(tmp_path / "first.lua", record))
    import_scans(config, now=NOW)
    record["item_pass"]["items"][1]["vendor_sell_copper"] += 1
    with pytest.raises(ValueError, match="different content"):
        import_scans(config, write_scans(tmp_path / "changed.lua", record), now=NOW)


def test_effective_frame_matches_effective_view(tmp_path):
    record = enriched()
    record["item_pass"]["items"][1]["vendor_sell_copper"] = 0  # a pass-reported zero stays present
    config = addon_source(tmp_path / "data", write_scans(tmp_path / "pass.lua", record))
    import_scans(config, now=NOW)
    fields = ", ".join(("item_id", *scan_details.PASS_FIELDS))
    expected = scan_details.effective_frame(scan_details.reference_frame(record)).sort("item_id")
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        rows = db.execute(f"SELECT {fields} FROM effective_scan_items ORDER BY item_id").fetchall()
    assert rows == expected.select("item_id", *scan_details.PASS_FIELDS).rows()
