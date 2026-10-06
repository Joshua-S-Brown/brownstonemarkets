"""Richer scans: real Forever link shapes, nullable observations and isolated prices."""
import gzip
import json

import duckdb
import polars as pl
import pytest
from test_scans import FINISHED, NOW, addon_source, listing, packed, scan, write_scans

from brownstone import scan_details, scans, variants
from brownstone.analysis import browse, rank
from brownstone.markets import MARKET_KEYS
from brownstone.metrics import rebuild_scan_metrics
from brownstone.pipeline import import_scans, preview_scans
from brownstone.scan_changes import compare_scans
from brownstone.storage import MIGRATIONS, ensure_schema, listing_depth, price_observations, upgrade_database

# Exact payloads from the 2026-10-04 Forever beta archive; no seller data in fixtures.
MONKEY = "|cnIQ2:|Hitem:6538::::::::1:1491:::1:12721::::::|h[Willow Robe of the Monkey]|h|r"
BEAR = "|cnIQ2:|Hitem:6538::::::::1:1491::1:1:12722:1:28:5240:::::|h[Willow Robe of the Bear]|h|r"
BASE = "|cnIQ1:|Hitem:2589::::::::1:1491:::::::::|h[Linen Cloth]|h|r"


def rich(scan_id="rich", finished=FINISHED, status="completed"):
    rows = [listing(6538, 1, 500, "Willow Robe of the Monkey"),
            listing(6538, 2, 300, "Willow Robe of the Bear"),
            listing(6538, 1, 1, ""), listing(2589, 20, 701, "Linen Cloth"),
            listing(2589, 10, 0, "Linen Cloth")]
    record = packed(scan(scan_id, finished, rows, status=status))
    extras = [(1, 4, 2, 10, 1, 1), (2, 1, 2, 10, 1, 2), (0, "", "", "", 0, 0),
              (1, 3, 1, 0, 1, 3), (1, 2, 1, 15, 2, 3)]
    return {**record, "schema_version": 3, "listing_format": scans.PACKED_V3_FORMAT,
            "listings": [r + ":" + ":".join(map(str, e)) for r, e in zip(record["listings"], extras, strict=True)],
            "sellers": ["TestSeller", "TestSeller-Other"], "level_types": ["REQ_LEVEL", "ITEM_LEVEL"],
            "links": [MONKEY, BEAR, BASE], "duration_seconds": 12.5,
            "items": [{"item_id": 6538, "class_id": 4, "subclass_id": 1, "item_level": 15,
                       "max_stack_size": 1, "vendor_sell_copper": 0}, {"item_id": 2589}]}


def test_v3_fields_units_availability_and_missing_values():
    record = rich()
    frame = scans.listing_frame(record)
    assert frame["seller"].to_list() == ["TestSeller", "TestSeller-Other", None, "TestSeller", "TestSeller"]
    assert frame["required_level"].to_list() == [10, 10, None, 0, None]
    assert frame["quality"].to_list() == [2, 2, None, 1, 1]
    assert frame["time_left"].to_list() == [4, 1, None, 3, 2]
    assert frame["item_link"].to_list() == [MONKEY, BEAR, None, BASE, BASE]
    assert frame["variant_state"].to_list() == ["variant", "variant", "unresolved", "base", "base"]
    assert frame["unit_buyout_ceil"].to_list() == [500, 150, 1, 36, None]
    items = scan_details.item_frame(record)
    assert items.row(1, named=True) == dict.fromkeys(scan_details.ITEM_SCHEMA) | {"item_id": 2589}
    assert items["vendor_sell_copper"].to_list() == [0, None]
    measured = scan_details.availability(frame, items)
    assert measured["listing_available"]["seller"] == 4
    assert measured["listing_available"]["required_level"] == 3
    assert measured["item_available"]["vendor_sell_copper"] == 1
    assert measured["variant_states"] == {"variant": 2, "base": 2, "unresolved": 1}
    prices = scans.item_prices(frame)
    assert prices.height == 4
    assert prices.filter(pl.col("variant_state") == "variant")["min_buyout"].to_list() == [500, 150]


