"""Offline skill/window capture and shared import-page evidence."""
import copy
import gzip

import pytest
from test_addon import ROOT, python_value
from test_character_snapshots import capture_client, snapshot
from test_journal import entries, entry, fire, journal_client, write
from test_scans import NOW, addon_source

from brownstone import professions
from brownstone.config import MARKET_KEYS
from brownstone.pipeline import import_scans, preview_scans


def test_skills_both_apis_level_missing_and_raw_tuples():
    lua, g, _ = journal_client()
    lua.execute('''
        function UnitLevel() return 22 end
        function GetNumSkillLines() return 3 end
        function GetSkillLineInfo(i)
            if i == 1 then return "Professions", true, false end
            if i == 2 then return "Mining", false, false, 55, nil, nil, 75 end
            return "First Aid", false, false, 10, nil, nil, 75
        end
        function GetProfessions() return 1, nil, 3 end
        function GetProfessionInfo(i) return i == 1 and "Engineering" or "Cooking", nil, 20, 75, nil, nil, 202 end
    ''')
    fire(g, "PLAYER_LOGOUT")
    record = python_value(g.BrownstoneScanDB.snapshots)[-1]
    assert record["level"] == 22 and record["addon_version"] == "0.11.2"
    assert record["skills"]["legacy"]["rows"][1]["rank"] == 55
    assert "skill_id" not in record["skills"]["legacy"]["rows"][1]
    assert record["skills"]["modern"]["indexes"]["n"] == 3
    assert record["skills"]["modern"]["rows"][1]["skill_id"] == 202
    lua.execute('UnitLevel=nil; GetNumSkillLines=nil; GetProfessions=nil')
    fire(g, "PLAYER_LOGOUT")
    record = python_value(g.BrownstoneScanDB.snapshots)[-1]
    assert "level" not in record and record["skills"] == {}


@pytest.mark.parametrize("craft", [False, True])
def test_recipe_windows_change_only_raw_quantities_filters_missing_no_actions(craft):
    lua, g, _ = journal_client()
    prefix = "GetCraft" if craft else "GetTradeSkill"
    event = "CRAFT" if craft else "TRADE_SKILL"
    line = "GetCraftDisplaySkillLine" if craft else "GetTradeSkillLine"
    count = "GetNumCrafts" if craft else "GetNumTradeSkills"
    lua.execute(f'''
        rowCount, expanded, filtered, forbiddenCalls = 2, false, false, 0
        function {line}() return "Engineering", 20, 75 end
        function {count}() return rowCount end
        function {prefix}Info(i)
            if i == 1 then return "Parts", { 'nil, "header", 0, expanded' if craft else '"header", 0, expanded' } end
            return "Part", { 'nil, "optimal", 2, nil' if craft else '"optimal", 2, nil' }
        end
        function {prefix}RecipeLink() return "|Henchant:123|h" end
        function {prefix}ItemLink() return "|Hitem:456|h" end
        function {prefix}NumMade() return 2, 3 end
        function {prefix}NumReagents() return 2 end
        function {prefix}ReagentInfo(_, i) return "Ore", nil, i + 1, nil end
        function {prefix}ReagentItemLink(_, i) if i == 1 then return "|Hitem:789|h" end end
        function {prefix}SubClasses() return "Parts", "Tools" end
        function {prefix}SubClassFilter() return not filtered end
        function {prefix}OnlyShowMakeable() return filtered end
        function forbidden() forbiddenCalls = forbiddenCalls + 1; error("mutation") end
        DoCraft, DoTradeSkill, LearnSpell, CastSpellByName = forbidden, forbidden, forbidden, forbidden
        ExpandCraftSkillLine, ExpandTradeSkillSubClass = forbidden, forbidden
        SetTradeSkillSubClassFilter, SetTradeSkillInvSlotFilter = forbidden, forbidden
    ''')
    before = len(g.messages)
    fire(g, event + "_SHOW")
    state = entries(g)[-1]["known_recipes"]
    assert state["possibly_incomplete"] is True
    row = state["rows"][1]
    assert row["recipe_id"] == 123 and row["min_made"] == 2 and row["max_made"] == 3
    assert row["reagents"][0]["item_id"] == 789 and row["reagents"][1]["count"] == 3
    assert "item_link" not in row["reagents"][1] and "item_id" not in row["reagents"][1]
    first = len(entries(g))
    fire(g, event + "_UPDATE")
    assert len(entries(g)) == first
    lua.execute('rowCount = 3; expanded = true')
    fire(g, event + "_UPDATE")
    assert len(entries(g)) == first + 1 and not entries(g)[-1]["known_recipes"]["possibly_incomplete"]
    lua.execute('filtered = true')
    fire(g, event + "_UPDATE")
    assert entries(g)[-1]["known_recipes"]["possibly_incomplete"] is True
    fire(g, "PLAYER_LOGOUT")
    assert g.BrownstoneScanDB.snapshots[1].sequence > g.BrownstoneScanDB.journal[len(entries(g))].sequence
    assert len(g.messages) == before and g.forbiddenCalls == 0
    lua.execute(f'{line}=nil; {count}=nil')
    fire(g, event + "_UPDATE")
    assert len(entries(g)) == first + 2


