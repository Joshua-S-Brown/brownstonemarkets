"""Market context keeps source, market, snapshot and item identity without affecting expectations."""
import duckdb
import pytest
from test_metrics import import_records
from test_scans import FINISHED, listing, scan

from brownstone.markets import MARKET_KEYS
from brownstone.today_data import read_skillup_market


def test_units_include_no_buyouts_and_missing_prices_stay_missing(tmp_path):
    record = scan('one', FINISHED, [listing(1, 2, 21), listing(1, 4, 0), listing(2, 3, 0)])
    config = import_records(tmp_path, record)
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb'), read_only=True) as db:
        rows = read_skillup_market(db, config, 'my-scans:one', [1, 2, 3])
    assert rows == {1: {'units': 6, 'min_buyout': 11}, 2: {'units': 3, 'min_buyout': None},
                    3: {'units': 0, 'min_buyout': None}}


@pytest.mark.parametrize('key', ['source_id', *MARKET_KEYS])
def test_full_scope_and_wrong_snapshot_never_join(tmp_path, key):
    config = import_records(tmp_path, scan('one', FINISHED, [listing(1, 2, 20)]))
    other = {**config, key: 'different'}
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb'), read_only=True) as db:
        unavailable = {1: {'units': None, 'units_note': 'no priced scan in this snapshot', 'min_buyout': None}}
        assert read_skillup_market(db, other, 'my-scans:one', [1]) == unavailable
        assert read_skillup_market(db, config, 'wrong-snapshot', [1]) == unavailable


def test_variant_and_unresolved_metrics_do_not_pool_into_base(tmp_path):
    from test_scan_v3 import rich
    config = import_records(tmp_path, rich())
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb'), read_only=True) as db:
        rows = read_skillup_market(db, config, 'my-scans:rich', [2589, 15210, 999999])
    assert rows[2589]['units'] == 30
    assert rows[15210] == rows[999999] == {'units': 0, 'min_buyout': None}
