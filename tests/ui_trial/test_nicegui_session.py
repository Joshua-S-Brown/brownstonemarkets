"""Native session toggle, scoped links, limits and Team reach-window reuse."""
from datetime import UTC, datetime

import pytest
from app_helpers import app as today_app
from nicegui import app, ui

from brownstone.freshness import assess
from brownstone.today_loading import load_today
from brownstone.today_settings import TodaySettings

from .test_nicegui_team import team_app

pytestmark = pytest.mark.asyncio


def labels(monkeypatch, source):
    from brownstone.flood_signals import settings
    now = datetime.now(UTC)
    rows = [{'item_id': i, 'variant_state': 'base', 'variant_id': None, 'crowding': crowding,
             'listings': 12, 'units': 20, 'largest_stack_units': 5, 'min_buyout': 10,
             'churn': {'changed': 3, 'pairs': 5},
             'overshoot': {'label': 'cheap', 'typical_copper': 30, 'scans': 5, 'days': 3}}
            for i, crowding in [(1, 'thin'), (3, 'contested')]]
    monkeypatch.setattr('brownstone.flood_signals.signals', lambda *args: {
        'rows': rows, 'settings': settings({}), 'note': '',
        'scan': {'scan_id': 'label-scan', 'snapshot_id': 'label-snapshot', 'finished_at': now},
        'freshness': assess({'updated_at': now.isoformat()}, now, 24)})


async def test_toggle_team_window_labels_links_and_plan_retained(user, tmp_path, monkeypatch):
    source, c, data = team_app(tmp_path, monkeypatch)
    labels(monkeypatch, source)
    await user.open('/')
    await user.should_see('This session')
    user.find(marker='plan-display').elements.pop().set_value('Table')
    original = [e.rows for e in user.find(kind=ui.table, marker='Craft').elements]
    with user.client:
        app.storage.tab.setdefault('team-test', {}).update(window=5)
    user.find(marker='session-view').elements.pop().set_value('This session')
    await user.should_see('Craft ')
    await user.should_see('Details for')
    await user.should_see('Reach window 5 points')
    await user.should_see('Crafting to sell')
    await user.should_see('Levelling professions')
    await user.should_see('contested')
    await user.should_see('thin')
    await user.should_see('cheap')
    user.find('How these options were made').click()
    await user.should_see('label-scan')
    await user.should_see('Not enough farming history')
    assert len(user.find(marker='session-character').elements) == 2
    await user.should_see('Recipe 33')
    await user.should_not_see('Recipe 31')
    links = user.find(ui.link).elements
    assert any('place=Market' in e._props['href'] and 'item=3' in e._props['href'] for e in links)
    assert any('place=Team' in e._props['href'] for e in links)
    user.find(marker='session-view').elements.pop().set_value('Today plan')
    assert [e.rows for e in user.find(kind=ui.table, marker='Craft').elements] == original
    user.find(marker='session-view').elements.pop().set_value('This session')
    user.find(kind=ui.link, content='Keenagen').click()
    with user.client:
        assert app.storage.tab['team-test']['character'][0] == 'Keenagen'


async def test_cap_missing_prices_and_incomplete_render(user, tmp_path, monkeypatch):
    source, c, data = team_app(tmp_path, monkeypatch)
    first = next(iter(data.values()))
    first['recipes']['Arbitrary title']['known_recipes']['max_rank'] = 8
    first['bags']['skills']['modern']['rows'][0]['max_rank'] = 8
    c['recipes_by_id'][30].pop('skillup_colors')
    await user.open('/')
    await user.should_see('This session')
    user.find(marker='session-view').elements.pop().set_value('This session')
    await user.should_see('capped')
    await user.should_see('incomplete: Rank 3')
    await user.should_see('cheap auction materials unknown')


async def test_empty_team_and_failed_signal_read(user, tmp_path, monkeypatch):
    today_app(tmp_path, monkeypatch, stale=True)
    await user.open('/')
    await user.should_see('This session')
    user.find(marker='session-view').elements.pop().set_value('This session')
    await user.should_see('No scoped Today characters imported')
    await user.should_see('stale — inspect only')
    await user.should_see('TSM source: no addon flood signals.')
    assert user.find(marker='session-view').elements.pop().value != 'Today plan'
    source, c, data = team_app(tmp_path, monkeypatch)
    def broken(*args, **kwargs):
        raise ValueError('unreadable signals')
    await user.open('/')
    await user.should_see('This session')
    monkeypatch.setattr('views.nicegui_today.build_options', broken)
    user.find(marker='session-view').elements.pop().set_value('This session')
    await user.should_see('Unable to build session options: unreadable signals')


