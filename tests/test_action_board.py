from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb
import pytest

from brownstone.action_board import compatible, rank_recipes
from brownstone.crafting import basis_prices, evaluate_recipe, load_recipe_catalog, material_plan
from brownstone.storage import price_observations

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)
MARKET = {"market_id": "classic-us-mankrik-alliance", "game_version": "classic",
          "region": "us", "scope": "realm", "realm": "mankrik-alliance", "ruleset": "classic-era"}


def catalog():
    return load_recipe_catalog(ROOT / "config/classic-era-tailoring.toml")


def snapshot(**overrides):
    return {**MARKET, "collected_at": NOW.isoformat(), "updated_at": None, **overrides}


def prices():
    return {2592: 10, 4240: 1000, 4338: 100, 10050: 10000,
            14047: 1000, 8170: 500, 14046: 20000}


def observed(p, market_values=None):
    """Listed prices; market value equals min buyout unless overridden, so bases agree."""
    market_values = market_values or {}
    return {i: {"min_buyout": v, "market_value": market_values.get(i, v)} for i, v in p.items()}


def board(**kwargs):
    return rank_recipes(catalog(), observed(prices()), MARKET, snapshot(), now=NOW, **kwargs)


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
    rows = rank_recipes(catalog(), observed(p), MARKET, snapshot(), now=NOW)["rows"]
    assert rows[-1]["action"] == "missing prices"
    assert rows[-1]["profit_copper"] is None
    assert rows[0]["action"] == "potential craft"
    assert next(r for r in rows if r["recipe_id"] == 18405)["action"] == "negative margin"


@pytest.mark.parametrize("basis", ["updated_at", "collected_at"])
def test_independent_freshness_basis_and_stale_boundary(basis):
    metadata = snapshot(**{basis: (NOW - timedelta(hours=24)).isoformat()})
    result = rank_recipes(catalog(), observed(prices()), MARKET, metadata, now=NOW)
    assert not result["freshness"]["stale"]
    assert result["freshness"]["basis"] == ("upstream scan" if basis == "updated_at" else "collection")
    metadata[basis] = (NOW - timedelta(hours=24, seconds=1)).isoformat()
    result = rank_recipes(catalog(), observed(prices()), MARKET, metadata, now=NOW)
    assert {r["action"] for r in result["rows"]} == {"stale data"}
    p = prices()
    p[2592] = 0
    result = rank_recipes(catalog(), observed(p), MARKET, metadata, now=NOW)
    assert result["rows"][-1]["action"] == "missing prices"


@pytest.mark.parametrize("key,value", [("game_version", "retail"), ("region", "eu"),
    ("realm", "mankrik-horde"), ("scope", "region"), ("market_id", "other")])
def test_rejects_incompatible_snapshot_scope(key, value):
    with pytest.raises(ValueError, match="different market"):
        rank_recipes(catalog(), observed(prices()), MARKET, snapshot(**{key: value}), now=NOW)


def test_forever_catalog_cannot_use_classic_prices():
    c = load_recipe_catalog(ROOT / "config/forever-tailoring.toml")
    with pytest.raises(ValueError, match="ruleset"):
        rank_recipes(c, observed(prices()), MARKET, snapshot(), now=NOW)


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
        db.execute("CREATE TABLE market_snapshots (snapshot_id VARCHAR, item_id INTEGER, min_buyout INTEGER, market_value INTEGER, market_id VARCHAR, game_version VARCHAR, region VARCHAR, scope VARCHAR, realm VARCHAR)")
        identity = [MARKET[key] for key in ("market_id", "game_version", "region", "scope", "realm")]
        db.execute("INSERT INTO market_snapshots VALUES ('same', 4240, 400, 450, ?, ?, ?, ?, ?)", identity)
        db.execute("INSERT INTO market_snapshots VALUES ('same', 4240, 999, 999, ?, 'retail', 'us', 'realm', 'area-52')", [MARKET["market_id"]])
        assert price_observations(db, MARKET, "same", [4240]) == {4240: {"min_buyout": 400, "market_value": 450}}
        assert price_observations(db, {**MARKET, "realm": "wrong"}, "same", [4240]) == {}


