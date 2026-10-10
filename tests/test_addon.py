"""Execute the shipped addon in Lua 5.1 against offline WoW API stubs."""
from pathlib import Path

import pytest
from lupa.lua51 import LuaRuntime
from test_scan_v3 import BASE, BEAR, MONKEY
from test_scans import NOW, addon_source, scan, write_scans

from brownstone import scan_details, scans
from brownstone.pipeline import import_scans

ROOT = Path(__file__).resolve().parents[1]


def python_value(table):
    if not hasattr(table, "items"):
        return table
    values = {k: python_value(v) for k, v in table.items()}
    if values and set(values) == set(range(1, len(values) + 1)):
        return [values[i] for i in range(1, len(values) + 1)]
    return values


def client(legacy=False, rows=5):
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute((ROOT / "tests/fixtures/addon_harness.lua").read_text())
    g = lua.globals()
    g.listingData = lua.table()
    g.linkData, g.timeData = lua.table(), lua.table()
    for index in range(1, rows + 1):
        item_id = 6538 if index < 3 else 2589 if index < 5 else 999
        data = {1: "Willow Robe" if index < 3 else "Linen Cloth", 3: 1, 4: 2, 6: 10, 7: "REQ_LEVEL",
                8: 0, 9: 1, 10: 500, 11: 0, 14: "TestOwner", 15: "TestOwner-Realm", 17: item_id, 18: True}
        if index == 2:
            data[15] = ""  # fallback to owner
        if index == 5:
            for key in (1, 4, 6, 7, 14, 15):
                del data[key]
            data[18] = False
        g.listingData[index] = lua.table_from(data)
        g.linkData[index] = MONKEY if index == 1 else BEAR if index == 2 else BASE if index < 5 else None
        g.timeData[index] = 4 if index < 5 else None
    if legacy:
        lua.execute("C_AuctionHouse = nil; C_Item = nil")
    lua.execute((ROOT / "addon/BrownstoneScan/BrownstoneScan.lua").read_text())
    g.mainFrame.scripts.OnEvent(g.mainFrame, "ADDON_LOADED", "BrownstoneScan")
    return lua, g


def complete(g, legacy=False):
    event = "AUCTION_ITEM_LIST_UPDATE" if legacy else "REPLICATE_ITEM_LIST_UPDATE"
    g.mainFrame.scripts.OnEvent(g.mainFrame, event)
    g.clock = 12.5
    while g.mainFrame.scripts.OnUpdate is not None:
        g.mainFrame.scripts.OnUpdate(g.mainFrame, 1)
    return python_value(g.BrownstoneScanDB.scans[1])


@pytest.mark.parametrize("legacy", [False, True])
def test_addon_captures_v4_on_both_apis_and_imports(tmp_path, legacy):
    _, g = client(legacy)
    assert g.requests == 0 and len(g.BrownstoneScanDB.scans) == 0
    g.SlashCmdList.BROWNSTONESCAN("start")
    assert g.requests == 1
    record = complete(g, legacy)
    assert record["schema_version"] == 4 and record["duration_seconds"] == 12.5
    assert record["api"] == ("legacy" if legacy else "modern")
    frame = scans.listing_frame(record)
    assert frame["seller"].to_list() == ["TestOwner-Realm", "TestOwner", "TestOwner-Realm", "TestOwner-Realm", None]
    assert frame["item_link"].to_list() == [MONKEY, BEAR, BASE, BASE, None]
    assert frame["quality"].to_list() == [2, 2, 2, 2, None]
    assert frame["required_level"].to_list() == [10, 10, 10, 10, None]
    assert frame["time_left"].to_list() == [4, 4, 4, 4, None]
    assert frame["variant_state"].to_list() == ["variant", "variant", "base", "base", "unresolved"]
    assert set(g.referenceCalls.values()) == {1} and set(g.instantCalls.values()) == {1}
    assert len(record["items"]) == 3
    assert record["items"][-1] == {"item_id": 999}
    assert scan_details.item_frame(record)["vendor_sell_copper"].to_list() == [0, 0, None]
    for key in ("textIndexes", "itemSeen", "cursor", "phase", "clock_start"):
        assert key not in record
    path = write_scans(tmp_path / "actual-addon.lua", record)
    manifest = import_scans(addon_source(tmp_path / "data", path), now=NOW)
    assert manifest["scans"][0]["availability"]["listing_available"]["seller"] == 4
    assert g.requests == 1  # no additional auction-house requests or auction actions
    # Clearing before /reload is still blocked, protecting scans that are only in memory.
    g.SlashCmdList.BROWNSTONESCAN("clear")
    assert len(g.BrownstoneScanDB.scans) == 1


