"""Offline STORY-042 contract, including privacy and write isolation."""
import copy
import hashlib
import json
import sys
from datetime import UTC, datetime

import pytest
from test_character_snapshots import snapshot
from test_journal import entry
from test_scans import FINISHED, NOW, addon_source, listing, scan, to_lua

from brownstone import beta_evidence as evidence
from brownstone import beta_report, cli


def database():
    first = snapshot("s1", sequence=1)
    first.update(event="BAGS_CAPTURE", gold_copper=100, addon_version="0.8.0", level=20,
                 skills={"legacy": {"api": "GetSkillLineInfo", "counts": {1: 1, "n": 1},
                                     "rows": [{"name": "Mining", "rank": 20, "max_rank": 75}]}})
    last = copy.deepcopy(first)
    last.update(snapshot_id="s2", sequence=5, event="PLAYER_LOGOUT", captured_at=FINISHED + 3, gold_copper=110)
    last.pop("captured_at_utc")
    last["slots"][0]["count"] = 5
    money = entry("m1", before_copper=100, after_copper=110)
    money.update(sequence=2, captured_at=FINISHED + 1)
    money.pop("captured_at_utc")
    bags = entry("b1")
    bags.update(sequence=3, family="bags", event="BAG_UPDATE_DELAYED", captured_at=FINISHED + 2,
                item_changes={2589: 2})
    bags.pop("captured_at_utc")
    recipes = entry("r1")
    recipes.update(sequence=4, family="craft", event="TRADE_SKILL_SHOW", captured_at=FINISHED + 2,
                   known_recipes={"name": "Engineering", "api": "GetTradeSkill", "counts": {1: 1, "n": 1},
                                  "possibly_incomplete": False, "rows": [{"type": "optimal", "item_id": 1}]})
    recipes.pop("captured_at_utc")
    return dict(schema_version=6, scans=[], snapshots=[first, last], journal=[money, bags, recipes],
                journal_diagnostics=dict(rejected_events=["UNSUPPORTED"], missing_hooks=["UnsupportedHook"],
                                         installed_hooks={"SendMail": True},
                                         fired_events={name: 1 for _, _, names in evidence.COVERAGE for name in names}))


def write(tmp_path, db, name="input.lua"):
    path = tmp_path / name
    path.write_text("BrownstoneScanDB = " + to_lua(db), encoding="utf-8")
    return path


def analyze(db):
    return beta_report.analyze(("BrownstoneScanDB = " + to_lua(db)).encode(), NOW)[0]


def checks(report, name, status=None):
    return [c for c in report["checks"] if c["check"] == name and (status is None or c["status"] == status)]


def test_clean_facts_sizes_sessions_characters_and_round_trip(tmp_path):
    path = write(tmp_path, database())
    config = addon_source(tmp_path / "configured-data", path)
    folder, report, code = beta_report.create_report(path, config, tmp_path / "work/beta-reports", now=NOW)
    assert code == 0 and report["totals"]["warn"] == report["totals"]["fail"] == 0
    assert checks(report, "import round trip", "pass")
    assert report["file"]["bytes"] == path.stat().st_size
    assert report["file"]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert report["file"]["record_counts"] == dict(scans=0, snapshots=2, journal=3)
    assert report["file"]["approximate_bytes"]["journal_by_family"]["craft"] > 0
    assert report["load_sessions"][0]["journal_entries"] == 3
    assert report["load_sessions"][0]["diagnostics"]["missing_hooks"] == ["UnsupportedHook"]
    character = report["characters"][0]
    assert character["snapshots"][0]["level"] == 20
    assert character["latest_known_recipes"][0]["listed_recipes"] == 1
    assert character["journal"][0]["first_utc"]
    assert json.loads((folder / "report.json").read_text()) == report
    assert '"residual_copper": 0' in (folder / "report.md").read_text()
    assert not config["data_dir"].exists()


@pytest.mark.parametrize("case, check_name, status", [
    ("money", "money chain", "fail"), ("gold", "snapshot gold", "warn"),
    ("bag", "bag residual", "warn"), ("conflict", "unique IDs", "fail"),
    ("overflow", "overflow", "fail"), ("skipped", "overflow", "fail"),
    ("diagnostics", "diagnostics", "warn"), ("invalid", "import validation", "fail"),
    ("sequence", "sequence", "fail"), ("shared", "shared sequence", "fail"),
    ("past", "time", "fail"), ("future", "time", "fail"),
    ("errors", "journal errors", "warn"), ("missing baseline", "money chain", "warn"),
    ("incomplete bags", "bag residual", "warn"),
])
def test_checks_continue_with_entry_ids(case, check_name, status):
    db = database()
    _mutate(db, case)
    report = analyze(db)
    assert checks(report, check_name, status)
    assert report["characters"] and report["coverage"]
    if case == "bag":
        assert checks(report, check_name)[0]["detail"]["residual_units"] == {2589: 3}
    if case == "invalid":
        assert "must be an integer" in checks(report, check_name, status)[0]["detail"]


