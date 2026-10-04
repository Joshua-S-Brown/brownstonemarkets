"""Offline UI smoke test using an isolated saved Classic snapshot."""
from pathlib import Path

import pytest

from brownstone.config import read_sources
from brownstone.pipeline import run

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402  (only after the skip check)

ROOT = Path(__file__).resolve().parents[1]


def test_action_board_saved_snapshot_and_retail_browse(tmp_path, monkeypatch):
    sources = read_sources(ROOT / "config/market.toml")
    for source in sources:
        source["data_dir"] = tmp_path / "data"
    source = tmp_path / "items.csv"
    source.write_text("itemId,name,marketValue,minBuyout,recent,historical,updatedAt\n" +
        "\n".join(f"{i},Item {i},0,{p},0,0," for i, p in
                  {2592: 10, 4240: 1000, 4338: 100, 10050: 10000,
                   14047: 1000, 8170: 500, 14046: 20000}.items()) + "\n")
    run(sources[0], source)
    monkeypatch.setattr("brownstone.config.read_sources", lambda *args: sources)
    at = AppTest.from_file(str(ROOT / "app.py")).run()
    assert not at.exception
    assert any(m.value == "#### Tailoring Action Board" for m in at.markdown)
    table = next(t.value for t in at.dataframe if "Action" in t.value.columns)
    assert len(table) == 3
    assert table.iloc[0]["Item"] == "Mageweave Bag"
    assert table.iloc[2]["Action"] == "negative margin"
    next(w for w in at.selectbox if w.label == "Rank by").set_value("margin").run()
    assert not at.exception
    table = next(t.value for t in at.dataframe if "Action" in t.value.columns)
    assert table.iloc[0]["Item"] == "Woolen Bag"
    assert any(m.label == "Break-even sale price" for m in at.metric)
    at.radio[0].set_value("Opportunities").run()
    assert not at.exception
    assert any("cannot run" in i.value for i in at.info)  # Classic historical values are zero.
    next(w for w in at.selectbox if w.label == "Data source").set_value(1).run()  # Retail still works.
    at.radio[0].set_value("Browse market").run()
    assert not at.exception
    assert not any(m.value == "#### Tailoring Action Board" for m in at.markdown)
    assert any(h.value == "Browse market" for h in at.subheader)


def test_addon_source_imports_on_click_and_prices_the_forever_board(tmp_path, monkeypatch):
    from test_scans import finished_now, forever_scan_file
    sources = read_sources(ROOT / "config/market.toml")
    addon = next(source for source in sources if source["provider"] == "addon")
    assert not addon["enabled"]  # Disabled in the tracked config; enabled per machine in market.local.toml.
    addon.update(enabled=True, data_dir=tmp_path / "data", scan_path=forever_scan_file(tmp_path, finished_now()),
                 scan_evidence={"faction": "Alliance"})
    monkeypatch.setattr("brownstone.config.read_sources", lambda *args: [addon])
    at = AppTest.from_file(str(ROOT / "app.py")).run()
    assert not at.exception
    assert any("Refresh or import" in i.value for i in at.info)  # Nothing imported until clicked.
    next(b for b in at.button if b.label == "Import addon scan").click().run()
    assert not at.exception
    assert any("Imported" in s.value for s in at.success)
    table = next(t.value for t in at.dataframe if "Action" in t.value.columns)
    assert table.iloc[0]["Item"].startswith("Runecloth Bag") and table.iloc[0]["Action"] == "potential craft"
    assert set(table["Action"][1:]) == {"missing prices"}  # Bags without listings in the fixture scan.


def classic_sources(tmp_path):
    sources = [source for source in read_sources(ROOT / "config/market.toml") if source["enabled"]]
    for source in sources:
        source["data_dir"] = tmp_path / "data"
    return sources