@pytest.mark.parametrize("legacy", [False, True])
def test_optional_field_apis_missing_or_erroring_preserve_nulls(legacy):
    lua, g = client(legacy)
    lua.execute("GetItemInfo = nil; GetItemInfoInstant = nil; C_Item = nil")
    if legacy:
        lua.execute('GetAuctionItemLink = nil; GetAuctionItemTimeLeft = function() error("not available") end')
    else:
        lua.execute('C_AuctionHouse.GetReplicateItemLink = nil; '
                    'C_AuctionHouse.GetReplicateItemTimeLeft = function() error("not available") end')
    g.SlashCmdList.BROWNSTONESCAN("start")
    record = complete(g, legacy)
    frame = scans.listing_frame(record)
    assert frame["item_link"].null_count() == frame.height
    assert frame["time_left"].null_count() == frame.height
    assert set(frame["variant_state"].to_list()) == {"unresolved"}
    assert all(set(item) == {"item_id"} for item in record["items"])


def test_chunks_closed_window_stops_and_old_scans_are_kept():
    lua, g = client(rows=2001)
    old = scan("old", 1793816300, [])
    g.BrownstoneScanDB.scans[1] = lua.table_from(old)
    g.SlashCmdList.BROWNSTONESCAN("start")
    g.mainFrame.scripts.OnEvent(g.mainFrame, "REPLICATE_ITEM_LIST_UPDATE")
    g.mainFrame.scripts.OnUpdate(g.mainFrame, 1)
    assert len(g.BrownstoneScanDB.scans) == 1
    g.mainFrame.scripts.OnEvent(g.mainFrame, "AUCTION_HOUSE_CLOSED")
    assert g.mainFrame.scripts.OnUpdate is None
    partial = python_value(g.BrownstoneScanDB.scans[2])
    assert partial["status"] == "stopped" and partial["listing_count"] == 2000 and partial["reported_count"] == 2001
    assert scans.summarize(partial)["partial"]
    assert g.BrownstoneScanDB.scans[1].schema_version == 1
    assert g.requests == 1
    assert set(g.referenceCalls.values()) == {1}


def test_button_starts_only_on_click_and_timeout_does_not_save_empty_scan():
    _, g = client()
    g.mainFrame.scripts.OnEvent(g.mainFrame, "AUCTION_HOUSE_SHOW")
    assert g.requests == 0
    g.scanButton.scripts.OnClick()
    assert g.requests == 1
    g.mainFrame.scripts.OnUpdate(g.mainFrame, 31)
    assert len(g.BrownstoneScanDB.scans) == 0 and g.mainFrame.scripts.OnUpdate is None
    assert any("timeout" in m for m in g.messages.values())


@pytest.mark.parametrize("legacy", [False, True])
def test_maintenance_buttons_follow_auction_window_and_reload(legacy):
    lua, g = client(legacy)
    if legacy:
        lua.execute("AuctionFrame = AuctionHouseFrame; AuctionHouseFrame = nil")
    parent = g.AuctionFrame if legacy else g.AuctionHouseFrame
    parent.shown = False
    assert g.reloadButton is None and g.clearButton is None
    parent.shown = True
    g.mainFrame.scripts.OnEvent(g.mainFrame, "AUCTION_HOUSE_SHOW")
    assert g.reloadButton.text == "Reload" and g.clearButton.text == "Clear saved scans"
    assert g.reloadButton.template == g.clearButton.template == "UIPanelButtonTemplate"
    assert g.reloadButton.point[3] == "LEFT" and g.clearButton.point[3] == "LEFT"
    assert g.requests == 0
    g.reloadButton.Click(g.reloadButton)
    assert g.reloads == 1
    g.clearButton.Click(g.clearButton)
    pending = g.popup
    parent.shown = False
    g.mainFrame.scripts.OnEvent(g.mainFrame, "AUCTION_HOUSE_CLOSED")
    assert not pending.shown and len(g.BrownstoneScanDB.scans) == 0
    assert not g.reloadButton.IsShown(g.reloadButton) and not g.clearButton.IsShown(g.clearButton)
    g.reloadButton.Click(g.reloadButton)
    g.clearButton.Click(g.clearButton)
    assert g.reloads == 1 and not g.popup.shown
    parent.shown = True
    g.mainFrame.scripts.OnEvent(g.mainFrame, "AUCTION_HOUSE_SHOW")
    g.reloadButton.Click(g.reloadButton)
    assert g.reloads == 2 and g.requests == 0


def test_clear_button_refuses_unsaved_scans_without_confirmation_or_force():
    _, g = client()
    g.SlashCmdList.BROWNSTONESCAN("start")
    complete(g)
    g.clearButton.Click(g.clearButton)
    assert g.popup is None and len(g.BrownstoneScanDB.scans) == 1
    assert "nothing was cleared" in g.messages[len(g.messages)]
    assert "Type /reload, import into Brownstone" in g.messages[len(g.messages)]
    g.SlashCmdList.BROWNSTONESCAN("clear")
    assert len(g.BrownstoneScanDB.scans) == 1
    g.SlashCmdList.BROWNSTONESCAN("clear all")
    assert len(g.BrownstoneScanDB.scans) == 0  # override remains slash-only


