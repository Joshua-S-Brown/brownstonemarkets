"""After-play check: offline, sanitized drops; state stays under the given (ignored) path."""
import json
import sys
from pathlib import Path

import pytest
from test_scan_inputs import dropped, inputs
from test_scans import FINISHED, NOW, listing, scan

from brownstone import after_play, beta_report, cli

README = """# Addon

## Last beta play session (by 21 October)

Play actions only.

1. **12-hour label (STORY-027):** scan once while posts
   have 8–12 hours left.
2. `/reload`, log out and run the drop script.

## Run a scan

1. Not a pending check.
"""


def run(config, tmp_path, report=beta_report.create_report):
    return after_play.run(config, tmp_path / "work/after-play/state.json", tmp_path / "work/beta-reports",
                          README, NOW, report)


def test_pending_checks_from_the_readme_section_only():
    assert after_play.pending_checks(README) == [
        "12-hour label (STORY-027): scan once while posts have 8–12 hours left.",
        "/reload, log out and run the drop script."]
    assert after_play.pending_checks("# No section\n") == []
    real = (Path(__file__).parents[1] / "addon/README.md").read_text(encoding="utf-8")
    assert after_play.pending_checks(real)


def test_first_run_imports_reports_and_later_runs_show_only_changes(tmp_path):
    config, folder = inputs(tmp_path)
    first = dropped(folder, [scan("win1", FINISHED, [listing(2, 1, 80)])])
    lines, code = run(config, tmp_path)
    text = "\n".join(lines)
    assert code == 0, text
    assert "1 new scans ['win1']" in text and "first after-play run" in text
    assert "new scan in file: win1" in text and "newly eligible scan: win1" in text
    assert "mac: own.lua" in text  # The configured local file is reported beside the latest drop.
    assert "  1. 12-hour label" in text and "Result: no failures" in text
    state_path = tmp_path / "work/after-play/state.json"
    state = json.loads(state_path.read_text())
    assert state["machines"]["windows-pc"]["path"] == str(first) and "win1" in state["eligible"]
    assert first.read_bytes().startswith(b"BrownstoneScanDB")  # Drops are never rewritten.

    lines, code = run(config, tmp_path)
    text = "\n".join(lines)
    assert code == 0 and "nothing new to import" in text and "unchanged since the previous run" in text
    assert "Eligible scans:\n  no change" in text and len(list((tmp_path / "work/beta-reports").iterdir())) == 2

    dropped(folder, [scan("win1", FINISHED, [listing(2, 1, 80)]), scan("win2", FINISHED + 60, [listing(3, 1, 90)])],
            "windows-pc-20261007T014900Z-BrownstoneScan.lua")
    lines, code = run(config, tmp_path)
    text = "\n".join(lines)
    assert code == 0 and "new scan in file: win2" in text and "new scan in file: win1" not in text
    assert "newly eligible scan: win2" in text and "first after-play run" not in text
    report = json.loads(next(Path(json.loads(state_path.read_text())["machines"]["windows-pc"]["report"])
                             .glob("report.json")).read_text())
    assert report["comparison"]["new_scans"] == 1  # The kept earlier drop was compared.


def test_unpriced_scan_is_not_eligible_and_report_fail_sets_the_exit_code(tmp_path):
    config, folder = inputs(tmp_path)
    dropped(folder, [scan("stopped", FINISHED, [listing(2, 1, 80)], status="stopped")])

    def failing(*args):
        folder_, report, _ = beta_report.create_report(*args)
        report["checks"].append({"check": "parse", "status": "fail", "detail": "broken", "entry_ids": []})
        return folder_, report, 1
    lines, code = run(config, tmp_path, failing)
    text = "\n".join(lines)
    assert code == 1 and "FAIL parse: broken (new)" in text and "Result: failures above" in text
    assert "NOT eligible (incomplete, partial, unpriced or other house): stopped" in text


def test_import_failures_are_reported_and_fail_the_run(tmp_path, monkeypatch):
    config, folder = inputs(tmp_path)
    dropped(folder, [scan("win1", FINISHED, [listing(2, 1, 80)])])
    monkeypatch.setattr(after_play, "import_inputs", lambda *a, **k: [
        {"file": str(folder / "x.lua"), "status": "error", "error": "boom"}])
    lines, code = run(config, tmp_path)
    assert code == 1 and "  IMPORT FAILED x.lua: boom" in lines

    def stale(*args, **kwargs):
        raise ValueError("Preview is stale")
    monkeypatch.setattr(after_play, "import_inputs", stale)
    lines, _ = run(config, tmp_path)
    assert "  IMPORT FAILED: Preview is stale" in lines


