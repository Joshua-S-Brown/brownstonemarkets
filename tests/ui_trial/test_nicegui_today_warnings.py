"""STORY-067: shared badges and honest evidence on cards, Sell and Queue posts."""
import pytest
from app_helpers import app
from nicegui import ui
from test_today_warnings import signal

from views.nicegui_today import today_warnings

pytestmark = pytest.mark.asyncio


async def test_warnings_on_each_output_surface(user, tmp_path, monkeypatch):
    app(tmp_path, monkeypatch)
    row_signal = signal(typical=1000) | {'min_buyout': 2000}
    monkeypatch.setattr('brownstone.flood_signals.signals', lambda *args: {'rows': [row_signal]})
    monkeypatch.setattr('views.nicegui_today.load_today_removals',
                        lambda *args: {3: {'pairs': 3, 'units': 0}})
    await user.open('/')
    await user.should_see('pricier than usual')
    await user.should_see('contested: many sellers')
    await user.should_see('no early removals in 3 scan gaps')
    await user.should_see('Low confidence')
    await user.should_see('priced at the typical earlier price, not the current lowest')
    for tab in ('Sell', 'Queue'):
        user.find(kind=ui.tab, content=tab).click()
        if tab == 'Sell':
            widget = user.find(kind=ui.table, marker='Sell').elements.pop()
            assert 'contested: many sellers' in widget.rows[0]['Warnings']
            user.find(kind=ui.table, marker='Sell').trigger('rowClick', [{}, widget.rows[0], 0])
        await user.should_see('pricier than usual')
        await user.should_see('contested: many sellers')
        await user.should_see('no early removals in 3 scan gaps')
        user.find('Listing evidence').elements.pop().open()
        await user.should_see('Lowest-buyout changes 3 / 5 comparable pairs')
        await user.should_see('Typical 10s · 3 days, 5 scans · current lowest 20s')
        user.find('Early-removal evidence').elements.pop().open()
        await user.should_see('0 removed early units in 3 scan gaps')
        await user.should_see('Classic assumptions pending a Forever check')
        await user.should_see('except a purchase replaced by an identical listing')
        if tab == 'Sell':
            user.find('Close').click()


async def test_thin_badge_and_two_gaps_or_one_removal_have_no_label(user):
    @ui.page('/warnings')
    def page():
        today_warnings({'signal': signal(label='cheap', crowding='thin'),
                        'early_removals': {'pairs': 2, 'units': 0}})
        today_warnings({'signal': signal(label='typical', crowding='steady'),
                        'early_removals': {'pairs': 3, 'units': 1}})
    await user.open('/warnings')
    await user.should_see('thin: few listings')
    await user.should_see('cheap right now')
    await user.should_not_see('no early removals in')


async def test_failed_today_signal_read_is_explicit(user, tmp_path, monkeypatch):
    app(tmp_path, monkeypatch)
    def broken(*args, **kwargs):
        raise ValueError('unreadable signals')
    monkeypatch.setattr('brownstone.flood_signals.signals', broken)
    await user.open('/')
    await user.should_see('Unable to build Today: unreadable signals')


async def test_session_reuses_one_today_flood_read(user, tmp_path, monkeypatch):
    from unittest.mock import Mock

    from brownstone import flood_signals
    app(tmp_path, monkeypatch)
    spy = Mock(wraps=flood_signals.signals)
    monkeypatch.setattr(flood_signals, 'signals', spy)
    await user.open('/')
    await user.should_see('This session')
    assert spy.call_count == 1
    user.find(marker='session-view').elements.pop().set_value('This session')
    await user.should_see('No scoped Today characters imported')
    assert spy.call_count == 1
