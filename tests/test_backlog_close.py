"""Closing a story edits only docs/backlog.md's story section, Done list and Order list; misses change nothing."""
import pytest

from brownstone import backlog_close, cli

BACKLOG = """# Backlog

## Next

**Order** (groomed):
1. STORY-062 sales speed (after STORY-027's check)
2. STORY-026 scan coverage
3. STORY-006 replay

**Done** (story text in Git): STORY-015b, 021, 063, 034b, 080 and SPIKE-009/009b.

### STORY-026 — Scan coverage

- coverage

### STORY-062 — Sales speed

As the owner, I want sales speed.

- **Acceptance.** Uses STORY-027.

### STORY-006 — Replay

- replay

## Later

- STORY-062 follow-up idea
"""


def test_close_story_removes_the_section_adds_done_in_order_and_renumbers():
    text, changes = backlog_close.close_story(BACKLOG, "STORY-062")
    assert "### STORY-062" not in text and "I want sales speed" not in text
    assert "### STORY-026 — Scan coverage\n\n- coverage\n\n### STORY-006" in text
    assert "STORY-015b, 021, 034b, 062, 063, 080 and SPIKE-009/009b." in text
    assert "1. STORY-026 scan coverage\n2. STORY-006 replay\n\n**Done**" in text
    assert "- STORY-062 follow-up idea" in text
    assert changes == ["Removed the STORY-062 section (6 lines from line 16)",
                       "Added STORY-062 to the Done list (now in numeric order)",
                       "Removed STORY-062 from the Order list and renumbered the 2 left"]


def test_close_story_accepts_bare_numbers_and_letter_suffixes():
    backlog = BACKLOG.replace("### STORY-006 — Replay", "### STORY-034c — Split")
    text, changes = backlog_close.close_story(backlog, "034c")
    assert "STORY-015b, 021, 034b, 034c, 063, 080 and" in text
    assert changes[2] == "STORY-034c was not in the Order list"
    assert "3. STORY-006 replay" in text


def test_close_story_reports_a_story_already_done():
    backlog = BACKLOG.replace("063, 034b", "062, 063, 034b")
    text, changes = backlog_close.close_story(backlog, "062")
    assert changes[1] == "STORY-062 was already in the Done list"
    assert text.count("062,") == 1


@pytest.mark.parametrize(("story_id", "backlog", "error", "message"), [
    ("STORY-099", BACKLOG, LookupError, "STORY-099 has no section"),
    ("SPIKE-009", BACKLOG, ValueError, "Not a story ID"),
    ("062", BACKLOG.replace("**Done**", "Done"), LookupError, "No **Done** list"),
    ("062", BACKLOG.replace("**Order**", "Order"), LookupError, "No **Order** list"),
])
def test_close_story_refuses_without_changes(story_id, backlog, error, message):
    with pytest.raises(error, match=message.replace("*", r"\*")):
        backlog_close.close_story(backlog, story_id)


def test_close_story_command_writes_the_file_and_prints_changes(tmp_path, monkeypatch, capsys):
    (tmp_path / "backlog.md").write_text(BACKLOG, encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["brownstone", "close-story", "STORY-062", "--docs", str(tmp_path)])
    cli.main()
    assert "### STORY-062" not in (tmp_path / "backlog.md").read_text(encoding="utf-8")
    assert capsys.readouterr().out.splitlines()[0].startswith("Removed the STORY-062 section")


def test_close_story_command_refuses_unknown_stories_and_leaves_the_file(tmp_path, monkeypatch, capsys):
    (tmp_path / "backlog.md").write_text(BACKLOG, encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["brownstone", "close-story", "STORY-099", "--docs", str(tmp_path)])
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    assert exit_info.value.code == 1
    assert (tmp_path / "backlog.md").read_text(encoding="utf-8") == BACKLOG
    assert "Nothing changed: STORY-099 has no section" in capsys.readouterr().err
