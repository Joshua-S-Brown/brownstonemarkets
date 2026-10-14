"""Offline journal gathering classification, stretch boundaries and copper valuation."""
import pytest

from brownstone import farming


def record(event, time, **fields):
    return ({'event': event, 'captured_at': time, 'sequence': time * 10 + (event == 'CHAT_MSG_LOOT'),
             'entry_id': f'{event}:{time}', 'login_at': 1, **fields}, 'pc')


def loot(time, item=2770, quantity=1, guid='GameObject-0-1-2-3-1731-0001', map_id=1429, delay=0):
    return [record('LOOT_OPENED', time, zone={'zone': 'Arbitrary zone', 'map_id': map_id},
                   loot_slots=[{'link': f'|Hitem:{item}|h', 'sources': {'1': guid}}]),
            record('CHAT_MSG_LOOT', time + delay,
                   arguments={'1': f'Anything: |Hitem:{item}|h[misleading name]|h|r x{quantity}.'})]


@pytest.mark.parametrize(('guid', 'kind', 'object_id'), [
    ('Creature-0-1-2-3-299-abc', 'mob', None),
    ('GameObject-0-1-2-3-1731-abc', 'object', 1731),  # node
    ('GameObject-0-1-2-3-2843-abc', 'object', 2843),  # chest
    ('GameObject-0-1-2-3-180248-abc', 'object', 180248),  # fishing pool
    ('Player-abc', 'unknown', None), ('', 'unknown', None)])
def test_guid_source_and_object_id(guid, kind, object_id):
    row = farming.gathered(loot(100, guid=guid))[0]
    assert (row['source_kind'], row['object_id']) == (kind, object_id)


@pytest.mark.parametrize(('delay', 'count'), [(0, 1), (5, 1), (6, 0)])
def test_five_second_boundary_and_quantities(delay, count):
    rows = farming.gathered(loot(100, quantity=7, delay=delay))
    assert len(rows) == count
    if rows:
        assert rows[0]['units'] == 7 and rows[0]['item_id'] == 2770
    events = loot(200)
    events[1][0]['arguments']['1'] = '|Hitem:2770|h[Name x99]|h|r'
    assert farming.gathered(events)[0]['units'] == 1


@pytest.mark.parametrize(('event', 'family'), [('TakeInboxItem', 'mail'), ('AutoLootMailItem', 'mail'),
                                              ('DoTradeSkill', 'craft'), ('BuyMerchantItem', 'vendor'),
                                              ('AcceptTrade', 'trade')])
def test_mail_craft_vendor_trade_excluded(event, family):
    window, message = loot(100, delay=2)
    assert farming.gathered([window, record(event, 101, family=family), message]) == []
    assert farming.gathered([message]) == []


def test_item_match_machine_login_dedup_and_names():
    events = loot(100)
    events[1][0]['arguments']['1'] = '|Hitem:999|h[2770 Copper Ore]|h|r'
    assert farming.gathered(events) == []
    events = loot(100)
    assert len(farming.gathered(events + events)) == 1
    assert farming.gathered([events[0], (events[1][0], 'other')]) == []
    events[1][0]['login_at'] = 2
    assert farming.gathered(events) == []
    assert farming.gathered([record('CHAT_MSG_LOOT', 100, arguments={'1': 'Copper Ore x5'})]) == []


def test_idle_map_short_stretches_integer_rates_and_evidence():
    events = sum((loot(t, quantity=2) for t in (0, 150, 300, 900)), [])
    events += sum((loot(t, map_id=2) for t in (901, 1000)), [])
    events += loot(1701, map_id=2)
    result = farming.history(events)
    assert len(result['stretches']) == 3  # gap of exactly ten minutes remains in the first
    assert result['excluded_stretches'] == 2
    assert result['recorded_seconds'] == 999
    row = result['rows'][0]
    assert row['units'] == 8 and row['units_per_hour'] == 32
    assert row['seconds'] == 900 and row['stretches'] == 1 and row['object_ids'] == [1731]
    assert len(farming.history(events, idle_minutes=2)['stretches']) == 6