def test_clear_confirmation_cancel_and_accept_match_protected_slash_clear():
    lua, g = client()
    g.BrownstoneScanDB.scans = lua.table_from([lua.table_from({"scan_id": "old-1"}),
                                            lua.table_from({"scan_id": "old-2"})])
    g.SlashCmdList.BROWNSTONESCAN("label Keep this label")
    g.mainFrame.scripts.OnEvent(g.mainFrame, "AUCTION_HOUSE_SHOW")
    before = python_value(g.BrownstoneScanDB)
    g.clearButton.Click(g.clearButton)
    assert python_value(g.BrownstoneScanDB) == before
    assert "Delete 2 saved" in g.popup.text and "Import them into Brownstone first" in g.popup.text
    definition = g.StaticPopupDialogs.BROWNSTONESCAN_CLEAR_SAVED
    assert definition.hideOnEscape and definition.timeout == 0 and definition.preferredIndex == 3
    g.popup.Cancel(g.popup)
    assert python_value(g.BrownstoneScanDB) == before
    g.clearButton.Click(g.clearButton)
    g.popup.Accept(g.popup)
    button_result = python_value(g.BrownstoneScanDB)
    assert len(g.BrownstoneScanDB.scans) == 0 and g.BrownstoneScanDB.label == "Keep this label"
    assert "next /reload" in g.messages[len(g.messages)] and g.reloads == 0
    g.BrownstoneScanDB.scans = lua.table_from([lua.table_from({"scan_id": "old-1"}),
                                            lua.table_from({"scan_id": "old-2"})])
    g.SlashCmdList.BROWNSTONESCAN("clear")
    assert python_value(g.BrownstoneScanDB) == button_result
    assert g.BrownstoneScanDB.addon_version == "0.11.1" and g.BrownstoneScanDB.schema_version == 6


@pytest.mark.parametrize("ending", [
    "complete", "stop", "closed", "timeout", "not_ready", "error", "zero", "legacy_throttled",
])
def test_maintenance_buttons_disabled_until_every_scan_exit(ending):
    lua, g = client(legacy=ending == "legacy_throttled", rows=0 if ending == "zero" else 5)
    g.SlashCmdList.BROWNSTONESCAN("panel")
    g.mainFrame.scripts.OnEvent(g.mainFrame, "AUCTION_HOUSE_SHOW")
    if ending == "not_ready":
        lua.execute("C_AuctionHouse.IsThrottledMessageSystemReady = function() return false end")
    elif ending == "error":
        lua.execute('C_AuctionHouse.ReplicateItems = function() error("test failure") end')
    elif ending == "legacy_throttled":
        lua.execute("CanSendAuctionQuery = function() return false, false end")
    g.scanButton.Click(g.scanButton)
    if ending not in {"not_ready", "error", "legacy_throttled"}:
        assert not g.reloadButton.enabled and not g.clearButton.enabled
        assert not g.BrownstonePanelReload.enabled and not g.BrownstonePanelClear.enabled
        assert not g.BrownstonePanelStart.enabled
        # Also invoke callbacks directly to verify guards beyond client disabled state.
        g.reloadButton.scripts.OnClick()
        g.clearButton.scripts.OnClick()
        assert g.reloads == 0 and g.popup is None
        if ending in {"complete", "zero"}:
            complete(g)
        elif ending == "stop":
            g.SlashCmdList.BROWNSTONESCAN("stop")
        elif ending == "closed":
            g.mainFrame.scripts.OnEvent(g.mainFrame, "AUCTION_HOUSE_CLOSED")
        else:
            g.mainFrame.scripts.OnUpdate(g.mainFrame, 31)
    assert g.reloadButton.enabled and g.clearButton.enabled
    assert g.BrownstonePanelReload.enabled and g.BrownstonePanelClear.enabled
    assert g.BrownstonePanelStart.enabled == (ending != "closed")
    g.reloadButton.Click(g.reloadButton)
    assert g.reloads == 1


def test_pending_clear_is_hidden_on_scan_start_and_rechecks_unsaved_on_accept():
    lua, g = client()
    g.BrownstoneScanDB.scans[1] = lua.table_from({"scan_id": "saved"})
    g.mainFrame.scripts.OnEvent(g.mainFrame, "AUCTION_HOUSE_SHOW")
    g.clearButton.Click(g.clearButton)
    pending = g.popup
    g.SlashCmdList.BROWNSTONESCAN("start")
    assert not pending.shown
    definition = g.StaticPopupDialogs.BROWNSTONESCAN_CLEAR_SAVED
    definition.OnAccept(pending)
    assert len(g.BrownstoneScanDB.scans) == 1
    complete(g)
    definition.OnAccept(pending)
    assert len(g.BrownstoneScanDB.scans) == 2
    assert "nothing was cleared" in g.messages[len(g.messages)]