@pytest.mark.parametrize("link", [None, "", "not an item link", MONKEY.replace("6538", "6539"),
                                  MONKEY.replace(":::1:12721", ":::2:12721"),
                                  MONKEY.replace("12721", "not-an-id"),
                                  BEAR.replace(":28:5240", ":29:5240"),
                                  BEAR.replace(":1:28:5240", ":2:28:5240"),
                                  BEAR.replace(":::::|h", ":::15::|h"),
                                  MONKEY.replace(":::1:12721", "::2:1:12721"),
                                  MONKEY.replace(":::1:12721", ":::1:0"),
                                  MONKEY.replace("::::::::1", "::::::-10:555:1"),
                                  "|Hitem:6538:0:0|h[x]|h"])
def test_unsupported_or_missing_links_are_unresolved(link):
    assert variants.identity(6538, link) == (None, "unresolved")


def test_variant_identity_ignores_viewer_provenance_and_keeps_stat_fields():
    monkey = variants.identity(6538, MONKEY)
    assert monkey == variants.identity(6538, MONKEY.replace(":1:1491", ":60:9999"))
    assert monkey == variants.identity(6538, MONKEY.replace(":::1:12721::::::", "::1:1:12721:1:28:1234:::::"))
    assert monkey != variants.identity(6538, BEAR)
    assert variants.identity(2589, BASE) == (None, "base")
    left = MONKEY.replace(":::1:12721", ":::2:12721:777")
    right = MONKEY.replace(":::1:12721", ":::2:777:12721")
    assert variants.identity(6538, left) == variants.identity(6538, right)
    assert variants.identity(6538, left) != monkey
    assert variants.identity(6538, MONKEY.replace("6538:", "6538:123")) != monkey
    assert variants.identity(6538, MONKEY.replace("6538::", "6538::456")) != monkey
    assert variants.identity(6538, MONKEY.replace("6538::::::", "6538::::::99")) != monkey


@pytest.mark.parametrize("field,value,match", [("seller_index", "3", "seller_index"),
                                             ("link_index", "-1", "link_index"),
                                             ("level_type_index", "3", "level_type_index"),
                                             ("quality", "1.5", "integer copper"),
                                             ("quantity", "", "missing packed"), ("flags", "", "missing packed"),
                                             ("buyout", "-1", "negative price"), ("bid", "-1", "negative price")])
def test_bad_rich_listing_is_rejected(field, value, match):
    record = rich()
    parts = record["listings"][0].split(":")
    parts[scans.PACKED_V3_FIELDS.index(field)] = value
    record["listings"][0] = ":".join(parts)
    with pytest.raises(ValueError, match=match):
        scans.listing_frame(record)


def test_out_of_range_optional_values_become_missing_and_are_counted():
    record = rich()
    for i, (field, value) in enumerate([("time_left", "0"), ("quality", "-1"), ("level", "-1")]):
        parts = record["listings"][i].split(":")
        parts[scans.PACKED_V3_FIELDS.index(field)] = value
        record["listings"][i] = ":".join(parts)
    frame = scans.listing_frame(record)
    assert frame["time_left"].to_list() == [None, 1, None, 3, 2]
    assert frame["quality"].to_list() == [2, None, None, 1, 1]
    assert frame["level"].to_list()[:3] == [10, 10, None]
    assert frame["unit_buyout_ceil"].to_list() == [500, 150, 1, 36, None]
    rejected = scans.optional_out_of_range(record)
    assert rejected == {"time_left": 1, "quality": 1, "level": 1}
    measured = scan_details.availability(frame, scan_details.item_frame(record), rejected)
    assert measured["listing_out_of_range"] == rejected
    assert scans.optional_out_of_range(packed(scan("v2", FINISHED, [listing(1, 1, 1)]))) == {
        "time_left": 0, "quality": 0, "level": 0}


@pytest.mark.parametrize("level_type,required", [("REQ_LEVEL", 10), ("REQ_LEVEL_ABBR", 10),
                                                 ("ITEM_LEVEL", None), ("SKILL_ABBR", None)])
def test_required_level_accepts_modern_and_classic_level_types(level_type, required):
    record = rich()
    record["level_types"][0] = level_type
    frame = scans.listing_frame(record)
    assert frame["level_type"][0] == level_type
    assert frame["required_level"][0] == required


