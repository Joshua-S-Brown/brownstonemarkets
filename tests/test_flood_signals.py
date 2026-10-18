"""STORY-064: offline boundaries, scoped metrics, identities and honest evidence."""
from datetime import timedelta

import duckdb
import pytest
from test_scans import FINISHED, NOW, addon_source, listing, scan, write_scans

from brownstone import flood_signals as flood
from brownstone.markets import MARKET_KEYS
from brownstone.pipeline import import_scans


def overshoot(price, values, options):
    return flood.overshoot(price, list(enumerate(values)), options)


def fixture(tmp_path, records=None):
    config = addon_source(tmp_path / 'data', flood_min_days=1)
    records = records or [scan(f's{i}', FINISHED - (5 - i) * 3600,
                               [listing(1, 3, 300, 'Scan Name')] * (10 if i == 5 else 2)) for i in range(6)]
    path = write_scans(tmp_path / 'scans.lua', *records)
    import_scans(config, path, now=NOW)
    import_scans(config, path, now=NOW)  # Reimports must not multiply scan or listing evidence.
    return config


def connection(config):
    return duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb'))


@pytest.mark.parametrize(('listings', 'changed', 'pairs', 'label'), [
    (1, 0, 0, 'thin'), (2, 1, 2, 'thin'), (3, 1, 2, 'steady'), (9, 1, 2, 'steady'),
    (10, 1, 2, 'contested'), (10, 0, 2, 'steady'), (10, 4, 10, 'steady'),
    (10, 5, 10, 'contested'), (10, 0, 0, 'contested'), (3, 0, 0, 'steady'),
])
def test_crowding_labels_and_boundaries(listings, changed, pairs, label):
    assert flood.crowding(listings, {'changed': changed, 'pairs': pairs}, flood.settings({})) == label


@pytest.mark.parametrize(('price', 'label'), [(59, 'cheap'), (60, 'cheap'), (61, 'typical'),
                                            (149, 'typical'), (150, 'high'), (151, 'high'),
                                            (None, 'no buyout'), (0, 'no buyout')])
def test_overshoot_cutoff_boundaries(price, label):
    result = overshoot(price, [100] * 5, flood.settings({}))
    assert result['label'] == label and result['typical_copper'] == 100 and result['scans'] == 5
    assert result['ratio'] == ({'numerator': price, 'denominator': 100} if price else None)


def test_too_few_missing_prices_median_integer_units_and_custom_settings():
    options = flood.settings({})
    assert overshoot(1, [100] * 2 + [None, 0], options)['label'] == 'too few days'
    assert overshoot(60, [1, 100, 100, 100, 10000], options)['typical_copper'] == 100
    assert overshoot(60, [100, 101], options | {'flood_min_days': 2})['typical_copper'] == 100
    assert overshoot(70, [100] * 5, options | {'flood_cheap_percent': 70})['label'] == 'cheap'
    assert overshoot(140, [100] * 5, options | {'flood_high_percent': 140})['label'] == 'high'
    assert flood.crowding(5, {'changed': 1, 'pairs': 4}, options | {
        'flood_contested_listings': 5, 'flood_churn_percent': 25}) == 'contested'


def test_scoped_metrics_counts_stack_share_churn_dedup_and_freshness(tmp_path):
    config = fixture(tmp_path)
    with connection(config) as db:
        db.execute("UPDATE scan_metrics SET min_buyout=60 WHERE scan_id='s5'")
        result = flood.signals(db, config, [1], NOW)
        row = result['rows'][0]
        assert (row['listings'], row['units'], row['largest_stack_units']) == (10, 30, 3)
        assert row['churn'] == {'changed': 1, 'pairs': 5}
        assert row['crowding'] == 'steady'
        assert row['overshoot'] == {'label': 'cheap', 'typical_copper': 100, 'scans': 5, 'days': 1,
                                    'ratio': {'numerator': 60, 'denominator': 100}}
        assert not result['freshness']['stale']
        assert flood.signals(db, config, [1], NOW + timedelta(days=2))['freshness']['stale']
        assert flood.signals(db, config, [1], NOW - timedelta(hours=2))['freshness']['stale']
        assert flood.signals(db, config, [], NOW)['rows'] == []
        assert 'No eligible' in flood.signals(db, config | {'source_id': 'other'}, [1], NOW)['note']
        assert 'TSM' in flood.signals(db, config | {'provider': 'tsm'}, [1], NOW)['note']


