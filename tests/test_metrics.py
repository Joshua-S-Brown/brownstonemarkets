"""STORY-024: semantic facts, privacy, scope, deterministic rebuild and migration safety."""
import hashlib

import duckdb
import polars as pl
import pytest
from test_scan_v3 import BASE, MONKEY, rich
from test_scans import FINISHED, NOW, addon_source, listing, packed, scan, write_scans

from brownstone import metrics, scans, variants
from brownstone.markets import MARKET_KEYS
from brownstone.pipeline import import_scans
from brownstone.storage import MIGRATIONS, ensure_schema, schema_version, upgrade_database


def frame(rows):
    return scans.listing_frame(scan("s", FINISHED, [listing(1, quantity, buyout) for quantity, buyout in rows]))


@pytest.mark.parametrize("rows,expected", [
    ([(1, 100)], (100, 100, 100, 100)),
    ([(1, 10), (1, 20)], (10, 10, 10, 10)),  # Even median is lower middle.
    ([(1, 10), (1, 20), (1, 30)], (10, 10, 10, 20)),
    ([(1, 10), (9, 180)], (10, 10, 20, 20)),  # Exact rank boundary at 10%.
    ([(1, 10), (10, 200)], (10, 20, 20, 20)),
    ([(3, 30), (1, 200), (4, 1200)], (10, 10, 10, 200)),
    ([(3, 10), (1, 5)], (4, 4, 4, 4)),  # Rounded-up unit copper.
    ([(20, 0), (2, 200)], (100, 100, 100, 100)),
    ([(20, 0)], (None, None, None, None)),
])
def test_weighted_nearest_rank_prices(rows, expected):
    listings = frame(rows)
    row = metrics.calculate_metrics(listings).row(0, named=True)
    assert tuple(row[c] for c in metrics.PRICE_COLUMNS) == expected
    assert row["units"] == sum(q for q, _ in rows)
    assert row["listings"] == len(rows)
    assert row["largest_stack_units"] == max(q for q, _ in rows)
    assert row["priced_units"] == sum(q for q, price in rows if price > 0)
    old_shape = scans.item_prices(listings).row(0, named=True)
    assert old_shape["min_buyout"] == (expected[0] or 0)
    assert old_shape["market_value"] == (expected[2] or 0)


