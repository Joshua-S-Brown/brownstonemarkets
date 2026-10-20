"""UI-15: minimal anonymized beta records, offline and integer copper throughout."""
import json
from copy import deepcopy
from pathlib import Path

import duckdb
import pytest
from test_scans import NOW
from test_stock import fixture as stock_fixture
from test_today import plan

from brownstone import earnings, ledger, sales, stock
from brownstone.storage import ensure_schema

FIXTURES = Path(__file__).parent / 'fixtures' / 'ledger'
CATEGORIES = json.loads((FIXTURES / 'categories.json').read_text())


def burst():
    return json.loads((FIXTURES / 'burst.json').read_text())


def money(amount=10, at=100, seq=2, **extra):
    return {'event': 'PLAYER_MONEY', 'family': 'money', 'entry_id': f'm:{at}:{seq}',
            'captured_at': at, 'sequence': seq, 'login_at': 1, 'machine': 'fixture',
            'character': 'Fixture', 'realm': 'Fixture Realm', 'faction': 'Alliance',
            'before_copper': 100, 'after_copper': 100 + amount, **extra}


def bags(at, gold, seq=3, **extra):
    return money(at=at, seq=seq) | {'kind': 'bags', 'snapshot_id': f'b:{at}:{seq}',
                                  'gold_copper': gold, 'containers': [{'container_id': 0, 'size': 20}], **extra}


@pytest.mark.parametrize('category', sorted(CATEGORIES))
def test_each_beta_category(category):
    rows = CATEGORIES[category]
    out = ledger.project(rows)['movements'][-1]
    assert out['parts'][0]['category'] == category
    assert out['copper'] == rows[-1]['after_copper'] - rows[-1]['before_copper']
    assert sum(p['copper'] for p in out['parts']) == out['copper']
    assert type(out['copper']) is int and out['entry_id'] == rows[-1]['entry_id']
    assert out['machine'] == 'fixture' and out['character'] == sales.character(rows[-1])


def test_beta_burst_shifted_indexes_amount_matching_invoice_split_and_dedup():
    rows = burst()
    out = ledger.project(rows)
    assert [m['copper'] for m in out['movements']] == [268, 755]
    assert all(m['reason'] is None for m in out['movements'])
    totals = {r['category']: r['in_copper'] for r in out['totals']}
    assert totals == {'auction sale': 323, 'deposit refund': 700}
    assert ledger.project(rows + rows) == out
    assert sum(r['in_copper'] for r in out['totals']) == out['team']['in_copper'] == 1023


def test_unreconciled_missing_index_and_bad_invoice():
    rows = burst()
    next(r for r in rows if r['event'] == 'PLAYER_MONEY')['after_copper'] += 1
    out = ledger.project(rows)
    assert out['movements'][0]['parts'][0]['category'] == 'mail in (unidentified)'
    assert out['movements'][0]['reason']
    assert ledger._mail_parts(money(), None) is None
    assert ledger._mail_parts(money(), {'header': {}, 'invoice': {}}) is None
    message = {'header': {'5': 1, '7': 30}, 'invoice': {'1': 'seller', '4': 100, '7': 5, '11': 1}}
    assert ledger._mail_parts(money(), message) is None
    message['header']['5'] = 0
    assert ledger._mail_parts(money(), message) is None
    take = money(at=100, seq=1) | {'event': 'TakeInboxMoney', 'arguments': {'1': 99}}
    assert ledger.project([take, money()])['movements'][0]['reason']


def test_plain_mail_baselines_units_and_unknowns():
    message = {'index': 1, 'header': {'5': 200, '7': 30}, 'invoice': {}}
    inbox = money(seq=0) | {'event': 'MAIL_INBOX_UPDATE', 'inbox': {'messages': [message]}}
    take = money(seq=1) | {'event': 'TakeInboxMoney', 'arguments': {'1': 1}}
    out = ledger.project([inbox, take, money(200), money(before_copper=None, seq=3),
                          money(after_copper=None, seq=4), money(before_copper=True, seq=5)])
    assert out['excluded_money'] == 3
    assert out['movements'][0]['parts'] == [{'category': 'mail in', 'copper': 200}]
    assert ledger.project([money(0)])['movements'][0]['parts'] == [{'category': 'other', 'copper': 0}]


@pytest.mark.parametrize('change', [{'login_at': 2}, {'machine': 'another'}, {'character': 'Another'},
                                  {'realm': 'another'}, {'faction': 'Horde'}, {'login_at': None},
                                  {'captured_at': 999}])
def test_hooks_cannot_cross_character_machine_login_or_time(change):
    rows = deepcopy(CATEGORIES['vendor purchase'])
    rows[-1].update(change)
    assert ledger.project(rows)['movements'][0]['parts'][0]['category'] == 'other'


