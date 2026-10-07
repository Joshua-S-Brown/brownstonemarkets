"""Character snapshots use the existing file review and collection contract, offline."""
import copy
import gzip
import sys
from datetime import UTC, datetime

import duckdb
import pytest
from test_addon import ROOT, client, python_value
from test_scans import FINISHED, NOW, addon_source, listing, scan, to_lua

from brownstone import character_snapshots as holdings
from brownstone import cli, storage
from brownstone.pipeline import StalePreviewError, import_guidance, import_scans, preview_scans
from brownstone.scan_inputs import import_inputs, preview_inputs


def snapshot(sid="char:bags:1", kind="bags", character="Alice", **extra):
    return dict(snapshot_id=sid, character=character, realm="Beta", faction="Alliance", kind=kind,
                captured_at=FINISHED,
                captured_at_utc=datetime.fromtimestamp(FINISHED, UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                addon_version="0.5.0", event="PLAYER_LOGOUT" if kind == "bags" else "BANKFRAME_OPENED",
                gold_copper=12345, containers=[dict(container_id=0, size=2)],
                slots=[dict(container_id=0, slot=1, item_id=2589, count=3, item_link="exact |Hitem:2589|h")], **extra)


def write(path, snapshots, scans=None, **extra):
    path.write_text("BrownstoneScanDB = " + to_lua(dict(schema_version=5, scans=scans or [],
                                                       snapshots=snapshots, **extra)) + "\n")
    return path


def test_snapshots_only_preview_import_archive_counts_and_unknown_bank(tmp_path):
    path = write(tmp_path / "own.lua", [snapshot(), snapshot("bob", character="Bob")])
    config = addon_source(tmp_path / "data", path)
    raw = path.read_bytes()
    preview = preview_scans(config, now=NOW)
    assert not config["data_dir"].exists()
    assert preview.new_snapshot_ids == ["char:bags:1", "bob"] and preview.new_ids == []
    assert holdings.preview_rows(preview, "mac")[0]["Gold"] == 1.2345
    manifest = import_scans(config, now=NOW, reviewed=preview, scan_ids=[])
    assert manifest["fully_imported"] and manifest["status"] == "no_complete_scan"
    assert len(manifest["snapshots"]) == 2 and "current login" in import_guidance(manifest)
    archive = config["data_dir"] / "bronze/my-scans" / manifest["bronze_file"]
    assert gzip.decompress(archive.read_bytes()) == raw == path.read_bytes()
    rows = holdings.latest_rows(config)
    assert [r["Character"] for r in rows] == ["Alice", "Bob"]
    assert all(r["Bank (UTC)"] == "bank unknown" and r["Bank items"] is None for r in rows)
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        assert db.execute("SELECT count(*) FROM character_slots").fetchone()[0] == 2
        assert db.execute("SELECT count(*) FROM market_snapshots").fetchone()[0] == 0
        assert db.execute("SELECT gold_copper, machine FROM character_snapshots").fetchall() == [(12345, "mac")] * 2
    assert not preview_scans(config, now=NOW).new_snapshot_ids
    repeated = import_scans(config, now=NOW)
    assert all(r["outcome"] == "duplicate" for r in repeated["snapshots"])
    assert repeated["bronze_file"] == manifest["bronze_file"]
    # Old snapshots never authorize clearing: the latest scan may still be in game memory.
    assert import_guidance(repeated).startswith("Nothing new: all 0 scan(s) and 2 snapshot(s)")


def test_snapshot_only_cli_import_reports_no_scan_warning(tmp_path, monkeypatch, capsys):
    r = snapshot()
    r.update(captured_at=1700000000)
    r.pop("captured_at_utc")
    config = addon_source(tmp_path / "data", write(tmp_path / "own.lua", [r]))
    monkeypatch.setattr(cli, "read_sources", lambda *args: [config])
    monkeypatch.setattr(sys, "argv", ["brownstone"])
    cli.main()
    out = capsys.readouterr().out
    assert "imported" in out and "No complete scan" not in out and "current login" in out


def test_mixed_overlapping_drops_dedup_machine_conflict_and_full_import(tmp_path):
    folder = tmp_path / "drops"
    folder.mkdir()
    own = write(tmp_path / "own.lua", [snapshot()], [scan("s", FINISHED, [listing(2589, 3, 99)])])
    drop = write(folder / "windows-pc-20261007T004900Z-BrownstoneScan.lua",
                 [snapshot(), snapshot("bank", "bank")])
    config = addon_source(tmp_path / "data", own, drop_folder=folder)
    preview = preview_inputs(config, NOW)
    results = import_inputs(config, preview, now=NOW)
    assert [r["status"] for r in results] == ["imported", "imported"]
    assert [r["outcome"] for r in results[1]["manifest"]["snapshots"]] == ["duplicate", "imported"]
    assert all(f.fully_imported for f in preview_inputs(config, NOW).files)
    assert import_inputs(config, preview_inputs(config, NOW), now=NOW) == []
    rows = holdings.latest_rows(config)
    assert rows[0]["Bags machine"] == "mac" and rows[0]["Bank machine"] == "windows-pc"
    altered = snapshot()
    altered["gold_copper"] += 1
    write(drop, [altered])
    bad = preview_inputs(config, NOW)
    assert "conflict" in bad.files[1].error and not bad.files[1].fully_imported
    with pytest.raises(ValueError, match="conflict"):
        import_scans(config, drop, now=NOW)
    assert holdings.latest_rows(config) == rows


def test_other_house_and_market_scope_are_not_pooled(tmp_path):
    foreign = snapshot("foreign")
    foreign["faction"] = "Horde"
    path = write(tmp_path / "own.lua", [snapshot(), foreign])
    config = addon_source(tmp_path / "data", path)
    preview = preview_scans(config, now=NOW)
    assert preview.new_snapshot_ids == ["char:bags:1"] and preview.snapshot_mismatches[1]
    manifest = import_scans(config, now=NOW, reviewed=preview)
    assert manifest["other_house"] == 1 and not manifest["fully_imported"]
    assert "another auction house" in import_guidance(manifest)
    assert len(holdings.latest_rows(config)) == 1
    other = config.copy()
    other["environment"] = "beta"
    assert holdings.latest_rows(other) == []
    with pytest.raises(ValueError, match="different market"):
        preview_scans(other, now=NOW)
    realm = config.copy()
    realm["scan_evidence"] = {"realm": "Another realm"}
    assert holdings.check_house(snapshot(), realm)


@pytest.mark.parametrize("change", ["bytes", "known"])
def test_snapshot_review_changes_fail_before_archive(tmp_path, change):
    path = write(tmp_path / "own.lua", [snapshot()])
    config = addon_source(tmp_path / "data", path)
    reviewed = preview_scans(config, now=NOW)
    if change == "bytes":
        path.write_bytes(path.read_bytes() + b"\n")
    else:
        import_scans(config, now=NOW)
    before = {str(p): p.read_bytes() for p in tmp_path.rglob("*.json")}
    with pytest.raises(StalePreviewError):
        import_scans(config, now=NOW, reviewed=reviewed)
    assert before == {str(p): p.read_bytes() for p in tmp_path.rglob("*.json")}


@pytest.mark.parametrize("mutation", [
    {"character": ""}, {"kind": "mail"}, {"gold_copper": -1}, {"gold_copper": 1.2}, {"gold_copper": True},
    {"captured_at": int(NOW.timestamp()) + 1000, "captured_at_utc": None},
    {"slots": [dict(container_id=0, slot=0)]}, {"slots": [dict(container_id=0, slot=1, count=0)]},
    {"slots": [dict(container_id=0, slot=1, item_link=7)]}, {"slots": [dict(container_id=0, slot=1, item_id=0)]},
    {"slots": [dict(container_id=0, slot=1)] * 2}, {"containers": [7]},
    {"containers": [dict(size=2)]}, {"containers": [dict(container_id=0, size=-1)]},
])
def test_invalid_evidence_preview_writes_nothing(tmp_path, mutation):
    r = snapshot()
    r.update(mutation)
    config = addon_source(tmp_path / "data", write(tmp_path / "own.lua", [r]))
    with pytest.raises(ValueError):
        preview_scans(config, now=NOW)
    assert not config["data_dir"].exists()


def test_missing_slot_values_remain_null_and_reported_zero_gold_survives(tmp_path):
    r = snapshot()
    r.update(gold_copper=0, slots=[dict(container_id=-2, slot=1, item_link="raw")],
             containers=[dict(container_id=-2)])
    path = write(tmp_path / "own.lua", [r])
    config = addon_source(tmp_path / "data", path)
    preview = preview_scans(config, now=NOW)
    assert preview.snapshot_summaries[0]["units"] is None
    assert not preview.snapshot_summaries[0]["complete"]
    import_scans(config, now=NOW)
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        assert db.execute("SELECT item_id, count, item_link FROM character_slots").fetchone() == (None, None, "raw")
    assert holdings.latest_rows(config)[0]["Gold"] == 0


def test_migration_9_backup_idempotent_and_old_file_import(tmp_path):
    path = tmp_path / "brownstone.duckdb"
    with duckdb.connect(str(path)) as db:
        for version in range(1, 10):
            storage.MIGRATIONS[version](db)
        db.execute("CREATE TABLE schema_info (key VARCHAR PRIMARY KEY, value VARCHAR)")
        db.execute("INSERT INTO schema_info VALUES ('schema_version', '9')")
    assert storage.upgrade_database(tmp_path)
    with duckdb.connect(str(path)) as db:
        assert storage.schema_version(db) == 11
        storage.MIGRATIONS[10](db)
        assert db.execute("SELECT count(*) FROM character_snapshots").fetchone()[0] == 0
    assert list(tmp_path.glob("brownstone.v9.backup.duckdb"))
    assert not storage.upgrade_database(tmp_path)
    from test_scans import FIXTURE
    assert import_scans(addon_source(tmp_path, FIXTURE), now=NOW)["status"] == "complete"


def test_snapshot_cli_preview_and_import(tmp_path, monkeypatch, capsys):
    path = write(tmp_path / "own.lua", [snapshot()])
    config = addon_source(tmp_path / "data", path)
    monkeypatch.setattr(cli, "read_sources", lambda *args: [config])
    monkeypatch.setattr(sys, "argv", ["brownstone", "--preview"])
    # CLI's real date precedes this fixture; move its evidence into the past.
    r = snapshot()
    r.update(captured_at=1700000000)
    r.pop("captured_at_utc")
    write(path, [r])
    cli.main()
    assert "Alice" in capsys.readouterr().out and not config["data_dir"].exists()
    monkeypatch.setattr(sys, "argv", ["brownstone"])
    cli.main()
    assert "Snapshot char:bags:1: imported" in capsys.readouterr().out


def capture_client(modern=True):
    lua, g = client()
    lua.execute('''
        epoch = 1793816400
        function time() return epoch end
        function UnitName(unit) return unit == "player" and "Alice" or "Auctioneer" end
        function GetMoney() return 12345 end
        NUM_BAG_SLOTS, NUM_BANKBAGSLOTS, KEYRING_CONTAINER = 4, 2, -2
        NUM_TOTAL_EQUIPPED_BAG_SLOTS, REAGENTBANK_CONTAINER = 5, -3
        Enum = { BagIndex = { Backpack = 0, Bag_1 = 1, Bag_2 = 2, Bag_3 = 3, Bag_4 = 4,
            ReagentBag = 5, Bank = -1, BankBag_1 = 6, BankBag_2 = 7, Reagentbank = -3 } }
        C_Container = {
            GetContainerNumSlots = function(id) return 2 end,
            GetContainerItemInfo = function(id, slot)
                if slot == 2 then return nil end
                return { itemID = 2589, stackCount = 3, hyperlink = "raw " .. id } end }
    ''')
    if not modern:
        # Classic layout: bank bags follow the four bags even if the shared Enum names a ReagentBag 5.
        lua.execute('''
            NUM_TOTAL_EQUIPPED_BAG_SLOTS, REAGENTBANK_CONTAINER = nil, nil
            C_Container = nil
            function GetContainerNumSlots(id) return 2 end
            function GetContainerItemInfo(id, slot) if slot == 1 then return "texture", 3 end end
            function GetContainerItemID(id, slot) if slot == 1 then return 2589 end end
            function GetContainerItemLink(id, slot) if slot == 1 then return "raw " .. id end end
        ''')
    g.mainFrame.scripts.OnEvent(g.mainFrame, "PLAYER_ENTERING_WORLD", True, False)
    return lua, g


@pytest.mark.parametrize("modern", [True, False])
def test_lua_all_reported_containers_empty_slots_logout_and_bank_open_close(tmp_path, modern):
    _, g = capture_client(modern)
    event = g.mainFrame.scripts.OnEvent
    g.SlashCmdList.BROWNSTONESCAN("status")
    assert any("bank unknown" in m for m in g.messages.values())
    event(g.mainFrame, "BANKFRAME_CLOSED")
    assert len(g.BrownstoneScanDB.snapshots) == 0
    event(g.mainFrame, "BANKFRAME_OPENED")
    event(g.mainFrame, "BANKFRAME_CLOSED")
    event(g.mainFrame, "PLAYER_LOGOUT")
    records = python_value(g.BrownstoneScanDB.snapshots)
    assert [r["event"] for r in records] == ["BANKFRAME_OPENED", "BANKFRAME_CLOSED", "PLAYER_LOGOUT"]
    bank, bags = ({-3, -1, 6, 7}, {-2, 0, 1, 2, 3, 4, 5}) if modern else ({-1, 5, 6}, {-2, 0, 1, 2, 3, 4})
    assert {s["container_id"] for s in records[0]["slots"]} == bank
    assert {s["container_id"] for s in records[2]["slots"]} == bags
    assert records[2]["container_layout"]["equipped_bags"] == (5 if modern else 4)
    assert all(s["slot"] == 1 and s["count"] == 3 for r in records for s in r["slots"])
    assert records[2]["gold_copper"] == 12345 and "gold_copper" not in records[0]
    assert len({r["snapshot_id"] for r in records}) == 3
    config = addon_source(tmp_path / "data", write(tmp_path / "own.lua", records))
    import_scans(config, now=NOW)
    assert holdings.latest_rows(config)[0]["Bank slots"] == len(bank)
    assert g.requests == 0 and g.mainFrame.scripts.OnUpdate is None


def test_lua_clear_preserves_login_across_reload_and_two_characters():
    lua, g = capture_client()
    event = g.mainFrame.scripts.OnEvent
    event(g.mainFrame, "BANKFRAME_OPENED")
    first = python_value(g.BrownstoneScanDB.snapshots[1])
    g.epoch += 100
    # Reload the actual addon while retaining the account-wide SavedVariables.
    lua.execute((ROOT / "addon/BrownstoneScan/BrownstoneScan.lua").read_text())
    event = g.mainFrame.scripts.OnEvent
    event(g.mainFrame, "ADDON_LOADED", "BrownstoneScan")
    event(g.mainFrame, "PLAYER_ENTERING_WORLD", False, True)
    event(g.mainFrame, "PLAYER_ENTERING_WORLD", False, False)
    event(g.mainFrame, "PLAYER_ENTERING_WORLD")  # a later loading screen on a client without flags
    g.SlashCmdList.BROWNSTONESCAN("clear")
    assert python_value(g.BrownstoneScanDB.snapshots[1]) == first
    assert any("0 character snapshot(s) from before this login" in m for m in g.messages.values())
    event(g.mainFrame, "PLAYER_LOGOUT")
    lua.execute('function UnitName() return "Bob" end')
    g.epoch += 100
    event(g.mainFrame, "PLAYER_ENTERING_WORLD", True, False)
    event(g.mainFrame, "PLAYER_LOGOUT")
    assert len(g.BrownstoneScanDB.snapshots) == 3
    g.SlashCmdList.BROWNSTONESCAN("clear all")
    assert [r["character"] for r in python_value(g.BrownstoneScanDB.snapshots)] == ["Bob"]
    g.SlashCmdList.BROWNSTONESCAN("status")
    assert any("bank unknown" in m for m in g.messages.values())


def test_lua_unknown_login_and_missing_apis_retain_evidence_without_zero():
    lua, g = capture_client()
    event = g.mainFrame.scripts.OnEvent
    event(g.mainFrame, "PLAYER_LOGOUT")
    g.epoch += 100
    lua.execute((ROOT / "addon/BrownstoneScan/BrownstoneScan.lua").read_text())
    event = g.mainFrame.scripts.OnEvent
    event(g.mainFrame, "ADDON_LOADED", "BrownstoneScan")
    event(g.mainFrame, "PLAYER_ENTERING_WORLD")
    g.SlashCmdList.BROWNSTONESCAN("clear")
    assert len(g.BrownstoneScanDB.snapshots) == 1
    assert any("every character snapshot was kept" in m for m in g.messages.values())
    lua.execute('GetMoney = nil; C_Container.GetContainerNumSlots = function() error("missing") end')
    event(g.mainFrame, "PLAYER_LOGOUT")
    record = python_value(g.BrownstoneScanDB.snapshots[2])
    assert "gold_copper" not in record and all("size" not in c for c in record["containers"])
    assert record["slots"] == {}
    assert holdings.summarize(record, NOW)["complete"] is False


def test_lua_rejected_character_event_is_guarded_and_recorded():
    lua, g = capture_client()
    lua.execute('''
        originalCreateFrame = CreateFrame
        CreateFrame = function(...)
            local f = originalCreateFrame(...)
            function f:RegisterEvent(event) if event == "PLAYER_LOGOUT" then error("unknown") end end
            return f
        end
    ''')
    lua.execute((ROOT / "addon/BrownstoneScan/BrownstoneScan.lua").read_text())
    event = g.mainFrame.scripts.OnEvent
    event(g.mainFrame, "ADDON_LOADED", "BrownstoneScan")
    event(g.mainFrame, "PLAYER_ENTERING_WORLD", False, True)
    event(g.mainFrame, "BANKFRAME_OPENED")
    r = python_value(g.BrownstoneScanDB.snapshots[1])
    assert r["rejected_events"] == ["PLAYER_LOGOUT"]
    assert r["fired_events"]["BANKFRAME_OPENED"] == 1


def test_duplicate_snapshot_id_and_empty_file_are_errors(tmp_path):
    config = addon_source(tmp_path / "data", write(tmp_path / "own.lua", [snapshot(), copy.deepcopy(snapshot())]))
    with pytest.raises(ValueError, match="Duplicate snapshot_id"):
        preview_scans(config, now=NOW)
    write(config["scan_path"], [])
    with pytest.raises(ValueError, match="no scans"):
        import_scans(config, now=NOW)


def test_lua_failed_slot_reads_are_unknown_not_empty():
    lua, g = capture_client()
    lua.execute('C_Container.GetContainerItemInfo = function() error("not available") end')
    g.mainFrame.scripts.OnEvent(g.mainFrame, "PLAYER_LOGOUT")
    r = python_value(g.BrownstoneScanDB.snapshots[1])
    assert all(c["slots_readable"] is False for c in r["containers"])
    assert not holdings.summarize(r, NOW)["complete"]


def test_classic_market_realm_slug_but_explicit_evidence_is_exact(tmp_path):
    config = addon_source(tmp_path, game_version="classic", server_type="", realm="mankrik")
    r = snapshot()
    r["realm"] = "Mankrik"
    assert holdings.check_house(r, config) == []
    config["scan_evidence"] = {"realm": "mankrik"}
    assert holdings.check_house(r, config)


def test_snapshot_only_selection_with_unselected_other_house_scan(tmp_path):
    foreign = scan("horde", FINISHED, [listing(1, 1, 50)])
    foreign["faction"]["player"] = "Horde"
    path = write(tmp_path / "own.lua", [snapshot()], [foreign])
    config = addon_source(tmp_path / "data", path)
    preview = preview_scans(config, now=NOW)
    manifest = import_scans(config, now=NOW, reviewed=preview, scan_ids=[])
    assert len(manifest["snapshots"]) == 1 and manifest["scans"] == []
    assert not manifest["fully_imported"]


def test_same_second_snapshot_sequence_orders_latest_numerically(tmp_path):
    old, newer = snapshot("id:9"), snapshot("id:10")
    old.update(sequence=9, gold_copper=900)
    newer.update(sequence=10, gold_copper=1000)
    config = addon_source(tmp_path / "data", write(tmp_path / "own.lua", [newer, old]))
    import_scans(config, now=NOW)
    assert holdings.latest_rows(config)[0]["Gold"] == 0.1


def test_snapshot_import_final_writer_state_recheck_prevents_archive(tmp_path, monkeypatch):
    from brownstone import pipeline
    config = addon_source(tmp_path / "data", write(tmp_path / "own.lua", [snapshot()]))
    reviewed = preview_scans(config, now=NOW)
    original = holdings.states

    def changed(source, records, db=None):
        return [{"snapshot_sha256": "unexpected concurrent import"}] if db is not None else original(source, records)

    monkeypatch.setattr(holdings, "states", changed)
    with pytest.raises(StalePreviewError, match="Imported non-scan records changed"):
        pipeline.import_scans(config, now=NOW, reviewed=reviewed)
    assert not list(config["data_dir"].rglob("*.json"))


def test_snapshot_drop_review_and_batch_conflicts(tmp_path):
    folder = tmp_path / "drop"
    folder.mkdir()
    own = write(tmp_path / "own.lua", [snapshot()])
    altered = snapshot()
    altered["gold_copper"] += 1
    drop = write(folder / "windows-pc-20261007T004900Z-BrownstoneScan.lua", [altered])
    config = addon_source(tmp_path / "data", own, drop_folder=folder)
    reviewed = preview_inputs(config, NOW)
    results = import_inputs(config, reviewed, now=NOW)
    assert results[0]["status"] == "imported" and "conflict" in results[1]["error"]
    assert not preview_inputs(config, NOW).files[1].fully_imported
    write(drop, [snapshot()])
    reviewed = preview_inputs(config, NOW)
    extra = snapshot("new")
    write(own, [snapshot(), extra])
    with pytest.raises(StalePreviewError):
        import_inputs(config, reviewed, now=NOW)


@pytest.mark.parametrize("bad_id", [[], {}, 7, ""])
def test_invalid_snapshot_ids_fail_as_file_errors(tmp_path, bad_id):
    r = snapshot()
    r["snapshot_id"] = bad_id
    folder = tmp_path / "drop"
    folder.mkdir()
    path = write(tmp_path / "own.lua", [r])
    config = addon_source(tmp_path / "data", path, drop_folder=folder)
    assert "snapshot_id" in preview_inputs(config, NOW).files[0].error
    assert not config["data_dir"].exists()


def test_missing_item_id_does_not_claim_zero_items_and_utc_uses_known_time(tmp_path):
    r = snapshot()
    r["slots"][0].pop("item_id")
    r.pop("captured_at_utc")
    config = addon_source(tmp_path / "data", write(tmp_path / "own.lua", [r]))
    preview = preview_scans(config, now=NOW)
    assert preview.snapshot_summaries[0]["items"] is None
    import_scans(config, now=NOW)
    row = holdings.latest_rows(config)[0]
    assert row["Bags items"] is None and row["Bags slots"] == 1
    assert row["Bags (UTC)"] == "2026-11-04T18:20:00Z"


def test_lua_contradictory_login_flags_never_authorize_pruning():
    _, g = capture_client()
    event = g.mainFrame.scripts.OnEvent
    event(g.mainFrame, "PLAYER_LOGOUT")
    g.epoch += 100
    event(g.mainFrame, "PLAYER_ENTERING_WORLD", True, True)
    g.SlashCmdList.BROWNSTONESCAN("clear all")
    assert len(g.BrownstoneScanDB.snapshots) == 1
