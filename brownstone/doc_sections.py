"""Named sections of the rule and design documents, so a session reads only what a story names.

Read-only and offline: the documents stay the single home for rules; this only slices them.
"""
import re
from collections.abc import Iterator
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"
HEADING = re.compile(r"^(#+) +(.+?)\s*$")
RULE_BULLET = re.compile(r"^- \*\*([A-Z]+-\d+)\b")
RULE_TITLE = re.compile(r"^- \*\*([A-Z]+-\d+[^*]*?):?\*\*")
RULE_ID = re.compile(r"^[A-Z]+-\d+$")


def _headings(lines: list[str]) -> Iterator[tuple[int, int, str]]:
    """(line index, level, title) of each heading outside code fences."""
    fenced = False
    for number, line in enumerate(lines):
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced and (match := HEADING.match(line)):
            yield number, len(match[1]), match[2]


def _heading_span(lines: list[str], start: int, level: int) -> tuple[int, int]:
    ends = (number for number, other, _ in _headings(lines) if number > start and other <= level)
    return start, next(ends, len(lines))


def _bullet_span(lines: list[str], start: int) -> tuple[int, int]:
    """A top-level bullet with everything up to the next top-level bullet or heading (tables, notes)."""
    end = start + 1
    while end < len(lines) and not lines[end].startswith(("- ", "#")):
        end += 1
    return start, end


def rule_span(lines: list[str], rule_id: str) -> tuple[int, int] | None:
    """A rule is either a heading starting with its ID or a top-level bullet `- **ID ...**`.

    A rule heading also ends at the next rule bullet, which belongs to the section above it.
    """
    for number, level, title in _headings(lines):
        if title.split()[0] == rule_id:
            start, end = _heading_span(lines, number, level)
            bullets = (other for other in range(start + 1, end) if RULE_BULLET.match(lines[other]))
            return start, next(bullets, end)
    for number, line in enumerate(lines):
        if (match := RULE_BULLET.match(line)) and match[1] == rule_id:
            return _bullet_span(lines, number)
    return None


def heading_span(lines: list[str], query: str) -> tuple[int, int]:
    """The one heading equal to the query, else the one containing it (case-insensitive)."""
    wanted = query.casefold()
    matches = [(number, level, title) for number, level, title in _headings(lines) if wanted in title.casefold()]
    matches = [match for match in matches if match[2].casefold() == wanted] or matches
    if len(matches) != 1:
        found = "; ".join(title for _, _, title in matches) or "no heading matches"
        raise LookupError(f"Section {query!r}: {found}")
    number, level, _ = matches[0]
    return _heading_span(lines, number, level)


def story_span(lines: list[str], story_id: str) -> tuple[int, int] | None:
    """A backlog story is the heading starting with its ID, e.g. `### STORY-062 — Sales speed`."""
    for number, level, title in _headings(lines):
        if title.split()[0].upper() == story_id:
            return _heading_span(lines, number, level)
    return None


def _block(path: Path, lines: list[str], span: tuple[int, int]) -> str:
    start, end = span
    return f"{path.parent.name}/{path.name}:{start + 1}\n" + "".join(lines[start:end]).rstrip()


def _lines(path: Path, needed: bool) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines(keepends=True) if needed else []


def _stories(backlog: Path, story_ids: list[str], blocks: list[str], errors: list[str]) -> None:
    lines = _lines(backlog, bool(story_ids))
    for story_id in (value.upper() for value in story_ids):
        story_id = story_id if "-" in story_id else f"STORY-{story_id}"
        if (span := story_span(lines, story_id)) is None:
            errors.append(f"Unknown story {story_id!r} in backlog.md (finished stories are in Git)")
        else:
            blocks.append(_block(backlog, lines, span))


def lookup(rule_ids: list[str], sections: list[str], design: list[str], docs: Path = DOCS,
           stories: list[str] | None = None) -> list[str]:
    """Text of each named story, rule, requirements section and design section; misses are reported together."""
    requirements, design_path = docs / "requirements.md", docs / "design.md"
    rule_lines = _lines(requirements, bool(rule_ids or sections))
    design_lines = _lines(design_path, bool(design))
    blocks: list[str] = []
    errors: list[str] = []
    _stories(docs / "backlog.md", stories or [], blocks, errors)
    for rule_id in (value.upper() for value in rule_ids):
        span = rule_span(rule_lines, rule_id) if RULE_ID.match(rule_id) else None
        if span is None:
            errors.append(f"Unknown rule ID {rule_id!r}")
        else:
            blocks.append(_block(requirements, rule_lines, span))
    for path, lines, queries in ((requirements, rule_lines, sections), (design_path, design_lines, design)):
        for query in queries:
            try:
                blocks.append(_block(path, lines, heading_span(lines, query)))
            except LookupError as error:
                errors.append(f"{path.name}: {error}")
    if errors:
        raise LookupError("\n".join(errors))
    return blocks


def contents(docs: Path = DOCS) -> list[str]:
    """Rule IDs and headings of the rule, design and backlog documents, to find what to look up."""
    rows = []
    for path in (docs / "requirements.md", docs / "design.md", docs / "backlog.md"):
        lines = path.read_text(encoding="utf-8").splitlines()
        headings = {number: (level, title) for number, level, title in _headings(lines)}
        rows.append(f"{path.parent.name}/{path.name}")
        for number, line in enumerate(lines):
            if number in headings:
                level, title = headings[number]
                rows.append(f"{'  ' * (level - 1)}{title}")
            elif path.name == "requirements.md" and (match := RULE_TITLE.match(line)):
                rows.append(f"      {match[1]}")
    return rows
