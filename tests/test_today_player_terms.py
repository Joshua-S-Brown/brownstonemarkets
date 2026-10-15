"""STORY-069 presentation preserves the pre-change funded plans byte for byte."""
import hashlib
import json

from test_today import plan


def test_pre_story_plans_identical():
    fixtures = [({}, '55d33e371f503198e2e63bdcfb6320b8875ebc0d12dbd9af054176f312ffce58'),
                ({'listings': None, 'metrics': None},
                 'e651ee9c42cca754d45090fb3368c0bd13cd0d771b88281c07648e84b81a0cd3'),
                ({'listings': {}, 'metrics': {}},
                 '72ed2a96e7e186b47798060669b1467833cce2e26ba627e356f2dac67b214c3c')]
    for arguments, expected in fixtures:
        encoded = json.dumps(plan(**arguments), sort_keys=True, default=str).encode()
        assert hashlib.sha256(encoded).hexdigest() == expected


def test_gold_transfers_order_unknowns_and_scope():
    from dataclasses import replace

    from test_today import NOW

    from brownstone.today_funds import resolve_funds
    from brownstone.today_session import gold_mail_lines, queue_line, queue_with_gold
    from brownstone.today_settings import TodaySettings

    result = plan()
    result['craft'][0]['made_by'] = 'Arille'
    cost = result['shopping_total_copper']
    data = {(name, 'Beta', 'Alliance'): {'bags': {'gold_copper': gold, 'captured_at': 1}}
            for name, gold in [('Arille', 1), ('Basilly', 100), ('Able', 100), ('Missing', 0)]}
    data[('Uncaptured', 'Beta', 'Alliance')] = {'bags': {'gold_copper': 99999}}
    funds = resolve_funds(TodaySettings(), data, NOW, 24)
    lines = gold_mail_lines(result, data, funds)
    assert [(r['character'], r['copper']) for r in lines] == [('Able', 100), ('Basilly', cost - 101)]
    assert queue_line(lines[0]) == 'Able mails 1s to Arille'
    original = json.dumps(result, sort_keys=True, default=str)
    queue = queue_with_gold(result, data, funds)
    assert queue['lines'][:2] == lines
    assert queue['lines'][2]['stage'] == 'auction house'
    assert json.dumps(result, sort_keys=True, default=str) == original
    result['queue']['lines'].insert(0, {'stage': 'take'})
    result['queue']['lines'].insert(1, {'stage': 'mail'})
    assert queue_with_gold(result, data, funds)['lines'][2:4] == lines
    data[('Arille', 'Beta', 'Alliance')]['bags'].pop('captured_at')
    unknown = gold_mail_lines(result, data, funds)
    assert len(unknown) == 1
    assert queue_line(unknown[0]) == "Arille's gold isn't captured; Arille needs 1s 30c for purchases"
    assert gold_mail_lines(result, data, replace(funds, origin='entered amount')) == []
    single = replace(funds, settings=replace(funds.settings, character=('Arille', 'Beta', 'Alliance')))
    assert gold_mail_lines(result, data, single) == []
    gone = replace(funds, settings=replace(funds.settings, character=('Gone', 'Beta', 'Alliance')))
    assert gold_mail_lines(result, data, gone) == unknown
    only_donor = {('Basilly', 'Beta', 'Alliance'): data[('Basilly', 'Beta', 'Alliance')]}
    assert gold_mail_lines(result, only_donor, funds) == []


def test_gold_spending_excludes_held_and_reserves_donors_own_crafts(monkeypatch):
    from test_today import NOW

    from brownstone.today_funds import resolve_funds
    from brownstone.today_session import gold_mail_lines
    from brownstone.today_settings import TodaySettings

    result = {'craft': [{'made_by': 'A'}, {'made_by': 'B'}]}
    monkeypatch.setattr('brownstone.today_session.craft_details', lambda r: {'materials': [
        {'method': 'held', 'cost_copper': 99999}, {'method': 'buy', 'cost_copper': 100}]})
    data = {(n, 'Beta', 'Alliance'): {'bags': {'gold_copper': g, 'captured_at': 1}}
            for n, g in [('A', 10), ('B', 200), ('C', 100)]}
    funds = resolve_funds(TodaySettings(), data, NOW, 24)
    assert gold_mail_lines(result, data, funds) == [
        {'stage': 'gold mail', 'name': 'A', 'character': 'B', 'copper': 90}]


