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


def test_loader_passes_stock_holdings_once_and_build_never_reads(tmp_path, monkeypatch):
    from unittest.mock import Mock

    from test_scans import NOW
    from test_stock import fixture

    from brownstone import character_snapshots, team_holdings
    from brownstone.today import build_today

    config = fixture(tmp_path)
    expected = team_holdings.holdings(character_snapshots.latest_data(config), NOW)
    reader = Mock(wraps=character_snapshots.latest_data)
    monkeypatch.setattr(character_snapshots, 'latest_data', reader)
    _, other_page = load_today(config, [], TodaySettings(1000, 1, 'fixed'), {}, NOW)
    assert reader.call_count == 0 and other_page['holdings_data'] is None  # Team and Market skip the read
    _, arguments = load_today(config, [], TodaySettings(1000, 1, 'fixed'), {}, NOW, holdings=True)
    assert reader.call_count == 1
    assert arguments['holdings_data'] == expected and arguments['holdings_warning'] is None
    monkeypatch.setattr(character_snapshots, 'latest_data', Mock(side_effect=AssertionError('pure build')))
    monkeypatch.setattr(team_holdings, 'holdings', Mock(side_effect=AssertionError('pure build')))
    result = build_today(**arguments)
    assert result['holdings_captures'] == expected[2]


def test_unreadable_holdings_plan_without_them_and_explain(tmp_path, monkeypatch):
    from unittest.mock import Mock

    from test_scans import NOW
    from test_stock import fixture

    from brownstone import character_snapshots
    from brownstone.today import build_today

    config = fixture(tmp_path)
    monkeypatch.setattr(character_snapshots, 'latest_data', Mock(side_effect=ValueError('bad capture')))
    _, arguments = load_today(config, [], TodaySettings(1000, 1, 'fixed'), {}, NOW, holdings=True)
    assert arguments['holdings_data'] is None
    result = build_today(**arguments)
    assert result['holdings_warning'] == 'Unable to read held items: bad capture. Planning as if nothing is held.'
    assert 'holdings_captures' not in result