@pytest.mark.parametrize("count", [5, 6, 19, 20, 21, 100, 101])
def test_percentiles_match_expanded_units_oracle(count):
    quantities = [(i % 4 + 1, (i % 4 + 1) * (i % 7 + 1)) for i in range(count)]
    expanded = sorted(price // q for q, price in quantities for _ in range(q))
    result = metrics.calculate_metrics(frame(quantities)).row(0, named=True)
    for p, column in ((10, "unit_buyout_p10"), (25, "unit_buyout_p25"), (50, "unit_buyout_median")):
        assert result[column] == expanded[(p * len(expanded) + 99) // 100 - 1]
    shuffled = frame(list(reversed(quantities)))
    assert metrics.calculate_metrics(shuffled).equals(metrics.calculate_metrics(frame(quantities)))


def import_records(tmp_path, *records):
    config = addon_source(tmp_path / "data")
    import_scans(config, write_scans(tmp_path / "scan.lua", *records), now=NOW)
    return config


def test_supply_threshold_shares_and_seller_coverage(tmp_path):
    record = rich()
    # Four base listings: known seller 20+10 units, another known seller 5, missing seller 15.
    record["listings"] += ["2589:5:200:0:0:1:0:2:1:1:1:1:3", "2589:15:0:0:0:1:0:0:1:1:1:1:3"]
    record["listing_count"] = record["reported_count"] = len(record["listings"])
    config = import_records(tmp_path, record)
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        rows = metrics.read_scan_metrics(db, config, "my-scans:rich")
        row = next(r for r in rows if r["item_id"] == 2589)
        assert (row["units"], row["listings"], row["priced_units"]) == (50, 4, 25)
        assert row["largest_stack_share"] == {"numerator": 20, "denominator": 50}
        assert row["seller_count"] == 2
        assert row["top_seller_share"] == {"numerator": 30, "denominator": 35}
        assert row["seller_unit_coverage"] == {"numerator": 35, "denominator": 50}
        assert row["seller_listing_coverage"] == {"numerator": 3, "denominator": 4}
        unknown = next(r for r in rows if r["variant_state"] == "unresolved")
        assert unknown["seller_count"] is None and unknown["top_seller_share"] is None
        assert unknown["seller_unit_coverage"] == {"numerator": 0, "denominator": 1}
        assert "seller" not in [c[0] for c in db.execute("SELECT * FROM scan_metrics LIMIT 0").description]
        assert all("TestSeller" not in str(r) for r in rows)
        for threshold, expected in ((36, 0), (37, 20), (40, 20), (41, 25)):
            assert metrics.units_below_price(db, config, "my-scans:rich", 2589, threshold,
                                             variant_state="base") == expected
        assert metrics.units_below_price(db, config, "my-scans:rich", 2589, 100) == 0  # Exact legacy only.
        assert metrics.units_below_price(db, config, "my-scans:rich", 999, 100) == 0
        assert metrics.units_below_price(db, config, "unknown", 2589, 100) is None
        for threshold in (0, -1, 1.5, True):
            with pytest.raises(ValueError, match="positive integer"):
                metrics.units_below_price(db, config, "my-scans:rich", 2589, threshold)


@pytest.mark.parametrize("format_version", [1, 2])
def test_legacy_seller_measures_null_and_scan_exclusions(tmp_path, format_version):
    complete = scan("complete", FINISHED, [listing(1, 2, 0)])
    if format_version == 2:
        complete = packed(complete)
    config = import_records(tmp_path, complete,
                            scan("stopped", FINISHED, [listing(1, 99, 1)], status="stopped"),
                            scan("partial", FINISHED, [listing(1, 99, 1)], reported=2),
                            scan("empty", FINISHED, []))
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        row = metrics.read_scan_metrics(db, config, "my-scans:complete")[0]
        assert row["variant_state"] is None
        assert all(row[c] is None for c in metrics.PRICE_COLUMNS)
        assert all(row[c] is None for c in ("seller_known_listings", "seller_known_units", "seller_count",
                                            "top_seller_units", "seller_unit_coverage", "seller_listing_coverage"))
        assert db.execute("SELECT count(*) FROM scan_metrics").fetchone() == (1,)
        for scan_id in ("stopped", "partial", "empty"):
            assert metrics.read_scan_metrics(db, config, f"my-scans:{scan_id}") is None
            assert metrics.units_below_price(db, config, f"my-scans:{scan_id}", 1, 100) is None


def test_variants_base_unresolved_and_legacy_never_pool(tmp_path):
    record = rich()
    # Add resolved base identity for the same item ID as two variants and unresolved evidence.
    record["links"].append(BASE.replace("2589", "6538"))
    record["listings"].append("6538:7:7000:0:0:1:0:1:1:1:1:1:4")
    record["listing_count"] = record["reported_count"] = len(record["listings"])
    config = import_records(tmp_path, record, scan("legacy", FINISHED, [listing(6538, 999, 999)]))
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        rows = [r for r in metrics.read_scan_metrics(db, config, "my-scans:rich") if r["item_id"] == 6538]
        assert sorted(r["units"] for r in rows) == [1, 1, 2, 7]
        assert {r["variant_state"] for r in rows} == {"base", "variant", "unresolved"}
        v = variants.identity(6538, MONKEY)[0]
        assert metrics.units_below_price(db, config, "my-scans:rich", 6538, 501, v, "variant") == 1
        legacy = metrics.read_scan_metrics(db, config, "my-scans:legacy")[0]
        assert legacy["units"] == 999 and legacy["variant_state"] is None
        before = db.execute("SELECT * FROM scan_metrics ORDER BY ALL").fetchall()
        assert metrics.rebuild_scan_metrics(db) == 6
        assert metrics.rebuild_scan_metrics(db) == 6
        assert db.execute("SELECT * FROM scan_metrics ORDER BY ALL").fetchall() == before
        with pytest.raises(duckdb.ConstraintException):
            db.execute("INSERT INTO scan_metrics SELECT * FROM scan_metrics WHERE variant_state IS NULL")


@pytest.mark.parametrize("key", ["source_id", *MARKET_KEYS, "snapshot_id", "scan_id"])
def test_metric_scope_reads_and_rebuild_parent_match_every_key(tmp_path, key):
    config = import_records(tmp_path, scan("s", FINISHED, [listing(1, 10, 100)]))
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        if key not in ("snapshot_id", "scan_id"):
            assert metrics.read_scan_metrics(db, {**config, key: "wrong"}, "my-scans:s") is None
            assert metrics.units_below_price(db, {**config, key: "wrong"}, "my-scans:s", 1, 100) is None
        db.execute(f"UPDATE scan_metrics SET {key}='wrong'")
        assert metrics.read_scan_metrics(db, config, "my-scans:s") == []
        assert metrics.rebuild_scan_metrics(db) == 1
        db.execute(f"UPDATE scan_listings SET {key}='wrong'")
        assert metrics.rebuild_scan_metrics(db) == 0
        assert metrics.units_below_price(db, config, "my-scans:s", 1, 100) == 0


def test_rebuild_atomicity_and_initialization_retry(tmp_path, monkeypatch):
    config = import_records(tmp_path, rich())
    path = config["data_dir"] / "brownstone.duckdb"
    with duckdb.connect(str(path)) as db:
        before = db.execute("SELECT * FROM scan_metrics ORDER BY ALL").fetchall()
        insert = metrics._insert_metrics
        db.execute("UPDATE scan_listings SET quantity=quantity+1")
        def fail(*args, **kwargs):
            insert(*args, **kwargs)
            raise RuntimeError("interrupted backfill")
        monkeypatch.setattr(metrics, "_insert_metrics", fail)
        with pytest.raises(RuntimeError, match="interrupted"):
            metrics.rebuild_scan_metrics(db)
        assert db.execute("SELECT * FROM scan_metrics ORDER BY ALL").fetchall() == before
        assert db.execute("SELECT value FROM schema_info WHERE key='metrics_version'").fetchone() == ('1',)
        db.execute("UPDATE scan_listings SET quantity=quantity-1")
        db.execute("DELETE FROM schema_info WHERE key='metrics_version'")
    with pytest.raises(RuntimeError, match="interrupted"):
        upgrade_database(config["data_dir"])
    monkeypatch.setattr(metrics, "_insert_metrics", insert)
    assert not upgrade_database(config["data_dir"])
    with duckdb.connect(str(path)) as db:
        assert db.execute("SELECT * FROM scan_metrics ORDER BY ALL").fetchall() == before
        assert db.execute("SELECT value FROM schema_info WHERE key='metrics_version'").fetchone() == ('1',)
        # No work on a current initialized database, even if the calculation is unavailable.
        monkeypatch.setattr(metrics, "_insert_metrics", fail)
        ensure_schema(db)


def test_schema6_backup_frozen_ddl_backfill_replay_and_layout(tmp_path):
    config = import_records(tmp_path, rich(), scan("legacy", FINISHED, [listing(1, 20, 200)]))
    path = config["data_dir"] / "brownstone.duckdb"
    with duckdb.connect(str(path)) as db:
        db.execute("DROP TABLE scan_metrics")
        db.execute("DELETE FROM schema_info WHERE key='metrics_version'")
        db.execute("UPDATE schema_info SET value='6' WHERE key='schema_version'")
        observations = {table: db.execute(f"SELECT * FROM {table} ORDER BY ALL").fetchall()
                        for table in ("market_snapshots", "addon_scans", "scan_listings", "scan_items")}
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert upgrade_database(config["data_dir"])
    backup = path.with_name("brownstone.v6.backup.duckdb")
    assert hashlib.sha256(backup.read_bytes()).hexdigest() == digest
    with duckdb.connect(str(path)) as db, duckdb.connect() as fresh:
        assert schema_version(db) == 8
        assert db.execute("SELECT count(*) FROM scan_metrics").fetchone() == (5,)
        assert all(db.execute(f"SELECT * FROM {table} ORDER BY ALL").fetchall() == rows
                   for table, rows in observations.items())
        before = db.execute("SELECT * FROM scan_metrics ORDER BY ALL").fetchall()
        MIGRATIONS[7](db)
        ensure_schema(db)
        assert db.execute("SELECT * FROM scan_metrics ORDER BY ALL").fetchall() == before
        ensure_schema(fresh)
        assert db.execute("DESCRIBE scan_metrics").fetchall() == fresh.execute("DESCRIBE scan_metrics").fetchall()
        db.execute("DROP TABLE scan_metrics")
        MIGRATIONS[7](db)
        assert db.execute("SELECT count(*) FROM scan_metrics").fetchone() == (0,)  # DDL has no calculator.
        assert metrics.rebuild_scan_metrics(db) == 5
    assert not upgrade_database(config["data_dir"])
    assert hashlib.sha256(backup.read_bytes()).hexdigest() == digest


def test_same_scan_and_item_in_different_sources_stay_independent(tmp_path):
    config = import_records(tmp_path, scan("s", FINISHED, [listing(1, 10, 100)]))
    other = addon_source(config["data_dir"], source_id="other")
    import_scans(other, write_scans(tmp_path / "other.lua", scan("s", FINISHED, [listing(1, 25, 5000)])), now=NOW)
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        assert metrics.read_scan_metrics(db, config, "my-scans:s")[0]["min_buyout"] == 10
        assert metrics.read_scan_metrics(db, other, "other:s")[0]["min_buyout"] == 200
        assert metrics.read_scan_metrics(db, config, "other:s") is None
        assert metrics.read_scan_metrics(db, {**config, "provider": "tsm"}, "my-scans:s") is None
        assert metrics.rebuild_scan_metrics(db) == 2
        assert metrics.read_scan_metrics(db, config, "my-scans:s")[0]["units"] == 10
        assert metrics.read_scan_metrics(db, other, "other:s")[0]["units"] == 25


def test_import_metric_failure_rolls_back_scan_listings_and_prices(tmp_path, monkeypatch):
    config = import_records(tmp_path, scan("first", FINISHED, [listing(1, 10, 100)]))
    store = metrics.store_scan_metrics
    def fail_after_metrics(*args):
        store(*args)
        raise RuntimeError("metric write failure")
    monkeypatch.setattr(metrics, "store_scan_metrics", fail_after_metrics)
    with pytest.raises(RuntimeError, match="metric write failure"):
        import_scans(config, write_scans(tmp_path / "new.lua", rich()), now=NOW)
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        for table in ("addon_scans", "scan_listings", "scan_metrics"):
            assert db.execute(f"SELECT count(*) FROM {table} WHERE scan_id='rich'").fetchone() == (0,)
        assert db.execute("SELECT count(*) FROM market_snapshots WHERE snapshot_id='my-scans:rich'").fetchone() == (0,)
        assert metrics.read_scan_metrics(db, config, "my-scans:first")[0]["units"] == 10


def test_calculator_never_drops_scope_or_accepts_partial_scope():
    raw = frame([(10, 100)])
    with pytest.raises(ValueError, match="every source, market, scan and snapshot"):
        metrics.calculate_metrics(raw.with_columns(pl.lit("observer").alias("source_id")))
    scoped = raw.with_columns(*[pl.lit("same").alias(k) for k in metrics.SCAN_KEYS])
    other = scoped.with_columns(pl.lit("other").alias("source_id"), pl.lit(200, pl.Int64).alias("unit_buyout_ceil"))
    result = metrics.calculate_metrics(pl.concat([scoped, other]))
    assert result.height == 2
    assert result["min_buyout"].to_list() == [200, 10]
    assert result["units"].to_list() == [10, 10]
