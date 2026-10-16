"""STORY-073: sanitized beta shapes
    every test is offline and uses disposable storage."""
import json
from copy import deepcopy
from pathlib import Path

import duckdb
import pytest
from test_scans import addon_source
from test_today import MARKET, plan

from brownstone import sales
from brownstone.beta_markdown import _your_sales
from brownstone.config import _validate_flood, build_source
from brownstone.markets import MARKET_KEYS
from brownstone.storage import ensure_schema
from views.today_rows import sales_text, sell_row

FIXTURES = Path(__file__).parent / 'fixtures' / 'sales'
KEY = ('Fixture', 'Fixture Realm', 'Alliance')


def fixture(name):
    return json.loads((FIXTURES / f'{name}.json').read_text(encoding='utf-8'))


def posted(item=2589, quantity=5, price=23, at=1000, login=1):
    rows = [fixture(k) for k in ('post', 'created', 'bag')]
    for seq, r in enumerate(rows, 1):
        r.update(captured_at=at, login_at=login, sequence=seq, entry_id=f'fixture:{at}:{seq}')
    rows[0]['arguments'].update({'3': quantity, '4': price})
    rows[2]['item_changes'] = {str(item): -quantity}
    return rows


def invoice(name='Linen Cloth', count=5, total=115, cut=5, at=2000):
    r = fixture('seller')
    r.update(captured_at=at, entry_id=f'mail:{at}:1')
    m = r['inbox']['messages'][0]
    m['header'].update({'4': f'Auction successful: {name} ({count})', '5': total + 100 - cut, '7': 30})
    m['invoice'].update({'2': name, '4': total, '7': cut, '11': count})
    return r


def returned(kind='expired', item=2589, count=1, at=2000):
    r = fixture('expired')
    r.update(captured_at=at, entry_id=f'return:{at}:1')
    m = r['inbox']['messages'][4]
    m['header'].update({'4': f'Auction {kind}: Linen Cloth', '7': 30})
    m['items'][0]['link'] = f'|Hitem:{item}::::::::|h[Linen Cloth]|h|r'
    m['items'][0]['info']['4'] = count
    r['inbox']['messages'] = [m]
    return r


def test_confirmed_post_and_refused_hook():
    records = posted()
    result = sales.project(records)['posts'][0]
    assert result['confirmed'] and result['quantity'] == 5 and result['unit_copper'] == 23
    assert result['duration_hours'] == 24 and result['item_id'] == 2589
    error = deepcopy(records[1])
    error['event'] = 'AUCTION_HOUSE_SHOW_ERROR'
    refused = sales.project([records[0], error])
    assert not refused['posts'][0]['confirmed'] and refused['items'] == []
    assert 'refused' in refused['posts'][0]['reason']


@pytest.mark.parametrize('missing', [1, 2])
def test_creation_and_bag_both_required_same_login_before_next_hook(missing):
    records = posted()
    records[missing]['login_at'] = 2
    assert not sales.project(records)['posts'][0]['confirmed']
    records = posted()
    next_hook = deepcopy(records[0])
    next_hook['entry_id'] = 'fixture:1000:2'
    records[1]['entry_id'] = 'fixture:1000:3'
    records[2]['entry_id'] = 'fixture:1000:4'
    assert not sales.project([records[0], next_hook, *records[1:]])['posts'][0]['confirmed']


def test_first_matching_bag_and_item_buyout_exact():
    records = posted(quantity=2)
    records[0]['event'] = 'C_AuctionHouse.PostItem'
    records[0]['arguments']['5'] = 600
    extra = deepcopy(records[2])
    extra.update(entry_id='fixture:1000:4', item_changes={'2318': -2})
    p = sales.project([*records, extra])['posts'][0]
    assert p['confirmed'] and p['item_id'] == 2589 and p['unit_copper'] == 300
    records[0]['arguments']['5'] = 601
    assert not sales.project(records)['posts'][0]['confirmed']


