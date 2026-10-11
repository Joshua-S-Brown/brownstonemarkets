"""Offline captured funds, scoping, persistence compatibility and Streamlit summary."""
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from streamlit.testing.v1 import AppTest
from test_character_snapshots import snapshot
from test_characters import fixture
from test_journal import write
from test_scans import NOW
from test_today_characters import CHARACTER, state
from test_today_view import ROOT, app, widget

from brownstone.config import MARKET_KEYS
from brownstone.pipeline import import_scans
from brownstone.professions import latest_data
from brownstone.today_funds import resolve_funds
from brownstone.today_settings import TodaySettings, load_settings, save_settings

TIME = datetime(2026, 10, 11, 10, 57, tzinfo=UTC)


def funds_data(gold=255):
    return {CHARACTER: state(learned=True) | {"bags": {
        "gold_copper": gold, "captured_at": int(TIME.timestamp())}}}


def test_character_gold_old_settings_override_and_integer_units(tmp_path):
    path = tmp_path / "old.json"
    path.write_text('{"gold_copper": 250000, "character": ["Basilly", "Beta", "Alliance"]}')
    saved = load_settings(path)
    funds = resolve_funds(saved, funds_data(), TIME, 24)
    assert not saved.gold_override and funds.settings.gold_copper == 255
    assert "Gold available: 2s 55c (Basilly, captured 2026-10-11 10:57 UTC)" in funds.summary
    assert saved.gold_copper == 250000  # No persistence mutation.
    override = replace(saved, gold_override=True, gold_copper=200)
    assert resolve_funds(override, funds_data(), TIME, 24).settings == override
    assert "(entered amount)" in resolve_funds(override, funds_data(), TIME, 24).summary
    save_settings(path, override)
    assert load_settings(path) == override
    with pytest.raises(ValueError, match="boolean"):
        TodaySettings(gold_override=1)


@pytest.mark.parametrize("data", [funds_data(None), funds_data(True), funds_data(0)])
def test_missing_gold_falls_back_without_borrowing(data):
    data = data | {("Other", "Beta", "Alliance"): {"bags": {
        "gold_copper": 999999, "captured_at": int(TIME.timestamp())}}}
    result = resolve_funds(TodaySettings(17, character=CHARACTER), data, TIME, 24)
    assert result.settings.gold_copper == 17 and result.origin == "entered amount"
    assert result.notes == ("No captured gold for Basilly; using the entered amount.",)


def test_missing_saved_character_totals_like_all_recipes():
    data = {("Other", "Beta", "Alliance"): {"bags": {"gold_copper": 10, "captured_at": int(TIME.timestamp())}}}
    result = resolve_funds(TodaySettings(17, character=CHARACTER), data, TIME, 24)
    assert result.settings.gold_copper == 10 and "across 1 characters" in result.origin


def test_all_recipes_totals_with_missing_and_stale_labels():
    data = funds_data() | {("Other", "Beta", "Alliance"): {"bags": {
        "gold_copper": 10, "captured_at": int((TIME - timedelta(hours=25)).timestamp())}},
        ("Unknown", "Beta", "Alliance"): {"bags": {}}}
    result = resolve_funds(TodaySettings(250000), data, TIME, 24)
    assert result.settings.gold_copper == 265
    assert result.origin == "across 2 characters; gold must be mailed to the crafter"
    assert any("stale gold capture, age 25.0 hours" in n for n in result.notes)
    assert any("Unknown; excluded" in n for n in result.notes)
    selected = resolve_funds(TodaySettings(character=CHARACTER), data, TIME + timedelta(hours=24), 24)
    assert "stale" not in selected.summary
    assert "stale" in resolve_funds(TodaySettings(character=CHARACTER), data,
                                    TIME + timedelta(hours=24, seconds=1), 24).summary


