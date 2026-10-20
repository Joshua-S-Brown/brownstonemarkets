"""STORY-027: offline scoped multiset matching and cautious time-left classification."""
from datetime import timedelta

import duckdb
import pytest
from test_scans import FINISHED, NOW, addon_source, listing, scan, write_scans

from brownstone import removed_listings as removed
from brownstone.markets import MARKET_KEYS
from brownstone.pipeline import import_scans


def fixture(tmp_path, earlier, later, gap=3600):
    config = addon_source(tmp_path / 'data')
    import_scans(config, write_scans(tmp_path / 'scans.lua',
                                    scan('old', FINISHED - gap, earlier), scan('new', FINISHED, later)), now=NOW)
    return config


def connection(config):
    return duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb'))


def compare(db, config, ids=None):
    return removed._compare(db, config, removed.scan_pairs(db, config)[0], ids)


def test_identical_reprice_quantity_buyout_and_excluded(tmp_path):
    a = [listing(1, 3, 99)] * 3 + [listing(2, 2, 100), listing(3, 2, 100), listing(4, 5, 0)]
    b = [listing(1, 3, 99), listing(2, 2, 110), listing(3, 1, 100), listing(4, 5, 0)]
    config = fixture(tmp_path, a, b)
    with connection(config) as db:
        rows = {r['item_id']: r for r in compare(db, config)['items']}
        assert rows[1]['unknown'] == {'listings': 2, 'units': 6}
        assert rows[2]['unknown'] == rows[3]['unknown'] == {'listings': 1, 'units': 2}
        assert rows[4]['unknown'] == {'listings': 0, 'units': 0}
        assert rows[4]['without_buyout'] == {'earlier': 1, 'later': 1}
        assert compare(db, config, [])['items'] == []
        assert [r['item_id'] for r in compare(db, config, [1])['items']] == [1]


@pytest.mark.parametrize(('bucket', 'lower'), [(1, 0), (2, 1800), (3, 7200), (4, 43200)])
def test_each_bucket_expiry_boundary(tmp_path, bucket, lower):
    config = fixture(tmp_path, [listing(1, 2, 100)], [listing(2, 1, 100)], gap=max(lower, 1))
    with connection(config) as db:
        db.execute('UPDATE scan_listings SET time_left=? WHERE item_id=1', [bucket])
        assert compare(db, config)['items'][0]['expiry'] == {'listings': 1, 'units': 2}
        if lower:
            db.execute("UPDATE addon_scans SET finished_at=finished_at + INTERVAL 1 SECOND WHERE scan_id='old'")
            row = compare(db, config)['items'][0]
            assert row['early'] == {'listings': 1, 'units': 2}
            assert row['expiry']['listings'] == 0


def test_shortest_first_and_unknown(tmp_path):
    config = fixture(tmp_path, [listing(1, 2, 100)] * 5, [listing(1, 2, 100)] * 2, gap=1800)
    with connection(config) as db:
        db.execute("UPDATE scan_listings SET time_left=CASE listing_index WHEN 1 THEN 4 WHEN 2 THEN 2 "
                   "WHEN 3 THEN 1 WHEN 4 THEN 3 END WHERE scan_id='old'")
        row = compare(db, config)['items'][0]
        assert row['expiry'] == {'listings': 2, 'units': 4}
        assert row['early'] == {'listings': 1, 'units': 2}
        assert row['unknown']['listings'] == 0
        assert [b['time_left'] for b in row['evidence'][0]['chosen_buckets']] == [1, 2, 3]
        db.execute("DELETE FROM scan_listings WHERE scan_id='new'")
        row = compare(db, config)['items'][0]
        assert row['unknown'] == {'listings': 1, 'units': 2}


def test_variants_and_legacy_match_rule(tmp_path):
    config = fixture(tmp_path, [listing(1, 1, 100)] * 2, [listing(1, 1, 100)] * 2)
    with connection(config) as db:
        db.execute("UPDATE scan_listings SET variant_state='base' WHERE scan_id='new'")
        assert compare(db, config)['items'][0]['unknown']['listings'] == 0
        db.execute("UPDATE scan_listings SET variant_state='variant', variant_id='suffix:-1' "
                   "WHERE scan_id='new' AND listing_index=2")
        rows = {r['variant_state']: r for r in compare(db, config)['items']}
        assert rows['legacy']['unknown']['listings'] == 2
        assert rows['base']['unknown']['listings'] == rows['variant']['unknown']['listings'] == 0
        db.execute("UPDATE scan_listings SET variant_state='variant', variant_id='suffix:-2' WHERE scan_id='old'")
        rows = {r['variant_id']: r for r in compare(db, config)['items']}
        assert rows['suffix:-2']['unknown']['listings'] == 2
        assert rows['suffix:-1']['unknown']['listings'] == 0
        db.execute("UPDATE scan_listings SET variant_state='unresolved', variant_id=NULL WHERE scan_id='old'")
        unresolved = next(r for r in compare(db, config)['items'] if r['variant_state'] == 'unresolved')
        assert unresolved['unknown']['units'] == 2


