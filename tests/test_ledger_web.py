"""Offline Ledger projections/API: moved Stock UI rule checks and UTC window contracts."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_item_ledger import chat, mail, receive, row, snapshot
from test_ledger import bags, burst
from test_stock import fixture

import api
from api import context
from api import ledger as adapter
from brownstone import item_ledger, ledger, ledger_view, stock


@pytest.fixture
def browser(tmp_path, monkeypatch):
    source = fixture(tmp_path)
    monkeypatch.setattr(context, "enabled", lambda: [source])
    monkeypatch.setattr(adapter, "_cache", {})
    monkeypatch.setattr(context.recipe_catalogs, "parse_catalogs", lambda _: ([], []))
    app = FastAPI()
    api.install(app, tmp_path, "secret")
    with TestClient(app) as client:
        yield client, source


def get(browser, **params):
    return browser[0].get("/api/ledger", params=dict(days="all", **params))


def save(browser, entries):
    return browser[0].post("/api/ledger/targets", json=dict(entries=entries), headers={"X-Brownstone-Token": "secret"})


def test_cached_search_chains_targets_capture_states_and_evidence(browser, monkeypatch):
    path = stock.targets_path(browser[1]["data_dir"], browser[1]["source_id"])
    assert save(browser, [dict(item_id=2589, target_units=20, buy_copper=30)]).status_code == 200
    calls = []
    original = stock.load_stock
    monkeypatch.setattr(stock, "load_stock", lambda *args: calls.append(1) or original(*args))
    data = get(browser).json()["stock"]
    assert data["rows"][0]["short"] == 9 and data["rows"][0]["at_most"]
    assert data["names"]["2589"] == "Linen Cloth"
    assert data["rows"][0]["speed"]["suggested_units"] is None
    assert data["rows"][0]["speed"]["reason"] == 'not enough scan gaps (0, 0.0 h)'
    assert any(c["character"] == "Cara" and c["unknown"] for c in data["captures"])
    assert any(c["excluded"] for c in data["captures"]) and any(c["empty"] for c in data["captures"])
    assert data["evidence"]["freshness"]["stale"]
    assert not get(browser, q="not found").json()["stock"]["rows"]
    filtered = get(browser, q="2589").json()["stock"]
    assert len(filtered["rows"]) == 1 and filtered["value_copper"] == 220
    empty = get(browser, chains=True).json()["stock"]
    assert not empty["rows"] and empty["items_held"] == empty["buy_cost_copper"] == empty["value_copper"] == 0
    assert len(calls) == 1
    assert stock.load_entries(path)[0].target_units == 20
    assert save(browser, [dict(item_id=2589, target_units=30)]).status_code == 200
    assert get(browser).json()["stock"]["rows"][0]["target_units"] == 30 and len(calls) == 2
    stock.save_entries(path, [stock.Entry(2589, 31)])
    assert get(browser).json()["stock"]["rows"][0]["target_units"] == 31 and len(calls) == 3


def test_empty_missing_limits_damaged_file_and_invalid_save(browser, monkeypatch):
    assert save(browser, [dict(item_id=9999, target_units=10, buy_percent=80)]).status_code == 200
    data = get(browser).json()["stock"]
    assert data["rows"][0]["item_id"] == 9999 and data["rows"][0]["limit_unknown"]
    assert data["rows"][0]["unlisted_units"] == 10
    assert data["rows"][0]["fill_state"] == "insufficient listings"
    assert data["rows"][0]["limit_kind"] == "percent"
    for bad in (
        [dict(item_id=True, target_units=1)],
        [dict(item_id=1, target_units=-1)],
        [dict(item_id=1, target_units=1, buy_copper=10, buy_percent=80)],
    ):
        assert save(browser, bad).status_code == 422
    path = stock.targets_path(browser[1]["data_dir"], browser[1]["source_id"])
    path.write_text("{}")
    rejected = save(browser, [])
    assert rejected.status_code == 422 and "Last saved targets kept" in rejected.text
    assert path.read_text() == "{}"
    data = get(browser).json()
    assert "Unable to read Stock evidence" in data["errors"]["stock"]
    assert data["gold"] is not None and data["items"] is not None
    monkeypatch.setattr(context, "enabled", lambda: [browser[1] | {"source_id": "empty"}])
    empty = get(browser).json()["stock"]
    assert not empty["captures"] and empty["evidence"]["snapshot"] is None


def test_gold_cached_categories_reconciliation_lazy_movements(browser, monkeypatch):
    records = burst()
    at = records[0]["captured_at"]
    data = ledger.project(records, [bags(at - 2, 0), bags(max(r["captured_at"] for r in records) + 2, 1075)])
    data["excluded_money"] = 1
    calls = []
    monkeypatch.setattr(ledger, "load", lambda _: calls.append(1) or data)
    result = get(browser).json()["gold"]
    assert {r["category"] for r in result["totals"]} == {"auction sale", "deposit refund"}
    assert result["team"]["in_copper"] == 1023
    assert result["reconciliation"][0]["unexplained_copper"] == 52
    assert result["evidence"]["excluded_money"] == 1
    assert {r["category"]: r["movement_count"] for r in result["categories"]} == {
        "auction sale": 2, "deposit refund": 2
    }
    total = result["totals"][0]
    movements = (
        browser[0]
        .get(
            "/api/ledger/movements",
            params=dict(
                ledger="gold",
                name=total["character"][0],
                realm=total["character"][1],
                faction=total["character"][2],
                day=total["day"],
                category=total["category"],
            ),
        )
        .json()
    )
    assert movements[0]["entry_id"] == data["movements"][0]["entry_id"]
    assert movements[0]["machine"] == "fixture" and movements[0]["copper"] == 268
    assert movements[0]["ledger_version"] == 1 and movements[0]["utc"].endswith("+00:00")
    get(browser, q="2589")
    assert len(calls) == 1
    assert (
        browser[0]
        .get(
            "/api/ledger/movements",
            params=dict(
                ledger="gold", name="Other", realm="x", faction="x", day=total["day"], category=total["category"]
            ),
        )
        .json()
        == []
    )


@pytest.mark.parametrize("failed", ["gold", "items", "stock"])
def test_failures_are_independent(browser, monkeypatch, failed):
    def broken(*args):
        raise ValueError("bad journal")

    target = dict(gold=(ledger, "load"), items=(item_ledger, "load"), stock=(stock, "load_stock"))[failed]
    monkeypatch.setattr(*target, broken)
    data = get(browser).json()
    assert data[failed] is None and "bad journal" in data["errors"][failed]
    assert all(data[k] is not None for k in ("gold", "items", "stock") if k != failed)
    if failed != "stock":
        assert (
            browser[0]
            .get(
                "/api/ledger/movements",
                params=dict(ledger=failed, name="a", realm="b", faction="c", day="2026-10-16", category="other"),
            )
            .status_code
            == 503
        )


def test_items_cached_filtered_totals_transfers_residual_order_and_provenance(browser, monkeypatch):
    records = [
        chat(),
        row(),
        row("SendMail", at=103, seq=1, arguments={"1": "Bob Surname"}),
        row(at=103, item_changes={"2589": -1}),
        *receive(mail(sender="Fixture Surname"), at=104, character="Bob", machine="pc"),
    ]
    data = item_ledger.project(records, [snapshot(), snapshot(110, 4)])
    calls = []
    monkeypatch.setattr(item_ledger, "load", lambda _: calls.append(1) or data)
    answer = get(browser).json()["items"]
    assert sum(r["in_units"] for r in answer["totals"]) == 2
    assert answer["transfers"][0]["status"] == "transfer" and answer["transfers"][0]["received"]["machine"] == "pc"
    assert answer["reconciliation"][0]["residual_units"] == 4
    assert get(browser, q="not found").json()["items"]["team"] == dict(in_units=0, out_units=0)
    assert get(browser, q="Linen").json()["items"]["totals"]
    assert not get(browser, chains=True).json()["items"]["totals"]
    total = next(
        t for t in answer["totals"] if t["character"][0] == "Fixture" and t["category"] == "gathered or looted"
    )
    movements = (
        browser[0]
        .get(
            "/api/ledger/movements",
            params=dict(
                ledger="items",
                name=total["character"][0],
                realm=total["character"][1],
                faction=total["character"][2],
                day=total["day"],
                category=total["category"],
            ),
        )
        .json()
    )
    assert movements[0]["entry_id"] == records[1]["entry_id"] and movements[0]["item_ledger_version"] == 1
    assert len(calls) == 1


def test_day_ranges_utc_midnight_all_and_unknown_pairs():
    now = datetime(2026, 10, 16, 0, 0, tzinfo=UTC)
    bounds = ledger_view.day_bounds("7", now)
    assert bounds == (int(datetime(2026, 10, 10, tzinfo=UTC).timestamp()), int((now + timedelta(days=1)).timestamp()))
    assert not ledger_view.in_range(bounds[0] - 1, bounds)
    assert ledger_view.in_range(bounds[0], bounds)
    assert ledger_view.in_range(bounds[1] - 1, bounds)
    assert not ledger_view.in_range(bounds[1], bounds)
    assert ledger_view.in_range(0, ledger_view.day_bounds("all", now))
    assert ledger_view.day_bounds("30", now)[0] == int(datetime(2026, 9, 17, tzinfo=UTC).timestamp())
    movements = [
        dict(character=("a", "r", "f"), at=t, parts=[dict(category="other", copper=10)])
        for t in (bounds[0] - 1, bounds[0], bounds[1] - 1, bounds[1])
    ]
    result = ledger_view.gold_answer(
        dict(
            movements=movements,
            reconciliation=[
                dict(to=bounds[0], unexplained_copper=None, **{"from": bounds[0] - 1}),
                dict(to=bounds[0] - 1, unexplained_copper=0, **{"from": bounds[0] - 2}),
            ],
        ),
        bounds,
    )
    assert result["team"]["in_copper"] == 20 and result["movement_count"] == 2
    assert [d["day"] for d in result["daily"]] == ["2026-10-10", "2026-10-16"]
    assert result["pairs"] == dict(total=1, reconciled=0, unknown=1)
    assert ledger_view.limit_kind(stock.Entry(1, 1, buy_copper=10)) == "copper"
    assert ledger_view.limit_kind(stock.Entry(1, 1)) == "none"


def test_cache_database_config_hour_changes(browser, monkeypatch):
    get(browser)
    first = adapter._cache[browser[1]["source_id"]][1]
    database = browser[1]["data_dir"] / "brownstone.duckdb"
    database.touch()
    get(browser)
    assert adapter._cache[browser[1]["source_id"]][1] is not first
    first = adapter._cache[browser[1]["source_id"]][1]
    now = datetime.now(UTC) + timedelta(hours=2)
    monkeypatch.setattr(adapter, "datetime", SimpleNamespace(now=lambda _: now))
    get(browser)
    assert adapter._cache[browser[1]["source_id"]][1] is not first
    first = adapter._cache[browser[1]["source_id"]][1]
    browser[1]["max_age_hours"] += 1
    get(browser)
    assert adapter._cache[browser[1]["source_id"]][1] is not first


def test_items_filter_uses_catalog_names_and_chains_when_stock_fails():
    now = datetime(2026, 10, 16, 12, tzinfo=UTC)
    moved = [
        dict(character=("a", "r", "f"), at=int(now.timestamp()), item_id=item, parts=[dict(category="other", units=n)])
        for item, n in ((2589, 3), (7, 5))
    ]
    loaded = dict(
        items=dict(movements=moved, reconciliation=[], transfers=[], baselines=[], item_ledger_version=1),
        catalog_filter=dict(chain_ids={2589}, names={2589: "Linen Cloth"}),
        errors=dict(stock="Unable to read Stock evidence"),
    )
    by_name = ledger_view.page(loaded, "all", now, "linen")
    assert by_name["stock"] is None and by_name["names"] == {2589: "Linen Cloth"}
    assert by_name["items"]["team"] == dict(in_units=3, out_units=0)
    assert ledger_view.page(loaded, "all", now, chains=True)["items"]["team"]["in_units"] == 3
    assert ledger_view.page(loaded, "all", now)["items"]["team"]["in_units"] == 8
    found = ledger_view.movements(
        loaded["items"], "items", ("a", "r", "f"), "2026-10-16", "other", ledger_view.filter_basis(loaded), "linen"
    )
    assert [m["name"] for m in found] == ["Linen Cloth"]


def test_category_counts_once_per_movement_category_in_selected_days():
    now = datetime(2026, 10, 16, tzinfo=UTC)
    at = int(now.timestamp())
    def movement(time, parts):
        return dict(character=("a", "r", "f"), at=time, parts=[dict(category=k, copper=v) for k, v in parts])
    movements = [movement(at, [("auction sale", 20), ("auction sale", 10), ("deposit refund", 5)]),
                 movement(at, [("other", 0)]), movement(at, [("auction sale", 15)]),
                 movement(at - 10 * 86400, [("auction sale", 99)])]
    result = ledger_view.gold_answer(dict(movements=movements, reconciliation=[]), ledger_view.day_bounds("7", now))
    categories = {r["category"]: r for r in result["categories"]}
    assert categories["auction sale"] == dict(
        category="auction sale", in_copper=45, out_copper=0, movement_count=2, net_copper=45
    )
    assert categories["deposit refund"]["movement_count"] == 1
    assert categories["other"]["movement_count"] == 1
    assert result["movement_count"] == 3
