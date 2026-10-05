"""Crafting shortlist policy; no storage, UI or network dependencies.

The board runs for any market whose game version and rules version match the catalog, so moving
from the Classic stand-in to WoW Forever is a configuration change, not a code change.
"""
from .config import MARKET_KEYS
from .crafting import PRICE_BASES, basis_prices, evaluate_recipe
from .freshness import assess

POLICY_VERSION = "0.2"


def compatible(catalog: dict, market: dict) -> bool:
    return (catalog["game_version"] == market.get("game_version")
            and catalog["rules_version"] == market.get("rules_version"))


def rank_recipes(catalog, observations, market, snapshot, *, now, sort_by="profit",
                 basis="cautious", max_age_hours=24, auction_cut=0.05):
    """Rank finished outputs; missing evidence sorts last, stale never signals action.

    Observations map item ID to unit copper {"min_buyout", "market_value"} from one scoped
    analytical snapshot. ``basis`` selects the ranked and labeled estimate; every row also
    carries profit under each basis. Margin is profit / net revenue; zero profit is
    conservatively non-actionable.
    """
    if not compatible(catalog, market):
        raise ValueError("The catalog's game version and rules version must match the market")
    if any(snapshot.get(key) != market.get(key) for key in MARKET_KEYS):
        raise ValueError("The snapshot belongs to a different market")
    if sort_by not in {"profit", "margin"}:
        raise ValueError("sort_by must be profit or margin")
    if basis not in PRICE_BASES:
        raise ValueError(f"Unknown price basis {basis}")
    freshness = assess(snapshot, now, max_age_hours)
    prices = {name: basis_prices(observations, name) for name in PRICE_BASES}
    rows = []
    for recipe in catalog["recipes_by_id"].values():
        output = catalog["items_by_id"][recipe["output_item_id"]]
        if output["role"] != "finished":
            continue
        try:
            results = {name: evaluate_recipe(catalog, recipe["recipe_id"], buy, auction_cut, sell)
                       for name, (buy, sell) in prices.items()}
        except ValueError as error:
            # One unsupported recipe (cycle, fractional units) must not hide the rest of the board.
            rows.append({"recipe_id": recipe["recipe_id"], "output_item_id": output["item_id"],
                         "output_name": output["name"], "valid": False, "error": str(error),
                         "action": "unsupported recipe", "craft_cost_copper": None,
                         "sale_price_copper": None, "net_revenue_copper": None,
                         "profit_copper": None, "margin": None,
                         "profit_by_basis": dict.fromkeys(PRICE_BASES)})
            continue
        result = results[basis]
        result["profit_by_basis"] = {name: r["profit_copper"] for name, r in results.items()}
        result["action"] = ("missing prices" if not result["valid"] else
                            "stale data" if freshness["stale"] else
                            "potential craft" if result["profit_copper"] > 0 else "negative margin")
        rows.append(result)
    return _ranked_board(rows, freshness, basis, sort_by)


def _ranked_board(rows, freshness, basis, sort_by):
    primary = "profit_copper" if sort_by == "profit" else "margin"
    secondary = "margin" if sort_by == "profit" else "profit_copper"
    rows.sort(key=lambda row: (not row["valid"], "error" in row, -(row[primary] or 0),
                               -(row[secondary] or 0), row["recipe_id"], row.get("catalog_id", "")))
    return {"rows": [{**row, "rank": rank} for rank, row in enumerate(rows, 1)],
            "freshness": freshness, "basis": basis, "policy_version": POLICY_VERSION}


def catalog_identity(catalog: dict) -> str:
    """Selection-file identity supplied by discovery; header identity for standalone catalogs."""
    return catalog.get("catalog_id", ":".join(catalog[key] for key in
                                              ("game_version", "rules_version", "profession", "catalog_version")))


def compatible_catalogs(catalogs: list[dict], market: dict) -> list[dict]:
    return [catalog for catalog in catalogs if compatible(catalog, market)]


def catalog_for_row(catalogs: list[dict], row: dict) -> dict:
    """Resolve details by catalog identity, never by a globally assumed recipe ID."""
    return next(catalog for catalog in catalogs if catalog_identity(catalog) == row["catalog_id"])


def filter_profession(board: dict, profession: str | None) -> dict:
    """Filter without changing the combined ranking or policy."""
    return {**board, "rows": [row for row in board["rows"]
                             if profession is None or row["profession"] == profession]}


def rank_catalogs(catalogs, observations, market, snapshot, *, now, sort_by="profit",
                  basis="cautious", max_age_hours=24, auction_cut=0.05):
    """One board, with independent recipe graphs and a catalog-qualified row identity."""
    selected = compatible_catalogs(catalogs, market)
    if not selected:
        raise ValueError("No compatible recipe catalogs")
    identities = [catalog_identity(catalog) for catalog in selected]
    if len(set(identities)) != len(identities):
        raise ValueError("Catalog identities must be unique")
    rows = []
    for catalog in selected:
        board = rank_recipes(catalog, observations, market, snapshot, now=now, sort_by=sort_by,
                             basis=basis, max_age_hours=max_age_hours, auction_cut=auction_cut)
        rows.extend({**row, "catalog_id": catalog_identity(catalog), "profession": catalog["profession"]}
                    for row in board["rows"])
    return _ranked_board(rows, board["freshness"], basis, sort_by)
