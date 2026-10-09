"""Scoped raw profession evidence for the addon import page; no catalog matching."""
import json
from pathlib import Path

import duckdb

from .config import MARKET_KEYS
from .recipe_catalogs import CONFIG_DIR, find_catalogs, profession_title
from .scans import _list, _utc


def latest_rows(config) -> list[dict]:
    path = Path(config["data_dir"]) / "brownstone.duckdb"
    if not path.exists():
        return []
    characters: dict[tuple, dict] = {}
    scope = " AND ".join(["source_id=?", *(f"{k}=?" for k in MARKET_KEYS)])
    params = [config["source_id"], *[config[k] for k in MARKET_KEYS]]
    with duckdb.connect(str(path), read_only=True) as db:
        tables = {r[0] for r in db.execute("SELECT table_name FROM information_schema.tables").fetchall()}
        for table in ("character_snapshots", "character_journal"):
            if table not in tables:
                continue
            keys = db.execute(f"SELECT DISTINCT character, character_realm, character_faction "
                              f"FROM {table} WHERE {scope}", params).fetchall()
            for key in keys:
                characters.setdefault(key, {"bags": {}, "recipes": {}})
            records = db.execute(f"SELECT character, character_realm, character_faction, record_json "
                                 f"FROM {table} WHERE {scope} AND {_LATEST[table]}", params).fetchall()
            for name, realm, faction, raw in records:
                state = characters.setdefault((name, realm, faction), {"bags": {}, "recipes": {}})
                _observe(state, json.loads(raw))
    catalog_ids = _catalog_recipe_ids(config)
    for state in characters.values():
        _project_crafts(state, catalog_ids)
    return [row for key, state in sorted(characters.items()) for row in _rows(key, state)]


_SEQUENCE = "TRY_CAST(json_extract_string(record_json, '$.sequence') AS BIGINT)"
# character_snapshots.unreadable_backpack in SQL: a bags read with a 0-slot backpack is not evidence.
_READABLE_BAGS = ("NOT coalesce(list_contains(list_transform(json_extract(record_json, '$.containers[*]'), "
                  "c -> json_extract_string(c, '$.container_id') = '0' AND json_extract_string(c, '$.size') = '0'), "
                  "true), false)")
# The newest bags snapshot and scoped craft evidence leave the database.
_LATEST = {
    "character_snapshots": f"kind='bags' AND {_READABLE_BAGS} QUALIFY row_number() OVER (PARTITION BY character, "
                           "character_realm, "
                           f"character_faction ORDER BY captured_at DESC, {_SEQUENCE} DESC NULLS LAST) = 1",
    "character_journal": "family='craft' ORDER BY captured_at, " + _SEQUENCE + " NULLS FIRST, entry_id",
}


def _order(record: dict) -> tuple:
    return record.get("captured_at", -1), record.get("sequence", -1)


def _observe(state: dict, record: dict) -> None:
    if record.get("kind") == "bags" and _order(record) > _order(state["bags"]):
        state["bags"] = record
    if _crafted_id(record) is not None:
        state.setdefault("crafts", []).append(record)
    recipes = record.get("known_recipes")
    if isinstance(recipes, dict) and isinstance(recipes.get("name"), str):
        previous = state["recipes"].get(recipes["name"], {})
        if _order(record) > _order(previous):
            state["recipes"][recipes["name"]] = record


def _crafted_id(record: dict) -> int | None:
    arguments = record.get("arguments") or {}
    event = record.get("event")
    value = None
    if event == "C_TradeSkillUI.CraftRecipe":
        value = _first(arguments)
    elif event == "UNIT_SPELLCAST_SUCCEEDED" and _first(arguments) == "player":
        value = arguments.get("3", arguments.get(3)) if isinstance(arguments, dict) else (
            arguments[2] if len(arguments) > 2 else None)
    return value if type(value) is int and value > 0 else None


def _catalog_recipe_ids(config) -> dict[int, set[str]]:
    result: dict[int, set[str]] = {}
    for entry in find_catalogs(CONFIG_DIR):
        catalog = entry["catalog"]
        if not catalog or any(catalog.get(k) != config.get(k) for k in ("game_version", "rules_version")):
            continue
        for recipe in catalog.get("recipes", []):
            result.setdefault(recipe["recipe_id"], set()).add(profession_title(catalog["profession"]))
    return result


def _project_crafts(state: dict, catalog_ids: dict[int, set[str]]) -> None:
    # Window IDs are direct client provenance. Catalogs supply profession metadata only; no price join.
    ids: dict[int, set[str]] = {}
    for name, record in state["recipes"].items():
        for row in _list(record["known_recipes"].get("rows"), "recipe rows"):
            for field in ("recipe_id", "spell_id"):
                if type(row.get(field)) is int:
                    ids.setdefault(row[field], set()).add(name)
    for catalog_id, catalog_names in catalog_ids.items():
        ids.setdefault(catalog_id, set(catalog_names))
    hook_ids = {_crafted_id(r) for r in state.get("crafts", []) if r.get("event") == "C_TradeSkillUI.CraftRecipe"}
    seen: dict[str, dict] = {}
    for record in state.get("crafts", []):
        recipe_id = _crafted_id(record)
        if recipe_id is None:
            continue
        if record.get("event") == "UNIT_SPELLCAST_SUCCEEDED" and recipe_id not in ids and recipe_id not in hook_ids:
            continue  # Opening a profession also casts a spell; an unidentified spell is not a recipe.
        names = ids.get(recipe_id, set())
        name = next(iter(names)) if len(names) == 1 else "Profession unknown"
        evidence = seen.setdefault(name, {})
        previous = evidence.get(recipe_id, {})
        if _order(record) > _order(previous):
            evidence[recipe_id] = record
    state["seen"] = seen


