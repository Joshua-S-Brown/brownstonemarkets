"""Scoped Today evidence reads from imported synthetic scans only."""
import duckdb
import pytest
from test_metrics import import_records
from test_scan_v3 import rich

from brownstone.today_data import read_today_evidence


def test_today_reads_base_identity_and_observed_vendor_price_only(tmp_path):
    record = rich()
    record['items'][1]['vendor_sell_copper'] = 80
    config = import_records(tmp_path, record)
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb'), read_only=True) as db:
        observations, ladders, metrics, vendors = read_today_evidence(db, config, 'my-scans:rich', [2589, 6538])
    assert observations == {2589: {'min_buyout': 36, 'market_value': 36}}
    assert ladders == {2589: [(20, 701, 36)]}
    assert metrics[2589]['units'] == 30 and metrics[2589]['listings'] == 2  # no-buyout counts remain
    assert vendors == {2589: 80}
    assert 6538 not in metrics  # unresolved and suffix identities never fill catalog prices


@pytest.mark.parametrize('key,value', [('source_id', 'other'), ('environment', 'beta'), ('region', 'eu'),
                                      ('scope', 'region'), ('realm', 'other'), ('server_type', 'pvp'),
                                      ('faction', 'horde'), ('game_version', 'classic'), ('market_id', 'other')])
def test_today_reads_every_source_market_key(tmp_path, key, value):
    config = import_records(tmp_path, rich())
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb'), read_only=True) as db:
        assert read_today_evidence(db, {**config, key: value}, 'my-scans:rich', [2589]) == ({}, None, None, {})
        assert read_today_evidence(db, config, 'other-snapshot', [2589]) == ({}, None, None, {})


def test_tsm_depth_unavailable_and_missing_scan(tmp_path):
    config = import_records(tmp_path, rich())
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb'), read_only=True) as db:
        evidence = read_today_evidence(db, {**config, 'provider': 'tsm'}, 'my-scans:rich', [2589])
        assert evidence[0][2589]['min_buyout'] == 36 and evidence[1:] == (None, None, {})
