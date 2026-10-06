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
def test_addon_captures_v3_on_both_apis_and_imports(tmp_path, legacy):
    _, g = client(legacy)
    assert g.requests == 0 and len(g.BrownstoneScanDB.scans) == 0
    g.SlashCmdList.BROWNSTONESCAN("start")
    assert g.requests == 1
    record = complete(g, legacy)
    assert record["schema_version"] == 3 and record["duration_seconds"] == 12.5
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
    assert g.requests == 1  # no follow-up requests, retries or auction actions
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
    assert g.BrownstoneScanDB.addon_version == "0.3.1" and g.BrownstoneScanDB.schema_version == 3


@pytest.mark.parametrize("ending", [
    "complete", "stop", "closed", "timeout", "not_ready", "error", "zero", "legacy_throttled",
])
def test_maintenance_buttons_disabled_until_every_scan_exit(ending):
    lua, g = client(legacy=ending == "legacy_throttled", rows=0 if ending == "zero" else 5)
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
    assert "/bscan start | stop | status | label <text> | clear [all]" in g.messages[len(g.messages)]
