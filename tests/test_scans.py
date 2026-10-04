"""Addon scan import (STORY-010): parsing, stack pricing, dedup, partial scans, house checks, migration."""
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import polars as pl
import pytest

from brownstone import cli, scans
from brownstone.action_board import rank_recipes
from brownstone.config import build_source
from brownstone.crafting import load_recipe_catalog
from brownstone.pipeline import import_scans
from brownstone.storage import MIGRATIONS, latest_snapshot, price_observations, schema_version

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/brownstone_scan_sample.lua"
COMPLETE, STOPPED = "20261104T180000Z-3fa91c", "20261104T181500Z-0b72de"
NOW = datetime(2026, 11, 4, 18, 30, tzinfo=UTC)  # Shortly after the sample scans finished.
EVIDENCE = {"faction": "Alliance", "zone": "Stormwind City"}


def addon_source(data_dir, scan_path=FIXTURE, **overrides):
    shared = dict(data_dir=data_dir, max_age_hours=24, auction_cut=.05, min_discount=.2, top_n=20)
    entry = dict(source_id="my-scans", provider="addon", scan_path=scan_path, game_version="forever",
                 region="us", scope="house", server_type="roleplaying", faction="alliance",
                 rules_version="forever-beta-1.60", scan_evidence=dict(EVIDENCE))
    return build_source(shared, {**entry, **overrides})


def to_lua(value, indent=0):
    """Write a value the way WoW writes SavedVariables."""
    pad = "\t" * (indent + 1)
    if isinstance(value, dict):
        body = "".join(f'{pad}[{json.dumps(k)}] = {to_lua(v, indent + 1)},\n' for k, v in value.items())
        return "{\n" + body + "\t" * indent + "}"
    if isinstance(value, list):
        return "{\n" + "".join(f"{pad}{to_lua(v, indent + 1)},\n" for v in value) + "\t" * indent + "}"
    if isinstance(value, bool):
        return "true" if value else "false"
    return json.dumps(value)


