"""Surviving entry points work even when Streamlit cannot be imported."""
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BLOCK_STREAMLIT = '''
import importlib.abc
import runpy
import sys

class NoStreamlit(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] == 'streamlit':
            raise ImportError('Streamlit is retired')

sys.meta_path.insert(0, NoStreamlit())
'''


def test_app_launcher_and_cli_import_without_streamlit():
    result = subprocess.run([sys.executable, '-c', BLOCK_STREAMLIT + '''
import nicegui_app
import launch_nicegui
import brownstone.cli
assert launch_nicegui.code_fingerprint()
assert not any(n.split('.')[0] == 'streamlit' for n in sys.modules)
'''], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('command', [[], ['recipes'], ['beta-report']])
def test_module_cli_commands_without_streamlit(command):
    code = (BLOCK_STREAMLIT + "sys.argv = ['brownstone', *sys.argv[1:]]\n"
            "runpy.run_module('brownstone', run_name='__main__')")
    result = subprocess.run([sys.executable, '-c', code, *command, '--help'], cwd=ROOT,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert 'usage:' in result.stdout


def test_retired_artifacts_and_dependency_are_absent():
    assert not (ROOT / 'app.py').exists()
    assert not (ROOT / 'launch.py').exists()
    assert not list(ROOT.glob('Open Old Streamlit App.*'))
    sources = [ROOT / 'nicegui_app.py', ROOT / 'launch_nicegui.py',
               *ROOT.glob('brownstone/*.py'), *ROOT.glob('views/*.py')]
    assert all('streamlit' not in p.read_text().lower() for p in sources)
    assert 'streamlit' not in (ROOT / 'pyproject.toml').read_text().lower()
    assert 'streamlit==' not in (ROOT / 'requirements.lock.txt').read_text().lower()


def test_document_size_and_rule_id_inventory():
    requirements = ROOT / 'docs/requirements.md'
    # Allow STORY-078 composition/contracts without rewriting unrelated rules.
    assert requirements.stat().st_size <= 101_000
    assert (ROOT / 'docs/design.md').stat().st_size <= 51_000
    expected = {f'{prefix}-{i:02}' for prefix, numbers in {
        'DATA': [1, 2, 3, 4, 5, 8], 'ADDON': range(1, 14), 'CRAFT': range(1, 14),
        'MONEY': [1, 2], 'OPS': [1, 2, 3], 'UI': range(1, 14),
    }.items() for i in numbers}
    actual = set(re.findall(r'\b(?:DATA|ADDON|CRAFT|MONEY|UI|OPS)-\d+\b', requirements.read_text()))
    assert actual == expected
