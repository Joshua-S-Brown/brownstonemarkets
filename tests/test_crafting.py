from pathlib import Path
import pytest

from brownstone.crafting import evaluate_recipe, load_recipe_catalog, material_plan


CATALOG = Path(__file__).resolve().parents[1] / "config/forever-tailoring.toml"
CLASSIC_CATALOG = Path(__file__).resolve().parents[1] / "config/classic-era-tailoring.toml"


def test_runecloth_bag_expands_intermediate_quantities():
    catalog = load_recipe_catalog(CATALOG)
    assert catalog["game_version"] == "forever"
    assert material_plan(catalog, 18405) == {8170: 2, 14047: 20, 14341: 1}


def test_classic_catalog_is_separate_but_supports_same_proof():
    catalog = load_recipe_catalog(CLASSIC_CATALOG)
    assert catalog["game_version"] == "classic"
    assert catalog["ruleset"] == "classic-era"
    assert material_plan(catalog, 18405) == {8170: 2, 14047: 20, 14341: 1}


def test_buy_versus_craft_uses_cheapest_valid_path_and_vendor_thread():
    catalog = load_recipe_catalog(CATALOG)
    result = evaluate_recipe(catalog, 18405, {
        14046: 200_000,  # 20g finished bag
        14048: 50_000,   # 5g bolt; crafting is cheaper
        14047: 10_000,   # 1g raw cloth -> 4g bolt
        8170: 5_000,     # 50s leather
    })
    assert result["valid"]
    assert result["craft_cost_copper"] == 215_000  # 20g cloth + 1g leather + 50s thread
    assert result["net_revenue_copper"] == 190_000
    assert result["profit_copper"] == -25_000
    assert [choice["method"] for choice in result["choices"]] == ["craft", "buy", "vendor"]


def test_missing_prices_invalidate_estimate_instead_of_becoming_zero():
    catalog = load_recipe_catalog(CATALOG)
    result = evaluate_recipe(catalog, 18405, {14046: 200_000})
    assert not result["valid"]
    assert result["craft_cost_copper"] is None
    assert set(result["missing_item_ids"]) == {14048, 8170}
    assert result["profit_copper"] is None


def test_invalid_auction_cut_rejected():
    with pytest.raises(ValueError, match="auction_cut"):
        evaluate_recipe(load_recipe_catalog(CATALOG), 18405, {}, 1)


def test_recipe_cycle_is_rejected():
    catalog = load_recipe_catalog(CATALOG)
    catalog["recipe_for_output"][14047] = 18405
    with pytest.raises(ValueError, match="cycle"):
        material_plan(catalog, 18405)
