"""STORY-014 Slice 2: catalogs found by selection file, their status, and previewed add and update writes."""
import tomllib
from datetime import date
from pathlib import Path

import pytest
from test_cli import SELECTION
from test_recipe_import import PAGE

from brownstone import recipe_catalogs as rc
from brownstone import selection_files
from brownstone.recipe_import import (
    archive_page,
    build_catalog,
    load_selection,
    page_build,
    parse_selection,
    prepare_catalog,
)

ROOT = Path(__file__).resolve().parents[1]
# The miniature page with the patch and build markers a real saved page carries.
BUILD_PAGE = PAGE.replace("<head>", '<head><meta name="description" content="Always up to date with the latest '
                          'patch (1.60.1).">').replace(
    "</script>", '</script><script>var f = [{"id":112,"options":[[69876,"69876 (1.60.1)"],[70205,"70205 (1.60.1)"],'
                 '[70300,"70300 (1.61.0)"]],"name":"Added in build"}];</script>')
CHANGED_PAGE = PAGE.replace('"reagents":[[2589,2]]', '"reagents":[[2589,3]]')
LEATHER_PAGE = PAGE.replace("professions/tailoring", "professions/leatherworking")


def tree(path):
    return {p: p.read_bytes() for p in sorted(path.rglob("*")) if p.is_file()}


@pytest.fixture
def workspace(tmp_path):
    return make_workspace(tmp_path)


def make_workspace(tmp_path):
    """A config folder with one generated Forever Tailoring catalog (from the miniature page) and an archive."""
    config = tmp_path / "config"
    (config / rc.SELECTIONS).mkdir(parents=True)
    selection = config / rc.SELECTIONS / "forever-tailoring.toml"
    selection.write_text("# Hand-written comment that a version bump keeps.\n" + SELECTION, encoding="utf-8")
    page = tmp_path / "page.html"
    page.write_bytes(PAGE.encode())
    copy, manifest = archive_page(page, tmp_path / "archive", "2026-10-01")
    (config / "forever-tailoring.toml").write_text(
        prepare_catalog(copy.read_bytes(), load_selection(selection), manifest["saved_at"], None)["text"],
        encoding="utf-8")
    return config, tmp_path / "archive"


def source(**overrides):
    return {"source_id": "forever-addon", "game_version": "forever", "rules_version": "forever-beta-1.60",
            **overrides}


def test_catalogs_are_found_by_selection_file_for_any_profession(tmp_path):
    entries = rc.find_catalogs(ROOT / "config")  # Other professions may be added in the app.
    assert {"classic-era-tailoring", "forever-tailoring"} <= {entry["name"] for entry in entries}
    assert all(entry["catalog"]["recipes"] for entry in entries)
    missing = rc.missing_professions(entries)
    assert "tailoring" not in missing["classic"] and "leatherworking" in missing["forever"]

    (tmp_path / rc.SELECTIONS).mkdir()
    (tmp_path / rc.SELECTIONS / "forever-leatherworking.toml").write_text(
        SELECTION.replace("tailoring", "leatherworking"), encoding="utf-8")
    (entry,) = rc.find_catalogs(tmp_path)
    assert entry["name"] == "forever-leatherworking" and entry["catalog"] is None  # Not generated yet.
    assert "leatherworking" not in rc.missing_professions([entry])["forever"]


def test_wowhead_page_names_follow_game_version_and_profession():
    assert rc.catalog_name("classic", "first-aid") == "classic-era-first-aid"
    assert rc.wowhead_page_url("forever", "leatherworking") == (
        "https://www.wowhead.com/forever/spells/professions/leatherworking")
    assert rc.profession_label("classic", "first-aid") == "Classic First Aid"


def test_page_build_is_the_newest_build_of_the_pages_patch():
    assert page_build(BUILD_PAGE) == {"patch": "1.60.1", "build": 70205}  # 70300 belongs to another patch.
    assert page_build(PAGE) == {"patch": None, "build": None}


