"""Offline web contracts, source isolation, SPA routing and launch-token boundary."""
import json
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_market_explorer import explorer_fixture

import api
from api import context
from brownstone.markets import MARKET_KEYS
from brownstone.money import format_money


@pytest.fixture
def client(tmp_path, monkeypatch):
    source, catalog = explorer_fixture(tmp_path)
    from test_character_snapshots import snapshot, write
    from test_scans import NOW

    from brownstone.pipeline import import_scans
    import_scans(source, write(tmp_path / 'characters.lua', [snapshot(character='Scoped Maker')]), now=NOW)
    monkeypatch.setattr(context, 'datetime', SimpleNamespace(now=lambda zone: NOW + timedelta(days=2)))
    monkeypatch.setattr(context, 'enabled', lambda: [source])
    monkeypatch.setattr(context, '_cache', {})
    monkeypatch.setattr(context.recipe_catalogs, 'find_catalogs', lambda path: [])
    monkeypatch.setattr(context.recipe_catalogs, 'parse_catalogs', lambda paths: ([catalog], []))
    app = FastAPI()
    dist = tmp_path / 'dist'
    dist.mkdir()
    (dist / 'index.html').write_text('<html><head><!-- brownstone-token --></head></html>')
    (dist / 'asset.js').write_text('asset')
    api.install(app, dist, 'launch-secret')

    @app.post('/api/test', include_in_schema=False)
    def post():
        return {'ok': True}

    @app.delete('/api/test', include_in_schema=False)
    def delete():
        return {'ok': True}

    with TestClient(app) as browser:
        yield browser, source


def test_routes_use_existing_overview_and_null_missing_price(client):
    browser, source = client
    sources = browser.get('/api/sources').json()
    assert sources['selected']['source_id'] == source['source_id']
    assert sources['evidence']['scan_id']
    assert sources['evidence']['freshness']['stale']  # Two days past the fixture scan.
    assert sources['questions']['Market']
    assert browser.get('/api/search?q=2589').json()[0]['name'] == 'Linen Cloth'
    assert {r['item_id'] for r in browser.get('/api/search?q=linen').json()} == {2589, 2996, 2576}
    item = browser.get('/api/items/2589').json()
    assert item['price_copper'] == 11 and item['units'] == 11 and item['listings'] == 1
    assert item['evidence']['market_id'] == source['market_id']
    assert browser.get('/api/items/99999').json()['price_copper'] is None
    assert browser.get('/api/items/123456').json()['price_copper'] is None
    assert browser.get('/api/items/2996').json()['made_from']['profit_copper'] is None


@pytest.mark.parametrize('key', ['source_id', *MARKET_KEYS])
def test_every_route_excludes_another_source_or_full_market(client, monkeypatch, key):
    browser, source = client
    monkeypatch.setattr(context, 'enabled', lambda: [source | {key: 'another'}])
    assert browser.get('/api/search?q=linen').json() == []
    assert browser.get('/api/search?q=Scoped').json() == []
    assert browser.get('/api/sources').json()['evidence']['scan_id'] is None
    assert browser.get('/api/items/2589').json()['price_copper'] is None


def test_source_choice_disabled_unknown_and_experience_order(client, monkeypatch):
    browser, source = client
    monkeypatch.setattr(context, 'enabled', lambda: [source, source | {'source_id': 'second'}])
    assert browser.get('/api/sources').json()['selected'] is None
    assert browser.get('/api/items/2589').status_code == 409
    assert browser.get('/api/search?q=linen').status_code == 409
    assert browser.get('/api/items/2589?source=my-scans').status_code == 200
    assert browser.get('/api/sources?source=disabled').status_code == 404


def test_token_and_spa_routes(client, tmp_path):
    browser, _ = client
    assert browser.post('/api/test').status_code == 403
    assert browser.post('/api/test', headers={'X-Brownstone-Token': 'wrong'}).status_code == 403
    assert browser.post('/api/test', headers={'X-Brownstone-Token': 'launch-secret'}).json() == {'ok': True}
    assert browser.delete('/api/test').status_code == 403  # Every write method, not only POST.
    assert browser.delete('/api/test', headers={'X-Brownstone-Token': 'launch-secret'}).json() == {'ok': True}
    for path in ['/app', '/app/market', '/app/nested/route']:
        response = browser.get(path)
        assert response.status_code == 200
        assert 'name="brownstone-token" content="launch-secret"' in response.text
        assert response.headers['cache-control'] == 'no-store'
    assert browser.get('/app/asset.js').text == 'asset'
    other = FastAPI()
    api.install(other, tmp_path / 'missing')
    with TestClient(other) as absent:
        assert absent.get('/app').status_code == 503


def test_money_vectors_match_python():
    for row in json.loads(Path('tests/fixtures/money_vectors.json').read_text()):
        assert format_money(row['copper']) == row['text']


