"""Rule and design lookup: only the named sections are printed, read-only and offline."""
import re

import pytest

from brownstone import cli, doc_sections

REQUIREMENTS = """# Requirements

## Rules

### Data
- **DATA-01 Raw:** keep bytes.
  - sub-rule
- **DATA-02:** validate.

  | Table | inside a loose bullet |

Note paragraph for DATA-02.
- **Stock:** not a rule.

### UI-17 Item history (STORY-021)

- history line
- **UI-08 Checklist:** belongs to the section above.
  1. numbered

### Operations
- **OPS-01:** offline tests.
"""
DESIGN = """# Design

## Data flow
flow text
```text
# not a heading
```
### Item charts (STORY-021)
chart text
## Market charts
other charts
"""
BACKLOG = """# Backlog

## Next

### STORY-062 — Sales speed

Acceptance:
- **STORY-027 removal rate** per item.

### STORY-011a — Survey

survey text

## Later
- **Idea:** later.
"""

@pytest.fixture
def docs(tmp_path):
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "requirements.md").write_text(REQUIREMENTS, encoding="utf-8")
    (folder / "design.md").write_text(DESIGN, encoding="utf-8")
    (folder / "backlog.md").write_text(BACKLOG, encoding="utf-8")
    return folder


def rules(monkeypatch, docs, *args):
    monkeypatch.setattr("sys.argv", ["brownstone", "rules", *args, "--docs", str(docs)])
    cli.main()


def test_bullet_rules_keep_sub_bullets_and_loose_content_but_stop_at_the_next_bullet(docs):
    data_01, data_02 = doc_sections.lookup(["DATA-01", "data-02"], [], [], docs)
    assert data_01 == "docs/requirements.md:6\n- **DATA-01 Raw:** keep bytes.\n  - sub-rule"
    assert "inside a loose bullet" in data_02 and "Note paragraph" in data_02 and "Stock" not in data_02


def test_heading_rules_stop_at_the_next_rule_bullet_or_heading(docs):
    [ui_17, ops] = doc_sections.lookup(["UI-17", "OPS-01"], [], [], docs)
    assert ui_17.startswith("docs/requirements.md:15\n### UI-17") and "history line" in ui_17
    assert "UI-08" not in ui_17
    assert ops.endswith("- **OPS-01:** offline tests.")
    assert "numbered" in doc_sections.lookup(["UI-08"], [], [], docs)[0]


def test_sections_match_headings_exactly_first_then_by_substring_outside_code_fences(docs):
    [data, flow, charts] = doc_sections.lookup([], ["data"], ["Data flow", "item charts"], docs)
    assert data.startswith("docs/requirements.md:5\n### Data") and "OPS-01" not in data
    assert flow.startswith("docs/design.md:3") and "# not a heading" in flow and "chart text" in flow
    assert charts == "docs/design.md:8\n### Item charts (STORY-021)\nchart text"
    with pytest.raises(LookupError, match="Item charts .*; Market charts"):
        doc_sections.lookup([], [], ["charts"], docs)


def test_stories_come_first_by_full_id_or_story_number(docs):
    sales, survey, ops = doc_sections.lookup(["OPS-01"], [], [], docs, ["062", "story-011A"])
    assert sales.startswith("docs/backlog.md:5\n### STORY-062") and "removal rate" in sales and "Survey" not in sales
    assert survey == "docs/backlog.md:10\n### STORY-011a — Survey\n\nsurvey text"
    assert ops.startswith("docs/requirements.md")
    with pytest.raises(LookupError, match="Unknown story 'STORY-021' in backlog.md"):
        doc_sections.lookup([], [], [], docs, ["021"])


def test_every_miss_is_reported_together(monkeypatch, docs, capsys):
    with pytest.raises(SystemExit) as exit_:
        rules(monkeypatch, docs, "UI-99", "nonsense", "--design", "zzz", "--section", "Missing")
    assert exit_.value.code == 1
    err = capsys.readouterr().err
    assert "Unknown rule ID 'UI-99'" in err and "Unknown rule ID 'NONSENSE'" in err
    assert "design.md: Section 'zzz': no heading matches" in err and "requirements.md: Section 'Missing'" in err
    assert "--list" in err


def test_command_prints_named_sections_or_the_contents(monkeypatch, docs, capsys):
    rules(monkeypatch, docs, "OPS-01", "--design", "Item charts")
    assert capsys.readouterr().out == ("docs/requirements.md:22\n- **OPS-01:** offline tests.\n\n"
                                       "docs/design.md:8\n### Item charts (STORY-021)\nchart text\n")
    rules(monkeypatch, docs, "--story", "062")
    assert capsys.readouterr().out.startswith("docs/backlog.md:5\n### STORY-062")
    rules(monkeypatch, docs, "--list")
    listing = capsys.readouterr().out.splitlines()
    assert "    STORY-062 — Sales speed" in listing and "      Idea" not in listing
    assert "      DATA-01 Raw" in listing and "      DATA-02" in listing and "  UI-17" not in listing
    assert "    UI-17 Item history (STORY-021)" in listing and "  Market charts" in listing
    assert "# not a heading" not in listing and "      Stock" not in listing
    with pytest.raises(SystemExit):
        rules(monkeypatch, docs)
    assert "name at least one rule ID" in capsys.readouterr().err


def test_every_rule_id_in_the_real_requirements_resolves():
    text = (doc_sections.DOCS / "requirements.md").read_text(encoding="utf-8")
    ids = sorted(set(re.findall(r"\b(?:DATA|ADDON|CRAFT|MONEY|UI|OPS)-\d+\b", text)))
    blocks = doc_sections.lookup(ids, [], [], doc_sections.DOCS)
    assert all(block.split("\n")[1].lstrip("-#* ").startswith(rule) for rule, block in zip(ids, blocks, strict=True))
