"""Edit a tracked selection file in place, changing only the lines that change.

Selection files carry hand-written comments that explain their values (why a yield is unconfirmed, where
a vendor was seen), so they are never re-dumped. Every edit is checked by reading the result back.
"""
from __future__ import annotations

import re
import tomllib

from .recipe_import import toml_value

VENDOR_NOTE = "Marked in the app; confirm at a vendor."


def set_value(text: str, key: str, value: str) -> str:
    """Replace one top-level ``key = "..."`` line."""
    pattern = re.compile(rf'^({re.escape(key)}\s*=\s*)"[^"]*"', re.MULTILINE)
    text, count = pattern.subn(lambda match: match.group(1) + toml_value(value), text)
    if count != 1:
        raise ValueError(f"The selection file needs exactly one {key} line")
    return text


def _blocks(lines: list[str], table: str) -> list[tuple[int, int, dict]]:
    """(first line, line after the last, parsed values) of each ``[[table]]``; a block ends at a blank line
    or the next table. Comments inside a block belong to it; comments just before the next table don't."""
    blocks = []
    for start, line in enumerate(lines):
        if line.strip() != f"[[{table}]]":
            continue
        end = start + 1
        while end < len(lines) and lines[end].strip() and not lines[end].startswith("["):
            end += 1
        while lines[end - 1].startswith("#"):
            end -= 1
        blocks.append((start, end, tomllib.loads("\n".join(lines[start + 1:end]))))
    return blocks


def _drop(lines: list[str], indices: set[int]) -> list[str]:
    return [line for index, line in enumerate(lines) if index not in indices]


def _block_lines(lines: list[str], start: int, end: int) -> set[int]:
    """A whole block's lines plus the blank line before it."""
    return set(range(start - 1 if start and not lines[start - 1].strip() else start, end))


def _split_tail(lines: list[str]) -> tuple[list[str], list[str]]:
    """(lines, the comments and blank lines ending the file): those introduce nothing, so they are kept."""
    end = len(lines)
    while end and (not lines[end - 1].strip() or lines[end - 1].startswith("#")):
        end -= 1
    return lines[:end], lines[end:]


def edit_recipes(text: str, extract: dict, recipe_ids: list[int], vendor_ids: list[int],
                 used_item_ids: set[int]) -> tuple[str, list[str]]:
    """The selection with exactly ``recipe_ids`` and vendor marks on exactly ``vendor_ids``.

    Notes on items no chosen recipe uses are dropped, as the importer requires. Returns the new text and
    the dropped notes, for the preview.
    """
    wanted, vendors = set(recipe_ids), set(vendor_ids) & used_item_ids  # Only used items can be marked.
    lines, tail = _split_tail(text.rstrip("\n").split("\n"))
    recipes = _blocks(lines, "recipes")
    current = {block[2]["recipe_id"] for block in recipes}
    lines = _drop(lines, {i for start, end, values in recipes if values["recipe_id"] not in wanted
                          for i in _block_lines(lines, start, end)})
    lines, dropped = _edit_items(lines, extract, vendors, used_item_ids)
    while lines and (not lines[-1].strip() or lines[-1].startswith("#")):
        lines.pop()  # A comment left at the end introduced notes that are all gone.
    new_blocks = [line for recipe_id in sorted(wanted - current) for line in
                  ("", "[[recipes]]", f"recipe_id = {recipe_id}  # {extract['recipes'][str(recipe_id)]['name']}")]
    remaining = _blocks(lines, "recipes")
    at = remaining[-1][1] if remaining else _first_table(lines, "items")
    lines[at:at] = new_blocks
    result = "\n".join(lines + tail) + "\n"
    _check(result, wanted, vendors)
    return result, dropped


def _edit_items(lines: list[str], extract: dict, vendors: set[int], used: set[int]) -> tuple[list[str], list[str]]:
    blocks = _blocks(lines, "items")
    dropped: list[str] = []
    drop: set[int] = set()
    for start, end, values in blocks:
        item_id = values["item_id"]
        name = extract["items"].get(str(item_id), {}).get("name", f"item {item_id}")
        if item_id not in used:
            dropped.append(name)
            drop |= _block_lines(lines, start, end)
        elif values.get("vendor") and item_id not in vendors:
            # Unmarking a vendor drops its vendor lines; other notes (availability) stay.
            values_lines = [i for i in range(start + 2, end) if not lines[i].startswith("#")]
            vendor_lines = {i for i in values_lines if lines[i].startswith("vendor")}
            drop |= _block_lines(lines, start, end) if len(vendor_lines) == len(values_lines) else vendor_lines
            dropped.append(f"{name} (vendor mark)")
    lines = _drop(lines, drop)
    marked = {values["item_id"] for _, _, values in blocks if values.get("vendor")}
    for item_id in sorted(vendors - marked):
        marks = ["vendor = true", "vendor_verified = false", f"vendor_note = {toml_value(VENDOR_NOTE)}"]
        existing = next((end for _, end, values in _blocks(lines, "items") if values["item_id"] == item_id), None)
        if existing is not None:
            lines[existing:existing] = marks
        else:
            lines += ["", "[[items]]", f"item_id = {item_id}  # {extract['items'][str(item_id)]['name']}", *marks]
    return lines, dropped


def _first_table(lines: list[str], table: str) -> int:
    """Where to insert before the first ``[[table]]`` (and its leading comments), or the end."""
    for index, line in enumerate(lines):
        if line.strip() == f"[[{table}]]":
            while index and lines[index - 1].startswith("#"):
                index -= 1
            return index - 1 if index and not lines[index - 1].strip() else index
    return len(lines)


def _check(text: str, recipes: set[int], vendors: set[int]) -> None:
    data = tomllib.loads(text)
    got = [pick["recipe_id"] for pick in data.get("recipes", [])]
    marked = {item["item_id"] for item in data.get("items", []) if item.get("vendor")}
    if sorted(got) != sorted(recipes) or len(got) != len(set(got)) or marked != vendors:
        raise ValueError("Could not edit the selection file safely; edit it by hand")
