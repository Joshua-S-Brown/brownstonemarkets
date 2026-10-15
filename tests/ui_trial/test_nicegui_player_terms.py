"""Offline NiceGUI acceptance for Today's player-facing words and values."""
from copy import deepcopy
from dataclasses import replace

import pytest
from nicegui import ui
from test_today import MARKET, NOW, plan

from brownstone.session_options import next_steps
from brownstone.today_funds import resolve_funds
from brownstone.today_session import headline_profit, queue_with_gold
from brownstone.today_settings import TodaySettings
from views import nicegui_today as view
from views import today_rows as rows

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize('listings', [True, False])
async def test_same_profit_everywhere_and_cautious_fallback(user, listings):
    result = plan(**({} if listings else {'listings': None, 'metrics': None}))
    original = deepcopy(result)
    craft, sell = result['craft'][0], result['sell'][0]
    profit = headline_profit(craft, sell)
    row = craft | profit | {'session_status': {'craft_status': 'Known'}, 'signal': None,
                           'purchases': [p | {'signal': None} for p in craft['purchases']]}
    character = {'character': ('Arille',), 'crafts': [row], 'craft_profit_copper': profit['headline_profit_copper']}

    @ui.page('/terms')
    def page():
        for label, value in rows.summary_tiles(result):
            view.theme.tile(label, value)
        view.craft_card(craft, sell)
        view.table([rows.sell_row(sell)], label='Sell')
        view.queue_panel(result, {})
        ui.label(view.step_text({'kind': 'craft'}, character, 25))
        view.session_crafts(character, MARKET)

    await user.open('/terms')
    from brownstone.money import format_money
    amount = format_money(profit['headline_profit_copper'])
    await user.should_see(f'planned profit {amount}{profit["profit_basis"]}')
    await user.should_see(f'Planned profit total {amount}{profit["profit_basis"]}')
    assert any(e.text == amount + profit['profit_basis'] for e in user.find(ui.label).elements)
    await user.should_see('Profit at the cautious sale price (used for ranking)')
    table = next(e for e in user.find(ui.table).elements if 'Sell' in e._markers)
    if listings:
        assert rows.summary_tiles(result)[2][1] == amount
        assert table.rows[0]['Profit at undercut for batch'] == amount
        await user.should_see(f'profit {amount}')
    else:
        assert rows.summary_tiles(result)[2][1] == 'unavailable'
        await user.should_see('at cautious sale price')
    assert result == original


async def test_tables_money_sort_and_plain_values(user):
    result = plan()
    result['buy'][0]['p25_copper'] = None

    @ui.page('/tables')
    def page():
        view.table([rows.craft_row(result['craft'][0], result['sell'][0])], label='Craft')
        view.table([rows.sell_row(result['sell'][0])], label='Sell')
        view.table([rows.buy_row(r, {}) for r in result['buy']], label='Buy')
        view.table([rows.vendor_row({'item_id': 1, 'purchased_units': 1, 'cost_copper': 1234,
                                    'vendor_sell_copper': 2000, 'highest_unit_copper': 1234,
                                    'gain_copper': 766, 'stale': False}, {})], label='Extras')
        view.craft_card(result['craft'][0], result['sell'][0])
        view.table([rows.present_row({'Cost (g)': v}) for v in (10200, 5000, None)], label='Sort')

    await user.open('/tables')
    for table in user.find(ui.table).elements:
        assert all('(g)' not in col['label'] for col in table.columns)
        for row in table.rows:
            for key in ('Thin', 'Cheap now'):
                if key in row:
                    assert row[key] in ('yes', 'no', 'unknown')
            if 'Warnings' in row:
                assert isinstance(row['Warnings'], str)
    buy = next(e for e in user.find(ui.table).elements if 'Buy' in e._markers)
    assert buy.rows[0]['Scan p25'] == 'unknown'
    widget = next(e for e in user.find(ui.table).elements if 'Sort' in e._markers)
    column = widget.columns[0]
    assert column[':sort'] == ('(a, b, rowA, rowB) => { const x = rowA["Cost_copper"] ?? Infinity, '
                               'y = rowB["Cost_copper"] ?? Infinity; return x === y ? 0 : (x < y ? -1 : 1) }')
    assert [r['Cost'] for r in sorted(widget.rows, key=lambda r: r['Cost_copper'] or float('inf'))] == [
        '50s', '1g 2s', 'unknown']
    assert all('_copper' not in c['name'] for c in widget.columns)


