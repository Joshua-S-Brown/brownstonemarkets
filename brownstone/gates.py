"""The project's quality gates as one command: ruff, mypy, then the parallel test suite with coverage.

Each gate runs with the calling interpreter, stops at the first failure and prints a short summary,
plus how many bytes the size-guarded documents have left. Developer tooling only, never imported by the app.
"""
import re
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Byte ceilings checked by tests/test_retirement.py. They grew only for UI-17 and the UI-18 web app
# decision, each rounded up to the next 100 bytes. Shrink a document rather than raise its ceiling.
DOC_SIZE_LIMITS = {"docs/requirements.md": 123_100, "docs/design.md": 57_700}
LINT = (("ruff", ("-m", "ruff", "check", ".")), ("mypy", ("-m", "mypy")))
TESTS = ("pytest", ("-m", "pytest", "-p", "no:cacheprovider", "-n", "auto", "--cov", "-q", "-ra"))
RESULT = re.compile(r"^=* ?(\d+ (?:passed|failed).*?) in [\d.]+s", re.MULTILINE)
COVERAGE = re.compile(r"Total coverage: ([\d.]+%)")

Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def _run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")


def doc_size(path: Path) -> int:
    """Bytes as committed: a Windows checkout's CRLF line endings don't count against the ceiling."""
    return len(path.read_bytes().replace(b"\r\n", b"\n"))


def doc_headroom(root: Path = ROOT) -> list[str]:
    """One line per size-guarded document: bytes used, ceiling and what is left."""
    lines = []
    for name, limit in DOC_SIZE_LIMITS.items():
        size = doc_size(root / name)
        lines.append(f"{Path(name).name}: {size:,} of {limit:,} bytes ({limit - size:,} left)")
    return lines


def suite_summary(output: str) -> str:
    """Pytest's final counts and the combined coverage total, from its quiet output."""
    results, coverage = RESULT.findall(output), COVERAGE.findall(output)
    counts = results[-1] if results else "no test summary found"
    return f"{counts}; coverage {coverage[-1]}" if coverage else counts


def run_gates(lint_only: bool = False, runner: Runner = _run, python: str = sys.executable) -> tuple[list[str], int]:
    """Run each gate in turn; return the summary lines and an exit code (the first failing gate's)."""
    lines: list[str] = []
    started = time.monotonic()
    for name, args in LINT if lint_only else (*LINT, TESTS):
        began = time.monotonic()
        result = runner([python, *args])
        output = result.stdout + result.stderr
        detail = suite_summary(output) if name == "pytest" else ""
        status = "ok" if result.returncode == 0 else "FAILED"
        lines.append(f"{name:<7}{status:<7}{time.monotonic() - began:6.1f}s  {detail}".rstrip())
        if result.returncode:
            return [output.rstrip(), "", *lines, *_footer(started)], result.returncode
    return [*lines, *_footer(started)], 0


def _footer(started: float) -> list[str]:
    return [f"{'total':<14}{time.monotonic() - started:6.1f}s", *(f"docs   {line}" for line in doc_headroom())]
