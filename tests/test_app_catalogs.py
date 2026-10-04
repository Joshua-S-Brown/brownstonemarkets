"""STORY-014 Slice 2 in the app: the Recipe catalogs page previews before every write."""
from pathlib import Path

import pytest
from test_app import classic_sources
from test_recipe_catalogs import CHANGED_PAGE, LEATHER_PAGE, make_workspace, tree

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402  (only after the skip check)

ROOT = Path(__file__).resolve().parents[1]


def open_page(tmp_path, monkeypatch):
    config, archive = make_workspace(tmp_path)
    sources = classic_sources(tmp_path)
    monkeypatch.setattr("brownstone.config.read_sources", lambda *args: sources)
    monkeypatch.setattr("brownstone.recipe_catalogs.CONFIG_DIR", config)
    monkeypatch.setattr("brownstone.recipe_catalogs.ARCHIVE_DIR", archive)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    at.radio[0].set_value("Recipe catalogs").run()
    assert not at.exception
    return at, config


def button(at, label):
    return next(b for b in at.button if b.label == label)


def widget(items, label):
    return next(w for w in items if w.label.startswith(label))


def upload(at, page, name="Forever Spells.html"):
    widget(at.radio, "Page").set_value("upload").run()
    at.file_uploader[0].set_value((name, page.encode(), "text/html")).run()


def start_add(at, profession):
    [s for s in at.selectbox if s.label == "Profession"][-1].set_value(profession).run()  # The Add tab's.


def test_catalogs_page_shows_one_game_version_at_a_time(tmp_path, monkeypatch):
    at, _ = open_page(tmp_path, monkeypatch)
    assert any(m.value == "#### WoW Forever catalogs" for m in at.markdown)
    table = at.dataframe[0].value
    assert list(table["Profession"]) == ["Tailoring"]
    assert table.iloc[0]["Version"] == "0.1" and table.iloc[0]["Recipes"] == 2
    assert any(c.value.startswith("No WoW Forever catalog yet: alchemy") and "tailoring" not in c.value
               for c in at.caption)
    widget(at.radio, "Game version").set_value("classic").run()
    assert not at.exception
    assert any(m.value == "#### Classic Era catalogs" for m in at.markdown)
    assert not at.dataframe  # The Forever catalog isn't shown on the Classic view.
    assert any("tailoring" in c.value for c in at.caption if c.value.startswith("No Classic Era catalog yet"))
    assert any("No Classic Era catalogs yet" in i.value for i in at.info)


def test_update_from_a_new_page_previews_then_regenerates_on_a_separate_click(tmp_path, monkeypatch):
    at, config = open_page(tmp_path, monkeypatch)
    upload(at, CHANGED_PAGE)
    before = tree(tmp_path)
    button(at, "Preview changes").click().run()
    assert not at.exception
    assert tree(tmp_path) == before  # A preview writes nothing.
    changes = next(d.value for d in at.dataframe if "Change" in d.value.columns)
    assert any(line.startswith("changed recipe 2963") for line in changes["Change"])
    assert any("version **0.2**" in m.value for m in at.markdown)
    button(at, "Regenerate").click().run()
    assert not at.exception
    assert any("catalog version 0.2" in s.value for s in at.success)
    listed = next(m.value for m in at.markdown if "Changed tracked files" in m.value)
    assert "forever-tailoring.toml" in listed and "recipe-selections" in listed
    assert 'catalog_version = "0.2"' in (config / "forever-tailoring.toml").read_text(encoding="utf-8")
    assert at.dataframe[0].value.iloc[0]["Version"] == "0.2"  # The status table reloaded.


def test_update_edits_recipes_and_vendors_from_the_archived_page(tmp_path, monkeypatch):
    at, config = open_page(tmp_path, monkeypatch)
    assert widget(at.radio, "Page").value == "archived"  # No upload needed to change choices.
    assert widget(at.multiselect, "Recipes").value == [3755]
    assert widget(at.multiselect, "Sold by vendors").value == [2320]
    button(at, "Preview changes").click().run()
    assert any("Nothing would change" in i.value for i in at.info)
    widget(at.multiselect, "Sold by vendors").set_value([]).run()
    button(at, "Preview changes").click().run()
    assert not at.exception
    assert any("Coarse Thread (vendor mark)" in w.value for w in at.warning)
    button(at, "Regenerate").click().run()
    assert not at.exception
    selection = (config / "recipe-selections/forever-tailoring.toml").read_text(encoding="utf-8")
    assert "vendor" not in selection and 'catalog_version = "0.2"' in selection
    assert widget(at.multiselect, "Sold by vendors").value == []  # Choices restart from the written files.


def test_update_refuses_a_page_from_another_game_version(tmp_path, monkeypatch):
    at, _ = open_page(tmp_path, monkeypatch)
    upload(at, CHANGED_PAGE.replace("/forever/", "/classic/"), "Classic Spells.html")
    assert any("never borrow" in e.value for e in at.error)
    assert not any(b.label in ("Preview changes", "Regenerate") for b in at.button)


