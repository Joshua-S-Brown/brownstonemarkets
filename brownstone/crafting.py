"""Versioned recipe loading and conservative crafting-cost evaluation."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import tomllib


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
    for recipe in recipes.values():
        if recipe.get("profession") != raw["profession"]:
            raise ValueError("Recipe profession must match its catalog")
        if recipe.get("output_item_id") not in items or recipe.get("output_quantity", 0) <= 0:
            raise ValueError("Recipe output must reference an item with a positive quantity")
        if recipe["output_item_id"] in output_recipes:
            raise ValueError("This milestone supports one recipe per output item")
        if not str(recipe.get("source_url", "")).startswith("https://"):
            raise ValueError("Every recipe requires an HTTPS provenance URL")
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


def evaluate_recipe(catalog: dict, recipe_id: int, prices: dict[int, int], auction_cut: float = 0.05) -> dict:
    """Cost a recipe, choosing the cheaper valid buy or craft path for intermediates."""
    if not 0 <= auction_cut < 1:
        raise ValueError("auction_cut must be in [0, 1)")
    choices = []

    def unit_cost(item_id: int, trail: tuple[int, ...]) -> tuple[int | None, str]:
        item = catalog["items_by_id"][item_id]
        candidates = []
        market = prices.get(item_id)
        if isinstance(market, int) and market > 0:
            candidates.append((market, "buy"))
        vendor = item.get("vendor_price_copper")
        if isinstance(vendor, int) and vendor > 0:
            candidates.append((vendor, "vendor"))
        nested_id = catalog["recipe_for_output"].get(item_id)
        if nested_id is not None:
            if nested_id in trail:
                raise ValueError("Recipe cycle detected")
            nested = catalog["recipes_by_id"][nested_id]
            subtotal = 0
            for ingredient in nested["inputs"]:
                cost, _ = unit_cost(ingredient["item_id"], trail + (nested_id,))
                if cost is None:
                    break
                subtotal += cost * ingredient["quantity"]
            else:
                if subtotal % nested["output_quantity"]:
                    raise ValueError("Fractional unit costs are not supported")
                candidates.append((subtotal // nested["output_quantity"], "craft"))
        return min(candidates) if candidates else (None, "missing")

    recipe = catalog["recipes_by_id"].get(recipe_id)
    if recipe is None:
        raise ValueError(f"Unknown recipe {recipe_id}")
    total = 0
    missing = []
    for ingredient in recipe["inputs"]:
        cost, method = unit_cost(ingredient["item_id"], (recipe_id,))
        name = catalog["items_by_id"][ingredient["item_id"]]["name"]
        choices.append({"item_id": ingredient["item_id"], "item_name": name,
                        "quantity": ingredient["quantity"], "method": method,
                        "unit_cost_copper": cost})
        if cost is None:
            missing.append(ingredient["item_id"])
        else:
            total += cost * ingredient["quantity"]

    output_id = recipe["output_item_id"]
    sale = prices.get(output_id)
    valid_sale = isinstance(sale, int) and sale > 0
    valid = not missing and valid_sale
    net_revenue = int(sale * recipe["output_quantity"] * (1 - auction_cut)) if valid_sale else None
    profit = net_revenue - total if valid else None
    return {
        "recipe_id": recipe_id, "output_item_id": output_id,
        "output_name": catalog["items_by_id"][output_id]["name"],
        "ruleset": catalog["ruleset"], "status": catalog["status"],
        "valid": valid, "missing_item_ids": missing + ([] if valid_sale else [output_id]),
        "craft_cost_copper": total if not missing else None,
        "sale_price_copper": sale if valid_sale else None,
        "net_revenue_copper": net_revenue, "profit_copper": profit,
        "choices": choices,
    }
