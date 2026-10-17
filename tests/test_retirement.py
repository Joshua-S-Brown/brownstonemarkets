"""Surviving entry points work without the retired display frameworks."""
import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest

from brownstone.gates import DOC_SIZE_LIMITS, doc_size

ROOT = Path(__file__).resolve().parents[1]
BLOCK_RETIRED = '''
import importlib.abc
import runpy
import sys

class NoRetiredFramework(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('streamlit', 'nicegui'):
            raise ImportError('Display framework is retired')

sys.meta_path.insert(0, NoRetiredFramework())
'''


def test_app_launcher_and_cli_import_without_retired_frameworks():
    result = subprocess.run([sys.executable, '-c', BLOCK_RETIRED + '''
import brownstone_app
import launch_app
import brownstone.cli
assert launch_app.code_fingerprint()
assert not any(n.split('.')[0] in ('streamlit', 'nicegui') for n in sys.modules)
'''], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('command', [[], ['recipes'], ['beta-report'], ['close-story']])
def test_module_cli_commands_without_retired_frameworks(command):
    code = (BLOCK_RETIRED + "sys.argv = ['brownstone', *sys.argv[1:]]\n"
            "runpy.run_module('brownstone', run_name='__main__')")
    result = subprocess.run([sys.executable, '-c', code, *command, '--help'], cwd=ROOT,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert 'usage:' in result.stdout


def test_retired_artifacts_and_dependency_are_absent():
    assert not (ROOT / 'app.py').exists()
    assert not (ROOT / 'launch.py').exists()
    assert not list(ROOT.glob('Open Old Streamlit App.*'))
    sources = [ROOT / 'brownstone_app.py', ROOT / 'launch_app.py',
               *ROOT.glob('brownstone/*.py'), *ROOT.glob('views/*.py')]
    assert all('streamlit' not in p.read_text(encoding='utf-8').lower() for p in sources)
    assert 'streamlit' not in (ROOT / 'pyproject.toml').read_text(encoding='utf-8').lower()
    assert 'streamlit==' not in (ROOT / 'requirements.lock.txt').read_text(encoding='utf-8').lower()

    for path in ROOT.rglob('*.py'):
        # Ruff's exclusions: hidden folders (.venv, .claude worktrees), work, data and node_modules.
        parts = path.relative_to(ROOT).parts
        if any(part.startswith('.') or part in ('work', 'data', 'node_modules') for part in parts):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node, ast.Import):
                assert all(a.name.split('.')[0] != 'nicegui' for a in node.names), path
            elif isinstance(node, ast.ImportFrom):
                assert (node.module or '').split('.')[0] != 'nicegui', path


def test_document_size_and_rule_id_inventory():
    requirements = ROOT / 'docs/requirements.md'
    # The ceilings live in brownstone/gates.py, which also prints the headroom left under them.
    for name, limit in DOC_SIZE_LIMITS.items():
        assert doc_size(ROOT / name) <= limit, name
    expected = {f'{prefix}-{i:02}' for prefix, numbers in {
        'DATA': [1, 2, 3, 4, 5, 8], 'ADDON': range(1, 14), 'CRAFT': range(1, 14),
        'MONEY': [1, 2], 'OPS': [1, 2, 3], 'UI': range(1, 19),
    }.items() for i in numbers}
    actual = set(re.findall(r'\b(?:DATA|ADDON|CRAFT|MONEY|UI|OPS)-\d+\b', requirements.read_text(encoding='utf-8')))
    assert actual == expected
