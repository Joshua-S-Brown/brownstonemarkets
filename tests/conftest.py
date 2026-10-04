"""Use ordinary directories, compatible with the desktop filesystem sandbox."""
import shutil
import uuid
from pathlib import Path

import pytest


@pytest.fixture
def tmp_path():
    path = Path(__file__).resolve().parents[1] / "work" / "test-runs" / uuid.uuid4().hex
    path.mkdir(parents=True)
    yield path
    shutil.rmtree(path)
