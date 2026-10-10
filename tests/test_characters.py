"""Offline character cards share the import projections, never local beta data."""
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest
from test_character_snapshots import snapshot
from test_journal import entry, write
from test_scans import FINISHED, NOW, addon_source

from brownstone import character_snapshots, characters, professions
from brownstone.config import MARKET_KEYS
from brownstone.pipeline import import_scans


def fixture(tmp_path):
    skills = {"modern": {"api": "GetProfessionInfo", "rows": [
        {"name": "Tailoring", "skill_id": 197, "rank": 75, "max_rank": 75}], "possibly_incomplete": True}}
    old = snapshot("old", level=8, skills=skills, sequence=1)
    newer = snapshot("new", level=9, skills={"modern": {"rows": [
        {"name": "Tailoring", "skill_id": 197, "rank": 76, "max_rank": 150}]}}, sequence=2)
    newer.update(captured_at=FINISHED + 1)
    newer.pop("captured_at_utc")
    broken = snapshot("broken", level=1, sequence=3)
    broken.update(captured_at=FINISHED + 2, gold_copper=0, containers=[{"container_id": 0, "size": 0}])
    broken.pop("captured_at_utc")
    listed = entry("list")
    listed.update(family="craft", known_recipes={"name": "Tailoring", "api": "C_TradeSkillUI",
        "counts": {1: 3}, "possibly_incomplete": True, "rows": [
            {"type": "recipe", "recipe_id": 2963, "learned": True},
            {"type": "recipe", "recipe_id": 3755, "learned": False}, {"type": "recipe", "recipe_id": 9}]})
    hook = entry("craft")
    hook.update(family="craft", event="C_TradeSkillUI.CraftRecipe", arguments={1: 3755, "n": 1}, sequence=4)
    path = write(tmp_path / "mac.lua", [listed, hook], [old])
    config = addon_source(tmp_path / "data", path)
    import_scans(config, now=NOW)
    path = write(tmp_path / "pc.lua", [], [newer, broken, snapshot("bob", character="Bob")])
    import_scans(config | {"scan_path": path, "machine": "windows-pc"}, now=NOW)
    return config


def test_cards_two_machines_history_unreadable_and_recipe_union(tmp_path):
    config = fixture(tmp_path)
    alice, bob = characters.build_characters(config, NOW)
    assert alice["name"] == "Alice" and alice["machine"] == "windows-pc"
    assert alice["level"] == 9 and alice["gold_copper"] == 12345 and not alice["stale"]
    assert bob["name"] == "Bob" and bob["machine"] == "windows-pc" and bob["skills_status"] == "skills unknown"
    assert character_snapshots.latest_data(config)[("Alice", "Beta", "Alliance")]["observations"][0][1] == "mac"
    tailoring = alice["professions"][0]
    assert tailoring["known_count"] == 2 and tailoring["recipe_source"] == "window list + seen crafted"
    assert tailoring["listed_count"] == 1 and tailoring["seen_ids"] == [3755] and tailoring["possibly_incomplete"]
    assert not tailoring["at_cap"] and tailoring["progress"] == 76 / 150
    assert [r["Value"] for r in alice["history"] if r["Series"] == "Level"] == [8, 9]
    assert [r["Value"] for r in alice["history"] if r["Series"] == "Tailoring"] == [75, 76]
    assert professions.latest_rows(config)[0]["Level"] == 9  # Import table contract retained.


def test_at_cap_staleness_boundary_unknown_gold_and_no_readable_bags(tmp_path):
    config = fixture(tmp_path)
    key = ("Alice", "Beta", "Alliance")
    state = professions.latest_data(config)[key]
    old = state["history"][0]
    state["bags"] = old
    card = characters._card(key, state, datetime.fromtimestamp(FINISHED, UTC) + timedelta(days=7))
    assert not card["stale"] and card["professions"][0]["at_cap"]
    assert card["skills_status"] == "possibly incomplete"
    assert characters._card(key, state, NOW + timedelta(days=8))["stale"]
    broken = snapshot("only")
    broken.update(containers=[{"container_id": 0, "size": 0}], gold_copper=0, level=1)
    path = write(tmp_path / "unknown.lua", [], [broken])
    unknown = config | {"source_id": "unknown", "scan_path": path}
    import_scans(unknown, now=NOW)
    card = characters.build_characters(unknown, NOW)[0]
    assert card["level"] is None and card["gold_copper"] is None and card["bags_at"] is None
    assert card["skills_status"] == "skills unknown" and card["history"] == []
    broken.update(snapshot_id="nullable", containers=[{"container_id": 0, "size": 2}], gold_copper=None)
    broken.pop("gold_copper")
    write(path, [], [broken])
    import_scans(unknown, now=NOW)
    assert characters.build_characters(unknown, NOW)[0]["gold_copper"] is None


def test_empty_and_every_scope_key(tmp_path):
    assert characters.build_characters(addon_source(tmp_path / "absent"), NOW) == []
    config = fixture(tmp_path)
    path = write(tmp_path / "outsider.lua", [], [snapshot("outsider", character="Outsider")])
    import_scans(config | {"source_id": "second-source", "scan_path": path}, now=NOW)
    assert {r["name"] for r in characters.build_characters(config, NOW)} == {"Alice", "Bob"}
    for key in MARKET_KEYS:
        assert characters.build_characters(config | {key: str(config[key]) + "_other"}, NOW) == []


