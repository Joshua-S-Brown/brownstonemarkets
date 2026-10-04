from pathlib import Path

import pytest

from brownstone.crafting import evaluate_recipe, load_recipe_catalog, material_plan

CATALOG = Path(__file__).resolve().parents[1] / "config/forever-tailoring.toml"
CLASSIC_CATALOG = Path(__file__).resolve().parents[1] / "config/classic-era-tailoring.toml"


def test_runecloth_bag_expands_intermediate_quantities():
    catalog = load_recipe_catalog(CATALOG)
    assert catalog["game_version"] == "forever"
    # Forever adds two dyes to the Classic recipe (STORY-004).
    assert material_plan(catalog, 18405) == {8170: 2, 14047: 25, 14341: 1, 249409: 2, 249430: 4}


def test_classic_catalog_is_separate_but_supports_same_proof():
    catalog = load_recipe_catalog(CLASSIC_CATALOG)
    assert catalog["game_version"] == "classic"
    assert catalog["rules_version"] == "classic-era"
    assert material_plan(catalog, 18405) == {8170: 2, 14047: 25, 14341: 1}


def test_classic_catalog_quantities_and_vendor_prices_are_verified():
    # STORY-007: values checked against Wowhead Classic. Changing one needs new evidence.
    catalog = load_recipe_catalog(CLASSIC_CATALOG)
    for recipe in catalog["recipes_by_id"].values():
        assert recipe["verified_at"] and recipe["verification_url"].startswith("https://")
    for item in catalog["items_by_id"].values():
        if "vendor_price_copper" in item:
            assert item["vendor_price_source_url"].startswith("https://")
    assert {i: item["vendor_price_copper"] for i, item in catalog["items_by_id"].items()
            if "vendor_price_copper" in item} == {2321: 100, 4291: 500, 14341: 5000}
    assert {r: [(x["item_id"], x["quantity"]) for x in recipe["inputs"]]
            for r, recipe in catalog["recipes_by_id"].items()} == {
        2964: [(2592, 3)], 3757: [(2997, 3), (2321, 1)],
        3865: [(4338, 5)], 12065: [(4339, 4), (4291, 2)],
        18401: [(14047, 5)], 18405: [(14048, 5), (8170, 2), (14341, 1)],
    }


def test_catalog_rejects_non_https_verification(tmp_path):
    path = tmp_path / "bad-catalog.toml"
    path.write_text(CLASSIC_CATALOG.read_text().replace(
        'verification_url = "https://www.wowhead.com/classic/spells/professions/tailoring"',
        'verification_url = "http://example.com"'))
    with pytest.raises(ValueError, match="verification"):
        load_recipe_catalog(path)


def test_buy_versus_craft_uses_cheapest_valid_path_and_vendor_thread():
    catalog = load_recipe_catalog(CLASSIC_CATALOG)
    result = evaluate_recipe(catalog, 18405, {
        14046: 200_000,  # 20g finished bag
        14048: 60_000,   # 6g bolt; crafting is cheaper
        14047: 10_000,   # 1g raw cloth -> 5g bolt
        8170: 5_000,     # 50s leather
    })
    assert result["valid"]
    assert result["craft_cost_copper"] == 265_000  # 25g cloth + 1g leather + 50s thread
    assert result["net_revenue_copper"] == 190_000
    assert result["profit_copper"] == -75_000
    assert [choice["method"] for choice in result["choices"]] == ["craft", "buy", "vendor"]


def test_missing_prices_invalidate_estimate_instead_of_becoming_zero():
    catalog = load_recipe_catalog(CATALOG)
    result = evaluate_recipe(catalog, 18405, {14046: 200_000})
    assert not result["valid"]
    assert result["craft_cost_copper"] is None
    assert set(result["missing_item_ids"]) == {14048, 8170, 249430, 249409}
    assert result["profit_copper"] is None


def test_invalid_auction_cut_rejected():
    with pytest.raises(ValueError, match="auction_cut"):
        evaluate_recipe(load_recipe_catalog(CATALOG), 18405, {}, 1)


def test_recipe_cycle_is_rejected():
    catalog = load_recipe_catalog(CATALOG)
    catalog["recipe_for_output"][14047] = 18405
    with pytest.raises(ValueError, match="cycle"):
        material_plan(catalog, 18405)


@pytest.mark.parametrize("old, new", [
    ("vendor_price_copper = 100\n", "vendor_price_copper = 100.5\n"),
    ("vendor_price_copper = 100\n", "vendor_price_copper = true\n"),
    ("item_id = 2592\nquantity = 3\n", "item_id = 2592\nquantity = 2.5\n"),
    ("output_quantity = 1\n", "output_quantity = 1.0\n"),
])
def test_catalog_quantities_and_vendor_prices_must_be_positive_integers(tmp_path, old, new):
    # A fractional or boolean value would otherwise be silently ignored or break integer copper.
    text = CLASSIC_CATALOG.read_text()
    assert old in text
    path = tmp_path / "bad-catalog.toml"
    path.write_text(text.replace(old, new, 1))
    with pytest.raises(ValueError, match="positive"):
        load_recipe_catalog(path)
