"""Versioned recipe loading and conservative crafting-cost evaluation."""
from __future__ import annotations

import tomllib
from collections import defaultdict
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from pathlib import Path

ROLES = {"material", "vendor_material", "intermediate", "finished"}


def load_recipe_catalog(path: Path) -> dict:
    with path.open("rb") as file:
        return parse_recipe_catalog(tomllib.load(file))


def parse_recipe_catalog(raw: dict) -> dict:
    """Validate a catalog's TOML data and index it by item, recipe and output."""
    if raw.get("schema_version") != 1:
        raise ValueError("Unsupported recipe catalog schema")
    for key in ("game_version", "rules_version", "profession", "status", "catalog_version"):
        if not raw.get(key):
            raise ValueError(f"Recipe catalog requires {key}")

    items = {item["item_id"]: item for item in raw.get("items", [])}
    recipes = {recipe["recipe_id"]: recipe for recipe in raw.get("recipes", [])}
    if len(items) != len(raw.get("items", [])) or len(recipes) != len(raw.get("recipes", [])):
        raise ValueError("Item and recipe IDs must be unique")
    if not items or not recipes:
        raise ValueError("Recipe catalog must contain items and recipes")

    for item in items.values():
        _check_item(item)
    output_recipes: dict[int, int] = {}
    for recipe in recipes.values():
        _check_recipe(recipe, raw["profession"], items, output_recipes)
        output_recipes[recipe["output_item_id"]] = recipe["recipe_id"]

    return {**raw, "items_by_id": items, "recipes_by_id": recipes,
            "recipe_for_output": output_recipes}


def _https(value: object) -> bool:
    return str(value).startswith("https://")


def _check_item(item: dict) -> None:
    if item.get("role") not in ROLES:
        raise ValueError("Unsupported item role")
    if not _https(item.get("source_url", "")):
        raise ValueError("Every item requires an HTTPS provenance URL")
    if "vendor_price_copper" in item and not _positive(item["vendor_price_copper"]):
        raise ValueError("Vendor prices must be positive copper integers")
    if not _https(item.get("vendor_price_source_url", "https://")):
        raise ValueError("Vendor price provenance must be an HTTPS URL")
    _check_flags(item)


def _check_recipe(recipe: dict, profession: str, items: dict, output_recipes: dict) -> None:
    """Validate one recipe; ``output_recipes`` holds the outputs of the recipes checked before it."""
    if recipe.get("profession") != profession:
        raise ValueError("Recipe profession must match its catalog")
    if recipe.get("output_item_id") not in items or not _positive(recipe.get("output_quantity")):
        raise ValueError("Recipe output must reference an item with a positive quantity")
    if recipe["output_item_id"] in output_recipes:
        raise ValueError("This milestone supports one recipe per output item")
    if not _https(recipe.get("source_url", "")):
        raise ValueError("Every recipe requires an HTTPS provenance URL")
    if not _https(recipe.get("verification_url", "https://")):
        raise ValueError("Recipe verification must be an HTTPS URL")
    _check_flags(recipe)
    for ingredient in recipe.get("inputs", []):
        if ingredient.get("item_id") not in items or not _positive(ingredient.get("quantity")):
            raise ValueError("Recipe inputs must reference items with positive quantities")


AVAILABILITY = {"available", "post-launch"}


def _check_flags(record: dict) -> None:
    """Display-only evidence flags: availability and the *_verified markers on unconfirmed values."""
    if record.get("availability", "available") not in AVAILABILITY:
        raise ValueError(f"availability must be one of {sorted(AVAILABILITY)}")
    for key, value in record.items():
        if key.endswith("_verified") and not isinstance(value, bool):
            raise ValueError(f"{key} must be true or false")


def material_plan(catalog: dict, recipe_id: int) -> dict[int, int]:
    """Expand intermediates into base quantities; fail on recipe cycles."""
    totals: defaultdict[int, int] = defaultdict(int)

    def expand_item(item_id: int, quantity: int, trail: tuple[int, ...]) -> None:
        nested_id = catalog["recipe_for_output"].get(item_id)
        if nested_id is None:
            totals[item_id] += quantity
            return
        if nested_id in trail:
            raise ValueError("Recipe cycle detected")
        nested = catalog["recipes_by_id"][nested_id]
        output_quantity = nested["output_quantity"]
        if quantity % output_quantity:
            raise ValueError("Fractional craft counts are not supported")
        crafts = quantity // output_quantity
        for ingredient in nested["inputs"]:
            expand_item(ingredient["item_id"], ingredient["quantity"] * crafts, trail + (nested_id,))

    recipe = catalog["recipes_by_id"].get(recipe_id)
    if recipe is None:
        raise ValueError(f"Unknown recipe {recipe_id}")
    for ingredient in recipe["inputs"]:
        expand_item(ingredient["item_id"], ingredient["quantity"], (recipe_id,))
    return dict(sorted(totals.items()))


