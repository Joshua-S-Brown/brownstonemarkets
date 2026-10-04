"""Recipe catalogs per game version and profession: discovery, status, and the add and update writes.

A catalog exists when its tracked selection file does (``config/recipe-selections/<name>.toml``); the
catalog itself is ``config/<name>.toml``, generated from one saved Wowhead page (CRAFT-08). Every write
here has a preview that writes nothing, and generation goes through ``recipe_import.prepare_catalog``,
as ``python -m brownstone recipes`` does. Nothing here downloads: the user saves the page in a browser.
"""
from __future__ import annotations

import hashlib
import re
import tomllib
from collections.abc import Iterable
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from . import selection_files
from .recipe_import import (
    GAME_PATHS,
    archive_bytes,
    archive_location,
    build_catalog,
    check_same_version,
    dumps_catalog,
    extract_page,
    load_selection,
    makes_fixed_quantity,
    page_build,
    parse_selection,
    prepare_catalog,
    single_makers,
    toml_value,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
ARCHIVE_DIR = ROOT / "data/recipe-sources"
SELECTIONS = "recipe-selections"
# Catalog file names start with these, for example classic-era-tailoring and forever-leatherworking.
CATALOG_PREFIXES = {"classic": "classic-era", "forever": "forever"}
# Wowhead's profession slugs (…/spells/professions/<slug>) for professions that craft items.
PROFESSIONS = ("alchemy", "blacksmithing", "cooking", "enchanting", "engineering", "first-aid",
               "leatherworking", "mining", "tailoring")
DEFAULT_REFRESH_DAYS = 30  # A selection may set refresh_after_days.
NEW_STATUS = {"classic": "reference-observed", "forever": "beta-observed"}
# Forever yields are unconfirmed until counted in game (CRAFT-08); new Forever catalogs say so.
NEW_DEFAULTS = {"forever": {"output_quantity_verified": False,
                            "output_quantity_note": "From Wowhead's list data; confirm in game by crafting one."}}
VENDOR_NOTE = selection_files.VENDOR_NOTE


def catalog_name(game: str, profession: str) -> str:
    return f"{CATALOG_PREFIXES[game]}-{profession}"


def profession_title(profession: str) -> str:
    return profession.replace("-", " ").title()


def profession_label(game: str, profession: str) -> str:
    return f"{game.title()} {profession_title(profession)}"


def build_label(patch: str | None, build: int | None) -> str | None:
    """"1.60.1 (build 70205)", or None when the page states no patch."""
    return patch and patch + (f" (build {build})" if build else "")


def wowhead_page_url(game: str, profession: str) -> str:
    """The page the user saves in a browser; Brownstone never fetches it."""
    return f"https://www.wowhead.com/{GAME_PATHS[game]}/spells/professions/{profession}"


def find_catalogs(config_dir: Path) -> list[dict]:
    """Every catalog with a selection file, whatever its profession; ``catalog`` is None until generated."""
    entries = []
    for selection_path in sorted((config_dir / SELECTIONS).glob("*.toml")):
        catalog_path = config_dir / selection_path.name
        catalog = None
        if catalog_path.exists():
            with catalog_path.open("rb") as file:
                catalog = tomllib.load(file)
        entries.append({"name": selection_path.stem, "selection_path": selection_path,
                        "catalog_path": catalog_path, "selection": load_selection(selection_path),
                        "catalog": catalog})
    return entries


def missing_professions(entries: list[dict]) -> dict[str, list[str]]:
    """Per game version, the professions with no selection file yet."""
    have = {(entry["selection"]["game_version"], entry["selection"]["profession"]) for entry in entries}
    return {game: [p for p in PROFESSIONS if (game, p) not in have] for game in CATALOG_PREFIXES}


def unconfirmed_values(catalog: dict) -> list[dict]:
    """Values still marked unconfirmed: yields, vendor status and price, and post-launch flags."""
    found = []
    for recipe in catalog.get("recipes", []):
        if recipe.get("output_quantity_verified") is False:
            found.append({"kind": "yield", "name": recipe["name"], "note": recipe.get("output_quantity_note", "")})
        if recipe.get("availability") == "post-launch":
            found.append({"kind": "post-launch", "name": recipe["name"], "note": recipe.get("availability_note", "")})
    for item in catalog.get("items", []):
        if item.get("vendor_verified") is False:
            found.append({"kind": "vendor", "name": item["name"], "note": item.get("vendor_note", "")})
        if item.get("availability") == "post-launch":
            found.append({"kind": "post-launch", "name": item["name"], "note": item.get("availability_note", "")})
    return found


def refresh_reasons(entry: dict, sources: list, today: date) -> list[str]:
    """Why the saved page should be saved again: a market moved to another rules_version, or it is old."""
    catalog = entry["catalog"] or {}
    selection = entry["selection"]
    reasons = [f"{source.get('label', source['source_id'])} uses rules {source['rules_version']}, "
               f"this catalog {selection['rules_version']}"
               for source in sources
               if source["game_version"] == selection["game_version"]
               and source.get("rules_version", selection["rules_version"]) != selection["rules_version"]]
    limit = selection.get("refresh_after_days", DEFAULT_REFRESH_DAYS)
    if catalog.get("verified_at"):
        age = (today - date.fromisoformat(catalog["verified_at"])).days
        if age > limit:
            reasons.append(f"page saved {age} days ago (refresh after {limit})")
    return reasons


def archived_copy(entry: dict, archive_dir: Path) -> Path | None:
    """The archived page behind a catalog, or None if it is not on this machine (``data/`` isn't in Git)."""
    sha256 = (entry["catalog"] or {}).get("source_sha256")
    if not sha256:
        return None
    selection = entry["selection"]
    page = archive_location(archive_dir, GAME_PATHS[selection["game_version"]], selection["profession"], sha256)
    return page if page.exists() else None


def archived_page(entry: dict, archive_dir: Path) -> dict | None:
    """The patch and build of the archived page behind a catalog, or None if it is not on this machine."""
    page = archived_copy(entry, archive_dir)
    return _archived_build(page) if page else None


@lru_cache(maxsize=64)
def _archived_build(page: Path) -> dict:
    """Archived copies are named by their SHA-256 and never rewritten, so each is scanned once."""
    return page_build(page.read_text(encoding="utf-8", errors="replace"))


def catalog_status(entry: dict, sources: list, archive_dir: Path, today: date) -> dict:
    catalog = entry["catalog"] or {}
    archived = archived_page(entry, archive_dir)
    build = build_label(archived["patch"], archived["build"]) if archived else None
    return {
        "name": entry["name"], "profession": entry["selection"]["profession"],
        "label": profession_label(entry["selection"]["game_version"], entry["selection"]["profession"]),
        "rules_version": entry["selection"]["rules_version"],
        "catalog_version": catalog.get("catalog_version"), "recipes": len(catalog.get("recipes", [])),
        "saved_at": catalog.get("verified_at"), "sha256": catalog.get("source_sha256"),
        "build": build, "archived": archived is not None,
        "unconfirmed": unconfirmed_values(catalog), "refresh": refresh_reasons(entry, sources, today),
    }


def bump_version(version: str) -> str:
    """0.1 -> 0.2: the minor part counts regenerations that changed the catalog."""
    match = re.fullmatch(r"(\d+)\.(\d+)", version)
    if not match:
        raise ValueError(f"catalog_version {version!r} is not MAJOR.MINOR; bump it by hand in the selection file")
    return f"{match.group(1)}.{int(match.group(2)) + 1}"


def choices(recipes: Iterable[int], vendor: Iterable[int] = ()) -> dict:
    """What a user chooses for a catalog: its recipes and the items sold by vendors."""
    return {"recipes": sorted(set(recipes)), "vendor": sorted(set(vendor))}


def current_choices(entry: dict) -> dict:
    """The choices a selection file records."""
    selection = entry["selection"]
    return choices([pick["recipe_id"] for pick in selection["recipes"]],
                   [item["item_id"] for item in selection.get("items", []) if item.get("vendor")])


def preview_update(entry: dict, raw: bytes, saved_at: str, chosen: dict | None = None,
                   rules_version: str | None = None) -> dict:
    """What Regenerate would write (writes nothing): the page, plus any recipe, item mark or rules changes.

    ``changed`` is False when nothing would change. Otherwise the catalog version is bumped, unless the
    catalog is being generated for the first time.
    """
    selection = entry["selection"]
    extract = read_page(raw, selection["game_version"], selection["profession"], saved_at)
    original = entry["selection_path"].read_text(encoding="utf-8")
    dropped: list[str] = []
    text = original
    if rules_version and rules_version != selection["rules_version"]:
        text = selection_files.set_value(text, "rules_version", rules_version)
    if chosen is not None:
        used = {item["item_id"] for item in build_catalog(extract, _draft_selection(extract, chosen))["items"]}
        text, dropped = selection_files.edit_recipes(text, extract, chosen["recipes"], chosen["vendor"], used)
    edited = parse_selection(tomllib.loads(text))
    current = entry["catalog_path"].read_text(encoding="utf-8") if entry["catalog_path"].exists() else None
    prepared = prepare_catalog(raw, edited, saved_at, current)
    result = {**prepared, "selection_text": text, "dropped_notes": dropped, "changed": True,
              "catalog_version": edited["catalog_version"]}
    if current is None:
        return result
    if prepared["text"] == current and text == original:
        return {**result, "changed": False}
    if tomllib.loads(current).get("catalog_version") != edited["catalog_version"]:
        return result  # The selection's version was already moved on by hand.
    version = bump_version(edited["catalog_version"])
    catalog = {**prepared["catalog"], "catalog_version": version}  # The version is a header value only.
    return {**result, "catalog": catalog, "text": dumps_catalog(catalog), "catalog_version": version,
            "selection_text": selection_files.set_value(text, "catalog_version", version)}


def regenerate(entry: dict, raw: bytes, page_name: str, saved_at: str, archive_dir: Path,
               chosen: dict | None = None, rules_version: str | None = None) -> dict:
    """Archive the page, then write the selection file and catalog that ``preview_update`` shows."""
    preview = preview_update(entry, raw, saved_at, chosen, rules_version)
    copy, manifest = archive_bytes(raw, page_name, archive_dir, saved_at)
    written: dict[str, list[Path]] = {"tracked": [], "archived": [copy, copy.with_suffix(".json")]}
    if preview["changed"]:
        if preview["selection_text"] != entry["selection_path"].read_text(encoding="utf-8"):
            entry["selection_path"].write_text(preview["selection_text"], encoding="utf-8")
            written["tracked"].append(entry["selection_path"])
        entry["catalog_path"].write_text(preview["text"], encoding="utf-8")
        written["tracked"].append(entry["catalog_path"])
    return {**preview, **written, "manifest": manifest}


def read_page(raw: bytes, game: str, profession: str, saved_at: str) -> dict:
    """Parse an uploaded page for a new catalog, refusing another game version or profession."""
    extract = extract_page(raw.decode("utf-8", errors="replace"), hashlib.sha256(raw).hexdigest(), saved_at)
    check_same_version(extract, game, profession)
    return extract


def _excluded(recipe: dict, makers: dict[int, str]) -> str | None:
    """Why a recipe on the page can't be in a catalog, or None if it can (``makers``: ``single_makers``)."""
    if recipe.get("season"):
        return "seasonal"
    if not recipe["creates"]:
        return "no item"
    if not makes_fixed_quantity(recipe):
        return "no fixed yield"
    return None if makers.get(recipe["creates"][0]) == str(recipe["id"]) else "shared item"


def recipe_counts(extract: dict) -> dict[str, int]:
    """How many recipes on the page can be offered, and why the rest can't."""
    makers = single_makers(extract["recipes"])
    counts = {"offered": 0, "no item": 0, "no fixed yield": 0, "shared item": 0, "seasonal": 0}
    for recipe in extract["recipes"].values():
        counts[_excluded(recipe, makers) or "offered"] += 1
    return counts


def candidate_recipes(extract: dict, name: str = "", min_skill: int = 0, max_skill: int = 10_000) -> list[dict]:
    """Recipes on the page that make one fixed quantity of an item, filtered by name and skill.

    Seasonal realms' spells (Season of Discovery on Classic pages) and recipes for items other recipes also
    make (always bought) are never offered.
    """
    makers = single_makers(extract["recipes"])
    found = []
    for recipe in extract["recipes"].values():
        skill = recipe["learnedat"] or 0
        if _excluded(recipe, makers):
            continue
        if name.lower() in recipe["name"].lower() and min_skill <= skill <= max_skill:
            found.append(recipe)
    return sorted(found, key=lambda recipe: (recipe["learnedat"] or 0, recipe["name"]))


def vendor_candidates(extract: dict, chosen: dict) -> list[int]:
    """Reagents of the chosen recipes (and the intermediates they pull in) that the page gives a buy price.

    A buy price is not evidence of a vendor (CRAFT-08); these are only offered for the user to mark.
    """
    if not chosen["recipes"]:
        return []
    draft = build_catalog(extract, _draft_selection(extract, chosen))
    return [item["item_id"] for item in draft["items"]
            if item["role"] == "material" and extract["items"][str(item["item_id"])]["buyprice"]]


def _draft_selection(extract: dict, chosen: dict) -> dict:
    game = next(game for game, path in GAME_PATHS.items() if path == extract["game_path"])
    return {"game_version": game, "rules_version": "draft", "profession": extract["profession"],
            "status": "draft", "catalog_version": "0.0", "recipes": [{"recipe_id": r} for r in chosen["recipes"]]}


def new_selection(game: str, profession: str, rules_version: str, chosen: dict, notes: str = "") -> dict:
    if not rules_version:
        raise ValueError("Give the rules_version of the market this catalog prices")
    if not chosen["recipes"]:
        raise ValueError("Choose at least one recipe")
    selection: dict[str, Any] = {"game_version": game, "rules_version": rules_version, "profession": profession,
                                 "status": NEW_STATUS[game], "catalog_version": "0.1"}
    if notes:
        selection["notes"] = notes
    if game in NEW_DEFAULTS:
        selection["recipe_defaults"] = dict(NEW_DEFAULTS[game])
    selection["recipes"] = [{"recipe_id": recipe_id} for recipe_id in chosen["recipes"]]
    if chosen["vendor"]:
        selection["items"] = [{"item_id": item_id, "vendor": True, "vendor_verified": False,
                               "vendor_note": VENDOR_NOTE} for item_id in chosen["vendor"]]
    return selection


def dumps_selection(selection: dict, extract: dict) -> str:
    """A selection file in the hand-written files' layout, with each recipe and item named in a comment."""
    name = catalog_name(selection["game_version"], selection["profession"])
    lines = [f"# Which recipes `python -m brownstone recipes` puts in config/{name}.toml.",
             "# List finished recipes; the intermediates they need are added from the same page.",
             f"# Source page: {extract['source_url']}, saved in a browser. Added in the app."]
    lines += [f"{key} = {toml_value(selection[key])}" for key in
              ("game_version", "rules_version", "profession", "status", "catalog_version", "notes")
              if key in selection]
    if selection.get("recipe_defaults"):
        lines += ["", "[recipe_defaults]",
                  *(f"{key} = {toml_value(value)}" for key, value in selection["recipe_defaults"].items())]
    for pick in selection["recipes"]:
        lines += ["", "[[recipes]]",
                  f"recipe_id = {pick['recipe_id']}  # {extract['recipes'][str(pick['recipe_id'])]['name']}"]
    for note in selection.get("items", []):
        lines += ["", "[[items]]", f"item_id = {note['item_id']}  # {extract['items'][str(note['item_id'])]['name']}",
                  *(f"{key} = {toml_value(value)}" for key, value in note.items() if key != "item_id")]
    return "\n".join(lines) + "\n"


def preview_new(config_dir: Path, raw: bytes, selection: dict, saved_at: str) -> dict:
    """The selection file and catalog a new profession would get (writes nothing)."""
    name = catalog_name(selection["game_version"], selection["profession"])
    selection_path = config_dir / SELECTIONS / f"{name}.toml"
    if selection_path.exists():
        raise ValueError(f"{name} already has a selection file; update it instead")
    catalog_path = config_dir / f"{name}.toml"
    if catalog_path.exists():
        raise ValueError(f"config/{name}.toml exists without a selection file; move it aside or write its "
                         "selection file by hand")
    prepared = prepare_catalog(raw, selection, saved_at, None)
    selection_text = dumps_selection(selection, prepared["extract"])
    if tomllib.loads(selection_text) != selection:
        raise ValueError("The selection file would not read back as chosen")  # Guards the writer above.
    return {**prepared, "name": name, "selection_path": selection_path, "catalog_path": catalog_path,
            "selection_text": selection_text}


def create(config_dir: Path, raw: bytes, page_name: str, selection: dict, saved_at: str,
           archive_dir: Path) -> dict:
    """Archive the page and write the new selection file and catalog."""
    preview = preview_new(config_dir, raw, selection, saved_at)
    copy, manifest = archive_bytes(raw, page_name, archive_dir, saved_at)
    preview["selection_path"].parent.mkdir(parents=True, exist_ok=True)
    preview["selection_path"].write_text(preview["selection_text"], encoding="utf-8")
    preview["catalog_path"].write_text(preview["text"], encoding="utf-8")
    return {**preview, "manifest": manifest, "catalog_version": selection["catalog_version"],
            "tracked": [preview["selection_path"], preview["catalog_path"]],
            "archived": [copy, copy.with_suffix(".json")]}
