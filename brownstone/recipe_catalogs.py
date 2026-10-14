"""Selection-based catalog discovery and verified learning labels for the app and CLI."""
import tomllib
from pathlib import Path

from .crafting import parse_recipe_catalog
from .recipe_import import load_selection

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
ARCHIVE_DIR = ROOT / "data/recipe-sources"
SELECTIONS = "recipe-selections"
# Wowhead's slugs (…/spells/professions/<slug>, or secondary-skills/ for Cooking and First Aid) for professions
# that craft items.
PROFESSIONS = ("alchemy", "blacksmithing", "cooking", "enchanting", "engineering", "first-aid",
               "leatherworking", "mining", "tailoring")


def profession_title(profession: str) -> str:
    return profession.replace("-", " ").title()


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


def parse_catalogs(entries: list[dict]) -> tuple[list[dict], list[str]]:
    """Generated catalogs ready for the board, each with its ``catalog_id``; one bad catalog never hides the rest."""
    catalogs, errors = [], []
    for entry in entries:
        if entry["catalog"]:
            try:
                catalogs.append({**parse_recipe_catalog(entry["catalog"]), "catalog_id": entry["name"]})
            except Exception as error:
                errors.append(f"Recipe catalog {entry['name']} unavailable: {error}")
    return catalogs, errors


LEARNING_LABELS = {2: "drop", 4: "quest", 5: "vendor", 6: "trainer"}


def learning_label(recipe: dict) -> str:
    """Only verified listview-code meanings belong here; see CRAFT-08's evidence table."""
    return ", ".join(LEARNING_LABELS.get(code, f"other (code {code})")
                     for code in recipe.get("learned_from", [])) or "unknown"