def test_loot_chat_never_overrides_vendor_and_container_needs_open_merchant():
    rows = deepcopy(CATEGORIES['vendor purchase'])
    chat = rows[0] | {'entry_id': 'chat:1:0', 'event': 'CHAT_MSG_LOOT', 'sequence': 0}
    assert ledger.project([*rows, chat])['movements'][0]['parts'][0]['category'] == 'vendor purchase'
    rows = deepcopy(CATEGORIES['vendor sale'])
    rows[0].update(event='C_Container.UseContainerItem', windows={'merchant': False})
    assert ledger.project(rows)['movements'][0]['parts'][0]['category'] == 'other'


def test_reconciliation_gap_no_gap_missing_and_unreadable_character_separation():
    snapshots = [bags(90, 100), bags(110, 162), bags(120, 167),
                 bags(115, 0, containers=[{'container_id': 0, 'size': 0}]),
                 bags(90, 1, character='Other'), bags(120, 1, character='Other')]
    records = [money(10), money(5, at=119), money(1000, character='Other', at=130)]
    out = ledger.project(records, snapshots)
    assert [r['unexplained_copper'] for r in out['reconciliation']] == [52, 0, 0]
    assert out['unreadable_snapshots'] == 1
    assert ledger.project([money(before_copper=None)], snapshots)['reconciliation'][0]['unexplained_copper'] is None
    snapshots[0]['gold_copper'] = None
    assert ledger.project([], snapshots)['reconciliation'][0]['reason']


def test_load_empty_scoped_once_and_read_only(tmp_path):
    config = stock_fixture(tmp_path)
    assert ledger.load(config)['movements'] == []
    with duckdb.connect(':memory:') as db:
        assert ledger.load(config, db)['totals'] == []
        ensure_schema(db)
        row = money()
        scope = {k: config[k] for k in ('source_id', 'market_id', 'game_version', 'region', 'scope',
                                      'realm', 'server_type', 'faction', 'environment')}
        # The production table's full column set is exercised by the import tests; insert our projection evidence.
        for name, value in [(key, 'other') for key in scope] + [(None, None)]:
            data = scope | ({name: value} if name else {})
            data.update(entry_id=str(name), family='money', record_json=json.dumps(row),
                        character='Fixture', character_realm='Fixture Realm', character_faction='Alliance',
                        captured_at='2026-10-15T00:00:00Z')
            # Required provenance fields are supplied with harmless test values.
            for key in ('collection_id', 'source_sha256', 'record_sha256'):
                data[key] = 'fixture'
            cols = ','.join(data)
            db.execute(f"INSERT INTO character_journal ({cols}) VALUES ({','.join('?' for _ in data)})",
                       list(data.values()))
        data.update(entry_id='quest', family='quest', record_json=json.dumps(
            row | {'entry_id': 'quest', 'event': 'QUEST_TURNED_IN', 'family': 'quest',
                   'sequence': 1, 'arguments': {'3': 10}}))
        db.execute(f"INSERT INTO character_journal ({cols}) VALUES ({','.join('?' for _ in data)})",
                   list(data.values()))
        loaded = ledger.load(config, db)['movements']
        assert len(loaded) == 1 and loaded[0]['parts'][0]['category'] == 'quest reward'
    assert ledger.load(config | {'data_dir': tmp_path / 'missing'})['movements'] == []


def test_additive_projection_leaves_plans_holdings_targets_and_sales_unchanged(tmp_path):
    config = stock_fixture(tmp_path)
    before_stock = stock.load_stock(config, [], NOW)
    before_plan = plan()
    rows = burst()
    original = deepcopy(rows)
    before_sales = sales.project(rows)
    ledger.project(rows)
    ledger.load(config)
    assert rows == original and sales.project(rows) == before_sales
    assert stock.load_stock(config, [], NOW) == before_stock
    assert plan() == before_plan


def test_takes_shift_without_a_new_inbox_and_timeout_is_other():
    messages = [{'index': i, 'header': {'5': n, '7': 30}, 'invoice': {}}
                for i, n in enumerate((1, 200, 400), 1)]
    inbox = money(seq=0) | {'event': 'MAIL_INBOX_UPDATE', 'inbox': {'messages': messages}}
    takes = [money(seq=i) | {'event': 'TakeInboxMoney', 'arguments': {'1': 1}} for i in (1, 2, 3)]
    out = ledger.project([inbox, *takes, money(601, seq=4)])
    assert out['movements'][0]['parts'] == [{'category': 'mail in', 'copper': n} for n in (1, 200, 400)]
    late = ledger.project([inbox, *takes, money(601, at=102)])
    assert late['movements'][0]['parts'][0]['category'] == 'other'