def test_five_minutes_three_loots_and_summed_rates():
    events = sum((loot(t, quantity=1) for t in (0, 150, 300, 1000, 1100, 1301)), [])
    result = farming.history(events)
    assert result['excluded_stretches'] == 0
    assert result['rows'][0]['seconds'] == 601
    assert result['rows'][0]['stretches'] == 2
    assert result['rows'][0]['units_per_hour'] == 35
    assert farming.history(loot(0) + loot(300))['excluded_stretches'] == 1
    assert farming.history(loot(0) + loot(100) + loot(299))['excluded_stretches'] == 1


def test_rate_rests_on_all_zone_time_not_only_stretches_with_the_item():
    first = sum((loot(t) for t in (0, 150, 300)), [])
    second = sum((loot(t, item=2589) for t in (2000, 2150, 2300)), [])
    rows = {r['item_id']: r for r in farming.history(first + second)['rows']}
    assert rows[2770]['seconds'] == rows[2589]['seconds'] == 600
    assert rows[2770]['stretches'] == 2 and rows[2770]['units_per_hour'] == 18


def test_missing_price_typical_copper_cut_and_top_order():
    history = farming.history(sum((loot(t, quantity=2) + loot(t + 1, item=2589) for t in (0, 150, 300)), []))
    signals = [{'item_id': 2770, 'variant_id': None, 'variant_state': 'base',
                'overshoot': {'typical_copper': 100}}]
    result = farming.valued(history, {2770: 11}, signals, .05)
    row, missing = result['rows']
    assert row['units_per_hour'] == 71
    assert row['value_per_hour_copper'] == 741 and type(row['value_per_hour_copper']) is int
    assert row['typical_price_copper'] == 100
    assert missing['value_per_hour_copper'] is None and missing['typical_price_copper'] is None
    assert farming.valued(history, {2770: 0}, [], .05)['rows'][0]['value_per_hour_copper'] is None


def test_journal_source_and_full_house_scope(tmp_path):
    import duckdb
    from test_journal import entry
    from test_scans import NOW, addon_source

    from brownstone import journal, professions, storage
    config = addon_source(tmp_path / 'data', tmp_path / 'unused.lua')
    config['data_dir'].mkdir()
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb')) as db:
        storage.ensure_schema(db)
        for scope in (config, config | {'source_id': 'other'}, config | {'faction': 'horde'}):
            for pair in loot(100):
                raw = entry() | {k: v for k, v in pair[0].items() if k not in ('entry_id', 'captured_at')}
                raw['arguments']['n'] = 1
                raw['family'] = 'loot'
                raw['entry_id'] = f"{scope['source_id']}:{scope['faction']}:{pair[0]['entry_id']}"
                journal.load_one(db, scope, raw, journal.summarize(raw, NOW), 'collection', 'hash')
    data = professions.latest_data(config)
    assert len(data) == 1
    observations = next(iter(data.values()))['observations']
    assert len(observations) == 2
    assert len(farming.gathered(observations)) == 1


def test_idle_setting_default_inheritance_override_validation(tmp_path):
    from test_scans import addon_source

    from brownstone.config import build_source
    base = dict(addon_source(tmp_path, tmp_path / 'scan.lua'))
    base.pop('market_id')
    base.pop('data_dir')
    base.pop('farming_idle_minutes')
    assert build_source(base, {})['farming_idle_minutes'] == 10
    assert build_source(base | {'farming_idle_minutes': 15}, {})['farming_idle_minutes'] == 15
    assert build_source(base | {'farming_idle_minutes': 15}, {'farming_idle_minutes': 3})['farming_idle_minutes'] == 3
    for invalid in (0, -1, True, 1.5, '10'):
        with pytest.raises(ValueError, match='farming_idle_minutes'):
            build_source(base, {'farming_idle_minutes': invalid})


def test_stretch_rule_is_map_and_idle_across_logins():
    events = loot(0) + loot(150) + loot(300)
    for row, _ in events[2:]:
        row['login_at'] = 2
    history = farming.history(events)
    assert len(history['stretches']) == 1 and history['rows'][0]['units_per_hour'] == 36