@pytest.mark.parametrize("items,match", [([{"item_id": 1}, {"item_id": 1}], "duplicate"),
                                        ([{"item_id": 0}], "invalid"), ([{"item_id": None}], "invalid"),
                                        ([{"item_id": 1, "max_stack_size": 0}], "invalid"),
                                        ([{"item_id": 1, "vendor_sell_copper": -1}], "invalid"),
                                        ([{"item_id": 1, "item_level": 1.5}], "integers"),
                                        ([{"item_id": True}], "integers"),
                                        ([{"item_id": 1, "class_id": True}], "integers"),
                                        (["bad"], "item tables")])
def test_bad_item_reference_is_rejected(items, match):
    with pytest.raises(ValueError, match=match):
        scan_details.item_frame({"schema_version": 3, "items": items})


@pytest.mark.parametrize("value", [-1, float("inf"), float("nan"), "12", True])
def test_duration_validation(value):
    with pytest.raises(ValueError, match="duration_seconds"):
        scan_details.duration({"duration_seconds": value})


def test_formats_1_2_3_preservation_dedup_and_new_nulls(tmp_path):
    old = scan("v1", FINISHED - 60, [listing(6538, 1, 10, "Old", link=MONKEY)])
    compact = packed(scan("v2", FINISHED - 30, [listing(6538, 1, 20, "Old")]))
    path = write_scans(tmp_path / "mixed.lua", old, compact, rich())
    # WoW upgrades the global version but keeps every individual scan's version.
    path.write_text(path.read_text().replace('["schema_version"] = 1,', '["schema_version"] = 3,', 1))
    config = addon_source(tmp_path / "data", path)
    preview = preview_scans(config, now=NOW)
    assert len(preview.new_ids) == 3 and not config["data_dir"].exists()
    manifest = import_scans(config, now=NOW)
    archive = config["data_dir"] / "bronze/my-scans" / manifest["bronze_file"]
    assert gzip.decompress(archive.read_bytes()) == path.read_bytes()
    measured = next(r for r in manifest["scans"] if r["scan_id"] == "rich")["availability"]
    assert measured["listing_total"] == 5
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        for key in scan_details.LISTING_DETAILS:
            assert db.execute(f"SELECT count({key}) FROM scan_listings WHERE scan_id IN ('v1','v2')").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM scan_items").fetchone()[0] == 2
        assert db.execute("SELECT format_version, duration_seconds, availability_json FROM addon_scans "
                          "WHERE scan_id='rich'").fetchone() == (3, 12.5, json.dumps(measured, sort_keys=True))
        assert db.execute("SELECT count(*) FROM market_snapshots WHERE item_id=6538 AND snapshot_id='my-scans:rich'"
                          ).fetchone()[0] == 3
        assert price_observations(db, config, "my-scans:rich", [6538, 2589]) == {
            2589: {"min_buyout": 36, "market_value": 36}}
        v = variants.identity(6538, MONKEY)[0]
        assert price_observations(db, config, "my-scans:rich", [6538], v)[6538]["min_buyout"] == 500
        assert listing_depth(db, config, "my-scans:rich", [6538])[6538] == {"listings": 0, "units": 0}
        assert listing_depth(db, config, "my-scans:rich", [6538], v)[6538] == {"listings": 1, "units": 1}
        assert listing_depth(db, config, "my-scans:rich", [6538], variant_state="unresolved")[6538]["units"] == 1
        assert browse(db, "my-scans:rich", config).height == 4
        # Variant names never label the item ID; only base (or legacy) rows supply item_names.
        assert db.execute("SELECT item_name FROM item_names WHERE item_id=6538").fetchall() == [("Old",)]
        assert db.execute("SELECT item_name FROM item_names WHERE item_id=2589").fetchall() == [("Linen Cloth",)]
        ranked = rank(db, "my-scans:rich", {**config, "auction_cut": 0.05, "min_discount": 0, "top_n": 10})
        assert {"variant_id", "variant_state"} <= set(ranked.columns)
    assert {r["outcome"] for r in import_scans(config, now=NOW)["scans"]} == {"duplicate"}
    changed = rich()
    changed["sellers"][0] = "ChangedTestSeller"
    with pytest.raises(ValueError, match="different content"):
        import_scans(config, write_scans(tmp_path / "changed.lua", changed), now=NOW)


