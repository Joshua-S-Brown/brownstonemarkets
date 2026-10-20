"""UI-16: anonymized beta projections plus focused offline boundary cases."""
import json
from copy import deepcopy
from pathlib import Path

import duckdb
import pytest
from test_ledger import money
from test_scans import NOW
from test_stock import fixture
from test_today import plan

from brownstone import earnings, ledger, sales, stock
from brownstone import item_ledger as items
from brownstone.storage import ensure_schema

CATEGORIES = json.loads((Path(__file__).parent / 'fixtures/item_ledger/categories.json').read_text())


def row(event='BAG_UPDATE_DELAYED', at=100, seq=2, **extra):
    return money(at=at, seq=seq) | {'event': event, 'family': 'bags', 'addon_version': '0.12.7',
                                   'item_changes': {'2589': 1}, **extra}


def chat(prefix='You receive loot:', count=1, **extra):
    return row('CHAT_MSG_LOOT', **({'seq': 1, 'arguments': {
        '1': prefix + ' |cnIQ1:|Hitem:2589:::::::::|h[Linen Cloth]|h|r' +
        (f'x{count}' if count != 1 else '')}} | extra))


def snapshot(at=90, count=0, kind='bags', **extra):
    return {k: v for k, v in (row(at=at) | {
        'snapshot_id': f"s:{at}:{kind}:{extra.get('character', 'Fixture')}", 'kind': kind,
        'containers': [{'container_id': 0, 'size': 16}],
        'slots': [{'item_id': 2589, 'count': count}]} | extra).items() if k != 'entry_id'}


def mail(subject='Cloth', sender='Sender', count=1, **extra):
    return {'index': 1, 'header': {'3': sender, '4': subject, '5': 0, '7': 30},
            'items': [{'link': '|Hitem:2589:::::::::|h[Linen Cloth]|h|r', 'info': {'4': count}}], **extra}


def receive(message=None, **extra):
    return [row('MAIL_INBOX_UPDATE', seq=0, inbox={'messages': [message or mail()]}, **extra),
            row('TakeInboxItem', seq=1, arguments={'1': 1, '2': 1}, **extra), row(**extra)]


@pytest.mark.parametrize('category', sorted(CATEGORIES))
def test_copied_beta_categories_and_allocations(category):
    out = items.project(CATEGORIES[category])
    assert any(p['category'] == category for m in out['movements'] for p in m['parts'])
    for m in out['movements']:
        assert sum(p['units'] for p in m['parts']) == m['units']
        assert type(m['item_id']) is int and type(m['units']) is int
    assert items.project(CATEGORIES[category] * 2) == out


def test_mixed_craft_entry_and_summed_vendor_buys():
    records = [row('UNIT_SPELLCAST_SUCCEEDED', seq=0), chat('You create:'),
               row(item_changes={'2589': 1, '2320': -2})]
    out = items.project(records)
    assert {p['category'] for m in out['movements'] for p in m['parts']} == {'craft in', 'craft out'}
    records = [row('BuyMerchantItem', seq=0), chat('You receive item:'),
               chat('You receive item:', seq=2), row(seq=3, item_changes={'2589': 2})]
    assert items.project(records)['movements'][0]['parts'] == [
        {'category': 'vendor purchase', 'units': 1, 'counterparty': None, 'reason': None}] * 2
    records[-1]['item_changes']['2589'] = 3
    assert items.project(records)['movements'][0]['parts'][-1]['category'] == 'other'


def test_conjuring_quest_counts_and_expired_evidence():
    for prefix in ('You create:', 'You receive item:'):
        assert items.project([chat(prefix), row()])['movements'][0]['parts'][0]['category'] == 'other'
    for evidence in (chat(count=3), chat(at=97), chat(arguments={'1': 'no link'})):
        assert items.project([evidence, row()])['movements'][0]['parts'][0]['category'] == 'other'


@pytest.mark.parametrize('change', [{'character': 'Other'}, {'realm': 'Other'}, {'faction': 'Horde'},
                                  {'machine': 'pc'}, {'login_at': 5}, {'login_at': None}, {'captured_at': 103}])
def test_evidence_cannot_cross_character_machine_login_window(change):
    assert items.project([chat(), row(**change)])['movements'][0]['parts'][0]['category'] == 'other'