async def test_no_list_unknown_prices_and_reasons(user, tmp_path, monkeypatch):
    source, c, data = team_app(tmp_path, monkeypatch)
    data[('NoList', 'Beta', 'Alliance')] = {'recipes': {}, 'seen': {}, 'bags': {},
        'history': [], 'observations': []}
    from brownstone.pipeline import run
    csv = tmp_path / 'missing.csv'
    csv.write_text('itemId,name,marketValue,minBuyout,recent,historical,updatedAt\n1,Material,0,0,0,0,\n')
    run(source, csv)
    await user.open('/')
    await user.should_see('This session')
    user.find(marker='session-view').elements.pop().set_value('This session')
    await user.should_see('No profession list reported.')
    await user.should_see('missing prices')
    await user.should_see('missing material price')
    await user.should_see('profit per craft unknown')
    assert len(user.find(marker='session-character').elements) == 3
    _, args = load_today(source, [c], TodaySettings(), data, datetime.now(UTC))
    assert args['observations'][1]['min_buyout'] == 0


async def test_no_buyout_churn_unknown_evidence(user):
    from views.nicegui_today import session_signal
    @ui.page('/signal')
    def page():
        session_signal({'crowding': 'thin', 'listings': 1, 'units': 2, 'largest_stack_units': 2,
                        'min_buyout': 0, 'churn': {'changed': 0, 'pairs': 0},
                        'overshoot': {'label': 'no buyout', 'typical_copper': 100, 'scans': 5, 'days': 3}})
        session_signal(None)
    await user.open('/signal')
    await user.should_see('thin')
    await user.should_see('no buyout')
    user.find('Listing evidence').click()
    await user.should_see('Lowest-buyout churn unknown')
    await user.should_see('current lowest unknown')
    await user.should_see('Listing / relative-price evidence unavailable')


async def test_step_text_every_kind():
    from views.nicegui_today import step_text
    tier = {'name': 'Journeyman', 'cap': 75, 'required_level': 10, 'level_ok': False}
    group = {'profession': 'Tailoring', 'rank': 8, 'capped': False}
    recipe = {'name': 'Brown Linen Pants', 'required_skill': 30, 'profit_copper': 187,
              'estimate': {'cost_copper': 989, 'cheap_cost_copper': 989}}
    character = {'character': ('Basilly', 'Realm', 'Alliance'), 'level': 6, 'craft_profit_copper': 12501,
                 'crafts': [{'batch_size': 3, 'output_name': 'White Linen Shirt'}]}
    lines = [step_text(s, character, 25) for s in [
        {'kind': 'craft'}, {'kind': 'level_profession', 'group': group, 'recipe': recipe, 'more': 5},
        {'kind': 'level_character', 'group': group, 'tier': tier},
        {'kind': 'train', 'group': group | {'capped': True}, 'tier': tier | {'level_ok': True}},
        {'kind': 'nothing'}, {'kind': 'evidence'}]]
    assert lines[0] == 'Craft 3 White Linen Shirt · planned profit 1g 25s 1c'
    assert lines[1] == ('Level Tailoring 8 → 30 for 9s 89c, all on materials that are cheap right now · '
                        'unlocks Brown Linen Pants at 1s 87c per craft (+5 more on the way)')
    assert lines[2] == 'Before Tailoring reaches 75: level Basilly 6 → 10 to train Journeyman'
    assert lines[3] == 'Tailoring is capped at 75: train Journeyman Tailoring at a trainer'
    assert 'within 25 points' in lines[4] and 'Gathering is an option' in lines[4]
    assert 'open each profession window' in lines[5]
    capped = step_text({'kind': 'level_character', 'group': group | {'capped': True}, 'tier': tier},
                       character | {'level': None}, 25)
    assert capped == 'Tailoring is capped at 75: level Basilly to 10 (level unknown) to train Journeyman'
    partial = recipe | {'estimate': {'cost_copper': 989, 'cheap_cost_copper': 100}}
    assert '1s of it on cheap auction materials' in step_text(
        {'kind': 'level_profession', 'group': group, 'recipe': partial, 'more': 0}, character, 25)
    none = recipe | {'estimate': {'cost_copper': 989, 'cheap_cost_copper': 0}}
    assert 'no cheap auction materials' in step_text(
        {'kind': 'level_profession', 'group': group, 'recipe': none, 'more': 0}, character, 25)


