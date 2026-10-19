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
    assert not ({'reference', 'beta_typical_copper', 'beta_ratio', 'beta_faded'} & item.keys())
    assert not any(key.startswith('beta_') for key in item['details'])
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
    assert sources.waiting({'provider': 'addon', 'drop_folder': 'drops'}) == (None, 'file unreadable')
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
        {'character': ['Scoped Maker', 'Beta', 'Alliance'],
         'role': None, 'kind': 'character', 'name': 'Scoped Maker', 'item_id': None, 'quality': None,
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
    monkeypatch.setattr(context.market_explorer, 'load_explorer', lambda *a, **k: builds.append(1) or real(*a, **k))
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


def test_market_grid_catalog_roles_prices_sparkline_and_lazy_item_reads(client, monkeypatch):
    from brownstone import item_history as ih
    from brownstone import market_explorer as me
    browser, _ = client
    def forbidden(*args):
        raise AssertionError('Item-only history/holdings must not load on Market home')
    monkeypatch.setattr(ih, 'load_history', forbidden)
    from brownstone import sales_speed
    monkeypatch.setattr(sales_speed, 'load', forbidden)
    monkeypatch.setattr(me, 'item_summary', forbidden)
    assert browser.get('/api/market').json()['rows'] == []  # No captured profession ranks.
    assert browser.get('/api/market?window=4').status_code == 422
    page = browser.get('/api/market?role=all').json()
    assert 'reference' not in page
    assert all(not ({'beta_typical_copper', 'beta_ratio', 'beta_faded'} & row.keys())
               for row in page['rows'])
    rows = {r['item_id']: r for r in page['rows']}
    assert rows[2589]['price_copper'] == 11
    assert rows[2589]['sparkline'] == [10, 11]
    assert rows[2589]['roles'] == ['materials']
    assert rows[2996]['roles'] == ['materials', 'crafts', 'intermediates']
    assert rows[2576]['roles'] == ['crafts']
    outside = browser.get('/api/market?q=99999').json()['rows'][0]
    assert outside['price_copper'] is None and outside['roles'] == []
    assert outside['gap_copper'] is None
    assert outside['sparkline'] == [None, None]  # Noncatalog history is included in the same batch.
    assert page['movement']['rows'][0]['change']['min_buyout'] == 1
    assert page['evidence']['source_id']


def test_history_ladder_picker_gaps_no_buyout_errors_and_chain_routes(client, monkeypatch):
    from brownstone import item_history as ih
    browser, _ = client
    history = browser.get('/api/items/2589/history').json()
    assert [p['metrics']['min_buyout'] for p in history['points']] == [10, 11]
    assert history['points'][0]['finished_at'].endswith('+00:00')
    assert history['removals']['pairs'] and history['removals_error'] is None
    newest = browser.get('/api/items/2589/ladder').json()
    assert newest['rows'] == [dict(price_copper=11, listings=1, units=11, cumulative_units=11)]
    assert newest['zoom_copper'] == 11
    assert browser.get('/api/items/2589/ladder?scan=scan-0').json()['rows'][0]['units'] == 10
    assert browser.get('/api/items/2589/ladder?scan=foreign').status_code == 400
    unpriced = browser.get('/api/items/99999/ladder').json()
    assert unpriced['no_buyout_listings'] == 1 and unpriced['no_buyout_units'] == 1
    assert unpriced['rows'] == [] and unpriced['zoom_copper'] is None
    assert all(p['metrics'] is None for p in browser.get('/api/items/123456/history').json()['points'])
    shirt = browser.get('/api/items/2576/chain').json()
    assert [r['item_id'] for r in shirt['made_from'][0]['materials']] == [2996, 2589, 2320, 2324]
    assert shirt['made_from'][0]['materials'][1]['quantity'] == 2
    assert shirt['made_from'][0]['materials'][1]['depth'] == 1
    bolt = browser.get('/api/items/2996/chain').json()
    assert bolt['made_from'][0]['profit_copper'] is None
    assert 'Intermediate' in bolt['made_from'][0]['reason']
    assert bolt['best_uses'][0]['action'] == 'craft into White Linen Shirt'
    assert bolt['best_uses'][0]['value_copper'] == 1865
    assert bolt['best_uses'][0]['eligibility'] == 'nobody on the team knows it'
    assert bolt['used_in'][0]['quantity'] == 1 and bolt['demand']
    assert bolt['used_in'][0]['characters'][0]['craft_status'] == 'Unknown'
    assert not browser.get('/api/items/99999/chain').json()['in_chain']
    def broken(*args):
        raise OSError('locked fixture')
    monkeypatch.setattr(ih, 'load_ladder', broken)
    assert browser.get('/api/items/2589/ladder').status_code == 503
    monkeypatch.setattr(ih, 'load_history', broken)
    assert 'Use Data' in browser.get('/api/items/2589/history').json()['detail']
    assert browser.get('/api/items/2589').status_code == 200


@pytest.mark.parametrize('key', ['source_id', *MARKET_KEYS])
def test_new_market_endpoints_never_cross_scope(client, monkeypatch, key):
    browser, source = client
    monkeypatch.setattr(context, 'enabled', lambda: [source | {key: 'foreign'}])
    assert browser.get('/api/market').json()['rows'] == []
    assert browser.get('/api/items/2589/history').json()['points'] == []
    assert browser.get('/api/items/2589/ladder').status_code == 400
    activity = browser.get('/api/items/2589/activity').json()
    assert activity['held'] is None and activity['your_sales'] == [] and activity['farming'] == []


def test_selected_variant_prices_units_quality_and_refresh_never_use_base(client, tmp_path):
    from test_scan_v3 import rich
    from test_scans import FINISHED, NOW, write_scans

    from brownstone.pipeline import import_scans
    browser, source = client
    import_scans(source, write_scans(tmp_path / 'variants.lua', rich(finished=FINISHED + 60)), now=NOW)
    hits = browser.get('/api/search?q=6538').json()
    values = []
    for hit in hits:
        identity = json.dumps([hit['variant_state'], hit['variant_id']])
        item = browser.get('/api/items/6538', params={'variant': identity}).json()
        parents = browser.get('/api/market?q=6538').json()['rows']
        identities = [r for parent in parents for r in [parent, *parent['variants']]]
        row = next(r for r in identities
                   if r['item_id'] == 6538 and r['variant_id'] == hit['variant_id'] and
                   r['variant_state'] == hit['variant_state'])
        assert (item['price_copper'], item['units'], item['quality']) == (
            row['price_copper'], row['units'], row['quality'])
        values.append(item['price_copper'])
    assert len(set(values)) > 1
    assert browser.get('/api/items/6538', params={'variant': '["variant", "not-observed"]'}).json()[
        'price_copper'] is None
    for invalid in ['invalid', '{}', 'null', '["unsupported", null]', '["base", 1]']:
        assert browser.get('/api/items/6538', params={'variant': invalid}).status_code == 400


def test_activity_sales_holdings_failures_and_farming_preserve_other_evidence(client, monkeypatch):
    from test_farming import mob_loot, named_window
    from test_sales import invoice, posted, returned

    from brownstone import market_explorer as me
    from brownstone import sales
    browser, source = client
    result = context.explorer(source)
    result['characters'] = {('Alpha', 'Realm', 'Alliance'): {'observations':
        mob_loot(0, 475) + mob_loot(150, 475) + mob_loot(300, 475) + [named_window(400)]}}
    data = sales.project([*posted(), invoice(), returned(at=2200), invoice(name='Unknown', at=2300)],
                         {2589: {'Linen Cloth'}})
    monkeypatch.setattr(me.sales, 'load', lambda c: data)
    activity = browser.get('/api/items/2589/activity').json()
    assert activity['your_sales'][0]['sold'] == 5 and activity['your_sales'][0]['expired'] == 1
    assert activity['unidentified_sales'] == 1
    assert activity['farming'][0]['farming']['rows'][0]['units_per_hour'] == 36
    spot = activity['farming'][0]['farming']['spots'][0]
    assert spot['mob'] == 'Kobold Tunneler (NPC 475)' and spot['mob_name'] == 'Kobold Tunneler'
    assert activity['wowhead_url'] == 'https://www.wowhead.com/forever/item=2589'
    def broken(*args):
        raise OSError('busy fixture')
    monkeypatch.setattr(me.sales, 'load', broken)
    monkeypatch.setattr(me, 'item_floods', broken)
    item = browser.get('/api/items/2589').json()
    assert item['price_copper'] == 11 and 'busy fixture' in item['details']['floods_error']
    assert item['speed']['pairs'] == 1 and item['speed']['daily_units'] is None
    from brownstone import sales_speed
    monkeypatch.setattr(sales_speed, 'load', broken)
    assert browser.get('/api/items/2589').json()['speed'] is None
    assert 'busy fixture' in browser.get('/api/items/2589/activity').json()['sales_error']
    monkeypatch.setattr(me, 'item_removals', broken)
    h = browser.get('/api/items/2589/history').json()
    assert 'busy fixture' in h['removals_error'] and len(h['points']) == 2


def test_market_pulse_matches_shared_lists_and_reads_batch_once(tmp_path, monkeypatch):
    import duckdb
    from test_scans import NOW

    from brownstone import item_history as ih
    from brownstone import market_explorer as me
    source, catalog = explorer_fixture(tmp_path, count=6)
    source['flood_min_days'] = 1
    with duckdb.connect(str(source['data_dir'] / 'brownstone.duckdb')) as db:
        db.execute("UPDATE scan_metrics SET listings=10,min_buyout=6 WHERE scan_id='scan-5' AND item_id=2589")
        db.execute("UPDATE scan_metrics SET listings=5,units=10,min_buyout=200 WHERE scan_id='scan-5' AND item_id=2996")
        db.execute("UPDATE scan_listings SET time_left=4 WHERE scan_id='scan-4'")
    calls = []
    real = ih._metrics_by_scan
    def tracked(*args):
        calls.append(args[-1])
        return real(*args)
    monkeypatch.setattr(ih, '_metrics_by_scan', tracked)
    r = me.load_explorer(source, [catalog], NOW)
    assert len(calls) == 1 and set(calls[0]) == {item['item_id'] for item in r['items']}
    assert r['market']['pulse']['cheap'] + r['market']['pulse']['high'] == r['floods']['overshoots']
    assert r['market']['pulse']['early'] == r['removals']['rows']
    assert r['market']['pulse']['cheap'][0]['item_id'] == 2589
    assert r['market']['pulse']['high'][0]['item_id'] == 2996
    assert r['market']['pulse']['early'][0]['early']['units'] == 14
    assert r['market']['movement']['comparison']['gap'].total_seconds() == 3600


def test_summary_best_use_vendor_prices_and_holdings_keep_exact_base(client, monkeypatch):
    from copy import deepcopy

    from brownstone import market_explorer as me
    browser, source = client
    r = context.explorer(source)
    r['vendors'][2589] = 5
    r['stack_sizes'][2589] = 20
    r['catalogs'][0]['items_by_id'][2589]['vendor_price_copper'] = 8
    for recipe in r['recipes']:
        recipe['value']['profit_copper'] = 123 if recipe['recipe']['output_item_id'] == 2996 else 456
    row = deepcopy(r['recipes'][0])
    row['value'].update(profit_copper=None, action='missing prices')
    r['recipes'].append(row)
    for observed in r['items'] + r['metrics']:
        if observed['item_id'] == 2589:
            observed['variant_state'] = 'base'
    variant = deepcopy(next(i for i in r['items'] if i['item_id'] == 2589))
    variant.update(variant_id='suffix', variant_state='variant', min_buyout=99999)
    r['items'].append(variant)
    captures = [{'unknown': True, 'partial': True}]
    monkeypatch.setattr(me, '_load_holdings', lambda *a: (({(2589, None, 'base'): 7,
        (2589, 'suffix', 'variant'): 99}, {}, captures, []), None))
    item = browser.get('/api/items/2589').json()
    assert item['price_copper'] == 11 and item['held'] == 7 and item['at_least']
    assert item['vendor_buy'] == [8] and item['vendor_sell'] == 5
    assert item['role'] == 'Material' and item['deposit_copper'] == 100
    assert item['used_in']['profit_copper'] == 123
    assert len(item['details']['identities']) == 2
    selected = browser.get('/api/items/2589', params={'variant': '["variant", "suffix"]'}).json()
    assert selected['price_copper'] == 99999 and selected['held'] is None
    assert selected['used_in']['profit_copper'] is None


def test_web_tab_presence_follows_socket_lifetime_and_requires_source(client):
    from fastapi import WebSocketDisconnect

    from api import presence
    browser, source = client
    assert not presence.connected
    with browser.websocket_connect('/api/presence?source=' + source['source_id']):
        assert len(presence.connected) == 1
    assert not presence.connected
    with pytest.raises(WebSocketDisconnect), browser.websocket_connect('/api/presence?source=disabled'):
        pass
    assert not presence.connected


def test_market_cache_rebuilds_on_config_file_and_source_setting_change(client, monkeypatch, tmp_path):
    browser, source = client
    monkeypatch.setattr(context, 'ROOT', tmp_path)
    folder = tmp_path / 'config'
    folder.mkdir()
    builds = []
    real = context.market_explorer.load_explorer
    monkeypatch.setattr(context.market_explorer, 'load_explorer', lambda *a, **k: builds.append(1) or real(*a, **k))
    browser.get('/api/market')
    browser.get('/api/market')
    assert len(builds) == 1
    (folder / 'evidence.toml').write_text('changed = true')
    browser.get('/api/market')
    assert len(builds) == 2
    source['flood_min_days'] = 1
    browser.get('/api/market')
    assert len(builds) == 3


def test_source_short_label_keeps_configured_menu_label(client):
    from brownstone import navigation

    browser, source = client
    selected = browser.get('/api/sources?inventory=false').json()['selected']
    assert selected['short_label'] == navigation.source_label(source)
    assert selected['label'] == (source.get('label') or navigation.source_label(source))


def test_search_role_uses_catalog_evidence_and_joins_disagreements():
    from brownstone.market_explorer import search_items, search_role

    catalogs = [{'items_by_id': {1: {'role': 'finished'}, 2: {'role': 'intermediate'}}},
                {'items_by_id': {1: {'role': 'material'}, 3: {'role': 'vendor_material'}}}]
    assert search_role(catalogs, 1) == 'Craft · Material'
    assert search_role(catalogs, 2) == 'Intermediate'
    assert search_role(catalogs, 3) is None
    assert search_role(catalogs, 999) is None
    result = {'catalogs': catalogs, 'items': [{'item_id': 1, 'item_name': 'Cloth', 'variant_state': 'variant',
                                            'variant_id': 'exact-key'}]}
    assert search_items(result, 'cloth') == [result['items'][0] | {'role': 'Craft · Material'}]


def test_market_api_server_sort_role_filter_and_card_contract(client):
    browser, _ = client
    page = browser.get('/api/market?role=all').json()
    assert page['item_count'] > page['listed_chain_count']
    assert page['identity_count'] >= page['item_count']
    assert all(len(card['preview']) <= 3 for card in page['cards'].values())
    assert all(not r['variants'] for r in page['rows'])
    crafts = browser.get('/api/market?role=crafts&sort=name&descending=false').json()['rows']
    assert {r['item_id'] for r in crafts} == {2996, 2576}
    assert [r['name'] for r in crafts] == sorted(r['name'] for r in crafts)
    rows = browser.get('/api/market?sort=price_copper&descending=true').json()['rows']
    assert [r['price_copper'] for r in rows] == sorted((r['price_copper'] for r in rows), reverse=True)
