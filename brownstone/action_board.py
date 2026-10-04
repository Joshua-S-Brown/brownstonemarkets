"""Classic Tailoring shortlist policy; no storage, UI or network dependencies."""
from datetime import datetime

from .crafting import evaluate_recipe

MARKET = {
    "market_id": "classic-us-mankrik-alliance", "game_version": "classic",
    "region": "us", "scope": "realm", "realm": "mankrik-alliance",
}
POLICY_VERSION = "0.1"


def rank_recipes(catalog, prices, market, snapshot, *, now, sort_by="profit", max_age_hours=24,
                 auction_cut=0.05):
    """Rank finished outputs; missing evidence sorts last, stale never signals action.

    Prices are positive unit minimum buyouts from one scoped analytical snapshot.
    Margin is profit / net revenue. Zero profit is conservatively non-actionable.
    """
    if any(market.get(key) != value or snapshot.get(key) != value
           for key, value in MARKET.items()):
        raise ValueError("Action Board requires a Mankrik Alliance Classic Era snapshot")
    if catalog["game_version"] != "classic" or catalog["ruleset"] != "classic-era":
        raise ValueError("Action Board requires the Classic Era catalog")
    if sort_by not in {"profit", "margin"}:
        raise ValueError("sort_by must be profit or margin")
    if max_age_hours <= 0:
        raise ValueError("max_age_hours must be positive")
    timestamp = snapshot.get("updated_at") or snapshot["collected_at"]
    age = (now - datetime.fromisoformat(timestamp)).total_seconds() / 3600
    stale = age > max_age_hours or age < -0.25
    rows = []
    for recipe in catalog["recipes_by_id"].values():
        if catalog["items_by_id"][recipe["output_item_id"]]["role"] != "finished":
            continue
        result = evaluate_recipe(catalog, recipe["recipe_id"], prices, auction_cut)
        result["action"] = ("missing prices" if not result["valid"] else
                            "stale data" if stale else
                            "potential craft" if result["profit_copper"] > 0 else "negative margin")
        rows.append(result)
    primary = "profit_copper" if sort_by == "profit" else "margin"
    secondary = "margin" if sort_by == "profit" else "profit_copper"
    rows.sort(key=lambda row: (not row["valid"], -(row[primary] or 0),
                               -(row[secondary] or 0), row["recipe_id"]))
    return {"rows": [{**row, "rank": rank} for rank, row in enumerate(rows, 1)],
            "age_hours": age, "stale": stale,
            "freshness_basis": "upstream scan" if snapshot.get("updated_at") else "collection",
            "policy_version": POLICY_VERSION}