def test_money_projections_and_unknowns():
    from brownstone.today import craft_details
    from views.today_rows import buy_row, craft_row, material_row, sell_row, vendor_row

    result = plan()
    craft, sell = result['craft'][0], result['sell'][0]
    rows = [craft_row(craft, sell), sell_row(sell), buy_row(result['buy'][0], {}),
            material_row(craft_details(craft)['materials'][0]), vendor_row({
                'item_id': 1, 'purchased_units': 2, 'cost_copper': 1234, 'vendor_sell_copper': 700,
                'highest_unit_copper': 617, 'gain_copper': 166, 'stale': False}, {})]
    for row in rows:
        for key, value in row.items():
            assert '(g)' not in key
            if key.endswith('_copper'):
                assert type(value) is int or value is None
            else:
                assert not isinstance(value, (float, bool))
    assert rows[2]['Cheap now'] == 'yes'
    assert rows[1]['Thin'] == 'no'
    assert isinstance(rows[1]['Warnings'], str)
    sell['undercut_batch_profit_copper'] = None
    assert sell_row(sell)['Profit at undercut for batch'] == 'unknown'
    assert craft_row(craft, sell)['Profit basis'] == 'at cautious sale price'


def test_merge_level_and_train_require_same_tier_and_kind():
    from brownstone.session_options import merge_tier_steps
    from views.nicegui_today import step_text

    tier = {'name': 'Journeyman', 'required_level': 10}
    steps = [{'kind': kind, 'tier': tier, 'group': {'profession': profession}}
             for kind in ['level_character', 'train'] for profession in ['Tailoring', 'Cooking']]
    merged = merge_tier_steps(steps)
    assert len(merged) == 2
    character = {'character': ('Arille',), 'level': 8}
    assert step_text(merged[0], character, 25) == 'Level Arille 8 → 10 to train Journeyman Tailoring and Cooking'
    assert step_text(merged[1], character, 25) == 'Train Journeyman at a trainer: Tailoring and Cooking'
    assert len(merge_tier_steps(steps + [{'kind': 'evidence'}])) == 3


def test_post_profit_zero_negative_rounding_and_cautious_fallback():
    from brownstone.today_session import headline_profit

    craft = {'batch_size': 3, 'batch_profit_copper': 100}
    for quote, expected, basis in [(0, 0, ''), (-4, -4, ''), (None, 100, ' at cautious sale price')]:
        result = headline_profit(craft, {'undercut_batch_profit_copper': quote})
        assert result == {'headline_profit_copper': expected, 'headline_per_craft_copper': expected // 3,
                          'profit_basis': basis}


def test_gold_donors_use_largest_surplus_before_name(monkeypatch):
    from test_today import NOW

    from brownstone.today_funds import resolve_funds
    from brownstone.today_session import gold_mail_lines
    from brownstone.today_settings import TodaySettings

    monkeypatch.setattr('brownstone.today_session.craft_details', lambda r: {
        'materials': [{'method': 'buy', 'cost_copper': 250}]})
    data = {(n, 'Beta', 'Alliance'): {'bags': {'gold_copper': g, 'captured_at': 1}}
            for n, g in [('Crafter', 1), ('Able', 100), ('Zed', 200)]}
    result = {'craft': [{'made_by': 'Crafter'}]}
    funds = resolve_funds(TodaySettings(), data, NOW, 24)
    assert gold_mail_lines(result, data, funds) == [
        {'stage': 'gold mail', 'name': 'Crafter', 'character': 'Zed', 'copper': 200},
        {'stage': 'gold mail', 'name': 'Crafter', 'character': 'Able', 'copper': 49}]
