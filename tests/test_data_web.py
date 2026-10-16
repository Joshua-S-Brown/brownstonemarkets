"""Offline Data API parity, review lifetime, writer exclusion and moved Import UI rules."""

import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import duckdb
import pytest
from app_helpers import preview_addon
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_scans import finished_now, listing, scan, write_scans

import api
from api import context, data
from brownstone import cli, import_review, pipeline, scan_inputs


@pytest.fixture
def browser(tmp_path, monkeypatch):
    _, source = preview_addon(tmp_path, monkeypatch)
    monkeypatch.setattr(data, "_registry", {})
    monkeypatch.setattr(data, "_writer", threading.Lock())
    app = FastAPI()
    api.install(app, tmp_path, "secret")
    with TestClient(app) as client:
        yield client, source


def post(browser, route, body=None, source=""):
    return browser[0].post(
        "/api/data/" + route, params=dict(source=source), json=body or {}, headers={"X-Brownstone-Token": "secret"}
    )


def records(folder):
    result = {}
    with duckdb.connect(str(folder / "brownstone.duckdb"), read_only=True) as db:
        for name in ("scan_listings", "market_snapshots", "addon_scans", "character_snapshots", "character_journal"):
            excluded = ("collected_at", "collection_id") if name == "addon_scans" else ("collected_at",)
            columns = [r[0] for r in db.execute(f"DESCRIBE {name}").fetchall() if r[0] not in excluded]
            fields = ",".join('"' + c + '"' for c in columns)
            result[name] = db.execute(f"SELECT {fields} FROM {name} ORDER BY ALL").fetchall()
    return result


def test_saved_chips_details_are_read_only_imported_lazy_and_non_addon(browser, monkeypatch):
    def broken(*args):
        raise AssertionError("GET must never read the game file")

    monkeypatch.setattr(pipeline, "preview_scans", broken)
    result = browser[0].get("/api/data").json()
    assert result["provider"] == "addon" and "scans imported" in result["chips"][0]
    assert "Drop folder" in result["chips"][1] and result["details"]["source_id"] == browser[1]["source_id"]
    assert browser[0].get("/api/data/imported").status_code == 200
    assert not browser[1]["data_dir"].exists()
    monkeypatch.setattr(context, "resolve", lambda _: browser[1] | dict(provider="tsm"))
    result = browser[0].get("/api/data").json()
    assert not result["chips"] and "--source " in result["cli"]
    assert post(browser, "review").status_code == 422
    assert post(browser, "import", dict(review_id="x", selected=[])).status_code == 422


def test_preview_subset_import_matches_cli_and_consumes_review(browser, tmp_path, monkeypatch):
    source = browser[1]
    other = source | dict(data_dir=tmp_path / "cli")
    before = source["scan_path"].read_bytes()
    result = post(browser, "review").json()
    review = result["review"]
    assert review["new"] and review["default"] == ["one", "two"]
    assert "New partial scan: two" in review["problems"]
    assert not source["data_dir"].exists()
    shaped = import_review.selection(data._registry[source["source_id"]][2], False, ["one"])
    assert shaped["selection_differs"] and "Selection differs from the default" in shaped["problems"]
    selected = post(browser, 'selection', dict(review_id=result['review_id'], selected=['one'])).json()
    assert selected['selection_differs'] and selected['selected'] == ['one'] and selected['lines']
    response = post(browser, "import", dict(review_id=result["review_id"], selected=["one"])).json()
    assert response["success"] and response["review"] is None
    assert "Imported. Collection prices come from scan one" in response["messages"][0][1]
    assert source["scan_path"].read_bytes() == before
    assert post(browser, "import", dict(review_id=result["review_id"], selected=["one"])).status_code == 409
    monkeypatch.setattr(cli, "_select_source", lambda _: other)
    monkeypatch.setattr(sys, "argv", ["brownstone", "--scan", "one"])
    cli.main()
    assert records(source["data_dir"]) == records(other["data_dir"])


def test_replaced_other_source_config_and_discarded_reviews(browser, monkeypatch):
    old = post(browser, "review").json()["review_id"]
    new = post(browser, "review").json()["review_id"]
    assert old != new
    assert post(browser, "import", dict(review_id=old, selected=["one"])).status_code == 409
    source = browser[1]
    monkeypatch.setattr(context, "enabled", lambda: [source, source | dict(source_id="other")])
    assert post(browser, "import", dict(review_id=new, selected=["one"]), source="other").status_code == 409
    source["machine"] = "changed"
    failure = post(browser, "import", dict(review_id=new, selected=["one"]), source=source["source_id"])
    assert failure.status_code == 409 and "Review out of date: check for new scans again" in failure.text
    fresh = post(browser, "review", source=source["source_id"]).json()["review_id"]
    post(browser, "discard", dict(review_id="old"), source=source["source_id"])
    assert data._registry[source["source_id"]][0] == fresh
    post(browser, "discard", dict(review_id=fresh), source=source["source_id"])
    assert (
        post(browser, "import", dict(review_id=fresh, selected=["one"]), source=source["source_id"]).status_code == 409
    )