def test_variants_compare_separately_and_legacy_matches_only_pure_base(tmp_path):
    config = addon_source(tmp_path / "data")
    newer = rich("new", FINISHED)
    newer["listings"][0] = newer["listings"][0].replace(":500:", ":700:")
    path = write_scans(tmp_path / "pair.lua", rich("old", FINISHED - 60), newer,
                       packed(scan("legacy", FINISHED - 120, [listing(6538, 1, 2, "Legacy"),
                                                               listing(2589, 20, 800, "Linen Cloth"),
                                                               listing(4306, 1, 50, "Silk Cloth")])),
                       packed(scan("legacy2", FINISHED - 90, [listing(6538, 1, 3, "Legacy"),
                                                               listing(2589, 20, 900, "Linen Cloth")])))
    import_scans(config, path, now=NOW)
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        diff = compare_scans(db, config, "old", "new")
        assert len(diff["items"]) == 4
        assert sum(r["changed"] for r in diff["items"]) == 1
        monkey = next(r for r in diff["items"] if r["variant_id"] == variants.identity(6538, MONKEY)[0])
        assert monkey["change"]["min_buyout"] == 200
        # Linen Cloth is base-only in the format-3 scan, so the legacy row compares with it.
        cross = compare_scans(db, config, "legacy", "new")
        assert [(r["item_id"], r["variant_state"]) for r in cross["items"]] == [(2589, "base")]
        assert cross["items"][0]["change"]["min_buyout"] == 36 - 40
        # The robe has variant/unresolved rows in format 3, so possibly pooled legacy suffixes stay apart.
        assert [(r["item_id"], r["variant_state"]) for r in cross["vanished"]] == [(4306, "legacy"),
                                                                                (6538, "legacy")]
        assert {r["variant_state"] for r in cross["new"]} == {"variant", "unresolved"}
        legacy = compare_scans(db, config, "legacy", "legacy2")
        assert {(r["item_id"], r["variant_state"]) for r in legacy["items"]} == {(2589, "legacy"),
                                                                                 (6538, "legacy")}
        assert price_observations(db, config, "my-scans:legacy", [6538], variant_state="unresolved") == {}
        assert listing_depth(db, config, "my-scans:legacy", [6538], variant_state="unresolved") == {
            6538: {"listings": 0, "units": 0}}
        assert price_observations(db, config, "my-scans:legacy", [6538])[6538]["min_buyout"] == 2


def test_partial_reference_data_is_stored_without_prices_and_bad_refs_fail_preview(tmp_path):
    config = addon_source(tmp_path / "data")
    partial = rich(status="stopped")
    path = write_scans(tmp_path / "partial.lua", partial)
    manifest = import_scans(config, path, now=NOW)
    assert manifest["scans"][0]["outcome"] == "partial (not priced)"
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        assert db.execute("SELECT count(*) FROM scan_items").fetchone()[0] == 2
        assert db.execute("SELECT count(*) FROM market_snapshots").fetchone()[0] == 0
    partial["items"].append({"item_id": 999})
    with pytest.raises(ValueError, match="no listing"):
        preview_scans(config, write_scans(tmp_path / "bad.lua", partial), now=NOW)


