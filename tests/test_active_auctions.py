"""Passive owned-list evidence and scoped import-page projection, offline."""
import gzip

import duckdb
import pytest
from test_addon import ROOT, python_value
from test_character_snapshots import snapshot
from test_journal import entries, entry, fire, journal_client, write
from test_scans import NOW, addon_source

from brownstone import journal
from brownstone.config import MARKET_KEYS
from brownstone.pipeline import import_scans, preview_scans


@pytest.mark.parametrize("modern", [True, False])
def test_owned_event_reads_raw_changed_empty_missing_silent_no_requests(modern):
    lua, g, _ = journal_client()
    lua.execute('''
        reads, forbiddenCalls = 0, 0
        function forbidden() forbiddenCalls=forbiddenCalls+1; error("owned auction request/action called") end
        QueryAuctionItems = forbidden
        GetOwnerAuctionItems = forbidden
        C_AuctionHouse.QueryOwnedAuctions = forbidden
        count, price = 3, 12345
        Enum = { AuctionStatus = { Active=0, Sold=1 } }
        C_AuctionHouse.GetNumOwnedAuctions = function() reads=reads+1; return count end
        C_AuctionHouse.HasFullOwnedAuctionResults = function() return true end
        C_AuctionHouse.GetOwnedAuctionInfo = function(i)
            reads=reads+1
            if i == 3 then return {auctionID=103, quantity=2} end
            return {auctionID=100+i, itemKey={itemID=2589}, itemLink="raw link",
                quantity=2, status=i-1, bidAmount=0, buyoutAmount=price,
                bidder="Buyer", timeLeft=2, timeLeftSeconds=123, extra=false}
        end
        function GetNumAuctionItems(kind) assert(kind=="owner"); reads=reads+1; return count, count end
        function GetAuctionItemInfo(kind, i)
            assert(kind=="owner"); reads=reads+1
            if i==3 then return nil, nil, 2, nil, nil, nil, nil, nil, nil, nil, nil,
                nil, nil, nil, nil, nil, 2589 end
            return "Linen", 123, 2, 1, nil, 5, "level", 100, 1, price, 0,
                "Buyer", "Buyer-Realm", "Alice", nil, i-1, 2589, true
        end
        function GetAuctionItemLink(kind, i) assert(kind=="owner"); if i<3 then return "raw link" end end
        function GetAuctionItemTimeLeft(kind, i) assert(kind=="owner"); if i<3 then return 2 end end
    ''')
    event = "OWNED_AUCTIONS_UPDATED" if modern else "AUCTION_OWNED_LIST_UPDATE"
    before = len(g.messages)
    fire(g, "AUCTION_HOUSE_SHOW")
    assert g.reads == 0
    fire(g, event)
    state = entries(g)[-1]["owned_auctions"]
    assert entries(g)[-1]["family"] == "auction" and state["counts"][1] == 3
    first = state["auctions"][0]["info"]
    assert first["buyoutAmount" if modern else 10] == 12345
    assert first["bidAmount" if modern else 11] == 0
    assert ("status" if modern else 16) not in state["auctions"][2]["info"]
    if modern:
        assert first["itemKey"]["itemID"] == 2589 and first["extra"] is False
    else:
        assert first["n"] == 18 and state["auctions"][2]["info"][17] == 2589
    size = len(entries(g))
    fire(g, event)
    assert len(entries(g)) == size
    lua.execute('price=23456')
    fire(g, event)
    assert len(entries(g)) == size + 1
    lua.execute('count=0')
    fire(g, event)
    assert entries(g)[-1]["owned_auctions"]["counts"][1] == 0
    lua.execute('count=nil')
    fire(g, event)
    assert 1 not in entries(g)[-1]["owned_auctions"]["counts"]
    assert len(g.messages) == before and g.actionCalls == 0 and g.forbiddenCalls == 0
    # A fresh load records the same state again; saved lists are not session baselines.
    lua.execute((ROOT / "addon/BrownstoneScan/BrownstoneScan.lua").read_text())
    fire(g, "ADDON_LOADED", "BrownstoneScan")
    size = len(entries(g))
    fire(g, event)
    assert len(entries(g)) == size + 1


@pytest.mark.parametrize("event", ["OWNED_AUCTIONS_UPDATED", "AUCTION_OWNED_LIST_UPDATE"])
def test_owned_event_rejected_registration_guarded(event):
    lua, g, _ = journal_client()
    lua.execute('''
        originalCreateFrame=CreateFrame
        function CreateFrame(...)
            local f=originalCreateFrame(...)
            function f:RegisterEvent(name) if name==rejected then error("unsupported") end end
            return f
        end
    ''')
    g.rejected = event
    lua.execute((ROOT / "addon/BrownstoneScan/BrownstoneScan.lua").read_text())
    fire(g, "ADDON_LOADED", "BrownstoneScan")
    assert event in python_value(g.BrownstoneScanDB.journal_diagnostics)["rejected_events"]