@pytest.mark.parametrize("event", ["TRADE_SKILL_SHOW", "TRADE_SKILL_UPDATE", "CRAFT_SHOW", "CRAFT_UPDATE"])
def test_profession_rejected_registration(event):
    lua, g = capture_client()
    lua.execute(f'''local original = CreateFrame
        function CreateFrame(...)
            local frame = original(...)
            function frame:RegisterEvent(e) if e == "{event}" then error("unsupported") end end
            return frame
        end''')
    lua.execute((ROOT / "addon/BrownstoneScan/BrownstoneScan.lua").read_text())
    fire(g, "ADDON_LOADED", "BrownstoneScan")
    assert event in python_value(g.BrownstoneScanDB.journal_diagnostics)["rejected_events"]


def recipes(eid="recipes", **extra):
    record = entry(eid)
    record.update(family="craft", sequence=3, known_recipes={"name": "Engineering", "counts": {1: 2, "n": 1},
                  "rows": [{"type": "header"}, {"type": "optimal"}], "possibly_incomplete": True})
    record.update(extra)
    return record


def test_profession_import_scope_latest_unknown_dedup_conflict_exact_bronze(tmp_path):
    alice = snapshot(level=22, skills={"legacy": {"api": "GetSkillLineInfo", "rows": [
        {"name": "Mining", "rank": 55, "max_rank": 75}, {"name": "Engineering", "rank": 20, "max_rank": 75}]}})
    bob = snapshot("bob", character="Bob")
    path = write(tmp_path / "own.lua", [recipes()], [alice, bob])
    config = addon_source(tmp_path / "data", path)
    assert professions.latest_rows(config) == []
    preview = preview_scans(config, now=NOW)
    result = import_scans(config, reviewed=preview, now=NOW)
    rows = professions.latest_rows(config)
    engineering, mining, unknown = rows
    assert engineering["Listed recipes"] == 1 and engineering["Level"] == 22
    assert engineering["Rank"] == 20 and engineering["Possibly incomplete"] is True
    assert mining["Known recipes (UTC)"] == "known recipes unknown" and mining["Listed recipes"] is None
    assert unknown["Skills"] == "skills unknown" and unknown["Level"] is None
    for field in ("source_id", *MARKET_KEYS):
        assert professions.latest_rows(config | {field: str(config[field]) + "_other"}) == []
    assert not preview_scans(config, now=NOW).new_record_ids
    blobs = list((config["data_dir"] / "bronze").rglob("*.gz"))
    assert any(gzip.decompress(p.read_bytes()) == path.read_bytes() for p in blobs)
    assert result
    later = recipes("later", sequence=4)
    later["known_recipes"].update(counts={1: 0, "n": 1}, rows=[], possibly_incomplete=False)
    write(path, [later])
    import_scans(config, reviewed=preview_scans(config, now=NOW), now=NOW)
    assert professions.latest_rows(config)[0]["Listed recipes"] == 0
    changed = copy.deepcopy(later)
    changed["known_recipes"]["name"] = "Other"
    write(path, [changed])
    with pytest.raises(ValueError, match="conflict"):
        preview_scans(config, now=NOW)


def test_profession_missing_count_or_row_type_stays_unknown():
    assert professions._recipe_count({}) is None
    assert professions._recipe_count({"counts": {"1": 1}, "rows": [{}]}) is None


def test_actual_lua_skills_import_nil_holes_hash_and_old_hash_unchanged(tmp_path):
    from brownstone.character_snapshots import content_hash
    from brownstone.journal import content_hash as journal_hash

    lua, g, _ = journal_client()
    lua.execute('''
        function GetProfessions() return 1, nil, 3 end
        function GetProfessionInfo(i) return "Skill" .. i, nil, 1, 75, nil, nil, i end
    ''')
    fire(g, "PLAYER_LOGOUT")
    records = python_value(g.BrownstoneScanDB.snapshots)
    path = write(tmp_path / "actual.lua", [], records)
    config = addon_source(tmp_path / "data", path)
    from datetime import UTC, datetime
    now = datetime.fromtimestamp(records[0]["captured_at"], UTC)
    result = import_scans(config, now=now)
    assert result["fully_imported"]
    rows = professions.latest_rows(config)
    assert [r["Profession / skill"] for r in rows] == ["Skill1", "Skill3"]
    assert all(r["Known recipes (UTC)"] == "known recipes unknown" for r in rows)
    assert not preview_scans(config, now=now).new_record_ids
    old = snapshot()
    import hashlib
    import json
    assert content_hash(old) == hashlib.sha256(json.dumps(old, sort_keys=True, ensure_ascii=False,
                                              separators=(",", ":")).encode()).hexdigest()
    raw = records[0]
    different = copy.deepcopy(raw)
    different["skills"]["modern"]["indexes"]["1"] = different["skills"]["modern"]["indexes"].pop(1)
    assert content_hash(raw) != content_hash(different)
    assert journal_hash(raw) != journal_hash(different)