PRICE_BASES = {
    "cautious": "Buy inputs at the higher, sell output at the lower, of minimum buyout and market value",
    "listed": "Buy and sell at the current minimum buyout",
}


def basis_prices(observations: dict[int, dict], basis: str) -> tuple[dict[int, int], dict[int, int]]:
    """Return (buy, sell) unit copper prices for a price basis.

    Observations map item ID to {"min_buyout", "market_value"}; zero means unavailable.
    One cheap listing rarely covers a whole shopping list, so the cautious basis prices
    purchases at the higher available value and sales at the lower. When only one value
    is positive it is used for both; when neither is, the item stays missing.
    """
    if basis not in PRICE_BASES:
        raise ValueError(f"Unknown price basis {basis}")
    buy: dict[int, int] = {}
    sell: dict[int, int] = {}
    for item_id, observed in observations.items():
        keys = ["min_buyout"] if basis == "listed" else ["min_buyout", "market_value"]
        values: list[int] = [observed[key] for key in keys if _positive(observed.get(key))]
        if values:
            buy[item_id], sell[item_id] = max(values), min(values)
    return buy, sell


def _positive(value) -> bool:
    """A usable copper price: a positive int. Zero, None and bools mean unavailable."""
    return type(value) is int and value > 0


def _to_copper(amount: Decimal, rounding: str) -> int:
    return int(amount.to_integral_value(rounding=rounding))


Route = tuple[int | None, str, dict[int, int]]  # Unit cost (None: no usable route), method, leaves per unit.


def _cheapest_route(catalog: dict, prices: dict[int, int], item_id: int, trail: tuple[int, ...]) -> Route:
    """The cheapest valid buy, vendor or craft route for one unit; equal costs resolve by method name."""
    item = catalog["items_by_id"][item_id]
    candidates: list[tuple[int, str, dict[int, int]]] = []
    if _positive(prices.get(item_id)):
        candidates.append((prices[item_id], "buy", {item_id: 1}))
    if _positive(item.get("vendor_price_copper")):
        candidates.append((item["vendor_price_copper"], "vendor", {item_id: 1}))
    nested_id = catalog["recipe_for_output"].get(item_id)
    if nested_id is not None:
        craft = _craft_route(catalog, prices, nested_id, trail)
        if craft is not None:
            candidates.append(craft)
    if not candidates:
        return None, "missing", {item_id: 1}
    return min(candidates, key=lambda candidate: candidate[:2])  # Cost, then method name.


def _craft_route(catalog: dict, prices: dict[int, int], recipe_id: int,
                 trail: tuple[int, ...]) -> tuple[int, str, dict[int, int]] | None:
    """Unit cost of crafting through ``recipe_id``; None when any input has no usable route."""
    if recipe_id in trail:
        raise ValueError("Recipe cycle detected")
    recipe = catalog["recipes_by_id"][recipe_id]
    subtotal = 0
    leaves: defaultdict[int, int] = defaultdict(int)
    for ingredient in recipe["inputs"]:
        cost, _, nested_leaves = _cheapest_route(catalog, prices, ingredient["item_id"], trail + (recipe_id,))
        if cost is None:
            return None
        subtotal += cost * ingredient["quantity"]
        for leaf_id, quantity in nested_leaves.items():
            leaves[leaf_id] += quantity * ingredient["quantity"]
    made = recipe["output_quantity"]
    if subtotal % made:
        raise ValueError("Fractional unit costs are not supported")
    if any(quantity % made for quantity in leaves.values()):
        raise ValueError("Fractional shopping quantities are not supported")
    return subtotal // made, "craft", {leaf_id: quantity // made for leaf_id, quantity in leaves.items()}


