"""STORY-014 Slice 2 in the app: the Recipe catalogs page reviews every write live, then saves on one click."""
from pathlib import Path

import pytest
from test_app import classic_sources
from test_recipe_catalogs import CHANGED_PAGE, LEATHER_PAGE, make_workspace, tree

from brownstone.config import read_sources

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402  (only after the skip check)

ROOT = Path(__file__).resolve().parents[1]


def open_page(tmp_path, monkeypatch, experience="forever", forever_rules=True):
    """The Recipe catalogs page for the sidebar experience (Classic and an enabled Forever source)."""
    config, archive = make_workspace(tmp_path)
    sources = classic_sources(tmp_path)
    forever = next(source for source in read_sources(ROOT / "config/market.toml")
                   if source["game_version"] == "forever")
    forever = {**forever, "enabled": True, "data_dir": tmp_path / "forever"}
    if not forever_rules:
        forever.pop("rules_version", None)
    sources.append(forever)
    monkeypatch.setattr("brownstone.config.read_sources", lambda *args: sources)
    monkeypatch.setattr("brownstone.recipe_catalogs.CONFIG_DIR", config)
    monkeypatch.setattr("brownstone.recipe_catalogs.ARCHIVE_DIR", archive)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    widget(at.selectbox, "Experience").set_value(experience).run()
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


def save(at):
    return next(b for b in at.button if b.label == "Save catalog")


def start_add(at, profession):
    widget(at.selectbox, "1. Profession").set_value(f"new:{profession}").run()


def test_catalogs_page_follows_the_sidebar_experience(tmp_path, monkeypatch):
    at, _ = open_page(tmp_path, monkeypatch)
    assert not any(w.label == "Game version" for w in at.radio)  # No second experience choice on the page.
    assert any(c.value.startswith("Showing **WoW Forever**") for c in at.caption)
    assert any(m.value == "#### WoW Forever catalogs" for m in at.markdown)
    table = at.dataframe[0].value
    assert list(table["Profession"]) == ["Tailoring"]
    assert table.iloc[0]["Version"] == "0.1" and table.iloc[0]["Recipes"] == 2 and table.iloc[0]["Items"] > 0
    assert widget(at.selectbox, "1. Profession").value == "forever-tailoring"  # Existing catalogs come first.
    assert any(c.value.startswith("No WoW Forever catalog yet: alchemy") and "tailoring" not in c.value
               for c in at.caption)
    widget(at.selectbox, "Experience").set_value("classic").run()
    at.radio[0].set_value("Recipe catalogs").run()  # Each source remembers its own view.
    assert not at.exception
    assert any(c.value.startswith("Showing **Classic Era**") for c in at.caption)
    assert any(m.value == "#### Classic Era catalogs" for m in at.markdown)
    assert not at.dataframe  # The Forever catalog isn't shown on the Classic view.
    assert any("tailoring" in c.value for c in at.caption if c.value.startswith("No Classic Era catalog yet"))
    assert any("No Classic Era catalogs yet" in i.value for i in at.info)
    widget(at.selectbox, "Experience").set_value("retail").run()
    widget(at.selectbox, "Data source").set_value(0).run()
    at.radio[0].set_value("Recipe catalogs").run()
    assert not at.exception
    assert any("Retail (regression) has no recipe catalogs" in i.value for i in at.info)
    assert not at.dataframe and not at.tabs


def test_update_from_a_new_page_reviews_live_then_saves_on_one_click(tmp_path, monkeypatch):
    at, config = open_page(tmp_path, monkeypatch)
    before = tree(tmp_path)
    upload(at, CHANGED_PAGE)
    assert not at.exception
    assert tree(tmp_path) == before  # The review writes nothing.
    changes = next(d.value for d in at.dataframe if "Change" in d.value.columns)
    assert any(line.startswith("changed recipe 2963") for line in changes["Change"])
    assert any("version **0.2**" in m.value and "**2 recipes** (now 2: 0 added, 0 removed)" in m.value
               for m in at.markdown)
    save(at).click().run()
    assert not at.exception
    assert any("catalog version 0.2" in s.value for s in at.success)
    listed = next(m.value for m in at.markdown if "Changed tracked files" in m.value)
    assert "forever-tailoring.toml" in listed and "recipe-selections" in listed
    assert 'catalog_version = "0.2"' in (config / "forever-tailoring.toml").read_text(encoding="utf-8")
    assert at.dataframe[0].value.iloc[0]["Version"] == "0.2"  # The status table reloaded.
    assert widget(at.selectbox, "1. Profession").value == "forever-tailoring"


def test_update_edits_recipes_and_vendors_from_the_archived_page(tmp_path, monkeypatch):
    at, config = open_page(tmp_path, monkeypatch)
    assert widget(at.radio, "Page").value == "archived"  # No upload needed to change choices.
    assert widget(at.multiselect, "Recipes").value == [3755]
    assert widget(at.multiselect, "Sold by vendors").value == [2320]
    assert any("Nothing to save" in i.value for i in at.info)
    assert not any(b.label == "Save catalog" for b in at.button)
    widget(at.multiselect, "Sold by vendors").set_value([]).run()
    assert not at.exception
    assert any("Coarse Thread (vendor mark)" in w.value for w in at.warning)
    save(at).click().run()
    assert not at.exception
    selection = (config / "recipe-selections/forever-tailoring.toml").read_text(encoding="utf-8")
    assert "vendor" not in selection and 'catalog_version = "0.2"' in selection
    assert widget(at.multiselect, "Sold by vendors").value == []  # Choices restart from the written files.


