"""UI-15: minimal anonymized beta records, offline and integer copper throughout."""
import json
from copy import deepcopy
from pathlib import Path

import duckdb
import pytest
from test_scans import NOW
from test_stock import fixture as stock_fixture
from test_today import plan

from brownstone import ledger, sales, stock
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
        assert len(ledger.load(config, db)['movements']) == 1
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