def test_future_snapshot_is_non_actionable_and_ties_are_stable():
    metadata = snapshot(collected_at=(NOW + timedelta(hours=1)).isoformat())
    assert {r["action"] for r in rank_recipes(catalog(), observed(prices()), MARKET, metadata, now=NOW)["rows"]} == {"stale data"}
    c = catalog()
    for recipe in c["recipes_by_id"].values():
        if c["items_by_id"][recipe["output_item_id"]]["role"] == "finished":
            recipe["inputs"] = [{"item_id": 2321, "quantity": 1}]
    p = {4240: 100, 10050: 100, 14046: 100}
    result = rank_recipes(c, observed(p), MARKET, snapshot(), now=NOW, auction_cut=0)
    assert [r["recipe_id"] for r in result["rows"]] == [3757, 12065, 18405]
    assert {r["action"] for r in result["rows"]} == {"negative margin"}


def test_unsupported_recipe_is_isolated_and_sorts_last():
    c = catalog()
    c["recipe_for_output"][14047] = 18405  # Runecloth Bag now cycles through its own cloth.
    p = prices()
    p[10050] = 0
    rows = rank_recipes(c, observed(p), MARKET, snapshot(), now=NOW)["rows"]
    assert [r["recipe_id"] for r in rows] == [3757, 12065, 18405]
    assert [r["action"] for r in rows] == ["potential craft", "missing prices", "unsupported recipe"]
    assert "cycle" in rows[-1]["error"]
    assert rows[-1]["profit_copper"] is None


def test_copper_math_does_not_lose_a_copper_to_float_rounding():
    result = evaluate_recipe(catalog(), 3757, {**prices(), 4240: 100}, auction_cut=.07)
    assert result["net_revenue_copper"] == 93
    assert sum(c["total_cost_copper"] for c in result["shopping_choices"]) == result["craft_cost_copper"]


def test_cautious_basis_buys_high_sells_low_and_ranks_on_it():
    # One cheap Runecloth listing makes Runecloth Bag look best; typical prices do not.
    p = {**prices(), 14047: 100, 14046: 20000}
    data = observed(p, {14047: 1000})
    buy, sell = basis_prices(data, "cautious")
    assert buy[14047] == 1000 and sell[14047] == 100
    listed = rank_recipes(catalog(), data, MARKET, snapshot(), now=NOW, basis="listed")["rows"]
    cautious = rank_recipes(catalog(), data, MARKET, snapshot(), now=NOW)["rows"]
    assert listed[0]["recipe_id"] == 18405
    assert cautious[0]["recipe_id"] != 18405
    bag = next(r for r in cautious if r["recipe_id"] == 18405)
    assert bag["profit_by_basis"]["cautious"] < bag["profit_by_basis"]["listed"]
    assert bag["profit_copper"] == bag["profit_by_basis"]["cautious"]


def test_cautious_basis_falls_back_to_the_only_positive_value_and_never_zero():
    data = {1: {"min_buyout": 0, "market_value": 700}, 2: {"min_buyout": 300, "market_value": 0},
            3: {"min_buyout": 0, "market_value": 0}}
    assert basis_prices(data, "cautious") == ({1: 700, 2: 300}, {1: 700, 2: 300})
    assert basis_prices(data, "listed") == ({2: 300}, {2: 300})
    with pytest.raises(ValueError):
        basis_prices(data, "optimistic")


def test_board_follows_configuration_not_a_hard_coded_realm():
    other = {**MARKET, "market_id": "classic-us-other-horde", "realm": "other-horde"}
    assert rank_recipes(catalog(), observed(prices()), other, snapshot(**other), now=NOW)["rows"]
    forever = load_recipe_catalog(ROOT / "config/forever-tailoring.toml")
    assert not compatible(forever, MARKET)
    assert compatible(forever, {**MARKET, "game_version": "forever", "ruleset": forever["ruleset"]})
    assert not compatible(catalog(), {k: v for k, v in MARKET.items() if k != "ruleset"})