def test_recipe_only_seen_and_journal_last_seen(tmp_path, monkeypatch):
    monkeypatch.setattr(professions, "_catalog_recipe_ids", lambda _: {2963: {"Tailoring"}})
    hook = entry("hook")
    hook.update(family="craft", event="C_TradeSkillUI.CraftRecipe", arguments={1: 2963, "n": 1})
    path = write(tmp_path / "only.lua", [hook])
    config = addon_source(tmp_path / "data", path)
    import_scans(config, now=NOW)
    card = characters.build_characters(config, NOW)[0]
    assert card["machine"] == "mac" and card["level"] is None
    assert card["professions"][0]["known_count"] == 1
    assert card["professions"][0]["recipe_source"] == "seen crafted"
    assert card["professions"][0]["progress"] is None


@pytest.mark.parametrize("seconds, expected", [(0, "just now"), (60, "1 minute ago"), (7200, "2 hours ago"),
                                              (86400, "1 day ago"), (-1, "in the future")])
def test_relative_time(seconds, expected):
    assert characters.relative_time(NOW - timedelta(seconds=seconds), NOW) == expected


def test_apptest_navigation_cards_chart_and_empty(tmp_path, monkeypatch):
    config = fixture(tmp_path)
    monkeypatch.setattr("brownstone.config.read_sources", lambda *a: [config])
    monkeypatch.setattr("brownstone.recipe_catalogs.find_catalogs", lambda *a: [])
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run()
    assert at.radio[0].options[:2] == ["Today", "Characters"]
    at.radio[0].set_value("Characters").run()
    assert not at.exception
    assert [m.value for m in at.metric] == ["9", "1g 23s 45c", "unknown", "1g 23s 45c"]
    assert any("Known recipes: 2" in c.value for c in at.caption)
    assert len(at.get("vega_lite_chart")) == 1
    assert all(not e.proto.expanded for e in at.expander if e.label == "Progress over time")
    assert at.dataframe[0].value["Value"].tolist() == [8, 75, 9, 76]
    monkeypatch.setattr("views.characters.build_characters", lambda _: [])
    at.run()
    assert any("Use Import addon scan" in i.value for i in at.info)
    assert not at.metric


def test_apptest_unknown_gold_badges_and_error(tmp_path, monkeypatch):
    config = fixture(tmp_path)
    cards = characters.build_characters(config, NOW + timedelta(days=8))
    cards[0].update(gold_copper=None, skills_status="possibly incomplete")
    cards[0]["professions"][0].update(at_cap=True, progress=None, rank=None)
    cards[1]["professions"] = [{**cards[0]["professions"][0], "recipe_source": "seen crafted"}]
    monkeypatch.setattr("views.characters.build_characters", lambda _: cards)
    at = AppTest.from_string('from views.characters import render\nrender({"source_id": "s", "market_id": "m"})').run()
    assert not at.exception and at.metric[1].value == "unknown"
    markdown = " ".join(m.value for m in at.markdown)
    assert "stale" in markdown and "at cap" in markdown and "possibly incomplete" in markdown
    def fail(_):
        raise ValueError("fixture error")
    monkeypatch.setattr("views.characters.build_characters", fail)
    at.run()
    assert "fixture error" in at.error[0].value


def test_apptest_unreadable_only_and_readable_empty_skill_list(tmp_path, monkeypatch):
    record = snapshot("unreadable", level=1)
    record.update(containers=[{"container_id": 0, "size": 0}], gold_copper=0)
    path = write(tmp_path / "only.lua", [], [record])
    config = addon_source(tmp_path / "data", path)
    import_scans(config, now=NOW)
    cards = characters.build_characters(config, NOW)
    monkeypatch.setattr("views.characters.build_characters", lambda _: cards)
    at = AppTest.from_string('from views.characters import render\nrender({"source_id": "s", "market_id": "m"})').run()
    assert not at.exception and [m.value for m in at.metric] == ["unknown", "unknown"]
    assert any("No readable bags" in c.value for c in at.caption)
    assert any("No readable level" in c.value for c in at.caption)
    assert "skills unknown" in " ".join(m.value for m in at.markdown)
    record.update(snapshot_id="readable", containers=[{"container_id": 0, "size": 2}],
                  skills={"modern": {"indexes": {"n": 0}, "rows": []}})
    write(path, [], [record])
    import_scans(config, now=NOW)
    cards[:] = characters.build_characters(config, NOW)
    at.run()
    assert not at.exception and at.metric[1].value == "0c"
    assert any("No skill lines reported" in c.value for c in at.caption)
    record.update(snapshot_id="skill-only", sequence=1, level=4, skills={"modern": {"rows": [
        {"name": "Tailoring", "skill_id": 197, "rank": 75, "max_rank": 75}]}})
    write(path, [], [record])
    import_scans(config, now=NOW)
    cards[:] = characters.build_characters(config, NOW)
    at.run()
    assert not at.exception and cards[0]["professions"][0]["known_count"] is None
    assert any("Known recipes: unknown" in c.value for c in at.caption)
    assert "at cap: train the next tier" in " ".join(m.value for m in at.markdown)
