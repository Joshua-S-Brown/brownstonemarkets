"""API error boundaries, shared explorer cache and repeatable overrides."""
import pytest
from test_web_api import client as client


def test_outputs_route_cache_and_contract(client, monkeypatch):
    browser, source = client
    from api import context
    calls = []
    original = context.market_explorer.load_explorer
    def load(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)
    monkeypatch.setattr(context.market_explorer, 'load_explorer', load)
    assert browser.get('/api/chains?q=2996').json()['hits'][0]['recipe_id'] == 2963
    r = browser.get('/api/chains/route?catalog_id=tailoring&recipe_id=2393').json()
    assert r['source_evidence']['source_id'] == source['source_id']
    assert r['max_crafts'] == 5
    assert isinstance(r['spend_copper'], int)
    assert r['nodes'][0]['held'] is None or isinstance(r['nodes'][0]['held'], int)
    r = browser.get('/api/chains/route?catalog_id=tailoring&recipe_id=2393&force=2996:buy&force=2320:vendor').json()
    assert next(n for n in r['nodes'] if n['item_id'] == 2996)['method'] == 'buy'
    assert len(calls) == 1


@pytest.mark.parametrize('args,status', [
    ('catalog_id=missing&recipe_id=2393', 404), ('catalog_id=tailoring&recipe_id=999', 404),
    ('catalog_id=tailoring&recipe_id=2393&batch=0', 422),
    ('catalog_id=tailoring&recipe_id=2393&batch=6', 422),
    ('catalog_id=tailoring&recipe_id=2393&batch=1.5', 422),
    ('catalog_id=tailoring&recipe_id=2393&force=2576:buy', 422),
    ('catalog_id=tailoring&recipe_id=2393&force=999:buy', 422),
    ('catalog_id=tailoring&recipe_id=2393&force=2996:vendor', 422),
    ('catalog_id=tailoring&recipe_id=2393&force=bad', 422),
    ('catalog_id=tailoring&recipe_id=2393&force=2996:buy&force=2996:craft', 422),
])
def test_bad_recipe_force_and_batch(client, args, status):
    browser, _ = client
    assert browser.get('/api/chains/route?' + args).status_code == status


def test_source_and_market_compatibility(client, monkeypatch):
    browser, source = client
    from api import context
    assert browser.get('/api/chains?source=another').status_code == 404
    monkeypatch.setattr(context, 'enabled', lambda: [source | {'rules_version': 'other'}])
    result = browser.get('/api/chains').json()
    assert result['scan_at']
    assert result['ranked'] == result['hits'] == [] and result['hit_count'] == 0
    assert browser.get('/api/chains/route?catalog_id=tailoring&recipe_id=2393').status_code == 404
