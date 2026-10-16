"""UI-17 offline contracts: stored facts, scope, identity, gaps and whole-listing supply."""
from datetime import timedelta

import duckdb
import pytest
from test_flood_signals import connection, fixture
from test_market_explorer import explorer_fixture
from test_scans import FINISHED, NOW, listing, scan

from brownstone import item_history as ih
from brownstone import market_explorer as me
from brownstone.markets import MARKET_KEYS
from brownstone.today import TODAY_VERSION, build_today
from brownstone.today_loading import load_today
from brownstone.today_settings import TodaySettings


def test_gaps_null_price_eligibility_stored_metrics_and_dedup(tmp_path):
    records = [scan('priced', FINISHED - 5 * 3600, [listing(1, 3, 302)]),
               scan('absent', FINISHED - 4 * 3600, [listing(2, 1, 1)]),
               scan('no-buyout', FINISHED - 3600, [listing(1, 7, 0)]),
               scan('partial', FINISHED - 60, [listing(1, 1, 1)], reported=2),
               scan('unpriced', FINISHED, [listing(1, 1, 1)])]
    config = fixture(tmp_path, records)
    with connection(config) as db:
        db.execute("UPDATE addon_scans SET priced=false WHERE scan_id='unpriced'")
        db.execute("UPDATE scan_metrics SET min_buyout=123, unit_buyout_p25=456 WHERE scan_id='priced'")
        db.execute("SET TimeZone='Pacific/Auckland'")
        result = ih.history(db, config, 1)
        assert [s['scan_id'] for s in result['scans']] == ['no-buyout', 'absent', 'priced']
        points = result['points']
        assert [p['scan_id'] for p in points] == ['priced', 'absent', 'no-buyout']
        assert points[0]['metrics']['min_buyout'] == 123
        assert points[0]['metrics']['market_value'] == 456
        assert points[0]['metrics']['units'] == 3  # Deduplicated on import.
        assert points[1]['metrics'] is None
        assert points[2]['metrics']['min_buyout'] is None
        assert points[2]['metrics']['market_value'] is None
        assert points[2]['metrics']['units'] == 7
        assert points[0]['finished_at'].utcoffset() == timedelta(0)
        assert points[2]['finished_at'] - points[1]['finished_at'] == timedelta(hours=3)
        for invalid in ['partial', 'unpriced', 'foreign']:
            with pytest.raises(ValueError, match='eligible scan'):
                ih.ladder(db, config, 1, result, invalid, NOW)
        missing = ih.ladder(db, config, 1, result, 'absent', NOW)
        assert missing['rows'] == [] and 'absent' in missing['note']


def test_ladder_grouping_ceiling_cumulative_no_buyout_and_freshness(tmp_path):
    config = fixture(tmp_path, [scan('one', FINISHED, [listing(1, 3, 302), listing(1, 2, 202),
                    listing(1, 5, 1000), listing(1, 4, 0), listing(2, 1, 1)])])
    with connection(config) as db:
        evidence = ih.history(db, config, 1)
        assert len(evidence['points']) == 1
        result = ih.ladder(db, config, 1, evidence, 'one', NOW)
        assert result['rows'] == [dict(price_copper=101, listings=2, units=5, cumulative_units=5),
                                  dict(price_copper=200, listings=1, units=5, cumulative_units=10)]
        assert (result['no_buyout_listings'], result['no_buyout_units']) == (1, 4)
        assert not result['freshness']['stale']
        for now in [NOW + timedelta(days=2), NOW - timedelta(hours=2)]:
            assert ih.ladder(db, config, 1, evidence, 'one', now)['freshness']['stale']
        db.execute('UPDATE scan_listings SET buyout=0, unit_buyout_ceil=NULL')
        assert ih.ladder(db, config, 1, evidence, 'one', NOW)['rows'] == []


@pytest.mark.parametrize('key', ['source_id', *MARKET_KEYS])
def test_every_scope_field_and_metrics_version_on_both_reads(tmp_path, key):
    config = fixture(tmp_path, [scan('one', FINISHED, [listing(1, 3, 300)])])
    with connection(config) as db:
        assert ih.history(db, config | {key: 'foreign'}, 1)['scans'] == []
        for table in ['scan_metrics', 'scan_listings']:
            columns = [r[1] for r in db.execute(f"PRAGMA table_info('{table}')").fetchall()]
            fields = ', '.join('?' if c == key else "metric_key || '-foreign'" if c == 'metric_key'
                               else 'listing_index + 100' if c == 'listing_index' else c for c in columns)
            db.execute(f'INSERT INTO {table} SELECT {fields} FROM {table}', ['foreign'])
        evidence = ih.history(db, config, 1)
        assert evidence['points'][0]['metrics']['units'] == 3
        assert ih.ladder(db, config, 1, evidence, 'one', NOW)['rows'][0]['units'] == 3
        db.execute('UPDATE scan_metrics SET metrics_version=-1')
        assert ih.history(db, config, 1)['points'][0]['metrics'] is None
        assert ih.ladder(db, config, 1, evidence, 'one', NOW)['rows'] == []