@pytest.mark.parametrize('key', ['source_id', *MARKET_KEYS])
def test_each_scope_field_on_scans_metrics_and_names(tmp_path, key):
    config = fixture(tmp_path)
    with connection(config) as db:
        assert flood.signals(db, config | {key: 'other'}, [1], NOW)['rows'] == []
        columns = [r[1] for r in db.execute("PRAGMA table_info('scan_metrics')").fetchall()]
        fields = ', '.join('?' if col == key else "metric_key || '-foreign'" if col == 'metric_key' else
                           '99999' if col in ('listings', 'units', 'min_buyout') else col for col in columns)
        db.execute(f"INSERT INTO scan_metrics SELECT {fields} FROM scan_metrics", ['other'])
        assert flood.signals(db, config, [1], NOW)['rows'][0]['listings'] == 10
        db.execute(f"UPDATE scan_listings SET {key}='other'")
        db.execute(f"UPDATE market_snapshots SET {key}='other'")
        db.execute("DELETE FROM item_names")
        assert flood.signals(db, config, [1], NOW)['rows'][0]['item_name'] == 'Item 1'


def test_variants_unresolved_and_legacy_base_compatibility(tmp_path):
    config = fixture(tmp_path)
    with connection(config) as db:
        db.execute("UPDATE scan_metrics SET variant_state='base' WHERE scan_id='s5'")
        assert flood.signals(db, config, [1], NOW)['rows'][0]['overshoot']['scans'] == 5
        columns = [r[1] for r in db.execute("PRAGMA table_info('scan_metrics')").fetchall()]
        fields = ', '.join("metric_key || '-variant'" if c == 'metric_key' else
                           "'variant'" if c == 'variant_state' else "'suffix:-1'" if c == 'variant_id' else
                           '1' if c == 'listings' else c for c in columns)
        db.execute(f"INSERT INTO scan_metrics SELECT {fields} FROM scan_metrics WHERE scan_id='s5'")
        rows = flood.signals(db, config, [1], NOW)['rows']
        assert len(rows) == 2 and {r['listings'] for r in rows} == {1, 10}
        assert all(r['overshoot']['scans'] == 0 and r['churn']['pairs'] == 0 for r in rows)
        db.execute("UPDATE scan_metrics SET variant_state='unresolved', variant_id=NULL WHERE scan_id='s5'")
        # Distinct metric keys in this synthetic test; real storage has one row per identity.
        assert all(r['overshoot']['scans'] == 0 for r in flood.signals(db, config, [1], NOW)['rows'])
        db.execute("DELETE FROM scan_metrics WHERE metric_key LIKE '%-variant'")
        db.execute("UPDATE scan_metrics SET variant_state='base' WHERE scan_id != 's5'")
        db.execute("UPDATE scan_metrics SET variant_state=NULL WHERE scan_id='s5'")
        assert flood.signals(db, config, [1], NOW)['rows'][0]['overshoot']['scans'] == 5
        db.execute(f"INSERT INTO scan_metrics SELECT {fields} FROM scan_metrics WHERE scan_id='s0'")
        assert flood.signals(db, config, [1], NOW)['rows'][0]['overshoot']['scans'] == 4


def test_window_newest_exclusion_gap_boundary_pair_limit_and_eligibility(tmp_path):
    records = [scan(f's{i:02}', FINISHED - (13 - i) * 60, [listing(1, 1, 100 + i)]) for i in range(14)]
    records += [scan('boundary', FINISHED - 7 * 86400, [listing(1, 1, 200)]),
                scan('outside', FINISHED - 7 * 86400 - 1, [listing(1, 1, 99999)]),
                scan('partial', FINISHED - 5, [listing(1, 1, 1)], reported=2),
                scan('unpriced', FINISHED - 4, [listing(1, 1, 1)])]
    config = fixture(tmp_path, records)
    with connection(config) as db:
        db.execute("UPDATE addon_scans SET priced=false WHERE scan_id='unpriced'")
        row = flood.signals(db, config, [1], NOW)['rows'][0]
        assert row['overshoot']['scans'] == 14 and row['overshoot']['typical_copper'] == 153
        assert row['churn'] == {'changed': 10, 'pairs': 10}
        assert flood.signals(db, config | {'flood_window_days': 1}, [1], NOW)['rows'][0]['overshoot']['scans'] == 13
        db.execute("DELETE FROM addon_scans WHERE scan_id NOT IN ('s12','s13')")
        db.execute("UPDATE addon_scans SET finished_at=TIMESTAMPTZ '2026-11-04 18:20:00+00' "
                   "- INTERVAL 12 HOURS WHERE scan_id='s12'")
        assert flood.signals(db, config, [1], NOW)['rows'][0]['churn']['pairs'] == 1
        db.execute("UPDATE addon_scans SET finished_at=finished_at - INTERVAL 1 SECOND WHERE scan_id='s12'")
        assert flood.signals(db, config, [1], NOW)['rows'][0]['churn']['pairs'] == 0