def test_stale_draft_mail_units_and_cross_machine_transfer_and_unmatched():
    records = [row('SendMail', seq=1, arguments={'1': 'Bob Surname'}, draft={'items': [{'count': 99}]}),
               row(item_changes={'2589': -1}),
               *receive(mail(sender='Fixture Surname'), character='Bob', machine='pc', at=101),
               row('SendMail', at=103, seq=1, arguments={'1': 'Bob Surname'}),
               row(at=103, item_changes={'2589': -2})]
    original = deepcopy(records)
    out = items.project(records)
    assert records == original
    assert [t['status'] for t in out['transfers']] == ['transfer', 'sent, not yet received']
    transfer = out['transfers'][0]
    assert transfer['units'] == 1
    assert transfer['sent']['machine'] == 'fixture' and transfer['received']['machine'] == 'pc'
    assert out['team'] == {'in_units': 0, 'out_units': 2}
    received = items.project(records[2:5] + [row(character='Fixture', at=90)])
    assert received['transfers'][0]['status'] == 'received, no send recorded'


@pytest.mark.parametrize('subject,category', [('Auction won: Cloth', 'auction purchase'),
                                             ('Auction expired: Cloth', 'expired/cancelled return'),
                                             ('Auction canceled: Cloth', 'expired/cancelled return'),
                                             ('Cloth', 'mail in')])
def test_mail_subjects_attachment_slot_and_count(subject, category):
    assert items.project(receive(mail(subject)))['movements'][0]['parts'][0]['category'] == category
    rows = receive(mail(subject, count=2))
    out = items.project(rows)['movements'][0]
    assert out['parts'][0]['category'] == 'mail in (unidentified)' and out['parts'][0]['reason']


def test_inbox_shift_multiple_slots_pending_across_update_and_unknowns():
    message = mail()
    message['items'].append(deepcopy(message['items'][0]))
    records = [row('MAIL_INBOX_UPDATE', seq=0, inbox={'messages': [message, mail()]}),
               row('TakeInboxItem', seq=1, arguments={'1': 1, '2': 1}),
               row('TakeInboxItem', seq=2, arguments={'1': 1, '2': 2}),
               row('AutoLootMailItem', seq=3, arguments={'1': 1}),
               row(seq=4, item_changes={'2589': 3})]
    out = items.project(records)['movements'][0]
    assert sum(p['units'] for p in out['parts'] if p['category'] == 'mail in') == 3
    for args in ({}, {'1': 9}, {'1': 1, '2': 9}):
        rows = receive()
        rows[1]['arguments'] = args
        assert items.project(rows)['movements'][0]['parts'][0]['reason']
    rows = receive(mail(header={}))
    assert items.project(rows)['movements'][0]['parts'][0]['category'] == 'mail in (unidentified)'
    rows = receive()
    rows[-1] = row(seq=3)
    rows.insert(2, row('MAIL_INBOX_UPDATE', seq=2, inbox={'messages': []}))
    assert items.project(rows)['movements'][0]['parts'][0]['category'] == 'mail in'


def test_baselines_dedup_utc_days_character_separation_and_unknown_login():
    records = [row(at=1, baseline_missing=True), row(at=2, item_changes=None)]
    records[1].pop('item_changes')
    records += [row(at=3, addon_version='0.10.0', character='Old'),
                row(at=6, addon_version='0.10.0', character='Old'), row(at=86400)]
    out = items.project(records * 2)
    assert len(out['baselines']) == 3 and len(out['movements']) == 2
    assert len({m['character'] for m in out['movements']}) == 2
    assert {r['day'] for r in out['totals']} == {'1970-01-01', '1970-01-02'}
    assert items.project([row('BANKFRAME_OPENED'), row(seq=3, login_at=None)])['movements'][0]['parts'][0][
        'category'] == 'other'


def test_reconciliation_residual_baseline_gap_bank_and_unreadable():
    captures = [snapshot(), snapshot(110, 4), snapshot(120, 5),
                snapshot(115, containers=[{'container_id': 0, 'size': 0}]),
                snapshot(kind='bank', count=8), snapshot(110, 6, kind='bank'),
                snapshot(character='Other'), snapshot(110, character='Other')]
    records = [row('BANKFRAME_OPENED', seq=0), row(item_changes={'2589': 2}),
               row('BANKFRAME_CLOSED', at=101), row(at=105, baseline_missing=True), row(at=119)]
    out = items.project(records, captures)
    assert out['unreadable_snapshots'] == 1
    bags = [r for r in out['reconciliation'] if r['kind'] == 'bags' and r['character'][0] == 'Fixture']
    assert [r['items'][0]['residual_units'] for r in bags] == [2, 0]
    assert bags[0]['possibly_incomplete'] and not bags[1]['possibly_incomplete']
    bank = next(r for r in out['reconciliation'] if r['kind'] == 'bank')
    assert bank['items'] == [{'item_id': 2589, 'actual_units': -2, 'recorded_units': -2, 'residual_units': 0}]
    assert items.project(records, [snapshot()])['reconciliation'] == []