async def test_gold_mail_copy_ticks_and_no_plan_mutation(user):
    result = plan()
    result['craft'][0]['made_by'] = 'Arille'
    data = {(name, 'Beta', 'Alliance'): {'bags': {'gold_copper': gold, 'captured_at': 1}}
            for name, gold in [('Arille', 1), ('Basilly', 100), ('Able', 100)]}
    funds = resolve_funds(TodaySettings(), data, NOW, 24)
    session = {'display_queue': queue_with_gold(result, data, funds)}
    original = deepcopy(result)

    @ui.page('/queue')
    def page():
        view.queue_panel(result, session)

    await user.open('/queue')
    await user.should_see('Able mails 1s to Arille')
    boxes = sorted(user.find(ui.checkbox).elements, key=lambda e: e.id)
    assert boxes[0].text == 'Able mails 1s to Arille'
    assert boxes[1].text == 'Basilly mails 29c to Arille'
    assert boxes[2].text.startswith('Buy at')
    assert any('Able mails 1s to Arille\nBasilly mails 29c to Arille' in e.content
               for e in user.find(ui.code).elements)
    identity = session['queue_identity']
    session['ticks'] = {'0': True}
    session['display_queue'] = queue_with_gold(result, data, replace(funds, origin='entered amount'))
    await user.open('/queue')
    assert session['queue_identity'] != identity and session['ticks'] == {}
    assert result == original


def no_history(seconds=738):
    return {'rows': [], 'spots': [], 'recorded_seconds': seconds, 'stretches': [], 'excluded_stretches': 1}


async def test_merged_steps_no_farming_and_single_caveat(user):
    group = {'profession': 'Tailoring', 'best': None, 'tier': {'name': 'Journeyman', 'cap': 75,
             'required_level': 10, 'level_ok': False}, 'capped': False}
    character = {'character': ('Arille', 'Beta', 'Alliance'), 'level': 8, 'crafts': [],
                 'professions': [group, group | {'profession': 'Cooking'}]}
    character['next_steps'] = next_steps(character)

    @ui.page('/farming')
    def page():
        view.session_summary(character, {'window': 25}, MARKET)
        view.session_farming(no_history(), MARKET)
        view.session_farming(no_history(), MARKET)
        view.farming_caveat()
        ui.label(view.competition({'listings': 1, 'units': 2}))
        ui.label(rows.count_word(1, 'stretch', 'stretches'))
        ui.label(rows.count_word(1, 'skipped stretch', 'skipped stretches'))

    await user.open('/farming')
    await user.should_see('Level Arille 8 → 10 to train Journeyman Tailoring and Cooking')
    assert len(user.find(marker='session-step').elements) == 2  # nothing + one shared level step
    await user.should_see('Farming: not enough history yet (12.3 minutes recorded)')
    texts = [e.text for e in user.find(ui.label).elements]
    assert sum(t.startswith('Your own past sessions') for t in texts) == 1
    assert 'Farming' not in texts and 'Farming spots' not in texts
    assert '1 listing / 2 units' in texts and '1 stretch' in texts and '1 skipped stretch' in texts


async def test_why_summary_order_and_details_retain_ids(user):
    result = plan()
    result['hidden'] = {'rank below required skill': 441, 'no character has this profession': 1298,
                        'missing prices': 3}
    funds = resolve_funds(TodaySettings(), {}, NOW, 24)

    @ui.page('/why')
    def page():
        view.plan_info(result, MARKET | {'auction_cut': .05, 'max_age_hours': 24},
                       {'scan_id': 'scan-evidence'}, {'snapshot': {'snapshot_id': 'snapshot-evidence'}}, funds, {})

    await user.open('/why')
    await user.should_see('1,298 need a profession nobody has · 441 need more skill · 3 need prices')
    details = next(iter(user.find(ui.expansion, content='Details').elements))
    text = '\n'.join(e.text for e in details.descendants() if isinstance(e, ui.label))
    for value in ['snapshot-evidence', 'scan-evidence', 'fixture', 'classic-us-mankrik-alliance', 'Today rules v14']:
        assert value in text