async def test_farming_top_three_prices_evidence_and_caveats(user, tmp_path, monkeypatch):
    from test_farming import loot
    source, c, data = team_app(tmp_path, monkeypatch)
    first = next(iter(data.values()))
    first['observations'] = sum((sum((loot(t + i, item=i + 1) for i in range(4)), [])
                                 for t in (0, 150, 300)), []) + loot(1000, item=1)
    labels(monkeypatch, source)
    await user.open('/')
    await user.should_see('This session')
    user.find(marker='session-view').elements.pop().set_value('This session')
    await user.should_see('Farming')
    await user.should_see('units/hour')
    await user.should_see('no price')
    await user.should_see('typical unit')
    await user.should_see('1 stretches excluded')
    await user.should_see('Your own past sessions, not a promise')
    await user.should_see('launch respawn competition differs')
    await user.should_see('listings are not sales')
    cards = user.find(marker='session-farming').elements
    assert len(cards) == 2
    assert sorted(sum(isinstance(e, ui.link) for e in card.descendants()) for card in cards) == [0, 3]
    user.find('Farming evidence').elements.pop().open()
    await user.should_see('object IDs [1731]')


@pytest.mark.parametrize('named', [False, True])
async def test_farming_spots_table_npc_links_values_and_coin_caveat(user, tmp_path, monkeypatch, named):
    from test_farming import mob_loot
    source, c, data = team_app(tmp_path, monkeypatch)
    first = next(iter(data.values()))
    first['observations'] = mob_loot(0, 20, item=1) + mob_loot(150, 10, item=3) + mob_loot(300, 20, item=999)
    if named:
        from test_farming import named_window
        first['observations'] += [named_window(400, 20), named_window(500, 10, 'Other mob')]
    labels(monkeypatch, source)
    await user.open('/')
    await user.should_see('This session')
    user.find(marker='session-view').elements.pop().set_value('This session')
    await user.should_see('Farming spots')
    await user.should_see('Coin unavailable')
    tables = user.find(marker='farming-spots').elements
    assert len(tables) == 1
    widget = tables.pop()
    row = widget.rows[0]
    assert 'https://www.wowhead.com/classic/npc=' in widget.slots['body-cell-Mob'].template
    assert row['Mob'] == ('Kobold Tunneler (NPC 20)' if named else 'NPC 20')
    assert row['Also looted'] == ('Other mob (NPC 10)' if named else 'NPC 10')
    assert row['Minutes'] == '5.0' and row['Stretches'] == 1 and row['No price'] == '1 item / 1 unit'
    user.find('Spot item values').elements.pop().open()
    await user.should_see('Item 999')
    if named:
        await user.should_see('Map 1 · Kobold Tunneler (NPC 20) · Item 999')


async def test_farming_cell_centre_coin_share_and_vendor_disagreement(user, tmp_path, monkeypatch):
    from test_farming import positioned, record

    from brownstone import farming
    from views.nicegui_today import session_farming_spots, spot_coin_share, spot_position

    events = sum((positioned(t, .47, .72) for t in (0, 150, 300)), [])
    for r, _ in events:
        if r['event'] == 'LOOT_OPENED':
            r['loot_slots'][0]['vendor_sell_copper'] = 7
    events[0][0]['loot_slots'].append({'slot_type': 2, 'quantity': 0})
    events.append(record('PLAYER_MONEY', 1, before_copper=100, after_copper=200))
    result = farming.valued(farming.history(events), {}, [], .05, {2589: 9})
    assert spot_position({'cell': None}) == '—'
    assert spot_coin_share({'coin_copper': 0, 'value_copper': 0}) == 'Coin unknown'

    @ui.page('/farming-capture')
    def page():
        session_farming_spots(result)

    await user.open('/farming-capture')
    row = user.find(marker='farming-spots').elements.pop().rows[0]
    assert row['Position'] == 'around 47, 72'
    assert 'Coin 78%' in row['Value shares']
    user.find('Spot item values').elements.pop().open()
    await user.should_see('vendor price disagreement')
    await user.should_see('using scan')
