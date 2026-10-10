"""Offline character eligibility, exact ID matching and unchanged funded planning."""
from copy import deepcopy
from dataclasses import replace

import pytest
from streamlit.testing.v1 import AppTest
from test_characters import fixture
from test_today import catalog, output_catalog, plan
from test_today_view import ROOT, app, widget

from brownstone.professions import latest_data
from brownstone.today_characters import (
    available_characters,
    catalog_check,
    project_recipes,
    recipe_status,
    resolve_character,
)
from brownstone.today_settings import TodaySettings, load_settings, save_settings
from views.today import _character_columns, _filter_confidence

CHARACTER = ("Basilly", "Beta", "Alliance")


def state(*, learned=False, incomplete=False, rank=8, recipe_id=30):
    return {"bags": {}, "seen": {}, "recipes": {"Arbitrary title": {
        "captured_at": 100, "sequence": 2, "known_recipes": {
            "rank": rank, "skill_id": 197, "possibly_incomplete": incomplete,
            "rows": [{"recipe_id": recipe_id, "name": "Fixture craft", "learned": learned}]}}}}


def recipe(**changes):
    return catalog()["recipes_by_id"][30] | {"learned_from": [6], "required_skill": 8} | changes


@pytest.mark.parametrize("changes,evidence,status,reason", [
    ({}, state(learned=True), "Known", ""),
    ({}, state(learned=True, incomplete=True), "Known", ""),
    ({"learned_from": [5]}, state(rank=None), "Not yet", "needs pattern or other source"),
    ({"training_cost_copper": 100}, state(), "Train now", ""),
    ({"learned_from": [2, 6]}, state(), "Train now", ""),
    ({}, state(rank=7), "Not yet", "rank below required skill"),
    ({"learned_from": [2, 5, 16]}, state(), "Not yet", "needs pattern or other source"),
    ({"learned_from": None}, state(), "Unknown", "how it's learned is unknown"),
    ({}, state(learned=None), "Unknown", "learned flag unknown"),
    ({}, state(incomplete=True), "Unknown", "possibly incomplete list"),
    ({}, state(incomplete=True, recipe_id=31), "Unknown", "recipe not listed"),
    ({}, state(rank=None), "Unknown", "rank unknown"),
])
def test_statuses(changes, evidence, status, reason):
    result = recipe_status(recipe(**changes), evidence)
    assert result["craft_status"] == status and result["character_reason"] == reason


def test_id_only_latest_containing_list_and_seen_crafted():
    evidence = state(learned=True, recipe_id=31)
    evidence["recipes"]["Arbitrary title"]["known_recipes"]["rows"][0].update(item_id=3, spell_id=30)
    assert recipe_status(recipe(), evidence)["craft_status"] == "Unknown"
    evidence["seen"] = {"Unknown profession": {30: {}}}
    assert recipe_status(recipe(), evidence)["craft_status"] == "Known"
    evidence = state(learned=True)
    evidence["recipes"]["Another title"] = deepcopy(state()["recipes"]["Arbitrary title"])
    evidence["recipes"]["Another title"]["sequence"] = 3
    assert recipe_status(recipe(), evidence)["craft_status"] == "Train now"


@pytest.mark.parametrize("time,sequence,skill_id,expected", [(101, 1, 197, "Train now"),
    (100, 3, 197, "Train now"), (100, 1, 197, "Not yet"), (101, 1, 999, "Not yet")])
def test_newer_bags_rank_by_skill_id(time, sequence, skill_id, expected):
    evidence = state(rank=7)
    surface = evidence["recipes"]["Arbitrary title"]["known_recipes"]
    surface.pop("skill_id")
    surface["profession"] = {"GetBaseProfessionInfo": {"1": {"professionID": 197}}}
    evidence["bags"] = {"captured_at": time, "sequence": sequence, "skills": {"modern": {"rows": [
        {"name": "Different name", "rank": 8, "skill_id": skill_id}]}}}
    assert recipe_status(recipe(), evidence)["craft_status"] == expected


def test_training_cost_display_not_subtracted_and_unknown_cost():
    c = catalog()
    c["recipes_by_id"][30].update(learned_from=[6], training_cost_copper=100)
    settings = TodaySettings(10000, 1, "fixed", character=CHARACTER)
    original = plan(catalogs=[c])
    result = plan(settings, catalogs=[c], character_data={CHARACTER: state()})
    for field in ("batch_profit_copper", "batch_cost_copper", "batch_size", "purchases", "plan_order"):
        assert result["craft"][0][field] == original["craft"][0][field]
    assert result["queue"] == original["queue"] and result["buy"] == original["buy"]
    assert _character_columns(result["craft"][0]) == {"Can make": "Train now", "Learning": "Training: 1s"}
    c["recipes_by_id"][30].pop("training_cost_copper")
    result = plan(settings, catalogs=[c], character_data={CHARACTER: state()})
    assert _character_columns(result["craft"][0])["Learning"] == "Training: cost unknown"