def _mutate(db, case):
    if case == "money":
        m = copy.deepcopy(db["journal"][0])
        m.update(entry_id="m2", sequence=3, before_copper=109, after_copper=110)
        db["journal"].insert(1, m)
    elif case == "gold":
        db["snapshots"][-1]["gold_copper"] += 1
    elif case == "bag":
        db["snapshots"][-1]["slots"][0]["count"] += 3
    elif case == "conflict":
        m = copy.deepcopy(db["journal"][0])
        m["after_copper"] = 120
        db["journal"].append(m)
    elif case in ("overflow", "skipped"):
        db["journal"][0].update(event="JOURNAL_OVERFLOW" if case == "overflow" else "PLAYER_MONEY", skipped=7)
    elif case == "diagnostics":
        db.pop("journal_diagnostics")
    elif case == "invalid":
        db["journal"][0]["before_copper"] = -1
    else:
        _mutate_more(db, case)


def _mutate_more(db, case):
    if case == "sequence":
        db["journal"].reverse()
    elif case == "shared":
        db["journal"][0]["sequence"] = 1
    elif case == "past":
        db["journal"][0]["captured_at"] = int(datetime(2026, 9, 16, tzinfo=UTC).timestamp())
    elif case == "future":
        db["journal"][0]["captured_at"] = int(NOW.timestamp()) + 1
    elif case == "errors":
        db["journal_errors"] = {"SendMail": 2}
    elif case == "missing baseline":
        db["journal"][0].pop("before_copper")
    else:
        db["snapshots"][0]["containers"][0]["slots_readable"] = False


@pytest.mark.parametrize("name", [None, "", "UNKNOWN", "  unknown  "])
def test_profession_name_fail(name):
    db = database()
    if name is None:
        db["journal"][-1]["known_recipes"].pop("name")
    else:
        db["journal"][-1]["known_recipes"]["name"] = name
    assert checks(analyze(db), "profession name", "fail")


def test_profession_frequency_missing_level_skills_and_incomplete_causes():
    db = database()
    recipe = db["journal"][-1]
    for n in range(5):
        r = copy.deepcopy(recipe)
        r.update(entry_id=f"recipe{n}", sequence=5 + n)
        db["journal"].append(r)
    db["snapshots"][-1]["sequence"] = 10
    db["snapshots"][0].pop("level")
    db["snapshots"][-1].pop("skills")
    state = recipe["known_recipes"]
    state.update(possibly_incomplete=True, filters={"OnlyShowMakeable": True},
                 rows=[{"type": "header", "expanded": False}, {}])
    report = analyze(db)
    assert checks(report, "profession frequency", "warn")[0]["detail"]["lists"] == 6
    assert len(checks(report, "bags level/skills", "warn")) == 2
    assert set(checks(report, "recipe list", "warn")[0]["detail"]["causes"]) == {
        "filter", "collapsed/unknown header", "missing row type", "missing/unreadable count or row count mismatch"}


def test_session_boundaries_uptime_persists_and_characters_not_pooled():
    db = database()
    later = entry("new", before_copper=999, after_copper=1000)
    later.update(sequence=6, captured_at=FINISHED + 4, session_time=100)
    later.pop("captured_at_utc")
    db["journal"].append(later)
    report = analyze(db)
    assert len(report["load_sessions"]) == 2
    assert report["load_sessions"][0]["diagnostics"] is None
    assert not checks(report, "money chain", "fail")
    reset = dict(later, entry_id="reset", sequence=7, session_time=1)
    different = dict(reset, entry_id="other", sequence=8, character="Bob")
    assert len(evidence.load_sessions([later, reset, different])) == 3


def test_comparison_new_by_character_family_and_conflicts(tmp_path):
    db = database()
    previous = write(tmp_path, db, "previous.lua")
    new = entry("new")
    new.update(character="Bob", family="vendor", event="BuyMerchantItem", sequence=6)
    db["journal"].append(new)
    path = write(tmp_path, db)
    _, report, code = beta_report.create_report(path, addon_source(tmp_path / "data", path),
                                               tmp_path / "work/beta-reports", previous, NOW)
    assert code == 0
    assert report["comparison"]["additions"] == [dict(character="Bob", realm="Beta", faction="Alliance",
                                                      family="vendor", records=1)]
    db["journal"][0]["after_copper"] = 9
    report = analyze(db)
    beta_report.compare(report, scans_lists(db), previous.read_bytes(), NOW)
    assert checks(report, "comparison conflict", "fail")


def scans_lists(db):
    return db["scans"], db["snapshots"], db["journal"]