def test_status_reports_page_evidence_unconfirmed_values_and_refresh_due(workspace):
    config, archive = workspace
    (entry,) = rc.find_catalogs(config)
    status = rc.catalog_status(entry, [source()], archive, date(2026, 10, 4))
    assert (status["catalog_version"], status["recipes"], status["saved_at"]) == ("0.1", 2, "2026-10-01")
    assert status["archived"] and status["build"] is None  # The miniature page states no build.
    assert status["refresh"] == []
    assert status["unconfirmed"] == []

    real = next(e for e in rc.find_catalogs(ROOT / "config") if e["name"] == "forever-tailoring")
    kinds = [value["kind"] for value in rc.unconfirmed_values(real["catalog"])]
    assert kinds.count("yield") == 7 and kinds.count("vendor") == 4 and kinds.count("post-launch") == 3

    moved = rc.catalog_status(entry, [source(rules_version="forever-1.61", label="Forever AH"),
                                      source(game_version="classic", rules_version="classic-era")],
                              archive, date(2026, 12, 1))
    assert moved["refresh"] == ["Forever AH uses rules forever-1.61, this catalog forever-beta-1.60",
                                "page saved 61 days ago (refresh after 30)"]
    entry["selection"]["refresh_after_days"] = 90
    assert rc.refresh_reasons(entry, [], date(2026, 12, 1)) == []


def test_status_without_the_archived_page_on_this_machine(workspace):
    config, _ = workspace
    (entry,) = rc.find_catalogs(config)
    status = rc.catalog_status(entry, [], config / "elsewhere", date(2026, 10, 4))
    assert not status["archived"] and status["sha256"] == entry["catalog"]["source_sha256"]
    entry["catalog"] = None
    assert rc.archived_page(entry, config) is None


def test_update_preview_writes_nothing_then_regenerate_bumps_the_version(workspace):
    config, archive = workspace
    (entry,) = rc.find_catalogs(config)
    before = tree(config.parent)
    preview = rc.preview_update(entry, CHANGED_PAGE.encode(), "2026-10-04")
    assert tree(config.parent) == before
    assert preview["changed"] and preview["catalog_version"] == "0.2"
    assert any(line.startswith("changed recipe 2963") for line in preview["changes"])

    result = rc.regenerate(entry, CHANGED_PAGE.encode(), "Forever Spells.html", "2026-10-04", archive)
    assert result["tracked"] == [entry["selection_path"], entry["catalog_path"]]
    assert result["archived"][0].read_bytes() == CHANGED_PAGE.encode()  # Archived byte-for-byte.
    selection_text = entry["selection_path"].read_text(encoding="utf-8")
    assert selection_text.startswith("# Hand-written comment") and 'catalog_version = "0.2"' in selection_text
    catalog = tomllib.loads(entry["catalog_path"].read_text(encoding="utf-8"))
    assert catalog["catalog_version"] == "0.2" and catalog["verified_at"] == "2026-10-04"
    assert catalog["source_sha256"] == result["manifest"]["sha256"]


def test_regenerating_from_the_same_page_changes_nothing(workspace):
    config, archive = workspace
    (entry,) = rc.find_catalogs(config)
    assert not rc.preview_update(entry, PAGE.encode(), "2026-10-01")["changed"]
    before = tree(config)
    result = rc.regenerate(entry, PAGE.encode(), "page.html", "2026-10-01", archive)
    assert result["tracked"] == [] and tree(config) == before


def test_regenerate_creates_a_missing_catalog_without_a_bump(workspace):
    config, archive = workspace
    (entry,) = rc.find_catalogs(config)
    entry["catalog_path"].unlink()
    result = rc.regenerate(entry, PAGE.encode(), "page.html", "2026-10-01", archive)
    assert result["catalog_version"] == "0.1" and result["tracked"] == [entry["catalog_path"]]


def test_update_refuses_another_game_versions_or_professions_page(workspace):
    config, archive = workspace
    (entry,) = rc.find_catalogs(config)
    for page in (PAGE.replace("/forever/", "/classic/"), LEATHER_PAGE):
        with pytest.raises(ValueError, match="never borrow"):
            rc.preview_update(entry, page.encode(), "2026-10-04")
        with pytest.raises(ValueError, match="never borrow"):
            rc.regenerate(entry, page.encode(), "page.html", "2026-10-04", archive)
    assert not (archive / "wowhead/classic").exists() and not (archive / "wowhead/forever/leatherworking").exists()