def _skills(bags: dict) -> dict:
    skills = {}
    surfaces = bags.get("skills") or {}
    for api_name in ("legacy", "modern"):
        api = surfaces.get(api_name, {})
        for skill in _list(api.get("rows"), "skill rows"):
            if skill.get("name") and not skill.get("is_header"):
                skills[skill["name"]] = skill | {"api": api.get("api")}
    return skills


def _first(values):
    if isinstance(values, list):
        return values[0] if values else None
    if isinstance(values, dict):
        return values.get("1", values.get(1))
    return None


def _recipe_count(state: dict) -> int | None:
    count = _first(state.get("counts"))
    rows = _list(state.get("rows"), "recipe rows")
    if type(count) is not int or len(rows) != count or any(r.get("type") is None for r in rows):
        return None
    if state.get("api") == "C_TradeSkillUI":
        return sum(r.get("learned") is True for r in rows)
    return sum(r["type"] != "header" for r in rows)


def _skills_status(bags: dict, skills: dict) -> str:
    if not _readable_skills(bags, skills):
        return "skills unknown"
    surfaces = (bags.get("skills") or {}).values()
    return "possibly incomplete" if any(api.get("possibly_incomplete") for api in surfaces) else "observed"


def _readable_skills(bags: dict, skills: dict) -> bool:
    if skills:
        return True
    for api in (bags.get("skills") or {}).values():
        counts = api.get("counts") or {}
        indexes = api.get("indexes") or {}
        if type(_first(counts)) is int or (isinstance(indexes, dict) and type(indexes.get("n")) is int):
            return True
    return False


def _rows(key: tuple, state: dict) -> list[dict]:
    bags = state["bags"]
    skills = _skills(bags)
    names = sorted(set(skills) | set(state["recipes"]) | set(state.get("seen", {})))
    result = []
    for name in names or [None]:
        skill = skills.get(name, {})
        record = state["recipes"].get(name, {})
        recipes = record.get("known_recipes", {})
        seen = state.get("seen", {}).get(name, {})
        crafted: dict = max(seen.values(), key=_order, default={})
        latest = record or crafted
        moment = (_utc(latest["captured_at"], latest.get("captured_at_utc"), "captured_at").isoformat()
                  if latest else "known recipes unknown")
        result.append(dict(zip(("Character", "Realm", "Faction"), key, strict=True)) | {
            "Level": bags.get("level"), "Skills": _skills_status(bags, skills),
            "Profession / skill": name, "Skill API": skill.get("api"), "Skill ID": skill.get("skill_id"),
            "Rank": skill.get("rank"), "Max rank": skill.get("max_rank"),
            "Known recipes (UTC)": moment, "Listed recipes": _recipe_count(recipes),
            "Recipe source": " + ".join((["window list"] if record else []) + (["seen crafted"] if seen else []))
                or "unknown",
            "Seen crafted recipes": sorted(seen), "Known recipes": _known_count(recipes, seen),
            "Seen crafted (UTC)": _evidence_time(crafted),
            "Possibly incomplete": recipes.get("possibly_incomplete")})
    return result


def _evidence_time(record: dict) -> str | None:
    return (_utc(record["captured_at"], record.get("captured_at_utc"), "captured_at").isoformat()
            if record else None)


def _known_count(recipes: dict, seen: dict) -> int | None:
    count = _recipe_count(recipes)
    if count is None:
        return len(seen) if seen else None
    rows = _list(recipes.get("rows"), "recipe rows")
    known = [row for row in rows if row.get("type") != "header" and
             (recipes.get("api") != "C_TradeSkillUI" or row.get("learned") is True)]
    listed_ids = {row.get(field) for row in known for field in ("recipe_id", "spell_id")}
    return count + len(set(seen) - listed_ids)


def validate_skills(record: dict) -> None:
    """Validate optional display fields without interpreting raw client tuples."""
    _integers(record, ("level",))
    skills = record.get("skills")
    if skills is None:
        return
    if not isinstance(skills, dict):
        raise ValueError("Snapshot skills must be a table")
    for api in skills.values():
        if not isinstance(api, dict):
            raise ValueError("Skill API evidence must be a table")
        for skill in _list(api.get("rows"), "skill rows"):
            _integers(skill, ("rank", "max_rank", "skill_id"))
            _text(skill, ("name",))


def validate_recipes(record: dict) -> None:
    state = record.get("known_recipes")
    if state is None:
        return
    if not isinstance(state, dict):
        raise ValueError("Known recipes must be a table")
    _text(state, ("name", "api"))
    _integers(state, ("rank", "max_rank"))
    for row in _list(state.get("rows"), "recipe rows"):
        _text(row, ("name", "type", "recipe_link", "item_link"))
        if row.get("learned") is not None and type(row["learned"]) is not bool:
            raise ValueError("Recipe learned must be boolean or missing")
        _integers(row, ("index", "recipe_id", "spell_id", "item_id", "min_made", "max_made"))
        for reagent in _list(row.get("reagents"), "recipe reagents"):
            _text(reagent, ("item_link",))
            _integers(reagent, ("index", "item_id", "count"))


def _integers(row: dict, fields: tuple) -> None:
    if not isinstance(row, dict):
        raise ValueError("Profession evidence row must be a table")
    for field in fields:
        value = row.get(field)
        if value is not None and (type(value) is not int or not 0 <= value <= 2**63 - 1):
            raise ValueError(f"Profession {field} must be a nonnegative integer or missing")


def _text(row: dict, fields: tuple) -> None:
    if not isinstance(row, dict):
        raise ValueError("Profession evidence row must be a table")
    for field in fields:
        if row.get(field) is not None and not isinstance(row[field], str):
            raise ValueError(f"Profession {field} must be text or missing")
