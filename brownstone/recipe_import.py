"""Build recipe catalogs from a Wowhead profession list page saved in the user's browser.

Wowhead's terms allow personal use through a web browser but not automated downloads (recorded in
requirements.md), so this module never touches the network. One saved page, for example
``https://www.wowhead.com/forever/spells/professions/tailoring`` (Cooking and First Aid are under
``.../spells/secondary-skills/``), carries every recipe of a profession
(reagents, quantities, created item and count, skill learned at) and every item it mentions (name,
sell price, and vendor buy price for vendor-sold items).

Flow: ``archive_page`` keeps the exact bytes with provenance, ``extract_page`` parses them,
``build_catalog`` applies a tracked selection file, and ``dumps_catalog`` writes the catalog TOML.
"""
from __future__ import annotations

import hashlib
import json
import re
import tomllib
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from .crafting import (
    AVAILABILITY,
    parse_recipe_catalog,
    valid_learned_from,
    valid_skillup_colors,
    valid_training_cost,
)

GAME_PATHS = {"classic": "classic", "forever": "forever"}  # Catalog game_version -> Wowhead path segment.
# Wowhead lists Cooking and First Aid as secondary skills; every other crafting profession under professions.
SECONDARY_SKILLS = frozenset({"cooking", "first-aid"})
_CANONICAL = re.compile(r'<link rel="canonical" href="(https://www\.wowhead\.com/([a-z-]+)/spells/'
                        r'(?:professions|secondary-skills)/([a-z-]+))">')
_NOT_A_LIST = ("Not a Wowhead profession spell list page (no canonical .../spells/professions/... or "
               ".../spells/secondary-skills/... link)")


def spell_list_url(game_path: str, profession: str) -> str:
    """The Wowhead page listing a profession's spells, under the section Wowhead files it in."""
    section = "secondary-skills" if profession in SECONDARY_SKILLS else "professions"
    return f"https://www.wowhead.com/{game_path}/spells/{section}/{profession}"
_UNQUOTED_KEY = re.compile(r'([{,])([A-Za-z_]\w*):')
_PATCH = re.compile(r'latest patch \((\d+(?:\.\d+)+)\)')
_BUILD_FILTER = '"name":"Added in build"'


def _balanced(text: str, start: int, opening: str, closing: str) -> str:
    """The bracketed literal beginning at ``start``; strings are skipped so brackets inside names are safe."""
    depth, in_string, escaped = 0, False, False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise ValueError("Unterminated data literal in the saved page")


def _literal(text: str, marker: str, opening: str, closing: str) -> Any:
    position = text.find(marker)
    if position < 0:
        raise ValueError(f"The saved page has no {marker!r}; save the profession's spell list page")
    start = text.find(opening, position + len(marker))
    raw = _balanced(text, start, opening, closing)
    # Wowhead leaves a few keys unquoted (quality:1); everything else is JSON.
    return json.loads(_UNQUOTED_KEY.sub(r'\1"\2":', raw))


def extract_page(html: str, sha256: str, saved_at: str) -> dict:
    """Parse a saved profession list page into recipes and items keyed by ID (JSON-friendly)."""
    match = _CANONICAL.search(html)
    if not match:
        raise ValueError(_NOT_A_LIST)
    source_url, game_path, profession = match.groups()
    recipes = {}
    for row in _literal(html, "listviewspells =", "[", "]"):
        recipe = {"id": row["id"], "name": row["name"], "learnedat": row.get("learnedat"),
                  "creates": row.get("creates"), "reagents": row.get("reagents") or []}
        if valid_skillup_colors(row.get("colors")):
            recipe["skillup_colors"] = row["colors"]
        if valid_learned_from(row.get("source")):
            recipe["learned_from"] = row["source"]
        if valid_training_cost(row.get("trainingcost")):
            recipe["training_cost_copper"] = row["trainingcost"]
        if "envChange" in row:  # Forever pages flag new or changed spells relative to Classic.
            recipe["env_status"] = row["envChange"].get("status")
        if row.get("seasonId"):  # Classic pages include seasonal realms' spells (2 = Season of Discovery).
            recipe["season"] = row["seasonId"]
        recipes[str(row["id"])] = recipe
    items = {}
    for item_id, row in _literal(html, "WH.Gatherer.addData(3,", "{", "}").items():
        prices = row.get("jsonequip", {})
        items[item_id] = {"name": row["name_enus"], "sellprice": prices.get("sellprice"),
                          "buyprice": prices.get("buyprice")}
    if not recipes or not items:
        raise ValueError("The saved page holds no recipe or item data")
    return {"source_url": source_url,
            "game_path": game_path,
            "profession": profession, "sha256": sha256, "saved_at": saved_at,
            "recipes": recipes, "items": items}