def test_invoice_spans_posts_same_price_names_narrow_identity():
    records = [*posted(quantity=1, price=44), *posted(quantity=1, price=44, at=1100),
               *posted(item=2672, quantity=4, price=44, at=1200),
               invoice(count=2, total=88, cut=4)]
    x = sales.project(records, {2589: {'Linen Cloth'}, 2672: {'Stringy Wolf Meat'}})
    row = next(r for r in x['items'] if r['item_id'] == 2589)
    assert (row['posted'], row['sold'], row['resolved'], row['average_copper']) == (2, 2, 2, 42)
    assert x['unidentified'] == 0


@pytest.mark.parametrize('names,reason', [({}, 'no matching item'),
                                          ({2589: {'Linen Cloth'}, 2318: {'Linen Cloth'}},
                                           'multiple matching items')])
def test_unidentified_invoice_retains_reason_no_item_credit(names, reason):
    x = sales.project([*posted(), *posted(item=2318, at=1100), invoice()], names)
    assert x['unidentified'] == 1 and x['outcomes'][0]['reason'] == reason
    assert all(r['sold'] == 0 for r in x['items'])


@pytest.mark.parametrize('at', [999, 91001])
def test_invoice_time_window_excludes_future_or_expired_post(at):
    x = sales.project([*posted(), invoice(at=at)], {2589: {'Linen Cloth'}})
    assert x['unidentified'] == 1


def test_repeat_late_buyer_collected_money_and_max_multiplicity():
    first = invoice()
    second = deepcopy(first)
    second.update(captured_at=2003, entry_id='mail:2003:2')
    second['inbox']['messages'][0]['invoice']['3'] = 'Late buyer'
    collected = deepcopy(second)
    collected.update(captured_at=2004, entry_id='mail:2004:3')
    collected['inbox']['messages'][0]['header']['5'] = 0
    x = sales.project([*posted(), first, second, collected], {2589: {'Linen Cloth'}})
    assert len(x['outcomes']) == 1 and x['items'][0]['sold'] == 5
    assert x['outcomes'][0]['observed_money'] == [210, 0]
    assert x['outcomes'][0]['net_copper'] == 110
    first['inbox']['messages'] *= 2
    second['inbox']['messages'] *= 2
    x = sales.project([*posted(), first, second], {2589: {'Linen Cloth'}})
    assert len(x['outcomes']) == 2 and x['items'][0]['sold'] == 10


def test_arrival_estimate_two_minute_boundary_and_character():
    first = invoice()
    later = deepcopy(first)
    later.update(captured_at=10640, entry_id='mail:10640:2')
    later['inbox']['messages'][0]['header']['7'] = 29.9
    assert len(sales.messages([first, later])) == 1
    later['captured_at'] += 121
    assert len(sales.messages([first, later])) == 2
    later['captured_at'] -= 121
    later['character'] = 'Other'
    assert len(sales.messages([first, later])) == 2


def test_buyer_ignored_and_invalid_invoice_not_credited():
    r = invoice()
    r['inbox']['messages'][0]['invoice']['1'] = 'buyer'
    assert sales.project([r])['outcomes'] == []
    r['inbox']['messages'][0]['invoice'].update({'1': 'seller', '11': 0})
    assert sales.project([r])['outcomes'][0]['reason'] == 'invalid invoice units or copper'
    r['inbox']['messages'][0]['header'].pop('7')
    assert sales.project([r])['outcomes'] == []


def test_returns_rate_rounding_runs_reset_and_name_from_attachment():
    records = [*posted(price=44), returned(count=1), returned('canceled', count=2, at=2100),
               returned(at=2200)]
    x = sales.project(records)
    row = x['items'][0]
    assert (row['expired'], row['cancelled'], row['expiry_run']) == (2, 2, 3)
    assert sales_text(row) == '0 of 4 sold'
    records.append(invoice(count=3, total=132, cut=6, at=2300))
    row = sales.project(records)['items'][0]
    assert (row['sold'], row['resolved'], row['average_copper'], row['expiry_run']) == (3, 7, 42, 0)
    assert row['newest_sale'] == 2300
    assert sales_text(row) == '3 of 7 sold · 42c each after cut'
    assert sales_text(sales.combined(sales.project(posted()), 2589)) == 'none resolved yet'


