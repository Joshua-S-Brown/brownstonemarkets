"""STORY-018: historical comparisons preserve scope, unavailable prices and scan identity."""
from pathlib import Path

import duckdb
import pytest
from conftest import make_source
from test_scans import FINISHED, NOW, addon_source, listing, scan, write_scans

from brownstone import recipe_catalogs as rc
from brownstone.markets import MARKET_KEYS
from brownstone.metrics import rebuild_scan_metrics
from brownstone.pipeline import import_scans
from brownstone.scan_changes import compare_scans, eligible_scans


def import_pair(tmp_path):
    config = addon_source(tmp_path / "data")
    path = write_scans(tmp_path / "pair.lua",
                       scan("old", FINISHED - 3600, [listing(1, 2, 200), listing(2, 3, 300),
                                                    listing(3, 1, 10), listing(5, 4, 0), listing(6, 1, 0)]),
                       scan("new", FINISHED, [listing(1, 2, 240), listing(2, 3, 300), listing(4, 5, 0),
                                              listing(5, 4, 0), listing(6, 1, 50)]))
    import_scans(config, path, now=NOW)
    return config, path


def test_diff_new_vanished_changed_unchanged_no_buyout_and_catalog_ids(tmp_path):
    config, _ = import_pair(tmp_path)
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        diff = compare_scans(db, config, "new", "old")  # Selection order cannot reverse chronology.
        assert diff["earlier"]["scan_id"] == "old" and diff["gap"].total_seconds() == 3600
        rows = {r["item_id"]: r for r in diff["items"]}
        assert rows[1]["earlier"] == {"min_buyout": 100, "market_value": 100, "listings": 1, "units": 2}
        assert rows[1]["change"] == {"min_buyout": 20, "market_value": 20, "listings": 0, "units": 0}
        assert rows[1]["changed"] and not rows[2]["changed"]
        assert not rows[5]["changed"] and rows[5]["later"]["min_buyout"] is None
        assert rows[6]["changed"] and rows[6]["change"]["min_buyout"] is None
        new = diff["new"][0]
        assert new["item_id"] == 4 and new["earlier"] is None
        assert new["later"] == {"min_buyout": None, "market_value": None, "listings": 1, "units": 5}
        assert all(v is None for v in new["change"].values())
        assert diff["vanished"][0]["item_id"] == 3 and diff["vanished"][0]["later"] is None
        filtered = compare_scans(db, config, "old", "new", [1, 4, 3])
        assert [r["item_id"] for r in filtered["items"]] == [1]
        assert len(filtered["new"]) == len(filtered["vanished"]) == 1
        assert compare_scans(db, config, "old", "new", [])["items"] == []
        for ids in (("old", "old"), ("old", "unknown")):
            with pytest.raises(ValueError, match="distinct complete"):
                compare_scans(db, config, *ids)


def test_choices_newest_distinct_complete_priced_scans_not_imports(tmp_path):
    config, path = import_pair(tmp_path)
    import_scans(config, path, now=NOW)
    extras = write_scans(tmp_path / "extra.lua",
                         scan("stopped", FINISHED + 30, [listing(1, 1, 10)], status="stopped"),
                         scan("partial", FINISHED + 60, [listing(1, 1, 10)], reported=2),
                         scan("third", FINISHED - 7200, [listing(1, 1, 10)]))
    import_scans(config, extras, now=NOW)
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        assert [s["scan_id"] for s in eligible_scans(db, config)] == ["new", "old", "third"]
        for sid in ("partial", "stopped"):
            with pytest.raises(ValueError):
                compare_scans(db, config, "old", sid)
        db.execute("UPDATE addon_scans SET priced=false WHERE scan_id='third'")
        assert len(eligible_scans(db, config)) == 2
        assert eligible_scans(db, make_source(tmp_path / "data")) == []
        with pytest.raises(ValueError):
            compare_scans(db, make_source(tmp_path / "data"), "old", "new")