def test_names_loaded_then_game_version_lookup_then_id(tmp_path):
    config = fixture(tmp_path)
    with connection(config) as db:
        db.execute("INSERT OR REPLACE INTO item_names VALUES (?, 1, 'Lookup', 1, now(), 'test')",
                   [config['game_version']])
        assert flood.signals(db, config, [1], NOW)['rows'][0]['item_name'] == 'Scan Name'
        db.execute("UPDATE market_snapshots SET item_name='Item 1'")
        assert flood.signals(db, config, [1], NOW)['rows'][0]['item_name'] == 'Scan Name'
        db.execute("UPDATE scan_listings SET item_name='' WHERE scan_id='s5'")
        assert flood.signals(db, config, [1], NOW)['rows'][0]['item_name'] == 'Lookup'
        db.execute("UPDATE item_names SET game_version='another' WHERE item_id=1 AND game_version='forever'")
        assert flood.signals(db, config, [1], NOW)['rows'][0]['item_name'] == 'Item 1'


def test_top_lists_roles_both_directions_limits_determinism_and_no_pooling(tmp_path):
    config = fixture(tmp_path)
    with connection(config) as db:
        result = flood.signals(db, config, [1], NOW)
    rows = []
    for item_id in range(1, 15):
        for variant in ('suffix:-1', 'suffix:-2'):
            rows.append(result['rows'][0] | {'item_id': item_id, 'variant_id': variant, 'variant_state': 'variant',
                        'listings': 10, 'units': 20, 'crowding': 'contested',
                        'overshoot': overshoot(50 if item_id % 2 else 200, [100] * 5, flood.settings({}))})
    catalog = {'items_by_id': dict.fromkeys(range(1, 14)),
               'recipes_by_id': {1: {'output_item_id': 1, 'inputs': [{'item_id': 2}]},
                                 2: {'output_item_id': 2, 'inputs': [{'item_id': 3}]}}}
    roles = flood.catalog_roles([catalog])
    assert roles[1] == 'output' and roles[2] == 'material / output' and roles[3] == 'material'
    lists = flood.top_lists(result | {'rows': rows}, roles)
    assert len(lists['contested']) == len(lists['overshoots']) == 10
    assert len({r['item_id'] for r in lists['overshoots']}) == 10
    assert lists['rows'] == rows  # Exact identities and every price/count remain in data.
    assert {r['overshoot']['label'] for r in lists['overshoots']} == {'cheap', 'high'}
    assert all(r['item_id'] != 14 and r['listings'] == 10 for r in lists['contested'])
    reversed_lists = flood.top_lists(result | {'rows': list(reversed(rows))}, roles)
    assert all(lists[key] == reversed_lists[key] for key in ('contested', 'overshoots'))
    thin = [r | {'listings': 2, 'crowding': 'thin'} for r in rows]
    assert flood.top_lists(result | {'rows': thin}, roles)['overshoots'] == []
    # Floors are per identity, inclusive, before selecting five; never sum sibling evidence.
    examples = [rows[0] | {'listings': 4, 'units': 100}, rows[0] | {'listings': 20, 'units': 9},
                rows[2] | {'listings': 5, 'units': 10,
                            'overshoot': overshoot(50, [100] * 5, flood.settings({}))},
                rows[2] | {'variant_id': 'larger', 'overshoot': overshoot(900, [100] * 5, flood.settings({}))}]
    selected = flood.top_lists(result | {'rows': examples}, roles)
    assert selected['rows'] == examples
    assert selected['overshoots'] == [examples[3] | {'role': roles[2]}]
    assert flood.top_lists(result | {'rows': examples[:3]}, roles)['overshoots'] == [examples[2] | {'role': roles[2]}]


@pytest.mark.parametrize(('key', 'value'), [('flood_window_days', 0), ('flood_min_days', True),
    ('flood_cheap_percent', 100), ('flood_high_percent', 100), ('flood_churn_percent', 101),
    ('flood_thin_listings', 10)])
def test_config_rejects_invalid_settings(tmp_path, key, value):
    with pytest.raises(ValueError, match='flood'):
        addon_source(tmp_path / 'data', **{key: value})


def test_item_index_matches_plain_scan_rows():
    from brownstone.flood_signals import Rows, _match, compatible_identity
    rows = [{'item_id': 1, 'variant_id': None, 'variant_state': 'base', 'min_buyout': 5},
            {'item_id': 2, 'variant_id': 7, 'variant_state': 'variant', 'min_buyout': 9},
            {'item_id': 2, 'variant_id': None, 'variant_state': 'base', 'min_buyout': 8}]
    legacy = {'item_id': 1, 'variant_id': None, 'variant_state': None}
    for current in (*rows, legacy, {'item_id': 3, 'variant_id': None, 'variant_state': None}):
        assert _match(current, Rows(rows)) == _match(current, rows)
        assert compatible_identity(current, Rows(rows), Rows(rows)) == compatible_identity(current, rows, rows)
    assert Rows(rows).by_item[2] == rows[1:]