def test_today_display_only_low_reason_and_character_aggregation():
    records = [*posted(item=3), returned(item=3), returned(item=3, at=2200), returned(item=3, at=2400)]
    data = sales.project(records)
    before, after = plan(), plan(sales_data=data)
    assert before['buy'] == after['buy']
    assert before['shopping_total_copper'] == after['shopping_total_copper']
    assert after['sell'][0]['confidence'] == 'Low'
    assert 'expired 3 times running' in after['craft'][0]['confidence_reasons']
    assert sell_row(after['sell'][0])['Your sales'] == '0 of 3 sold'
    assert sales.combined(data, 3, ('Other', 'Fixture Realm', 'Alliance'))['resolved'] == 0
    assert sales.combined(data, 3, KEY)['expiry_run'] == 3
    higher = plan(sales_data=data, market={**MARKET, 'max_expiries': 4})
    assert 'expired 3 times running' not in higher['craft'][0]['confidence_reasons']
    reset = sales.project([*records, invoice(count=5, total=115, cut=5, at=2600)], {3: {'Linen Cloth'}})
    assert 'expired 3 times running' not in plan(sales_data=reset)['craft'][0]['confidence_reasons']
    assert _your_sales(data)[1] == '## Your sales'


@pytest.mark.parametrize('value', [0, -1, True, 1.5, '3'])
def test_max_expiries_invalid(value):
    with pytest.raises(ValueError, match='max_expiries must be a positive integer'):
        _validate_flood({'max_expiries': value})


def test_max_expiries_shared_and_source_override(tmp_path):
    config = addon_source(tmp_path)
    assert build_source({**config, 'max_expiries': 5}, {})['max_expiries'] == 5
    assert build_source({**config, 'max_expiries': 5}, {'max_expiries': 2})['max_expiries'] == 2


@pytest.mark.parametrize('key', ['source_id', *MARKET_KEYS])
def test_scoped_reader_never_borrows_records_or_names(tmp_path, key):
    config = addon_source(tmp_path)
    tmp_path.mkdir(exist_ok=True)
    with duckdb.connect(str(tmp_path / 'brownstone.duckdb')) as db:
        ensure_schema(db)
        for r in [*posted(), invoice()]:
            fields = {'source_id': config['source_id'], **{k: config[k] for k in MARKET_KEYS},
                      'entry_id': r['entry_id'], 'character': r['character'], 'character_realm': r['realm'],
                      'character_faction': r['faction'], 'family': r['family'], 'captured_at': '2026-10-10',
                      'collection_id': 'fixture', 'source_sha256': 'fixture',
                      'record_json': json.dumps(r), 'record_sha256': r['entry_id']}
            db.execute(f"INSERT INTO character_journal ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
                       list(fields.values()))
        assert len(sales.load(config, db)['posts']) == 1
        assert sales.load({**config, key: 'other'}, db)['posts'] == []
    assert sales.load({'data_dir': tmp_path / 'missing'})['items'] == []


def test_round_average_down_and_ignore_unrelated_return_mail():
    data = sales.project([*posted(price=18), invoice(count=3, total=54, cut=2)], {2589: {'Linen Cloth'}})
    assert data['items'][0]['net_copper'] == 52 and data['items'][0]['average_copper'] == 17
    r = returned()
    r['inbox']['messages'][0]['header']['3'] = 'Friend'
    assert sales.project([r])['outcomes'] == []
    r['inbox']['messages'][0]['header']['3'] = 'Alliance Auction House'
    r['inbox']['messages'][0]['header']['4'] = 'Unrelated subject'
    assert sales.project([r])['outcomes'] == []


def test_no_login_never_confirms_and_link_names_from_other_records():
    records = posted()
    for r in records:
        r.pop('login_at')
    assert not sales.project(records)['posts'][0]['confirmed']
    records = posted()
    records[2]['items'] = {'link': '|Hitem:2589::::::::|h[Linen Cloth]|h|r'}
    assert sales.project([*records, invoice()])['unidentified'] == 0


