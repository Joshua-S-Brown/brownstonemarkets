"""Market display, navigation and refresh using NiceGUI's offline user fixture."""
import pytest
from nicegui import ui
from test_market_explorer import explorer_fixture

pytestmark = pytest.mark.asyncio


def market_app(tmp_path, monkeypatch, count=2):
    config, catalog = explorer_fixture(tmp_path, count)
    monkeypatch.setattr('brownstone.config.read_sources', lambda *args: [config])
    monkeypatch.setattr('brownstone.recipe_catalogs.find_catalogs',
                        lambda *args: [{'name': 'tailoring', 'catalog': catalog}])
    monkeypatch.setattr('brownstone.recipe_catalogs.parse_catalogs', lambda *args: ([catalog], []))
    return config, catalog


async def test_search_item_sections_walk_and_url_refresh(user, tmp_path, monkeypatch):
    config, _ = market_app(tmp_path, monkeypatch)
    await user.open('/?place=Market&item=2996')
    await user.should_see('Made from')
    await user.should_see('Used in')
    await user.should_see('Skill-up demand')
    await user.should_see('Intermediate: no Action Board profit row')
    await user.should_see('Team: Unknown')
    user.find(marker='market-search').type('2589')
    user.find(marker='market-search-button').click()
    await user.should_see('1 matches')
    links = sorted(user.find(ui.link).elements, key=lambda e: e.id)
    linen = next(e for e in links if e.text == 'Linen Cloth')
    assert 'item=2589' in linen._props['href']
    await user.open(linen._props['href'])
    await user.should_see('No compatible recipe makes this item')
    links = sorted(user.find(ui.link).elements, key=lambda e: e.id)
    bolt = next(e for e in links if e.text == 'Bolt of Linen Cloth')
    await user.open(bolt._props['href'])
    await user.should_see('Made from')
    assert user.client.request.query_params['item'] == '2996'
    await user.open(str(user.client.request.url.path) + '?' + str(user.client.request.query_params))
    await user.should_see('Made from')
    user.find(marker='page-info').click()
    await user.should_see('Market evidence')
    await user.should_see(f"Source {config['source_id']}")
    await user.should_see('Snapshot my-scans:scan-1')


async def test_unpriced_non_catalog_absent_stale_and_movement(user, tmp_path, monkeypatch):
    market_app(tmp_path, monkeypatch)
    await user.open('/?place=Market&item=99999')
    await user.should_see('This item is in no compatible catalog')
    await user.should_see('unknown')
    assert not any(e.text == '0c' for e in user.find(ui.label).elements)
    await user.should_see('Lowest buyout change: +1c · units change: +1')
    await user.should_see('historical')
    user.find(marker='market-search').type('Unpriced')
    await user.should_see('1 matches')
    await user.open('/?place=Market&item=123456')
    await user.should_see('Not listed in this snapshot')
    from datetime import timedelta

    from test_scans import NOW

    from brownstone import market_explorer as me
    original = me.load_explorer
    monkeypatch.setattr(me, 'load_explorer', lambda c, cs, now: original(c, cs, NOW + timedelta(days=2)))
    await user.open('/?place=Market')
    await user.should_see('Stale')


async def test_one_scan_tsm_empty_and_error_states(user, tmp_path, monkeypatch):
    config, _ = market_app(tmp_path, monkeypatch, count=1)
    await user.open('/?place=Market')
    await user.should_see('No earlier scan')
    monkeypatch.setattr('brownstone.config.read_sources', lambda *args: [config | {'provider': 'tsm'}])
    await user.open('/?place=Market')
    await user.should_see('TSM source: no scan comparison')
    monkeypatch.setattr('brownstone.config.read_sources', lambda *args: [config | {'source_id': 'another'}])
    await user.open('/?place=Market')
    await user.should_see('No saved snapshot for this source and market')
    from brownstone import market_explorer as me
    def broken(*args):
        raise OSError('fixture unreadable')
    monkeypatch.setattr(me, 'load_explorer', broken)
    await user.open('/?place=Market')
    await user.should_see('Unable to read Market evidence: fixture unreadable')


async def test_nested_routes_board_missing_reason_and_incompatible_evidence(user, tmp_path, monkeypatch):
    config, catalog = market_app(tmp_path, monkeypatch)
    await user.open('/?place=Market&item=2576')
    await user.should_see('craft')
    await user.should_see('22c total')
    # One named nested material retains indentation and a link back to its page.
    link = next(e for e in user.find(ui.link).elements if e.text == 'Linen Cloth')
    assert 'item=2589' in link._props['href']
    await user.should_see('stale data')
    from brownstone import market_explorer as me
    original = me.load_explorer
    def missing(*args):
        result = original(*args)
        row = next(r for r in result['recipes'] if r['recipe']['output_item_id'] == 2576)
        row['value'].update(profit_copper=None, action='missing prices')
        return result
    monkeypatch.setattr(me, 'load_explorer', missing)
    await user.open('/?place=Market&item=2576')
    await user.should_see('Profit per craft: unknown')
    await user.should_see('missing prices')
    monkeypatch.setattr(me, 'load_explorer', original)
    catalog['rules_version'] = 'incompatible-fixture'
    await user.open('/?place=Market&item=2576')
    await user.should_see('No compatible catalogs')
    await user.should_see('Price evidence only')
    user.find(marker='page-info').click()
    await user.should_see('incompatible-fixture')
    await user.should_see(f"does not match {config['game_version']} / {config['rules_version']}; unpriced")