def test_clear_confirmation_rejects_changed_saved_count_and_allows_zero():
    lua, g = client()
    g.BrownstoneScanDB.scans[1] = lua.table_from({"scan_id": "saved"})
    g.mainFrame.scripts.OnEvent(g.mainFrame, "AUCTION_HOUSE_SHOW")
    g.clearButton.Click(g.clearButton)
    g.SlashCmdList.BROWNSTONESCAN("clear")
    g.popup.Accept(g.popup)
    assert "Saved scans changed" in g.messages[len(g.messages)]
    g.clearButton.Click(g.clearButton)
    assert "Delete 0 saved" in g.popup.text
    g.popup.Accept(g.popup)
    assert len(g.BrownstoneScanDB.scans) == 0 and "next /reload" in g.messages[len(g.messages)]


def test_slash_commands_label_status_stop_help_and_case_still_work():
    _, g = client()
    command = g.SlashCmdList.BROWNSTONESCAN
    assert g.SLASH_BROWNSTONESCAN1 == "/bscan"
    command("  LABEL  Test house  ")
    command("START")
    record = complete(g)
    assert record["label"] == "Test house"
    command("status")
    assert "1 saved scan(s). API: modern" in g.messages[len(g.messages)]
    command("stop")
    assert "No scan is running" in g.messages[len(g.messages)]
    command("label")
    assert g.BrownstoneScanDB.label is None
    command("unknown")
    assert "/bscan start | stop | status | panel | label <text> | clear [all]" in g.messages[len(g.messages)]


def pass_client(rows=5, rejected=False, legacy=False):
    lua, g = client(legacy=legacy, rows=rows)
    # Reload the addon with a client whose reference data is initially uncached.
    lua.execute('''
        loaded, itemRequests = {}, {}
        GetItemInfo = function(id)
            referenceCalls[id] = (referenceCalls[id] or 0) + 1
            if not loaded[id] then return nil end
            return "Loaded", nil, 2, 25, 10, "Armor", "Cloth", 20, nil, nil, 123
        end
        C_Item = { GetItemInfo = GetItemInfo, RequestLoadItemDataByID = function(id)
            itemRequests[id] = (itemRequests[id] or 0) + 1
        end }
    ''')
    if rejected:
        lua.execute('''
            originalCreateFrame = CreateFrame
            CreateFrame = function(...)
                local f = originalCreateFrame(...)
                function f:RegisterEvent(event)
                    if event == "GET_ITEM_INFO_RECEIVED" then error("unknown event") end
                end
                return f
            end
        ''')
    lua.execute((ROOT / "addon/BrownstoneScan/BrownstoneScan.lua").read_text())
    g.mainFrame.scripts.OnEvent(g.mainFrame, "ADDON_LOADED", "BrownstoneScan")
    g.SlashCmdList.BROWNSTONESCAN("start")
    g.mainFrame.scripts.OnEvent(g.mainFrame, "AUCTION_ITEM_LIST_UPDATE" if legacy else "REPLICATE_ITEM_LIST_UPDATE")
    while len(g.BrownstoneScanDB.scans) == 0:
        g.mainFrame.scripts.OnUpdate(g.mainFrame, 1)
    return lua, g


def advance(g, seconds=1):
    g.clock += seconds
    g.mainFrame.scripts.OnUpdate(g.mainFrame, seconds)


