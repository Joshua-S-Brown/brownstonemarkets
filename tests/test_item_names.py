"""STORY-022: labels are derived without changing observations or market joins."""
import hashlib

import duckdb
import pytest
from conftest import make_source
from test_pipeline import HEADER
from test_pipeline import NOW as CSV_NOW
from test_scans import FINISHED, NOW, addon_source, listing, scan, write_scans

from brownstone.analysis import browse, rank
from brownstone.item_names import (
    remember_catalog_names,
    remember_local_catalog_names,
    remember_observed_names,
    seed_catalog_names,
)
from brownstone.pipeline import import_scans, run
from brownstone.scan_changes import compare_scans
from brownstone.storage import MIGRATIONS, ensure_schema, listing_depth, upgrade_database
from views.crafting import _board_row


def catalog(game, names):
    return {'game_version': game, 'items': [{'item_id': item, 'name': name,
            'source_url': f'https://example.com/{game}/{item}'} for item, name in names.items()]}


def imported_names(tmp_path):
    config = addon_source(tmp_path / 'data')
    path = write_scans(tmp_path / 'scans.lua',
                       scan('old', FINISHED - 60, [listing(14047, 2, 100), listing(90001, 1, 50),
                                                 listing(90002, 1, 10, name='Item 90002')]),
                       scan('new', FINISHED, [listing(14047, 2, 100, name='Runecloth'),
                                             listing(90001, 1, 50), listing(90002, 1, 10)]))
    import_scans(config, path, now=NOW)
    return config


def test_missing_name_later_loaded_browse_search_changes_and_depth(tmp_path):
    config = imported_names(tmp_path)
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb')) as db:
        assert browse(db, 'my-scans:old', config, 'runECLOTH')['item_name'].to_list() == ['Runecloth']
        names = dict(browse(db, 'my-scans:old', config).select('item_id', 'item_name').rows())
        assert names == {14047: 'Runecloth', 90001: 'Item 90001', 90002: 'Item 90002'}
        diff = compare_scans(db, config, 'old', 'new')
        assert diff['items'][0]['item_name'] == 'Runecloth'
        assert not any(row['changed'] for row in diff['items'])
        # Depth's labels already come from the catalog, not nullable price/listing names.
        depth = listing_depth(db, config, 'my-scans:old', [14047, 90001])
        row = {'recipe_id': 1, 'output_item_id': 90001, 'rank': 1, 'output_name': 'Bag',
               'profession': 'tailoring', 'action': 'missing prices', 'craft_cost_copper': None,
               'sale_price_copper': None, 'net_revenue_copper': None, 'profit_copper': None, 'margin': None,
               'profit_by_basis': {'listed': None}}
        recipe_catalog = {'recipes_by_id': {1: {'inputs': [{'item_id': 14047}]}},
                          'items_by_id': {14047: {'name': 'Runecloth'}}}
        assert 'Runecloth:' in _board_row(recipe_catalog, row, 'listed', depth)['Direct input depth']
        assert db.execute("SELECT item_name FROM market_snapshots WHERE snapshot_id='my-scans:old' "
                          'AND item_id=14047').fetchone() == ('Item 14047',)
        assert db.execute("SELECT item_name FROM scan_listings WHERE scan_id='old' "
                          'AND item_id=14047').fetchone() == (None,)


def test_catalog_only_placeholder_rejected_and_game_version_isolation(tmp_path):
    config = imported_names(tmp_path)
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb')) as db:
        remember_catalog_names(db, [catalog('classic', {90001: 'Classic label'}),
                                    catalog('forever', {90002: 'Catalog label', 90001: 'Item 123'})])
        assert browse(db, 'my-scans:old', config, 'Catalog label')['item_id'].to_list() == [90002]
        assert browse(db, 'my-scans:old', config, 'Classic label').is_empty()
        assert browse(db, 'my-scans:old', config, '90001')['item_name'][0] == 'Item 90001'
        assert db.execute('SELECT item_name FROM named_scan_listings WHERE item_id=90002').fetchall() == [
            ('Catalog label',), ('Catalog label',)]
        assert next(r for r in compare_scans(db, config, 'old', 'new')['items']
                    if r['item_id'] == 90002)['item_name'] == 'Catalog label'