def test_version_bumps_need_major_minor_and_one_version_line():
    assert rc.bump_version("0.9") == "0.10"
    with pytest.raises(ValueError, match="MAJOR.MINOR"):
        rc.bump_version("beta")
    assert selection_files.set_value('# catalog_version = "x"\ncatalog_version = "0.1"\n', "catalog_version",
                                     "0.2") == '# catalog_version = "x"\ncatalog_version = "0.2"\n'
    with pytest.raises(ValueError, match="exactly one catalog_version"):
        selection_files.set_value('status = "x"\n', "catalog_version", "0.2")


def test_new_profession_pages_must_match_the_chosen_version_and_profession():
    page = LEATHER_PAGE.encode()
    assert rc.read_page(page, "forever", "leatherworking", "2026-10-04")["profession"] == "leatherworking"
    with pytest.raises(ValueError, match="never borrow"):
        rc.read_page(page, "classic", "leatherworking", "2026-10-04")
    with pytest.raises(ValueError, match="never borrow"):
        rc.read_page(page, "forever", "tailoring", "2026-10-04")


def test_recipe_choices_filter_by_name_and_skill_and_skip_variable_yields():
    extract = rc.read_page(LEATHER_PAGE.encode(), "forever", "leatherworking", "2026-10-04")
    assert [r["id"] for r in rc.candidate_recipes(extract)] == [2963, 3755]  # Lucky Bolt makes 1-3.
    assert [r["id"] for r in rc.candidate_recipes(extract, name="bag")] == [3755]
    assert [r["id"] for r in rc.candidate_recipes(extract, min_skill=10)] == [3755]
    assert rc.vendor_candidates(extract, rc.choices([3755])) == [2320]  # Only items with a page buy price are offered.
    assert rc.vendor_candidates(extract, rc.choices([])) == []


def test_new_selections_mark_forever_yields_and_vendors_unconfirmed():
    with pytest.raises(ValueError, match="rules_version"):
        rc.new_selection("forever", "leatherworking", "", rc.choices([3755], []))
    with pytest.raises(ValueError, match="at least one recipe"):
        rc.new_selection("forever", "leatherworking", "forever-beta-1.60", rc.choices([], []))
    forever = rc.new_selection("forever", "leatherworking", "forever-beta-1.60", rc.choices([3755], [2320]),
                               "First tier")
    assert forever["recipe_defaults"]["output_quantity_verified"] is False
    assert forever["items"] == [{"item_id": 2320, "vendor": True, "vendor_verified": False,
                                 "vendor_note": rc.VENDOR_NOTE}]
    classic = rc.new_selection("classic", "leatherworking", "classic-era", rc.choices([3755], []))
    assert "recipe_defaults" not in classic and "items" not in classic and classic["status"] == "reference-observed"


def test_add_preview_writes_nothing_then_create_matches_the_cli(tmp_path, monkeypatch):
    config, archive = tmp_path / "config", tmp_path / "archive"
    config.mkdir()
    selection = rc.new_selection("forever", "leatherworking", "forever-beta-1.60", rc.choices([3755], [2320]))
    preview = rc.preview_new(config, LEATHER_PAGE.encode(), selection, "2026-10-04")
    assert tree(tmp_path) == {}
    assert preview["name"] == "forever-leatherworking"
    assert "recipe_id = 3755  # Linen Bag" in preview["selection_text"]
    assert "item_id = 2320  # Coarse Thread" in preview["selection_text"]

    result = rc.create(config, LEATHER_PAGE.encode(), "Forever Leatherworking.html", selection, "2026-10-04",
                       archive)
    assert result["tracked"] == [config / "recipe-selections/forever-leatherworking.toml",
                                 config / "forever-leatherworking.toml"]
    assert load_selection(result["tracked"][0]) == selection
    assert result["catalog_version"] == "0.1"
    (entry,) = rc.find_catalogs(config)
    assert len(entry["catalog"]["recipes"]) == 2  # The bolt intermediate was added.
    # The same files the CLI produces from the archived page.
    from brownstone import cli
    monkeypatch.setattr("sys.argv", ["brownstone", "recipes", "--page", str(result["archived"][0]),
                                     "--selection", str(result["tracked"][0]),
                                     "--output", str(tmp_path / "cli.toml"), "--archive-dir", str(archive)])
    cli.main()
    assert (tmp_path / "cli.toml").read_text() == result["tracked"][1].read_text()
    with pytest.raises(ValueError, match="already has a selection"):
        rc.preview_new(config, LEATHER_PAGE.encode(), selection, "2026-10-04")
    result["tracked"][0].unlink()  # A catalog without its selection file is never overwritten.
    with pytest.raises(ValueError, match="exists without a selection file"):
        rc.preview_new(config, LEATHER_PAGE.encode(), selection, "2026-10-04")


