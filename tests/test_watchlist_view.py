"""Watchlist UI and hit panels on offline TSM and addon fixtures."""
from navigation_helpers import navigate
from test_today_view import app, listing_evidence_app, widget

from brownstone.watchlist import Entry, load_entries, save_entries, watchlist_path


def test_page_add_edit_remove_and_tsm(tmp_path, monkeypatch):
    at, config, _ = app(tmp_path, monkeypatch)
    navigate(at, 'Watchlist')
    assert not at.exception
    assert next(w for w in at.radio if w.label == "View").value == 'Market'
    assert at.get('button_group')[0].value == 'Watchlist'
    widget(at.text_input, 'Buy below').set_value('10c')
    widget(at.text_input, 'Sell above').set_value('10c')
    widget(at.button, 'Save entry').click().run()
    path = watchlist_path(config['data_dir'], config['source_id'])
    assert load_entries(path) == [Entry(1, 10, 10)]
    assert widget(at.text_input, 'Buy below').value == ''  # the add form starts empty again
    table = at.dataframe[0].value
    assert table.iloc[0]['Buy state'] == table.iloc[0]['Sell state'] == 'hit'
    assert table.iloc[0]['Lowest unit buyout (g)'] == 0.001
    assert table.iloc[0]['Units listed'] == 'not available for this source'
    widget(at.selectbox, 'Entry to edit').set_value(1).run()
    assert not any(s.label == 'Known item (optional)' for s in at.selectbox)  # editing can't move the entry
    widget(at.text_input, 'Note').set_value('cloth')
    widget(at.button, 'Save entry').click().run()
    assert load_entries(path)[0].note == 'cloth'
    widget(at.button, 'Remove entry').click().run()
    assert load_entries(path) == [] and not at.exception
    widget(at.text_input, 'Buy below').set_value('0c')
    widget(at.button, 'Save entry').click().run()
    assert any('positive' in e.value for e in at.error)
    widget(at.selectbox, 'Known item (optional)').set_value(3)
    widget(at.text_input, 'Buy below').set_value('20s')
    widget(at.button, 'Save entry').click().run()
    assert load_entries(path)[0].item_id == 3


def test_invalid_unreadable_file_warning_and_no_editor(tmp_path, monkeypatch):
    at, config, _ = app(tmp_path, monkeypatch)
    path = watchlist_path(config['data_dir'], config['source_id'])
    path.write_text('bad json')
    navigate(at, 'Watchlist')
    assert not at.exception and any('read-only' in w.value for w in at.warning)
    assert not any(b.label == 'Save entry' for b in at.button)
    assert path.read_text() == 'bad json'
    path.unlink()
    path.mkdir()
    at.run()
    assert any('read-only' in w.value for w in at.warning)
    assert path.is_dir()


def test_today_hits_do_not_change_tables_and_no_hits_hidden(tmp_path, monkeypatch):
    at, config, _ = app(tmp_path, monkeypatch)
    before = [d.value.copy() for d in at.dataframe]
    path = watchlist_path(config['data_dir'], config['source_id'])
    save_entries(path, [Entry(1, 10, 10)])
    at.run()
    assert any('Watchlist hits' in m.value for m in at.markdown)
    assert any('units not available' in c.value for c in at.caption)
    assert all(a.equals(b.value) for a, b in zip(before, at.dataframe, strict=True))
    save_entries(path, [Entry(1, 9, 11)])
    at.run()
    assert not any('Watchlist hits' in m.value for m in at.markdown)


def test_addon_page_and_successful_import_panel(tmp_path, monkeypatch):
    at, config = listing_evidence_app(tmp_path, monkeypatch, -25)
    path = watchlist_path(config['data_dir'], config['source_id'])
    save_entries(path, [Entry(1, 10)])
    navigate(at, 'Watchlist')
    assert not at.exception
    assert at.dataframe[0].value.iloc[0]['Units at or below buy target'] == 2
    assert 'stale' in at.dataframe[0].value.iloc[0]['Buy state']
    navigate(at, 'Data')
    at.session_state['scan_import_result'] = [('success', 'Imported fixture')]
    at.run()
    assert any('Watchlist hits' in m.value for m in at.markdown)
    assert any('2 units at or below target' in c.value for c in at.caption)
    # Data's hit panel labels stale evidence; the Watchlist page's warning is not rendered here.
    assert sum('stale or future-dated' in w.value for w in at.warning) == 0
    assert any('Imported fixture' in s.value for s in at.success)
    at.run()
    assert not any('Watchlist hits' in m.value for m in at.markdown)


def test_save_failure_duplicate_and_evidence_failure(tmp_path, monkeypatch):
    at, config, _ = app(tmp_path, monkeypatch)
    save_entries(watchlist_path(config['data_dir'], config['source_id']), [Entry(1, 10)])
    navigate(at, 'Watchlist')
    widget(at.text_input, 'Buy below').set_value('10c')
    widget(at.button, 'Save entry').click().run()
    assert any('already has an entry' in e.value for e in at.error)
    def fail(*args):
        raise OSError('fixture')
    monkeypatch.setattr('views.watchlist.save_entries', fail)
    widget(at.selectbox, 'Entry to edit').set_value(1).run()
    widget(at.button, 'Save entry').click().run()
    assert any('not saved' in e.value for e in at.error)
    monkeypatch.setattr('views.watchlist.read_watchlist', fail)
    at.run()
    assert any('evidence unavailable' in w.value for w in at.warning)


def test_source_list_not_shown_for_other(tmp_path, monkeypatch):
    at, config, _ = app(tmp_path, monkeypatch)
    save_entries(watchlist_path(config['data_dir'], 'another-source'), [Entry(1, 10)])
    navigate(at, 'Watchlist')
    assert not at.dataframe and any('No watchlist entries' in i.value for i in at.info)


def test_no_snapshot_page_known_catalog_picker(tmp_path, monkeypatch):
    at, config, _ = app(tmp_path, monkeypatch)
    save_entries(watchlist_path(config['data_dir'], config['source_id']), [Entry(1, 10)])
    monkeypatch.setattr('brownstone.watchlist.latest_snapshot', lambda *args: (None, None, 0))
    navigate(at, 'Watchlist')
    row = at.dataframe[0].value.iloc[0]
    assert row['Buy state'] == row['Units listed'] == row['Units at or below buy target'] == 'no snapshot'
    assert not at.exception


def test_actual_addon_import_shows_new_hits(tmp_path, monkeypatch):
    from datetime import UTC, datetime

    from test_scans import listing, scan, write_scans

    at, config = listing_evidence_app(tmp_path, monkeypatch, 0)
    save_entries(watchlist_path(config['data_dir'], config['source_id']), [Entry(1, 10)])
    finish = int(datetime.now(UTC).timestamp())
    write_scans(config['scan_path'], scan('watch-new', finish, [listing(1, 7, 70)]))
    navigate(at, 'Data')
    widget(at.button, 'Preview addon scans').click().run()
    widget(at.button, 'Import addon scan').click().run()
    assert not at.exception and any('Imported.' in s.value for s in at.success)
    assert any('7 units at or below target' in c.value for c in at.caption)
    navigate(at, 'Watchlist')
    assert at.dataframe[0].value.iloc[0]['Units at or below buy target'] == 7