def test_utc_days_outflow_and_coin_missing_login():
    a, b = money(10, at=86399), money(-5, at=86400)
    out = ledger.project([a, b])
    assert [r['day'] for r in out['totals']] == ['1970-01-01', '1970-01-02']
    assert out['team'] == {'in_copper': 10, 'out_copper': 5}
    rows = deepcopy(CATEGORIES['coin loot'])
    for r in rows:
        r['login_at'] = None
    assert ledger.project(rows)['movements'][-1]['parts'][0]['category'] == 'other'


def test_same_second_uses_numeric_sequence_even_without_sequence_field():
    early, late = money(seq=2), money(seq=10)
    assert [m['entry_id'] for m in ledger.project([late, early])['movements']] == [
        early['entry_id'], late['entry_id']]
    rows = deepcopy(CATEGORIES['coin loot'])
    for r in rows:
        r.pop('sequence', None)
    assert ledger.project(rows)['movements'][-1]['parts'][0]['category'] == 'coin loot'


def test_quest_exact_unmatched_two_same_second_cost_and_reconciliation():
    quest = money(seq=1) | {'event': 'QUEST_TURNED_IN', 'family': 'quest', 'entry_id': 'q1',
                            'arguments': {'1': 42, '2': 100, '3': 10}}
    another = quest | {'entry_id': 'q2', 'sequence': 2, 'arguments': {'3': 20}}
    cost = quest | {'entry_id': 'cost', 'captured_at': 102, 'arguments': {'3': -5}}
    records = [quest, quest | {'entry_id': 'xp', 'family': 'xp'}, another, money(10, seq=3),
               money(20, seq=4), money(10, seq=5),
               cost, money(-5, at=103), money(11, at=104), money(20, at=105)]
    out = ledger.project(records, [bags(90, 100), bags(110, 166)])
    assert out['ledger_version'] == 2
    assert [m['parts'][0]['category'] for m in out['movements']] == [
        'quest reward', 'quest reward', 'other', 'quest cost', 'other', 'other']
    assert out['reconciliation'][0]['unexplained_copper'] == 0
    assert earnings.project(records)['total']['world_copper'] == 25
    assert ledger.project(records + records) == ledger.project(records)
    for change in ({'machine': 'different'}, {'login_at': None}, {'character': 'Different'}):
        assert ledger.project([quest, money(10, **change)])['movements'][0]['parts'][0]['category'] == 'other'
    for arguments in ({'3': 11}, {'3': '10'}, {}, {'3': 0}):
        assert ledger.project([quest | {'arguments': arguments}, money(10)])['movements'][0]['parts'][0][
            'category'] == 'other'


@pytest.mark.parametrize('category', sorted(CATEGORIES))
def test_earnings_exact_ledger_category_grouping(category):
    out = earnings.project(CATEGORIES[category])['characters'][0]['total']
    copper = sum(p['copper'] for m in ledger.project(CATEGORIES[category])['movements'] for p in m['parts'])
    assert out['world_copper'] == (copper if category in earnings.WORLD else 0)
    assert out['market_copper'] == (copper if category in earnings.MARKET else 0)
    assert sum(out['categories'].values()) + out['own_mail_copper'] == copper