def test_unreadable_drop_is_listed(tmp_path):
    config, folder = inputs(tmp_path)
    (folder / "windows-pc-20261007T004900Z-BrownstoneScan.lua").write_bytes(b"broken lua")
    lines, _ = run(config, tmp_path, lambda *a: (tmp_path, {"file": {}, "totals": {}, "checks": []}, 0))
    assert any(line.startswith("  unreadable windows-pc-") for line in lines)


def test_file_summary_diffs_fails_warns_versions_and_evidence():
    previous = {"addon_versions": ["0.12.6"], "scans": ["a"], "fails": ["x: old", "y: kept"], "warns": ["w: gone"],
                "evidence": {"sale posts": 1}}
    current = {"path": "/drop/f.lua", "report": "r", "totals": {"pass": 1, "warn": 1, "fail": 1},
               "addon_versions": ["0.12.8"], "scans": ["a", "b"], "fails": ["y: kept"], "warns": ["w: new"],
               "evidence": {"sale posts": 3, "loot windows": 0}}
    assert after_play.file_summary("win", previous, current)[1:] == [
        "  addon versions: ['0.12.6'] -> ['0.12.8']", "  new scan in file: b", "  FAIL y: kept",
        "  resolved fail: x: old", "  new warn w: new", "  resolved warn w: gone", "  sale posts: 1 -> 3"]
    grouped = after_play._changes("warn", [], ["coverage: a", "coverage: b", "time: c"])
    assert grouped == ["  new warn coverage: a; b", "  new warn time: c"]
    assert after_play.eligibility_summary([], list("abcde"), ["a"]) == [
        "  newly eligible scan: a", "  newly eligible scan: b", "  newly eligible scan: c",
        "  ... and 2 older newly eligible scans"]


def test_labels_evidence_and_state_reset_across_sources(tmp_path):
    coverage = {"check": "coverage", "status": "warn", "detail": {"checklist": "journal", "action": "money"}}
    other = {"check": "time", "status": "warn", "detail": {"z": 1}}
    assert after_play._label(coverage) == "coverage: journal money"
    assert after_play._label(other) == 'time: {"z": 1}'
    report = {"your_sales": {"posts": [1], "outcomes": [], "unidentified": 2},
              "characters": [{"latest_owned_auctions": {"observed_rows": 4}, "latest_known_recipes": [{}]}],
              "trainer_tiers": {"observations": [1]}, "scan_attempts": {"attempts": [1]},
              "farming_capture": {"loot_windows": 2}}
    assert after_play._evidence(report) == {
        "sale posts": 1, "sale outcomes": 0, "unidentified invoices": 2, "trainer tier observations": 1,
        "failed scan starts": 1, "loot windows": 2, "owned auction rows": 4, "recipe windows": 1}
    assert after_play._evidence({}) == {k: 0 for k in after_play._evidence(report)}
    state = tmp_path / "work/after-play/state.json"
    after_play.write_state(state, {"source_id": "elsewhere", "machines": {"windows-pc": {"sha256": "x"}}})
    config, folder = inputs(tmp_path)
    dropped(folder, [scan("win1", FINISHED, [listing(2, 1, 80)])])
    assert "first after-play run" in "\n".join(run(config, tmp_path)[0])
    state.write_text("not json")
    assert after_play.read_state(state) == {}


def test_cli_prints_the_summary_and_requires_a_drop_folder_source(tmp_path, monkeypatch, capsys):
    config, folder = inputs(tmp_path)
    dropped(folder, [scan("win1", FINISHED, [listing(2, 1, 80)])])
    (tmp_path / "addon").mkdir()
    (tmp_path / "addon/README.md").write_text(README, encoding="utf-8")
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(cli, "read_sources", lambda *args: [config])
    original = after_play.run
    monkeypatch.setattr(after_play, "run", lambda *args: original(*args, now=NOW))
    monkeypatch.setattr(sys, "argv", ["brownstone", "after-play"])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 0
    out = capsys.readouterr().out
    assert out.startswith("After-play check for my-scans") and "newly eligible scan: win1" in out
    assert (tmp_path / "work/after-play/state.json").exists()
    monkeypatch.setattr(cli, "read_sources", lambda *args: [config | {"drop_folder": None}])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2 and "drop_folder" in capsys.readouterr().err
