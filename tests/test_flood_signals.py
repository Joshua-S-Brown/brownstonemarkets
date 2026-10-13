"""STORY-064: offline boundaries, scoped metrics, identities and honest evidence."""
from datetime import timedelta

import duckdb
import pytest
from test_scans import FINISHED, NOW, addon_source, listing, scan, write_scans

from brownstone import flood_signals as flood
from brownstone.markets import MARKET_KEYS
from brownstone.pipeline import import_scans


def fixture(tmp_path, records=None):
    config = addon_source(tmp_path / 'data')
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
    result = flood.overshoot(price, [100] * 5, flood.settings({}))
    assert result['label'] == label and result['typical_copper'] == 100 and result['scans'] == 5
    assert result['ratio'] == ({'numerator': price, 'denominator': 100} if price else None)


def test_too_few_missing_prices_median_integer_units_and_custom_settings():
    options = flood.settings({})
    assert flood.overshoot(1, [100] * 4 + [None, 0], options)['label'] == 'too few scans'
    assert flood.overshoot(60, [1, 100, 100, 100, 10000], options)['typical_copper'] == 100
    assert flood.overshoot(60, [100, 101], options | {'flood_min_scans': 2})['typical_copper'] == 100
    assert flood.overshoot(70, [100] * 5, options | {'flood_cheap_percent': 70})['label'] == 'cheap'
    assert flood.overshoot(140, [100] * 5, options | {'flood_high_percent': 140})['label'] == 'high'
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
        assert row['overshoot'] == {'label': 'cheap', 'typical_copper': 100, 'scans': 5,
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
        assert row['overshoot']['scans'] == 14 and row['overshoot']['typical_copper'] == 106
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
                        'listings': 10, 'crowding': 'contested',
                        'overshoot': flood.overshoot(50 if item_id % 2 else 200, [100] * 5, flood.settings({}))})
    catalog = {'items_by_id': dict.fromkeys(range(1, 14)),
               'recipes_by_id': {1: {'output_item_id': 1, 'inputs': [{'item_id': 2}]},
                                 2: {'output_item_id': 2, 'inputs': [{'item_id': 3}]}}}
    roles = flood.catalog_roles([catalog])
    assert roles[1] == 'output' and roles[2] == 'material / output' and roles[3] == 'material'
    lists = flood.top_lists(result | {'rows': rows}, roles)
    assert len(lists['contested']) == len(lists['overshoots']) == 10
    assert {r['overshoot']['label'] for r in lists['overshoots']} == {'cheap', 'high'}
    assert all(r['item_id'] != 14 and r['listings'] == 10 for r in lists['contested'])
    reversed_lists = flood.top_lists(result | {'rows': list(reversed(rows))}, roles)
    assert all(lists[key] == reversed_lists[key] for key in ('contested', 'overshoots'))
    thin = [r | {'listings': 2, 'crowding': 'thin'} for r in rows]
    assert flood.top_lists(result | {'rows': thin}, roles)['overshoots'] == []


@pytest.mark.parametrize(('key', 'value'), [('flood_window_days', 0), ('flood_min_scans', True),
    ('flood_cheap_percent', 100), ('flood_high_percent', 100), ('flood_churn_percent', 101),
    ('flood_thin_listings', 10)])
def test_config_rejects_invalid_settings(tmp_path, key, value):
    with pytest.raises(ValueError, match='flood'):
        addon_source(tmp_path / 'data', **{key: value})