@pytest.mark.parametrize("key", ["source_id", *MARKET_KEYS])
def test_every_scope_field_required_for_choices_prices_and_listings(tmp_path, key):
    config, _ = import_pair(tmp_path)
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        wrong = {**config, key: "another"}
        assert eligible_scans(db, wrong) == []
        with pytest.raises(ValueError):
            compare_scans(db, wrong, "old", "new")
        db.execute(f"UPDATE scan_metrics SET {key}='another' WHERE snapshot_id='my-scans:new'")
        diff = compare_scans(db, config, "old", "new")
        assert not diff["items"] and len(diff["vanished"]) == 5
        db.execute(f"UPDATE scan_listings SET {key}='another' WHERE scan_id='new'")
        diff = compare_scans(db, config, "old", "new")
        assert not diff["items"] and not diff["new"] and len(diff["vanished"]) == 5
        db.execute(f"UPDATE addon_scans SET {key}='another' WHERE scan_id='new'")
        assert [s["scan_id"] for s in eligible_scans(db, config)] == ["old"]


@pytest.mark.parametrize("table,id_column", [("scan_listings", "snapshot_id"),
                                             ("scan_listings", "scan_id"), ("scan_metrics", "snapshot_id")])
def test_exact_snapshot_and_scan_ids_required(tmp_path, table, id_column):
    config, _ = import_pair(tmp_path)
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        db.execute(f"UPDATE {table} SET {id_column}='wrong' WHERE snapshot_id='my-scans:new'")
        if table == "scan_listings":
            rebuild_scan_metrics(db)
        diff = compare_scans(db, config, "old", "new")
        if table == "scan_listings":
            assert not diff["items"] and not diff["new"]
        else:
            assert not diff["items"] and len(diff["vanished"]) == 5


def test_sql_aggregates_supply_and_preserves_historical_weighted_prices(tmp_path):
    config = addon_source(tmp_path / "data")
    path = write_scans(tmp_path / "weighted.lua",
                       scan("old", FINISHED - 60, [listing(1, 1, 10), listing(1, 10, 200), listing(1, 1, 1000)]),
                       scan("new", FINISHED, [listing(1, 3, 10), listing(1, 1, 4), listing(1, 20, 2000)]))
    import_scans(config, path, now=NOW)
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        row = compare_scans(db, config, "old", "new")["items"][0]
        assert row["earlier"] == {"min_buyout": 10, "market_value": 20, "listings": 3, "units": 12}
        assert row["later"] == {"min_buyout": 4, "market_value": 100, "listings": 3, "units": 24}
        assert row["change"]["units"] == 12


