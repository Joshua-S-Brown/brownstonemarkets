"""Surviving native places redirect Today URLs and preserve source/view origins."""
from urllib.parse import parse_qs, urlsplit

import pytest
from app_helpers import team_app

from views.nicegui_navigation import read_origin, today_url

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize('view,tab,expected', [('', '', 'route'), ('This session', 'Buy', 'level-up'),
    ('Today plan', 'Craft', 'opportunities'), ('route', '', 'route'), ('opportunities', '', 'opportunities'),
    ('level-up', '', 'level-up'), ('bad', 'Queue', 'route')])
async def test_today_default_and_legacy_urls(user, tmp_path, monkeypatch, view, tab, expected):
    source, _, _ = team_app(tmp_path, monkeypatch)
    targets = []
    monkeypatch.setattr(user.navigate, 'to', targets.append)
    await user.open('/?' + __import__('urllib.parse', fromlist=['urlencode']).urlencode(
        {'source': source['source_id'], 'view': view, 'tab': tab}))
    await user.should_see('Brownstone')
    assert urlsplit(targets[-1]).path == '/app/today'
    assert parse_qs(urlsplit(targets[-1]).query) == {'source': ['test'], 'view': [expected]}


async def test_team_back_to_today_keeps_source_view_and_character_out_of_url(user, tmp_path, monkeypatch):
    source, _, _ = team_app(tmp_path, monkeypatch)
    await user.open('/?place=Team&origin_place=Today&origin_tab=Queue&origin_view=This+session')
    await user.should_see('← Back to Today · This session')
    target = user.find(marker='back-link').elements.pop().props['href']
    assert target == '/app/today?source=test&view=level-up'
    assert 'character' not in parse_qs(urlsplit(target).query)
    assert read_origin('Today', 'unknown', 'This session', '', '') == {}
    assert today_url(source, 'unknown', 'unknown').endswith('view=route')
