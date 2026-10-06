"""Today UI uses only synthetic sources/catalogs and local preferences."""
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from conftest import make_source
from test_today import catalog

from brownstone.pipeline import run
from brownstone.today_settings import TodaySettings, load_settings, save_settings, settings_path

pytest.importorskip('streamlit')
from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def app(tmp_path, monkeypatch, *, stale=False, corrupt=False):
    source = make_source(tmp_path / 'data', game_version='classic', realm='mankrik', faction='alliance',
                         rules_version='fixture-v1', allow_missing_updated_at=True)
    time = (datetime.now(UTC) - timedelta(hours=25)).isoformat() if stale else ''
    csv = tmp_path / 'items.csv'
    csv.write_text('itemId,name,marketValue,minBuyout,recent,historical,updatedAt\n'
                   f'1,Material,20,10,0,0,{time}\n3,Output,2000,2000,0,0,{time}\n')
    source["max_age_hours"] = 48
    run(source, csv)
    source["max_age_hours"] = 24
    path = settings_path(source['data_dir'], source['source_id'])
    save_settings(path, TodaySettings(100000, 1, 'fixed'))
    if corrupt:
        path.write_text('not json')
    monkeypatch.setattr('brownstone.config.read_sources', lambda *args: [source])
    monkeypatch.setattr('brownstone.recipe_catalogs.find_catalogs',
                        lambda *args: [{'name': 'fixture', 'catalog': catalog()}])
    return AppTest.from_file(str(ROOT / 'app.py')).run(), source, path


def widget(widgets, label):
    return next(w for w in widgets if w.label == label)


def test_today_default_settings_save_rejection_and_new_session(tmp_path, monkeypatch):
    at, _, path = app(tmp_path, monkeypatch)
    assert not at.exception and at.radio[0].value == 'Today'
    assert any('not available for this source' in i.value for i in at.info)
    assert any('Batch profit (g)' in t.value.columns for t in at.dataframe)
    widget(at.text_input, 'Gold available').set_value('12')
    widget(at.button, 'Save Today settings').click().run()
    assert any('bare numbers' in e.value for e in at.error)
    assert load_settings(path).gold_copper == 100000
    # A rejected save keeps the plan visible, still sized by the last saved settings.
    assert any('Batch profit (g)' in t.value.columns for t in at.dataframe)
    widget(at.text_input, 'Gold available').set_value('12g 50s')
    widget(at.text_input, 'Fixed minimum gain').set_value('10s')
    widget(at.selectbox, 'Minimum gain mode').set_value('scaled')
    widget(at.number_input, 'Most crafts per item').set_value(3)
    widget(at.button, 'Save Today settings').click().run()
    assert not at.exception and load_settings(path) == TodaySettings(125000, 1000, 'scaled', 100, 3)
    again = AppTest.from_file(str(ROOT / 'app.py')).run()
    assert widget(again.text_input, 'Gold available').value == '12g 50s'
    assert widget(again.number_input, 'Most crafts per item').value == 3


def test_today_stale_banner_inspection_and_corrupt_settings(tmp_path, monkeypatch):
    at, _, _ = app(tmp_path, monkeypatch, stale=True)
    assert not at.exception and any('stale' in w.value for w in at.warning)
    for table in at.dataframe:
        assert set(table.value['State']) == {'stale — inspect only'}
    at, _, _ = app(tmp_path, monkeypatch, corrupt=True)
    assert not at.exception and any('Could not read Today settings' in w.value for w in at.warning)
    assert widget(at.text_input, 'Gold available').value == '0c'


def test_today_reports_calculation_and_persistence_errors(tmp_path, monkeypatch):
    at, _, _ = app(tmp_path, monkeypatch)
    def fail(*args, **kwargs):
        raise OSError('fixture failure')
    monkeypatch.setattr('views.today.save_settings', fail)
    widget(at.button, 'Save Today settings').click().run()
    assert any('Settings not saved' in e.value for e in at.error)
    monkeypatch.setattr('views.today.build_today', fail)
    at.run()
    assert any('Unable to build Today' in e.value for e in at.error)