def test_seller_names_excluded_and_owned_numeric_projection(tmp_path):
    db = database()
    db["scans"] = [scan("scan", FINISHED, [listing(1, 1, 10, seller="PRIVATE_SELLER")])]
    owned = entry("owned")
    owned.update(sequence=6, family="auction", event="OWNED_AUCTIONS_UPDATED", owned_auctions={
        "api": "modern", "counts": {1: 1, "n": 1}, "auctions": [{"info": {
            "auctionID": 123, "bidder": "PRIVATE_BIDDER", "owner": "PRIVATE_SELLER", "buyoutAmount": 100}}]})
    db["journal"].append(owned)
    path = write(tmp_path, db)
    folder, report, code = beta_report.create_report(path, addon_source(tmp_path / "data", path),
                                                    tmp_path / "work/beta-reports", now=NOW)
    assert code == 0
    assert report["characters"][0]["latest_owned_auctions"]["auctions"] == [{"auctionID": 123, "buyoutAmount": 100}]
    for file in folder.iterdir():
        text = file.read_text()
        assert "PRIVATE_SELLER" not in text and "PRIVATE_BIDDER" not in text
    assert set(report["scans"][0]) == {"scan_id", "started_at", "finished_at", "listing_count"}


@pytest.mark.parametrize("case, expected", [("clean", 0), ("fail", 1), ("parse", 1), ("unreadable", 2)])
def test_cli_exit_codes_parse_report_write_isolation(tmp_path, monkeypatch, capsys, case, expected):
    db = database()
    if case == "fail":
        db["journal"][-1]["known_recipes"]["name"] = "UNKNOWN"
    path = write(tmp_path, db)
    if case == "parse":
        path.write_bytes(b"broken lua")
    if case == "unreadable":
        path.unlink()
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    config = addon_source(tmp_path / "data", path)
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(cli, "read_sources", lambda *args: [config])
    original = beta_report.create_report
    monkeypatch.setattr(beta_report, "create_report", lambda *args: original(*args, now=NOW))
    monkeypatch.setattr(sys, "argv", ["brownstone", "beta-report", str(path)])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == expected
    output = capsys.readouterr().out.splitlines()
    assert len(output) == 2 and output[1].endswith("fail")
    folder = tmp_path / "work/beta-reports"
    assert len(list(folder.iterdir())) == 1
    for file in tmp_path.rglob("*"):
        if file.is_file():
            assert file in before or file.is_relative_to(folder)
    assert all(p.read_bytes() == raw for p, raw in before.items())
    if case == "parse":
        report = json.loads(next(folder.rglob("report.json")).read_text())
        assert len(report["checks"]) == 1 and report["file"]["bytes"] == 10


def test_previous_unreadable_invalid_and_import_failure(tmp_path):
    path = write(tmp_path, database())
    config = addon_source(tmp_path / "data", path)
    output = tmp_path / "work/beta-reports"
    _, report, code = beta_report.create_report(path, config, output, tmp_path / "missing", NOW)
    assert code == 2 and checks(report, "previous input read", "fail")
    bad = write(tmp_path, dict(schema_version=6, journal=[1]), "bad.lua")
    report = analyze(database())
    beta_report.compare(report, scans_lists(database()), bad.read_bytes(), NOW)
    assert checks(report, "comparison", "fail")
    config["scan_evidence"]["faction"] = "Horde"
    _, report, code = beta_report.create_report(path, config, output, now=NOW)
    assert code == 1 and checks(report, "import round trip", "fail")


@pytest.mark.parametrize("value", [False, {"all": False}, {"all": None, 1: {"enabled": False}}])
def test_filter_causes(value):
    filters = {"SubClass": value} if isinstance(value, dict) else {"OnlyShowSkillUps": True}
    assert evidence._filtered(filters)
    assert evidence._filtered({"ItemLevelFilter": {1: 5, "n": 1}})
    assert not evidence._filtered({"ItemLevelFilter": {1: 0, "n": 1}})


def test_malformed_list_or_record_continues_and_duplicate_identical():
    db = database()
    db["scans"] = "broken"
    report = analyze(db)
    assert checks(report, "import validation", "fail") and report["characters"]
    db["scans"] = [42, scan("broken", FINISHED, [listing(1, 0, 0)])]
    db["journal"].append(copy.deepcopy(db["journal"][0]))
    report = analyze(db)
    assert len(checks(report, "import validation", "fail")) == 2
    assert checks(report, "unique IDs", "fail")[0]["detail"] == "Duplicate ID in file"
    assert report["characters"]