def test_vendor_container_requires_observed_merchant_and_bank_requires_events():
    for opened, category in ((True, 'vendor sale'), (False, 'other')):
        records = [row('UseContainerItem', seq=1, windows={'merchant': opened}), row(item_changes={'2589': -1})]
        assert items.project(records)['movements'][0]['parts'][0]['category'] == category
    assert items.project([row(windows={'bank': True})])['movements'][0]['parts'][0]['category'] == 'other'


def test_additive_gold_sales_today_holdings_and_targets_unchanged(tmp_path):
    config = fixture(tmp_path)
    rows = sum(CATEGORIES.values(), [])
    original = deepcopy(rows)
    before = ledger.project(rows), sales.project(rows), stock.load_stock(config, [], NOW), plan()
    items.project(rows)
    items.load(config)
    assert rows == original
    assert (ledger.project(rows), sales.project(rows), stock.load_stock(config, [], NOW), plan()) == before
    assert ledger.LEDGER_VERSION == 2 and items.ITEM_LEDGER_VERSION == 1


def test_scoped_read_database_machine_and_empty_read_only(tmp_path):
    config = fixture(tmp_path)
    assert items.load(config)['movements'] == []
    assert items.load(config | {'data_dir': tmp_path / 'absent'})['movements'] == []
    with duckdb.connect(str(tmp_path / 'brownstone.duckdb')) as db:
        assert items.load(config, db)['totals'] == []
        ensure_schema(db)
        scope = {k: config[k] for k in ('source_id', 'market_id', 'game_version', 'region', 'scope',
                                      'realm', 'server_type', 'faction', 'environment')}
        for key in [*scope, None]:
            data = scope | ({key: 'other'} if key else {})
            record = row(entry_id=f'scope:{key}', character='Outside' if key else 'Fixture')
            data.update(entry_id=str(key), family='bags', record_json=json.dumps(record), machine='db-machine',
                        character='Fixture', character_realm='Fixture Realm', character_faction='Alliance',
                        captured_at='2026-10-15T00:00:00Z', collection_id='fixture', source_sha256='fixture',
                        record_sha256='fixture')
            db.execute(f"INSERT INTO character_journal ({','.join(data)}) VALUES ({','.join('?' for _ in data)})",
                       list(data.values()))
        out = items.load(config, db)
        assert len(out['movements']) == 1 and out['movements'][0]['machine'] == 'db-machine'

    measured = earnings.load(config | {'data_dir': tmp_path}, {}, {})
    assert len(measured['characters']) == 1
    assert measured['characters'][0]['sessions'][0]['machine'] == 'db-machine'
    assert measured['characters'][0]['bands'][0]['label'] == 'level unknown'
    assert earnings.load(config | {'data_dir': tmp_path / 'absent'}, {}, {})['characters'] == []


def test_bank_inaccessible_and_unknown_slots_excluded_without_invented_changes():
    captures = [snapshot(kind='bank'), snapshot(at=95, kind='bank',
                containers=[{'container_id': -1, 'size': 0}]), snapshot(110, 3, kind='bank'),
                snapshot(at=105, slots=[{'item_id': 2589, 'count': None}])]
    out = items.project([], captures)
    assert out['unreadable_snapshots'] == 2
    assert len(out['reconciliation']) == 1
    assert out['reconciliation'][0]['items'][0]['residual_units'] == 3


def test_post_same_second_order_does_not_consume_an_earlier_decrease():
    p = {'item_id': 2589, 'at': 100, 'bag_id': row(seq=4)['entry_id'], 'quantity': 1}
    m = {'item_id': 2589, 'parts': []}
    assert items._posted(m, row(seq=2), [p], 1) == 1
    assert m['parts'] == []


def test_copied_beta_transfer_uses_first_word_across_machines():
    path = Path(__file__).parent / 'fixtures/item_ledger/transfer.json'
    out = items.project(json.loads(path.read_text()))
    transfer = next(t for t in out['transfers'] if t['item_id'] == 2840)
    assert transfer['status'] == 'transfer' and transfer['units'] == 5
    assert transfer['sent']['machine'] == 'fixture-pc' and transfer['received']['machine'] == 'fixture-mac'
    assert items.team([m for m in out['movements'] if m['item_id'] == 2840]) == {'in_units': 0, 'out_units': 0}


