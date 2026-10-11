"""The shared loader preserves snapshot, source and every market predicate."""
from datetime import UTC, datetime

import pytest
from test_metrics import import_records
from test_scan_v3 import rich

from brownstone.markets import MARKET_KEYS
from brownstone.today_loading import load_today
from brownstone.today_settings import TodaySettings


@pytest.mark.parametrize('key', ['source_id', *MARKET_KEYS])
def test_shared_loader_never_borrows_a_snapshot(tmp_path, key):
    config = import_records(tmp_path, rich())
    now = datetime.now(UTC)
    manifest, arguments = load_today(config, [], TodaySettings(), {}, now)
    assert manifest is not None and arguments['now'] is now
    assert arguments['snapshot']['snapshot_id'] == 'my-scans:rich'
    assert arguments['market'] is config
    assert load_today({**config, key: 'other'}, [], TodaySettings(), {}, now) == (None, None)