def scan(scan_id, finished, listings, status="completed", reported=None, **extra):
    record = {"schema_version": 1, "scan_id": scan_id, "started_at": finished - 10, "finished_at": finished,
              "finished_at_utc": datetime.fromtimestamp(finished, UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "status": status, "listing_count": len(listings),
              "reported_count": len(listings) if reported is None else reported, "api": "modern",
              "faction": {"player": "Alliance", "neutral_source": "undetermined"},
              "house": {"npc_name": "Example Auctioneer", "zone": "Stormwind City"},
              "listings": listings, **extra}
    return record


def listing(item_id, quantity, buyout, name="", **extra):
    return {"item_id": item_id, "name": name, "quantity": quantity, "buyout": buyout, "min_bid": 0,
            "complete_info": True, **extra}


def write_scans(path, *records):
    path.write_text("BrownstoneScanDB = " + to_lua({"schema_version": 1, "scans": list(records)}) + "\n",
                    encoding="utf-8")
    return path


FINISHED = int(NOW.timestamp()) - 600


def test_parse_the_sample_file():
    complete, stopped = scans.read_saved_variables(FIXTURE.read_bytes())
    summary = scans.summarize(complete)
    assert (summary["scan_id"], summary["status"], summary["partial"]) == (COMPLETE, "completed", False)
    assert summary["finished_at"] == datetime(2026, 11, 4, 18, 1, 2, tzinfo=UTC)
    assert (summary["auctioneer"], summary["realm_name"], summary["label"]) == (
        "Example Auctioneer", "Classic Beta PvE 2", "sample roleplaying alliance")
    assert complete["listings"][0]["link"].startswith("|cnIQ1:|Hitem:2589")
    stopped_summary = scans.summarize(stopped)
    assert stopped_summary["partial"] and stopped_summary["stop_reason"] == "auction house window closed"
    assert stopped_summary["errors"] == ["auction house window closed"]


def test_parser_subset_escapes_and_errors():
    parsed = scans.parse_lua('A = {\n["s"] = "say \\"hi\\"\\\nnext\\65",\n[2] = -1.5e2,\n{},\n["n"] = nil,\n}\n')
    assert parsed == {"A": {"s": 'say "hi"\nnextA', 2: -150.0, 1: {}, "n": None}}
    assert scans.parse_lua("A = {\n1,\n2,\n}") == {"A": [1, 2]}
    for bad in ("A = {", "A = { print() }", "1", "A = {}\n}"):
        with pytest.raises(ValueError):
            scans.parse_lua(bad)
    with pytest.raises(ValueError, match="BrownstoneScanDB"):
        scans.read_saved_variables(b"OtherDB = {\n}\n")
    with pytest.raises(ValueError, match="schema_version"):
        scans.read_saved_variables(b'BrownstoneScanDB = {\n["schema_version"] = 2,\n}\n')


def test_stack_pricing_rounds_up_and_never_prices_missing_buyouts():
    listings = scans.listing_frame(scans.read_saved_variables(FIXTURE.read_bytes())[0])
    wool = listings.filter(pl.col("item_id") == 2592).row(0, named=True)
    # 250c for a stack of 3 is 83.33c each: no exact unit price, and a cost that rounds up.
    assert (wool["buyout"], wool["quantity"], wool["unit_buyout"], wool["unit_buyout_ceil"]) == (250, 3, None, 84)
    linen = listings.filter(pl.col("item_id") == 2589)
    assert linen["unit_buyout"].to_list() == linen["unit_buyout_ceil"].to_list() == [35, 38]
    sword = listings.filter(pl.col("item_id") == 8178).row(0, named=True)
    assert sword["buyout"] is None and sword["unit_buyout_ceil"] is None and sword["bid"] == 5000
    assert scans.nonexact_stacks(listings) == 1
    prices = {row["item_id"]: row for row in scans.item_prices(listings).iter_rows(named=True)}
    assert (prices[2592]["min_buyout"], prices[2592]["market_value"]) == (84, 84)
    assert (prices[8178]["min_buyout"], prices[8178]["market_value"]) == (0, 0)  # Unavailable, not free.
    assert prices[2578]["item_name"] == "Item 2578"  # The client had not loaded the name.
    assert all(type(prices[i][k]) is int for i in prices for k in ("min_buyout", "market_value"))


def test_market_value_is_the_quantity_weighted_lower_quartile():
    record = scan("q", FINISHED, [listing(1, 1, 10), listing(1, 10, 200), listing(1, 1, 1000),
                                  listing(2, 3, 10), listing(2, 1, 4), listing(2, 20, 2000, name="Two")])
    prices = scans.item_prices(scans.listing_frame(record)).rows_by_key("item_id", named=True)
    # Item 1: 12 units, nearest rank ceil(12 × 25%) = 3 lands in the 10-unit stack at 20c each.
    assert (prices[1][0]["min_buyout"], prices[1][0]["market_value"]) == (10, 20)
    # Item 2: 4 @ 4c (one exact, three rounded up from 3⅓c), then 20 @ 100c; rank ceil(24 × 25%) = 6.
    assert (prices[2][0]["min_buyout"], prices[2][0]["market_value"], prices[2][0]["item_name"]) == (4, 100, "Two")


@pytest.mark.parametrize("bad,match", [
    (listing(1, 2, 7, unit_buyout=3), "unit_buyout"),
    (listing(1, 3, 9, unit_buyout=4), "unit_buyout"),
    (listing(1, 0, 9), "quantity"),
    (listing(0, 1, 9), "item ID"),
    (listing(1, 1, -5), "negative"),
    (listing(1, 1, 9.5), "integer copper"),
])
def test_corrupt_listings_are_rejected(bad, match):
    with pytest.raises(ValueError, match=match):
        scans.listing_frame(scan("bad", FINISHED, [bad]))


def test_zero_buyout_means_no_buyout():
    frame = scans.listing_frame(scan("z", FINISHED, [listing(1, 1, 0)]))
    assert frame["buyout"][0] is None and frame["unit_buyout_ceil"][0] is None


def test_import_preserves_bytes_dedupes_and_labels_partial_scans(tmp_path):
    config = addon_source(tmp_path / "data")
    manifest = import_scans(config, now=NOW)
    bronze = tmp_path / "data/bronze/my-scans"
    assert (bronze / manifest["bronze_file"]).read_bytes() == FIXTURE.read_bytes()
    assert manifest["status"] == "complete" and manifest["scan_id"] == COMPLETE
    assert manifest["analytical_snapshot_id"] == f"my-scans:{COMPLETE}" and manifest["rows"] == 4
    assert manifest["updated_at"] == "2026-11-04T18:01:02+00:00" and manifest["freshness_basis"] == "upstream"
    outcomes = {s["scan_id"]: (s["outcome"], s["partial"]) for s in manifest["scans"]}
    assert outcomes == {COMPLETE: ("imported", False), STOPPED: ("partial (not priced)", True)}
    with duckdb.connect(str(tmp_path / "data/brownstone.duckdb")) as db:
        assert schema_version(db) == 3
        assert db.execute("SELECT scan_id, partial, priced, nonexact_stacks FROM addon_scans ORDER BY scan_id"
                          ).fetchall() == [(COMPLETE, False, True, 1), (STOPPED, True, False, 0)]
        assert db.execute("SELECT count(*), count(DISTINCT market_id) FROM scan_listings").fetchone() == (6, 1)
        # Only the complete scan feeds prices.
        assert db.execute("SELECT DISTINCT snapshot_id, market_id, updated_at FROM market_snapshots").fetchall() == [
            (f"my-scans:{COMPLETE}", "forever-us-roleplaying-alliance", datetime(2026, 11, 4, 18, 1, 2, tzinfo=UTC))]

    again = import_scans(config, now=NOW)
    assert {s["outcome"] for s in again["scans"]} == {"duplicate"}
    assert again["analytical_snapshot_id"] == manifest["analytical_snapshot_id"] and not again["new_observation"]
    assert again["bronze_file"] == manifest["bronze_file"]  # Identical bytes are stored once.
    assert len(list(bronze.glob("*.lua"))) == 1 and len(list(bronze.glob("*.json"))) == 2
    with duckdb.connect(str(tmp_path / "data/brownstone.duckdb")) as db:
        assert db.execute("SELECT count(*) FROM scan_listings").fetchone()[0] == 6
        assert db.execute("SELECT count(*) FROM market_snapshots").fetchone()[0] == 4


def test_a_file_without_a_complete_scan_leaves_prices_unchanged(tmp_path):
    config = addon_source(tmp_path / "data")
    manifest = import_scans(config, scan_ids=[STOPPED], now=NOW)
    assert manifest["status"] == "no_complete_scan"
    assert latest_snapshot(config) == (None, None, 0)
    with pytest.raises(ValueError, match="not in this file"):
        import_scans(config, scan_ids=["nope"], now=NOW)


def test_newest_scan_wins_regardless_of_import_order(tmp_path):
    newer = write_scans(tmp_path / "newer.lua", scan("new", FINISHED, [listing(1, 1, 50)]))
    older = write_scans(tmp_path / "older.lua", scan("old", FINISHED - 3600, [listing(1, 1, 90)]))
    config = addon_source(tmp_path / "data")
    import_scans(config, newer, now=NOW)
    import_scans(config, older, now=NOW)
    manifest, sid, count = latest_snapshot(config)
    assert (sid, count) == ("my-scans:new", 2)


@pytest.mark.parametrize("overrides,match", [
    (dict(faction="horde", scan_evidence={}), "player faction"),
    (dict(scan_evidence={"zone": "Orgrimmar"}), "zone"),
    (dict(scan_evidence={"auctioneer": "Auctioneer Fitch"}), "auctioneer"),
    (dict(scan_evidence={"realm": "Classic Beta PvP 1"}), "realm"),
    (dict(scan_evidence={"label": "neutral"}), "label"),
    (dict(faction="neutral", scan_evidence={}), "neutral"),
])
def test_house_mismatch_fails_before_anything_is_stored(tmp_path, overrides, match):
    config = addon_source(tmp_path / "data", **overrides)
    with pytest.raises(ValueError, match=match):
        import_scans(config, now=NOW)
    [failed] = [json.loads(p.read_text()) for p in (tmp_path / "data/bronze/my-scans").glob("*.json")]
    assert failed["status"] == "failed" and "configured market" in failed["error"]
    assert failed["market_id"] == config["market_id"]  # The configured market, never one from the scan.
    assert not (tmp_path / "data/brownstone.duckdb").exists()


def test_neutral_house_is_accepted_on_configured_auctioneer_evidence(tmp_path):
    config = addon_source(tmp_path / "data", faction="neutral",
                          scan_evidence={"auctioneer": "Example Auctioneer"})
    assert config["market_id"] == "forever-us-roleplaying-neutral"
    with pytest.raises(ValueError, match="auctioneer is None"):  # The stopped sample scan has no auctioneer.
        import_scans(config, now=NOW)
    assert import_scans(config, scan_ids=[COMPLETE], now=NOW)["status"] == "complete"


def test_changed_content_under_a_known_scan_id_and_future_scans_fail(tmp_path):
    config = addon_source(tmp_path / "data")
    import_scans(config, write_scans(tmp_path / "a.lua", scan("s", FINISHED, [listing(1, 1, 50)])), now=NOW)
    with pytest.raises(ValueError, match="different content"):
        import_scans(config, write_scans(tmp_path / "b.lua", scan("s", FINISHED, [listing(1, 1, 51)])), now=NOW)
    future = write_scans(tmp_path / "c.lua", scan("f", FINISHED + 7200, [listing(1, 1, 50)]))
    with pytest.raises(ValueError, match="future"):
        import_scans(config, future, now=NOW)
    # An old scan is allowed in; the board labels it stale rather than refusing it.
    old = write_scans(tmp_path / "d.lua", scan("o", FINISHED - 86400 * 7, [listing(1, 1, 50)]))
    assert import_scans(config, old, now=NOW)["status"] == "complete"


def test_migrates_an_existing_v2_database(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    with duckdb.connect(str(data / "brownstone.duckdb")) as db:
        db.execute("CREATE TABLE schema_info (key VARCHAR PRIMARY KEY, value VARCHAR NOT NULL)")
        MIGRATIONS[1](db)
        MIGRATIONS[2](db)
        db.execute("INSERT INTO schema_info VALUES ('schema_version', '2')")
        db.execute("""INSERT INTO market_snapshots (item_id, item_name, min_buyout, market_id, snapshot_id,
            source_id) VALUES (14047, 'Runecloth', 9500, 'classic-us-mankrik-alliance', 'old', 'classic')""")
    import_scans(addon_source(data), now=NOW)
    assert (data / "brownstone.v2.backup.duckdb").exists()
    with duckdb.connect(str(data / "brownstone.duckdb")) as db:
        assert schema_version(db) == 3
        assert db.execute("SELECT item_name, min_buyout FROM market_snapshots WHERE snapshot_id='old'"
                          ).fetchall() == [("Runecloth", 9500)]
        assert db.execute("SELECT count(*) FROM scan_listings").fetchone()[0] == 6
        MIGRATIONS[3](db)  # Idempotent.


def finished_now():
    return int(datetime.now(UTC).timestamp()) - 60


def forever_scan_file(folder, finished=FINISHED):
    runecloth, bolt, bag, leather, magenta, cerulean = 14047, 14048, 14046, 8170, 249430, 249409
    return write_scans(folder / "forever.lua", scan("rc", finished, [
        listing(runecloth, 20, 20000, "Runecloth"),          # 1,000c each
        listing(runecloth, 5, 5001, "Runecloth"),            # 1,000.2c: priced 1,001c
        listing(runecloth, 1, 900, "Runecloth"),             # cheapest single
        listing(bolt, 2, 12000, "Bolt of Runecloth"),        # 6,000c each
        listing(leather, 10, 5000, "Rugged Leather"),        # 500c each
        listing(magenta, 4, 2000, "Magenta Dye"),            # 500c each
        listing(cerulean, 2, 500, "Cerulean Dye"),           # 250c each
        listing(bag, 1, 60000, "Runecloth Bag"),
        listing(bag, 1, 80000, "Runecloth Bag"),
    ]))


def test_derived_prices_feed_the_forever_action_board_unchanged(tmp_path):
    runecloth, bag = 14047, 14046
    config = addon_source(tmp_path / "data", forever_scan_file(tmp_path))
    import_scans(config, now=NOW)
    catalog = load_recipe_catalog(ROOT / "config/forever-tailoring.toml")
    manifest, sid, _ = latest_snapshot(config)
    with duckdb.connect(str(tmp_path / "data/brownstone.duckdb"), read_only=True) as db:
        observations = price_observations(db, config, sid, sorted(catalog["items_by_id"]))
    # Runecloth: 26 units, rank ceil(6.5) = 7 is in the 1,000c stack.
    assert observations[runecloth] == {"min_buyout": 900, "market_value": 1000}
    assert observations[bag] == {"min_buyout": 60000, "market_value": 60000}
    board = rank_recipes(catalog, observations, config, manifest, now=NOW,
                         max_age_hours=config["max_age_hours"], auction_cut=config["auction_cut"])
    row = next(row for row in board["rows"] if row["output_item_id"] == bag)
    # Unlisted bags stay missing prices, never free.
    assert {r["action"] for r in board["rows"] if r is not row} == {"missing prices"}
    # Cautious: Bolt crafts at 5 × 1,000 = 5,000c (< 6,000c bought); 5 bolts + 2 leather + thread + dyes.
    dyes = 4 * 500 + 2 * 250
    assert row["craft_cost_copper"] == 5 * 5000 + 2 * 500 + 5000 + dyes
    assert row["net_revenue_copper"] == 57000 and row["action"] == "potential craft"
    assert row["profit_by_basis"] == {"cautious": 57000 - 33500, "listed": 57000 - (5 * 4500 + 1000 + 5000 + dyes)}
    assert not board["freshness"]["stale"] and board["freshness"]["basis"] == "upstream scan"


@pytest.mark.parametrize("overrides,match", [
    (dict(scan_path=""), "scan_path"),
    (dict(source_url="https://example.com/x"), "not source_url"),
    (dict(scan_evidence={"guild": "x"}), "unknown scan_evidence"),
    (dict(scan_evidence={"zone": ""}), "non-empty"),
    (dict(enabled="yes"), "enabled"),
])
def test_addon_source_validation(tmp_path, overrides, match):
    with pytest.raises(ValueError, match=match):
        addon_source(tmp_path, **overrides)


def test_tsm_sources_take_no_scan_settings(tmp_path):
    from conftest import make_source
    with pytest.raises(ValueError, match="addon sources only"):
        make_source(tmp_path, scan_path="x.lua")
    with pytest.raises(ValueError, match="HTTPS"):
        make_source(tmp_path, source_url="http://example.com/items.csv")


def test_cli_refuses_disabled_sources_and_imports_enabled_ones(tmp_path, monkeypatch, capsys):
    config = tmp_path / "config/market.toml"
    config.parent.mkdir()
    old = write_scans(tmp_path / "scan.lua", scan("cli", int(datetime.now(UTC).timestamp()) - 60, [listing(1, 1, 50)]))
    body = ('data_dir = "data"\nmax_age_hours = 1000000\nauction_cut = 0.05\nmin_discount = 0.2\ntop_n = 20\n'
            '[[sources]]\nsource_id = "mine"\nprovider = "addon"\nenabled = {enabled}\nscan_path = "scan.lua"\n'
            'game_version = "forever"\nregion = "us"\nscope = "house"\nserver_type = "normal"\nfaction = "alliance"\n')
    config.write_text(body.format(enabled="false"))
    monkeypatch.setattr(sys, "argv", ["brownstone", "--config", str(config), "--source", "mine"])
    with pytest.raises(SystemExit):
        cli.main()
    assert "disabled" in capsys.readouterr().err
    config.write_text(body.format(enabled="true"))
    cli.main()
    out = capsys.readouterr().out
    assert "Scan cli: completed, 1 listings, imported" in out and old.exists()


def test_local_overrides_keep_personal_settings_out_of_the_tracked_config(tmp_path):
    from brownstone.config import LOCAL_OVERRIDES, read_sources
    (tmp_path / "config").mkdir()
    tracked = tmp_path / "config/market.toml"
    local = tracked.with_name(LOCAL_OVERRIDES)
    tracked.write_text('data_dir = "data"\nmax_age_hours = 24\nauction_cut = 0.05\nmin_discount = 0.2\ntop_n = 20\n'
                       '[[sources]]\nsource_id = "mine"\nprovider = "addon"\nenabled = false\n'
                       'scan_path = "data/inbox/BrownstoneScan.lua"\ngame_version = "forever"\nregion = "us"\n'
                       'scope = "house"\nserver_type = "normal"\nfaction = "alliance"\n')
    [default] = read_sources(tracked, local)  # No local file: the tracked settings apply.
    assert not default["enabled"] and default["scan_path"] == (tmp_path / "data/inbox/BrownstoneScan.lua").resolve()
    local.write_text('[sources.mine]\nenabled = true\nscan_path = "/Games/WTF/Account/Me/SavedVariables/x.lua"\n')
    [mine] = read_sources(tracked, local)
    assert mine["enabled"] and mine["scan_path"] == Path("/Games/WTF/Account/Me/SavedVariables/x.lua").resolve()
    assert not read_sources(tracked)[0]["enabled"]  # Tests and tools that pass no local file are unaffected.
    local.write_text('[sources.someone-else]\nenabled = true\n')
    with pytest.raises(ValueError, match="unknown sources"):
        read_sources(tracked, local)
    local.write_text('[sources.mine]\nsource_id = "other"\n')
    with pytest.raises(ValueError, match="cannot change"):
        read_sources(tracked, local)
