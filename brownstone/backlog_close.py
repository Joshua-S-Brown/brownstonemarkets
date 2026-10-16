"""Close a finished story in docs/backlog.md: the mechanical edits only (docs/prompts/story-closure.md).

Removes the story's section, adds it to the *Done* list in numeric order and drops it from the numbered *Order*
list. Offline, and nothing is written unless every step finds what it needs.
"""
import re
from pathlib import Path

from .doc_sections import DOCS, story_span

DONE = re.compile(r"^(?P<head>\*\*Done\*\*.*?: STORY-)(?P<ids>\d+[a-z]?(?:(?:, | and )\d+[a-z]?)*)(?P<tail>.*)$")
ORDER_ITEM = re.compile(r"^\d+\. ")


def story_number(story_id: str) -> str:
    """`062`, `STORY-062` or `story-034b` -> `062` / `034b`; anything else is refused."""
    match = re.fullmatch(r"(?:STORY-)?(\d+[a-z]?)", story_id.strip(), re.IGNORECASE)
    if match is None:
        raise ValueError(f"Not a story ID: {story_id!r} (expected STORY-NNN)")
    return match[1].lower()


def _sort_key(number: str) -> tuple[int, str]:
    digits = re.match(r"\d+", number)
    assert digits is not None
    return int(digits[0]), number[digits.end():]


def _add_to_done(lines: list[str], number: str) -> str:
    for index, line in enumerate(lines):
        if match := DONE.match(line.rstrip("\n")):
            numbers = re.split(r", | and ", match["ids"])
            if number in numbers:
                return f"STORY-{number} was already in the Done list"
            ordered = sorted([*numbers, number], key=_sort_key)
            lines[index] = f"{match['head']}{', '.join(ordered)}{match['tail']}\n"
            return f"Added STORY-{number} to the Done list (now in numeric order)"
    raise LookupError("No **Done** list of the form `**Done** ...: STORY-001, 002 ...` in backlog.md")


def _drop_from_order(lines: list[str], story_id: str) -> str:
    start = next((index for index, line in enumerate(lines) if line.startswith("**Order**")), None)
    if start is None:
        raise LookupError("No **Order** list in backlog.md")
    first = end = start + 1
    while end < len(lines) and ORDER_ITEM.match(lines[end]):
        end += 1
    items = [line.split(". ", 1)[1].rstrip("\n") for line in lines[first:end]]
    kept = [text for text in items if not re.match(rf"{story_id}\b", text)]
    if len(kept) == len(items):
        return f"{story_id} was not in the Order list"
    lines[first:end] = [f"{position}. {text}\n" for position, text in enumerate(kept, 1)]
    return f"Removed {story_id} from the Order list and renumbered the {len(kept)} left"


def close_story(text: str, story_id: str) -> tuple[str, list[str]]:
    """The backlog text with the story closed, and one line per change; LookupError if the story isn't there."""
    number = story_number(story_id)
    story_id = f"STORY-{number}"
    lines = text.splitlines(keepends=True)
    span = story_span(lines, story_id.upper())
    if span is None:
        raise LookupError(f"{story_id} has no section in backlog.md (already closed?)")
    start, end = span
    del lines[start:end]
    changes = [f"Removed the {story_id} section ({end - start} lines from line {start + 1})",
               _add_to_done(lines, number), _drop_from_order(lines, story_id)]
    return "".join(lines), changes


def close_story_file(story_id: str, docs: Path = DOCS) -> list[str]:
    path = docs / "backlog.md"
    text, changes = close_story(path.read_text(encoding="utf-8"), story_id)
    path.write_text(text, encoding="utf-8")
    return changes