def test_stale_bytes_preview_error_import_failure_and_watchlist(browser, monkeypatch):
    source = browser[1]
    original = source["scan_path"].read_bytes()
    reviewed = post(browser, "review").json()["review_id"]
    source["scan_path"].write_bytes(original + b"\n")
    result = post(browser, "import", dict(review_id=reviewed, selected=["one"])).json()
    assert not result["success"] and result["review"] is None and "Nothing was imported" in result["messages"][0][1]
    assert not source["data_dir"].exists()
    source["scan_path"].unlink()
    failure = post(browser, "review").json()
    assert failure["review_id"] is None and "Preview failed" in failure["messages"][0][1]
    source["scan_path"].write_bytes(original)
    reviewed = post(browser, "review").json()["review_id"]

    def broken(*args, **kwargs):
        raise ValueError("fixture failure")

    with monkeypatch.context() as patch:
        patch.setattr(pipeline, "import_scans", broken)
        response = post(browser, "import", dict(review_id=reviewed, selected=["one"])).json()
        assert "previous snapshot remains available" in response["messages"][0][1]
    from brownstone import watchlist

    watchlist.save_entries(
        watchlist.watchlist_path(source["data_dir"], source["source_id"]), [watchlist.Entry(1, buy_copper=50)]
    )
    reviewed = post(browser, "review").json()["review_id"]
    response = post(browser, "import", dict(review_id=reviewed, selected=["one"])).json()
    assert response["success"] and response["hits"]
    assert "(1)" in response["hits"][0] and "Buy hit" in response["hits"][0]
    with monkeypatch.context() as patch:
        patch.setattr(watchlist, "load_entries", broken)
        assert "Watchlist evidence unavailable" in import_review.watchlist_hits(source, [])[0]


def test_concurrent_second_import_rejected_without_consuming_review(browser, monkeypatch):
    reviewed = post(browser, "review").json()["review_id"]
    started, finish = threading.Event(), threading.Event()
    original = pipeline.import_scans

    def slow(*args, **kwargs):
        started.set()
        assert finish.wait(10)
        return original(*args, **kwargs)

    monkeypatch.setattr(pipeline, "import_scans", slow)
    body = dict(review_id=reviewed, selected=["one"])
    with ThreadPoolExecutor() as pool:
        first = pool.submit(post, browser, "import", body)
        assert started.wait(10)
        try:
            second = post(browser, "import", body)
            assert second.status_code == 409 and "Another import is running" in second.text
        finally:
            finish.set()
        assert first.result().json()["success"]


def test_drop_fresh_review_rejected_cleanup_lines_and_stale_review(browser, tmp_path, monkeypatch):
    source = browser[1]
    folder = tmp_path / "drops"
    folder.mkdir()
    source["drop_folder"] = folder
    good = write_scans(
        folder / "windows-pc-20261007T004900Z-BrownstoneScan.lua", scan("win", finished_now(), [listing(2, 1, 80)])
    )
    bad = folder / "windows-pc-20261007T005000Z-BrownstoneScan.lua"
    bad.write_text("truncated")
    result = post(browser, "review").json()
    assert any(bad.name in p for p in result["review"]["problems"])
    assert str(good) in result["review"]["choices"]
    assert not source["data_dir"].exists()
    response = post(browser, "import", dict(review_id=result["review_id"], selected=[str(good)])).json()
    assert response["success"] and response["review_id"] != result["review_id"]
    assert any("1 dropped file is fully imported" in line for line in response["review"]["lines"])
    assert any(
        "don't /bscan clear; its latest drop is not fully imported" in line for line in response["review"]["clear"]
    )
    assert str(good) not in response["review"]["default"]
    good.write_bytes(good.read_bytes() + b"\n")
    failed = post(browser, "import", dict(review_id=response["review_id"], selected=[str(good)])).json()
    assert failed["review"] is None and "Nothing was imported" in failed["messages"][0][1]
    assert bad.read_text() == "truncated"
    reviewed = scan_inputs.preview_inputs(source)
    shaped = import_review.selection(reviewed, True, [])
    assert shaped["selection_differs"] and shaped["file_status"] and shaped["notes"]

    # A post-import preview failure must still tell the client to reload saved evidence.
    again = post(browser, 'review').json()['review_id']
    def busy_preview(_):
        raise OSError('drop folder busy after write')
    monkeypatch.setattr(data, 'create_review', busy_preview)
    result = post(browser, 'import', dict(review_id=again, selected=[str(good)])).json()
    assert result['success'] and result['review'] is None
    assert any('Preview failed' in text for _, text in result['messages'])