@pytest.mark.parametrize("record,validator", [
    ({"level": False}, professions.validate_skills),
    ({"skills": []}, professions.validate_skills),
    ({"skills": {"legacy": []}}, professions.validate_skills),
    ({"skills": {"legacy": {"rows": [False]}}}, professions.validate_skills),
    ({"skills": {"legacy": {"rows": [{"name": 123}]}}}, professions.validate_skills),
    ({"known_recipes": []}, professions.validate_recipes),
    ({"known_recipes": {"rows": [{"recipe_id": False}]}}, professions.validate_recipes),
    ({"known_recipes": {"rows": [{"reagents": [{"count": -1}]}]}}, professions.validate_recipes),
])
def test_malformed_profession_evidence_rejected(record, validator):
    with pytest.raises(ValueError):
        validator(record)


def test_profession_cap_retry_reload_identity_and_missing_readers():
    lua, g, _ = journal_client()
    lua.execute('''
        function GetTradeSkillLine() return "Engineering", nil, 75 end
        function GetNumTradeSkills() return 0 end
        for i=1,10000 do mainFrame.scripts.OnEvent(mainFrame, "PLAYER_MONEY") end
    ''')
    fire(g, "TRADE_SKILL_SHOW")
    assert entries(g)[-1]["event"] == "JOURNAL_OVERFLOW"
    lua.execute('BrownstoneScanDB.journal = {}')
    fire(g, "TRADE_SKILL_UPDATE")
    assert entries(g)[-1]["known_recipes"]["counts"][1] == 0
    lua.execute('UnitName=function() return "Other" end')
    fire(g, "TRADE_SKILL_UPDATE")
    assert entries(g)[-1]["character"] == "Other" and len(entries(g)) == 2
    lua.execute('GetNumTradeSkills=nil')
    fire(g, "TRADE_SKILL_UPDATE")
    state = entries(g)[-1]["known_recipes"]
    assert "counts" not in state and state["possibly_incomplete"] is True and "rank" not in state
    lua.execute((ROOT / "addon/BrownstoneScan/BrownstoneScan.lua").read_text())
    fire(g, "ADDON_LOADED", "BrownstoneScan")
    fire(g, "TRADE_SKILL_UPDATE")  # A reload closes the window; nothing is read until it is shown again.
    assert len(entries(g)) == 3
    fire(g, "TRADE_SKILL_SHOW")
    assert len(entries(g)) == 4


def test_filter_all_numeric_unrestricted_text_level_and_each_profession():
    lua, g, _ = journal_client()
    lua.execute('''
        profession, allFilter, textFilter, levelFilter = "Engineering", 1, "", 0
        function GetTradeSkillLine() return profession, 1, 75 end
        function GetNumTradeSkills() return 0 end
        function GetTradeSkillSubClasses() return "Parts", "Tools" end
        function GetTradeSkillSubClassFilter(i) if i == 0 then return allFilter else return 0 end end
        function GetTradeSkillItemNameFilter() return textFilter end
        function GetTradeSkillItemLevelFilter() return levelFilter, nil end
    ''')
    fire(g, "TRADE_SKILL_SHOW")
    assert not entries(g)[-1]["known_recipes"]["possibly_incomplete"]
    lua.execute('profession = "Mining"')
    fire(g, "TRADE_SKILL_SHOW")
    lua.execute('profession = "Engineering"')
    fire(g, "TRADE_SKILL_SHOW")  # Unchanged list: only the small window-open entry.
    assert len(entries(g)) == 3 and "known_recipes" not in entries(g)[-1]
    lua.execute('allFilter = 0')
    fire(g, "TRADE_SKILL_UPDATE")
    assert entries(g)[-1]["known_recipes"]["possibly_incomplete"] is True
    lua.execute('allFilter = 1; textFilter = "Ore"')
    fire(g, "TRADE_SKILL_UPDATE")
    assert entries(g)[-1]["known_recipes"]["filters"]["ItemNameFilter"] == "Ore"
    lua.execute('textFilter = ""; levelFilter = 5')
    fire(g, "TRADE_SKILL_UPDATE")
    assert entries(g)[-1]["known_recipes"]["possibly_incomplete"] is True


