"""STORY-060 contracts through NiceGUI's offline user fixture."""
from dataclasses import replace

import pytest
from nicegui import app as native_app
from nicegui import ui
from test_today_view import app

from brownstone.today_settings import load_settings, save_settings
from views import nicegui_theme as theme

pytestmark = pytest.mark.asyncio


async def ready(user):
    await user.should_see('recipes hidden')


async def test_info_dialog_retains_provenance_gold_hidden_and_limits(user, tmp_path, monkeypatch):
    _, source, _ = app(tmp_path, monkeypatch, stale=True)
    await user.open('/')
    await ready(user)
    await user.should_not_see('Today rules v6')
    user.find(marker='page-info').click()
    await user.should_see('How this plan was made')
    await user.should_see('Today rules v6')
    await user.should_see(f"source {source['source_id']}")
    await user.should_see(f"market {source['market_id']}")
    await user.should_see('5% auction cut')
    await user.should_see('cautious output price')
    await user.should_see('snapshot')
    await user.should_see('evidence')
    await user.should_see('Gold available: 10g')
    await user.should_see('Hidden recipes:')
    await user.should_see("more rows outside this list's 10-row limit")
    assert any(d.value for d in user.find(ui.dialog).elements)


async def test_settings_dialog_cancel_scaled_visibility_and_save(user, tmp_path, monkeypatch):
    _, _, path = app(tmp_path, monkeypatch)
    before = path.read_bytes()
    await user.open('/')
    await ready(user)
    user.find(marker='page-settings').click()
    user.find(kind=ui.input, content='Gold available').clear().type('15g')
    assert path.read_bytes() == before
    user.find('Cancel').click()
    user.find(marker='page-settings').click()
    gold = next(iter(user.find(kind=ui.input, content='Gold available').elements))
    assert gold.value == '10g'
    mode = next(e for e in user.find(ui.select).elements if e.label == 'Minimum gain mode')
    percent = next(e for e in user.client.elements.values()
                   if isinstance(e, ui.number) and e.label == 'Percentage of gold available')
    assert mode.value == 'fixed' and not percent.visible
    mode.set_value('scaled')
    assert percent.visible
    percent.set_value(2.5)
    user.find('Enter an amount instead').click()
    user.find(kind=ui.input, content='Gold available').clear().type('15g')
    user.find('Save Today settings').click()
    await user.should_see('Today settings saved locally.')
    saved = load_settings(path)
    assert saved.gold_copper == 150000 and saved.mode == 'scaled'
    assert saved.percent_basis_points == 250 and saved.gold_override
    assert not next(iter(user.find(ui.dialog).elements)).value


@pytest.mark.parametrize('field,value', [('Gold available', '12'), ('Most crafts per item', 1.5),
                                        ('Percentage of gold available', 101)])
async def test_settings_dialog_rejection_preserves_saved_plan(user, tmp_path, monkeypatch, field, value):
    _, _, path = app(tmp_path, monkeypatch)
    before = path.read_bytes()
    await user.open('/')
    await ready(user)
    user.find(marker='page-settings').click()
    if field == 'Gold available':
        user.find(kind=ui.input, content=field).clear().type(value)
    else:
        if field == 'Percentage of gold available':
            next(e for e in user.find(ui.select).elements if e.label == 'Minimum gain mode').set_value('scaled')
        next(e for e in user.find(ui.number).elements if e.label == field).set_value(value)
    user.find('Save Today settings').click()
    await user.should_see('Settings not saved')
    assert path.read_bytes() == before
    assert next(iter(user.find(ui.dialog).elements)).value
    assert user.find(marker='craft-card').elements


async def test_empty_state_names_reasons_and_opens_both_dialogs(user, tmp_path, monkeypatch):
    _, _, path = app(tmp_path, monkeypatch)
    save_settings(path, replace(load_settings(path), minimum_copper=9990000))
    await user.open('/')
    await user.should_see('No craft clears your settings today')
    await user.should_see('999g minimum batch gain')
    await user.should_see('below minimum gain')
    user.find('See all reasons').click()
    await user.should_see('Hidden recipes: below minimum gain: 1')
    user.find('Review settings').click()
    assert any(d.value for d in user.find(ui.dialog).elements)
    await user.should_see('Minimum gain mode')


async def test_shared_light_theme_native_selection_and_scan_help(user, tmp_path, monkeypatch):
    app(tmp_path, monkeypatch, stale=True)
    await user.open('/')
    await ready(user)
    assert native_app.native.window_args['text_select'] is True
    assert next(iter(user.find(ui.dark_mode).elements)).value is False
    await user.should_not_see(kind=ui.left_drawer)
    assert '--ground:#F6F3EF' in theme.CSS and 'min-height:44px' in theme.CSS
    user.find('How to scan').click()
    await user.should_see('run /bscan')
    await user.should_see("Don't /bscan clear")


async def test_data_info_dialog_and_status_chips(user, tmp_path, monkeypatch):
    from test_app import preview_addon

    _, source = preview_addon(tmp_path, monkeypatch)
    await user.open('/?place=Data')
    await user.should_see('Check for new scans')
    await user.should_see('scans imported')
    await user.should_see('Drop folder')
    await user.should_not_see(f"source_id: {source['source_id']}")
    user.find(marker='page-info').click()
    await user.should_see(f"source_id: {source['source_id']}")
    await user.should_see('Partial scans are preserved but never feed prices')