def test_beta_report_uses_same_projection_and_scan_names(tmp_path):
    from test_beta_report import database, write
    from test_scans import FINISHED, NOW, listing, scan

    from brownstone.beta_report import create_report

    records = [*posted(at=FINISHED - 100), invoice(at=FINISHED), returned(at=FINISHED + 10)]
    for r in records:
        r['realm'] = 'Beta'
        r.pop('captured_at_utc', None)
        r['arguments'] = {int(k) if k.isdecimal() else k: v for k, v in r['arguments'].items()}
        if 'item_changes' in r:
            r['item_changes'] = {int(k): v for k, v in r['item_changes'].items()}
    db = database()
    db['journal'] = without_nil(records)
    db['scans'] = [scan('sale-names', FINISHED, [listing(2589, 5, 115, 'Linen Cloth')])]
    path = write(tmp_path, db)
    config = addon_source(tmp_path / 'data', path)
    folder, report, _ = create_report(path, config, tmp_path / 'reports', now=NOW)
    section = report['your_sales']
    assert section['posts'][0]['confirmed']
    assert section['unidentified'] == 0
    assert section['items'][0]['sold'] == 5 and section['items'][0]['expired'] == 1
    text = (folder / 'report.md').read_text(encoding='utf-8')
    assert '## Your sales' in text and 'confirmed · item 2589' in text
    assert 'Gross 115c · cut 5c · deposit 100c' in text
    assert 'sold · 5 units · item 2589' in text and 'expired · 1 units · item 2589' in text
    # Another market's scan cannot supply the name required to identify an invoice.
    db['scans'][0]['faction']['player'] = 'Horde'
    records[-1]['inbox']['messages'] = []  # Remove the attachment's independent name evidence.
    db['journal'] = without_nil(records)
    path = write(tmp_path, db)
    _, report, _ = create_report(path, config, tmp_path / 'reports', now=NOW)
    assert report['your_sales']['unidentified'] == 1


def without_nil(value):
    if isinstance(value, dict):
        return {k: without_nil(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [without_nil(v) for v in value]
    return value


def test_today_loads_sales_once_and_build_is_pure(tmp_path, monkeypatch):
    from unittest.mock import Mock

    from test_metrics import import_records
    from test_scan_v3 import rich
    from test_scans import NOW

    from brownstone.today import build_today
    from brownstone.today_loading import load_today
    from brownstone.today_settings import TodaySettings

    config = import_records(tmp_path, rich())
    evidence = sales.project([*posted(), invoice()], {2589: {'Linen Cloth'}})
    reader = Mock(return_value=evidence)
    monkeypatch.setattr(sales, 'load', reader)
    _, other = load_today(config, [], TodaySettings(), {}, NOW)
    assert other['sales_data'] is None and reader.call_count == 0
    _, args = load_today(config, [], TodaySettings(), {}, NOW, flood=True)
    assert args['sales_data'] is evidence and reader.call_count == 1
    monkeypatch.setattr(sales, 'load', Mock(side_effect=AssertionError('calculations must not load')))
    assert build_today(**args)['today_version'] == 14


def test_team_rate_combines_units_and_net_before_rounding():
    records = [*posted(price=18), invoice(count=3, total=54, cut=2)]
    other = [*posted(price=18, at=1100), invoice(count=2, total=36, cut=1, at=2200)]
    for r in other:
        r['character'] = 'Other'
    data = sales.project([*records, *other], {2589: {'Linen Cloth'}})
    assert sales.combined(data, 2589) == {'sold': 5, 'resolved': 5, 'average_copper': 17, 'expiry_run': 0}
    assert sales.combined(data, 2589, KEY)['sold'] == 3


@pytest.mark.parametrize('quantity,price', [(0, 18), (True, 18), (1, 0), (1, 1.5)])
def test_post_needs_positive_integer_units_and_copper(quantity, price):
    assert not sales.project(posted(quantity=quantity, price=price))['posts'][0]['confirmed']