def page_build(html: str) -> dict:
    """The game patch Wowhead says the page reflects, and the newest build it lists for that patch.

    Both come from the page itself: the description's "latest patch (1.60.1)" and the "Added in build"
    filter options, for example ``[70205,"70205 (1.60.1)"]``. Either is None when the page lacks it.
    """
    match = _PATCH.search(html)
    patch = match.group(1) if match else None
    end = html.find(_BUILD_FILTER)
    start = html.rfind('"options":', 0, end) if end >= 0 else -1
    builds = [(int(build), version) for build, version in
              re.findall(r'\[(\d+),"\d+ \((\d+(?:\.\d+)+)', html[start:end])] if start >= 0 else []
    matching = [build for build, version in builds if version == patch] if patch else []
    return {"patch": patch, "build": max(matching) if matching else None}


def archive_location(archive_dir: Path, game_path: str, profession: str, sha256: str) -> Path:
    """Where a page's archived copy lives; its manifest is the same path with ``.json``."""
    return archive_dir / "wowhead" / game_path / profession / f"{sha256[:16]}.html"


def _archive_paths(raw: bytes, archive_dir: Path) -> tuple[str, str, Path, Path]:
    """(SHA-256, decoded page, archived copy, manifest) for a saved page's bytes."""
    sha256 = hashlib.sha256(raw).hexdigest()
    html = raw.decode("utf-8", errors="replace")
    match = _CANONICAL.search(html)
    if not match:
        raise ValueError(_NOT_A_LIST)
    copy = archive_location(archive_dir, match.group(2), match.group(3), sha256)
    return sha256, html, copy, copy.with_suffix(".json")


def archived_saved_at(raw: bytes, archive_dir: Path) -> str | None:
    """The save date recorded when these exact bytes were archived before, if they were (reads only)."""
    manifest_path = _archive_paths(raw, archive_dir)[3]
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text(encoding="utf-8")).get("saved_at")


def archive_bytes(raw: bytes, original_name: str, archive_dir: Path, saved_at: str | None = None,
                  fallback_date: str | None = None) -> tuple[Path, dict]:
    """Keep the page's exact bytes once per SHA-256 with a provenance manifest; return (copy, manifest).

    ``saved_at`` (YYYY-MM-DD) is when the page was saved in the browser. It defaults to an earlier
    manifest for the same bytes, then to ``fallback_date``, so rebuilding from the archive reproduces
    the same catalog.
    """
    sha256, html, copy, manifest_path = _archive_paths(raw, archive_dir)
    previous = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    saved_at = saved_at or previous.get("saved_at") or fallback_date
    if not saved_at:
        raise ValueError("Give the date the page was saved (YYYY-MM-DD)")
    date.fromisoformat(saved_at)
    copy.parent.mkdir(parents=True, exist_ok=True)
    if not copy.exists():
        copy.write_bytes(raw)
    manifest = {"source_url": extract_page(html, sha256, saved_at)["source_url"], "sha256": sha256,
                "saved_at": saved_at, "original_name": original_name,
                "archived_at": previous.get("archived_at") or datetime.now(UTC).isoformat(timespec="seconds"),
                "bronze_file": copy.name, "capture": "saved by the user in a web browser"}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return copy, manifest


def archive_page(page: Path, archive_dir: Path, saved_at: str | None = None) -> tuple[Path, dict]:
    """``archive_bytes`` for a file on disk; the file's modification date is the last fallback for ``saved_at``."""
    modified = datetime.fromtimestamp(page.stat().st_mtime, UTC).date().isoformat()
    return archive_bytes(page.read_bytes(), page.name, archive_dir, saved_at, modified)


