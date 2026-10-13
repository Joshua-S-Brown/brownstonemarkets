"""Native STORY-015b labels, warnings and existing session reset over offline team routes."""
from copy import deepcopy

import pytest
from nicegui import ui
from test_action_board import observed
from test_recipe_graph import TAILOR, chain, evidence
from test_today import MARKET, NOW, SNAPSHOT

from brownstone.today import build_today
from brownstone.today_session import plan_context
from brownstone.today_settings import TodaySettings
from views import nicegui_today as view
from views import today_rows as wording

pytestmark = pytest.mark.asyncio


def arguments():
    catalogs = chain()
    return dict(catalogs=catalogs, observations=observed({1: 5, 2: 100, 3: 1000, 4: 10000}),
                market=MARKET, snapshot=SNAPSHOT, now=NOW, max_age_hours=24, auction_cut=.05,
                settings=TodaySettings(1000, 1, 'fixed', max_crafts=1, character=TAILOR),
                character_data=evidence(catalogs))


async def test_plan_and_queue_name_makers_before_consumers(user):
    args = arguments()
    plan = build_today(**args)
    @ui.page('/graph-labels')
    def page():
        view.craft_card(plan['craft'][0], plan['sell'][0])
        view.queue_panel(plan, {})
    await user.open('/graph-labels')
    await user.should_see('Copper Bar · Keenagen, Mining')
    await user.should_see('Buckle · Armorer, Blacksmithing')
    await user.should_see('postage is unconfirmed')
    boxes = sorted(user.find(ui.checkbox).elements, key=lambda e: e.id)
    crafts = [b.text for b in boxes if b.text.startswith('Craft:')]
    assert 'Copper Bar' in crafts[0] and 'Keenagen, Mining' in crafts[0]
    assert 'Buckle' in crafts[1] and 'Armorer, Blacksmithing' in crafts[1]
    assert 'Belt' in crafts[2] and 'Basilly, Tailoring' in crafts[2]


async def test_pre_change_plan_choices_and_ticks_reset_with_existing_note(user, monkeypatch):
    args = arguments()
    import brownstone.today_session as identity
    monkeypatch.setattr(identity, 'TODAY_VERSION', 5)
    old_context = plan_context(args)
    monkeypatch.setattr(identity, 'TODAY_VERSION', 6)
    session = {'context': old_context, 'choices': [{'catalog_id': 'tailor', 'recipe_id': 30, 'batch_size': None}],
               'rows': [], 'refill': False, 'ticks': {'0': True}}
    @ui.page('/graph-reset')
    def page():
        view.session_plan(args, session, ui.label(''))
    await user.open('/graph-reset')
    await user.should_see(wording.PLAN_RESET)
    assert session['choices'] is None and session['ticks'] == {} and session['refill']
    assert session['rows'][0]['recipe_id'] == 30


async def test_no_maker_bought_label_and_catalog_warning_on_plan(user):
    args = arguments()
    args['character_data'].pop(next(c for c in args['character_data'] if c[0] == 'Keenagen'))
    # Keep the smith output available so its bought-bar explanation is directly visible.
    args['settings'] = TodaySettings(1000, 1, 'fixed', max_crafts=1,
                                     character=next(c for c in args['character_data'] if c[0] == 'Armorer'))
    plan = build_today(**args)
    conflicting = deepcopy(args)
    conflicting['catalogs'][0]['items_by_id'][2]['availability'] = 'post-launch'
    conflicting['catalogs'][1]['items_by_id'][2]['availability'] = 'available'
    @ui.page('/graph-warnings')
    def page():
        view.craft_card(plan['craft'][0], plan['sell'][0])
        view.session_plan(conflicting, {}, ui.label(''))
    await user.open('/graph-warnings')
    await user.should_see('Copper Bar · no one on the team makes this')
    await user.should_see('Item 2: disagreeing route fields in catalogs mining, smith; buy-only')


async def test_team_displays_collision_refusal(user, tmp_path, monkeypatch):
    from .test_nicegui_team import team_app
    _, catalog, _ = team_app(tmp_path, monkeypatch)
    duplicate = deepcopy(catalog)
    monkeypatch.setattr('brownstone.recipe_catalogs.find_catalogs', lambda *args: [
        {'name': 'fixture', 'catalog': catalog}, {'name': 'duplicate', 'catalog': duplicate}])
    await user.open('/?place=Team')
    await user.should_see('Unable to build Team routes: Recipe ID 30 collides in catalogs duplicate and fixture')


async def test_team_displays_shared_item_catalog_warning(user, tmp_path, monkeypatch):
    from test_recipe_graph import make_catalog

    from .test_nicegui_team import team_app
    _, catalog, _ = team_app(tmp_path, monkeypatch)
    mining = make_catalog('mining', 'mining', 50, 2, [(1, 1)])
    mining['items_by_id'][2]['availability'] = 'post-launch'
    catalog['items_by_id'][2]['availability'] = 'available'
    monkeypatch.setattr('brownstone.recipe_catalogs.find_catalogs', lambda *args: [
        {'name': 'fixture', 'catalog': catalog}, {'name': 'mining', 'catalog': mining}])
    await user.open('/?place=Team')
    await user.should_see('Item 2: disagreeing route fields in catalogs fixture, mining; buy-only')
