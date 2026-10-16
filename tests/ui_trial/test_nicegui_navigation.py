"""STORY-076: URL return paths through the offline app harness."""
from urllib.parse import parse_qs, urlsplit

import pytest
from nicegui import app, ui
from test_farming import loot

from .test_nicegui_team import team_app

pytestmark = pytest.mark.asyncio


def href(user, text=None):
    return next(e._props['href'] for e in user.find(ui.link).elements
                if e.text == text) if text else user.find(marker='back-link').elements.pop()._props['href']


async def open_session(user, tmp_path, monkeypatch):
    config, _, data = team_app(tmp_path, monkeypatch)
    next(iter(data.values()))['observations'] = loot(0, item=1) + loot(150, item=1) + loot(300, item=1)
    await user.open('/?place=Today&tab=Shopping+list&view=This+session')
    await user.should_see('units/hour')
    return config


async def test_session_farming_back_chain_refresh_loaded(user, tmp_path, monkeypatch):
    config = await open_session(user, tmp_path, monkeypatch)
    link = next(e for farming in user.find(marker='session-farming').elements
                for e in farming.descendants() if isinstance(e, ui.link))
    target = link._props['href']
    query = parse_qs(urlsplit(target).query)
    assert query['origin_view'] == ['This session']
    assert query['origin_tab'] == ['Shopping list']
    assert query['source'] == [config['source_id']]
    assert urlsplit(target).path == '/app/market'
    assert query['inspect'] == ['1']


async def test_session_team_back_preserves_character_choices(user, tmp_path, monkeypatch):
    config = await open_session(user, tmp_path, monkeypatch)
    from views.nicegui_today import read_saved_settings
    before = read_saved_settings(config)
    link = next(e for e in user.find(ui.link).elements if e.text == 'Keenagen')
    target = link._props['href']
    user.find(kind=ui.link, content='Keenagen').click()
    await user.should_see('← Back to Today · This session')
    await user.should_see('Progression')
    assert 'character' not in parse_qs(urlsplit(target).query)
    with user.client:
        assert app.storage.tab['team-test']['character'][0] == 'Keenagen'
        selected = list(app.storage.tab['team-test']['character'])
    await user.open(href(user))
    await user.should_see('Details for')
    with user.client:
        assert app.storage.tab['team-test']['character'] == selected
    assert read_saved_settings(config) == before


async def test_plan_table_card_tab_view_changes_and_back(user, tmp_path, monkeypatch):
    team_app(tmp_path, monkeypatch)
    await user.open('/?place=Today&view=Today+plan')
    await user.should_see('This session')
    card = next(iter(user.find(marker='craft-card').elements))
    assert any(isinstance(e, ui.link) for e in card.descendants())
    user.find(marker='plan-display').elements.pop().set_value('Table')
    widget = user.find(kind=ui.table, marker='Craft').elements.pop()
    assert ':href="props.row._item_url"' in widget.slots['body-cell-Item'].template
    tabs = next(e for e in user.find(ui.tabs).elements)
    tabs.set_value('Sell')
    sell = user.find(kind=ui.table, marker='Sell').elements.pop()
    target = sell.rows[0]['_item_url']
    assert parse_qs(urlsplit(target).query)['origin_tab'] == ['Sell']
    user.find(marker='session-view').elements.pop().set_value('This session')
    await user.should_see('Details for')
    assert parse_qs(urlsplit(sell.rows[0]['_item_url']).query)['origin_view'] == ['This session']
    user.find(marker='session-view').elements.pop().set_value('Today plan')
    assert urlsplit(widget.rows[0]['_item_url']).path == '/app/market'
    assert parse_qs(urlsplit(target).query)['inspect']


async def test_toggle_replaces_url_and_refresh_loads_view(user, tmp_path, monkeypatch):
    team_app(tmp_path, monkeypatch)
    changes = []
    await user.open('/?place=Today&tab=Buy')
    await user.should_see('This session')
    monkeypatch.setattr(ui.navigate.history, 'replace', changes.append)
    user.find(marker='session-view').elements.pop().set_value('This session')
    await user.should_see('Details for')
    target = changes[-1]
    assert parse_qs(urlsplit(target).query)['tab'] == ['Shopping list']
    assert parse_qs(urlsplit(target).query)['view'] == ['This session']
    await user.open(target)
    await user.should_see('Details for')
    assert user.find(marker='session-view').elements.pop().value == 'This session'
    monkeypatch.setattr(ui.navigate.history, 'replace', changes.append)
    user.find(marker='session-view').elements.pop().set_value('Today plan')
    assert parse_qs(urlsplit(changes[-1]).query)['view'] == ['Today plan']


async def test_source_switch_keeps_each_source_view(user, tmp_path, monkeypatch):
    config, _, _ = team_app(tmp_path, monkeypatch)
    monkeypatch.setattr('brownstone.config.read_sources', lambda *args: [config, config | {'source_id': 'other'}])
    await user.open(f"/?game={config['game_version']}&source={config['source_id']}&place=Today&view=This+session")
    await user.should_see('Details for')
    targets = []
    monkeypatch.setattr(ui.navigate, 'to', targets.append)
    user.find(marker='place-Market').click()
    assert urlsplit(targets[-1]).path == '/app/market'
    assert parse_qs(urlsplit(targets[-1]).query)['source'] == [config['source_id']]
    next(e for e in user.find(ui.select).elements if e.props.get('label') == 'Data source').set_value('other')
    query = parse_qs(urlsplit(targets[-1]).query)
    assert query['source'] == ['other'] and 'view' not in query
