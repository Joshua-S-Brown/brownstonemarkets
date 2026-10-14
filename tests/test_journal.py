"""Execute the real journal under Lua 5.1 and exercise the shared offline import contract."""
import copy
import gzip
import json
import re
import sys
from datetime import UTC, datetime

import duckdb
import pytest
from test_addon import ROOT, python_value
from test_character_snapshots import capture_client, snapshot
from test_scans import FINISHED, NOW, addon_source, to_lua

from brownstone import cli, journal, storage
from brownstone.pipeline import StalePreviewError, import_guidance, import_scans, preview_scans
from brownstone.scan_inputs import InputFile, import_inputs, preview_inputs


def entry(eid="e1", **extra):
    return dict(entry_id=eid, character="Alice", realm="Beta", faction="Alliance", family="money",
                event="PLAYER_MONEY", addon_version="0.6.0", captured_at=FINISHED,
                captured_at_utc=datetime.fromtimestamp(FINISHED, UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                session_time=12.5, sequence=1, arguments={"n": 3, 1: "raw", 3: False}, **extra)


def write(path, entries, snapshots=None):
    path.write_text("BrownstoneScanDB = " + to_lua(dict(schema_version=6, scans=[], journal=entries,
                                                       snapshots=snapshots or [])))
    return path


def journal_client():
    lua, g = capture_client()
    # Install all candidate functions before reloading the addon, as the game installs its API.
    lua.execute('''
        actionCalls = 0
        function hooksecurefunc(target, name, callback)
            local original = target[name]
            target[name] = function(...)
                original(...)
                callback(...)
            end
        end
    ''')
    specs = re.findall(r'\{ "(\w+)", "(\w+)"(?:, "(\w+)")? \}',
                       (ROOT / "addon/BrownstoneScan/BrownstoneScan.lua").read_text().split("local journalHooks = {")[1]
                       .split("-- Explicit count")[0])
    for name, _family, namespace in specs:
        target = namespace + "." if namespace else ""
        if namespace:
            lua.execute(f"{namespace} = {namespace} or {{}}")
        lua.execute(f"{target}{name} = function(...) actionCalls = actionCalls + 1 end")
    lua.execute('''
        money, quantity = 12345, 3
        function GetMoney() return money end
        C_Container.GetContainerItemInfo = function(id, slot)
            if slot == 1 then return { itemID=2589, stackCount=quantity } end end
        function GetInboxNumItems() return 1, 1 end
        function GetInboxHeaderInfo() return nil, nil, "Sender", "Sold", 123, 0, 29, 1, false end
        function GetInboxInvoiceInfo() return "seller", "Linen", "Buyer", 1, 123, 5, 6 end
        function GetInboxItem() return "Linen", 2589, nil, 3 end
        function GetInboxItemLink() return "|Hitem:2589|h" end
        function GetSendMailItem() return "Linen", 2589, nil, 3 end
        function GetSendMailItemLink() return "raw attachment" end
        function GetSendMailMoney() return 10 end
        function GetSendMailCOD() return 0 end
    ''')
    lua.execute((ROOT / "addon/BrownstoneScan/BrownstoneScan.lua").read_text())
    g.mainFrame.scripts.OnEvent(g.mainFrame, "ADDON_LOADED", "BrownstoneScan")
    g.mainFrame.scripts.OnEvent(g.mainFrame, "PLAYER_ENTERING_WORLD", False, True)
    return lua, g, specs


def fire(g, name, *args):
    g.mainFrame.scripts.OnEvent(g.mainFrame, name, *args)


def entries(g):
    return python_value(g.BrownstoneScanDB.journal)


def test_lua_money_bag_changes_no_change_windows_unknown_and_shared_sequence(tmp_path):
    lua, g, _ = journal_client()
    before_chat = len(g.messages)
    fire(g, "BAG_UPDATE_DELAYED")
    assert len(entries(g)) == 0
    g.money = 12000
    fire(g, "PLAYER_MONEY")
    assert entries(g)[-1]["before_copper"] == 12345 and entries(g)[-1]["after_copper"] == 12000
    fire(g, "MERCHANT_SHOW")
    g.quantity = 1
    fire(g, "BAG_UPDATE_DELAYED")
    assert entries(g)[-1]["item_changes"] == {2589: -14}
    assert entries(g)[-1]["windows"]["merchant"] is True
    g.quantity = 4
    fire(g, "BAG_UPDATE_DELAYED")
    assert entries(g)[-1]["item_changes"] == {2589: 21}
    fire(g, "BAG_UPDATE_DELAYED")
    fire(g, "PLAYER_LOGOUT")
    assert g.BrownstoneScanDB.snapshots[1].sequence == entries(g)[-1]["sequence"] + 1
    lua.execute('GetMoney = nil; C_Container.GetContainerNumSlots = nil')
    fire(g, "PLAYER_MONEY")
    assert "after_copper" not in entries(g)[-1]
    fire(g, "BAG_UPDATE_DELAYED")
    assert entries(g)[-1]["baseline_missing"] is True and "item_changes" not in entries(g)[-1]
    assert len(g.messages) == before_chat and g.actionCalls == 0
    path = write(tmp_path / "actual.lua", entries(g), python_value(g.BrownstoneScanDB.snapshots))
    import_scans(addon_source(tmp_path / "data", path), now=NOW)


def test_lua_mailbox_dedup_invoices_raw_headers_and_send_draft():
    lua, g, _ = journal_client()
    fire(g, "MAIL_SHOW")
    first = entries(g)[-1]
    fire(g, "MAIL_INBOX_UPDATE")
    assert len(entries(g)) == 1
    assert first["inbox"]["messages"][0]["header"][3] == "Sender"
    assert first["inbox"]["messages"][0]["invoice"][7] == 6
    lua.execute('GetInboxHeaderInfo = function() return nil, nil, "Other", "Expired", nil end')
    fire(g, "MAIL_INBOX_UPDATE")
    assert len(entries(g)) == 2
    fire(g, "MAIL_SEND_INFO_UPDATE")
    g.SendMail("Bob", "raw subject", None)
    sent = entries(g)[-1]
    assert sent["arguments"]["n"] == 3 and sent["arguments"][1] == "Bob" and 3 not in sent["arguments"]
    assert sent["draft"]["money_copper"] == 10 and sent["draft"]["items"][0]["info"][4] == 3
    assert sent["draft_is_last_observed"] is True
    fire(g, "MAIL_CLOSED")
    fire(g, "MAIL_SHOW")  # Same inbox still deduplicates within this session.
    assert entries(g)[-1]["event"] == "MAIL_CLOSED"


def test_lua_every_candidate_hook_records_arguments_and_never_calls_actions():
    lua, g, specs = journal_client()
    fire(g, "MERCHANT_SHOW")
    baseline = g.actionCalls
    for name, family, namespace in specs:
        target = g[namespace] if namespace else g
        target[name](7, None, "raw", False)
        r = entries(g)[-1]
        assert r["event"] == (namespace + "." if namespace else "") + name
        assert r["family"] == family and r["arguments"] == {"n": 4, 1: 7, 3: "raw", 4: False}
    assert g.actionCalls - baseline == len(specs)
    lua.execute('C_TradeSkillUI.CraftRecipe({ recipeID=9, nested={count=2} }, nil)')
    assert entries(g)[-1]["arguments"][1]["nested"]["count"] == 2


def test_lua_all_event_families_own_spellcasts_and_loot():
    lua, g, _ = journal_client()
    fire(g, "UNIT_SPELLCAST_SUCCEEDED", "party1", "cast", 1)
    fire(g, "CHAT_MSG_LOOT", "other")
    assert not entries(g)
    for event in ("AUCTION_HOUSE_PURCHASE_COMPLETED", "MAIL_SEND_SUCCESS", "MERCHANT_SHOW",
                  "TRADE_SKILL_SHOW", "LOOT_OPENED"):
        fire(g, event, "player", None, 10)
    assert {r["family"] for r in entries(g)} == {"auction", "mail", "vendor", "craft", "loot"}
    args = ["own"] + [None] * 10 + [g.UnitGUID("player")]
    fire(g, "CHAT_MSG_LOOT", *args)
    assert entries(g)[-1]["arguments"]["n"] == 12
    lua.execute('UnitGUID = nil')
    fire(g, "CHAT_MSG_LOOT", *args)
    assert len(entries(g)) == 6


def test_lua_loot_sources_zone_and_missing_apis():
    lua, g, _ = journal_client()
    lua.execute('''
        function GetRealZoneText() return "Elwynn Forest" end
        C_Map = { GetBestMapForUnit = function(unit) return 1429 end }
        function GetNumLootItems() return 2 end
        function GetLootSlotLink(slot) return "|Hitem:" .. (slot == 1 and 2770 or 2589) .. "|h" end
        function GetLootSourceInfo(slot)
            if slot == 1 then return "GameObject-0-1-2-3-1731-0001", 2 end
            return "Creature-0-1-2-3-299-0002", 1, "Creature-0-1-2-3-299-0003", 1
        end
    ''')
    fire(g, "LOOT_OPENED", 0)
    r = entries(g)[-1]
    assert r["loot_slot_count"] == 2 and r["zone"] == {"zone": "Elwynn Forest", "subzone": "Trade District",
                                                        "map_id": 1429}
    first, second = r["loot_slots"]
    assert first == {"slot": 1, "link": "|Hitem:2770|h", "sources": {"n": 2, 1: "GameObject-0-1-2-3-1731-0001", 2: 2}}
    assert second["sources"]["n"] == 4 and second["sources"][3].startswith("Creature-")
    args = ["own"] + [None] * 10 + [g.UnitGUID("player")]
    fire(g, "CHAT_MSG_LOOT", *args)
    assert entries(g)[-1]["zone"]["map_id"] == 1429 and "loot_slots" not in entries(g)[-1]
    # Missing or failing APIs record nothing for that value, never a guess, and never break the entry.
    lua.execute('''
        GetLootSourceInfo = function() error("unavailable") end
        GetNumLootItems = function() return 1 end
        C_Map = nil
    ''')
    fire(g, "LOOT_OPENED", 0)
    r = entries(g)[-1]
    assert r["loot_slots"] == [{"slot": 1, "link": "|Hitem:2770|h"}] and "map_id" not in r["zone"]
    lua.execute('GetNumLootItems = nil')
    fire(g, "LOOT_OPENED", 0)
    assert entries(g)[-1].get("loot_slots") in ({}, [], None) and "loot_slot_count" not in entries(g)[-1]


def test_lua_trainer_services_levels_costs_and_filters():
    lua, g, _ = journal_client()
    lua.execute('''
        function GetNumTrainerServices() return 2 end
        function GetTrainerServiceInfo(i)
            if i == 1 then return "Journeyman Tailoring", "Journeyman", "unavailable" end
            return "Brown Linen Pants", nil, "available"
        end
        function GetTrainerServiceLevelReq(i) return i == 1 and 10 or 0 end
        function GetTrainerServiceSkillReq(i) if i == 1 then return "Tailoring", 50, false end end
        function GetTrainerServiceCost(i) return i == 1 and 500 or 50 end
        function GetTrainerServiceTypeFilter(kind) return kind ~= "used" end
    ''')
    fire(g, "TRAINER_SHOW")
    r = entries(g)[-1]
    assert r["event"] == "TRAINER_SHOW" and r["trainer_service_count"] == 2
    tier = r["trainer_services"][0]
    assert tier["info"] == {"n": 3, 1: "Journeyman Tailoring", 2: "Journeyman", 3: "unavailable"}
    assert tier["level_required"] == {"n": 1, 1: 10} and tier["cost"] == {"n": 1, 1: 500}
    assert tier["skill_required"] == {"n": 3, 1: "Tailoring", 2: 50, 3: False}
    assert r["trainer_services"][1]["skill_required"] == {"n": 0}
    assert r["trainer_filters"] == {"available": True, "unavailable": True, "used": False}
    fire(g, "TRAINER_CLOSED")
    assert "trainer_services" not in entries(g)[-1]


def test_lua_trainer_window_and_junk_button_are_vendor_evidence():
    _, g, _ = journal_client()
    fire(g, "TRAINER_SHOW")
    g.BuyTrainerService(3)
    g.money = 12000
    fire(g, "PLAYER_MONEY")
    fire(g, "TRAINER_CLOSED")
    fire(g, "MERCHANT_SHOW")
    g.C_MerchantFrame.SellAllJunkItems()
    rs = entries(g)
    assert [r["event"] for r in rs] == ["TRAINER_SHOW", "BuyTrainerService", "PLAYER_MONEY", "TRAINER_CLOSED",
                                        "MERCHANT_SHOW", "C_MerchantFrame.SellAllJunkItems"]
    assert {r["family"] for r in rs} == {"vendor", "money"}
    assert rs[2]["windows"]["trainer"] is True and rs[4]["windows"]["trainer"] is False


def test_lua_spellcasts_only_succeeded_crafts_and_refresh_events_only_counted():
    lua, g, _ = journal_client()
    for event in ("UNIT_SPELLCAST_START", "UNIT_SPELLCAST_FAILED", "UNIT_SPELLCAST_INTERRUPTED"):
        fire(g, event, "player", "cast", 1)
    fire(g, "UNIT_SPELLCAST_SUCCEEDED", "player", "combat", 133)  # No crafting window: combat or other spell.
    for event in ("MERCHANT_UPDATE", "TRADE_SKILL_UPDATE", "CRAFT_UPDATE", "AUCTION_ITEM_LIST_UPDATE"):
        fire(g, event)
    assert not entries(g)
    fire(g, "TRADE_SKILL_SHOW")
    fire(g, "UNIT_SPELLCAST_SUCCEEDED", "party1", "craft", 2)
    fire(g, "UNIT_SPELLCAST_SUCCEEDED", "player", "craft", 3275)
    fire(g, "TRADE_SKILL_UPDATE")
    fire(g, "TRADE_SKILL_CLOSE")
    fire(g, "UNIT_SPELLCAST_SUCCEEDED", "player", "combat", 133)
    assert [(r["event"], r["arguments"].get(3)) for r in entries(g)] == [
        ("TRADE_SKILL_SHOW", None), ("UNIT_SPELLCAST_SUCCEEDED", 3275), ("TRADE_SKILL_CLOSE", None)]
    fired = python_value(g.BrownstoneScanDB.journal_diagnostics)["fired_events"]
    assert fired["TRADE_SKILL_UPDATE"] == 2 and fired["MERCHANT_UPDATE"] == 1
    assert fired["UNIT_SPELLCAST_SUCCEEDED"] == 1


def test_lua_uncached_mail_attachments_are_kept():
    lua, g, _ = journal_client()
    lua.execute('function GetInboxItem(_, slot) if slot == 1 then return nil, 2589, nil, 3 end end')
    fire(g, "MAIL_SHOW")
    items = entries(g)[-1]["inbox"]["messages"][0]["items"]
    assert len(items) == 1 and items[0]["info"] == {"n": 4, 2: 2589, 4: 3}


def test_lua_cap_marker_new_ids_clear_current_session_reload_and_unknown_login():
    lua, g, _ = journal_client()
    lua.execute('for i=1,10002 do mainFrame.scripts.OnEvent(mainFrame, "PLAYER_MONEY") end')
    assert len(g.BrownstoneScanDB.journal) == 10001
    marker = entries(g)[-1]
    assert marker["skipped"] == 2
    fire(g, "PLAYER_MONEY")
    assert entries(g)[-1]["skipped"] == 3 and entries(g)[-1]["entry_id"] != marker["entry_id"]
    assert sum("Journal cap" in m for m in g.messages.values()) == 1
    g.SlashCmdList.BROWNSTONESCAN("clear")
    assert len(g.BrownstoneScanDB.journal) == 10001
    fire(g, "PLAYER_MONEY")  # Still full after a clear that kept this login: say so again.
    assert sum("Journal cap" in m for m in g.messages.values()) == 2
    g.epoch += 100
    lua.execute((ROOT / "addon/BrownstoneScan/BrownstoneScan.lua").read_text())
    fire(g, "ADDON_LOADED", "BrownstoneScan")
    fire(g, "PLAYER_ENTERING_WORLD", False, True)
    g.SlashCmdList.BROWNSTONESCAN("clear all")
    assert len(g.BrownstoneScanDB.journal) == 10001
    lua.execute((ROOT / "addon/BrownstoneScan/BrownstoneScan.lua").read_text())
    fire(g, "ADDON_LOADED", "BrownstoneScan")
    fire(g, "PLAYER_ENTERING_WORLD")
    g.SlashCmdList.BROWNSTONESCAN("clear")
    assert len(g.BrownstoneScanDB.journal) == 10001
    lua.execute((ROOT / "addon/BrownstoneScan/BrownstoneScan.lua").read_text())
    fire(g, "ADDON_LOADED", "BrownstoneScan")
    fire(g, "PLAYER_ENTERING_WORLD", True, False)
    fire(g, "MAIL_SHOW")
    newest = entries(g)[-1]["entry_id"]
    g.SlashCmdList.BROWNSTONESCAN("clear")
    assert [r["entry_id"] for r in entries(g)] == [newest]
    fire(g, "PLAYER_MONEY")
    assert len(entries(g)) == 2


def test_lua_rejected_events_and_missing_late_hooks_are_recorded():
    lua, g = capture_client()
    lua.execute('''
        local original = CreateFrame
        function CreateFrame(...)
            local f=original(...)
            function f:RegisterEvent(event)
                if event == "MAIL_SHOW" or event == "AUCTION_HOUSE_SHOW" then error("unknown") end
            end
            return f
        end
    ''')
    loaded = len(g.messages)
    lua.execute((ROOT / "addon/BrownstoneScan/BrownstoneScan.lua").read_text())
    fire(g, "ADDON_LOADED", "BrownstoneScan")
    diagnostics = python_value(g.BrownstoneScanDB.journal_diagnostics)
    assert "MAIL_SHOW" in diagnostics["rejected_events"] and "SendMail" in diagnostics["missing_hooks"]
    # The scan's own events are registered once, so a rejection is listed once.
    assert diagnostics["rejected_events"].count("AUCTION_HOUSE_SHOW") == 1
    # One summary line, however many candidates this client lacks.
    summaries = [m for i, m in g.messages.items() if i > loaded and "Journal" in m]
    assert len(summaries) == 1 and "1 event(s)" in summaries[0] and "/bscan status" in summaries[0]
    lua.execute('SendMail=function() end; hooksecurefunc=function() end')
    fire(g, "ADDON_LOADED", "Blizzard_MailFrame")
    assert [m for i, m in g.messages.items() if i > loaded and "Journal" in m] == summaries
    diagnostics = python_value(g.BrownstoneScanDB.journal_diagnostics)
    assert diagnostics["installed_hooks"]["SendMail"] and "SendMail" not in diagnostics["missing_hooks"]


def test_journal_discovery_context_imports_unchanged(tmp_path):
    loot = entry("loot", loot_slot_count=1,
                 loot_slots=[{"slot": 1, "link": "|Hitem:2770|h", "slot_type": 1, "quantity": 2,
                              "vendor_sell_copper": 5, "sources": {"n": 2, 1: "GameObject-0-1", 2: 2}}],
                 zone={"zone": "Elwynn Forest", "subzone": "Goldshire", "map_id": 1429, "x": .47, "y": .72})
    trainer = entry("trainer", trainer_service_count=1,
                    trainer_services=[{"index": 1, "level_required": {"n": 1, 1: 10}}],
                    trainer_filters={"available": True, "used": False})
    loot.update(family="loot", event="LOOT_OPENED")
    trainer.update(family="vendor", event="TRAINER_SHOW")
    config = addon_source(tmp_path / "data", write(tmp_path / "own.lua", [loot, trainer]))
    assert import_scans(config, now=NOW)["fully_imported"]
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        rows = db.execute("SELECT entry_id, record_json FROM character_journal").fetchall()
    saved = {entry_id: json.loads(record) for entry_id, record in rows}
    assert saved["loot"]["zone"]["x"] == .47 and saved["loot"]["zone"]["y"] == .72
    assert saved["loot"]["loot_slots"][0]["vendor_sell_copper"] == 5
    assert saved["loot"]["loot_slots"][0]["quantity"] == 2
    assert saved["loot"]["zone"]["map_id"] == 1429 and saved["loot"]["loot_slots"][0]["link"] == "|Hitem:2770|h"
    assert saved["trainer"]["trainer_services"][0]["index"] == 1
    assert saved["trainer"]["trainer_filters"]["used"] is False


def test_journal_shared_import_bronze_duplicates_scope_and_guidance(tmp_path):
    path = write(tmp_path / "own.lua", [entry()], [snapshot()])
    config = addon_source(tmp_path / "data", path)
    preview = preview_scans(config, now=NOW)
    assert preview.new_record_ids == ["char:bags:1", "e1"]
    assert journal.preview_rows(preview, "mac")[0]["new"] == 1
    result = import_scans(config, now=NOW, reviewed=preview)
    assert len(result["non_scan_records"]) == 2 and result["fully_imported"]
    archive = next((config["data_dir"] / "bronze" / config["source_id"]).glob("*.gz"))
    assert gzip.decompress(archive.read_bytes()) == path.read_bytes()
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        assert storage.schema_version(db) == 11
        assert db.execute("SELECT machine, family FROM character_journal").fetchall() == [("mac", "money")]
        assert db.execute("SELECT count(*) FROM market_snapshots").fetchone()[0] == 0
    assert journal.latest_rows(config)[0]["Entries"] == 1
    repeated = import_scans(config, now=NOW)
    assert all(r["outcome"] == "duplicate" for r in repeated["non_scan_records"])
    assert import_guidance(repeated).startswith("Nothing new:") and "/reload" in import_guidance(repeated)
    assert InputFile(path, "mac", preview=preview_scans(config, now=NOW)).fully_imported
    bad = copy.deepcopy(entry())
    bad["after_copper"] = 9
    write(path, [bad])
    with pytest.raises(ValueError, match="conflict"):
        preview_scans(config, now=NOW)
    changed = config.copy()
    changed["region"] = "eu"
    write(path, [entry()])
    with pytest.raises(ValueError, match="different market"):
        preview_scans(changed, now=NOW)


def test_journal_drops_stale_conflict_foreign_and_selection(tmp_path):
    folder = tmp_path / "drops"
    folder.mkdir()
    own = write(tmp_path / "own.lua", [entry()])
    drop = write(folder / "windows-pc-20261007T004900Z-BrownstoneScan.lua", [entry(), entry("e2")])
    config = addon_source(tmp_path / "data", own)
    config["drop_folder"] = folder
    preview = preview_inputs(config, NOW)
    results = import_inputs(config, preview, now=NOW)
    assert [r["outcome"] for r in results[1]["manifest"]["non_scan_records"]] == ["duplicate", "imported"]
    assert all(f.fully_imported for f in preview_inputs(config, NOW).files)
    with pytest.raises(StalePreviewError):
        import_inputs(config, preview, now=NOW)
    write(drop, [entry("e2", after_copper=9)])
    assert "conflict" in preview_inputs(config, NOW).files[1].error
    foreign = entry("foreign")
    foreign["faction"] = "Horde"
    write(own, [entry("e3"), foreign])
    p = preview_scans(config, now=NOW)
    assert journal.preview_rows(p)[1]["other house"] == 1
    result = import_scans(config, now=NOW, reviewed=p)
    assert not result["fully_imported"] and result["other_house"] == 1


@pytest.mark.parametrize("patch", [dict(entry_id=""), dict(family="bogus"), dict(sequence=0),
                                   dict(before_copper=-1), dict(session_time=-1), dict(arguments=[]),
                                   dict(item_changes={1: 1.5}), dict(captured_at=FINISHED+100000)])
def test_journal_validation_missing_unknown_signed_and_future(patch):
    r = entry()
    r.update(patch)
    with pytest.raises(ValueError):
        journal.summarize(r, NOW)


def test_journal_cli_and_page_aggregate_preview_and_display(tmp_path, monkeypatch, capsys):
    path = write(tmp_path / "own.lua", [entry(), entry("e2")])
    config = addon_source(tmp_path / "data", path)
    monkeypatch.setattr(cli, "_select_source", lambda *_: config)
    monkeypatch.setattr(sys, "argv", ["brownstone", "--preview"])
    monkeypatch.setattr(cli, "preview_scans", lambda config, path: preview_scans(config, path, NOW))
    cli.main()
    assert "'new': 2" in capsys.readouterr().out and not config["data_dir"].exists()
    import_scans(config, now=NOW)
    rows = journal.preview_rows(preview_scans(config, now=NOW), "mac")
    assert rows[0]["duplicate"] == 2
    assert journal.latest_rows(config)[0]["Entries"] == 2


def test_migration_10_to_11_backup_replay_and_preserves_snapshot_rows(tmp_path):
    config = addon_source(tmp_path, write(tmp_path / "own.lua", [entry()]))
    with duckdb.connect(str(tmp_path / "brownstone.duckdb")) as db:
        for version in range(1, 11):
            storage.MIGRATIONS[version](db)
        db.execute("CREATE TABLE schema_info (key VARCHAR PRIMARY KEY, value VARCHAR)")
        db.execute("INSERT INTO schema_info VALUES ('schema_version', '10')")
        from brownstone import character_snapshots
        character_snapshots.load(db, config, [snapshot()], "original", "raw-hash", NOW)
    assert storage.upgrade_database(tmp_path)
    assert (tmp_path / "brownstone.v10.backup.duckdb").exists()
    assert not storage.upgrade_database(tmp_path)
    with duckdb.connect(str(tmp_path / "brownstone.duckdb")) as db:
        storage.MIGRATIONS[11](db)
        assert db.execute("SELECT collection_id, source_sha256 FROM character_snapshots").fetchall() == [
            ("original", "raw-hash")]
        assert db.execute("SELECT count(*) FROM character_journal").fetchone()[0] == 0


def test_journal_final_writer_recheck_no_archive_and_unimported_reader(tmp_path, monkeypatch):
    path = write(tmp_path / "own.lua", [entry()])
    config = addon_source(tmp_path / "data", path)
    assert journal.latest_rows(config) == []
    preview = preview_scans(config, now=NOW)
    original = journal.states
    monkeypatch.setattr(journal, "states", lambda source, records, db=None:
                        [{"record_sha256": "concurrent"}] if db is not None else original(source, records))
    with pytest.raises(StalePreviewError, match="non-scan records"):
        import_scans(config, reviewed=preview, now=NOW)
    assert not (config["data_dir"] / "bronze").exists()
    monkeypatch.setattr(journal, "states", original)
    write(path, [entry("changed-file")])
    with pytest.raises(StalePreviewError):
        import_scans(config, reviewed=preview, now=NOW)
    assert not (config["data_dir"] / "bronze").exists()


def test_journal_empty_and_old_schema_display_and_validation(tmp_path):
    config = addon_source(tmp_path / "data", tmp_path / "unused.lua")
    config["data_dir"].mkdir()
    storage.upgrade_database(config["data_dir"], create=True)
    assert journal.latest_rows(config) == [] and journal.states(config, []) == []
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        db.execute("DROP TABLE character_journal")
    assert journal.latest_rows(config) == []
    assert journal.states(config, [entry()]) == [None]
    for patch in (dict(session_time=float("nan")), dict(session_time=float("inf")),
                  dict(item_changes=[]), dict(arguments={"n": -1})):
        r = entry()
        r.update(patch)
        with pytest.raises(ValueError):
            journal.summarize(r, NOW)


def test_lua_bag_baseline_survives_zone_transition_and_failures_are_problems():
    lua, g, _ = journal_client()
    g.quantity = 1
    fire(g, "PLAYER_ENTERING_WORLD", False, False)
    fire(g, "BAG_UPDATE_DELAYED")
    assert entries(g)[-1]["item_changes"] == {2589: -14}
    # A malformed read raises in journal code, but must not interrupt the game's event handler.
    lua.execute('C_Container.GetContainerItemInfo = function() return 99 end')
    fire(g, "BAG_UPDATE_DELAYED")
    assert g.BrownstoneScanDB.journal_errors.BAG_UPDATE_DELAYED == 1
    assert any("Journal observation rejected" in m for m in g.messages.values())


def test_lua_one_overflow_marker_after_partial_prune_and_resumed_capture():
    lua, g, _ = journal_client()
    lua.execute('for i=1,10001 do mainFrame.scripts.OnEvent(mainFrame, "PLAYER_MONEY") end')
    # Model old-session ordinary records with a current-session overflow marker.
    lua.execute('for i=1,9999 do BrownstoneScanDB.journal[i].captured_at = epoch - 1 end')
    g.SlashCmdList.BROWNSTONESCAN("clear")
    assert len(g.BrownstoneScanDB.journal) == 2
    lua.execute('for i=1,10001 do mainFrame.scripts.OnEvent(mainFrame, "PLAYER_MONEY") end')
    records = entries(g)
    assert len(records) == 10001
    markers = [r for r in records if r["event"] == "JOURNAL_OVERFLOW"]
    assert len(markers) == 1 and markers[0]["skipped"] == 3


def test_journal_hash_preserves_lua_key_types_and_aggregates_import_outcomes(tmp_path, monkeypatch, capsys):
    left = entry()
    right = entry()
    right["arguments"] = {"n": 3, "1": "raw", 3: False}
    assert journal.content_hash(left) != journal.content_hash(right)
    path = write(tmp_path / "own.lua", [entry(), entry("e2")])
    config = addon_source(tmp_path / "data", path)
    result = import_scans(config, now=NOW)
    assert journal.outcome_rows(result["non_scan_records"]) == [
        {"Character": "Alice", "Family": "money", "Outcome": "imported", "Entries": 2}]
    cli._report_scans(config, result)
    assert "Journal Alice money: 2 imported" in capsys.readouterr().out


def test_journal_batch_same_id_conflict_preserves_first_committed_file(tmp_path):
    folder = tmp_path / "drops"
    folder.mkdir()
    own = write(tmp_path / "own.lua", [entry()])
    write(folder / "windows-pc-20261007T004900Z-BrownstoneScan.lua", [entry(after_copper=9)])
    config = addon_source(tmp_path / "data", own)
    config["drop_folder"] = folder
    result = import_inputs(config, preview_inputs(config, NOW), now=NOW)
    assert result[0]["status"] == "imported" and result[1]["status"] == "error"
    assert "conflict" in result[1]["error"]
    assert journal.latest_rows(config)[0]["Entries"] == 1


def test_journal_mixed_scan_selection_and_transaction_rollback(tmp_path):
    from test_scans import listing, scan
    r = dict(schema_version=6, scans=[scan("a", FINISHED, [listing(2589, 2, 10)]),
                                    scan("b", FINISHED, [listing(2589, 2, 20)])], journal=[entry()])
    path = tmp_path / "mixed.lua"
    path.write_text("BrownstoneScanDB = " + to_lua(r))
    config = addon_source(tmp_path / "data", path)
    result = import_scans(config, scan_ids=["a"], now=NOW)
    assert result["remaining_unimported"] == 1 and not result["fully_imported"]
    assert result["non_scan_records"][0]["outcome"] == "imported"
    # A conflicting journal ID prevents the unimported scan from committing too.
    r["journal"] = [entry(after_copper=9)]
    path.write_text("BrownstoneScanDB = " + to_lua(r))
    with pytest.raises(ValueError, match="conflict"):
        import_scans(config, scan_ids=["b"], now=NOW)
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        assert db.execute("SELECT scan_id FROM addon_scans").fetchall() == [("a",)]


def test_lua_fresh_login_waits_for_loaded_bags_before_counting_changes():
    lua, g, _ = journal_client()
    # Beta 2026-10-09: at a fresh login the client reports empty bags until contents load.
    lua.execute('''
        loaded = false
        C_Container.GetContainerItemInfo = function(id, slot)
            if loaded and slot == 1 then return { itemID=2589, stackCount=quantity } end end
    ''')
    lua.execute((ROOT / "addon/BrownstoneScan/BrownstoneScan.lua").read_text())
    fire(g, "ADDON_LOADED", "BrownstoneScan")
    fire(g, "PLAYER_ENTERING_WORLD", True, False)
    before = len(entries(g))
    g.loaded = True
    fire(g, "BAG_UPDATE_DELAYED")
    assert entries(g)[-1]["baseline_missing"] is True and "item_changes" not in entries(g)[-1]
    g.quantity = 5
    fire(g, "BAG_UPDATE_DELAYED")
    # Two more in each of the stub's 7 carried containers, counted from the loaded baseline.
    assert entries(g)[-1]["item_changes"] == {2589: 14} and len(entries(g)) == before + 2


def test_lua_missing_namespace_never_hooks_a_similarly_named_global():
    lua, g, _ = journal_client()
    lua.execute('C_Container=nil; C_AuctionHouse=nil')
    lua.execute((ROOT / "addon/BrownstoneScan/BrownstoneScan.lua").read_text())
    fire(g, "ADDON_LOADED", "BrownstoneScan")
    diagnostics = python_value(g.BrownstoneScanDB.journal_diagnostics)
    assert "CancelAuction" in diagnostics["installed_hooks"]
    assert "C_AuctionHouse.CancelAuction" in diagnostics["missing_hooks"]
    assert "C_Container.UseContainerItem" in diagnostics["missing_hooks"]


def test_lua_unknown_sizes_values_and_disabled_vendor_container_hook():
    lua, g, _ = journal_client()
    g.UseContainerItem(0, 1)
    assert not entries(g)
    lua.execute('C_Container.GetContainerNumSlots = function() return -1 end')
    fire(g, "BAG_UPDATE_DELAYED")
    assert entries(g)[-1]["baseline_missing"]
    lua.execute('GetMoney = function() return "unknown" end')
    fire(g, "PLAYER_MONEY")
    assert "after_copper" not in entries(g)[-1]
    # Unsupported values and nil holes remain missing, with count retained.
    g.DoCraft(1, g.GetMoney, None)
    assert entries(g)[-1]["arguments"] == {"n": 3, 1: 1}


def test_lua_trainer_list_loading_after_show_is_read_on_update_or_one_second_later():
    lua, g, _ = journal_client()
    lua.execute('''
        services, timers = 0, {}
        C_Timer = { After = function(seconds, callback) timers[#timers + 1] = callback end }
        function GetNumTrainerServices() return services end
        function GetTrainerServiceInfo(i) return "Journeyman Tailoring", "Journeyman", "unavailable" end
        function GetTrainerServiceLevelReq(i) return 10 end
        function GetTrainerServiceCost(i) return 500 end
    ''')
    fire(g, "TRAINER_SHOW")
    assert entries(g)[-1]["trainer_service_count"] == 0  # 0.11.3 beta: empty at opening
    lua.execute('services = 1')
    fire(g, "TRAINER_UPDATE")
    loaded = entries(g)[-1]
    assert loaded["event"] == "TRAINER_UPDATE" and loaded["trainer_services"][0]["level_required"] == {"n": 1, 1: 10}
    count = len(entries(g))
    fire(g, "TRAINER_UPDATE")
    lua.execute('timers[1]()')
    assert len(entries(g)) == count  # unchanged lists are not saved again
    fire(g, "TRAINER_CLOSED")
    # Without TRAINER_UPDATE, the delayed read saves the loaded list; after closing it reads nothing.
    lua.execute('services = 0')
    fire(g, "TRAINER_SHOW")
    lua.execute('services = 2')
    lua.execute('timers[2]()')
    assert entries(g)[-1]["event"] == "TRAINER_DELAYED_READ" and entries(g)[-1]["trainer_service_count"] == 2
    fire(g, "TRAINER_CLOSED")
    lua.execute('services = 3; timers[2]()')
    assert entries(g)[-1]["event"] == "TRAINER_CLOSED"


def test_lua_merchant_late_loading_unchanged_closed_and_cost_stock():
    lua, g, _ = journal_client()
    lua.execute('''
        merchantCount, timers = 0, {}
        C_Timer = { After = function(seconds, callback) timers[#timers + 1] = callback end }
        function GetMerchantNumItems() return merchantCount end
        function GetMerchantItemLink(i) return "|Hitem:" .. (2320 + i - 1) .. "|h[Thread]|h" end
        function GetMerchantItemInfo(i) return "Thread", nil, 20, 2, i == 1 and -1 or 3, true, true, false end
        function GetMerchantItemCostInfo(i) return i == 2 and 1 or 0 end
        function UnitGUID(unit) return "Creature-0-1-2-3-1234-0001" end
        function UnitReaction(player, unit) return 4 end
        function GetRealZoneText() return "Elwynn Forest" end
    ''')
    fire(g, "MERCHANT_UPDATE")
    count = len(entries(g))
    fire(g, "MERCHANT_SHOW")
    assert entries(g)[-1]["merchant_item_count"] == 0
    lua.execute('merchantCount = 2')
    fire(g, "MERCHANT_UPDATE")
    loaded = entries(g)[-1]
    assert loaded["family"] == "vendor" and loaded["vendor_npc_id"] == 1234
    assert loaded["vendor_standing"] == 4 and loaded["zone"]["zone"] == "Elwynn Forest"
    first, second = loaded["merchant_items"]
    assert (first["item_id"], first["price_copper"], first["quantity"], first["stock"]) == (2320, 20, 2, -1)
    assert first["extended_cost"] is False and second["extended_cost"] is True and second["stock"] == 3
    assert first["link"] == "|Hitem:2320|h[Thread]|h"
    fire(g, "MERCHANT_UPDATE")
    lua.execute('timers[1]()')
    assert len(entries(g)) == count + 2
    fire(g, "MERCHANT_CLOSED")
    lua.execute('merchantCount = 3; timers[1]()')
    fire(g, "MERCHANT_UPDATE")
    assert entries(g)[-1]["event"] == "MERCHANT_CLOSED"
    lua.execute('merchantCount = 0')
    fire(g, "MERCHANT_SHOW")
    lua.execute('merchantCount = 1; timers[2]()')
    assert entries(g)[-1]["event"] == "MERCHANT_DELAYED_READ"
    assert g.actionCalls == 0


def test_lua_merchant_modern_guarded_and_bounded():
    lua, g, _ = journal_client()
    lua.execute('''
        function GetMerchantNumItems() return 9999 end
        C_MerchantFrame.GetItemInfo = function(i)
            return { price = 95, stackCount = 1, numAvailable = 0, hasExtendedCost = true }
        end
        function GetMerchantItemLink(i) error("not loaded") end
        function UnitReaction() error("unavailable") end
    ''')
    fire(g, "MERCHANT_SHOW")
    r = entries(g)[-1]
    assert r["merchant_item_count"] == 1000 and len(r["merchant_items"]) == 300
    assert r["merchant_items"][0]["price_copper"] == 95
    assert r["merchant_items"][0]["stock"] == 0 and r["merchant_items"][0]["extended_cost"] is True
    assert "vendor_standing" not in r and "link" not in r["merchant_items"][0]
    assert g.actionCalls == 0


def test_merchant_journal_import_scope_deduplication_and_raw(tmp_path):
    vendor = entry("vendor", merchant_items=[{"item_id": 2320, "price_copper": 20, "quantity": 2,
                                            "stock": -1, "extended_cost": False}], vendor_standing=4)
    vendor.update(family="vendor", event="MERCHANT_SHOW")
    path = write(tmp_path / "vendor.lua", [vendor])
    config = addon_source(tmp_path / "data", path)
    assert import_scans(config, now=NOW)["fully_imported"]
    assert import_scans(config, now=NOW)["non_scan_records"][0]["outcome"] == "duplicate"
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        saved = db.execute("SELECT source_id, market_id, record_json FROM character_journal").fetchone()
    assert saved[:2] == (config["source_id"], config["market_id"])
    assert json.loads(saved[2])["merchant_items"] == vendor["merchant_items"]
    vendor.update(faction="Horde", entry_id="other-house")
    write(path, [vendor])
    assert preview_scans(config, now=NOW).non_scan_mismatches[0]