def test_browse_market_lists_saved_items_blanks_zero_prices_and_searches(tmp_path, monkeypatch):
    sources = classic_sources(tmp_path)
    items = tmp_path / "items.csv"
    items.write_text("itemId,name,marketValue,minBuyout,recent,historical,updatedAt\n"
                     "2592,Wool Cloth,0,120,0,0,\n4306,Silk Cloth,900,0,0,0,\n", encoding="utf-8")
    run(sources[0], items)
    monkeypatch.setattr("brownstone.config.read_sources", lambda *args: sources)
    at = AppTest.from_file(str(ROOT / "app.py")).run()
    at.radio[0].set_value("Browse market").run()
    assert not at.exception
    table = at.dataframe[0].value
    assert list(table["Item"]) == ["Silk Cloth", "Wool Cloth"]
    assert table.set_index("Item").loc["Wool Cloth", "Minimum buyout (g)"] == 0.012
    assert table["Market value (g)"].isna().sum() == 1  # Zero is unavailable, shown blank, never free.
    next(t for t in at.text_input if t.label == "Find an item").set_value("silk").run()
    assert list(at.dataframe[0].value["Item"]) == ["Silk Cloth"]
    next(t for t in at.text_input if t.label == "Find an item").set_value("no such item").run()
    assert any("No items match" in i.value for i in at.info)


def test_refresh_reports_success_and_failure_without_losing_saved_data(tmp_path, monkeypatch):
    sources = classic_sources(tmp_path)
    monkeypatch.setattr("brownstone.config.read_sources", lambda *args: sources)
    calls = []

    def offline(config):
        calls.append(config["source_id"])
        if len(calls) == 1:
            raise RuntimeError("network unreachable")

    monkeypatch.setattr("brownstone.pipeline.run", offline)
    at = AppTest.from_file(str(ROOT / "app.py")).run()
    assert not calls  # Opening the app never downloads (UI-01).
    next(b for b in at.button if b.label == "Refresh from TSM").click().run()
    assert any("Refresh failed: network unreachable" in e.value for e in at.error)
    next(b for b in at.button if b.label == "Refresh from TSM").click().run()
    assert any("refreshed and saved" in s.value for s in at.success)
    assert calls == ["classic-us-mankrik-alliance"] * 2


def test_import_of_a_file_without_a_complete_scan_says_prices_are_unchanged(tmp_path, monkeypatch):
    from test_scans import finished_now, scan, write_scans
    addon = next(source for source in read_sources(ROOT / "config/market.toml") if source["provider"] == "addon")
    scan_file = write_scans(tmp_path / "scan.lua", scan("cut-short", finished_now(), [], status="stopped",
                                                        reported=5, house={"zone": "Stormwind City",
                                                                           "npc_name": "Auctioneer Fitch"}))
    addon.update(enabled=True, data_dir=tmp_path / "data", scan_path=scan_file)
    monkeypatch.setattr("brownstone.config.read_sources", lambda *args: [addon])
    at = AppTest.from_file(str(ROOT / "app.py")).run()
    next(b for b in at.button if b.label == "Import addon scan").click().run()
    assert not at.exception
    assert any("No complete scan in the file, so prices are unchanged" in w.value for w in at.warning)


def test_no_enabled_source_explains_how_to_enable_one(monkeypatch):
    monkeypatch.setattr("brownstone.config.read_sources", lambda *args: [])
    at = AppTest.from_file(str(ROOT / "app.py")).run()
    assert not at.exception
    assert any("No enabled data source" in e.value for e in at.error)


def test_importing_nothing_new_warns_to_reload_instead_of_claiming_success(tmp_path, monkeypatch):
    from test_scans import finished_now, forever_scan_file
    addon = next(source for source in read_sources(ROOT / "config/market.toml") if source["provider"] == "addon")
    addon.update(enabled=True, data_dir=tmp_path / "data", scan_path=forever_scan_file(tmp_path, finished_now()),
                 scan_evidence={"faction": "Alliance"})
    monkeypatch.setattr("brownstone.config.read_sources", lambda *args: [addon])
    at = AppTest.from_file(str(ROOT / "app.py")).run()
    next(b for b in at.button if b.label == "Import addon scan").click().run()
    assert any("/bscan clear" in i.value for i in at.info)  # Something new was saved: clearing is safe.
    next(b for b in at.button if b.label == "Import addon scan").click().run()
    assert not at.success
    assert any(w.value.startswith("Nothing new") and "/reload" in w.value for w in at.warning)
