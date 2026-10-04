"""STORY-004: catalogs generated offline from a Wowhead profession page saved in a browser."""
import copy
import json
import tomllib
from pathlib import Path

import pytest

from brownstone.crafting import load_recipe_catalog, material_plan
from brownstone.recipe_import import (
    archive_page,
    build_catalog,
    catalog_changes,
    dumps_catalog,
    extract_page,
    load_selection,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/wowhead"
# A miniature saved page in Wowhead's shape: unquoted keys, a bracket inside a name, a variable yield.
PAGE = """<html><head>
<link rel="canonical" href="https://www.wowhead.com/forever/spells/professions/tailoring">
</head><body><script>
WH.Gatherer.addData(3, 16, {"2589":{"name_enus":"Linen Cloth","jsonequip":{"sellprice":13}},
"2996":{"name_enus":"Bolt of Linen Cloth","jsonequip":{"sellprice":40}},
"2320":{"name_enus":"Coarse Thread","jsonequip":{"buyprice":10,"sellprice":2}},
"4238":{"name_enus":"Linen Bag [test]","jsonequip":{"sellprice":200}},
"9999":{"name_enus":"Lucky Bolt","jsonequip":{}}});
var listviewspells = [{"id":2963,"name":"Bolt of Linen Cloth","creates":[2996,1,1],"reagents":[[2589,2]],
"learnedat":1,"envChange":{"status":"unchanged"},quality:1,popularity:4},
{"id":3755,"name":"Linen Bag","creates":[4238,1,1],"reagents":[[2996,3],[2320,3]],"learnedat":45,
"envChange":{"status":"unchanged"},quality:1},
{"id":7777,"name":"Lucky Bolt","creates":[9999,1,3],"reagents":[[2589,1]],"learnedat":5,
"envChange":{"status":"new"}}];
new Listview({template: 'spell', data: listviewspells});
</script></body></html>"""


def extract(game="forever"):
    return json.loads((FIXTURES / f"{game}-tailoring-extract.json").read_text())


def selection(**overrides):
    return {"game_version": "forever", "rules_version": "forever-beta-1.60", "profession": "tailoring",
            "status": "beta-observed", "catalog_version": "0.1", "recipes": [{"recipe_id": 3755}],
            "items": [{"item_id": 2320, "vendor": True}], **overrides}


def test_parses_saved_page_data_including_unquoted_keys():
    page = extract_page(PAGE, "abc", "2026-10-04")
    assert page["source_url"] == "https://www.wowhead.com/forever/spells/professions/tailoring"
    assert (page["game_path"], page["profession"]) == ("forever", "tailoring")
    assert page["recipes"]["3755"]["reagents"] == [[2996, 3], [2320, 3]]
    assert page["items"]["4238"]["name"] == "Linen Bag [test]"
    assert page["items"]["2320"] == {"name": "Coarse Thread", "sellprice": 2, "buyprice": 10}


def test_rejects_pages_without_profession_data():
    with pytest.raises(ValueError, match="profession spell list"):
        extract_page("<html></html>", "abc", "2026-10-04")
    no_data = PAGE.replace("listviewspells", "somethingelse")
    with pytest.raises(ValueError, match="listviewspells"):
        extract_page(no_data, "abc", "2026-10-04")


def test_builds_intermediates_roles_and_vendor_prices_from_the_page():
    catalog = build_catalog(extract_page(PAGE, "abc", "2026-10-04"), selection())
    assert [r["recipe_id"] for r in catalog["recipes"]] == [2963, 3755]  # The bolt is added automatically.
    roles = {i["item_id"]: i["role"] for i in catalog["items"]}
    assert roles == {2320: "vendor_material", 2589: "material", 2996: "intermediate", 4238: "finished"}
    thread = next(i for i in catalog["items"] if i["item_id"] == 2320)
    assert thread["vendor_price_copper"] == 10  # The page's buy price, not sell price x 4 (8c).
    bag = catalog["recipes"][1]
    assert bag["required_skill"] == 45 and bag["evidence_sha256"] == "abc"
    assert bag["source_url"] == "https://www.wowhead.com/forever/spell=3755"


def test_buy_price_alone_never_makes_a_vendor_material():
    # Wowhead gives items no vendor sells (Felcloth, raid gear) a buy price, so vendor status needs evidence.
    catalog = build_catalog(extract_page(PAGE, "abc", "2026-10-04"), selection(items=[]))
    thread = next(i for i in catalog["items"] if i["item_id"] == 2320)
    assert thread["role"] == "material" and "vendor_price_copper" not in thread
    with pytest.raises(ValueError, match="no buy price"):
        build_catalog(extract_page(PAGE, "abc", "2026-10-04"), selection(items=[{"item_id": 2589, "vendor": True}]))


def test_variable_yields_and_unknown_recipes_are_rejected():
    page = extract_page(PAGE, "abc", "2026-10-04")
    with pytest.raises(ValueError, match="variable yields"):
        build_catalog(page, selection(recipes=[{"recipe_id": 7777}], items=[]))
    with pytest.raises(ValueError, match="not on the page"):
        build_catalog(page, selection(recipes=[{"recipe_id": 1}]))


def test_reagent_made_by_several_recipes_needs_an_explicit_choice():
    page = extract_page(PAGE, "abc", "2026-10-04")
    page["recipes"]["8888"] = {"id": 8888, "name": "Other Bolt", "learnedat": 1, "creates": [2996, 1, 1],
                               "reagents": [[2589, 3]]}
    with pytest.raises(ValueError, match="select exactly one"):
        build_catalog(page, selection())
    chosen = build_catalog(page, selection(recipes=[{"recipe_id": 3755}, {"recipe_id": 2963}]))
    assert {r["recipe_id"] for r in chosen["recipes"]} == {2963, 3755}


def test_never_builds_one_game_version_from_another_versions_page():
    with pytest.raises(ValueError, match="never borrow"):
        build_catalog(extract("classic"), load_selection(ROOT / "config/recipe-selections/forever-tailoring.toml"))
    with pytest.raises(ValueError, match="never borrow"):
        build_catalog(extract("forever"), load_selection(ROOT / "config/recipe-selections/classic-era-tailoring.toml"))


@pytest.mark.parametrize("game,name", [("classic", "classic-era-tailoring"), ("forever", "forever-tailoring")])
def test_tracked_catalogs_are_exactly_what_the_importer_generates(game, name):
    selected = load_selection(ROOT / f"config/recipe-selections/{name}.toml")
    generated = dumps_catalog(build_catalog(extract(game), selected))
    assert generated == (ROOT / f"config/{name}.toml").read_text(encoding="utf-8")


def test_classic_import_keeps_the_hand_verified_values_and_fills_skill_levels():
    # STORY-007 verified these by hand; the importer must reproduce them from the saved page.
    catalog = load_recipe_catalog(ROOT / "config/classic-era-tailoring.toml")
    assert catalog["catalog_version"] == "0.2"
    assert {r: recipe["required_skill"] for r, recipe in catalog["recipes_by_id"].items()} == {
        2964: 75, 3757: 80, 3865: 175, 12065: 225, 18401: 250, 18405: 260}
    assert not any("required_skill_verified" in recipe for recipe in catalog["recipes_by_id"].values())
    assert {i: item["role"] for i, item in catalog["items_by_id"].items()} == {
        2321: "vendor_material", 2592: "material", 2997: "intermediate", 4240: "finished",
        4291: "vendor_material", 4338: "material", 4339: "intermediate", 8170: "material",
        10050: "finished", 14046: "finished", 14047: "material", 14048: "intermediate",
        14341: "vendor_material"}


def test_forever_catalog_has_beta_tiers_new_dyes_and_only_forever_evidence():
    text = (ROOT / "config/forever-tailoring.toml").read_text(encoding="utf-8")
    assert "/classic/" not in text
    catalog = load_recipe_catalog(ROOT / "config/forever-tailoring.toml")
    finished = {i for i, item in catalog["items_by_id"].items() if item["role"] == "finished"}
    assert finished == {4238, 5762, 4240, 14046}  # Linen, Red Linen, Woolen and Runecloth bags.
    assert material_plan(catalog, 3755) == {2320: 3, 2589: 6}
    assert material_plan(catalog, 18405) == {8170: 2, 14047: 25, 14341: 1, 249409: 2, 249430: 4}
    runecloth_bag = catalog["recipes_by_id"][18405]
    assert runecloth_bag["availability"] == "post-launch"
    assert {catalog["items_by_id"][i]["availability"] for i in (249409, 249430)} == {"post-launch"}
    for recipe in catalog["recipes_by_id"].values():
        assert recipe["output_quantity"] == 1 and recipe["output_quantity_verified"] is False
    assert all(item.get("vendor_verified") is False for item in catalog["items_by_id"].values()
               if item["role"] == "vendor_material")


def test_archive_keeps_bytes_once_and_remembers_the_saved_date(tmp_path):
    page = tmp_path / "Forever Spells.html"
    page.write_text(PAGE, encoding="utf-8")
    archive = tmp_path / "archive"
    copy_path, manifest = archive_page(page, archive, "2026-10-04")
    assert copy_path.read_bytes() == page.read_bytes()
    assert copy_path.parent == archive / "wowhead/forever/tailoring"
    assert manifest["source_url"].endswith("/forever/spells/professions/tailoring")
    again, second = archive_page(copy_path, archive)  # Rebuilding from the archive keeps the original date.
    assert again == copy_path and second["saved_at"] == "2026-10-04"
    assert second["archived_at"] == manifest["archived_at"]
    assert len(list(copy_path.parent.iterdir())) == 2  # One page, one manifest.


def test_catalog_changes_lists_recipe_and_price_differences():
    old = tomllib.loads((ROOT / "config/forever-tailoring.toml").read_text(encoding="utf-8"))
    new = copy.deepcopy(old)
    new["recipes"][0]["inputs"][0]["quantity"] += 1
    new["items"][0]["vendor_price_copper"] = 12
    new["recipes"].pop()
    changes = catalog_changes(old, new)
    assert any(line.startswith("changed recipe 2963") for line in changes)
    assert any(line.startswith("removed recipe 18405") for line in changes)
    assert "vendor price of item 2320: 10 -> 12" in changes
    assert catalog_changes(old, old) == []