def prepare_catalog(raw: bytes, selection: dict, saved_at: str, current: str | None) -> dict:
    """Everything a write would produce, without writing: the catalog, its TOML and the changes from ``current``.

    The CLI and the app both generate through this, after archiving the same bytes.
    """
    sha256 = hashlib.sha256(raw).hexdigest()
    html = raw.decode("utf-8", errors="replace")
    extract = extract_page(html, sha256, saved_at)
    catalog = build_catalog(extract, selection)
    text = dumps_catalog(catalog)
    parsed = tomllib.loads(text)
    parse_recipe_catalog(parsed)  # Refuse anything the board could not load.
    changes = None if current is None else catalog_changes(tomllib.loads(current), parsed)
    return {"extract": extract, "catalog": catalog, "text": text, "changes": changes, "sha256": sha256,
            "saved_at": saved_at, **page_build(html)}


def load_selection(path: Path) -> dict:
    with path.open("rb") as file:
        return parse_selection(tomllib.load(file))


def parse_selection(selection: dict) -> dict:
    """Validate a selection file's TOML data."""
    for key in ("game_version", "rules_version", "profession", "status", "catalog_version"):
        if not selection.get(key):
            raise ValueError(f"Selection requires {key}")
    if selection["game_version"] not in GAME_PATHS:
        raise ValueError(f"No Wowhead path for game_version {selection['game_version']}")
    if not selection.get("recipes"):
        raise ValueError("Selection must list at least one recipe")
    return selection


def check_same_version(extract: dict, game: str, profession: str) -> None:
    """Refuse a page from another game version or profession (CRAFT-08)."""
    if extract["game_path"] != GAME_PATHS.get(game) or extract["profession"] != profession:
        raise ValueError(f"The page is {extract['game_path']} {extract['profession']}, but the catalog is "
                         f"{game} {profession}; catalogs never borrow another version's data")


def build_catalog(extract: dict, selection: dict) -> dict:
    """Catalog for the selected recipes plus every intermediate they need, in the loader's shape.

    A reagent made by exactly one usable recipe on the page is crafted (an intermediate). An item several
    recipes make is always bought, so a catalog never chooses between recipes, and recipes making such
    items can't be selected. Vendor materials are the items the selection marks ``vendor = true`` with
    evidence; their price is the page's buy price. Nothing is inferred from names, and values never come
    from another game version's page, or from a seasonal realm's spells on it.
    """
    check_same_version(extract, selection["game_version"], selection["profession"])
    recipes = {rid: recipe for rid, recipe in extract["recipes"].items() if not recipe.get("season")}
    picks = {str(pick["recipe_id"]): pick for pick in selection["recipes"]}
    seasonal = sorted(set(picks) & (set(extract["recipes"]) - set(recipes)), key=int)
    if seasonal:
        raise ValueError(f"Selected recipes belong to a seasonal realm such as Season of Discovery: {seasonal}")
    unknown = sorted(set(picks) - set(recipes), key=int)
    if unknown:
        raise ValueError(f"Selected recipes are not on the page: {unknown}")
    makers = single_makers(recipes)
    shared = sorted((rid for rid in picks
                     if makes_fixed_quantity(recipes[rid]) and makers.get(recipes[rid]["creates"][0]) != rid), key=int)
    if shared:
        raise ValueError(f"Selected recipes {recipe_label(recipes, shared)} make items other recipes also make; "
                         "such items are always bought, so remove them")
    included: dict[str, dict] = {}
    for recipe_id in picks:
        _include(recipe_id, (), recipes, picks, makers, included)
    item_notes = {str(entry["item_id"]): entry for entry in selection.get("items", [])}

    defaults = selection.get("recipe_defaults", {})
    consumed = {reagent for rid in included for reagent, _ in recipes[rid]["reagents"]}
    outputs = {recipes[rid]["creates"][0] for rid in included}
    catalog_recipes = [_catalog_recipe(extract, selection["profession"], recipe_id, defaults, included[recipe_id])
                       for recipe_id in sorted(included, key=lambda rid: (recipes[rid]["learnedat"] or 0, int(rid)))]
    catalog_items = [_catalog_item(extract, item_id, _role(item_id, consumed, outputs, item_notes),
                                   item_notes.get(str(item_id), {}))
                     for item_id in sorted(consumed | outputs)]
    unused = sorted(set(item_notes) - {str(item["item_id"]) for item in catalog_items}, key=int)
    if unused:
        raise ValueError(f"Selection notes items no selected recipe uses: {unused}")

    header = {key: selection[key] for key in ("game_version", "rules_version", "profession", "status",
                                              "catalog_version")}
    return {
        "schema_version": 1, **header,
        "verified_at": extract["saved_at"],
        "verification": (f"Generated by `python -m brownstone recipes` from the Wowhead list page saved on "
                         f"{extract['saved_at']} (SHA-256 {extract['sha256'][:12]}...). Reagents, quantities, "
                         f"output counts, skill levels and vendor buy prices come from that page."),
        "source_url": extract["source_url"], "source_sha256": extract["sha256"],
        "page_coverage": page_coverage(extract),
        **({"notes": selection["notes"]} if selection.get("notes") else {}),
        "items": catalog_items, "recipes": catalog_recipes,
    }