def test_enabled_experience_order(tmp_path, monkeypatch):
    from test_scans import addon_source
    source = addon_source(tmp_path)
    monkeypatch.setattr(context.config, 'read_sources', lambda *args: [
        source | {'game_version': 'retail'}, source | {'enabled': False}, source,
        source | {'game_version': 'classic'}])
    assert [s['game_version'] for s in context.enabled()] == ['forever', 'classic', 'retail']


def test_waiting_inventory_deduplicates_new_scans_and_reports_errors(monkeypatch):
    from types import SimpleNamespace

    from api import sources
    preview = SimpleNamespace(files=[
        SimpleNamespace(preview=SimpleNamespace(new_ids=['one', 'two']), error=''),
        SimpleNamespace(preview=SimpleNamespace(new_ids=['two']), error=''),
        SimpleNamespace(preview=None, error='file unreadable')])
    monkeypatch.setattr(sources.scan_inputs, 'preview_inputs', lambda source: preview)
    assert sources.waiting({'provider': 'addon', 'drop_folder': 'drops'}) == (2, 'file unreadable')
    assert sources.waiting({'provider': 'tsm'}) == (0, None)
    monkeypatch.setattr(sources.pipeline, 'preview_scans', lambda source: SimpleNamespace(new_ids=['one']))
    assert sources.waiting({'provider': 'addon'}) == (1, None)
    def broken(source):
        raise OSError('busy')
    monkeypatch.setattr(sources.pipeline, 'preview_scans', broken)
    count, error = sources.waiting({'provider': 'addon'})
    assert count is None and 'Open Data' in error


def test_search_returns_only_scoped_roster(client):
    browser, _ = client
    assert browser.get('/api/search?q=Scoped').json() == [
        {'kind': 'character', 'name': 'Scoped Maker · Beta · Alliance', 'item_id': None, 'quality': None,
         'variant_state': None, 'variant_id': None}]


def test_fast_shell_evidence_skips_inventory(client, monkeypatch):
    from api import sources
    browser, _ = client
    def no_inventory(source):
        raise AssertionError('Inventory should load independently')
    monkeypatch.setattr(sources, 'waiting', no_inventory)
    data = browser.get('/api/sources?inventory=false').json()
    assert data['selected'] and data['evidence']['scan_id'] and data['waiting'] is None
    assert list(context._cache) == [data['selected']['source_id']]  # Warmed for the first search.
    monkeypatch.setattr(context, 'explorer', lambda source: 1 / 0)
    assert browser.get('/api/sources?inventory=false').status_code == 200  # A failed warm-up is silent.


def test_search_retains_and_labels_captured_variant_identities(client, tmp_path):
    from test_scan_v3 import rich
    from test_scans import FINISHED, NOW, write_scans

    from brownstone.pipeline import import_scans

    browser, source = client
    import_scans(source, write_scans(tmp_path / 'variants.lua', rich(finished=FINISHED + 60)), now=NOW)
    hits = browser.get('/api/search?q=6538').json()
    assert len(hits) == 3
    assert len({(r['variant_state'], r['variant_id']) for r in hits}) == 3
    assert {r['quality'] for r in hits} == {2, None}


def test_explorer_is_reused_until_its_inputs_change(client, monkeypatch, tmp_path):
    from test_scan_v3 import rich
    from test_scans import FINISHED, NOW, write_scans

    from brownstone.pipeline import import_scans

    browser, source = client
    builds = []
    real = context.market_explorer.load_explorer
    monkeypatch.setattr(context.market_explorer, 'load_explorer', lambda *a: builds.append(1) or real(*a))
    browser.get('/api/search?q=linen')
    browser.get('/api/items/2589')
    assert len(builds) == 1  # Search and the item record share one build.
    import_scans(source, write_scans(tmp_path / 'later.lua', rich(finished=FINISHED + 60)), now=NOW)
    assert len(browser.get('/api/search?q=6538').json()) == 3  # A new import is visible at once.
    assert len(builds) == 2
    later = NOW + timedelta(days=2, minutes=context.CACHE_MINUTES)
    monkeypatch.setattr(context, 'datetime', SimpleNamespace(now=lambda zone: later))
    browser.get('/api/items/2589')
    assert len(builds) == 3  # Clock-dependent evidence is recomputed.
    other = source | {'source_id': 'second'}
    monkeypatch.setattr(context, 'enabled', lambda: [source, other])
    browser.get('/api/items/2589?source=second')
    assert len(builds) == 4  # Sources never share a cached projection.


def test_search_ranks_exact_id_and_prefix_first_and_caps_hits(client, monkeypatch):
    from api import market
    browser, _ = client
    assert browser.get('/api/search?q=2589').json()[0]['item_id'] == 2589
    names = [r['name'] for r in browser.get('/api/search?q=linen').json()]
    assert names[0] == 'Linen Cloth'  # Prefix before "Bolt of Linen Cloth".
    monkeypatch.setattr(market, 'SEARCH_LIMIT', 1)
    assert len(browser.get('/api/search?q=linen').json()) == 1