def test_filter_before_plan_reservations_and_queue_unknown_kept():
    c = catalog()
    c["recipes_by_id"][30].update(learned_from=[6], required_skill=9)
    settings = TodaySettings(10000, 1, "fixed", character=CHARACTER)
    result = plan(settings, catalogs=[c], character_data={CHARACTER: state()})
    assert not result["craft"] and not result["queue"]["lines"] and not result["buy"]
    assert result["hidden"]["rank below required skill"] == 1
    result = plan(settings, catalogs=[c], character_data={CHARACTER: state(incomplete=True)})
    assert result["craft"][0]["craft_status"] == "Unknown"
    low = {**result, "craft": [r | {"confidence": "Low"} for r in result["craft"]]}
    visible, hidden = _filter_confidence(low, True)
    assert visible == [] and hidden["low confidence"] == 1  # eligibility keeps Unknown; Hide Low still applies


def test_rank_ignores_unreadable_newer_bags_and_malformed_profession_id():
    evidence = state(rank=8)
    surface = evidence["recipes"]["Arbitrary title"]["known_recipes"]
    surface["profession"] = {"GetBaseProfessionInfo": {"1": {"professionID": None}}}
    evidence["bags"] = {"captured_at": 200, "sequence": 1, "skills": {"modern": {"rows": [
        {"name": "Tailoring", "rank": None, "skill_id": 197}]}}}
    assert recipe_status(recipe(), evidence)["craft_status"] == "Train now"


def test_who_can_make_it_and_missing_character_fallback():
    data = {CHARACTER: state(learned=True), ("Other", "Beta", "Alliance"): state(),
            ("No evidence", "Beta", "Alliance"): {"recipes": {}, "seen": {}}}
    c = catalog()
    c["recipes_by_id"][30].update(learned_from=[6])
    projection = project_recipes([c], data, None)
    assert projection["statuses"][("fixture", 30)]["who_can_make_it"] == ["Basilly", "Other"]
    assert resolve_character(("Gone", "Beta", "Alliance"), data) is None
    assert len(available_characters(data)) == 2
    result = plan(catalogs=[c], character_data=data)
    assert _character_columns(result["craft"][0])["Who can make it"] == "Basilly, Other"


def test_catalog_differences_optional_and_legacy_reagents():
    r = recipe()
    row = {"item_id": 4, "min_made": 2, "max_made": 2,
           "reagents": [{"item_id": 1, "count": 3}]}
    assert catalog_check(r, row) == ["output item differs", "yield differs", "required reagents differ"]
    assert catalog_check(r, {"reagents": [{"item_id": 1}]}) == [
        "not compared: required reagents unreadable"]
    row = {"item_id": 3, "min_made": 1, "max_made": 1, "schematic": {"reagentSlotSchematics": [
        {"required": True, "quantityRequired": 2, "reagents": [{"itemID": 1}]},
        {"required": True, "quantityRequired": 1, "reagents": [{"itemID": 2}]}]}}
    assert catalog_check(r, row) == []
    row["schematic"]["reagentSlotSchematics"][0]["quantityRequired"] = 3
    assert catalog_check(r, row) == ["required reagents differ"]
    row["schematic"]["reagentSlotSchematics"][0]["required"] = False
    assert catalog_check(r, row)[0].startswith("not compared")
    row["schematic"]["reagentSlotSchematics"][0].update(required=True, reagents=[{"itemID": 1}, {"itemID": 4}])
    assert catalog_check(r, row)[0].startswith("not compared")
    evidence = state()
    evidence["recipes"]["Arbitrary title"]["known_recipes"]["rows"] = [row | {"recipe_id": 30}]
    assert project_recipes([catalog()], {CHARACTER: evidence}, CHARACTER)["catalog_checks"][0]["Check"].startswith(
        "not compared")


def test_settings_round_trip_old_files_invalid_identity(tmp_path):
    path = tmp_path / "settings.json"
    value = TodaySettings(10000, character=CHARACTER)
    save_settings(path, value)
    assert load_settings(path) == value
    path.write_text('{"gold_copper": 10000}')
    assert load_settings(path).character is None
    for invalid in ("Basilly", ["Basilly"], ["Basilly", "Beta", 1], ["", "Beta", "Alliance"]):
        with pytest.raises(ValueError):
            TodaySettings(character=invalid)


def test_shared_projection_scopes_source_and_market(tmp_path):
    config = fixture(tmp_path)
    data = latest_data(config)
    assert available_characters(data) == [("Alice", "Beta", "Alliance")]
    assert not available_characters(latest_data(config | {"source_id": "other"}))
    assert not available_characters(latest_data(config | {"realm": "other"}))


