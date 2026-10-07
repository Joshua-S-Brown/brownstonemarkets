"""Scoped raw profession evidence for the addon import page; no catalog matching."""
import json
from pathlib import Path

import duckdb

from .config import MARKET_KEYS
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
    return [row for key, state in sorted(characters.items()) for row in _rows(key, state)]


_SEQUENCE = "TRY_CAST(json_extract_string(record_json, '$.sequence') AS BIGINT)"
_RECIPES = "json_extract_string(record_json, '$.known_recipes.name')"
# Only the newest bags snapshot per character and newest list per profession leave the database.
_LATEST = {
    "character_snapshots": "kind='bags' QUALIFY row_number() OVER (PARTITION BY character, character_realm, "
                           f"character_faction ORDER BY captured_at DESC, {_SEQUENCE} DESC NULLS LAST) = 1",
    "character_journal": f"family='craft' AND {_RECIPES} IS NOT NULL QUALIFY row_number() OVER (PARTITION BY "
                         f"character, character_realm, character_faction, {_RECIPES} "
                         f"ORDER BY captured_at DESC, {_SEQUENCE} DESC NULLS LAST) = 1",
}


def _order(record: dict) -> tuple:
    return record.get("captured_at", -1), record.get("sequence", -1)


def _observe(state: dict, record: dict) -> None:
    if record.get("kind") == "bags" and _order(record) > _order(state["bags"]):
        state["bags"] = record
    recipes = record.get("known_recipes")
    if isinstance(recipes, dict) and isinstance(recipes.get("name"), str):
        previous = state["recipes"].get(recipes["name"], {})
        if _order(record) > _order(previous):
            state["recipes"][recipes["name"]] = record


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
    names = sorted(set(skills) | set(state["recipes"]))
    result = []
    for name in names or [None]:
        skill = skills.get(name, {})
        record = state["recipes"].get(name, {})
        recipes = record.get("known_recipes", {})
        moment = (_utc(record["captured_at"], record.get("captured_at_utc"), "captured_at").isoformat()
                  if record else "known recipes unknown")
        result.append(dict(zip(("Character", "Realm", "Faction"), key, strict=True)) | {
            "Level": bags.get("level"), "Skills": _skills_status(bags, skills),
            "Profession / skill": name, "Skill API": skill.get("api"), "Skill ID": skill.get("skill_id"),
            "Rank": skill.get("rank"), "Max rank": skill.get("max_rank"),
            "Known recipes (UTC)": moment, "Listed recipes": _recipe_count(recipes),
            "Possibly incomplete": recipes.get("possibly_incomplete")})
    return result


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