def _cost_row(item_id: int, quantity: int, route: Route) -> dict:
    cost, method, _ = route
    return {"item_id": item_id, "quantity": quantity, "method": method, "unit_cost_copper": cost,
            "total_cost_copper": cost * quantity if cost is not None else None}


def _intermediate_steps(catalog: dict, prices: dict[int, int], recipe_id: int,
                        quantity: int = 1, depth: int = 1, trail: tuple[int, ...] = ()) -> list[dict]:
    """Retain only craft branches chosen by the same catalog-local cost routing."""
    steps = []
    recipe = catalog["recipes_by_id"][recipe_id]
    for ingredient in recipe["inputs"]:
        item_id = ingredient["item_id"]
        route = _cheapest_route(catalog, prices, item_id, trail + (recipe_id,))
        if route[1] != "craft":
            continue
        nested_id = catalog["recipe_for_output"][item_id]
        units = ingredient["quantity"] * quantity
        made = catalog["recipes_by_id"][nested_id]["output_quantity"]
        if units % made:
            raise ValueError("Fractional craft counts are not supported")
        steps.append({"item_id": item_id, "item_name": catalog["items_by_id"][item_id]["name"],
                      "recipe_id": nested_id, "quantity": units, "crafts": units // made, "depth": depth})
        steps.extend(_intermediate_steps(catalog, prices, nested_id, units // made, depth + 1,
                                         trail + (recipe_id,)))
    return steps


def evaluate_recipe(catalog: dict, recipe_id: int, prices: dict[int, int], auction_cut: float = 0.05,
                    sale_prices: dict[int, int] | None = None) -> dict:
    """Cost a recipe, choosing the cheaper valid buy or craft path for intermediates.

    ``prices`` are unit purchase prices; ``sale_prices`` (default: ``prices``) price the output.
    """
    if not 0 <= auction_cut < 1:
        raise ValueError("auction_cut must be in [0, 1)")
    recipe = catalog["recipes_by_id"].get(recipe_id)
    if recipe is None:
        raise ValueError(f"Unknown recipe {recipe_id}")
    choices = []
    shopping: defaultdict[int, int] = defaultdict(int)
    for ingredient in recipe["inputs"]:
        route = _cheapest_route(catalog, prices, ingredient["item_id"], (recipe_id,))
        choices.append({**_cost_row(ingredient["item_id"], ingredient["quantity"], route),
                        "item_name": catalog["items_by_id"][ingredient["item_id"]]["name"]})
        for leaf_id, quantity in route[2].items():
            shopping[leaf_id] += quantity * ingredient["quantity"]
    missing = [choice["item_id"] for choice in choices if choice["unit_cost_copper"] is None]
    total = sum(choice["total_cost_copper"] for choice in choices if choice["unit_cost_copper"] is not None)

    output_id = recipe["output_item_id"]
    sale = (prices if sale_prices is None else sale_prices).get(output_id)
    valid_sale = _positive(sale)
    valid = not missing and valid_sale
    retained = Decimal(1) - Decimal(str(auction_cut))
    net_revenue = (_to_copper(Decimal(sale * recipe["output_quantity"]) * retained, ROUND_FLOOR)
                   if valid_sale else None)
    break_even = (_to_copper(Decimal(total) / (retained * recipe["output_quantity"]), ROUND_CEILING)
                  if not missing else None)
    profit = net_revenue - total if valid and net_revenue is not None else None
    shopping_choices = [_cost_row(item_id, quantity, _cheapest_route(catalog, prices, item_id, (recipe_id,)))
                        for item_id, quantity in sorted(shopping.items())]
    return {
        "recipe_id": recipe_id, "output_item_id": output_id,
        "output_name": catalog["items_by_id"][output_id]["name"],
        "rules_version": catalog["rules_version"], "status": catalog["status"],
        "valid": valid, "missing_item_ids": missing + ([] if valid_sale else [output_id]),
        "craft_cost_copper": total if not missing else None,
        "sale_price_copper": sale if valid_sale else None,
        "net_revenue_copper": net_revenue, "profit_copper": profit,
        "choices": choices,
        "intermediate_steps": _intermediate_steps(catalog, prices, recipe_id),
        "shopping_list": dict(sorted(shopping.items())),
        "shopping_choices": shopping_choices,
        "expanded_materials": material_plan(catalog, recipe_id),
        "margin": profit / net_revenue if profit is not None and net_revenue else None,
        "break_even_copper": break_even,
    }