def test_today_apptest_character_save_status_cost_checks_and_missing(tmp_path, monkeypatch):
    data = {CHARACTER: state()}
    c = catalog()
    c["recipes_by_id"][30].update(learned_from=[6], training_cost_copper=100)
    monkeypatch.setattr("views.today.professions.latest_data", lambda config: data)
    at, _, path = app(tmp_path, monkeypatch)
    monkeypatch.setattr("brownstone.recipe_catalogs.find_catalogs", lambda *args: [{"name": "fixture", "catalog": c}])
    at.run()
    assert not at.exception and not at.error, str(at.exception) + str([e.value for e in at.error])
    assert at.tabs[0].dataframe[0].value["Who can make it"].tolist() == ["Basilly"]
    widget(at.selectbox, "Character").select(CHARACTER)
    widget(at.button, "Save Today settings").click().run()
    assert not at.exception and load_settings(path).character == CHARACTER
    table = at.tabs[0].dataframe[0].value
    assert table["Can make"].tolist() == ["Train now"] and table["Learning"].tolist() == ["Training: 1s"]
    again = AppTest.from_file(str(ROOT / "app.py")).run()
    assert not again.exception and widget(again.selectbox, "Character").value == CHARACTER
    save_settings(path, replace(load_settings(path), character=("Gone", "Beta", "Alliance")))
    again = AppTest.from_file(str(ROOT / "app.py")).run()
    assert not again.exception and any("no longer present" in v.value for v in again.caption)
    assert "Who can make it" in again.tabs[0].dataframe[0].value


def test_today_apptest_unreadable_character_evidence_still_shows_all_recipes(tmp_path, monkeypatch):
    def broken(config):
        raise OSError("journal locked")
    monkeypatch.setattr("views.today.professions.latest_data", broken)
    at, _, _ = app(tmp_path, monkeypatch)
    assert not at.exception and not at.error
    assert any("journal locked" in w.value for w in at.warning)
    assert "Who can make it" in at.tabs[0].dataframe[0].value


def test_filtered_plan_matches_same_set_including_shared_reservations_and_choices():
    first, second, hidden = catalog(), output_catalog(4, "second"), output_catalog(5, "hidden")
    for c in (first, second):
        c["recipes_by_id"][30]["learned_from"] = [6]
    hidden["recipes_by_id"][31] = hidden["recipes_by_id"].pop(30) | {
        "recipe_id": 31, "learned_from": [5]}
    hidden["recipe_for_output"][5] = 31
    evidence = state(learned=True)
    evidence["recipes"]["Arbitrary title"]["known_recipes"]["rows"].append({"recipe_id": 31, "learned": False})
    settings = TodaySettings(1000, 1, "fixed", max_crafts=1, character=CHARACTER)
    arguments = dict(settings=settings, observations={1: {"min_buyout": 10, "market_value": 20},
                        3: {"min_buyout": 200}, 4: {"min_buyout": 200}, 5: {"min_buyout": 2000}},
                     listings={1: [(3, 30, 10), (4, 80, 20)]}, character_data={CHARACTER: evidence})
    expected = plan(catalogs=[first, second], **arguments)
    filtered = plan(catalogs=[first, second, hidden], **arguments)
    # The inherited board rank includes excluded rows; relative plan order and all plan numbers agree.
    def crafts(result):
        return [{k: v for k, v in row.items() if k != "rank"} for row in result["craft"]]
    assert crafts(filtered) == crafts(expected)
    for field in ("buy", "sell", "queue", "shopping_total_copper", "choice_limits"):
        assert filtered[field] == expected[field]
    assert filtered["hidden"] == {"needs pattern or other source": 1}
    choices = [{"catalog_id": "fixture", "recipe_id": 30, "batch_size": None}]
    for refill in (True, False):
        expected = plan(catalogs=[first, second], choices=choices, refill=refill, **arguments)
        filtered = plan(catalogs=[first, second, hidden], choices=choices, refill=refill, **arguments)
        assert crafts(filtered) == crafts(expected) and filtered["queue"] == expected["queue"]


def test_today_apptest_unknown_cost_catalog_differences_and_changed_evidence(tmp_path, monkeypatch):
    data = {CHARACTER: state()}
    c = catalog()
    c["recipes_by_id"][30].update(learned_from=[6])
    row = data[CHARACTER]["recipes"]["Arbitrary title"]["known_recipes"]["rows"][0]
    row.update(item_id=4, min_made=2)
    monkeypatch.setattr("views.today.professions.latest_data", lambda config: data)
    at, _, path = app(tmp_path, monkeypatch)
    monkeypatch.setattr("brownstone.recipe_catalogs.find_catalogs", lambda *args: [{"name": "fixture", "catalog": c}])
    save_settings(path, replace(load_settings(path), character=CHARACTER))
    at = AppTest.from_file(str(ROOT / "app.py")).run()
    assert not at.exception and at.tabs[0].dataframe[0].value["Learning"].tolist() == ["Training: cost unknown"]
    checks = next(e for e in at.expander if e.label == "Catalog checks")
    assert not checks.proto.expanded
    assert checks.dataframe[0].value["Check"].tolist() == ["output item differs; yield differs"]
    row["learned"] = True
    at.run()
    assert not at.exception and at.tabs[0].dataframe[0].value["Can make"].tolist() == ["Known"]
    assert any("session choices and queue ticks reset" in e.value for e in at.info)