def test_add_refuses_catalogs_the_board_could_not_load(tmp_path):
    # Two selected recipes making the same bag: an item several recipes make is always bought.
    page = LEATHER_PAGE.replace('"creates":[9999,1,3]', '"creates":[4238,1,1]')
    selection = rc.new_selection("forever", "leatherworking", "forever-beta-1.60", rc.choices([3755, 7777], []))
    with pytest.raises(ValueError, match=r"3755 \(Linen Bag\), 7777 \(Lucky Bolt\) make items other recipes"):
        rc.preview_new(tmp_path, page.encode(), selection, "2026-10-04")
    assert not any(tmp_path.iterdir())


def test_seasonal_recipes_are_never_offered_or_built():
    # Classic pages list Season of Discovery spells (seasonId 2) beside Classic Era ones.
    page = LEATHER_PAGE.replace(
        '"envChange":{"status":"new"}}];',
        '"envChange":{"status":"new"}},{"id":8000,"name":"Sigil","creates":[4238,1,1],"reagents":[[2589,1]],'
        '"learnedat":50,"seasonId":2},{"id":8001,"name":"Enchant Cloak","creates":null,"reagents":[[2589,1]],'
        '"learnedat":1}];')
    extract = rc.read_page(page.encode(), "forever", "leatherworking", "2026-10-04")
    assert extract["recipes"]["8000"]["season"] == 2
    assert rc.recipe_counts(extract) == {"offered": 2, "no item": 1, "no fixed yield": 1, "shared item": 0,
                                         "seasonal": 1}
    assert 8000 not in [r["id"] for r in rc.candidate_recipes(extract)]
    # The seasonal recipe also makes the Linen Bag, but never makes it ambiguous or gets added.
    assert len(rc.vendor_candidates(extract, rc.choices([3755]))) == 1
    with pytest.raises(ValueError, match="seasonal realm"):
        rc.preview_new(Path("unused"), page.encode(),
                       rc.new_selection("forever", "leatherworking", "forever-beta-1.60", rc.choices([8000])),
                       "2026-10-04")


def test_new_selections_list_each_recipe_and_item_once():
    selection = rc.new_selection("classic", "enchanting", "classic-era", rc.choices([14810, 7421, 14810], [2320, 2320]))
    assert selection["recipes"] == [{"recipe_id": 7421}, {"recipe_id": 14810}]
    assert [item["item_id"] for item in selection["items"]] == [2320]


def used_items(extract, recipes):
    draft = build_catalog(extract, rc._draft_selection(extract, rc.choices(recipes)))
    return {item["item_id"] for item in draft["items"]}


def fixture_extract(game):
    import json
    return json.loads((ROOT / f"tests/fixtures/wowhead/{game}-tailoring-extract.json").read_text())


def test_editing_a_selection_keeps_comments_and_drops_notes_nothing_uses():
    text = (ROOT / "config/recipe-selections/forever-tailoring.toml").read_text(encoding="utf-8")
    extract = fixture_extract("forever")
    recipes = [3755, 3757, 18401]  # Drop Red Linen and Runecloth bags; pick Bolt of Runecloth as finished.
    used = used_items(extract, recipes)
    edited, dropped = selection_files.edit_recipes(text, extract, recipes, [2320, 2321], used)
    assert "# Output counts: Wowhead's list data" in edited and "[recipe_defaults]" in edited
    data = tomllib.loads(edited)
    assert [pick["recipe_id"] for pick in data["recipes"]] == [3755, 3757, 18401]
    assert {item["item_id"] for item in data["items"]} == {2320, 2321}
    assert set(dropped) == {"Magenta Dye", "Cerulean Dye", "Red Dye", "Rune Thread"}
    assert "recipe_id = 18401  # Bolt of Runecloth" in edited
    build_catalog(extract, parse_selection(data))  # The importer accepts the result.


