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
    assert record["level"] == 22 and record["addon_version"] == "0.8.0"
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