def test_add_a_profession_previews_then_creates_its_selection_and_catalog(tmp_path, monkeypatch):
    at, config = open_page(tmp_path, monkeypatch)
    start_add(at, "leatherworking")
    assert any("wowhead.com/forever/spells/professions/leatherworking" in m.value for m in at.markdown)
    at.file_uploader[-1].set_value(("Forever Leatherworking.html", LEATHER_PAGE.encode(), "text/html")).run()
    assert not at.exception
    assert any("2 of 3 recipes on this page" in c.value for c in at.caption)  # Lucky Bolt has no fixed yield.
    adding = [m for m in at.multiselect if m.label == "Recipes"][-1]
    assert adding.value == []
    [b for b in at.button if b.label == "Add all 2 matching"][-1].click().run()
    adding = [m for m in at.multiselect if m.label == "Recipes"][-1]
    assert adding.value == [2963, 3755]
    adding.set_value([3755]).run()
    [m for m in at.multiselect if m.label.startswith("Sold by vendors")][-1].set_value([2320]).run()
    assert any("rules_version" in i.value for i in at.info)  # No enabled Forever market names one.
    widget(at.text_input, "Rules version").set_value("forever-beta-1.60").run()
    button(at, "Preview catalog").click().run()
    assert not at.exception
    assert not (config / "forever-leatherworking.toml").exists()
    assert any("2 recipes (1 intermediates added)" in m.value for m in at.markdown)
    button(at, "Create catalog").click().run()
    assert not at.exception
    assert any("Wrote forever-leatherworking" in s.value for s in at.success)
    assert (config / "recipe-selections/forever-leatherworking.toml").exists()
    assert "Leatherworking" in list(at.dataframe[0].value["Profession"])
    # Leatherworking now sorts first; the Update tab stays on Tailoring.
    assert [s for s in at.selectbox if s.label == "Profession"][0].value == "forever-tailoring"


def test_matching_recipes_are_added_and_removed_by_name(tmp_path, monkeypatch):
    at, _ = open_page(tmp_path, monkeypatch)
    widget(at.text_input, "Recipe name contains").set_value("bolt").run()
    button(at, "Add all 1 matching").click().run()
    assert widget(at.multiselect, "Recipes").value == [2963, 3755]
    button(at, "Remove all 1 matching").click().run()
    assert widget(at.multiselect, "Recipes").value == [3755]


def test_add_refuses_a_page_for_another_profession(tmp_path, monkeypatch):
    at, _ = open_page(tmp_path, monkeypatch)
    start_add(at, "alchemy")
    at.file_uploader[-1].set_value(("Leatherworking.html", LEATHER_PAGE.encode(), "text/html")).run()
    assert any("never borrow" in e.value for e in at.error)
    assert not any(b.label == "Preview catalog" for b in at.button)


def test_changing_the_selection_after_a_preview_needs_a_new_preview(tmp_path, monkeypatch):
    at, config = open_page(tmp_path, monkeypatch)
    upload(at, CHANGED_PAGE)
    button(at, "Preview changes").click().run()
    assert any(b.label == "Regenerate" for b in at.button)
    selection = config / "recipe-selections/forever-tailoring.toml"
    selection.write_text(selection.read_text(encoding="utf-8") + "# edited elsewhere\n", encoding="utf-8")
    at.run()
    assert not any(b.label == "Regenerate" for b in at.button)


def test_pages_without_skill_levels_still_offer_recipes(tmp_path, monkeypatch):
    at, _ = open_page(tmp_path, monkeypatch)
    start_add(at, "leatherworking")
    page = LEATHER_PAGE.replace('"learnedat":1,', '').replace('"learnedat":45,', '').replace('"learnedat":5,', '')
    at.file_uploader[-1].set_value(("Leatherworking.html", page.encode(), "text/html")).run()
    assert not at.exception
    assert any(b.label == "Add all 2 matching" for b in at.button)


def test_crafting_without_any_catalog_points_to_the_catalogs_page(tmp_path, monkeypatch):
    sources = classic_sources(tmp_path)
    (tmp_path / "config").mkdir()
    monkeypatch.setattr("brownstone.config.read_sources", lambda *args: sources)
    monkeypatch.setattr("brownstone.recipe_catalogs.CONFIG_DIR", tmp_path / "config")
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    at.radio[0].set_value("Crafting").run()
    assert not at.exception
    assert any("Add a profession" in i.value for i in at.info)


def test_a_broken_selection_file_leaves_the_other_views_working(tmp_path, monkeypatch):
    sources = classic_sources(tmp_path)
    (tmp_path / "config/recipe-selections").mkdir(parents=True)
    (tmp_path / "config/recipe-selections/forever-alchemy.toml").write_text('profession = "alchemy"\n')
    monkeypatch.setattr("brownstone.config.read_sources", lambda *args: sources)
    monkeypatch.setattr("brownstone.recipe_catalogs.CONFIG_DIR", tmp_path / "config")
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception
    assert any("Recipe catalogs unavailable" in w.value for w in at.warning)
    at.radio[0].set_value("Recipe catalogs").run()
    assert any("Could not read the selection files" in e.value for e in at.error)