@pytest.mark.parametrize("legacy", [False, True])
def test_item_pass_delayed_answers_saved_before_end_close_and_first_values_unchanged(legacy):
    _, g = pass_client(legacy=legacy)
    original = python_value(g.BrownstoneScanDB.scans[1])
    assert original["status"] == "completed" and original["item_pass"]["status"] == "running"
    assert not g.scanButton.enabled and not g.reloadButton.enabled and not g.clearButton.enabled
    g.SlashCmdList.BROWNSTONESCAN("clear all")
    assert "Wait for the scan and its item info pass to finish" in g.messages[len(g.messages)]
    g.reloadButton.scripts.OnClick()
    g.clearButton.scripts.OnClick()
    assert len(g.BrownstoneScanDB.scans) == 1 and g.reloads == 0
    advance(g)
    assert dict(g.itemRequests.items()) == {6538: 1, 2589: 1, 999: 1}
    g.mainFrame.scripts.OnEvent(g.mainFrame, "AUCTION_HOUSE_CLOSED")
    for item_id in (6538, 2589, 999):
        advance(g)
        g.loaded[item_id] = True
        g.mainFrame.scripts.OnEvent(g.mainFrame, "GET_ITEM_INFO_RECEIVED", item_id, True)
        # duplicate and unsolicited events must not create observations or change counts
        g.mainFrame.scripts.OnEvent(g.mainFrame, "GET_ITEM_INFO_RECEIVED", item_id, True)
        g.mainFrame.scripts.OnEvent(g.mainFrame, "GET_ITEM_INFO_RECEIVED", 123456, True)
    advance(g)
    result = python_value(g.BrownstoneScanDB.scans[1])
    assert result["items"] == original["items"] and result["listings"] == original["listings"]
    assert result["status"] == "completed" and not scans.summarize(result)["partial"]
    assert result["item_pass"]["received"] == 3 and result["item_pass"]["status"] == "completed"
    assert result["item_pass"]["duration_seconds"] == 5
    assert scan_details.reference_frame(result)["pass_vendor_sell_copper"].to_list() == [123, 123, 123]
    assert g.mainFrame.scripts.OnUpdate is None and g.reloadButton.enabled and g.clearButton.enabled
    assert dict(g.itemRequests.items()) == {6538: 1, 2589: 1, 999: 1}
    assert sum("Item info:" in m for m in g.messages.values()) == 1
    g.SlashCmdList.BROWNSTONESCAN("clear")
    assert len(g.BrownstoneScanDB.scans) == 1  # counted as unsaved before pass began


def test_item_pass_failure_timeout_late_event_and_saved_running_import(tmp_path):
    _, g = pass_client()
    advance(g)
    g.mainFrame.scripts.OnEvent(g.mainFrame, "GET_ITEM_INFO_RECEIVED", 6538, False)
    g.loaded[2589] = True
    g.mainFrame.scripts.OnEvent(g.mainFrame, "GET_ITEM_INFO_RECEIVED", 2589, True)
    advance(g)
    running = python_value(g.BrownstoneScanDB.scans[1])
    path = write_scans(tmp_path / "reload-mid-pass.lua", running)
    manifest = import_scans(addon_source(tmp_path / "data", path), now=NOW)
    assert manifest["scans"][0]["priced"] and manifest["scans"][0]["availability"]["item_pass"]["received"] == 1
    advance(g, 18)
    result = python_value(g.BrownstoneScanDB.scans[1])
    assert result["item_pass"] | {} == {
        "total": 3, "requested": 3, "received": 1, "failed": 1, "timed_out": 1, "cached": 0,
        "wait_limit_seconds": 20, "duration_seconds": 20, "status": "timeout",
        "api": "C_Item.RequestLoadItemDataByID", "items": [
            {"item_id": 2589, "item_level": 25, "max_stack_size": 20, "vendor_sell_copper": 123}]}
    g.loaded[999] = True
    g.mainFrame.scripts.OnEvent(g.mainFrame, "GET_ITEM_INFO_RECEIVED", 999, True)
    assert python_value(g.BrownstoneScanDB.scans[1]) == result
    assert not scans.summarize(result)["partial"] and g.mainFrame.scripts.OnUpdate is None


def test_item_pass_rejected_event_is_recorded_and_skipped():
    _, g = pass_client(rejected=True)
    result = python_value(g.BrownstoneScanDB.scans[1])["item_pass"]
    assert result["status"] == "skipped" and result["requested"] == 0
    assert result["reason"] == "GET_ITEM_INFO_RECEIVED registration rejected"
    assert g.mainFrame.scripts.OnUpdate is None and g.reloadButton.enabled
    g.SlashCmdList.BROWNSTONESCAN("status")
    assert "GET_ITEM_INFO_RECEIVED" in g.messages[len(g.messages) - 1]


def test_item_pass_missing_api_records_reason():
    _, g = client()
    g.SlashCmdList.BROWNSTONESCAN("start")
    result = complete(g)["item_pass"]
    assert result["status"] == "skipped" and result["reason"] == "request API missing"
    assert result["total"] == 1 and result["requested"] == 0


def test_item_pass_requests_spread_across_frames_and_errors_are_not_retried():
    lua, g = client(rows=401)
    for index in range(1, 402):
        g.listingData[index][17] = index
    lua.execute('''
        itemRequests = {}
        C_Item.GetItemInfo = function() return nil end
        C_Item.RequestLoadItemDataByID = function(id)
            itemRequests[id] = (itemRequests[id] or 0) + 1
            error("request failed")
        end
    ''')
    g.SlashCmdList.BROWNSTONESCAN("start")
    g.mainFrame.scripts.OnEvent(g.mainFrame, "REPLICATE_ITEM_LIST_UPDATE")
    g.mainFrame.scripts.OnUpdate(g.mainFrame, 1)
    advance(g)
    assert len(g.itemRequests) == 200
    advance(g)
    assert len(g.itemRequests) == 400
    advance(g)
    result = python_value(g.BrownstoneScanDB.scans[1])["item_pass"]
    assert result["requested"] == result["failed"] == 401 and result["status"] == "completed"
    assert set(g.itemRequests.values()) == {1} and g.mainFrame.scripts.OnUpdate is None


