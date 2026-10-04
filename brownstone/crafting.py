"""Versioned recipe loading and conservative crafting-cost evaluation."""
from __future__ import annotations

import tomllib
from collections import defaultdict
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from pathlib import Path


def load_recipe_catalog(path: Path) -> dict:
    with path.open("rb") as file:
        raw = tomllib.load(file)
    if raw.get("schema_version") != 1:
        raise ValueError("Unsupported recipe catalog schema")
    for key in ("game_version", "ruleset", "profession", "status"):
        if not raw.get(key):
            raise ValueError(f"Recipe catalog requires {key}")

    items = {item["item_id"]: item for item in raw.get("items", [])}
    recipes = {recipe["recipe_id"]: recipe for recipe in raw.get("recipes", [])}
    if len(items) != len(raw.get("items", [])) or len(recipes) != len(raw.get("recipes", [])):
        raise ValueError("Item and recipe IDs must be unique")
    if not items or not recipes:
        raise ValueError("Recipe catalog must contain items and recipes")

    output_recipes = {}
    for item in items.values():
        if item.get("role") not in {"material", "vendor_material", "intermediate", "finished"}:
            raise ValueError("Unsupported item role")
        if not str(item.get("source_url", "")).startswith("https://"):
            raise ValueError("Every item requires an HTTPS provenance URL")
        if item.get("vendor_price_copper", 1) <= 0:
            raise ValueError("Vendor prices must be positive copper integers")
        if not str(item.get("vendor_price_source_url", "https://")).startswith("https://"):
            raise ValueError("Vendor price provenance must be an HTTPS URL")
    for recipe in recipes.values():
        if recipe.get("profession") != raw["profession"]:
            raise ValueError("Recipe profession must match its catalog")
        if recipe.get("output_item_id") not in items or recipe.get("output_quantity", 0) <= 0:
            raise ValueError("Recipe output must reference an item with a positive quantity")
        if recipe["output_item_id"] in output_recipes:
            raise ValueError("This milestone supports one recipe per output item")
        if not str(recipe.get("source_url", "")).startswith("https://"):
            raise ValueError("Every recipe requires an HTTPS provenance URL")
        if not str(recipe.get("verification_url", "https://")).startswith("https://"):
            raise ValueError("Recipe verification must be an HTTPS URL")
        for ingredient in recipe.get("inputs", []):
            if ingredient.get("item_id") not in items or ingredient.get("quantity", 0) <= 0:
                raise ValueError("Recipe inputs must reference items with positive quantities")
        output_recipes[recipe["output_item_id"]] = recipe["recipe_id"]

    return {**raw, "items_by_id": items, "recipes_by_id": recipes,
            "recipe_for_output": output_recipes}


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


def evaluate_recipe(catalog: dict, recipe_id: int, prices: dict[int, int], auction_cut: float = 0.05,
                    sale_prices: dict[int, int] | None = None) -> dict:
    """Cost a recipe, choosing the cheaper valid buy or craft path for intermediates.

    ``prices`` are unit purchase prices; ``sale_prices`` (default: ``prices``) price the output.
    """
    if not 0 <= auction_cut < 1:
        raise ValueError("auction_cut must be in [0, 1)")
    choices = []
    shopping: defaultdict[int, int] = defaultdict(int)

    def unit_cost(item_id: int, trail: tuple[int, ...]) -> tuple[int | None, str, dict[int, int]]:
        item = catalog["items_by_id"][item_id]
        candidates = []
        if _positive(prices.get(item_id)):
            candidates.append((prices[item_id], "buy", {item_id: 1}))
        if _positive(item.get("vendor_price_copper")):
            candidates.append((item["vendor_price_copper"], "vendor", {item_id: 1}))
        nested_id = catalog["recipe_for_output"].get(item_id)
        if nested_id is not None:
            if nested_id in trail:
                raise ValueError("Recipe cycle detected")
            nested = catalog["recipes_by_id"][nested_id]
            subtotal = 0
            leaves: defaultdict[int, int] = defaultdict(int)
            for ingredient in nested["inputs"]:
                cost, _, nested_leaves = unit_cost(ingredient["item_id"], trail + (nested_id,))
                if cost is None:
                    break
                subtotal += cost * ingredient["quantity"]
                for leaf_id, quantity in nested_leaves.items():
                    leaves[leaf_id] += quantity * ingredient["quantity"]
            else:
                if subtotal % nested["output_quantity"]:
                    raise ValueError("Fractional unit costs are not supported")
                if any(q % nested["output_quantity"] for q in leaves.values()):
                    raise ValueError("Fractional shopping quantities are not supported")
                candidates.append((subtotal // nested["output_quantity"], "craft",
                                   {i: q // nested["output_quantity"] for i, q in leaves.items()}))
        if not candidates:
            return None, "missing", {item_id: 1}
        return min(candidates, key=lambda candidate: candidate[:2])  # Cost, then method name.

    recipe = catalog["recipes_by_id"].get(recipe_id)
    if recipe is None:
        raise ValueError(f"Unknown recipe {recipe_id}")
    total = 0
    missing = []
    for ingredient in recipe["inputs"]:
        cost, method, leaves = unit_cost(ingredient["item_id"], (recipe_id,))
        name = catalog["items_by_id"][ingredient["item_id"]]["name"]
        choices.append({"item_id": ingredient["item_id"], "item_name": name,
                        "quantity": ingredient["quantity"], "method": method,
                        "unit_cost_copper": cost,
                        "total_cost_copper": cost * ingredient["quantity"] if cost is not None else None})
        for leaf_id, quantity in leaves.items():
            shopping[leaf_id] += quantity * ingredient["quantity"]
        if cost is None:
            missing.append(ingredient["item_id"])
        else:
            total += cost * ingredient["quantity"]

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
    shopping_choices = []
    for item_id, quantity in sorted(shopping.items()):
        cost, method, _ = unit_cost(item_id, (recipe_id,))
        shopping_choices.append({
            "item_id": item_id, "quantity": quantity, "method": method,
            "unit_cost_copper": cost,
            "total_cost_copper": cost * quantity if cost is not None else None,
        })
    return {
        "recipe_id": recipe_id, "output_item_id": output_id,
        "output_name": catalog["items_by_id"][output_id]["name"],
        "ruleset": catalog["ruleset"], "status": catalog["status"],
        "valid": valid, "missing_item_ids": missing + ([] if valid_sale else [output_id]),
        "craft_cost_copper": total if not missing else None,
        "sale_price_copper": sale if valid_sale else None,
        "net_revenue_copper": net_revenue, "profit_copper": profit,
        "choices": choices,
        "shopping_list": dict(sorted(shopping.items())),
        "shopping_choices": shopping_choices,
        "expanded_materials": material_plan(catalog, recipe_id),
        "margin": profit / net_revenue if profit is not None and net_revenue else None,
        "break_even_copper": break_even,
    }