def app_for(config, monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr("brownstone.config.read_sources", lambda *args: [config])
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run()
    at.radio[0].set_value("Scan changes").run()
    assert not at.exception
    return at


def classic_only_item():
    """An item in a real Classic catalog and in no Forever catalog, whichever professions have been added."""
    items = {"classic": set(), "forever": set()}
    for entry in rc.find_catalogs(rc.CONFIG_DIR):
        items[entry["selection"]["game_version"]] |= {item["item_id"] for item in entry["catalog"]["items"]}
    return min(items["classic"] - items["forever"], default=999_999_999)  # Else an item in no catalog.


def test_scan_changes_app_selects_two_scans_filters_compatible_catalogs_and_labels(tmp_path, monkeypatch):
    config, _ = import_pair(tmp_path)
    extra = write_scans(tmp_path / "third.lua", scan("third", FINISHED - 7200, [listing(1, 1, 50)]))
    import_scans(config, extra, now=NOW)
    # Real compatible catalog includes Linen Cloth (2589). Item 1 deliberately shares its name.
    classic_only = classic_only_item()
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        db.execute("UPDATE market_snapshots SET item_name='Linen Cloth' WHERE item_id=1")
        for table in ("market_snapshots", "scan_listings"):
            db.execute(f"UPDATE {table} SET item_id=2589 WHERE item_id=2")
            db.execute(f"UPDATE {table} SET item_id={classic_only} WHERE item_id=6")
        rebuild_scan_metrics(db)
    at = app_for(config, monkeypatch)
    first = next(w for w in at.selectbox if w.label == "First scan")
    second = next(w for w in at.selectbox if w.label == "Second scan")
    assert first.value == "old" and second.value == "new"
    assert any("Gap: 1:00:00" in c.value and "UTC" in c.value for c in at.caption)
    assert any("2026-11-04 17:20:00 UTC" in c.value and "2026-11-04 18:20:00 UTC" in c.value
               for c in at.caption)
    assert any("source" in c.value and "market" in c.value for c in at.caption)
    table = at.dataframe[0].value.set_index("Item ID")
    assert table.loc[1, "Change Min buyout (g)"] == .002
    assert table.loc[5, "Earlier Min buyout (g)"] == "no buyout"
    assert table.loc[5, "Earlier Market value (g)"] == "no market value"
    assert len(at.warning) <= 1  # Only the later scan may warn that prices are stale.
    new = at.dataframe[1].value.iloc[0]
    vanished = at.dataframe[2].value.iloc[0]
    assert new["Earlier Units"] == "not listed" and vanished["Later Units"] == "not listed"
    assert new["Change Units"] is None
    first.set_value("third").run()
    assert not at.exception
    assert any("third" in c.value and "Earlier:" in c.value for c in at.caption)
    at.checkbox[0].check().run()
    assert not at.exception
    assert set(at.dataframe[0].value["Item ID"]) == {2589}  # Names and incompatible catalog IDs never match.
    monkeypatch.setattr("views.scan_changes.compatible_catalogs", lambda *args: [])
    at.run()
    assert not at.exception and not at.dataframe
    assert any("No compatible recipe catalogs" in i.value for i in at.info)


@pytest.mark.parametrize("provider", ["tsm", "addon"])
def test_scan_changes_app_explains_unavailable_comparisons(tmp_path, monkeypatch, provider):
    config = make_source(tmp_path / "data") if provider == "tsm" else addon_source(tmp_path / "data")
    if provider == "addon":
        path = write_scans(tmp_path / "one.lua", scan("one", FINISHED, [listing(1, 1, 100)]))
        import_scans(config, path, now=NOW)
    at = app_for(config, monkeypatch)
    assert not at.dataframe
    assert any("addon source" in i.value if provider == "tsm" else "at least two" in i.value for i in at.info)


def test_scan_changes_without_database_and_empty_groups(tmp_path, monkeypatch):
    config = addon_source(tmp_path / "data")
    at = app_for(config, monkeypatch)
    assert any("at least two" in i.value for i in at.info)
    assert not at.dataframe


def test_diff_does_not_mix_another_observer_and_counts_supply_only_changes(tmp_path):
    config = addon_source(tmp_path / "data")
    path = write_scans(tmp_path / "supply.lua",
                       scan("old", FINISHED - 60, [listing(1, 1, 100)]),
                       scan("new", FINISHED, [listing(1, 1, 100), listing(1, 3, 0)]))
    import_scans(config, path, now=NOW)
    other = addon_source(tmp_path / "data", source_id="other")
    foreign = write_scans(tmp_path / "foreign.lua", scan("foreign", FINISHED + 30, [listing(2, 900, 9000)]))
    import_scans(other, foreign, now=NOW)
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        assert [s["scan_id"] for s in eligible_scans(db, config)] == ["new", "old"]
        diff = compare_scans(db, config, "old", "new")
        assert not diff["new"] and not diff["vanished"]
        assert diff["items"][0]["changed"]
        assert diff["items"][0]["change"] == {"min_buyout": 0, "market_value": 0, "listings": 1, "units": 3}