def test_item_pass_deadline_rejects_answer_before_next_update_and_stop_keeps_scan():
    _, g = pass_client()
    advance(g)
    g.clock = 20
    g.loaded[2589] = True
    g.mainFrame.scripts.OnEvent(g.mainFrame, "GET_ITEM_INFO_RECEIVED", 2589, True)
    assert g.BrownstoneScanDB.scans[1].item_pass.received == 0
    advance(g, 0)
    assert g.BrownstoneScanDB.scans[1].item_pass.timed_out == 3
    _, g = pass_client()
    advance(g)
    g.SlashCmdList.BROWNSTONESCAN("stop")
    assert g.BrownstoneScanDB.scans[1].status == "completed"
    assert g.BrownstoneScanDB.scans[1].item_pass.status == "stopped"
    assert g.mainFrame.scripts.OnUpdate is None and g.reloadButton.enabled


def test_item_pass_synchronous_answers_zero_precedence_and_omitted_fields():
    lua, g = client()
    lua.execute('''
        loaded, itemRequests = {}, {}
        C_Item.GetItemInfo = function(id)
            if not loaded[id] then
                return "Initial", nil, nil, 0, nil, nil, nil, nil, nil, nil, 0
            end
            return "Loaded", nil, nil, 50, nil, nil, nil, 20, nil, nil, 100
        end
        C_Item.RequestLoadItemDataByID = function(id)
            itemRequests[id] = (itemRequests[id] or 0) + 1
            loaded[id] = true
            mainFrame.scripts.OnEvent(mainFrame, "GET_ITEM_INFO_RECEIVED", id, true)
        end
    ''')
    g.SlashCmdList.BROWNSTONESCAN("start")
    record = complete(g)
    assert record["item_pass"]["received"] == 3 and record["item_pass"]["status"] == "completed"
    assert all(r == {"item_id": r["item_id"], "max_stack_size": 20} for r in record["item_pass"]["items"])
    assert scan_details.effective_frame(scan_details.reference_frame(record))["vendor_sell_copper"].to_list() == [0] * 3
    assert set(g.itemRequests.values()) == {1}


def test_item_pass_success_without_values_and_no_candidate_scan_terminate():
    _, g = pass_client()
    advance(g)
    for item_id in (6538, 2589, 999):
        g.mainFrame.scripts.OnEvent(g.mainFrame, "GET_ITEM_INFO_RECEIVED", item_id, True)
    advance(g)
    result = python_value(g.BrownstoneScanDB.scans[1])["item_pass"]
    assert result["received"] == 3 and result["items"] == {} and result["status"] == "completed"
    _, g = client(rows=4)
    g.SlashCmdList.BROWNSTONESCAN("start")
    result = complete(g)["item_pass"]
    assert result["status"] == "completed" and result["total"] == result["requested"] == 0


def test_item_pass_reads_items_loaded_during_listing_reads_without_requesting():
    _, g = pass_client()
    g.loaded[2589] = True  # answered while listings were read, before the pass listened
    advance(g)
    assert dict(g.itemRequests.items()) == {6538: 1, 999: 1}
    for item_id in (6538, 999):
        g.mainFrame.scripts.OnEvent(g.mainFrame, "GET_ITEM_INFO_RECEIVED", item_id, False)
    advance(g)
    result = python_value(g.BrownstoneScanDB.scans[1])
    assert result["item_pass"]["status"] == "completed"
    assert {k: result["item_pass"][k] for k in ("total", "requested", "failed", "cached")} == {
        "total": 3, "requested": 2, "failed": 2, "cached": 1}
    assert result["item_pass"]["items"] == [
        {"item_id": 2589, "item_level": 25, "max_stack_size": 20, "vendor_sell_copper": 123}]
    assert "1 already loaded, 2 requested" in g.messages[len(g.messages)]
    assert scan_details.reference_frame(result)["pass_vendor_sell_copper"].to_list() == [None, 123, None]



