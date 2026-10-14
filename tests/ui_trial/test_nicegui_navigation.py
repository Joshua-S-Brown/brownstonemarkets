"""STORY-076: URL return paths through the offline app harness."""
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from nicegui import app, ui
from test_farming import loot

from .test_nicegui_market import market_app
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
    await user.open(target)
    await user.should_see('← Back to Today · This session')
    await user.open(target)  # refresh
    await user.should_see('← Back to Today · This session')
    await user.should_see('Find an item')
    user.find(marker='market-search').type('3')
    await user.should_see('matches')
    chain = next(e._props['href'] for e in user.find(ui.link).elements if 'item=3&' in e._props['href'])
    await user.open(chain)
    await user.should_see('← Back to Today · This session')
    back = href(user)
    assert parse_qs(urlsplit(back).query)['tab'] == ['Shopping list']
    await user.open(back)
    await user.should_see('units/hour')
    await user.should_see('Details for')
    await user.open(back)
    await user.should_see('units/hour')
    assert user.find(marker='session-view').elements.pop().value == 'This session'
    assert not any('back-link' in e._markers for e in user.client.elements.values())


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
    await user.open(widget.rows[0]['_item_url'])
    await user.should_see('← Back to Today · Sell')
    await user.open(href(user))
    await user.should_see('This session')
    assert user.find(marker='session-view').elements.pop().value == 'Today plan'
    assert next(iter(user.find(ui.tabs).elements)).value == 'Sell'


async def test_market_item_chain_returns_to_first_item(user, tmp_path, monkeypatch):
    market_app(tmp_path, monkeypatch)
    await user.open('/?place=Market&item=2996')
    await user.should_see('Made from')
    assert not any('back-link' in e._markers for e in user.client.elements.values())
    await user.open(href(user, 'Linen Cloth'))
    await user.should_see('← Back to Market · Bolt of Linen Cloth')
    await user.should_see('Used in')
    await user.open(href(user, 'Bolt of Linen Cloth'))
    await user.should_see('← Back to Market · Bolt of Linen Cloth')
    back = href(user)
    assert parse_qs(urlsplit(back).query)['item'] == ['2996']
    await user.open(back)
    await user.should_see('Made from')
    assert not any('back-link' in e._markers for e in user.client.elements.values())


@pytest.mark.parametrize('origin', [dict(origin_place='Elsewhere'),
    dict(origin_place='Today', origin_tab='Bad', origin_view='This session'),
    dict(origin_place='Today', origin_tab='Plan', origin_view='Bad'),
    dict(origin_place='Market', origin_item='oops', origin_name='Bad'),
    dict(origin_place='Market', origin_item='9' * 4400, origin_name='Bad'), {}])
async def test_invalid_direct_and_place_tab_clear_origin(user, tmp_path, monkeypatch, origin):
    team_app(tmp_path, monkeypatch)
    await user.open('/?' + urlencode(dict(place='Market', item=1, **origin)))
    await user.should_see('Find an item')
    assert not any('back-link' in e._markers for e in user.client.elements.values())
    await user.open('/?place=Team&origin_place=Today&origin_tab=Plan&origin_view=This+session')
    await user.should_see('← Back to Today · This session')
    user.find(marker='place-Market').click()
    await user.should_see('Find an item')
    assert not any('back-link' in e._markers for e in user.client.elements.values())


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
    assert parse_qs(urlsplit(targets[-1]).query)['view'] == ['This session']
    next(e for e in user.find(ui.select).elements if e.props.get('label') == 'Data source').set_value('other')
    query = parse_qs(urlsplit(targets[-1]).query)
    assert query['source'] == ['other'] and 'view' not in query