def test_output_enchant_link_id_without_recipe_api_and_unreadable_skills(tmp_path):
    lua, g, _ = journal_client()
    lua.execute('''
        function GetCraftDisplaySkillLine() return "Enchanting" end
        function GetNumCrafts() return 1 end
        function GetCraftInfo() return "Enchant", nil, "trivial", nil end
        function GetCraftItemLink() return "|Henchant:7418|h" end
        function GetNumSkillLines() return nil end
    ''')
    fire(g, "CRAFT_SHOW")
    row = entries(g)[-1]["known_recipes"]["rows"][0]
    assert row["spell_id"] == 7418 and "recipe_id" not in row and "craftable" not in row
    fire(g, "PLAYER_LOGOUT")
    snapshots = python_value(g.BrownstoneScanDB.snapshots)
    path = write(tmp_path / "actual.lua", entries(g), snapshots)
    config = addon_source(tmp_path / "data", path)
    from datetime import UTC, datetime
    import_scans(config, now=datetime.fromtimestamp(snapshots[0]["captured_at"], UTC))
    assert professions.latest_rows(config)[0]["Skills"] == "skills unknown"


def test_profession_projection_old_database_and_bank_only(tmp_path):
    import duckdb

    config = addon_source(tmp_path / "data", tmp_path / "unused.lua")
    config["data_dir"].mkdir()
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb")) as db:
        db.execute("CREATE TABLE unrelated (id INTEGER)")
    assert professions.latest_rows(config) == []
    rows = professions._rows(("Alice", "Beta", "Alliance"), {"bags": {}, "recipes": {}})
    assert rows[0]["Skills"] == "skills unknown" and rows[0]["Listed recipes"] is None
    assert professions._rows(("Alice", "Beta", "Alliance"), {
        "bags": {"skills": {"legacy": {"counts": {"1": 0}}}}, "recipes": {}})[0]["Skills"] == "observed"



def test_duplicate_skill_api_display_preference_explicit_and_missing_not_filled():
    surfaces = {"modern": {"api": "GetProfessionInfo", "rows": [{"name": "Mining", "skill_id": 186}]},
                "legacy": {"api": "GetSkillLineInfo", "rows": [{"name": "Mining", "rank": 55, "max_rank": 75}]}}
    row = professions._rows(("Alice", "Beta", "Alliance"), {"bags": {"skills": surfaces}, "recipes": {}})[0]
    assert row["Skill API"] == "GetProfessionInfo" and row["Skill ID"] == 186
    assert row["Rank"] is None and row["Max rank"] is None
    reversed_surfaces = dict(reversed(list(surfaces.items())))
    assert professions._skills({"skills": surfaces}) == professions._skills({"skills": reversed_surfaces})


@pytest.mark.parametrize("craft", [False, True])
def test_craftable_count_changes_alone_save_no_new_list(craft):
    lua, g, _ = journal_client()
    prefix, event = ("GetCraft", "CRAFT") if craft else ("GetTradeSkill", "TRADE_SKILL")
    line = "GetCraftDisplaySkillLine" if craft else "GetTradeSkillLine"
    count = "GetNumCrafts" if craft else "GetNumTradeSkills"
    lua.execute(f'''
        available, rank = 4, 20
        function {line}() return "Engineering", rank, 75 end
        function {count}() return 1 end
        function {prefix}Info() return "Bolt", { 'nil, "optimal", available' if craft else '"optimal", available' } end
    ''')
    fire(g, event + "_SHOW")
    assert entries(g)[-1]["known_recipes"]["rows"][0]["craftable"] == 4
    lua.execute('available = 3')
    fire(g, event + "_UPDATE")
    assert len(entries(g)) == 1
    lua.execute('available = 2; rank = 21')
    fire(g, event + "_UPDATE")
    assert len(entries(g)) == 2 and entries(g)[-1]["known_recipes"]["rows"][0]["craftable"] == 2


def test_closed_window_updates_ignored_and_unchanged_show_still_journalled():
    lua, g, _ = journal_client()
    lua.execute('''
        name = "UNKNOWN"
        function GetTradeSkillLine() return name, 0, 0 end
        function GetNumTradeSkills() return 0 end
    ''')
    fire(g, "TRADE_SKILL_UPDATE")
    fire(g, "CRAFT_UPDATE")
    assert not entries(g)
    lua.execute('name = "Mining"')
    fire(g, "TRADE_SKILL_SHOW")
    fire(g, "TRADE_SKILL_CLOSE")
    lua.execute('name = "UNKNOWN"')
    fire(g, "TRADE_SKILL_UPDATE")
    lua.execute('name = "Mining"')
    fire(g, "TRADE_SKILL_SHOW")
    assert [(r["event"], "known_recipes" in r) for r in entries(g)] == [
        ("TRADE_SKILL_SHOW", True), ("TRADE_SKILL_CLOSE", False), ("TRADE_SKILL_SHOW", False)]