def test_vendor_marks_are_added_into_existing_notes_and_removed_without_losing_them():
    text = (ROOT / "config/recipe-selections/forever-tailoring.toml").read_text(encoding="utf-8")
    extract = fixture_extract("forever")
    recipes = [3755, 3757, 6686, 18405]
    used = used_items(extract, recipes)
    # Mark Magenta Dye (which has an availability note) and unmark Rune Thread.
    marks = [2320, 2321, 2604, 249430]
    edited, dropped = selection_files.edit_recipes(text, extract, recipes, marks, used)
    items = {item["item_id"]: item for item in tomllib.loads(edited)["items"]}
    assert items[249430]["availability"] == "post-launch" and items[249430]["vendor_verified"] is False
    assert 14341 not in items and dropped == ["Rune Thread (vendor mark)"]

    classic = (ROOT / "config/recipe-selections/classic-era-tailoring.toml").read_text(encoding="utf-8")
    extract = fixture_extract("classic")
    recipes = [3757, 12065, 18405]
    used = used_items(extract, recipes)
    edited, _ = selection_files.edit_recipes(classic, extract, recipes, [2321, 4291, 14341], used)
    assert edited == classic  # Choosing what is already there changes nothing.


def test_update_can_change_recipes_vendors_and_rules_then_bumps_once(workspace):
    config, archive = workspace
    (entry,) = rc.find_catalogs(config)
    assert rc.current_choices(entry) == {"recipes": [3755], "vendor": [2320]}
    before = tree(config.parent)
    preview = rc.preview_update(entry, PAGE.encode(), "2026-10-01", rc.choices([3755]), "forever-1.61")
    assert tree(config.parent) == before
    assert preview["changed"] and preview["catalog_version"] == "0.2"
    assert preview["dropped_notes"] == ["Coarse Thread (vendor mark)"]  # Its whole note was the mark.
    assert 'rules_version = "forever-1.61"' in preview["selection_text"]
    rc.regenerate(entry, PAGE.encode(), "page.html", "2026-10-01", archive, rc.choices([3755]), "forever-1.61")
    (entry,) = rc.find_catalogs(config)
    assert entry["selection"]["catalog_version"] == entry["catalog"]["catalog_version"] == "0.2"
    assert entry["catalog"]["rules_version"] == "forever-1.61"
    assert entry["selection_path"].read_text(encoding="utf-8").startswith("# Hand-written comment")
    assert rc.archived_copy(entry, archive).read_bytes() == PAGE.encode()
    assert not rc.preview_update(entry, PAGE.encode(), "2026-10-01", rc.choices([3755]), "forever-1.61")["changed"]


def test_replacing_every_recipe_puts_the_new_ones_before_the_item_notes():
    text = (ROOT / "config/recipe-selections/forever-tailoring.toml").read_text(encoding="utf-8")
    extract = fixture_extract("forever")
    used = used_items(extract, [18401])
    edited, dropped = selection_files.edit_recipes(text, extract, [18401], [], used)
    assert "# Vendor materials" not in edited  # Its notes are all gone, so the comment goes too.
    assert edited.endswith("[[recipes]]\nrecipe_id = 18401  # Bolt of Runecloth\n")
    assert [pick["recipe_id"] for pick in tomllib.loads(edited)["recipes"]] == [18401]
    assert "Magenta Dye" in dropped
    assert selection_files.edit_recipes(edited, extract, [18401], [], used)[0] == edited


def test_new_recipes_go_before_the_item_notes_and_their_comments():
    text = SELECTION.replace("recipe_id = 3755", "recipe_id = 3757").replace(
        "[[items]]", "# Thread is sold by vendors.\n[[items]]")
    extract = fixture_extract("forever")
    used = used_items(extract, [3755])
    edited, dropped = selection_files.edit_recipes(text, extract, [3755], [2320], used)
    assert dropped == [] and edited.index("recipe_id = 3755") < edited.index("# Thread is sold")
    assert "3757" not in edited