def test_the_review_names_recipes_added_and_removed(tmp_path, monkeypatch):
    at, _ = open_page(tmp_path, monkeypatch)
    widget(at.multiselect, "Recipes").set_value([2963]).run()  # Bolt alone: Linen Bag leaves the catalog.
    assert not at.exception
    assert any("**1 recipe** (now 2: 0 added, 1 removed)" in m.value for m in at.markdown)
    assert any(e.label == "Recipes removed (1)" for e in at.expander)
    assert not any(e.label.startswith("Recipes added") for e in at.expander)


def test_update_refuses_a_page_from_another_game_version(tmp_path, monkeypatch):
    at, _ = open_page(tmp_path, monkeypatch)
    upload(at, CHANGED_PAGE.replace("/forever/", "/classic/"), "Classic Spells.html")
    assert any("never borrow" in e.value for e in at.error)
    assert not any(b.label == "Save catalog" for b in at.button)


def test_add_a_profession_reviews_then_creates_its_selection_and_catalog(tmp_path, monkeypatch):
    at, config = open_page(tmp_path, monkeypatch, forever_rules=False)
    options = widget(at.selectbox, "1. Profession").options
    assert any(o.startswith("Leatherworking · new catalog") for o in options)
    assert any(o.startswith("Tailoring · update (2 recipes)") for o in options)
    start_add(at, "leatherworking")
    assert any("wowhead.com/forever/spells/professions/leatherworking" in m.value for m in at.markdown)
    at.file_uploader[-1].set_value(("Forever Leatherworking.html", LEATHER_PAGE.encode(), "text/html")).run()
    assert not at.exception
    assert any("2 of 3 recipes on this page" in c.value for c in at.caption)  # Lucky Bolt has no fixed yield.
    adding = widget(at.multiselect, "Recipes")
    assert adding.value == []
    button(at, "Add all 2 matching").click().run()
    adding = widget(at.multiselect, "Recipes")
    assert adding.value == [2963, 3755]
    adding.set_value([3755]).run()
    widget(at.multiselect, "Sold by vendors").set_value([2320]).run()
    assert any("rules_version" in i.value for i in at.info)  # No enabled Forever market names one.
    assert not any(b.label == "Save catalog" for b in at.button)
    widget(at.text_input, "Rules version").set_value("forever-beta-1.60").run()
    assert not at.exception
    assert not (config / "forever-leatherworking.toml").exists()  # The review writes nothing.
    assert any("**2 recipes** (now 0: 2 added, 0 removed)" in m.value for m in at.markdown)
    save(at).click().run()
    assert not at.exception
    assert any("Saved forever-leatherworking" in s.value for s in at.success)
    assert (config / "recipe-selections/forever-leatherworking.toml").exists()
    assert "Leatherworking" in list(at.dataframe[0].value["Profession"])
    # The profession just saved stays selected, now as an update.
    assert widget(at.selectbox, "1. Profession").value == "forever-leatherworking"


def test_matching_recipes_are_added_and_removed_by_name(tmp_path, monkeypatch):
    at, _ = open_page(tmp_path, monkeypatch)
    widget(at.text_input, "Recipe name contains").set_value("bolt").run()
    button(at, "Add all 1 matching").click().run()
    assert widget(at.multiselect, "Recipes").value == [2963, 3755]
    button(at, "Remove all 1 matching").click().run()
    assert widget(at.multiselect, "Recipes").value == [3755]


def test_secondary_skills_link_to_their_own_wowhead_page(tmp_path, monkeypatch):
    at, _ = open_page(tmp_path, monkeypatch)
    start_add(at, "first-aid")
    assert any("wowhead.com/forever/spells/secondary-skills/first-aid" in m.value for m in at.markdown)


def test_add_refuses_a_page_for_another_profession(tmp_path, monkeypatch):
    at, _ = open_page(tmp_path, monkeypatch)
    start_add(at, "alchemy")
    at.file_uploader[-1].set_value(("Leatherworking.html", LEATHER_PAGE.encode(), "text/html")).run()
    assert any("never borrow" in e.value for e in at.error)
    assert not any(b.label == "Save catalog" for b in at.button)


def test_a_save_click_on_a_review_the_files_have_since_changed_writes_nothing(tmp_path, monkeypatch):
    at, config = open_page(tmp_path, monkeypatch)
    upload(at, CHANGED_PAGE)
    stale = save(at)
    selection = config / "recipe-selections/forever-tailoring.toml"
    edited = selection.read_text(encoding="utf-8") + "# edited elsewhere\n"
    selection.write_text(edited, encoding="utf-8")
    catalog = (config / "forever-tailoring.toml").read_text(encoding="utf-8")
    stale.click().run()
    assert not at.exception
    assert selection.read_text(encoding="utf-8") == edited  # The old review's click did nothing.
    assert (config / "forever-tailoring.toml").read_text(encoding="utf-8") == catalog
    assert not at.success
    assert any(b.label == "Save catalog" for b in at.button)  # A fresh review of the new files.


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
    assert any("Add or update a profession" in i.value for i in at.info)


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
