"""Run the shipped Windows helper on disposable offline files when PowerShell exists."""
import shutil
import subprocess
from pathlib import Path

import pytest

POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable; Windows CI runs the drop-script tests")
def test_windows_drop_script_contract_and_copy_guards(tmp_path):
    script = Path(__file__).resolve().parents[1] / "tools/windows/test-drop-scans.ps1"
    result = subprocess.run([str(POWERSHELL), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
                             "-TestRoot", str(tmp_path / "powershell")], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS: shared names" in result.stdout