def test_daily_points_equal_weight_utc_days_and_newest_exclusion(tmp_path):
    records = [scan(f'busy{i}', FINISHED - 86400 - i * 60, [listing(1, 3, 30)]) for i in range(6)]
    records += [scan('day2', FINISHED - 2 * 86400, [listing(1, 3, 300)]),
                scan('day3', FINISHED - 3 * 86400, [listing(1, 3, 600)]),
                scan('newest', FINISHED, [listing(1, 3, 180)])]
    config = fixture(tmp_path, records) | {'flood_min_days': 3}
    with connection(config) as db:
        # Returned TIMESTAMPTZ values may use the connection's local time zone.
        db.execute("SET TimeZone='Pacific/Auckland'")
        row = flood.signals(db, config, [1], NOW)['rows'][0]
        assert row['overshoot'] == {'days': 3, 'scans': 8, 'typical_copper': 100, 'label': 'cheap',
                                    'ratio': {'numerator': 60, 'denominator': 100}}
        db.execute("UPDATE addon_scans SET finished_at=finished_at + INTERVAL 1 DAY WHERE scan_id='day3'")
        history = flood.signals(db, config, [1], NOW)['rows'][0]['overshoot']
        assert history == {'days': 2, 'scans': 8, 'typical_copper': None, 'label': 'too few days', 'ratio': None}


def test_daily_and_final_even_medians_round_down_and_ignore_nonpositive():
    result = flood.overshoot(60, [('a', 100), ('a', 103), ('b', 104), ('b', 107),
                                ('c', None), ('c', 0), ('c', -10)],
                             flood.settings({'flood_min_days': 2}))
    assert result == {'days': 2, 'scans': 4, 'typical_copper': 103, 'label': 'cheap',
                      'ratio': {'numerator': 60, 'denominator': 103}}


def test_utc_midnight_groups_by_utc_not_connection_timezone(tmp_path):
    from datetime import UTC, datetime
    midnight = int(datetime(2026, 11, 4, tzinfo=UTC).timestamp())
    records = [scan('before', midnight - 60, [listing(1, 1, 100)]),
               scan('after', midnight + 60, [listing(1, 1, 200)]),
               scan('newest', FINISHED, [listing(1, 1, 60)])]
    config = fixture(tmp_path, records) | {'flood_min_days': 2}
    with connection(config) as db:
        db.execute("SET TimeZone='America/Chicago'")
        assert flood.signals(db, config, [1], NOW)['rows'][0]['overshoot']['days'] == 2


def test_min_days_defaults_inheritance_override_and_old_setting_rejected(tmp_path):
    from brownstone.config import build_source
    source = addon_source(tmp_path / 'data')
    entry = {k: v for k, v in source.items() if k not in ('data_dir', 'market_id', 'flood_min_days')}
    shared = {'data_dir': tmp_path / 'data', 'flood_min_days': 4}
    assert source['flood_min_days'] == 3
    assert build_source(shared, entry)['flood_min_days'] == 4
    assert build_source(shared, entry | {'flood_min_days': 2})['flood_min_days'] == 2
    for old_shared, old_entry in [(shared | {'flood_min_scans': 5}, entry),
                                  (shared, entry | {'flood_min_scans': 5})]:
        with pytest.raises(ValueError, match='flood_min_scans.*flood_min_days'):
            build_source(old_shared, old_entry)


def test_daily_variant_points_never_pool(tmp_path):
    records = [scan(f'day{i}', FINISHED - i * 86400, [listing(1, 1, 100)]) for i in range(4)]
    config = fixture(tmp_path, records) | {'flood_min_days': 3}
    with connection(config) as db:
        db.execute("UPDATE scan_metrics SET variant_state='variant', variant_id='suffix:-1'")
        columns = [r[1] for r in db.execute("PRAGMA table_info('scan_metrics')").fetchall()]
        fields = ', '.join("metric_key || '-second'" if c == 'metric_key' else
                           "'suffix:-2'" if c == 'variant_id' else '1000' if c == 'min_buyout' else c
                           for c in columns)
        db.execute(f"INSERT INTO scan_metrics SELECT {fields} FROM scan_metrics")
        rows = flood.signals(db, config, [1], NOW)['rows']
        assert {r['variant_id']: r['overshoot']['typical_copper'] for r in rows} == {
            'suffix:-1': 100, 'suffix:-2': 1000}
        assert all(r['overshoot']['days'] == 3 and r['overshoot']['scans'] == 3 for r in rows)
        db.execute("DELETE FROM scan_metrics WHERE scan_id='day3' AND variant_id='suffix:-2'")
        rows = flood.signals(db, config, [1], NOW)['rows']
        assert {r['variant_id']: r['overshoot']['label'] for r in rows} == {
            'suffix:-1': 'typical', 'suffix:-2': 'too few days'}
