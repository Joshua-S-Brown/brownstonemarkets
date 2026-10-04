"""Offline UI smoke test using an isolated saved Classic snapshot."""
from pathlib import Path

import pytest

st = pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest
from brownstone.config import read_config
from brownstone.pipeline import run

ROOT = Path(__file__).resolve().parents[1]


def test_action_board_saved_snapshot_and_retail_browse(tmp_path, monkeypatch):
    config = read_config(ROOT / "config/market.toml")
    for source in config["sources"]:
        source["data_dir"] = tmp_path / "data"
    source = tmp_path / "items.csv"
    source.write_text("itemId,name,marketValue,minBuyout,recent,historical,updatedAt\n" +
        "\n".join(f"{i},Item {i},0,{p},0,0," for i, p in
                  {2592: 10, 4240: 1000, 4338: 100, 10050: 10000,
                   14047: 1000, 8170: 500, 14046: 20000}.items()) + "\n")
    run(config["sources"][0], source)
    monkeypatch.setattr("brownstone.config.read_config", lambda path: config)
    at = AppTest.from_file(str(ROOT / "app.py")).run()
    assert not at.exception
    assert any(h.value == "Classic Tailoring Action Board v0.1" for h in at.subheader)
    table = next(t.value for t in at.dataframe if "Action" in t.value.columns)
    assert len(table) == 3
    assert table.iloc[0]["Bag"] == "Mageweave Bag"
    assert table.iloc[2]["Action"] == "negative margin"
    next(w for w in at.selectbox if w.label == "Rank by").set_value("margin").run()
    assert not at.exception
    table = next(t.value for t in at.dataframe if "Action" in t.value.columns)
    assert table.iloc[0]["Bag"] == "Woolen Bag"
    assert any(m.label == "Break-even output unit price" for m in at.metric)
    next(w for w in at.selectbox if w.label == "Data source").set_value(1).run()  # Retail keeps its existing view available.
    at.radio[0].set_value("Browse market").run()
    assert not at.exception
    assert not any(h.value == "Classic Tailoring Action Board v0.1" for h in at.subheader)