def test_observed_precedence_newest_loaded_lexical_ties_and_older_import(tmp_path):
    config = imported_names(tmp_path)
    path = write_scans(tmp_path / 'conflicts.lua',
                       scan('older', FINISHED - 30, [listing(14047, 1, 50, name='Older name')]),
                       scan('tie', FINISHED, [listing(14047, 1, 50, name='A tie winner')]),
                       scan('empty-name', FINISHED + 10, [listing(14047, 1, 50)]))
    import_scans(config, path, now=NOW)
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb')) as db:
        remember_catalog_names(db, [catalog('forever', {14047: 'AAA Catalog'})])
        assert browse(db, 'my-scans:old', config, '14047')['item_name'][0] == 'A tie winner'
        # Keep a row's own loaded name even when it disagrees with newer fallback evidence.
        assert browse(db, 'my-scans:new', config, '14047')['item_name'][0] == 'Runecloth'
        assert browse(db, 'my-scans:older', config, '14047')['item_name'][0] == 'Older name'
        before = db.execute('SELECT * FROM item_names ORDER BY ALL').fetchall()
        remember_observed_names(db)
        remember_catalog_names(db, [catalog('forever', {14047: 'AAA Catalog'})])
        assert db.execute('SELECT * FROM item_names ORDER BY ALL').fetchall() == before


def test_name_only_shares_between_sources_markets_and_environments(tmp_path):
    config = imported_names(tmp_path)
    other = addon_source(config['data_dir'], source_id='other', server_type='normal', environment='beta')
    path = write_scans(tmp_path / 'other.lua', scan('other', FINISHED + 20,
                      [listing(90001, 1, 900, name='Shared label')]))
    import_scans(other, path, now=NOW)
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb')) as db:
        found = browse(db, 'my-scans:old', config, 'Shared label')
        assert found.select('item_id', 'min_buyout').rows() == [(90001, 50)]
        assert listing_depth(db, config, 'my-scans:old', [90001])[90001] == {'listings': 1, 'units': 1}
        assert browse(db, 'other:other', config).is_empty()


def test_v4_migration_backfill_replay_backup_and_immutable_rows(tmp_path):
    config = imported_names(tmp_path)
    database = config['data_dir'] / 'brownstone.duckdb'
    with duckdb.connect(str(database)) as db:
        original = {table: db.execute(f'SELECT * FROM {table} ORDER BY ALL').fetchall()
                    for table in ('market_snapshots', 'scan_listings', 'addon_scans')}
        db.execute('DROP VIEW named_market_snapshots')
        db.execute('DROP VIEW named_scan_listings')
        db.execute('DROP TABLE item_names')
        db.execute("UPDATE schema_info SET value='4'")
    before_hash = hashlib.sha256(database.read_bytes()).hexdigest()
    assert upgrade_database(config['data_dir'])
    assert hashlib.sha256(database.with_name('brownstone.v4.backup.duckdb').read_bytes()).hexdigest() == before_hash
    with duckdb.connect(str(database)) as db:
        assert browse(db, 'my-scans:old', config, 'Runecloth').height == 1
        before = db.execute('SELECT * FROM item_names ORDER BY ALL').fetchall()
        MIGRATIONS[5](db)
        MIGRATIONS[5](db)
        assert db.execute('SELECT * FROM item_names ORDER BY ALL').fetchall() == before
        assert all(db.execute(f'SELECT * FROM {table} ORDER BY ALL').fetchall() == rows
                   for table, rows in original.items())
    assert not upgrade_database(config['data_dir'])


def test_partial_listing_names_and_new_import_keep_filling_lookup(tmp_path):
    config = imported_names(tmp_path)
    path = write_scans(tmp_path / 'partial.lua', scan('partial', FINISHED + 30,
                       [listing(90001, 1, 100, name='Loaded on partial scan')], reported=2))
    import_scans(config, path, now=NOW)
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb')) as db:
        assert browse(db, 'my-scans:old', config, 'Loaded on partial scan').height == 1
        db.execute('DELETE FROM item_names WHERE item_id=90001')
        MIGRATIONS[5](db)
        assert browse(db, 'my-scans:old', config, 'Loaded on partial scan').height == 1


def test_tsm_names_fallback_search_rank_and_import_timestamp_policy(tmp_path):
    config = make_source(tmp_path / 'data')
    path = tmp_path / 'items.csv'
    def write(name, stamp):
        path.write_text(HEADER + f'90001,{name},100,10,100,100,{stamp}\n')
    write('', CSV_NOW.isoformat())
    result, _ = run(config, path)
    original_snapshot = result['snapshot_id'][0]
    write('TSM label', CSV_NOW.isoformat())
    run(config, path)
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb')) as db:
        assert rank(db, original_snapshot, config, 'TSM label')['item_name'].to_list() == ['TSM label']
        assert browse(db, original_snapshot, config, 'TSM label').height == 1
        assert db.execute('SELECT observed_at FROM item_names WHERE item_id=90001').fetchone() == (CSV_NOW,)


@pytest.mark.parametrize('name', [None, '', '   ', 'Item 90001', 'Item 123'])
def test_absent_labels_never_enter_lookup(name):
    with duckdb.connect() as db:
        ensure_schema(db)
        remember_catalog_names(db, [catalog('forever', {90001: name})])
        assert db.execute('SELECT count(*) FROM item_names').fetchone() == (0,)


