"""Character craft eligibility from the shared, scoped profession projection."""
from collections import Counter

from .professions import _first, _order
from .scans import _list


def available_characters(data: dict) -> list[tuple]:
    return sorted(key for key, state in data.items() if state["recipes"] or any(state.get("seen", {}).values()))


def resolve_character(character: tuple | None, data: dict) -> tuple | None:
    return character if character in available_characters(data) else None


def _match(state: dict, recipe_id: int) -> tuple[dict, dict]:
    matches = [(record, row) for record in state["recipes"].values()
               for row in _list(record["known_recipes"].get("rows"), "recipe rows")
               if row.get("recipe_id") == recipe_id]
    return max(matches, key=lambda pair: _order(pair[0]), default=({}, {}))


def _skill_id(surface: dict) -> int | None:
    for api in ("GetBaseProfessionInfo", "GetChildProfessionInfo"):
        info = _first(surface.get("profession", {}).get(api, {}))
        if isinstance(info, dict) and type(info.get("professionID")) is int and info["professionID"] > 0:
            return info["professionID"]
    return surface.get("skill_id")


def _rank(state: dict, record: dict) -> int | None:
    surface = record["known_recipes"]
    rank = surface.get("rank")
    bags = state.get("bags", {})
    skill_id = _skill_id(surface)
    if skill_id is not None and _order(bags) > _order(record):
        for api in (bags.get("skills") or {}).values():
            for skill in _list(api.get("rows"), "skill rows"):
                if skill.get("skill_id") == skill_id and type(skill.get("rank")) is int:
                    rank = skill["rank"]
    return rank


def recipe_status(recipe: dict, state: dict) -> dict:
    """Positive observed knowledge wins; missing/incomplete evidence never excludes a craft."""
    record, row = _match(state, recipe["recipe_id"])
    if row.get("learned") is True or any(recipe["recipe_id"] in ids for ids in state.get("seen", {}).values()):
        return {"craft_status": "Known", "character_reason": "", "training_cost_copper": None}
    surface = record.get("known_recipes", {})
    reason = _unknown_reason(surface, row, recipe)
    if reason:
        return {"craft_status": "Unknown", "character_reason": reason, "training_cost_copper": None}
    rank = _rank(state, record)
    if rank is not None and rank < recipe["required_skill"]:
        return {"craft_status": "Not yet", "character_reason": "rank below required skill",
                "training_cost_copper": None}
    if 6 not in recipe["learned_from"]:
        return {"craft_status": "Not yet", "character_reason": "needs pattern or other source",
                "training_cost_copper": None}
    if rank is None:
        return {"craft_status": "Unknown", "character_reason": "rank unknown", "training_cost_copper": None}
    return {"craft_status": "Train now", "character_reason": "",
            "training_cost_copper": recipe.get("training_cost_copper")}


def _unknown_reason(surface: dict, row: dict, recipe: dict) -> str:
    if not row:
        return "recipe not listed"
    if surface.get("possibly_incomplete"):
        return "possibly incomplete list"
    if row.get("learned") is not False:
        return "learned flag unknown"
    if not recipe.get("learned_from"):
        return "how it's learned is unknown"
    return ""


def catalog_check(recipe: dict, row: dict) -> list[str]:
    """Compare explicit fixed outputs/required reagents; preserve complex slots as not compared."""
    reagents: list | None
    slots = row.get("schematic", {}).get("reagentSlotSchematics")
    if slots is not None:
        slots = _list(slots, "reagent slots")
        if any(slot.get("required") is not True or len(_list(slot.get("reagents"), "options")) != 1
               or slot.get("variableQuantities") for slot in slots):
            return ["not compared: optional, multi-choice or variable reagent slots"]
        reagents = [{"item_id": _list(s.get("reagents"), "options")[0].get("itemID"),
                     "count": s.get("quantityRequired")} for s in slots]
    else:
        reagents = _list(row.get("reagents"), "reagents") if "reagents" in row else None
    reasons = []
    if row.get("item_id") is not None and row["item_id"] != recipe["output_item_id"]:
        reasons.append("output item differs")
    if any(row.get(k) is not None and row[k] != recipe["output_quantity"] for k in ("min_made", "max_made")):
        reasons.append("yield differs")
    if reagents is not None:
        actual: Counter = Counter()
        for reagent in reagents:
            if reagent.get("item_id") is None or reagent.get("count") is None:
                return [*reasons, "not compared: required reagents unreadable"]
            actual[reagent["item_id"]] += reagent["count"]
        expected: Counter = Counter()
        for reagent in recipe["inputs"]:
            expected[reagent["item_id"]] += reagent["quantity"]
        if actual != expected:
            reasons.append("required reagents differ")
    return reasons


def project_recipes(catalogs: list, data: dict, character: tuple | None) -> dict:
    """Catalog-scoped statuses and diagnostics, independent of prices or batch sizing."""
    selected = resolve_character(character, data)
    characters = available_characters(data)
    statuses, checks = {}, []
    for catalog in catalogs:
        for recipe in catalog["recipes_by_id"].values():
            key = (catalog["catalog_id"], recipe["recipe_id"])
            statuses[key] = (recipe_status(recipe, data[selected]) if selected else {}) | {
                "who_can_make_it": [c[0] for c in characters
                                    if recipe_status(recipe, data[c])["craft_status"] in ("Known", "Train now")]}
            for c in ([selected] if selected else characters):
                _, row = _match(data[c], recipe["recipe_id"])
                reasons = catalog_check(recipe, row) if row else []
                if reasons:
                    checks.append({"Character": c[0], "Catalog": catalog["catalog_id"],
                                   "Recipe": recipe["recipe_id"], "Check": "; ".join(reasons)})
    return {"character": selected, "statuses": statuses, "catalog_checks": checks}


def filter_candidates(rows: list, projection: dict) -> tuple[list, Counter]:
    kept = []
    hidden: Counter[str] = Counter()
    for row in rows:
        status = projection["statuses"].get((row["catalog_id"], row["recipe_id"]), {})
        if status.get("craft_status") == "Not yet":
            hidden[status["character_reason"]] += 1
        else:
            kept.append(row | status)
    return kept, hidden
