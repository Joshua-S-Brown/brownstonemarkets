"""Use ordinary directories, compatible with the desktop filesystem sandbox."""
import shutil
import sys
import uuid
from functools import partial
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def app_test_timeout():
    """Allow covered offline app runs to finish; preserve explicitly supplied timeouts."""
    # A separate patch context preserves test monkeypatch/tmp_path teardown order.
    with pytest.MonkeyPatch.context() as patch:
        module = sys.modules.get('streamlit.testing.v1')
        if module is not None:
            patch.setattr(module.AppTest, 'from_file', partial(module.AppTest.from_file, default_timeout=10))
        yield


@pytest.fixture
def tmp_path():
    path = Path(__file__).resolve().parents[1] / "work" / "test-runs" / uuid.uuid4().hex
    path.mkdir(parents=True)
    yield path
    shutil.rmtree(path)


def make_source(data_dir, **overrides):
    """A valid configured source for tests; override any field (market fields included)."""
    from brownstone.config import build_source
    shared = dict(data_dir=data_dir, max_age_hours=24, auction_cut=.05, min_discount=.2, top_n=20)
    entry = dict(source_id="test", provider="tsm", source_url="https://example.com/items.csv",
                 game_version="retail", region="us", scope="house", realm="area-52")
    return build_source(shared, {**entry, **overrides})


def pytest_addoption(parser):
    # Only register the main-file option. NiceGUI's fixtures are local to tests/ui_trial;
    # importing its plugin globally would reset application state in unrelated tests.
    parser.addini('main_file', 'NiceGUI main-app entry point', default='nicegui_app.py')
