"""STORY-078 item decisions, fallbacks and disclosures through the offline app."""
from copy import deepcopy

import pytest
from nicegui import ui
from test_farming import loot

from brownstone import market_explorer as me
from brownstone.today import TODAY_VERSION

from .test_nicegui_market import market_app

pytestmark = pytest.mark.asyncio


def labels(element):
    return [e.text for e in element.descendants() if isinstance(e, ui.label)]


def summary_labels(user):
    return labels(next(iter(user.find(marker='item-summary').elements)))


async def test_summary_figures_base_only_best_material_output_and_refresh(user, tmp_path, monkeypatch):
    market_app(tmp_path, monkeypatch)
    original = me.load_explorer
    def evidence(*args):
        result = original(*args)
        result['vendors'][2589] = 5
        result['catalogs'][0]['items_by_id'][2589]['vendor_price_copper'] = 8
        for row in result['recipes']:
            row['value']['profit_copper'] = 123 if row['recipe']['output_item_id'] == 2996 else 456
        cheaper = deepcopy(result['recipes'][0])
        cheaper['value']['profit_copper'] = 1
        unknown = deepcopy(cheaper)
        unknown['value'].update(profit_copper=None, action='missing prices')
        result['recipes'].extend([cheaper, unknown])
        for row in result['items'] + result['metrics']:
            if row['item_id'] == 2589:
                row['variant_state'] = 'base'
        variant = deepcopy(next(r for r in result['items'] if r['item_id'] == 2589))
        variant.update(variant_state='variant', variant_id='suffix', min_buyout=99999)
        result['items'].append(variant)
        return result
    monkeypatch.setattr(me, 'load_explorer', evidence)
    version = TODAY_VERSION
    await user.open('/?place=Market&item=2589')
    await user.should_see('Best use in our catalogs')
    texts = summary_labels(user)
    assert '11c' in texts and '10c' in texts  # newest price and earlier typical
    assert '99999' not in ' '.join(texts)
    assert 'Used in · Profit per craft: 1s 23c' in texts
    assert '11' in texts and '1' in texts
    assert '8c' in texts and '5c' in texts
    panels = next(e for e in user.find(ui.tab_panels).elements)
    assert panels.value == 'Summary'
    names = [
        e._props['name'] for e in sorted(user.find(ui.tab).elements, key=lambda e: e.id)]
    assert names == ['Summary', 'Crafting', 'Market', 'Identity and evidence']
    panels.set_value('Crafting')
    await user.open('/?place=Market&item=2996')
    await user.should_see('Best use in our catalogs')
    texts = summary_labels(user)
    assert 'Used in · Profit per craft: 4s 56c' in texts
    assert 'Made from · Profit per craft: 1s 23c' in texts
    assert next(iter(user.find(ui.tab_panels).elements)).value == 'Summary'
    assert version == TODAY_VERSION


async def test_unknown_fallbacks_non_catalog_no_profit_and_no_gathering(user, tmp_path, monkeypatch):
    market_app(tmp_path, monkeypatch, count=1)
    await user.open('/?place=Market&item=99999')
    await user.should_see('Best use in our catalogs')
    texts = summary_labels(user)
    assert 'typical unknown' in texts and 'unknown' in texts
    assert 'unknown' in texts and not any(t.startswith('at least') for t in texts)
    assert any('no profitable use known · No compatible catalog recipe' in t for t in texts)
    assert any('No character captures' in t for t in texts)
    await user.should_see('not gathered yet')
    assert next(e for e in user.find(ui.link).elements if e.text == 'Wowhead drop sources and places'
                )._props['href'] == 'https://www.wowhead.com/forever/item=99999'
    await user.open('/?place=Market&item=123456')
    await user.should_see('Best use in our catalogs')
    assert 'Not listed in this snapshot' in summary_labels(user)
    await user.open('/?place=Market&item=2996')
    await user.should_see('Best use in our catalogs')
    assert any('no profitable use known · Intermediate: no Action Board profit row' in t
               for t in summary_labels(user))