def owned(eid, sequence, count=2, api="C_AuctionHouse", **extra):
    r = entry(eid)
    r.update(family="auction", event="OWNED_AUCTIONS_UPDATED", sequence=sequence,
             owned_auctions=dict(api=api, counts={1: count, "n": 1}, sold_status=1,
                                auctions={1: {"info": {"status": 0}}, 2: {"info": {"status": 1}}}, **extra))
    return r


def test_owned_shared_import_latest_sequence_empty_unknown_scope_bronze(tmp_path):
    path = write(tmp_path / "own.lua", [owned("later", 3), owned("earlier", 2, count=1), entry("money")],
                 [snapshot(character="Bob")])
    config = addon_source(tmp_path / "data", path)
    assert journal.active_auction_rows(config) == []
    preview = preview_scans(config, now=NOW)
    assert next(r for r in journal.preview_rows(preview) if r["Family"] == "auction")["new"] == 2
    result = import_scans(config, now=NOW, reviewed=preview)
    assert result["fully_imported"] and len(result["non_scan_records"]) == 4
    archive = config["data_dir"] / "bronze/my-scans" / result["bronze_file"]
    assert gzip.decompress(archive.read_bytes()) == path.read_bytes()
    rows = journal.active_auction_rows(config)
    assert rows[0]["Auctions"] == 2 and rows[0]["Marked sold"] == 1
    assert rows[0]["Active auctions (UTC)"].endswith("+00:00")
    assert rows[1]["Active auctions (UTC)"] == "active auctions unknown" and rows[1]["Auctions"] is None
    assert journal.active_auction_rows(config | {"source_id": "other"}) == []
    for field in MARKET_KEYS:
        assert journal.active_auction_rows(config | {field: str(config[field]) + "_other"}) == []
    assert all(r["outcome"] == "duplicate" for r in import_scans(config, now=NOW)["non_scan_records"])
    r = owned("empty", 4, count=0)
    r["owned_auctions"]["auctions"] = {}
    write(path, [r])
    import_scans(config, now=NOW)
    assert journal.active_auction_rows(config)[0]["Auctions"] == 0
    assert journal.active_auction_rows(config)[0]["Marked sold"] == 0
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        db.execute("DROP TABLE character_journal")
    assert journal.active_auction_rows(config)[0]["Active auctions (UTC)"] == "active auctions unknown"


@pytest.mark.parametrize("state,count,expected", [
    ({"api": "legacy", "auctions": {"1": {"info": {"16": 1}}, "2": {"info": {"16": 0}}}}, 2, 1),
    ({"api": "legacy", "auctions": [{"info": {}}]}, 1, None),
    ({"auctions": {}, "full_results": False}, 0, None),
    ({"auctions": {}}, None, None),
    ({"auctions": {}}, -1, None),
    ({"auctions": {}}, 1, None),
    ({"auctions": [{"info": {"status": 1}}]}, 1, None),
])
def test_owned_sold_count_missing_partial_legacy(state, count, expected):
    assert journal._sold_count(state, count) == expected


def test_owned_unavailable_readers_stay_unknown_and_cap_retries(tmp_path):
    lua, g, _ = journal_client()
    before = len(g.messages)
    fire(g, "OWNED_AUCTIONS_UPDATED")
    state = entries(g)[-1]["owned_auctions"]
    assert "counts" not in state
    r = entry()
    r.update(family="auction", owned_auctions=state)
    path = write(tmp_path / "missing.lua", [r])
    config = addon_source(tmp_path / "data", path)
    import_scans(config, now=NOW)
    row = journal.active_auction_rows(config)[0]
    assert row["Auctions"] is None and row["Marked sold"] is None
    assert len(g.messages) == before
    lua.execute('''
        C_AuctionHouse.GetNumOwnedAuctions=function() return 0 end
        for i=1,10000 do BrownstoneScanDB.journal[i]={entry_id="old"..i, captured_at=epoch-1} end
    ''')
    fire(g, "OWNED_AUCTIONS_UPDATED")
    assert len(g.BrownstoneScanDB.journal) == 10001
    assert entries(g)[-1]["event"] == "JOURNAL_OVERFLOW"
    # Clear old evidence; an observation skipped at the cap was never the saved baseline.
    g.SlashCmdList.BROWNSTONESCAN("clear")
    fire(g, "OWNED_AUCTIONS_UPDATED")
    assert entries(g)[-1]["owned_auctions"]["counts"][1] == 0


def test_owned_legacy_reported_total_does_not_call_partial_batch_empty(tmp_path):
    r = owned("partial", 1, count=0, api="legacy")
    r["owned_auctions"].update(counts={1: 0, 2: 51, "n": 2}, auctions={})
    path = write(tmp_path / "partial.lua", [r])
    config = addon_source(tmp_path / "data", path)
    import_scans(config, now=NOW)
    row = journal.active_auction_rows(config)[0]
    assert row["Auctions"] == 51 and row["Marked sold"] is None