def page_coverage(extract: dict) -> dict[str, int]:
    """Non-seasonal reagent-bearing page spells, including those not selected."""
    counts = {"usable": 0, "no_item": 0, "unknown_yield": 0}
    for recipe in extract["recipes"].values():
        if recipe.get("season") or not recipe["reagents"]:
            continue
        kind = "no_item" if not recipe["creates"] else (
            "usable" if makes_fixed_quantity(recipe) else "unknown_yield")
        counts[kind] += 1
    return counts


def makes_fixed_quantity(recipe: dict) -> bool:
    """Whether a recipe can be in a catalog: it makes one known, fixed quantity of an item.

    Wowhead lists some (Alchemy transmutes and oils, for example) as making 0, meaning unknown. Those never
    make anything in a catalog, so their item is bought instead; a yield is never guessed.
    """
    creates = recipe["creates"]
    return bool(creates) and creates[1] == creates[2] and creates[1] > 0


def single_makers(recipes: dict) -> dict[int, str]:
    """Item -> the one recipe that makes it in a catalog.

    Only recipes that make a fixed quantity count, and seasonal ones never do. Items several such recipes
    make are left out: they are always bought (CRAFT-08).
    """
    makers: dict[int, list[str]] = {}
    for recipe_id, recipe in recipes.items():
        if not recipe.get("season") and makes_fixed_quantity(recipe):
            makers.setdefault(recipe["creates"][0], []).append(recipe_id)
    return {item_id: recipe_ids[0] for item_id, recipe_ids in makers.items() if len(recipe_ids) == 1}


def recipe_label(recipes: dict, recipe_ids: list[str]) -> str:
    return ", ".join(f"{rid} ({recipes[rid]['name']})" for rid in recipe_ids)


def _include(recipe_id: str, trail: tuple[str, ...], recipes: dict, picks: dict,
             makers: dict[int, str], included: dict[str, dict]) -> None:
    if recipe_id in trail:
        raise ValueError(f"Recipe cycle through {recipe_label(recipes, list(trail + (recipe_id,)))}")
    if recipe_id in included:
        return
    recipe = recipes[recipe_id]
    if not recipe["creates"]:
        raise ValueError(f"Recipe {recipe_id} ({recipe['name']}) creates no item")
    included[recipe_id] = picks.get(recipe_id, {})
    for reagent_id, _ in recipe["reagents"]:
        if reagent_id in makers:
            _include(makers[reagent_id], trail + (recipe_id,), recipes, picks, makers, included)


def _check_availability(record: dict, label: str) -> None:
    if record.get("availability", "available") not in AVAILABILITY:
        raise ValueError(f"{label}: availability must be one of {sorted(AVAILABILITY)}")


def _catalog_recipe(extract: dict, profession: str, recipe_id: str, defaults: dict, pick: dict) -> dict:
    recipe = extract["recipes"][recipe_id]
    output_id, made_min, made_max = recipe["creates"]
    if made_min != made_max or made_min <= 0:
        raise ValueError(f"Recipe {recipe_id} makes {made_min}-{made_max}; variable yields are not supported")
    entry: dict[str, Any] = {
        "recipe_id": int(recipe_id), "name": recipe["name"], "profession": profession,
        "required_skill": recipe["learnedat"], "output_item_id": output_id, "output_quantity": made_min,
        "source_url": f"https://www.wowhead.com/{extract['game_path']}/spell={recipe_id}",
        "verified_at": extract["saved_at"], "verification_url": extract["source_url"],
        "evidence_sha256": extract["sha256"],
    }
    entry.update(defaults)
    entry.update({key: value for key, value in pick.items() if key != "recipe_id"})
    entry.pop("skillup_colors", None)
    if valid_skillup_colors(recipe.get("skillup_colors")):
        entry["skillup_colors"] = recipe["skillup_colors"]
    for key, validator in (("learned_from", valid_learned_from), ("training_cost_copper", valid_training_cost)):
        entry.pop(key, None)
        if validator(recipe.get(key)):
            entry[key] = recipe[key]
    _check_availability(entry, f"Recipe {recipe_id}")
    entry["inputs"] = [{"item_id": reagent, "quantity": quantity} for reagent, quantity in recipe["reagents"]]
    return entry


