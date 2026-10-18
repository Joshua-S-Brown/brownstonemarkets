"""UI-19 offline evidence, units, thresholds and source isolation."""
import pytest
from test_removed_listings import connection
from test_scans import FINISHED, NOW, addon_source, listing, scan, write_scans

from brownstone import sales_speed as speed
from brownstone.config import SPEED_DEFAULTS, build_source
from brownstone.markets import MARKET_KEYS
from brownstone.pipeline import import_scans


def test_weighted_window_absence_expiry_variants_and_scope(tmp_path):
    config = addon_source(tmp_path / 'data') | {'speed_window_days': 1, 'speed_min_pairs': 2, 'speed_min_hours': 4}
    # Unequal 1h/3h gaps: 3+1 removed, not median per-gap rates. Old and >12h gaps are excluded.
    entries = [scan('outside-old', FINISHED - 93600, [listing(1, 200, 100)]),
               scan('outside', FINISHED - 90000, [listing(1, 100, 100)]),
               scan('a', FINISHED - 14400, [listing(1, 10, 100), listing(2, 4, 100)]),
               scan('b', FINISHED - 10800, [listing(1, 7, 100), listing(3, 1, 100)]),
               scan('c', FINISHED, [listing(1, 6, 100)])]
    import_scans(config, write_scans(tmp_path / 'scans.lua', *entries), now=NOW)
    with connection(config) as db:
        # UI-10 whole-stack matching: changing stack quantity removes the earlier whole stack.
        db.execute('UPDATE scan_listings SET time_left=4, variant_state=\'base\'')
        rows = speed.read(db, config, [1, 2, 3])
        row = speed.select(rows, 1, None, 'base', config)
        assert (row['daily_units'], row['pairs'], row['hours'], row['median_units']) == (102, 2, 4, 8.5)
        assert row['days_supply'] == pytest.approx(8.5 / 102)
        assert row['suggested_units'] == 2  # fractional median cap floors once
        absent = speed.select(rows, 2, None, 'base', config)
        assert absent['pairs'] == 1 and absent['daily_units'] is None
        assert absent['reason'] == 'not enough scan gaps (1, 1.0 h)'
        for key in ('source_id', *MARKET_KEYS):
            assert speed.read(db, config | {key: 'other'}, [1]) == []
        db.execute("UPDATE scan_listings SET time_left=1 WHERE scan_id='a'")
        db.execute("UPDATE scan_listings SET time_left=NULL WHERE scan_id='b'")
        row = speed.read(db, config, [1])[0]
        assert row['daily_units'] == 0 and row['days_supply'] is None
        assert row['reason'] == 'no early removals in 2 scan gaps'
        db.execute("UPDATE scan_listings SET variant_state='variant', variant_id='suffix' WHERE scan_id='b'")
        rows = speed.read(db, config, [1])
        assert {r['variant_state']: r['pairs'] for r in rows} == {'base': 1, 'variant': 1}
        assert speed.read(db, config, []) == []
        assert speed.read(db, config | {'provider': 'tsm'}, [1]) == []
        # Earlier exactly on cutoff is included; moving the window reference one second excludes it.
        db.execute("UPDATE addon_scans SET finished_at=finished_at + INTERVAL 1 DAY - INTERVAL 4 HOUR "
                   "WHERE scan_id='c'")
        assert speed.read(db, config, [1])[0]['pairs'] == 1
        db.execute("UPDATE addon_scans SET finished_at=finished_at + INTERVAL 1 SECOND WHERE scan_id='c'")
        assert speed.read(db, config, [1]) == []
    assert speed.load(config, [999]) == []


def test_fractional_rate_cover_cap_and_inclusive_thresholds():
    config = {'speed_min_pairs': 2, 'speed_min_hours': 4, 'speed_cap_percent': 100}
    samples = [{'seconds': 3600, 'removed': 1, 'listed': 100},
               {'seconds': 10800, 'removed': 0, 'listed': 101}]
    row = speed.summarize(samples, config)
    assert row['daily_units'] == 6 and row['suggested_units'] == 18
    assert row['median_units'] == 100.5 and row['days_supply'] == 16.75
    # Keep the fractional rate for cover; floor only the final integer units.
    row = speed.summarize([{'seconds': 90000, 'removed': 2, 'listed': 100}],
                          {'speed_min_pairs': 1, 'speed_min_hours': 25})
    assert row['daily_units'] == 1 and row['suggested_units'] == 5
    assert speed.summarize(samples, config | {'speed_min_hours': 5})['daily_units'] is None
    assert speed.summarize(samples, config | {'speed_min_pairs': 3})['suggested_units'] is None
    assert speed.summarize([], {})['reason'] == 'not enough scan gaps (0, 0.0 h)'


@pytest.mark.parametrize('key', SPEED_DEFAULTS)
def test_settings_defaults_shared_overrides_and_validation(tmp_path, key):
    config = addon_source(tmp_path / 'data')
    config.pop('market_id')
    config.pop('data_dir')
    for setting in SPEED_DEFAULTS:
        config.pop(setting)
    default = build_source({'data_dir': tmp_path}, config)
    assert all(default[k] == value for k, value in SPEED_DEFAULTS.items())
    assert build_source({'data_dir': tmp_path, key: 8}, config)[key] == 8
    assert build_source({'data_dir': tmp_path, key: 8}, config | {key: 2})[key] == 2
    for invalid in (0, -1, True, 1.5, '2'):
        with pytest.raises(ValueError, match=key):
            build_source({'data_dir': tmp_path}, config | {key: invalid})


def test_legacy_base_matching_remains_pair_specific(tmp_path):
    from test_removed_listings import fixture
    config = fixture(tmp_path, [listing(1, 2, 100)] * 2, [listing(1, 2, 100)])
    config.update(speed_min_pairs=1, speed_min_hours=1)
    with connection(config) as db:
        db.execute("UPDATE scan_listings SET time_left=4")
        legacy = speed.read(db, config, [1])
        assert speed.select(legacy, 1, None, 'base', config) == legacy[0]  # Legacy-only evidence answers base.
        db.execute("UPDATE scan_listings SET variant_state='base' WHERE scan_id='new'")
        rows = speed.read(db, config, [1])
        assert len(rows) == 1 and rows[0]['variant_state'] == 'base'
        assert rows[0]['daily_units'] == 48 and rows[0]['median_units'] == 4
        db.execute("UPDATE scan_listings SET variant_state='unresolved' WHERE scan_id='new'")
        rows = speed.read(db, config, [1])
        assert speed.select(rows, 1, None, None, config)['daily_units'] == 96
        assert speed.select(rows, 1, None, 'unresolved', config)['pairs'] == 0
        db.execute("UPDATE addon_scans SET finished_at=(SELECT max(finished_at) FROM addon_scans)")
        assert speed.select(speed.read(db, config, [1]), 1, None, None, config)['hours'] == 0