def test_collapsed_skill_header_flagged_and_shown(tmp_path):
    lua, g, _ = journal_client()
    lua.execute('''
        expanded = nil
        function GetNumSkillLines() return 2 end
        function GetSkillLineInfo(i)
            if i == 1 then return "Professions", 1, expanded end
            return "Secondary Skills", 1, nil
        end
    ''')
    fire(g, "PLAYER_LOGOUT")
    record = python_value(g.BrownstoneScanDB.snapshots)[-1]
    assert record["skills"]["legacy"]["possibly_incomplete"] is True
    lua.execute('function GetSkillLineInfo(i) if i == 1 then return "Professions", 1, 1 end '
                'return "Mining", nil, nil, 55, nil, nil, 75 end')
    fire(g, "PLAYER_LOGOUT")
    assert "possibly_incomplete" not in python_value(g.BrownstoneScanDB.snapshots)[-1]["skills"]["legacy"]
    surfaces = {"legacy": {"counts": {"1": 2}, "rows": [], "possibly_incomplete": True}}
    rows = professions._rows(("Alice", "Beta", "Alliance"), {"bags": {"skills": surfaces}, "recipes": {}})
    assert rows[0]["Skills"] == "possibly incomplete"


def modern_client():
    lua, g, _ = journal_client()
    lua.execute('''
        learned, available, filtered = false, 2, false
        C_TradeSkillUI.GetAllRecipeIDs = function() return {2963, 3755, 999} end
        C_TradeSkillUI.GetRecipeInfo = function(id)
            if id == 999 then return {name="Unknown flag"} end
            return {name="Recipe", learned=id == 2963 or learned, categoryID=1, numAvailable=available}
        end
        C_TradeSkillUI.GetRecipeSchematic = function(id)
            return {outputItemID=2589, quantityMin=1, quantityMax=2,
                reagentSlotSchematics={{required=true, quantityRequired=3, reagents={{itemID=2320}}}}}
        end
        C_TradeSkillUI.GetBaseProfessionInfo = function()
            return {professionName="Tailoring", skillLevel=7, maxSkillLevel=75, professionID=197}
        end
        C_TradeSkillUI.GetOnlyShowMakeableRecipes = function() return filtered end
        C_TradeSkillUI.GetCategoryInfo = function() return {isCollapsed=filtered} end
        C_TradeSkillUI.SetRecipeItemNameFilter = function() error("action forbidden") end
        C_TradeSkillUI.OpenTradeSkill = function() error("action forbidden") end
        function GetTradeSkillLine() error("modern must take precedence") end
    ''')
    return lua, g


def test_modern_recipes_raw_learned_schematic_inventory_change_only_silent_no_actions():
    lua, g = modern_client()
    messages = len(g.messages)
    fire(g, "TRADE_SKILL_SHOW")
    record = entries(g)[-1]
    state = record["known_recipes"]
    assert state["api"] == "C_TradeSkillUI" and state["rank"] == 7
    assert [r.get("learned") for r in state["rows"]] == [True, False, None]
    assert professions._recipe_count(state) == 1
    assert state["rows"][0]["schematic"]["reagentSlotSchematics"][0]["quantityRequired"] == 3
    assert state["rows"][0]["min_made"] == 1 and state["rows"][0]["max_made"] == 2
    inventory = record["trade_skill_api_inventory"]
    assert "GetRecipeInfo" in inventory["functions"] and "GetRecipeLink" not in inventory["functions"]
    assert "TRADE_SKILL_LIST_UPDATE" in inventory["events"]
    lua.execute('available=1')
    fire(g, "TRADE_SKILL_LIST_UPDATE")
    assert len(entries(g)) == 1
    fire(g, "TRADE_SKILL_CLOSE")
    fire(g, "TRADE_SKILL_SHOW")
    assert "known_recipes" not in entries(g)[-1]
    assert sum("trade_skill_api_inventory" in e for e in entries(g)) == 1
    lua.execute('learned=true')
    fire(g, "NEW_RECIPE_LEARNED", 3755)
    assert professions._recipe_count(entries(g)[-1]["known_recipes"]) == 2
    lua.execute('filtered=true; C_TradeSkillUI.GetRecipeSchematic=nil')
    fire(g, "TRADE_SKILL_DATA_SOURCE_CHANGED")
    assert entries(g)[-1]["known_recipes"]["possibly_incomplete"] is True
    assert "schematic" not in entries(g)[-1]["known_recipes"]["rows"][0]
    assert g.actionCalls == 0 and len(g.messages) == messages
    assert g.BrownstoneScanDB.journal_diagnostics.fired_events.NEW_RECIPE_LEARNED == 1


