"""Frozen bronze checks use only isolated synthetic addon records."""
import json
from datetime import UTC, datetime

import pytest
from test_character_snapshots import snapshot, write
from test_scan_v3 import rich
from test_scans import FINISHED, NOW, addon_source, listing, scan

from api import beta_check, context
from brownstone.pipeline import import_scans
from brownstone.today_settings import TodaySettings, save_settings, settings_path


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    data = tmp_path / 'data'
    path = write(tmp_path / 'scan.lua', [snapshot()], [
        rich('earlier', FINISHED - 3600), rich('complete', FINISHED),
        scan('partial', FINISHED + 1, [listing(2589, 1, 20)], reported=2)])
    source = addon_source(data, path, speed_min_pairs=1, speed_min_hours=1)
    import_scans(source, now=NOW)
    save_settings(settings_path(data, source['source_id']), TodaySettings(gold_copper=987, gold_override=True))
    (data / 'watchlist.my-scans.local.json').write_text('[]\n')
    (data / 'unrelated.other.local.json').write_text('{}\n')
    monkeypatch.setattr(context, 'enabled', lambda: [source])
    monkeypatch.setattr(beta_check, 'CORPUS_ROOT', tmp_path / 'work/beta-corpus')
    monkeypatch.setattr(beta_check.recipe_catalogs, 'find_catalogs', lambda _: [])
    return source, tmp_path / 'work/beta-corpus/frozen'


def test_freeze_check_differences_accept_and_read_only(corpus, capsys):
    source, folder = corpus
    data = source['data_dir']
    before = {p.relative_to(data): p.read_bytes() for p in data.rglob('*') if p.is_file()}
    assert beta_check.main(['freeze', str(folder), '--source', source['source_id']]) == 0
    manifest = json.loads((folder / 'manifest.json').read_text())
    expected = json.loads((folder / 'expected.json').read_text())
    assert manifest == dict(scan_count=3, eligible_scan_count=2, character_count=1,
                            newest_scan_id='complete', reference_time=datetime.fromtimestamp(FINISHED, UTC).isoformat(),
                            file_count=5, sha256=beta_check.hashes(folder))
    assert expected == {'data.eligible_scans': 2, 'data.newest_scan_id': 'complete', 'market.grid_rows': 0,
                        'market.chain_count': 0, 'today.route_steps': 0, 'today.planned_profit_copper': 0,
                        'team.characters': 1, 'ledger.team_net_copper': 0, 'ledger.reconciled_pairs': 0,
                        'item.2589.daily_units': 0, 'item.2589.suggested_units': 0}
    resolved = json.loads((folder / 'source.json').read_text())
    assert not {'scan_path', 'drop_folder', 'data_dir'} & resolved.keys()
    assert not (folder / 'unrelated.other.local.json').exists()
    assert (folder / settings_path(data, source['source_id']).name).read_bytes() == settings_path(
        data, source['source_id']).read_bytes()
    frozen = {p.relative_to(folder): p.read_bytes() for p in folder.rglob('*') if p.is_file()}
    capsys.readouterr()
    assert beta_check.main(['check', str(folder)]) == 0
    first = capsys.readouterr().out
    assert beta_check.main(['check', str(folder)]) == 0
    assert capsys.readouterr().out == first
    assert {p.relative_to(folder): p.read_bytes() for p in folder.rglob('*') if p.is_file()} == frozen
    expected['team.characters'] = 99
    (folder / 'expected.json').write_text(json.dumps(expected))
    assert beta_check.main(['check', str(folder)]) == 1
    assert 'team.characters: expected=99 actual=1 DIFFERENT' in capsys.readouterr().out
    assert beta_check.main(['check', str(folder), '--accept']) == 0
    assert json.loads((folder / 'expected.json').read_text())['team.characters'] == 1
    assert beta_check.hashes(folder) == manifest['sha256']
    assert (folder / 'manifest.json').read_bytes() == frozen[next(p for p in frozen if p.name == 'manifest.json')]
    assert beta_check.main(['freeze', str(folder), '--source', source['source_id']]) == 2
    assert 'File exists' in capsys.readouterr().out
    assert {p.relative_to(data): p.read_bytes() for p in data.rglob('*') if p.is_file()} == before


@pytest.mark.parametrize('damage', ['change', 'remove', 'during'])
def test_hash_damage_stops_before_replay_or_accept(corpus, monkeypatch, damage, capsys):
    source, folder = corpus
    beta_check.freeze(folder, source)
    path = next((folder / 'bronze').rglob('*.gz'))
    expected = (folder / 'expected.json').read_bytes()

    def replay(*args):
        assert damage == 'during', 'Hash verification must precede replay'
        path.write_bytes(b'changed during replay')
        return {}, {}

    monkeypatch.setattr(beta_check, 'headlines', replay)
    if damage == 'change':
        path.write_bytes(b'changed')
    elif damage == 'remove':
        path.unlink()
    assert beta_check.main(['check', str(folder), '--accept']) == 2
    assert 'hash mismatch' in capsys.readouterr().out
    assert (folder / 'expected.json').read_bytes() == expected


def test_finder_metadata_ignored_and_failed_freeze_removed(corpus, monkeypatch):
    source, folder = corpus
    beta_check.freeze(folder, source)
    (folder / 'bronze' / '.DS_Store').write_bytes(b'finder')
    assert beta_check.main(['check', str(folder)]) == 0
    again = folder.with_name('again')

    def broken(*args):
        raise ValueError('replay failed')

    monkeypatch.setattr(beta_check, 'headlines', broken)
    assert beta_check.main(['freeze', str(again), '--source', source['source_id']]) == 2
    assert not again.exists()