def test_slot_keyed_attachment_resolves_its_slot_and_lowercase_recipient_is_own():
    # Beta 2026-10-13: an attachment in slot 7 was persisted as {"7": ...} and taken as (1, 7).
    message = mail(sender='Fixture Surname', count=4)
    message['items'] = {'7': message['items'][0]}
    records = [row('SendMail', at=99, seq=1, arguments={'1': 'bob'}),
               row(at=99, item_changes={'2589': -4}),
               row('MAIL_INBOX_UPDATE', seq=0, inbox={'messages': [message]}, character='Bob', machine='pc'),
               row('TakeInboxItem', seq=1, arguments={'1': 1, '2': 7}, character='Bob', machine='pc'),
               row(seq=3, item_changes={'2589': 4}, character='Bob', machine='pc')]
    out = items.project(records)
    assert [t['status'] for t in out['transfers']] == ['transfer']
    assert out['team'] == {'in_units': 0, 'out_units': 0}


def test_bags_still_loading_after_a_login_baseline_are_baselines():
    # Beta: 81 Light Shot arrived in a second entry 0 s after the login baseline, already held.
    records = [row(at=10, seq=1, baseline_missing=True), row(at=10, seq=2, item_changes={'2516': 81}),
               row(at=12, seq=3, item_changes={'2770': 8}), row(at=13, seq=4, item_changes={'2835': 1}),
               row(at=20, seq=5, baseline_missing=True), row('CHAT_MSG_LOOT', at=20, seq=6),
               row(at=21, seq=7)]
    out = items.project(records)
    assert len(out['baselines']) == 4
    assert [m['item_id'] for m in out['movements']] == [2835, 2589]


def test_auto_loot_takes_every_attachment_and_other_players_loot_is_ignored():
    message = mail(count=2)
    message['items'].append({'link': '|Hitem:2770:::::::::|h[Copper Ore]|h|r', 'info': {'4': 3}})
    records = [row('MAIL_INBOX_UPDATE', seq=0, inbox={'messages': [message]}),
               row('AutoLootMailItem', seq=1, arguments={'1': 1}),
               row(seq=2, item_changes={'2589': 2, '2770': 3})]
    assert {p['category'] for m in items.project(records)['movements'] for p in m['parts']} == {'mail in'}
    rows = [row('CHAT_MSG_LOOT', seq=1, arguments={
        '1': 'Bob receives loot: |cnIQ1:|Hitem:2589:::::::::|h[Linen Cloth]|h|r'}), chat(seq=1), row()]
    assert items.project(rows)['movements'][0]['parts'][0]['category'] == 'gathered or looted'


def test_own_mail_matches_summed_counts_across_several_takes_or_sends():
    message = mail(sender='Fixture Surname', count=20)
    second = deepcopy(message['items'][0])
    message['items'].append(second)
    bob = {'character': 'Bob', 'machine': 'pc'}
    records = [row('SendMail', at=50, seq=1, arguments={'1': 'Bob'}), row(at=50, item_changes={'2589': -40}),
               row('MAIL_INBOX_UPDATE', seq=0, inbox={'messages': [message]}, **bob),
               row('TakeInboxItem', seq=1, arguments={'1': 1, '2': 1}, **bob),
               row(seq=2, item_changes={'2589': 20}, **bob),
               row('TakeInboxItem', at=103, seq=3, arguments={'1': 1, '2': 2}, **bob),
               row(at=103, seq=4, item_changes={'2589': 20}, **bob)]
    out = items.project(records)
    assert [(t['status'], t['units'], t['mails'], t['takes']) for t in out['transfers']] == [('transfer', 40, 1, 2)]
    assert out['team'] == {'in_units': 0, 'out_units': 0}
    sends = [row('SendMail', at=50, seq=1, arguments={'1': 'Bob'}), row(at=50, item_changes={'2589': -20}),
             row('SendMail', at=60, seq=1, arguments={'1': 'Bob'}), row(at=60, item_changes={'2589': -20})]
    message['items'] = [{'link': second['link'], 'info': {'4': 40}}]
    out = items.project(sends + [records[2], records[3], row(seq=2, item_changes={'2589': 40}, **bob)])
    assert [(t['status'], t['units'], t['mails'], t['takes']) for t in out['transfers']] == [('transfer', 40, 2, 1)]


def test_unresolved_mail_is_not_hidden_by_generic_receive_chat():
    rows = receive(mail(header={}))
    rows[-1] = row(seq=3)
    rows.insert(2, chat('You receive item:', seq=2))
    part = items.project(rows)['movements'][0]['parts'][0]
    assert part['category'] == 'mail in (unidentified)' and part['reason']