async def test_holdings_farming_all_characters_item_filter_and_lazy_reads(user, tmp_path, monkeypatch):
    from test_character_snapshots import snapshot

    from brownstone import team_holdings

    config, _ = market_app(tmp_path, monkeypatch)
    # Use the shared capture composition, including a partial bag and uncaptured bank.
    from test_scans import NOW
    record = snapshot('bag', 'bags', 'Holder')
    record['slots'] = [{'item_id': 2589, 'count': 7,
                        'item_link': '|Hitem:2589:0:0:0:0:0:0:0:0:0:0:0:0|h[Linen Cloth]|h|r'}]
    record['slots'].append({'item_id': 2589, 'count': 99,
                            'item_link': '|Hitem:2589::::::::6:1482:::1:12721::::::|h[Variant]|h|r'})
    record['complete'] = False
    data = {('Holder', 'Realm', 'Alliance'): {'bags': (record, 'pc'), 'observations': [(record, 'pc')]}}
    calls = []
    def held(*args):
        calls.append('holdings')
        return team_holdings.holdings(data, NOW), None
    monkeypatch.setattr(me, '_load_holdings', held)
    history = me.farming.history
    def tracked_history(*args):
        calls.append('farming')
        return history(*args)
    monkeypatch.setattr(me.farming, 'history', tracked_history)
    original = me.load_explorer
    def result(*args):
        value = original(*args)
        observations = loot(0, item=2589) + loot(150, item=2589) + loot(300, item=2589)
        observations += loot(1000, item=2996, map_id=1430) + loot(1150, item=2996, map_id=1430)
        observations += loot(1300, item=2996, map_id=1430)
        value['characters'] = {('Alpha', 'Realm', 'Alliance'): {'observations': observations},
                               ('Beta', 'Realm', 'Alliance'): {'observations': observations}}
        return value
    monkeypatch.setattr(me, 'load_explorer', result)
    signal = me.item_floods
    def floods(*args):
        calls.append('signal')
        return signal(*args)
    monkeypatch.setattr(me, 'item_floods', floods)
    await user.open('/?place=Market')
    await user.should_see('What moved since the last scan')
    assert calls == []
    await user.open('/?place=Market&item=2589')
    await user.should_see('Where to get it')
    assert calls == ['signal', 'holdings', 'farming', 'farming']
    assert 'at least 7' in summary_labels(user)
    await user.should_see('Holder · bank not captured')
    await user.should_see('Holder · Realm · bags: 7')
    await user.should_see('h old')
    await user.should_see('Alpha · Realm · Alliance')
    await user.should_see('Beta · Realm · Alliance')
    await user.should_see('36 units/hour')
    tables = list(user.find(ui.table).elements)
    assert len(tables) == 2
    assert all(len(t.rows) == 1 and t.rows[0]['Zone'] == 'Arbitrary zone' for t in tables)
    for element in user.find(marker='session-farming').elements:
        assert not any('Item 2996' in t for t in labels(element))
    await user.should_not_see(marker='market-floods')
    await user.should_not_see(marker='market-removals')
    await user.open('/?place=Market')
    await user.should_see('What moved since the last scan')
    assert user.find(marker='market-floods').elements
    assert user.find(marker='market-removals').elements
    await user.should_see('What moved since the last scan')


async def test_removal_three_newest_skipped_count_and_show_all(user, tmp_path, monkeypatch):
    market_app(tmp_path, monkeypatch, count=6)
    original = me.item_removals
    def removals(*args):
        history = original(*args)
        history['pairs'].insert(1, history['pairs'][0] | {'skipped': True})
        return history
    monkeypatch.setattr(me, 'item_removals', removals)
    await user.open('/?place=Market&item=2589&origin_place=Today&origin_tab=Plan&origin_view=This+session')
    await user.should_see('← Back to Today · This session')
    await user.should_see('Removed between scans')
    history = next(iter(user.find(marker='item-removals').elements))
    expansion = next(e for e in history.descendants() if isinstance(e, ui.expansion)
                     and e._props['label'] == 'Show all scan gaps')
    hidden = set(expansion.descendants())
    headings = [e for e in history.descendants() if isinstance(e, ui.label) and 'UTC →' in e.text]
    assert len([e for e in headings if e not in hidden]) == 3
    assert len([e for e in headings if e in hidden]) == 2
    assert '1 skipped gap (over 12 hours)' in labels(history)
    assert not any('Skipped:' in t for t in labels(history))
    expansion.set_value(True)  # The offline harness does not emulate Quasar expansion toggles.
    assert expansion.value is True