def test_partial_diagnostics_unreadable_owned_and_no_sequence():
    db = database()
    db["journal_diagnostics"] = "unreadable"
    db["journal"][0].pop("sequence")
    db["journal"][1]["owned_auctions"] = "unknown"
    report = analyze(db)
    assert checks(report, "diagnostic fields", "warn")
    assert checks(report, "sequence", "fail")
    assert report["characters"][0]["latest_owned_auctions"]["observed_rows"] == 0


def test_shared_reader_equivalence_and_formats_1_through_6(tmp_path):
    from brownstone import scans
    for version in range(1, 7):
        db = database() if version == 6 else {"schema_version": version, "scans": [scan("scan", FINISHED, [])]}
        if version == 5:
            db["snapshots"] = [snapshot("old", sequence=1)]
        path = write(tmp_path, db, f"format{version}.lua")
        raw = path.read_bytes()
        _, lists = beta_report.analyze(raw, NOW)
        imported_scans, imported_records = scans.read_addon_records(raw)
        assert lists[0] == imported_scans and lists[1] + lists[2] == imported_records
        _, report, code = beta_report.create_report(path, addon_source(tmp_path / "data", path),
                                                    tmp_path / "work/beta-reports", now=NOW)
        assert code == 0 and checks(report, "import round trip", "pass")
        if version == 5:
            assert checks(report, "bags level/skills", "pass")


def test_cli_source_selection_previous_option_and_repeated_unique_folders(tmp_path, monkeypatch, capsys):
    path = write(tmp_path, database())
    config = addon_source(tmp_path / "data", path)
    config["enabled"] = False
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(cli, "read_sources", lambda *args: [config])
    original = beta_report.create_report
    monkeypatch.setattr(beta_report, "create_report", lambda *args: original(*args, now=NOW))
    for _ in range(2):
        with pytest.raises(SystemExit) as error:
            cli.beta_report_main([str(path), "--previous", str(path), "--source", "my-scans"])
        assert error.value.code == 0
    assert len(list((tmp_path / "work/beta-reports").iterdir())) == 2
    with pytest.raises(SystemExit) as error:
        cli.beta_report_main([str(path)])
    assert error.value.code == 2
    capsys.readouterr()


def test_read_limit_and_changed_input_get_reports(tmp_path, monkeypatch):
    path = write(tmp_path, database())
    monkeypatch.setattr(beta_report.pipeline, "_read_scan_bytes", lambda p: (_ for _ in ()).throw(
        ValueError("Scan file changed while reading")))
    folder, report, code = beta_report.create_report(path, addon_source(tmp_path / "data", path),
                                                    tmp_path / "work/beta-reports", now=NOW)
    assert code == 2 and folder.exists() and checks(report, "input read", "fail")


def test_recipe_filter_count_unknown_gold_and_missing_bag_changes():
    db = database()
    db["snapshots"][0].pop("gold_copper")
    db["journal"][1].pop("item_changes")
    db["journal"][-1]["known_recipes"].pop("counts")
    report = analyze(db)
    assert checks(report, "snapshot gold", "warn") and checks(report, "bag residual", "warn")
    assert checks(report, "recipe list", "warn")
    assert evidence._filtered({"SubClass": {"all": True, 1: {"enabled": False}}}) is False
    assert evidence.recipe_causes({"possibly_incomplete": True, "counts": {1: 0}, "rows": []}) == [
        "client marked incomplete; cause not readable"]


def test_empty_load_retains_diagnostics_and_historical_loads_warn():
    db = database()
    report = analyze(dict(schema_version=6, scans=[], journal=[], snapshots=[],
                          journal_diagnostics=db["journal_diagnostics"]))
    assert report["load_sessions"][0]["journal_entries"] == 0
    assert report["load_sessions"][0]["diagnostics"]["installed_hooks"]["SendMail"]
    r = entry("later")
    r.update(sequence=6, captured_at=FINISHED + 5)
    r.pop("captured_at_utc")
    db["journal"].append(r)
    report = analyze(db)
    assert checks(report, "load diagnostics", "warn")


def test_markdown_collapses_repeated_passes_and_caps_ids():
    from views.beta_report import markdown
    db = database()
    for i in range(30):
        r = entry(f"bulk{i}", before_copper=110, after_copper=110)
        r.update(sequence=10 + i, captured_at=FINISHED + 4)
        r.pop("captured_at_utc")
        db["journal"].append(r)
    db["journal"][-1]["skipped"] = 3
    report = analyze(db)
    statuses = [c["status"] for c in report["checks"]]
    report.update(generated_utc=NOW.isoformat(), totals={k: statuses.count(k) for k in ("pass", "warn", "fail")})
    text = markdown(report)
    assert "import validation ×" in text and "| import validation | pass |" not in text
    assert "| overflow | fail | bulk29 |" in text
    assert "(+" in text and "bulk0, " not in text.split("## Facts")[1]
    assert '"records": ' in text and "| money | PLAYER_MONEY |" in text
    assert len(text) < 30_000