def test_modern_failed_read_inventory_legacy_fallback_and_closed_events():
    lua, g = modern_client()
    lua.execute('''C_TradeSkillUI.GetBaseProfessionInfo = function() error("unavailable") end
        function GetTradeSkillLine() return "Engineering", 1, 75 end
        function GetNumTradeSkills() return 0 end''')
    fire(g, "TRADE_SKILL_LIST_UPDATE")
    assert not entries(g)
    fire(g, "TRADE_SKILL_SHOW")
    assert entries(g)[-1]["known_recipes"]["api"] == "GetTradeSkill"
    assert "trade_skill_api_inventory" in entries(g)[-1]
    lua, g = modern_client()
    lua.execute('C_TradeSkillUI.GetBaseProfessionInfo=nil; GetTradeSkillLine=nil')
    fire(g, "CRAFT_SHOW")
    assert "known_recipes" not in entries(g)[-1]
    assert "trade_skill_api_inventory" in entries(g)[-1]


def test_modern_client_craft_window_uses_craft_reader():
    lua, g = modern_client()
    lua.execute('''
        function GetCraftDisplaySkillLine() return "Enchanting", 10, 75 end
        function GetNumCrafts() return 1 end
        function GetCraftInfo() return "Enchant", nil, "trivial", nil end
        function GetCraftItemLink() return "|Henchant:7418|h" end
    ''')
    fire(g, "CRAFT_SHOW")
    state = entries(g)[-1]["known_recipes"]
    assert state["api"] == "GetCraft" and state["name"] == "Enchanting"


@pytest.mark.parametrize("event", ["TRADE_SKILL_LIST_UPDATE", "TRADE_SKILL_DATA_SOURCE_CHANGED", "NEW_RECIPE_LEARNED"])
def test_modern_event_rejected_inventory(event):
    lua, g = capture_client()
    lua.execute(f'''local original = CreateFrame
        function CreateFrame(...)
            local frame = original(...)
            function frame:RegisterEvent(e) if e == "{event}" then error("unsupported") end end
            return frame
        end''')
    lua.execute((ROOT / "addon/BrownstoneScan/BrownstoneScan.lua").read_text())
    fire(g, "ADDON_LOADED", "BrownstoneScan")
    fire(g, "TRADE_SKILL_SHOW")
    assert event not in entries(g)[-1]["trade_skill_api_inventory"]["events"]


def test_seen_crafted_projection_import_scope_union_time_and_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr(professions, "_catalog_recipe_ids", lambda c: {2963: {"Tailoring"}, 3755: {"Tailoring"}})
    hook = entry("hook")
    hook.update(family="craft", event="C_TradeSkillUI.CraftRecipe", arguments={1: 2963, 2: 1, "n": 2})
    cast = entry("cast")
    cast["sequence"] = 2
    cast.update(family="craft", event="UNIT_SPELLCAST_SUCCEEDED", arguments={1: "player", 2: "cast", 3: 3755, "n": 3})
    duplicate = copy.deepcopy(hook)
    duplicate.update(entry_id="again", sequence=3)
    bob = entry("bob")
    bob["character"] = "Bob"
    bob.update(family="craft", event="C_TradeSkillUI.CraftRecipe", arguments={1: 123456, "n": 1})
    opening_cast = copy.deepcopy(cast)
    opening_cast.update(entry_id="opening", arguments={1: "player", 3: 3908, "n": 3})
    path = write(tmp_path / "craft.lua", [hook, cast, duplicate, bob, opening_cast], [snapshot()])
    config = addon_source(tmp_path / "data", path)
    import_scans(config, now=NOW)
    alice, bob_row = professions.latest_rows(config)
    assert alice["Recipe source"] == "seen crafted" and alice["Known recipes"] == 2
    assert alice["Seen crafted recipes"] == [2963, 3755] and alice["Listed recipes"] is None
    assert bob_row["Profession / skill"] == "Profession unknown" and bob_row["Known recipes"] == 1
    for field in ("source_id", *MARKET_KEYS):
        assert professions.latest_rows(config | {field: str(config[field]) + "_other"}) == []
    listed = recipes("list", sequence=4)
    listed["known_recipes"] = {"api": "C_TradeSkillUI", "name": "Tailoring", "counts": {1: 3}, "rows": [
        {"type": "recipe", "recipe_id": 2963, "learned": True},
        {"type": "recipe", "recipe_id": 3755, "learned": False}, {"type": "recipe", "recipe_id": 9}]}
    write(path, [listed])
    import_scans(config, now=NOW)
    alice = professions.latest_rows(config)[0]
    assert alice["Known recipes"] == 2 and alice["Listed recipes"] == 1
    assert alice["Recipe source"] == "window list + seen crafted"
    from views import scan_import
    tables = []
    monkeypatch.setattr(scan_import.st, "dataframe", lambda rows, **_: tables.append(rows))
    monkeypatch.setattr(scan_import.st, "caption", lambda *_: None)
    scan_import._show_holdings(config)
    table = next(t for t in tables if t and "Known recipes" in t[0])
    assert table[0]["Seen crafted recipes"] == [2963, 3755] and table[0]["Known recipes"] == 2
    assert professions._crafted_id({"event": "UNIT_SPELLCAST_SUCCEEDED", "arguments": ["target", "cast", 1]}) is None
    assert professions._crafted_id({"event": "C_TradeSkillUI.CraftRecipe", "arguments": [False]}) is None


