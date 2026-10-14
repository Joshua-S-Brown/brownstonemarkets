"""Offline target storage and scoped scan evidence."""
from datetime import UTC, datetime, timedelta

import duckdb
import pytest
from test_metrics import import_records
from test_scan_v3 import rich
from test_scans import FINISHED, listing, scan

from brownstone.markets import MARKET_KEYS
from brownstone.watchlist import (
    Entry,
    build_watchlist,
    catalog_names,
    known_names,
    read_watchlist,
    save_entries,
    watchlist_path,
)


@pytest.mark.parametrize('raw', ['bad json', '{}', '[{"item_id":1}]', '[{"item_id":true,"buy_copper":1}]'])
def test_invalid_file_preserved_and_save_refused(tmp_path, raw):
    path = watchlist_path(tmp_path, 'one')
    path.write_text(raw)
    with pytest.raises((ValueError, TypeError)):
        save_entries(path, [Entry(1, 1)])
    assert path.read_text() == raw


@pytest.mark.parametrize('hours', [0, -25, 1])
def test_hits_exact_targets_missing_and_freshness(hours):
    now = datetime.now(UTC)
    snapshot = {'collected_at': (now + timedelta(hours=hours)).isoformat()}
    result = build_watchlist([Entry(1, 11, 11), Entry(2, 1, 1), Entry(3, 10, 12)],
                             {1: {'min_buyout': 11, 'units': 6}, 2: {'min_buyout': 0},
                              3: {'min_buyout': 11}}, snapshot, now, 24, {1: 2})
    row = result['rows'][0]
    assert row['buy_hit'] and row['sell_hit'] and row['buy_units'] == 2
    assert result['freshness']['stale'] == (hours != 0)
    assert ('stale' in row['buy_state']) == (hours != 0)
    assert result['rows'][1]['price'] is None and not result['rows'][1]['buy_hit']
    assert result['rows'][1]['sell_state'].startswith('not listed')
    assert result['rows'][2]['buy_state'].startswith('not hit')
    empty = build_watchlist([Entry(1, 1, 1)], {}, None, now, 24)['rows'][0]
    assert empty['buy_state'] == empty['sell_state'] == 'no snapshot'


def test_buy_units_rounding_zero_buyouts_and_newest_snapshot(tmp_path):
    config = import_records(tmp_path, scan('old', FINISHED - 3600, [listing(1, 99, 99)]),
                            scan('new', FINISHED, [listing(1, 2, 21), listing(1, 3, 33),
                                                   listing(1, 4, 48), listing(1, 5, 0)]))
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb'), read_only=True) as db:
        row = read_watchlist(db, config, [Entry(1, 11, 11)], datetime.fromtimestamp(FINISHED, UTC))['rows'][0]
    assert row['price'] == 11 and row['units'] == 14 and row['buy_units'] == 5
    assert row['buy_hit'] and row['sell_hit']


@pytest.mark.parametrize('key', ['source_id', *MARKET_KEYS])
def test_full_scope_isolation(tmp_path, key):
    config = import_records(tmp_path, scan('one', FINISHED, [listing(1, 2, 20)]))
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb'), read_only=True) as db:
        other = {**config, key: 'other'}
        row = read_watchlist(db, other, [Entry(1, 10)], datetime.fromtimestamp(FINISHED, UTC))['rows'][0]
        assert row['buy_state'] == 'no snapshot' and not row['buy_hit']
        assert known_names(db, other, []) == {}


def test_variant_excluded_explicit_base_units(tmp_path):
    config = import_records(tmp_path, rich())
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb'), read_only=True) as db:
        rows = read_watchlist(db, config, [Entry(2589, 36), Entry(15210, 999999)],
                              datetime.fromtimestamp(FINISHED, UTC))['rows']
    assert rows[0]['buy_hit'] and rows[0]['buy_units'] == 20 and rows[0]['units'] == 30
    assert rows[1]['price'] is None and not rows[1]['buy_hit']


def test_atomic_replace_failure_preserves_saved_file(tmp_path, monkeypatch):
    from pathlib import Path

    path = watchlist_path(tmp_path, 'one')
    save_entries(path, [Entry(1, 10)])
    original = path.read_bytes()
    def fail(*args):
        raise OSError('replace failed')
    monkeypatch.setattr(Path, 'replace', fail)
    with pytest.raises(OSError, match='replace failed'):
        save_entries(path, [Entry(2, 20)])
    assert path.read_bytes() == original


def test_picker_catalog_compatibility_and_own_observations(tmp_path):
    from test_today import catalog

    config = import_records(tmp_path, scan('one', FINISHED, [listing(1, 2, 20)]))
    c = catalog()
    c['game_version'] = config['game_version']
    c['rules_version'] = config['rules_version']
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb'), read_only=True) as db:
        assert known_names(db, config, [c])[3] == c['items_by_id'][3]['name']
        # A catalog item without a name is never offered (and never breaks the sorted picker).
        c['items_by_id'][99] = {'name': None}
        assert 99 not in catalog_names([c], config)
        c['rules_version'] = 'incompatible'
        assert 3 not in known_names(db, config, [c])


def test_picker_knows_unpriced_scan_names_but_never_variant_names(tmp_path):
    record = rich(status='stopped')
    config = import_records(tmp_path, record)
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb'), read_only=True) as db:
        names = known_names(db, config, [])
    assert names[2589] == 'Linen Cloth'
    assert 6538 not in names