@pytest.mark.parametrize('market', [False, True])
async def test_farming_caveat_once_from_both_page_callers(user, monkeypatch, market):
    from test_farming import loot

    from brownstone import farming, tier_levels
    from brownstone.freshness import assess
    from views.nicegui_market import where_to_get

    history = farming.valued(farming.history(loot(1) + loot(151) + loot(301)), {}, [], .05)
    characters = [{'character': (name, 'Beta', 'Alliance'), 'farming': deepcopy(history)}
                  for name in ['Arille', 'Basilly']]
    monkeypatch.setattr(view, 'session_summary', lambda *args: None)
    monkeypatch.setattr(view, 'session_crafts', lambda *args: None)
    monkeypatch.setattr(view, 'session_professions', lambda *args: None)

    @ui.page('/caveats')
    def page():
        if market:
            where_to_get(MARKET, {'farming': characters, 'wowhead_url': 'https://www.wowhead.com/classic/item=2770'})
        else:
            view.session_options({'characters': characters,
                                  'tier_explanation': tier_levels.explanation({}, MARKET['game_version']),
                                  'freshness': assess({'collected_at': NOW.isoformat()}, NOW, 24),
                                  'signals': {'note': '', 'scan': None}, 'window': 25,
                                  'snapshot': {'snapshot_id': 'fixture'}}, MARKET | {'max_age_hours': 24})

    await user.open('/caveats')
    labels = [e.text for e in user.find(ui.label).elements]
    assert sum(t.startswith('Your own past sessions') for t in labels) == 1
    assert sum('1 stretch' in t for t in labels) == 2


async def test_one_more_on_way(user):
    @ui.page('/singular')
    def page():
        ui.label(view.step_text({'kind': 'level_profession', 'group': {'profession': 'Cooking', 'rank': 1},
                                'recipe': {'name': 'Food', 'required_skill': 2, 'profit_copper': 1,
                                           'estimate': {'cost_copper': 1, 'cheap_cost_copper': 0}}, 'more': 1},
                               {'character': ('Arille',)}, 25))

    await user.open('/singular')
    await user.should_see('1 more on the way')


@pytest.mark.parametrize('mode,expected', [
    ('uncaptured donor', ['Able mails 1s to Arille', 'Basilly mails 29c to Arille']),
    ('uncaptured crafter', ["Arille's gold isn't captured; Arille needs 1s 30c for purchases"]),
    ('single', []), ('entered', []),
])
async def test_gold_mail_capture_and_budget_modes(user, mode, expected):
    result = plan()
    result['craft'][0]['made_by'] = 'Arille'
    data = {(name, 'Beta', 'Alliance'): {'bags': {'gold_copper': gold, 'captured_at': 1}}
            for name, gold in [('Arille', 1), ('Basilly', 100), ('Able', 100), ('Uncaptured', 99999)]}
    data[('Uncaptured', 'Beta', 'Alliance')]['bags'].pop('captured_at')
    if mode == 'uncaptured crafter':
        data[('Arille', 'Beta', 'Alliance')]['bags'].pop('captured_at')
    settings = TodaySettings(character=('Arille', 'Beta', 'Alliance') if mode == 'single' else None,
                             gold_override=mode == 'entered')
    funds = resolve_funds(settings, data, NOW, 24)
    queue = queue_with_gold(result, data, funds)

    @ui.page('/gold-modes')
    def page():
        view.queue_panel(result, {'display_queue': queue})

    await user.open('/gold-modes')
    boxes = sorted(user.find(ui.checkbox).elements, key=lambda e: e.id)
    gold_text = [e.text for e in boxes if 'mails' in e.text or "gold isn't captured" in e.text]
    assert gold_text == expected
    assert not any('Uncaptured mails' in e.text for e in boxes)
    copy = next(iter(user.find(ui.code).elements)).content
    assert all(line in copy for line in expected)
