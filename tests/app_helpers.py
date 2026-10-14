"""Framework-free synthetic app evidence shared by offline NiceGUI tests."""
from datetime import UTC, datetime, timedelta
from pathlib import Path

from conftest import make_source
from test_today import catalog

from brownstone.config import read_sources
from brownstone.pipeline import run
from brownstone.today_settings import TodaySettings, save_settings, settings_path

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
    return None, source, path

def listing_evidence_app(tmp_path, monkeypatch, hours):
    from test_scans import addon_source, listing, scan, write_scans

    from brownstone.pipeline import import_scans
    source = addon_source(tmp_path / 'addon-data', game_version='classic', realm='mankrik', server_type='',
                         faction='alliance', rules_version='fixture-v1', max_age_hours=48,
                         scan_evidence={'faction': 'Alliance'})
    finish = int((datetime.now(UTC) + timedelta(hours=hours)).timestamp())
    path = write_scans(tmp_path / 'evidence.lua', scan('evidence', finish,
                       [listing(1, 2, 20), listing(1, 4, 80), listing(3, 8, 16000)]))
    source['scan_path'] = path
    # Import under that clock, then render under the current clock to exercise clock rollback.
    import_scans(source, path, now=datetime.fromtimestamp(finish + 1, UTC))
    source['max_age_hours'] = 24
    save_settings(settings_path(source['data_dir'], source['source_id']), TodaySettings(100000, 1, 'fixed'))
    monkeypatch.setattr('brownstone.config.read_sources', lambda *args: [source])
    monkeypatch.setattr('brownstone.recipe_catalogs.find_catalogs',
                        lambda *args: [{'name': 'fixture', 'catalog': catalog()}])
    original = __import__('brownstone.today_loading', fromlist=['read_today_evidence']).read_today_evidence

    def evidence(db, config, sid, ids):
        observations, listings, metrics, _ = original(db, config, sid, ids)
        return observations, listings, metrics, {1: 21}

    monkeypatch.setattr('brownstone.today_loading.read_today_evidence', evidence)
    return None, source

def preview_addon(tmp_path, monkeypatch, records=None, sources_count=1):
    from test_scans import finished_now, listing, scan, write_scans
    addon = next(s for s in read_sources(ROOT / "config/market.toml") if s["provider"] == "addon")
    records = records if records is not None else [scan("one", finished_now(), [listing(1, 1, 50)]),
                                                   scan("two", finished_now(), [], status="stopped")]
    path = write_scans(tmp_path / "preview.lua", *records)
    addon.update(enabled=True, data_dir=tmp_path / "data", scan_path=path, scan_evidence={"faction": "Alliance"})
    sources = [addon]
    if sources_count == 2:
        sources.append({**addon, "source_id": "other", "label": "Other observer"})
    monkeypatch.setattr("brownstone.config.read_sources", lambda *args: sources)
    return None, addon
