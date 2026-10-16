"""Character craft eligibility from the shared, scoped profession projection."""
from collections import Counter

from .professions import _first, _order
from .recipe_graph import identity
from .scans import _list

# Evidence: requirements.md → Character eligibility → Profession skill-line IDs.
PROFESSION_SKILL_IDS = {
    "alchemy": 171, "blacksmithing": 164, "cooking": 185, "enchanting": 333,
    "engineering": 202, "first-aid": 129, "leatherworking": 165, "mining": 186, "tailoring": 197,
}
NO_CHARACTER_EVIDENCE = "No character evidence exists for this source; showing every catalog recipe."


def _complete_skills(api: dict, modern: bool) -> bool:
    if api.get("possibly_incomplete"):
        return False
    rows = _list(api.get("rows"), "skill rows")
    if modern:
        if not _complete_indexes(api, rows):
            return False
    else:
        count = _first(api.get("counts"))
        if type(count) is not int or count < 0 or len(rows) != count:
            return False
    return all(r.get("is_header") in (True, 1) or
               (type(r.get("skill_id")) is int and r["skill_id"] > 0) for r in rows)


def _complete_indexes(api: dict, rows: list) -> bool:
    indexes = api.get("indexes") or {}
    if not isinstance(indexes, dict) or type(indexes.get("n")) is not int or indexes["n"] < 0:
        return False
    values = [indexes.get(str(i), indexes.get(i)) for i in range(1, indexes["n"] + 1)]
    if any(v is not None and (type(v) is not int or v <= 0) for v in values):
        return False
    expected = [int(v) for v in values if v is not None]
    return sorted(r.get("index", -1) for r in rows) == sorted(expected)


def _lacks_profession(recipe: dict, state: dict) -> bool:
    skill_id = PROFESSION_SKILL_IDS.get(recipe.get("profession", ""))
    if skill_id is None:
        return False
    surfaces = state.get("bags", {}).get("skills") or {}
    complete = [api for name, api in surfaces.items() if _complete_skills(api, name == "modern")]
    return bool(complete) and all(row.get("skill_id") != skill_id for api in complete
                                  for row in _list(api.get("rows"), "skill rows"))


def available_characters(data: dict) -> list[tuple]:
    return sorted(data)


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


def profession_rank(state: dict, record: dict) -> tuple[int | None, int | None]:
    """Rank and cap from the list, or newer readable bags for the same skill ID."""
    surface = record["known_recipes"]
    bags = state.get("bags", {})
    result = surface.get("rank"), surface.get("max_rank")
    skill_id = _skill_id(surface)
    if skill_id is not None and _order(bags) > _order(record):
        for api in (bags.get("skills") or {}).values():
            for skill in _list(api.get("rows"), "skill rows"):
                if skill.get("skill_id") == skill_id and type(skill.get("rank")) is int:
                    result = skill["rank"], skill.get("max_rank")
    return result


def _rank(state: dict, record: dict) -> int | None:
    return profession_rank(state, record)[0]


def recipe_rank(state: dict, recipe_id: int) -> int | None:
    """Rank of the profession list that knows this recipe, or None when no list does."""
    record = _match(state, recipe_id)[0]
    return _rank(state, record) if record else None


def recipe_status(recipe: dict, state: dict, *, planned_rank: int | None = None) -> dict:
    """Resolve exact-ID status; planned_rank changes only the rank check for progression steps."""
    record, row = _match(state, recipe["recipe_id"])
    # A window list newer than the skills snapshot (profession learned since) outranks its absence.
    if _lacks_profession(recipe, state) and (not row or _order(state.get("bags", {})) > _order(record)):
        return {"craft_status": "Not yet", "character_reason": "no character has this profession",
                "training_cost_copper": None}
    if row.get("learned") is True or any(recipe["recipe_id"] in ids for ids in state.get("seen", {}).values()):
        return {"craft_status": "Known", "character_reason": "", "training_cost_copper": None}
    surface = record.get("known_recipes", {})
    reason = _unknown_reason(surface, row, recipe)
    if reason:
        return {"craft_status": "Unknown", "character_reason": reason, "training_cost_copper": None}
    rank = _rank(state, record) if planned_rank is None else planned_rank
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
    if recipe.get("required_skill") is None:  # Wowhead's no-skill sentinel is never a rank to compare (CRAFT-08).
        return "required skill unknown"
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


def _team_status(statuses: list[dict]) -> dict:
    if any(s["craft_status"] in ("Known", "Train now") for s in statuses):
        return {}
    unknown = any(s["craft_status"] == "Unknown" for s in statuses)
    reason = "unknown for every character" if unknown else next(
        reason for reason in ("rank below required skill", "needs pattern or other source",
                               "no character has this profession")
         if any(s["character_reason"] == reason for s in statuses))
    return {"craft_status": "Unknown" if unknown else "Not yet", "character_reason": reason,
            "training_cost_copper": None}


def project_recipes(catalogs: list, data: dict, character: tuple | None, include_unknown: bool = False) -> dict:
    """Catalog-scoped statuses and diagnostics, independent of prices or batch sizing."""
    selected = resolve_character(character, data)
    characters = available_characters(data)
    statuses, checks = {}, []
    for catalog in catalogs:
        for recipe in catalog["recipes_by_id"].values():
            key = (catalog["catalog_id"], recipe["recipe_id"])
            evidence = {c: recipe_status(recipe, data[c]) for c in characters}
            status = evidence[selected] if selected else (_team_status(list(evidence.values())) if evidence else {})
            statuses[key] = status | {"who_can_make_it": [c[0] for c, s in evidence.items()
                                                        if s["craft_status"] in ("Known", "Train now")],
                                      "team": selected is None}
            for c in ([selected] if selected else characters):
                _, row = _match(data[c], recipe["recipe_id"])
                reasons = catalog_check(recipe, row) if row else []
                if reasons:
                    checks.append({"Character": c[0], "Catalog": catalog["catalog_id"],
                                   "Recipe": recipe["recipe_id"], "Check": "; ".join(reasons)})
    return {"character": selected, "statuses": statuses, "catalog_checks": checks,
            "include_unknown": include_unknown,
            "character_note": "" if characters else NO_CHARACTER_EVIDENCE}


def filter_candidates(rows: list, projection: dict) -> tuple[list, Counter]:
    kept = []
    hidden: Counter[str] = Counter()
    for row in rows:
        status = projection["statuses"].get((row["catalog_id"], row["recipe_id"]), {})
        if status.get("craft_status") == "Not yet" or (
                status.get("craft_status") == "Unknown" and not projection["include_unknown"]):
            hidden[status["character_reason"]] += 1
        else:
            kept.append(row | status)
    return kept, hidden


def team_makeable(catalogs, data):
    """Catalog-qualified makers from scoped data, Known before Train now, then by character."""
    if not data:
        return None
    return {(identity(c), r["recipe_id"]): _makers(r, data) for c in catalogs for r in c["recipes_by_id"].values()}


def _makers(recipe, data):
    statuses = [(recipe_status(recipe, state)["craft_status"], character) for character, state in data.items()]
    return [character[0] for status, character in sorted(statuses, key=lambda s: (s[0] != "Known", s[1]))
            if status in ("Known", "Train now")]
