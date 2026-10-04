"""Build recipe catalogs from a Wowhead profession list page saved in the user's browser.

Wowhead's terms allow personal use through a web browser but not automated downloads (recorded in
requirements.md), so this module never touches the network. One saved page, for example
``https://www.wowhead.com/forever/spells/professions/tailoring``, carries every recipe of a profession
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

from .crafting import AVAILABILITY

GAME_PATHS = {"classic": "classic", "forever": "forever"}  # Catalog game_version -> Wowhead path segment.
_CANONICAL = re.compile(
    r'<link rel="canonical" href="https://www\.wowhead\.com/([a-z-]+)/spells/professions/([a-z-]+)">')
_UNQUOTED_KEY = re.compile(r'([{,])([A-Za-z_]\w*):')


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
        raise ValueError("Not a Wowhead profession spell list page (no canonical .../spells/professions/... link)")
    game_path, profession = match.groups()
    recipes = {}
    for row in _literal(html, "listviewspells =", "[", "]"):
        recipe = {"id": row["id"], "name": row["name"], "learnedat": row.get("learnedat"),
                  "creates": row.get("creates"), "reagents": row.get("reagents") or []}
        if "envChange" in row:  # Forever pages flag new or changed spells relative to Classic.
            recipe["env_status"] = row["envChange"].get("status")
        recipes[str(row["id"])] = recipe
    items = {}
    for item_id, row in _literal(html, "WH.Gatherer.addData(3,", "{", "}").items():
        prices = row.get("jsonequip", {})
        items[item_id] = {"name": row["name_enus"], "sellprice": prices.get("sellprice"),
                          "buyprice": prices.get("buyprice")}
    if not recipes or not items:
        raise ValueError("The saved page holds no recipe or item data")
    return {"source_url": f"https://www.wowhead.com/{game_path}/spells/professions/{profession}",
            "game_path": game_path,
            "profession": profession, "sha256": sha256, "saved_at": saved_at,
            "recipes": recipes, "items": items}


def archive_page(page: Path, archive_dir: Path, saved_at: str | None = None) -> tuple[Path, dict]:
    """Keep the page's exact bytes once per SHA-256 with a provenance manifest; return (copy, manifest).

    ``saved_at`` (YYYY-MM-DD) is when the page was saved in the browser. It defaults to an earlier
    manifest for the same bytes, then to the file's modification date, so rebuilding from the archive
    reproduces the same catalog.
    """
    raw = page.read_bytes()
    sha256 = hashlib.sha256(raw).hexdigest()
    html = raw.decode("utf-8", errors="replace")
    match = _CANONICAL.search(html)
    if not match:
        raise ValueError("Not a Wowhead profession spell list page (no canonical .../spells/professions/... link)")
    folder = archive_dir / "wowhead" / match.group(1) / match.group(2)
    copy, manifest_path = folder / f"{sha256[:16]}.html", folder / f"{sha256[:16]}.json"
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    saved_at = (saved_at or previous.get("saved_at")
                or datetime.fromtimestamp(page.stat().st_mtime, UTC).date().isoformat())
    date.fromisoformat(saved_at)
    folder.mkdir(parents=True, exist_ok=True)
    if not copy.exists():
        copy.write_bytes(raw)
    manifest = {"source_url": extract_page(html, sha256, saved_at)["source_url"], "sha256": sha256,
                "saved_at": saved_at, "original_name": page.name,
                "archived_at": previous.get("archived_at") or datetime.now(UTC).isoformat(timespec="seconds"),
                "bronze_file": copy.name, "capture": "saved by the user in a web browser"}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return copy, manifest


def load_selection(path: Path) -> dict:
    with path.open("rb") as file:
        selection = tomllib.load(file)
    for key in ("game_version", "rules_version", "profession", "status", "catalog_version"):
        if not selection.get(key):
            raise ValueError(f"Selection requires {key}")
    if selection["game_version"] not in GAME_PATHS:
        raise ValueError(f"No Wowhead path for game_version {selection['game_version']}")
    if not selection.get("recipes"):
        raise ValueError("Selection must list at least one recipe")
    return selection


def build_catalog(extract: dict, selection: dict) -> dict:  # noqa: C901
    """Catalog for the selected recipes plus every intermediate they need, in the loader's shape.

    A reagent created by exactly one recipe on the page is crafted (an intermediate); a reagent created
    by several must have its recipe selected explicitly. Vendor materials are the items the selection marks
    ``vendor = true`` with evidence; their price is the page's buy price. Nothing is inferred from names,
    and values never come from another game version's page.
    """
    game = selection["game_version"]
    if extract["game_path"] != GAME_PATHS[game] or extract["profession"] != selection["profession"]:
        raise ValueError(f"The page is {extract['game_path']} {extract['profession']}, but the selection is "
                         f"{game} {selection['profession']}; catalogs never borrow another version's data")
    recipes, items = extract["recipes"], extract["items"]
    picks = {str(pick["recipe_id"]): pick for pick in selection["recipes"]}
    unknown = sorted(set(picks) - set(recipes), key=int)
    if unknown:
        raise ValueError(f"Selected recipes are not on the page: {unknown}")
    creators: dict[int, list[str]] = {}
    for recipe_id, recipe in recipes.items():
        if recipe["creates"]:
            creators.setdefault(recipe["creates"][0], []).append(recipe_id)

    included: dict[str, dict] = {}  # Recipe ID -> pick (or {} for an automatic intermediate).

    def include(recipe_id: str, trail: tuple[str, ...]) -> None:
        if recipe_id in trail:
            raise ValueError(f"Recipe cycle through {recipe_id}")
        if recipe_id in included:
            return
        recipe = recipes[recipe_id]
        if not recipe["creates"]:
            raise ValueError(f"Recipe {recipe_id} ({recipe['name']}) creates no item")
        included[recipe_id] = picks.get(recipe_id, {})
        for reagent_id, _ in recipe["reagents"]:
            options = creators.get(reagent_id, [])
            chosen = [option for option in options if option in picks]
            if len(chosen) > 1 or (len(options) > 1 and not chosen):
                raise ValueError(f"Item {reagent_id} is made by recipes {options}; select exactly one of them")
            if chosen or options:
                include((chosen or options)[0], trail + (recipe_id,))

    for recipe_id in picks:
        include(recipe_id, ())

    defaults = selection.get("recipe_defaults", {})
    item_notes = {str(entry["item_id"]): entry for entry in selection.get("items", [])}
    consumed = {reagent for rid in included for reagent, _ in recipes[rid]["reagents"]}
    outputs = {recipes[rid]["creates"][0] for rid in included}
    catalog_recipes = []
    for recipe_id in sorted(included, key=lambda rid: (recipes[rid]["learnedat"] or 0, int(rid))):
        recipe, pick = recipes[recipe_id], included[recipe_id]
        output_id, made_min, made_max = recipe["creates"]
        if made_min != made_max or made_min <= 0:
            raise ValueError(f"Recipe {recipe_id} makes {made_min}-{made_max}; variable yields are not supported")
        entry: dict[str, Any] = {
            "recipe_id": int(recipe_id), "name": recipe["name"], "profession": selection["profession"],
            "required_skill": recipe["learnedat"], "output_item_id": output_id, "output_quantity": made_min,
            "source_url": f"https://www.wowhead.com/{extract['game_path']}/spell={recipe_id}",
            "verified_at": extract["saved_at"], "verification_url": extract["source_url"],
            "evidence_sha256": extract["sha256"],
        }
        entry.update(defaults)
        entry.update({key: value for key, value in pick.items() if key != "recipe_id"})
        if entry.get("availability", "available") not in AVAILABILITY:
            raise ValueError(f"Recipe {recipe_id}: availability must be one of {sorted(AVAILABILITY)}")
        entry["inputs"] = [{"item_id": reagent, "quantity": quantity} for reagent, quantity in recipe["reagents"]]
        catalog_recipes.append(entry)

    catalog_items = []
    for item_id in sorted(consumed | outputs):
        row = items.get(str(item_id))
        if row is None:
            raise ValueError(f"Item {item_id} is used by a selected recipe but missing from the page")
        note = item_notes.get(str(item_id), {})
        role = ("intermediate" if item_id in outputs and item_id in consumed else "finished" if item_id in outputs
                else "vendor_material" if note.get("vendor") else "material")
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
        if item.get("availability", "available") not in AVAILABILITY:
            raise ValueError(f"Item {item_id}: availability must be one of {sorted(AVAILABILITY)}")
        catalog_items.append(item)
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
        **({"notes": selection["notes"]} if selection.get("notes") else {}),
        "items": catalog_items, "recipes": catalog_recipes,
    }


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)  # JSON string escapes are valid TOML basic strings.
    raise TypeError(f"Unsupported catalog value {value!r}")


def dumps_catalog(catalog: dict) -> str:
    """Deterministic TOML for a generated catalog."""
    lines = ["# Generated by `python -m brownstone recipes`; edit the selection file and regenerate, "
             "not this file."]
    lines += [f"{key} = {_toml_value(value)}" for key, value in catalog.items() if key not in ("items", "recipes")]
    for item in catalog["items"]:
        lines += ["", "[[items]]", *(f"{key} = {_toml_value(value)}" for key, value in item.items())]
    for recipe in catalog["recipes"]:
        lines += ["", "[[recipes]]",
                  *(f"{key} = {_toml_value(value)}" for key, value in recipe.items() if key != "inputs")]
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