def test_modern_learned_flag_validation():
    with pytest.raises(ValueError, match="learned"):
        professions.validate_recipes({"known_recipes": {"rows": [{"learned": 1}]}})


def test_modern_lua_shared_import_and_page_evidence(tmp_path, monkeypatch):
    from datetime import UTC, datetime

    from views import scan_import

    _, g = modern_client()
    fire(g, "TRADE_SKILL_SHOW")
    fire(g, "PLAYER_LOGOUT")
    raw = entries(g)
    path = write(tmp_path / "modern.lua", raw, python_value(g.BrownstoneScanDB.snapshots))
    config = addon_source(tmp_path / "data", path)
    now = datetime.fromtimestamp(raw[0]["captured_at"], UTC)
    import_scans(config, now=now)
    assert not preview_scans(config, now=now).new_record_ids
    tables = []
    monkeypatch.setattr(scan_import.st, "dataframe", lambda rows, **_: tables.append(rows))
    monkeypatch.setattr(scan_import.st, "caption", lambda *_: None)
    scan_import._show_holdings(config)
    table = next(t for t in tables if t and "Known recipes" in t[0])
    assert table[0]["Recipe source"] == "window list" and table[0]["Known recipes"] == 1


def test_catalog_recipe_profession_metadata_requires_game_and_rules(monkeypatch):
    catalogs = [{"catalog": {"game_version": game, "rules_version": rules, "profession": profession,
                             "recipes": [{"recipe_id": 1}]}}
                for game, rules, profession in [("forever", "beta", "tailoring"),
                                                ("classic", "beta", "engineering"),
                                                ("forever", "other", "alchemy")]]
    monkeypatch.setattr(professions, "find_catalogs", lambda _: catalogs + [{"catalog": None}])
    assert professions._catalog_recipe_ids({"game_version": "forever", "rules_version": "beta"}) == {1: {"Tailoring"}}
    assert professions._catalog_recipe_ids({"game_version": "forever"}) == {}


def test_window_profession_provenance_precedes_catalog_and_list_time_stays_visible():
    listed = {"captured_at": 100, "sequence": 1, "known_recipes": {"name": "Client profession",
              "api": "C_TradeSkillUI", "counts": {1: 1},
              "rows": [{"recipe_id": 1, "type": "recipe", "learned": True}]}}
    crafted = {"captured_at": 200, "sequence": 2, "event": "C_TradeSkillUI.CraftRecipe", "arguments": [1]}
    state = {"bags": {}, "recipes": {"Client profession": listed}, "crafts": [crafted]}
    professions._project_crafts(state, {1: {"Catalog profession"}})
    row = professions._rows(("Alice", "Beta", "Alliance"), state)[0]
    assert row["Profession / skill"] == "Client profession" and row["Known recipes"] == 1
    assert row["Known recipes (UTC)"] == "1970-01-01T00:01:40+00:00"
    assert row["Seen crafted (UTC)"] == "1970-01-01T00:03:20+00:00"


def test_inventory_retry_after_cap_and_new_load():
    _, g = modern_client()
    for i in range(1, 10001):
        g.BrownstoneScanDB.journal[i] = g.BrownstoneScanDB.journal[i] or g.mainFrame
    fire(g, "TRADE_SKILL_SHOW")
    # Remove the synthetic capped entries; the unsaved inventory must still be available.
    g.BrownstoneScanDB.journal = g.BrownstoneScanDB.scans
    fire(g, "TRADE_SKILL_SHOW")
    assert "trade_skill_api_inventory" in entries(g)[-1]
    _, fresh = modern_client()
    fire(fresh, "TRADE_SKILL_SHOW")
    assert "trade_skill_api_inventory" in entries(fresh)[-1]


def test_forever_child_name_empty_falls_through_to_base_profession():
    lua, g = modern_client()
    lua.execute('C_TradeSkillUI.GetChildProfessionInfo = function() return {professionName="", skillLevel=0} end')
    fire(g, "TRADE_SKILL_SHOW")
    state = entries(g)[-1]["known_recipes"]
    assert state["name"] == "Tailoring" and state["rank"] == 7
    assert state["profession"]["GetChildProfessionInfo"][1]["professionName"] == ""


