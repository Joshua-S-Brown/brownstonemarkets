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


def make_source(data_dir, **overrides):
    """A valid configured source for tests; override any field (market fields included)."""
    from brownstone.config import build_source
    shared = dict(data_dir=data_dir, max_age_hours=24, auction_cut=.05, min_discount=.2, top_n=20)
    entry = dict(source_id="test", provider="tsm", source_url="https://example.com/items.csv",
                 game_version="retail", region="us", scope="house", realm="area-52")
    return build_source(shared, {**entry, **overrides})