# Alchemy in miniature: two transmutes make Essence of Water, and Water and Undeath are made from each other.
ALCHEMY_PAGE = """<html><head>
<link rel="canonical" href="https://www.wowhead.com/classic/spells/professions/alchemy">
</head><body><script>
WH.Gatherer.addData(3, 4, {"7076":{"name_enus":"Essence of Earth","jsonequip":{}},
"7078":{"name_enus":"Essence of Fire","jsonequip":{}},
"7082":{"name_enus":"Essence of Air","jsonequip":{}},
"7080":{"name_enus":"Essence of Water","jsonequip":{}},
"12808":{"name_enus":"Essence of Undeath","jsonequip":{}},
"3371":{"name_enus":"Empty Vial","jsonequip":{"buyprice":4,"sellprice":1}},
"5000":{"name_enus":"Water Potion","jsonequip":{}}});
var listviewspells = [
{"id":17561,"name":"Transmute: Earth to Water","creates":[7080,1,1],"reagents":[[7076,1]],"learnedat":275},
{"id":17563,"name":"Transmute: Undeath to Water","creates":[7080,1,1],"reagents":[[12808,1]],"learnedat":275},
{"id":17564,"name":"Transmute: Water to Undeath","creates":[12808,1,1],"reagents":[[7080,1]],"learnedat":275},
{"id":17567,"name":"Transmute: Fire to Earth","creates":[7076,1,1],"reagents":[[7078,1]],"learnedat":275},
{"id":17559,"name":"Transmute: Air to Fire","creates":[7078,0,0],"reagents":[[7082,1]],"learnedat":275},
{"id":9000,"name":"Water Potion","creates":[5000,1,1],"reagents":[[7080,2],[3371,1]],"learnedat":200}];
</script></body></html>"""


def alchemy():
    return rc.read_page(ALCHEMY_PAGE.encode(), "classic", "alchemy", "2026-10-04")


def test_items_several_recipes_make_are_bought_and_their_recipes_not_offered():
    extract = alchemy()
    # Water has two transmutes and Fire's only one makes "0" (unknown), so both are bought; Earth and
    # Undeath each have one recipe that makes a fixed quantity.
    assert rc.recipe_counts(extract) == {"offered": 3, "no item": 0, "no fixed yield": 1, "shared item": 2,
                                         "seasonal": 0}
    assert [r["id"] for r in rc.candidate_recipes(extract)] == [9000, 17567, 17564]  # By skill, then name.
    catalog = build_catalog(extract, rc._draft_selection(extract, rc.choices([9000])))
    assert [r["recipe_id"] for r in catalog["recipes"]] == [9000]
    assert {i["item_id"]: i["role"] for i in catalog["items"]} == {3371: "material", 5000: "finished",
                                                                   7080: "material"}
    with pytest.raises(ValueError, match=r"17561 \(Transmute: Earth to Water\) make items other recipes also make"):
        build_catalog(extract, rc._draft_selection(extract, rc.choices([9000, 17561])))
    # Water to Undeath is offered; its Water is bought, so there is no loop.
    catalog = build_catalog(extract, rc._draft_selection(extract, rc.choices([17564])))
    assert [r["recipe_id"] for r in catalog["recipes"]] == [17564]


def test_comments_inside_a_block_stay_with_it_and_a_closing_comment_is_kept():
    text = (ROOT / "config/recipe-selections/forever-tailoring.toml").read_text(encoding="utf-8").replace(
        "recipe_id = 6686  # Red Linen Bag (pattern from a vendor or drop)\n",
        "recipe_id = 6686  # Red Linen Bag\n# Counted in game.\noutput_quantity_verified = true\n")
    extract = fixture_extract("forever")
    recipes = [3755, 3757, 18405]  # Drop Red Linen Bag: its override must not move to Linen Bag.
    used = used_items(extract, recipes)
    edited, _ = selection_files.edit_recipes(text, extract, recipes, [2320, 2321, 14341], used)
    assert all("output_quantity_verified" not in pick for pick in tomllib.loads(edited)["recipes"])
    assert "Counted in game" not in edited

    closing = SELECTION + "\n# Closing note.\n"
    extract = rc.read_page(PAGE.encode(), "forever", "tailoring", "2026-10-04")
    used = used_items(extract, [3755])
    assert selection_files.edit_recipes(closing, extract, [3755], [2320], used)[0] == closing


def test_a_version_bumped_by_hand_is_not_bumped_again(workspace):
    config, _ = workspace
    (entry,) = rc.find_catalogs(config)
    path = entry["selection_path"]
    path.write_text(path.read_text(encoding="utf-8").replace('catalog_version = "0.1"', 'catalog_version = "1.0"'),
                    encoding="utf-8")
    (entry,) = rc.find_catalogs(config)
    preview = rc.preview_update(entry, PAGE.encode(), "2026-10-01")
    assert preview["changed"] and preview["catalog_version"] == "1.0"
    assert tomllib.loads(preview["text"])["catalog_version"] == "1.0"
