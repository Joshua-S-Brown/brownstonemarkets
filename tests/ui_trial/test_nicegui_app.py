"""Main-app navigation and import parity, using NiceGUI's offline user fixture."""

import duckdb
import pytest
from navigation_helpers import navigate
from nicegui import ui
from test_app import preview_addon
from test_scans import finished_now, listing, scan, write_scans
from test_today_view import app

from brownstone.navigation import QUESTIONS

pytestmark = pytest.mark.asyncio


def table(user, marker):
    return next(iter(user.find(kind=ui.table, marker=marker).elements))


def records(data):
    with duckdb.connect(str(data / 'brownstone.duckdb'), read_only=True) as db:
        return {name: db.execute(f"SELECT * {'EXCLUDE (collected_at)' if name == 'market_snapshots' else ''} "
                                       f'FROM {name} ORDER BY ALL').fetchall()
                for name in ('scan_listings', 'market_snapshots')}


async def test_places_order_questions_place_source_tab_refresh(user, tmp_path, monkeypatch):
    _, source, _ = app(tmp_path, monkeypatch)
    other = source | {'source_id': 'other'}
    monkeypatch.setattr('brownstone.config.read_sources', lambda *args: [source, other])
    await user.open('/?game=classic&source=test&place=Team&tab=Buy')
    buttons = sorted((e for e in user.find(ui.button).elements if any(
        m.startswith('place-') for m in e._markers)), key=lambda e: e.id)
    assert [b.text for b in buttons] == ['Today', 'Team', 'Market', 'Stock', 'Data']
    assert buttons[-2].id < next(iter(user.find(ui.separator).elements)).id < buttons[-1].id
    await user.should_see(QUESTIONS['Team'])
    await user.should_see('No characters imported for this source')
    await user.open('/?game=classic&source=test&place=Team&tab=Buy')
    await user.should_see('No characters imported for this source')
    user.find(marker='place-Market').click()
    await user.should_see(QUESTIONS['Market'])
    await user.should_see('Find an item')
    assert user.client.request.query_params['place'] == 'Market'
    assert user.client.request.query_params['source'] == 'test'
    user.find(marker='place-Stock').click()
    await user.should_see(QUESTIONS['Stock'])
    await user.should_see('What needs restocking')
    user.find(marker='place-Today').click()
    await user.should_see('Save Today settings')
    assert next(iter(user.find(ui.tabs).elements)).value == 'Shopping list'
    user.find('Queue').click()
    user.find(marker='place-Team').click()
    await user.should_see('No characters imported for this source')
    assert user.client.request.query_params['tab'] == 'Queue'
    user.find(marker='place-Today').click()
    await user.should_see('Save Today settings')
    assert next(iter(user.find(ui.tabs).elements)).value == 'Queue'
    await user.open('/?game=classic&source=other&place=Data&tab=Queue')
    await user.should_see("old app's Refresh from TSM")
    user.find(marker='page-info').click()
    await user.should_see('source other')
    await user.should_not_see('Check for new scans')


async def test_preview_subset_import_matches_streamlit_records(user, tmp_path, monkeypatch):
    at, source = preview_addon(tmp_path, monkeypatch)
    old = source.copy()
    source['data_dir'] = tmp_path / 'nicegui-data'
    await user.open('/?place=Data')
    await user.should_see('Check for new scans')
    await user.should_not_see(marker='import-action')
    before = source['scan_path'].read_bytes()
    user.find('Check for new scans').click()
    await user.should_see('New partial scan: two')
    assert not source['data_dir'].exists()
    assert [r['Import state'] for r in table(user, 'Scan preview').rows] == ['New', 'New']
    select = next(iter(user.find(kind=ui.select, content='New scans to import').elements))
    select.set_value([])
    await user.should_not_see(marker='import-action')
    next(iter(user.find(kind=ui.select, content='New scans to import').elements)).set_value(['one'])
    user.find(marker='import-action').click()
    await user.should_see('Imported. Collection prices come from scan one')
    await user.should_not_see(marker='Scan preview')
    assert source['scan_path'].read_bytes() == before
    # Run the existing Streamlit page on a separate directory, with the same selected bytes.
    monkeypatch.setattr('brownstone.config.read_sources', lambda *args: [old])
    at.run()
    navigate(at, 'Data')
    next(b for b in at.button if b.label == 'Preview addon scans').click().run()
    at.multiselect[0].set_value(['one']).run()
    next(b for b in at.button if b.label == 'Import addon scan').click().run()
    assert not at.exception
    assert records(source['data_dir']) == records(old['data_dir'])


async def test_drop_rejected_file_cleanup_and_stale_review(user, tmp_path, monkeypatch):
    _, source = preview_addon(tmp_path, monkeypatch, [])
    folder = tmp_path / 'drops'
    folder.mkdir()
    good = write_scans(folder / 'windows-pc-20261007T004900Z-BrownstoneScan.lua',
                       scan('win', finished_now(), [listing(2, 1, 80)]))
    bad = folder / 'windows-pc-20261007T005000Z-BrownstoneScan.lua'
    bad.write_text('truncated')
    source.update(drop_folder=folder)
    await user.open('/?place=Data')
    await user.should_see('Check for new scans')
    user.find('Check for new scans').click()
    await user.should_see(bad.name)
    assert not source['data_dir'].exists()
    user.find(marker='import-action').click()
    await user.should_see(f'{good}: imported')
    await user.should_see('1 dropped file is fully imported')
    await user.should_see("don't /bscan clear; its latest drop is not fully imported")
    assert table(user, 'Latest drops').rows[0]['Fully imported'] is False
    assert table(user, 'Files').rows[1]['Fully imported'] is True
    # Duplicates may be explicitly selected, but changed bytes invalidate the review.
    select = next(iter(user.find(kind=ui.select, content='Files to import').elements))
    select.set_value([str(good)])
    good.write_bytes(good.read_bytes() + b'\n')
    user.find(marker='import-action').click()
    await user.should_see('Nothing was imported')
    await user.should_not_see(marker='Files')
    assert bad.read_text() == 'truncated'


async def test_preview_error_and_identity_change_discard_review(user, tmp_path, monkeypatch):
    _, source = preview_addon(tmp_path, monkeypatch)
    before = source['scan_path'].read_bytes()
    source['scan_path'].unlink()
    await user.open('/?place=Data')
    await user.should_see('Check for new scans')
    user.find('Check for new scans').click()
    await user.should_see('Preview failed')
    assert not source['data_dir'].exists()
    source['scan_path'].write_bytes(before)
    user.find('Check for new scans').click()
    await user.should_see(marker='import-action')
    second = source | {'source_id': 'second'}
    monkeypatch.setattr('brownstone.config.read_sources', lambda *args: [source, second])
    await user.open('/?game=forever&source=second&place=Data')
    await user.should_not_see(marker='import-action')
    await user.open('/?game=forever&source=' + source['source_id'] + '&place=Data')
    await user.should_not_see(marker='import-action')
