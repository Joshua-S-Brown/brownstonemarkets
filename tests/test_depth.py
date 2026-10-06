"""STORY-019: depth belongs to exactly one complete priced scan, source and market."""
import duckdb
import pytest
from conftest import make_source
from test_scans import FINISHED, NOW, addon_source, listing, scan, write_scans

from brownstone.markets import MARKET_KEYS
from brownstone.metrics import rebuild_scan_metrics
from brownstone.pipeline import import_scans
from brownstone.storage import latest_snapshot, listing_depth


def test_depth_counts_stacks_and_no_buyout_listings_without_using_other_scans(tmp_path):
    config = addon_source(tmp_path / "data")
    newer = write_scans(tmp_path / "new.lua", scan("new", FINISHED, [
        listing(1, 20, 200), listing(1, 3, 0), listing(2, 7, 0),
    ]))
    manifest = import_scans(config, newer, now=NOW)
    older = write_scans(tmp_path / "old.lua", scan("old", FINISHED - 3600, [listing(1, 500, 5000),
                                                                              listing(3, 50, 500)]))
    import_scans(config, older, now=NOW)
    partial = write_scans(tmp_path / "partial.lua", scan("partial", FINISHED + 30,
                                                        [listing(1, 900, 9000)], status="stopped"))
    import_scans(config, partial, now=NOW)
    other = addon_source(tmp_path / "data", source_id="other")
    import_scans(other, newer, now=NOW)
    duplicate = import_scans(config, newer, now=NOW)
    _, sid, _ = latest_snapshot(config)
    assert sid == duplicate["analytical_snapshot_id"] == manifest["analytical_snapshot_id"]
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb"), read_only=True) as db:
        assert listing_depth(db, config, sid, [1, 2, 3]) == {
            1: {"listings": 2, "units": 23}, 2: {"listings": 1, "units": 7},
            3: {"listings": 0, "units": 0},
        }
        assert listing_depth(db, config, "my-scans:old", [1, 3]) == {
            1: {"listings": 1, "units": 500}, 3: {"listings": 1, "units": 50},
        }
        assert listing_depth(db, config, "my-scans:partial", [1]) is None
        assert listing_depth(db, config, "other:new", [1]) is None
        assert listing_depth(db, config, sid, []) == {}


@pytest.mark.parametrize("key", ["source_id", *MARKET_KEYS])
def test_depth_requires_every_source_and_market_field(tmp_path, key):
    config = addon_source(tmp_path / "data")
    path = write_scans(tmp_path / "scan.lua", scan("s", FINISHED, [listing(1, 20, 200)]))
    sid = import_scans(config, path, now=NOW)["analytical_snapshot_id"]
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        assert listing_depth(db, {**config, key: "another"}, sid, [1]) is None
        # Even with valid scan metadata, listing rows with a different identity cannot contribute.
        db.execute(f"UPDATE scan_listings SET {key}=?", ["another"])
        rebuild_scan_metrics(db)
        assert listing_depth(db, config, sid, [1]) == {1: {"listings": 0, "units": 0}}


def test_depth_is_unavailable_without_a_matching_priced_scan_or_for_tsm(tmp_path):
    config = addon_source(tmp_path / "data")
    path = write_scans(tmp_path / "scan.lua", scan("s", FINISHED, [listing(1, 20, 200)]))
    sid = import_scans(config, path, now=NOW)["analytical_snapshot_id"]
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        assert listing_depth(db, config, "unknown", [1]) is None
        assert listing_depth(db, make_source(tmp_path / "data"), sid, [1]) is None
        db.execute("UPDATE addon_scans SET priced=false")
        assert listing_depth(db, config, sid, [1]) is None
