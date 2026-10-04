from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb
import pytest

from brownstone.action_board import MARKET, rank_recipes
from brownstone.crafting import evaluate_recipe, load_recipe_catalog, material_plan
from brownstone.storage import recipe_prices

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def catalog():
    return load_recipe_catalog(ROOT / "config/classic-era-tailoring.toml")


def snapshot(**overrides):
    return {**MARKET, "collected_at": NOW.isoformat(), "updated_at": None, **overrides}


def prices():
    return {2592: 10, 4240: 1000, 4338: 100, 10050: 10000,
            14047: 1000, 8170: 500, 14046: 20000}


def board(**kwargs):
    return rank_recipes(catalog(), prices(), MARKET, snapshot(), now=NOW, **kwargs)


def test_representative_catalog_quantities_and_version():
    c = catalog()
    assert c["catalog_version"] == "0.1"
    assert material_plan(c, 3757) == {2321: 1, 2592: 9}
    assert material_plan(c, 12065) == {4291: 2, 4338: 20}
    assert material_plan(c, 18405) == {8170: 2, 14047: 25, 14341: 1}
    assert len(board()["rows"]) == 3  # No intermediate bolts ranked as bags.


def test_profit_and_margin_ranking_are_distinct_and_missing_last():
    assert [r["recipe_id"] for r in board()["rows"]] == [12065, 3757, 18405]
    assert [r["recipe_id"] for r in board(sort_by="margin")["rows"]] == [3757, 12065, 18405]
    p = prices()
    p[10050] = 0
    rows = rank_recipes(catalog(), p, MARKET, snapshot(), now=NOW)["rows"]
    assert rows[-1]["action"] == "missing prices"
    assert rows[-1]["profit_copper"] is None
    assert rows[0]["action"] == "potential craft"
    assert next(r for r in rows if r["recipe_id"] == 18405)["action"] == "negative margin"


@pytest.mark.parametrize("basis", ["updated_at", "collected_at"])
def test_independent_freshness_basis_and_stale_boundary(basis):
    metadata = snapshot(**{basis: (NOW - timedelta(hours=24)).isoformat()})
    result = rank_recipes(catalog(), prices(), MARKET, metadata, now=NOW)
    assert not result["stale"]
    assert result["freshness_basis"] == ("upstream scan" if basis == "updated_at" else "collection")
    metadata[basis] = (NOW - timedelta(hours=24, seconds=1)).isoformat()
    result = rank_recipes(catalog(), prices(), MARKET, metadata, now=NOW)
    assert {r["action"] for r in result["rows"]} == {"stale data"}
    p = prices()
    p[2592] = 0
    result = rank_recipes(catalog(), p, MARKET, metadata, now=NOW)
    assert result["rows"][-1]["action"] == "missing prices"


@pytest.mark.parametrize("key,value", [("game_version", "retail"), ("region", "eu"),
    ("realm", "mankrik-horde"), ("scope", "region"), ("market_id", "other")])
def test_rejects_incompatible_snapshot_scope(key, value):
    with pytest.raises(ValueError, match="Mankrik"):
        rank_recipes(catalog(), prices(), MARKET, snapshot(**{key: value}), now=NOW)


def test_forever_catalog_cannot_use_classic_prices():
    c = load_recipe_catalog(ROOT / "config/forever-tailoring.toml")
    with pytest.raises(ValueError, match="catalog"):
        rank_recipes(c, prices(), MARKET, snapshot(), now=NOW)


def test_selected_shopping_routes_and_break_even_rounding():
    p = {**prices(), 2997: 20}
    result = evaluate_recipe(catalog(), 3757, p)
    assert result["shopping_list"] == {2321: 1, 2997: 3}
    assert result["expanded_materials"] == {2321: 1, 2592: 9}
    assert result["choices"][0]["method"] == "buy"
    assert result["choices"][0]["total_cost_copper"] == 60
    assert result["craft_cost_copper"] == 160
    assert result["break_even_copper"] == 169
    result = evaluate_recipe(catalog(), 3757, {**p, 4240: 169})
    assert result["profit_copper"] == 0
    assert result["margin"] == 0
    result = evaluate_recipe(catalog(), 3757, {**p, 4240: 168})
    assert result["profit_copper"] == -1
    assert evaluate_recipe(catalog(), 3757, {4240: 100, 2592: 0})["craft_cost_copper"] is None


def test_multi_output_units_and_vendor_vs_market():
    c = catalog()
    c["recipes_by_id"][3757]["output_quantity"] = 2
    result = evaluate_recipe(c, 3757, {**prices(), 2321: 50})
    assert result["craft_cost_copper"] == 140
    assert result["net_revenue_copper"] == 1900
    assert result["break_even_copper"] == 74
    assert result["choices"][1]["method"] == "buy"


def test_price_read_enforces_full_market_identity():
    with duckdb.connect(":memory:") as db:
        db.execute("CREATE TABLE market_snapshots (snapshot_id VARCHAR, item_id INTEGER, min_buyout INTEGER, market_id VARCHAR, game_version VARCHAR, region VARCHAR, scope VARCHAR, realm VARCHAR)")
        db.execute("INSERT INTO market_snapshots VALUES ('same', 4240, 400, ?, ?, ?, ?, ?)", list(MARKET.values()))
        db.execute("INSERT INTO market_snapshots VALUES ('same', 4240, 999, ?, 'retail', 'us', 'realm', 'area-52')", [MARKET["market_id"]])
        assert recipe_prices(db, MARKET, "same", [4240]) == {4240: 400}
        assert recipe_prices(db, {**MARKET, "realm": "wrong"}, "same", [4240]) == {}


def test_future_snapshot_is_non_actionable_and_ties_are_stable():
    metadata = snapshot(collected_at=(NOW + timedelta(hours=1)).isoformat())
    assert {r["action"] for r in rank_recipes(catalog(), prices(), MARKET, metadata, now=NOW)["rows"]} == {"stale data"}
    c = catalog()
    for recipe in c["recipes_by_id"].values():
        if c["items_by_id"][recipe["output_item_id"]]["role"] == "finished":
            recipe["inputs"] = [{"item_id": 2321, "quantity": 1}]
    p = {4240: 100, 10050: 100, 14046: 100}
    result = rank_recipes(c, p, MARKET, snapshot(), now=NOW, auction_cut=0)
    assert [r["recipe_id"] for r in result["rows"]] == [3757, 12065, 18405]
    assert {r["action"] for r in result["rows"]} == {"negative margin"}


def test_copper_math_does_not_lose_a_copper_to_float_rounding():
    result = evaluate_recipe(catalog(), 3757, {**prices(), 4240: 100}, auction_cut=.07)
    assert result["net_revenue_copper"] == 93
    assert sum(c["total_cost_copper"] for c in result["shopping_choices"]) == result["craft_cost_copper"]
