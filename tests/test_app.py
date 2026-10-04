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