def test_panel_toggle_movement_escape_tooltip_and_no_capture():
    lua, g = client()
    before = python_value(g.BrownstoneScanDB)
    icon = g.BrownstoneScanMinimapButton
    assert icon.width == icon.height == 32 and lua.eval("BrownstoneScanMinimapButton.parent == Minimap")
    icon.scripts.OnEnter(icon)
    assert list(g.GameTooltip.lines.values()) == ["Brownstone Scan", "Click: open panel. Drag: move"]
    icon.scripts.OnLeave()
    assert not g.GameTooltip.shown
    icon.Click(icon)
    window = g.BrownstoneScanPanel
    assert window.IsShown(window) and window.movable and window.clamped
    assert window.template == "BasicFrameTemplateWithInset" and window.TitleText.text == "Brownstone Scan"
    assert "BrownstoneScanPanel" in g.UISpecialFrames.values()  # client's Escape-close registry
    window.scripts.OnDragStart(window)
    assert window.moving
    window.scripts.OnDragStop(window)
    assert not window.moving
    window.CloseButton.Click()
    assert not window.IsShown(window)
    g.SlashCmdList.BROWNSTONESCAN("panel")
    assert window.IsShown(window)
    g.SlashCmdList.BROWNSTONESCAN("panel")
    assert not window.IsShown(window)
    assert python_value(g.BrownstoneScanDB) == before
    assert g.requests == 0 and g.mainFrame.scripts.OnUpdate is None
    assert "1. Play. 2. Reload (or log out)" in window.fontStrings[3].text
    assert "duplicates." in window.fontStrings[3].text


def test_minimap_drag_angle_restored_after_reload():
    lua, g = client()
    icon = g.BrownstoneScanMinimapButton
    assert g.BrownstoneScanDB.ui.minimap_angle == 225
    icon.scripts.OnDragStart(icon)
    assert icon.scripts.OnUpdate is not None
    g.cursorX, g.cursorY = 200, 360  # scale 2: cursor is directly above minimap center
    icon.scripts.OnUpdate(icon, 0.1)
    icon.scripts.OnDragStop(icon)
    assert icon.scripts.OnUpdate is None
    assert g.BrownstoneScanDB.ui.minimap_angle == pytest.approx(90)
    assert icon.point[4] == pytest.approx(0, abs=1e-10) and icon.point[5] == pytest.approx(80)
    before = python_value(g.BrownstoneScanDB)
    lua.execute((ROOT / "addon/BrownstoneScan/BrownstoneScan.lua").read_text())
    g.mainFrame.scripts.OnEvent(g.mainFrame, "ADDON_LOADED", "BrownstoneScan")
    assert g.BrownstoneScanDB.ui.minimap_angle == 90
    assert g.BrownstoneScanMinimapButton.point[5] == pytest.approx(80)
    assert python_value(g.BrownstoneScanDB) == before
    restored = g.BrownstoneScanMinimapButton
    restored.scripts.OnDragStart(restored)
    restored.Hide(restored)
    assert restored.scripts.OnUpdate is None  # hiding minimap controls ends active drag updates


@pytest.mark.parametrize("bad_angle", ['"invalid"', '0/0', 'math.huge'])
def test_minimap_invalid_angle_uses_default(bad_angle):
    lua, g = client()
    lua.execute(f"BrownstoneScanDB.ui.minimap_angle = {bad_angle}")
    lua.execute((ROOT / "addon/BrownstoneScan/BrownstoneScan.lua").read_text())
    g.mainFrame.scripts.OnEvent(g.mainFrame, "ADDON_LOADED", "BrownstoneScan")
    assert g.BrownstoneScanDB.ui.minimap_angle == 225


def test_panel_status_counts_threshold_overflow_login_and_chat():
    lua, g = client()
    g.BrownstoneScanDB.scans[1] = lua.table_from(dict(scan_id="saved", status="complete"))
    g.BrownstoneScanDB.snapshots[1] = lua.table_from(
        dict(snapshot_id="old", character="Example Auctioneer", realm="Beta"))
    lua.execute('for i = 1, 7999 do BrownstoneScanDB.journal[i] = { event = "TEST" } end')
    g.SlashCmdList.BROWNSTONESCAN("panel")
    status, journal = g.BrownstoneScanPanel.fontStrings[1], g.BrownstoneScanPanel.fontStrings[2]
    assert "Saved scans in file: 1" in status.text and "Session scans not written: 0" in status.text
    assert "Character snapshots: 1" in status.text and "unknown (Clear keeps all" in status.text
    assert journal.text == "Journal entries: 7999 / 10,000" and journal.color[2] == 1
    lua.execute('BrownstoneScanDB.journal[8000] = { event = "TEST" }; '
                'BrownstoneScanDB.journal[8001] = { event = "JOURNAL_OVERFLOW", skipped = 37 }')
    g.mainFrame.scripts.OnEvent(g.mainFrame, "PLAYER_ENTERING_WORLD", True, False)
    g.BrownstonePanelStatus.Click(g.BrownstonePanelStatus)
    assert "Login time: known" in status.text
    assert journal.text == "Journal entries: 8000 / 10,000; skipped: 37" and journal.color[2] == 0.65
    panel_chat = list(g.messages.values())[-5:]
    g.SlashCmdList.BROWNSTONESCAN("status")
    assert list(g.messages.values())[-5:] == panel_chat
    lua.execute('BrownstoneScanDB.journal = {}')
    g.BrownstonePanelStatus.Click(g.BrownstonePanelStatus)
    assert journal.color[2] == 1 and journal.text == "Journal entries: 0 / 10,000"