def test_base_legacy_compatibility_variants_unresolved_and_absent_newest(tmp_path):
    config = fixture(tmp_path, [scan('legacy', FINISHED - 3600, [listing(1, 2, 200)]),
                               scan('base', FINISHED, [listing(1, 3, 600)])])
    with connection(config) as db:
        for table in ['scan_metrics', 'scan_listings']:
            db.execute(f"UPDATE {table} SET variant_state='base' WHERE scan_id='base'")
        evidence = ih.history(db, config, 1)
        assert all(p['metrics'] is not None for p in evidence['points'])
        assert ih.ladder(db, config, 1, evidence, 'legacy', NOW)['rows'][0]['units'] == 2
        for table in ['scan_metrics', 'scan_listings']:
            columns = [r[1] for r in db.execute(f"PRAGMA table_info('{table}')").fetchall()]
            fields = ', '.join("metric_key || '-variant'" if c == 'metric_key' else
                               "'variant'" if c == 'variant_state' else "'suffix:-1'" if c == 'variant_id'
                               else '999' if c == 'quantity' else 'listing_index + 100' if c == 'listing_index'
                               else c for c in columns)
            db.execute(f"INSERT INTO {table} SELECT {fields} FROM {table} WHERE scan_id='base'")
        evidence = ih.history(db, config, 1)
        assert evidence['other_identities'] == 1
        assert evidence['points'][0]['metrics'] is None  # Legacy might pool suffixes.
        assert evidence['points'][1]['metrics']['units'] == 3
        assert ih.ladder(db, config, 1, evidence, 'base', NOW)['rows'][0]['units'] == 3
        assert ih.ladder(db, config, 1, evidence, 'legacy', NOW)['rows'] == []
        db.execute("UPDATE scan_metrics SET variant_state='unresolved', variant_id=NULL WHERE scan_id='base'")
        assert all(p['metrics'] is None for p in ih.history(db, config, 1)['points'])
        db.execute("DELETE FROM scan_metrics WHERE scan_id='base'")
        evidence = ih.history(db, config, 1)
        assert evidence['points'][0]['metrics']['units'] == 2
        assert evidence['points'][1]['metrics'] is None


def test_exact_base_retained_with_newer_legacy_scans(tmp_path):
    config = fixture(tmp_path)
    with connection(config) as db:
        db.execute("UPDATE scan_metrics SET variant_state='base' WHERE scan_id='s0'")
        # Exact base is charted independently of legacy compatibility.
        assert ih.history(db, config, 1)['points'][0]['metrics']['variant_state'] == 'base'


def test_read_only_wrappers_empty_tsm_and_unchanged_item_today_outputs(tmp_path):
    config, catalog = explorer_fixture(tmp_path)
    database = config['data_dir'] / 'brownstone.duckdb'
    before_bytes = database.read_bytes()
    before = me.load_explorer(config, [catalog], NOW)
    page = me.item_page(before, 2996)
    _, args = load_today(config, [catalog], TodaySettings(), {}, NOW)
    today = build_today(**args)
    evidence = ih.load_history(config, 2996)
    assert ih.load_ladder(config, 2996, evidence, 'scan-1')['rows']
    assert database.read_bytes() == before_bytes
    after = me.load_explorer(config, [catalog], NOW)
    assert before == after and page == me.item_page(after, 2996)
    _, args_after = load_today(config, [catalog], TodaySettings(), {}, NOW)
    assert build_today(**args_after) == today
    assert TODAY_VERSION == 14
    with duckdb.connect(str(database), read_only=True) as db:
        assert 'TSM' in ih.history(db, config | {'provider': 'tsm'}, 2996)['note']
        assert 'No eligible' in ih.history(db, config | {'source_id': 'other'}, 2996)['note']


def test_zoom_cheapest_95_percent_keeps_table_outliers():
    rows = [dict(price_copper=p, cumulative_units=c) for p, c in [(20, 90), (25, 96), (500000, 100)]]
    assert ih.zoom_end(rows) == 25
    assert ih.zoom_end(rows, 100) == 500000
    assert ih.zoom_end([]) is None
    assert len(rows) == 3
