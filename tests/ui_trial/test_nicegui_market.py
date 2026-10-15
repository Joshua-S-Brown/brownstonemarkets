"""Market display, navigation and refresh using NiceGUI's offline user fixture."""
import pytest
from nicegui import ui
from test_market_explorer import explorer_fixture

pytestmark = pytest.mark.asyncio


def market_app(tmp_path, monkeypatch, count=2):
    config, catalog = explorer_fixture(tmp_path, count)
    config['flood_min_days'] = 1
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
    await user.should_not_see('What moved since the last scan')
    await user.open('/?place=Market')
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


async def test_removed_list_item_history_evidence_and_lazy_loading(user, tmp_path, monkeypatch):
    import duckdb

    from brownstone import market_explorer as me
    config, _ = market_app(tmp_path, monkeypatch)
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb')) as db:
        db.execute("UPDATE scan_listings SET time_left=4 WHERE scan_id='scan-0'")
    calls = []
    original = me.item_removals
    def tracked(config, item_id):
        calls.append(item_id)
        return original(config, item_id)
    monkeypatch.setattr(me, 'item_removals', tracked)
    await user.open('/?place=Market')
    assert calls == []
    await user.should_see('Removed early in our chains')
    await user.should_see('Removed early: 1 listings · 10 units')
    linen = next(e for e in user.find(ui.link).elements if e.text == 'Linen Cloth')
    await user.open(linen._props['href'])
    await user.should_see('Removed between scans')
    assert calls == [2589]
    await user.should_see('Could have expired: 0 listings · 0 units')
    await user.should_see('Time left unknown: 0 listings · 0 units')
    await user.should_see('Listings without a buyout (excluded): earlier 0 · later 0')
    user.find('Matching evidence').click()
    await user.should_see('whole-stack buyout 1s')
    assert not any('sold' in e.text.casefold() for e in user.find(ui.label).elements)
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb')) as db:
        db.execute("UPDATE addon_scans SET finished_at=finished_at - INTERVAL 12 HOURS WHERE scan_id='scan-0'")
    await user.open('/?place=Market&item=2589')
    await user.should_see('1 skipped gap (over 12 hours)')
    await user.open('/?place=Market')
    await user.should_see('Gap too long: no consecutive scans within 12 hours')
    await user.open('/?place=Market&item=99999')
    await user.should_see('Removed between scans')


async def test_removed_list_one_scan_and_tsm_explanations(user, tmp_path, monkeypatch):
    config, _ = market_app(tmp_path, monkeypatch, count=1)
    await user.open('/?place=Market&item=2589')
    await user.should_see('Fewer than two eligible scans')
    monkeypatch.setattr('brownstone.config.read_sources', lambda *args: [config | {'provider': 'tsm'}])
    await user.open('/?place=Market&item=2589')
    await user.should_see('TSM source: no addon scan pairs')


async def test_removed_history_failure_keeps_item_page(user, tmp_path, monkeypatch):
    from brownstone import market_explorer as me
    market_app(tmp_path, monkeypatch)
    def broken(config, item_id):
        raise RuntimeError('locked')
    monkeypatch.setattr(me, 'item_removals', broken)
    await user.open('/?place=Market&item=2589')
    await user.should_see('Unable to read removed listings: locked')
    await user.should_see('Made from')


async def test_flood_lists_links_counts_roles_settings_stale_and_lazy_item(user, tmp_path, monkeypatch):
    import duckdb

    from brownstone import market_explorer as me
    config, _ = market_app(tmp_path, monkeypatch, count=6)
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb')) as db:
        db.execute("UPDATE scan_metrics SET listings=10, min_buyout=6 "
                   "WHERE scan_id='scan-5' AND item_id=2589")
        db.execute("UPDATE scan_metrics SET listings=3, min_buyout=200 WHERE scan_id='scan-5' AND item_id=2996")
    calls = []
    original = me.item_floods
    def tracked(config, item_id, now):
        calls.append(item_id)
        return original(config, item_id, now)
    monkeypatch.setattr(me, 'item_floods', tracked)
    await user.open('/?place=Market')
    assert calls == []
    await user.should_see('Most contested')
    await user.should_see('Biggest overshoots · cheap and high')
    await user.should_see('cheap')
    await user.should_see('high')
    await user.should_see('Thin items (≤ 2 listings) are left out here; their item pages still flag them.')
    await user.should_see('material / output')
    await user.should_see('Typical: earlier 7 days · at least 1 distinct UTC days · cheap ≤ 60% · high ≥ 150%.')
    await user.should_see('Stale')
    linen = next(e for e in user.find(ui.link).elements if e.text == 'Linen Cloth')
    await user.open(linen._props['href'])
    await user.should_see('Crowding and overshoots')
    assert calls == [2589]
    await user.should_see('contested')
    await user.should_see('10 listings · 15 units listed · largest stack 15/15 units (100.0%)')
    await user.should_see('Lowest buyout changed: 5/5 comparable pairs')
    await user.should_see('50.0% of typical')
    await user.open('/?place=Market&item=99999')
    await user.should_see('too few days')
    await user.should_see('Outside catalog chains')
    await user.open('/?place=Market&item=123456')
    await user.should_see('Not listed in the newest eligible scan; no flood signal.')


async def test_flood_failure_preserves_item_and_one_scan_unknown_churn(user, tmp_path, monkeypatch):
    from brownstone import market_explorer as me
    market_app(tmp_path, monkeypatch, count=1)
    await user.open('/?place=Market&item=2589')
    await user.should_see('Lowest buyout churn unknown: no comparable pairs')
    await user.should_see('too few days')
    def broken(*args):
        raise RuntimeError('locked')
    monkeypatch.setattr(me, 'item_floods', broken)
    await user.open('/?place=Market&item=2589')
    await user.should_see('Best use in our catalogs')
    await user.should_see('Unable to read flood signals: locked')
    await user.should_see('not gathered yet')
    await user.should_see('Wowhead drop sources and places')
    await user.should_see('Used in')