def test_scoped_latest_readable_gold_and_all_market_keys(tmp_path):
    config = fixture(tmp_path)
    outsider = write(tmp_path / "other.lua", [], [(snapshot("other", character="Other") | {"gold_copper": 999999})])
    import_scans(config | {"source_id": "other", "scan_path": outsider}, now=NOW)
    data = latest_data(config)
    result = resolve_funds(TodaySettings(250000), data, NOW, 24)
    assert result.settings.gold_copper == 24690 and "across 2 characters" in result.origin
    alice = ("Alice", "Beta", "Alliance")
    assert data[alice]["bags"]["snapshot_id"] == "new"  # Newer unreadable zero excluded.
    assert resolve_funds(TodaySettings(character=alice), data, NOW, 24).settings.gold_copper == 12345
    for key in ("source_id", *MARKET_KEYS):
        scoped = latest_data(config | {key: "other-scope"})
        result = resolve_funds(TodaySettings(7, character=alice), scoped, NOW, 24)
        assert result.settings.gold_copper == 7 and result.notes


def test_streamlit_recorded_summary_sizing_override_and_fallback(tmp_path, monkeypatch):
    data = funds_data()
    monkeypatch.setattr("brownstone.today_loading.professions.latest_data", lambda config: data)
    _, _, path = app(tmp_path, monkeypatch)
    save_settings(path, TodaySettings(250000, 1, "fixed", character=CHARACTER))
    at = AppTest.from_file(str(ROOT / "app.py")).run()
    assert not at.exception
    assert any("Gold available: 2s 55c (Basilly, captured" in c.value for c in at.caption)
    assert sum(round(v * 10000) for v in at.tabs[1].dataframe[0].value['Cost (g)']) <= 255
    widget(at.toggle, "Enter an amount instead").set_value(True)
    widget(at.text_input, "Gold available").set_value("1s")
    widget(at.button, "Save Today settings").click().run()
    assert load_settings(path).gold_override
    assert any("Gold available: 1s (entered amount)" in c.value for c in at.caption)
    data[CHARACTER]["bags"] = {}
    widget(at.toggle, "Enter an amount instead").set_value(False)
    widget(at.button, "Save Today settings").click().run()
    assert any(c.value == "No captured gold for Basilly; using the entered amount." for c in at.caption)


def test_newest_gold_sequence_bank_independence_and_duplicate_import(tmp_path):
    from test_scans import addon_source
    records = [snapshot('first', sequence=1) | {'gold_copper': 11},
               snapshot('second', sequence=2) | {'gold_copper': 22},
               snapshot('bank', kind='bank', sequence=3) | {'gold_copper': 99}]
    path = write(tmp_path / 'captures.lua', [], records)
    config = addon_source(tmp_path / 'data', path)
    import_scans(config, now=NOW)
    import_scans(config, now=NOW)
    data = latest_data(config)
    assert len(data[('Alice', 'Beta', 'Alliance')]['history']) == 2
    funds = resolve_funds(TodaySettings(), data, NOW, 24)
    assert funds.settings.gold_copper == 22


def test_streamlit_all_recipes_recorded_total_summary(tmp_path, monkeypatch):
    monkeypatch.setattr('brownstone.today_loading.professions.latest_data', lambda config: funds_data())
    at, _, path = app(tmp_path, monkeypatch)
    assert not at.exception
    assert any('Gold available: 2s 55c (across 1 characters; gold must be mailed to the crafter)'
               in c.value for c in at.caption)
    assert load_settings(path).gold_copper == 100000  # Resolved funds are never saved automatically.


def test_shared_loader_matches_plan_with_same_funds(tmp_path, monkeypatch):
    from test_today import catalog

    from brownstone.crafting import parse_recipe_catalog
    from brownstone.today import build_today
    from brownstone.today_loading import load_today
    _, source, path = app(tmp_path, monkeypatch)
    settings = replace(load_settings(path), character=CHARACTER)
    catalogs = [parse_recipe_catalog(catalog()) | {'catalog_id': 'fixture'}]
    now = datetime.now(UTC)
    _, arguments = load_today(source, catalogs, settings, funds_data(), now)
    assert arguments['settings'].gold_copper == 255
    result = build_today(**arguments)
    expected = build_today(**(arguments | {'settings': replace(settings, gold_copper=255)}))
    assert result == expected and result['today_version'] == 5
    assert result['shopping_total_copper'] <= 255