def _role(item_id: int, consumed: set[int], outputs: set[int], item_notes: dict) -> str:
    if item_id in outputs:
        return "intermediate" if item_id in consumed else "finished"
    return "vendor_material" if item_notes.get(str(item_id), {}).get("vendor") else "material"


def _catalog_item(extract: dict, item_id: int, role: str, note: dict) -> dict:
    row = extract["items"].get(str(item_id))
    if row is None:
        raise ValueError(f"Item {item_id} is used by a selected recipe but missing from the page")
    item: dict[str, Any] = {"item_id": item_id, "name": row["name"], "role": role,
                            "source_url": f"https://www.wowhead.com/{extract['game_path']}/item={item_id}"}
    if note.get("vendor"):
        # Wowhead gives many items a buy price that no vendor sells them for (Felcloth, raid gear), so
        # vendor status comes from the selection's evidence; only the price comes from the page.
        if not row["buyprice"]:
            raise ValueError(f"Item {item_id} is marked as sold by vendors but the page has no buy price")
        item.update(vendor_price_copper=row["buyprice"], vendor_price_source_url=extract["source_url"],
                    vendor_price_note="Wowhead buy price; availability and reputation discounts are not modeled")
    item.update({key: value for key, value in note.items() if key not in ("item_id", "vendor")})
    _check_availability(item, f"Item {item_id}")
    return item


def toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{k} = {toml_value(v)}" for k, v in value.items()) + " }"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)  # JSON string escapes are valid TOML basic strings.
    raise TypeError(f"Unsupported catalog value {value!r}")


def dumps_catalog(catalog: dict) -> str:
    """Deterministic TOML for a generated catalog."""
    lines = ["# Generated by `python -m brownstone recipes`; edit the selection file and regenerate, "
             "not this file."]
    lines += [f"{key} = {toml_value(value)}" for key, value in catalog.items() if key not in ("items", "recipes")]
    for item in catalog["items"]:
        lines += ["", "[[items]]", *(f"{key} = {toml_value(value)}" for key, value in item.items())]
    for recipe in catalog["recipes"]:
        lines += ["", "[[recipes]]",
                  *(f"{key} = {toml_value(value)}" for key, value in recipe.items() if key != "inputs")]
        for ingredient in recipe["inputs"]:
            lines += ["", "[[recipes.inputs]]", f"item_id = {ingredient['item_id']}",
                      f"quantity = {ingredient['quantity']}"]
    return "\n".join(lines) + "\n"


def catalog_changes(old: dict, new: dict) -> list[str]:
    """Human-readable differences in recipes and item prices between two raw catalogs (for review)."""
    def recipes(catalog):
        return {r["recipe_id"]: (r.get("required_skill"), r["output_item_id"], r["output_quantity"],
                                 tuple((i["item_id"], i["quantity"]) for i in r.get("inputs", [])))
                for r in catalog.get("recipes", [])}

    def vendor(catalog):
        return {i["item_id"]: i.get("vendor_price_copper") for i in catalog.get("items", [])}

    before, after = recipes(old), recipes(new)
    names = {r["recipe_id"]: r["name"] for r in old.get("recipes", []) + new.get("recipes", [])}
    changes = [f"added recipe {rid} {names[rid]}" for rid in sorted(set(after) - set(before))]
    changes += [f"removed recipe {rid} {names[rid]}" for rid in sorted(set(before) - set(after))]
    changes += [f"changed recipe {rid} {names[rid]}: {before[rid]} -> {after[rid]}"
                for rid in sorted(set(before) & set(after)) if before[rid] != after[rid]]
    old_prices, new_prices = vendor(old), vendor(new)
    changes += [f"vendor price of item {iid}: {old_prices[iid]} -> {new_prices[iid]}"
                for iid in sorted(set(old_prices) & set(new_prices)) if old_prices[iid] != new_prices[iid]]
    return changes
