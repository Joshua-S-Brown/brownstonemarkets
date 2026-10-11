"""Offline STORY-053 place, reachability and source-state acceptance tests."""
from copy import deepcopy
from pathlib import Path

import pytest
from navigation_helpers import navigate
from streamlit.testing.v1 import AppTest

from brownstone.config import read_sources
from views.navigation import PLACES, QUESTIONS

ROOT = Path(__file__).resolve().parents[1]


def sources(tmp_path, monkeypatch):
    configured = read_sources(ROOT / 'config/market.toml')
    tsm = next(s for s in configured if s['game_version'] == 'classic')
    addon = next(s for s in configured if s['provider'] == 'addon')
    for source in (tsm, addon):
        source.update(enabled=True, data_dir=tmp_path / source['source_id'])
    addon['scan_path'] = tmp_path / 'missing.lua'
    monkeypatch.setattr('brownstone.config.read_sources', lambda *args: [tsm, addon])
    monkeypatch.setattr('brownstone.pipeline.run', lambda *args: pytest.fail('navigation downloaded'))
    monkeypatch.setattr('views.scan_import.preview_scans', lambda *args: pytest.fail('navigation previewed'))
    monkeypatch.setattr('views.scan_import.import_scans', lambda *args: pytest.fail('navigation imported'))
    return tsm, addon


@pytest.mark.parametrize('game', ['classic', 'forever'])
def test_places_and_every_old_page_reachable(tmp_path, monkeypatch, game):
    sources(tmp_path, monkeypatch)
    at = AppTest.from_file(str(ROOT / 'app.py')).run()
    next(w for w in at.selectbox if w.label == 'Experience').set_value(game).run()
    assert next(w for w in at.radio if w.label == "View").value == 'Today'
    assert next(w for w in at.radio if w.label == "View").options == list(PLACES)
    for place, sections in PLACES.items():
        navigate(at, place)
        assert not at.exception
        assert QUESTIONS[place] in [c.value for c in at.main.caption]
        assert at.get('button_group')[0].options == list(sections)
        assert not any(b.label in ('Preview addon scans', 'Refresh from TSM') for b in at.sidebar.button)
        for section in sections:
            if len(sections) > 1:
                at.get('button_group')[0].set_value(section).run()
            assert not at.exception
            assert QUESTIONS[section] in [c.value for c in at.main.caption]
            if section == 'Import':
                label = 'Preview addon scans' if game == 'forever' else 'Refresh from TSM'
                assert any(b.label == label for b in at.main.button)
            if section == 'Recipe catalogs':
                assert any(h.value == section for h in at.subheader)
    assert not at.sidebar.get('button_group')


def test_place_and_section_remembered_per_source(tmp_path, monkeypatch):
    _, addon = sources(tmp_path, monkeypatch)
    other = deepcopy(addon)
    other['source_id'] = 'other-addon'
    other['label'] = 'Other addon observer'
    monkeypatch.setattr('brownstone.config.read_sources', lambda *args: [addon, other])
    at = AppTest.from_file(str(ROOT / 'app.py')).run()
    def source():
        return next(w for w in at.selectbox if w.label == 'Data source')
    source().set_value(0).run()
    assert next(w for w in at.radio if w.label == "View").value == 'Today'
    navigate(at, 'Watchlist')
    source().set_value(1).run()
    assert next(w for w in at.radio if w.label == "View").value == 'Today'
    navigate(at, 'Data')
    source().set_value(0).run()
    assert next(w for w in at.radio if w.label == "View").value == 'Market'
    assert at.get('button_group')[0].value == 'Watchlist'
    assert at.session_state[f"view-{addon['source_id']}"] == 'Market'
    source().set_value(None).run()
    assert any('Choose one above' in i.value for i in at.info)
    source().set_value(0).run()
    assert next(w for w in at.radio if w.label == 'View').value == 'Market'
    source().set_value(1).run()
    assert next(w for w in at.radio if w.label == "View").value == 'Data'
    fresh = AppTest.from_file(str(ROOT / 'app.py')).run()
    next(w for w in fresh.selectbox if w.label == 'Data source').set_value(0).run()
    assert next(w for w in fresh.radio if w.label == "View").value == 'Today'


def test_addon_below_usual_price_reason_without_snapshot(tmp_path, monkeypatch):
    sources(tmp_path, monkeypatch)
    at = AppTest.from_file(str(ROOT / 'app.py')).run()
    navigate(at, 'Opportunities')
    assert not at.exception
    reason = next(i.value for i in at.info if 'no historical values' in i.value)
    assert all(section in reason for section in ('Browse market', 'Skill-up demand', 'Watchlist'))
    assert not at.dataframe and not at.slider


@pytest.mark.parametrize('old,place,section', [
    ('Crafting', 'Today', 'All recipes'), ('Opportunities', 'Market', 'Below usual price'),
    ('Recipe catalogs', 'Data', 'Recipe catalogs'),
])
def test_legacy_view_key_migrates(tmp_path, monkeypatch, old, place, section):
    _, addon = sources(tmp_path, monkeypatch)
    at = AppTest.from_file(str(ROOT / 'app.py'))
    at.session_state[f"view-{addon['source_id']}"] = old
    at.run()
    assert not at.exception and next(w for w in at.radio if w.label == "View").value == place
    assert at.get('button_group')[0].value == section


def test_navigation_preserves_plan_tables_and_saved_settings(tmp_path, monkeypatch):
    from test_today_view import app

    at, _, path = app(tmp_path, monkeypatch)
    tables = [table.value.copy() for table in at.dataframe]
    settings = path.read_bytes()
    navigate(at, 'Crafting')
    navigate(at, 'Market')
    navigate(at, 'Data')
    navigate(at, 'Today')
    assert not at.exception
    assert path.read_bytes() == settings
    assert len(at.dataframe) == len(tables)
    assert all(before.equals(after.value) for before, after in zip(tables, at.dataframe, strict=True))


def test_reviewed_import_selection_survives_place_navigation(tmp_path, monkeypatch):
    from test_app import preview_addon

    at, _ = preview_addon(tmp_path, monkeypatch)
    navigate(at, 'Data')
    next(b for b in at.button if b.label == 'Preview addon scans').click().run()
    at.multiselect[0].set_value(['one']).run()
    before = at.session_state['scan_import_preview']
    navigate(at, 'Team')
    navigate(at, 'Data')
    assert not at.exception
    assert at.multiselect[0].value == ['one']
    assert at.session_state['scan_import_preview'] == before
    assert any(b.label == 'Import addon scan' for b in at.button)
