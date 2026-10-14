"""Catalog discovery stays selection-driven after retiring the catalog editor."""
from pathlib import Path

from test_cli import SELECTION

from brownstone import recipe_catalogs as rc

ROOT = Path(__file__).resolve().parents[1]
def test_catalogs_are_found_by_selection_file_for_any_profession(tmp_path):
    entries = rc.find_catalogs(ROOT / "config")  # Discovery is driven by selections.
    assert {"classic-era-tailoring", "forever-tailoring"} <= {entry["name"] for entry in entries}
    assert all(entry["catalog"]["recipes"] for entry in entries)

    (tmp_path / rc.SELECTIONS).mkdir()
    (tmp_path / rc.SELECTIONS / "forever-leatherworking.toml").write_text(
        SELECTION.replace("tailoring", "leatherworking"), encoding="utf-8")
    (entry,) = rc.find_catalogs(tmp_path)
    assert entry["name"] == "forever-leatherworking" and entry["catalog"] is None  # Not generated yet.