def test_pairs_gap_eligibility_one_scan_tsm_and_no_bridging(tmp_path):
    config = fixture(tmp_path, [listing(1, 1, 100)], [listing(2, 1, 100)], gap=43201)
    import_scans(config, write_scans(tmp_path / 'extra.lua',
                                    scan('third', FINISHED - 43202, [listing(1, 1, 100)]),
                                    scan('partial', FINISHED - 5, [listing(1, 1, 100)], reported=2),
                                    scan('unpriced', FINISHED - 6, [listing(1, 1, 100)])), now=NOW)
    with connection(config) as db:
        db.execute("UPDATE addon_scans SET priced=false WHERE scan_id='unpriced'")
        pairs = removed.scan_pairs(db, config)
        assert [(p['earlier']['scan_id'], p['later']['scan_id']) for p in pairs] == [('old', 'new'), ('third', 'old')]
        assert compare(db, config)['items'] == []
        history = removed.item_history(db, config, 1)
        assert history['pairs'][0]['skipped'] and not history['pairs'][1]['skipped']
        assert removed.top_removals(db, config, [1])['pair'] == pairs[1]
        db.execute("DELETE FROM addon_scans WHERE scan_id='third'")
        assert 'Gap too long' in removed.top_removals(db, config, [1])['note']
        db.execute("DELETE FROM addon_scans WHERE scan_id='old'")
        assert 'Fewer than two' in removed.item_history(db, config, 1)['note']
        assert 'TSM' in removed.top_removals(db, config | {'provider': 'tsm'}, [1])['note']


@pytest.mark.parametrize('key', ['source_id', *MARKET_KEYS])
def test_all_scope_fields_on_scans_and_listings(tmp_path, key):
    config = fixture(tmp_path, [listing(1, 1, 100)] * 2, [listing(1, 1, 100)])
    with connection(config) as db:
        assert removed.scan_pairs(db, config | {key: 'another'}) == []
        # Wrong-scope rows with the SAME scan/snapshot/item IDs cannot offset removals.
        columns = [row[1] for row in db.execute("PRAGMA table_info('scan_listings')").fetchall()]
        fields = ', '.join('?' if column == key else
                           'listing_index + 100' if column == 'listing_index' else column for column in columns)
        db.execute(f"INSERT INTO scan_listings SELECT {fields} FROM scan_listings WHERE scan_id='new'", ['another'])
        assert compare(db, config)['items'][0]['unknown']['listings'] == 1


def test_history_limit_top_order_chain_filter_and_identity_no_pooling(tmp_path):
    config = fixture(tmp_path, [listing(i, i, i * 100) for i in range(1, 15)], [listing(99, 1, 100)])
    with connection(config) as db:
        db.execute('UPDATE scan_listings SET time_left=4')
        top = removed.top_removals(db, config, list(range(1, 14)))
        assert [r['item_id'] for r in top['rows']] == list(range(13, 3, -1))
        db.execute("UPDATE scan_listings SET variant_state='base' WHERE scan_id='old'")
        db.execute("UPDATE scan_listings SET item_id=12, variant_state='variant', variant_id='suffix:-1' "
                   "WHERE scan_id='old' AND item_id=13")
        top = removed.top_removals(db, config, [12])
        assert len(top['rows']) == 1 and top['rows'][0]['early']['units'] == 13
    records = [scan(f'history-{i}', FINISHED + i * 60, [listing(1, 1, 100)]) for i in range(12)]
    import_scans(config, write_scans(tmp_path / 'history.lua', *records), now=NOW + timedelta(hours=1))
    with connection(config) as db:
        assert len(removed.item_history(db, config, 1)['pairs']) == 10


def test_short_bucket_at_zero_gap():
    counts, _ = removed._classify({1: 1}, 1, timedelta(0))
    assert counts == {'early': 0, 'expiry': 1, 'unknown': 0}


def test_names_prefer_pair_then_version_lookup_then_id(tmp_path):
    config = fixture(tmp_path, [listing(1, 2, 100, name='Pair Name'), listing(2, 2, 100), listing(3, 2, 100)],
                     [listing(4, 1, 100)])
    with connection(config) as db:
        db.execute("INSERT OR REPLACE INTO item_names VALUES (?, 1, 'Lookup One', 1, now(), 'test'), "
                   "(?, 2, 'Lookup Two', 1, now(), 'test'), ('other-version', 3, 'Wrong Version', 1, now(), 'test')",
                   [config['game_version']] * 2)
        names = {r['item_id']: r['item_name'] for r in compare(db, config)['items']}
    assert names == {1: 'Pair Name', 2: 'Lookup Two', 3: 'Item 3', 4: 'Item 4'}