def test_migration_6_backup_replay_and_views(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    path = data / "brownstone.duckdb"
    with duckdb.connect(str(path)) as db:
        db.execute("CREATE TABLE schema_info (key VARCHAR PRIMARY KEY, value VARCHAR NOT NULL)")
        for target in range(1, 6):
            MIGRATIONS[target](db)
        db.execute("INSERT INTO schema_info VALUES ('schema_version','5')")
        db.execute("INSERT INTO market_snapshots (item_id, item_name, min_buyout) VALUES (6538, 'Old', 123)")
        before = db.execute("SELECT * FROM market_snapshots").fetchall()
    original = path.read_bytes()
    assert upgrade_database(data)
    assert (data / "brownstone.v5.backup.duckdb").read_bytes() == original
    with duckdb.connect(str(path)) as db, duckdb.connect(":memory:") as fresh:
        assert db.execute("SELECT * FROM market_snapshots").fetchall() == [(*before[0], None, None)]
        MIGRATIONS[6](db)
        ensure_schema(fresh)
        for table in ("market_snapshots", "scan_listings", "addon_scans", "scan_items"):
            assert db.execute(f"DESCRIBE {table}").fetchall() == fresh.execute(f"DESCRIBE {table}").fetchall()
        assert "variant_id" in [r[0] for r in db.execute("DESCRIBE named_market_snapshots").fetchall()]
    assert not upgrade_database(data)


@pytest.mark.parametrize("key", ["source_id", *MARKET_KEYS])
def test_variant_prices_depth_and_comparisons_enforce_every_scope_key(tmp_path, key):
    config = addon_source(tmp_path / "data")
    path = write_scans(tmp_path / "pair.lua", rich("old", FINISHED - 60), rich())
    import_scans(config, path, now=NOW)
    v = variants.identity(6538, MONKEY)[0]
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        assert price_observations(db, config, "my-scans:rich", [6538], v)[6538]["min_buyout"] == 500
        wrong = {**config, key: "another"}
        assert price_observations(db, wrong, "my-scans:rich", [6538], v) == {}
        assert listing_depth(db, wrong, "my-scans:rich", [6538], v) is None
        assert db.execute(f"SELECT DISTINCT {key} FROM scan_items").fetchall() == [(config[key],)]
        db.execute(f"UPDATE market_snapshots SET {key}='another' WHERE snapshot_id='my-scans:rich'")
        assert price_observations(db, config, "my-scans:rich", [6538], v) == {}
        diff = compare_scans(db, config, "old", "rich")
        assert any(r["later"]["min_buyout"] == 500 for r in diff["items"])
        db.execute(f"UPDATE scan_metrics SET {key}='another' WHERE snapshot_id='my-scans:rich'")
        diff = compare_scans(db, config, "old", "rich")
        assert not diff["items"] and len(diff["vanished"]) == 4
        db.execute(f"UPDATE scan_listings SET {key}='another' WHERE scan_id='rich'")
        rebuild_scan_metrics(db)
        assert listing_depth(db, config, "my-scans:rich", [6538], v) == {6538: {"listings": 0, "units": 0}}
        diff = compare_scans(db, config, "old", "rich")
        assert not diff["items"] and len(diff["vanished"]) == 4


def test_weighted_prices_never_include_other_variants_or_unresolved_stacks():
    record = rich()
    record["listings"].extend(["6538:10:6000:0:0:1:1:1:4:2:10:1:1",  # Monkey: 10 units @600
                               "6538:500:0:0:0:1:1:1:4:2:10:1:1"])  # No buyout: excluded from prices
    record["listing_count"] = record["reported_count"] = len(record["listings"])
    prices = scans.item_prices(scans.listing_frame(record))
    monkey = prices.filter(pl.col("variant_id") == variants.identity(6538, MONKEY)[0]).row(0, named=True)
    assert monkey["min_buyout"] == 500 and monkey["market_value"] == 600
    record["listings"][0] = record["listings"][0].replace(":500:", ":0:")
    record["listings"] = record["listings"][:5]
    record["listing_count"] = record["reported_count"] = 5
    prices = scans.item_prices(scans.listing_frame(record))
    monkey = prices.filter(pl.col("variant_id") == variants.identity(6538, MONKEY)[0]).row(0, named=True)
    assert monkey["min_buyout"] == monkey["market_value"] == 0


@pytest.mark.parametrize("table", ["sellers", "level_types", "links"])
def test_bad_indexed_tables_and_empty_rich_scan(table):
    record = rich()
    record[table] = [" "]
    with pytest.raises(ValueError, match="nonblank"):
        scans.listing_frame(record)
    record[table] = [123]
    with pytest.raises(ValueError, match="nonblank"):
        scans.listing_frame(record)
    empty = {**rich(), "listings": [], "items": {}, "listing_count": 0, "reported_count": 0,
             "sellers": {}, "links": {}, "level_types": {}}
    assert scans.listing_frame(empty).height == 0
    assert scans.item_prices(scans.listing_frame(empty)).height == 0
    assert scan_details.item_frame(empty).height == 0


def test_browse_and_scan_changes_show_variant_identity(tmp_path, monkeypatch):
    from test_scan_changes import app_for
    config = addon_source(tmp_path / "data")
    path = write_scans(tmp_path / "pair.lua", rich("old", FINISHED - 60), rich("new"))
    import_scans(config, path, now=NOW)
    app = app_for(config, monkeypatch)
    table = app.dataframe[0].value
    assert len(table) == 4 and set(table["Variant state"]) == {"variant", "base", "unresolved"}
    assert table["Variant"].notna().sum() == 2
    app.radio[0].set_value("Browse market").run()
    assert not app.exception
    assert len(app.dataframe[0].value) == 4
    assert "Variant" in app.dataframe[0].value.columns
