"""The one-command quality gates: order, stop at the first failure, summary and document headroom."""
import subprocess

import pytest

from brownstone import cli, gates

PYTEST_TAIL = ("Required test coverage of 88.0% reached. Total coverage: 89.31%\n"
               "1885 passed, 1 skipped in 61.20s (0:01:01)\n")


def runner(codes, output=PYTEST_TAIL):
    calls = []

    def run(command):
        calls.append(command)
        return subprocess.CompletedProcess(command, codes[len(calls) - 1], output, "")
    return run, calls


def test_gates_run_lint_then_parallel_tests_and_summarise():
    run, calls = runner([0, 0, 0])
    lines, code = gates.run_gates(runner=run, python="py")
    assert code == 0
    assert [call[:3] for call in calls] == [["py", "-m", "ruff"], ["py", "-m", "mypy"], ["py", "-m", "pytest"]]
    assert {"-n", "auto", "--cov"} <= set(calls[2])
    assert lines[2].startswith("pytest ok") and lines[2].endswith("1885 passed, 1 skipped; coverage 89.31%")
    assert lines[3].startswith("total")
    assert [line.split(":")[0] for line in lines[4:]] == ["docs   requirements.md", "docs   design.md"]


def test_gates_stop_at_the_first_failure_and_show_its_output():
    run, calls = runner([1], "E501 line too long\n")
    lines, code = gates.run_gates(runner=run, python="py")
    assert code == 1 and len(calls) == 1
    assert lines[0] == "E501 line too long"
    assert lines[2].startswith("ruff   FAILED")


def test_lint_only_skips_the_tests():
    run, calls = runner([0, 0])
    assert gates.run_gates(lint_only=True, runner=run, python="py")[1] == 0
    assert [call[2] for call in calls] == ["ruff", "mypy"]


def test_suite_summary_reads_counts_and_coverage():
    assert gates.suite_summary("3 failed, 2 passed in 1.0s\n") == "3 failed, 2 passed"
    assert gates.suite_summary("=== 4 passed in 0.5s ===\nTotal coverage: 90.00%") == "4 passed; coverage 90.00%"
    assert gates.suite_summary("collection error") == "no test summary found"


def test_doc_headroom_reports_bytes_left(tmp_path, monkeypatch):
    for name in gates.DOC_SIZE_LIMITS:
        (tmp_path / name).parent.mkdir(exist_ok=True)
        (tmp_path / name).write_bytes(b"x\r\n" * 50)  # A Windows checkout: CRLF counts as the committed LF.
    monkeypatch.setattr(gates, "DOC_SIZE_LIMITS", {"docs/requirements.md": 1_100})
    assert gates.doc_headroom(tmp_path) == ["requirements.md: 100 of 1,100 bytes (1,000 left)"]


def test_cli_gates_prints_the_summary_and_exits_with_its_code(monkeypatch, capsys):
    monkeypatch.setattr(gates, "run_gates", lambda lint_only: (["ruff   ok", f"lint_only={lint_only}"], 3))
    monkeypatch.setattr("sys.argv", ["brownstone", "gates", "--lint-only"])
    with pytest.raises(SystemExit) as exit_:
        cli.main()
    assert exit_.value.code == 3
    assert capsys.readouterr().out == "ruff   ok\nlint_only=True\n"