def test_own_mail_combines_multiple_attachment_parts_in_one_bag_entry():
    message = mail(sender='Fixture Surname', count=12)
    attachment = deepcopy(message['items'][0])
    attachment['info']['4'] = 20
    message['items'].append(attachment)
    records = [row('SendMail', at=99, seq=1, arguments={'1': 'Bob Surname'}),
               row(at=99, item_changes={'2589': -32}),
               row('MAIL_INBOX_UPDATE', seq=0, inbox={'messages': [message]}, character='Bob', machine='pc'),
               row('TakeInboxItem', seq=1, arguments={'1': 1, '2': 1}, character='Bob', machine='pc'),
               row('TakeInboxItem', seq=2, arguments={'1': 1, '2': 2}, character='Bob', machine='pc'),
               row(seq=3, item_changes={'2589': 32}, character='Bob', machine='pc')]
    out = items.project(records)
    assert len(out['transfers']) == 1 and out['transfers'][0]['status'] == 'transfer'
    assert out['transfers'][0]['units'] == 32 and out['team'] == {'in_units': 0, 'out_units': 0}


def test_shared_beta_reconciliation_normalizes_persisted_string_ids():
    from brownstone import beta_evidence
    report = {'checks': []}
    before, after = snapshot(count=5), snapshot(at=110, count=3)
    beta_evidence._bag_residual(report, before, after, [row(item_changes={'2589': -2})])
    assert report['checks'][0]['status'] == 'pass'
    assert report['checks'][0]['detail'] == {'residual_units': {}}
    with pytest.raises(ValueError, match='readable'):
        beta_evidence.inventory_change(before, snapshot(slots=[{'item_id': None, 'count': None}]))


def test_load_reads_families_and_snapshots_once(tmp_path):
    config = fixture(tmp_path)
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb'), read_only=True) as db:
        queries = []
        class Reader:
            def execute(self, query, params):
                queries.append(query)
                return db.execute(query, params)
        items.load(config, Reader())
        reads = [q for q in queries if q.startswith('SELECT record_json')]
        assert len(reads) == 2
        assert sum('FROM character_journal' in q for q in reads) == 1
        assert "('bags','loot','craft','vendor','mail','auction')" in reads[0]


@pytest.mark.parametrize('prices,vendors,expected,rate,unpriced', [
    ({2589: 101}, {2589: 50}, 285, 1710, 0), ({2589: 0}, {2589: 50}, 150, 900, 0),
    ({}, {2589: 0}, 0, None, 3)])
def test_earnings_world_loot_values_auction_vendor_unknown_and_quest_choices(prices, vendors, expected, rate, unpriced):
    records = [row('OBSERVE', at=100, login_at=100), chat(at=200, login_at=100), row(at=200, login_at=100),
               row('GetQuestReward', at=250, login_at=100, arguments={'1': 2}),
               row('QUEST_TURNED_IN', at=250, login_at=100, seq=3, family='quest', rewards={'items': [
                   {'kind': 'reward', 'link': '|Hitem:2589:|h[Cloth]', 'info': {'3': 1}},
                   {'kind': 'choice', 'index': 1, 'link': '|Hitem:2589:|h[Cloth]', 'info': {'3': 99}},
                   {'kind': 'choice', 'index': 2, 'link': '|Hitem:2589:|h[Cloth]', 'info': {'3': 1}}]}),
               row('MERCHANT_SHOW', at=300, login_at=100), chat(at=350, login_at=100, seq=4),
               row(at=350, login_at=100, seq=5), row('MERCHANT_CLOSED', at=400, login_at=100),
               row('OBSERVE', at=800, login_at=100)]
    out = earnings.project(records, prices=prices, vendors=vendors)['characters'][0]['total']
    assert out['loot_copper'] == expected and out['loot_per_hour_copper'] == rate
    assert out['unpriced_units'] == unpriced
    assert out['world_copper'] == 0 and out['xp_label'] == 'XP not captured'
    assert earnings.item_ids({('Fixture',): {'observations': [(r, 'fixture') for r in records]}}) == {2589}
    loot = row('LOOT_OPENED', at=199, login_at=100, loot_slots=[
        {'link': '|Hitem:2589:|h[Cloth]', 'vendor_sell_copper': 20}])
    fallback = earnings.project(records + [loot], prices=prices, vendors=vendors)['characters'][0]['total']
    assert fallback['loot_copper'] == (expected if expected else 60)
    assert fallback['unpriced_units'] == 0