def test_earnings_login_reload_idle_windows_bands_and_xp():
    def entry(at, event='OBSERVE', **extra):
        return money(at=at, login_at=100, **extra) | {'event': event, 'family': 'window'}

    rows = [entry(100), entry(160, 'MERCHANT_SHOW'),
            entry(180, 'MAIL_SHOW'), entry(200, windows={'merchant': True, 'mailbox': True}),
            entry(220, 'MERCHANT_CLOSED'), entry(240, 'MAIL_CLOSED'),
            entry(300, 'PLAYER_ENTERING_WORLD', arguments={'1': False, '2': True}),
            money(at=400, login_at=100) | {'event': 'PLAYER_LEVEL_UP', 'family': 'xp',
                                          'arguments': {'1': 6}, 'level': 6, 'quest_xp': 40, 'other_xp': 60},
            entry(500, windows={'trainer': True}), entry(520, windows={'trainer': True}),
            entry(1200, windows={'trainer': True}), entry(1260),
            money(at=1260, seq=3, login_at=100) | {'family': 'xp', 'event': 'PLAYER_LOGOUT', 'quest_xp': 20},
            money(at=2000, login_at=2000), money(at=2100, login_at=2000),
            money(at=1200, character='Second', login_at=1100),
            money(at=1800, character='Second', login_at=1100),
            money(at=1300, machine='pc', login_at=1300), money(at=1400, machine='pc', login_at=1300),
            money(at=1500, login_at=None)]
    for at, amount in ((350, 20), (450, -5)):
        rows.extend([money(at=at, seq=1, login_at=100) | {'event': 'QUEST_TURNED_IN', 'family': 'quest',
                                                       'arguments': {'3': amount}},
                     money(amount, at=at, login_at=100)])
    rows = [r | {'entry_id': f"{r['character']}:{r['machine']}:{r['entry_id']}"} for r in rows]
    snapshots = [bags(90, 100, level=5), bags(101, 100, level=50)]
    out = earnings.project(rows, snapshots)
    first = out['characters'][0]
    assert len(first['sessions']) == 3
    session = first['sessions'][0]
    assert (session['start'], session['end'], session['seconds']) == (100, 1260, 480)
    assert session['market_seconds'] == 100
    assert session['world_seconds'] == 380
    assert [(b['label'], b['seconds']) for b in session['bands']] == [('1–5', 300), ('6–10', 180)]
    assert [b['world_copper'] for b in session['bands']] == [20, -5]
    assert session['levels'] == 1 and session['quest_xp'] == 60 and session['other_xp'] == 60
    assert session['xp_label'] == 'at least' and session['xp_per_hour'] == 1136
    assert first['sessions'][1]['xp_label'] == 'XP not captured'
    assert first['bands'][0]['thin']
    assert out['unknown_login_entries'] == 1
    assert out['characters'][1]['total']['seconds'] == 700
    assert out['total']['seconds'] == 1380
    assert earnings.project(rows + rows, snapshots) == out
    assert earnings.project(rows, snapshots, idle=20)['characters'][0]['sessions'][0]['seconds'] == 1160
    reloaded = [entry(100, windows={'merchant': True}), entry(130, windows={'merchant': True}),
                entry(160, windows={}), entry(400, 'MERCHANT_SHOW'), entry(460, 'MERCHANT_CLOSED')]
    assert earnings.project(reloaded)['characters'][0]['sessions'][0]['market_seconds'] == 90
    complete = [entry(at, windows={'bank': True, 'loot': True}) for at in (100, 700, 1300)]
    complete.append(money(at=1900, login_at=100) | {'family': 'xp', 'event': 'PLAYER_LOGOUT',
                                                  'quest_xp': 0, 'other_xp': 120})
    band = earnings.project(complete, snapshots)['characters'][0]['bands'][0]
    assert not band['thin'] and band['world_seconds'] == 1800 and band['market_seconds'] == 0
    assert band['xp_label'] == 'captured' and band['xp_per_hour'] == 240
    complete[-1] |= {'other_xp': None}
    assert earnings.project(complete, snapshots)['characters'][0]['bands'][0]['xp_label'] == 'at least'


def test_earnings_own_mail_is_excluded_but_unidentified_and_other_stay_separate():
    def receive(sender, seq):
        return [money(seq=seq) | {'event': 'MAIL_INBOX_UPDATE', 'inbox': {'messages': [
            {'index': 1, 'header': {'3': sender, '5': 200, '7': 30}}]}},
            money(seq=seq+1) | {'event': 'TakeInboxMoney', 'arguments': {'1': 1}}, money(200, seq=seq+2)]
    rows = [*receive('bOB Surname', 0), *receive('Stranger', 3),
            money(seq=6) | {'event': 'SendMail', 'arguments': {'1': 'Bob Surname'},
                            'draft': {'recipient': 'Stranger'}}, money(-100, seq=7),
            money(seq=8) | {'event': 'TakeInboxMoney', 'arguments': {'1': 99}}, money(300, seq=9),
            money(10, seq=10), money(100, character='Bob', at=110)]
    out = earnings.project(rows)['characters'][1]['total']
    assert out['own_mail_copper'] == 100
    assert out['categories'] == {'mail in': 200, 'mail in (unidentified)': 300, 'other': 10}
    assert out['groups'] == {'world': {}, 'market': {}, 'not assigned': out['categories']}
    repair = [money(0, at=0, login_at=0), money(at=3600, seq=1, login_at=0) | {'event': 'RepairAllItems'},
              money(-7, at=3600, login_at=0), money(0, at=3601, login_at=0, seq=3)]
    lost = earnings.project(repair, idle=120)['total']
    assert lost['groups']['world'] == {'repairs': -7} and lost['world_per_hour_copper'] == -6  # toward zero
    assert out['world_copper'] == out['market_copper'] == 0
    assert earnings.project([money(login_at=None)])['total']['xp_per_hour'] is None
    assert earnings.character_record(earnings.project([]), ('Absent', 'Realm', 'Alliance'))['sessions'] == []