def test_panel_reload_and_confirmed_clear_share_existing_controls():
    lua, g = client()
    g.AuctionHouseFrame.shown = False
    g.SlashCmdList.BROWNSTONESCAN("panel")
    assert g.BrownstonePanelReload.enabled and g.BrownstonePanelClear.enabled
    g.BrownstonePanelReload.Click(g.BrownstonePanelReload)
    assert g.reloads == 1
    g.BrownstoneScanDB.scans[1] = lua.table_from(dict(scan_id="saved"))
    g.BrownstonePanelClear.Click(g.BrownstonePanelClear)
    assert g.popup.which == "BROWNSTONESCAN_CLEAR_SAVED" and g.popup.data == 1
    before = python_value(g.BrownstoneScanDB)
    g.popup.Cancel(g.popup)
    assert python_value(g.BrownstoneScanDB) == before
    g.BrownstonePanelClear.Click(g.BrownstonePanelClear)
    g.popup.Accept(g.popup)
    assert len(g.BrownstoneScanDB.scans) == 0
    assert "Saved scans in file: 0" in g.BrownstoneScanPanel.fontStrings[1].text
    assert g.BrownstoneScanDB.ui.minimap_angle == 225 and g.reloads == 1


@pytest.mark.parametrize("legacy", [False, True])
def test_panel_start_and_maintenance_sync_scan_item_pass_and_unsaved(legacy):
    lua, g = client(legacy)
    lua.execute("C_Item = C_Item or {}; C_Item.RequestLoadItemDataByID = function() end")
    g.AuctionHouseFrame.shown = False
    g.SlashCmdList.BROWNSTONESCAN("panel")
    start, reload, clear = g.BrownstonePanelStart, g.BrownstonePanelReload, g.BrownstonePanelClear
    assert not start.enabled
    start.Click(start)
    start.scripts.OnClick()  # same start guard even if called despite disabled state
    assert g.requests == 0
    g.AuctionHouseFrame.shown = True
    g.mainFrame.scripts.OnEvent(g.mainFrame, "AUCTION_HOUSE_SHOW")
    assert start.enabled
    start.Click(start)
    assert g.requests == 1
    assert not start.enabled and not reload.enabled and not clear.enabled
    assert reload.enabled == g.reloadButton.enabled and clear.enabled == g.clearButton.enabled
    reload.scripts.OnClick()
    clear.scripts.OnClick()
    start.scripts.OnClick()
    assert g.reloads == 0 and g.popup is None and g.requests == 1
    event = "AUCTION_ITEM_LIST_UPDATE" if legacy else "REPLICATE_ITEM_LIST_UPDATE"
    g.mainFrame.scripts.OnEvent(g.mainFrame, event)
    g.mainFrame.scripts.OnUpdate(g.mainFrame, 1)
    assert not g.scanButton.enabled and not start.enabled  # item pass
    g.AuctionHouseFrame.shown = False
    g.mainFrame.scripts.OnEvent(g.mainFrame, "AUCTION_HOUSE_CLOSED")
    assert not reload.enabled and not clear.enabled and not start.enabled
    reload.scripts.OnClick()
    clear.scripts.OnClick()
    assert g.reloads == 0 and g.popup is None
    g.clock = 30
    g.mainFrame.scripts.OnUpdate(g.mainFrame, 1)
    assert reload.enabled == g.reloadButton.enabled and clear.enabled == g.clearButton.enabled
    assert not start.enabled  # pass ended, but house closed
    clear.Click(clear)
    assert g.popup is None and len(g.BrownstoneScanDB.scans) == 1
    assert any("nothing was cleared" in m for m in g.messages.values())
    status = g.BrownstoneScanPanel.fontStrings[1].text
    assert "Saved scans in file: 0" in status and "Session scans not written: 1" in status
    g.AuctionHouseFrame.shown = True
    g.mainFrame.scripts.OnEvent(g.mainFrame, "AUCTION_HOUSE_SHOW")
    assert start.enabled == g.scanButton.enabled


def test_panel_start_tracks_auction_events_before_client_frame_visibility():
    _, g = client()
    g.AuctionHouseFrame.shown = False
    g.SlashCmdList.BROWNSTONESCAN("panel")
    g.mainFrame.scripts.OnEvent(g.mainFrame, "AUCTION_HOUSE_SHOW")
    assert g.BrownstonePanelStart.enabled
    g.AuctionHouseFrame.shown = True
    g.mainFrame.scripts.OnEvent(g.mainFrame, "AUCTION_HOUSE_CLOSED")
    assert not g.BrownstonePanelStart.enabled
    g.BrownstonePanelStatus.Click(g.BrownstonePanelStatus)
    assert not g.BrownstonePanelStart.enabled
