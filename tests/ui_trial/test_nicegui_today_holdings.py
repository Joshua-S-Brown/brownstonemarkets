"""STORY-068 uses held evidence in cards, Sell, capture labels and the copied Queue."""
import pytest
from app_helpers import app
from nicegui import ui
from test_today_characters import state
from test_today_holdings import evidence

from views import nicegui_today

pytestmark = pytest.mark.asyncio


async def test_held_material_output_and_unknown_bank_ui(user, tmp_path, monkeypatch):
    app(tmp_path, monkeypatch)
    monkeypatch.setattr('brownstone.professions.latest_data',
                        lambda config: {('Arille', 'realm', 'alliance'): state(learned=True)})
    original = nicegui_today.load_today
    def loaded(*args, **kwargs):
        manifest, arguments = original(*args, **kwargs)
        arguments['holdings_data'] = evidence((1, 2, 'Basilly', 'bags'), (3, 2, 'Basilly', 'bags'),
                                               age=30, unknown_bank=True)
        return manifest, arguments
    monkeypatch.setattr(nicegui_today, 'load_today', loaded)
    await user.open('/')
    for text in ('bank not captured', '30.0 hours old', 'held count from a stale capture'):
        await user.should_see(text)
    user.find(kind=ui.expansion, content='What to buy and where to sell').trigger('update:modelValue', True)
    materials = next(t for t in user.client.elements.values() if isinstance(t, ui.table) if 'Reserved' in t._markers)
    assert next(r for r in materials.rows if r['Where'] == 'Held')['Cost'] == 'worth 18c if sold'
    buy = next(t for t in user.client.elements.values() if isinstance(t, ui.table) if 'Buy' in t._markers)
    assert all(r['Route'] != 'held' for r in buy.rows)
    sell = next(t for t in user.client.elements.values() if isinstance(t, ui.table) if 'Sell' in t._markers)
    assert sell.rows[0]['Held units'] == 2
    assert sell.rows[0]['Held by'] == 'Basilly (bags): 2'
    assert 'Held units' in [c['name'] for c in sell.columns]
    for text in ('Basilly: take 2 Fixture 1 from the bags', 'Basilly mails 2 Fixture 1 to Arille',
                 'post 5 crafted + 2 held', 'postage is unconfirmed'):
        await user.should_see(text)


async def test_unreadable_holdings_warning_still_plans(user, tmp_path, monkeypatch):
    app(tmp_path, monkeypatch)
    monkeypatch.setattr('brownstone.character_snapshots.latest_data',
                        lambda config: (_ for _ in ()).throw(ValueError('bad capture')))
    await user.open('/')
    await user.should_see('Unable to read held items: bad capture. Planning as if nothing is held.')
    await user.should_not_see('Unable to build Today')