def test_catalog_empty_conflicts_and_malformed_local_catalog_isolation(tmp_path):
    selections = tmp_path / 'recipe-selections'
    selections.mkdir()
    (selections / 'missing.toml').touch()
    (selections / 'broken.toml').touch()
    (tmp_path / 'broken.toml').write_text('schema_version = 99')
    with duckdb.connect() as db:
        ensure_schema(db)
        remember_catalog_names(db, [])
        remember_local_catalog_names(db, tmp_path)
        remember_catalog_names(db, [catalog('forever', {90001: 'Z catalog'}),
                                    catalog('forever', {90001: 'A catalog'})])
        assert db.execute('SELECT item_name FROM item_names').fetchall() == [('A catalog',)]


def test_tsm_collection_time_when_update_time_absent_and_game_version_unknown(tmp_path):
    config = make_source(tmp_path / 'data', allow_missing_updated_at=True)
    path = tmp_path / 'items.csv'
    path.write_text(HEADER + '90001,Collection label,100,10,100,100,\n')
    run(config, path)
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb')) as db:
        assert db.execute('SELECT n.observed_at = p.collected_at FROM item_names n '
                          'JOIN market_snapshots p USING(game_version, item_id)').fetchone() == (True,)
        db.execute("INSERT INTO market_snapshots(item_id,item_name) VALUES(90002,'Unknown version')")
        remember_observed_names(db)
        assert db.execute('SELECT count(*) FROM item_names WHERE item_id=90002').fetchone() == (0,)


def test_duplicate_addon_import_still_seeds_new_catalog_labels(tmp_path, monkeypatch):
    config = imported_names(tmp_path)
    monkeypatch.setattr('brownstone.pipeline.remember_local_catalog_names',
                        lambda db: remember_catalog_names(db, [catalog('forever', {90001: 'New catalog label'})]))
    result = import_scans(config, tmp_path / 'scans.lua', now=NOW)
    assert result['already_imported'] == 2
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb')) as db:
        assert browse(db, 'my-scans:old', config, 'New catalog label').height == 1
        assert db.execute('SELECT count(*) FROM market_snapshots').fetchone() == (6,)


def test_scan_changes_keep_the_scans_own_loaded_name_over_newer_lookup(tmp_path):
    config = imported_names(tmp_path)
    path = write_scans(tmp_path / 'renamed.lua',
                       scan('first', FINISHED + 40, [listing(90003, 1, 10)]),
                       scan('second', FINISHED + 50, [listing(90003, 1, 10, name='Item 90003'),
                                                      listing(90003, 1, 20, name='Zeta')]),
                       scan('third', FINISHED + 60, [listing(90003, 1, 10, name='Alpha')]))
    import_scans(config, path, now=NOW)
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb')) as db:
        assert db.execute('SELECT item_name FROM item_names WHERE item_id=90003').fetchone() == ('Alpha',)
        changes = compare_scans(db, config, 'first', 'second')
        assert [row['item_name'] for row in changes['items'] if row['item_id'] == 90003] == ['Zeta']
        assert [row['item_name'] for row in compare_scans(db, config, 'old', 'first')['new']] == ['Alpha']


def test_padded_names_are_trimmed_and_compare_equal(tmp_path):
    with duckdb.connect() as db:
        ensure_schema(db)
        remember_catalog_names(db, [catalog('forever', {90001: '  Runecloth  '})])
        remember_catalog_names(db, [catalog('forever', {90001: 'Runecloth'})])
        assert db.execute('SELECT item_name FROM item_names').fetchall() == [('Runecloth',)]


def test_catalog_missing_ids_skipped_and_existing_database_seeded(tmp_path):
    selections = tmp_path / 'recipe-selections'
    selections.mkdir()
    (selections / 'no-ids.toml').touch()
    (tmp_path / 'no-ids.toml').write_text(
        'schema_version = 1\ngame_version = "forever"\nrules_version = "1"\nprofession = "tailoring"\n'
        'status = "beta-observed"\ncatalog_version = "1"\n[[items]]\nname = "No ID"\n')
    with duckdb.connect() as db:
        ensure_schema(db)
        remember_local_catalog_names(db, tmp_path)
        assert db.execute('SELECT count(*) FROM item_names').fetchone() == (0,)
    seed_catalog_names(tmp_path / 'absent', [catalog('forever', {90001: 'Never written'})])
    assert not (tmp_path / 'absent' / 'brownstone.duckdb').exists()
    config = imported_names(tmp_path)
    seed_catalog_names(config['data_dir'], [catalog('forever', {90001: 'Seeded label'})])
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb')) as db:
        assert browse(db, 'my-scans:old', config, 'Seeded label').height == 1