def test_forever_not_ready_or_unnamed_read_records_diagnostics_not_a_list():
    lua, g = modern_client()
    lua.execute('''ready = false
        C_TradeSkillUI.IsTradeSkillReady = function() return ready end
        C_TradeSkillUI.IsDataSourceChanging = function() return true end''')
    fire(g, "TRADE_SKILL_SHOW")
    record = entries(g)[-1]
    assert "known_recipes" not in record and "trade_skill_api_inventory" in record
    failure = record["trade_skill_read"]
    assert failure["ready"][1] is False and failure["data_source_changing"][1] is True
    assert failure["recipe_id_count"] == 3
    assert failure["profession"]["GetBaseProfessionInfo"][1]["professionName"] == "Tailoring"
    lua.execute('ready = true')
    fire(g, "TRADE_SKILL_LIST_UPDATE")
    assert entries(g)[-1]["known_recipes"]["name"] == "Tailoring"
    _, unnamed = modern_client()
    unnamed.C_TradeSkillUI.GetBaseProfessionInfo = None
    fire(unnamed, "TRADE_SKILL_SHOW")
    assert entries(unnamed)[-1]["trade_skill_read"]["recipe_id_count"] == 3


def test_forever_window_opened_without_show_read_on_ready_update_and_close():
    lua, g = modern_client()
    lua.execute('''ready = false
        C_TradeSkillUI.IsTradeSkillReady = function() return ready end''')
    fire(g, "TRADE_SKILL_LIST_UPDATE")
    fire(g, "CRAFT_UPDATE")
    assert not entries(g)
    lua.execute('ready = true')
    fire(g, "TRADE_SKILL_LIST_UPDATE")
    assert [(e["event"], "known_recipes" in e) for e in entries(g)] == [("TRADE_SKILL_LIST_UPDATE", True)]
    fire(g, "TRADE_SKILL_CLOSE")
    assert "known_recipes" not in entries(g)[-1] and "trade_skill_read" not in entries(g)[-1]
    lua.execute('learned = true')
    fire(g, "TRADE_SKILL_CLOSE")
    state = entries(g)[-1]["known_recipes"]
    assert entries(g)[-1]["event"] == "TRADE_SKILL_CLOSE" and professions._recipe_count(state) == 2
    _, closed = modern_client()
    fire(closed, "TRADE_SKILL_CLOSE")
    assert entries(closed)[-1]["known_recipes"]["name"] == "Tailoring"
    assert closed.actionCalls == 0


def test_forever_close_without_modern_list_stays_plain_and_never_reads_legacy():
    lua, g, _ = journal_client()
    lua.execute('''legacyCalls = 0
        function GetTradeSkillLine() legacyCalls = legacyCalls + 1 return "Mining", 1, 75 end
        function GetNumTradeSkills() return 0 end''')
    fire(g, "TRADE_SKILL_CLOSE")
    assert [(e["event"], "known_recipes" in e, "trade_skill_read" in e) for e in entries(g)] == [
        ("TRADE_SKILL_CLOSE", False, False)]
    assert g.legacyCalls == 0


def test_forever_close_list_and_failure_diagnostics_import_and_project(tmp_path):
    from datetime import UTC, datetime

    lua, g = modern_client()
    lua.execute('''ready = false
        C_TradeSkillUI.IsTradeSkillReady = function() return ready end''')
    fire(g, "TRADE_SKILL_SHOW")
    lua.execute('ready = true')
    fire(g, "TRADE_SKILL_CLOSE")
    fire(g, "PLAYER_LOGOUT")
    raw = entries(g)
    assert ["trade_skill_read" in e for e in raw] == [True, False]
    path = write(tmp_path / "forever.lua", raw, python_value(g.BrownstoneScanDB.snapshots))
    config = addon_source(tmp_path / "data", path)
    import_scans(config, now=datetime.fromtimestamp(raw[0]["captured_at"], UTC))
    row = next(r for r in professions.latest_rows(config) if r["Profession / skill"] == "Tailoring")
    assert row["Recipe source"] == "window list" and row["Known recipes"] == 1


def test_forever_first_opening_empty_list_is_not_ready_then_data_source_list_saved():
    lua, g = modern_client()
    lua.execute('''loaded = false
        C_TradeSkillUI.GetAllRecipeIDs = function() if loaded then return {2963, 3755, 999} end return {} end''')
    fire(g, "TRADE_SKILL_SHOW")
    record = entries(g)[-1]
    assert "known_recipes" not in record and record["trade_skill_read"]["recipe_id_count"] == 0
    lua.execute('loaded = true')
    fire(g, "TRADE_SKILL_DATA_SOURCE_CHANGED")
    assert professions._recipe_count(entries(g)[-1]["known_recipes"]) == 1
    lua.execute('C_TradeSkillUI.IsTradeSkillReady = function() return false end')
    fire(g, "TRADE_SKILL_CLOSE")
    assert [k for k in ("known_recipes", "trade_skill_read") if k in entries(g)[-1]] == []
