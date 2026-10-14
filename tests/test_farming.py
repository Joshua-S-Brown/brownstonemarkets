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


@pytest.mark.parametrize(('guid', 'expected'), [
    ('Creature-0-1-2-3-299-abc', ('mob', 299)),
    ('GameObject-0-1-2-3-1731-abc', ('object', 1731)),
    ('GameObject-0-1-2-3-0-abc', ('object', 0)),
    ('Creature-broken', ('mob', None)), ('Creature-0-1-2-3-no-abc', ('mob', None)),
    ('Creature-0-1-2-3-0-abc', ('mob', None)), ('unknown', ('unknown', None)),
])
def test_npc_source_identity(guid, expected):
    assert farming.source({'sources': {'1': guid}}) == expected


def mob_loot(time, npc, item=2589, quantity=1, map_id=1):
    return loot(time, item=item, quantity=quantity, guid=f'Creature-0-1-2-3-{npc}-abc', map_id=map_id)


def test_spot_votes_windows_not_items_tie_and_mixed_camps():
    events = mob_loot(0, 20) + mob_loot(150, 10) + mob_loot(300, 20) + mob_loot(450, 10)
    # Two item messages in one window must not give that NPC an extra vote.
    events[0][0]['loot_slots'].append({'link': '|Hitem:2770|h', 'sources': {'1': 'Creature-0-1-2-3-20-abc'}})
    events.append(record('CHAT_MSG_LOOT', 1, arguments={'1': '|Hitem:2770|h[Name]|h'}))
    events += mob_loot(2000, 30) + mob_loot(2150, 30) + mob_loot(2300, 30)
    events += loot(4000, map_id=1) + loot(4150, map_id=1) + loot(4300, map_id=1)
    history = farming.history(events + events)
    first, second, gathering = history['spots']
    assert (first['npc_id'], first['also_looted'], first['seconds'], first['stretches']) == (10, [20], 450, 1)
    assert first['items'] == {2589: 4, 2770: 1}
    assert second['npc_id'] == 30 and second['items'] == {2589: 3}
    assert gathering['npc_id'] is None and gathering['items'] == {2770: 3}


def test_spot_aggregate_all_items_seconds_vendor_and_missing_prices():
    events = mob_loot(0, 10, quantity=2) + mob_loot(150, 10, item=2770) + mob_loot(301, 10, item=999)
    events += mob_loot(2000, 10) + mob_loot(2150, 10) + mob_loot(2300, 10)
    events += mob_loot(4000, 30, item=999) + mob_loot(4150, 30, item=999) + mob_loot(4300, 30, item=999)
    history = farming.history(events)
    result = farming.valued(history, {2589: 11, 2770: 0}, [], .05, {2589: 1000, 2770: 7, 999: 0})
    priced, missing = result['spots']
    assert priced['seconds'] == 601 and priced['stretches'] == 2
    assert priced['auction_value_copper'] == 52 and priced['vendor_value_copper'] == 7
    assert priced['value_copper'] == 59 and priced['value_per_hour_copper'] == 353
    assert type(priced['value_per_hour_copper']) is int
    assert [r['basis'] for r in priced['items']] == ['no price', 'auction', 'vendor']
    assert priced['no_price_items'] == priced['no_price_units'] == 1
    assert missing['value_per_hour_copper'] is None and missing['no_price_units'] == 3
    assert priced['coin_copper'] is None


@pytest.mark.parametrize('family', [None, 'vendor', 'mail', 'trade', 'auction'])
def test_coin_deferred_even_inside_window_or_across_transactions(family):
    events = sum((mob_loot(t, 10) for t in (0, 150, 300)), [])
    if family:
        events.append(record('transaction', 1, family=family))
    events += [record('PLAYER_MONEY', 2, before_copper=10, after_copper=100), record('LOOT_CLOSED', 3)]
    result = farming.valued(farming.history(events), {2589: 10}, [], .05)
    assert result['spots'][0]['coin_copper'] is None
    assert result['spots'][0]['value_copper'] == 28


def test_existing_ui13_rows_identical_with_spots_and_vendor_data():
    events = mob_loot(0, 20) + mob_loot(150, 10) + mob_loot(300, 20)
    events += loot(2000, map_id=1) + loot(2150, map_id=1) + loot(2300, map_id=1)
    result = farming.valued(farming.history(events), {2589: 11}, [], .05, {2770: 999})
    assert result['rows'] == [
        {'item_id': 2589, 'map_id': 1, 'source_kind': 'mob', 'zone': 'Arbitrary zone', 'units': 3,
         'object_ids': [], 'seconds': 600, 'stretches': 2, 'units_per_hour': 18, 'item_name': None,
         'sell_price_copper': 11, 'value_per_hour_copper': 188, 'typical_price_copper': None},
        {'item_id': 2770, 'map_id': 1, 'source_kind': 'object', 'zone': 'Arbitrary zone', 'units': 3,
         'object_ids': [1731], 'seconds': 600, 'stretches': 2, 'units_per_hour': 18, 'item_name': None,
         'sell_price_copper': None, 'value_per_hour_copper': None, 'typical_price_copper': None}]


def test_spot_scope_map_seconds_and_excluded_stretches():
    events = sum((mob_loot(t, 10, map_id=1) for t in (0, 150, 300)), [])
    events += sum((mob_loot(t, 10, map_id=2) for t in (1000, 1150, 1300)), [])
    events += mob_loot(2000, 20, map_id=2)
    result = farming.history(events)
    assert [(r['map_id'], r['npc_id'], r['seconds'], r['stretches']) for r in result['spots']] == [
        (1, 10, 300, 1), (2, 10, 300, 1)]
    assert result['excluded_stretches'] == 1
    # Identical window stamps on different machines or logins are distinct observations.
    events = mob_loot(0, 10) + mob_loot(150, 10) + mob_loot(300, 20)
    duplicate = mob_loot(0, 20)
    for r, _m in duplicate:
        r['entry_id'] += ':other'
        r['login_at'] = 2
    assert farming.history(events + duplicate)['spots'][0]['npc_id'] == 10


def positioned(time, x, y, **kwargs):
    events = mob_loot(time, 10, **kwargs)
    events[0][0]['zone'].update(x=x, y=y)
    return events


def test_position_cell_floor_median_distinct_windows_and_missing():
    events = positioned(0, .45, .70) + positioned(150, .49, .74) + positioned(300, .91, .11)
    # Several messages in one window do not overweight its position.
    for time in (301, 302, 303):
        events.append(record('CHAT_MSG_LOOT', time, arguments={'1': '|Hitem:2589|h[x]|h'}))
    result = farming.history(events)
    assert result['spots'][0]['cell'] == (45, 70)
    assert result['stretches'][0]['cell'] == (45, 70)
    assert farming.history(events, cell_percent=10)['spots'][0]['cell'] == (40, 70)
    assert farming.history(mob_loot(0, 10))['stretches'][0]['cell'] is None
    even = farming.gathered(positioned(0, .40, .60) + positioned(150, .50, .80))
    assert farming.position_cell(even) == (45, 70)
    boundary = farming.gathered(positioned(0, .30, .60) + positioned(150, .60, .80))
    assert farming.position_cell(boundary) == (45, 70)
    even[0]['zone']['x'] = float('nan')
    assert farming.position_cell(even) == (50, 80)


def test_position_splits_same_npc_into_spots_and_preserves_item_rows():
    events = sum((positioned(t, .42, .72) for t in (0, 150, 300)), [])
    events += sum((positioned(t, .63, .81) for t in (2000, 2150, 2300)), [])
    history = farming.history(events)
    assert [(s['npc_id'], s['cell'], s['seconds']) for s in history['spots']] == [
        (10, (40, 70), 300), (10, (60, 80), 300)]
    assert history['rows'][0]['seconds'] == 600 and history['rows'][0]['units'] == 6


@pytest.mark.parametrize(('scan_price', 'chosen', 'disagreement'), [(None, 7, False), (0, 7, False),
                                                                   (7, 7, False), (9, 9, True)])
def test_loot_vendor_fallback_scan_preference_and_disagreement(scan_price, chosen, disagreement):
    events = sum((mob_loot(t, 10, quantity=2) for t in (0, 150, 300)), [])
    for r, _ in events:
        if r['event'] == 'LOOT_OPENED':
            r['loot_slots'][0]['vendor_sell_copper'] = 7
    result = farming.valued(farming.history(events), {}, [], .05, {2589: scan_price})['spots'][0]
    assert result['vendor_value_copper'] == 6 * chosen
    assert result['items'][0]['unit_copper'] == chosen
    assert bool(result['vendor_disagreements']) is disagreement
    assert farming.valued(farming.history(events), {2589: 100}, [], .05)['spots'][0]['items'][0]['basis'] == 'auction'


def test_coin_slot_money_after_close_dedup_and_machine_login_scope():
    events = sum((mob_loot(t, 10) for t in (0, 150, 300)), [])
    events[0][0]['loot_slots'].append({'slot_type': 2, 'quantity': 0})
    events += [record('LOOT_CLOSED', 1), record('PLAYER_MONEY', 2, before_copper=10, after_copper=110)]
    result = farming.valued(farming.history(events + events), {2589: 10}, [], .05)['spots'][0]
    assert result['coin_copper'] == 100 and result['value_copper'] == 128
    other = events[:-1] + [(events[-1][0], 'other')]
    assert farming.history(other)['spots'][0]['coin_copper'] is None
    events[-1][0]['login_at'] = 2
    assert farming.history(events)['spots'][0]['coin_copper'] is None


@pytest.mark.parametrize('block', ['vendor', 'mail', 'craft', 'trade', 'auction', 'next_window', 'late', 'negative'])
def test_coin_needs_slot_and_bounded_uninterrupted_money(block):
    events = sum((mob_loot(t, 10) for t in (0, 150, 300)), [])
    events[0][0]['loot_slots'].append({'slot_type': 2, 'quantity': 0})
    if block == 'next_window':
        events.append(record('LOOT_OPENED', 1, loot_slots=[]))
    elif block not in ('late', 'negative'):
        events.append(record('other', 1, family=block))
    events.append(record('PLAYER_MONEY', 6 if block == 'late' else 2, before_copper=100,
                         after_copper=90 if block == 'negative' else 200))
    assert farming.history(events)['spots'][0]['coin_copper'] is None


def test_cell_setting_default_inheritance_override_validation(tmp_path):
    from test_scans import addon_source

    from brownstone.config import build_source
    base = dict(addon_source(tmp_path, tmp_path / 'scan.lua'))
    for key in ('market_id', 'data_dir', 'farming_cell_percent'):
        base.pop(key, None)
    assert build_source(base, {})['farming_cell_percent'] == 5
    assert build_source(base | {'farming_cell_percent': 10}, {})['farming_cell_percent'] == 10
    assert build_source(base | {'farming_cell_percent': 10}, {'farming_cell_percent': 3})['farming_cell_percent'] == 3
    for invalid in (0, -1, 101, True, 1.5, '5'):
        with pytest.raises(ValueError, match='farming_cell_percent'):
            build_source(base, {'farming_cell_percent': invalid})


def test_coin_only_window_inside_stretch_counts_and_vendor_reports_all_disagreements():
    events = sum((mob_loot(t, 10) for t in (0, 150, 300)), [])
    events += [record('LOOT_OPENED', 100, zone={'map_id': 1}, loot_slots=[{'slot_type': 2, 'quantity': 0}]),
               record('PLAYER_MONEY', 101, before_copper=10, after_copper=110)]
    events[0][0]['loot_slots'][0]['vendor_sell_copper'] = 7
    events[2][0]['loot_slots'][0]['vendor_sell_copper'] = 9
    spot = farming.valued(farming.history(events), {}, [], .05, {2589: 9})['spots'][0]
    assert spot['coin_copper'] == 100
    assert spot['vendor_value_copper'] == 27
    assert spot['vendor_disagreements'] == [{'item_id': 2589, 'scan_copper': 9, 'loot_copper': 7}]


def test_coin_only_window_in_other_map_does_not_value_the_spot():
    events = sum((mob_loot(t, 10) for t in (0, 150, 300)), [])
    events += [record('LOOT_OPENED', 100, zone={'map_id': 2}, loot_slots=[{'slot_type': 2}]),
               record('PLAYER_MONEY', 101, before_copper=10, after_copper=110)]
    assert farming.history(events)['spots'][0]['coin_copper'] is None


@pytest.mark.parametrize(('moment', 'expected'), [(400, 100), (900, 100), (901, None)])
def test_trailing_coin_only_window_joins_stretch_within_idle_limit(moment, expected):
    events = sum((mob_loot(t, 10) for t in (0, 150, 300)), [])
    events += [record('LOOT_OPENED', moment, zone={'map_id': 1}, loot_slots=[{'slot_type': 2, 'quantity': 0}]),
               record('PLAYER_MONEY', moment + 1, before_copper=10, after_copper=110)]
    spot = farming.history(events)['spots'][0]
    assert (spot['coin_copper'], spot['seconds']) == (expected, 300)


def named_window(time, npc=475, name='Kobold Tunneler'):
    pair = mob_loot(time, npc)[0]
    pair[0].update(target_guid=f'Creature-0-1-2-3-{npc}-abc', target_name=name)
    pair[0]['loot_slots'][0]['sources']['1'] = pair[0]['target_guid']
    return pair


def test_newest_npc_name_wins_without_changing_rates_spots_or_values():
    events = sum((mob_loot(t, 475) for t in (0, 150, 300)), [])
    baseline = farming.valued(farming.history(events), {2589: 100}, [], .05)
    named = events + [named_window(400, name='Old name'), named_window(500), named_window(600, name='')]
    result = farming.valued(farming.history(reversed(named)), {2589: 100}, [], .05)
    assert result['npc_names'] == {475: 'Kobold Tunneler'}
    assert result | {'npc_names': {}} == baseline
    assert farming.history([named_window(1, npc=999)])['npc_names'] == {999: 'Kobold Tunneler'}


@pytest.mark.parametrize(('guid', 'name', 'event'), [
    ('Player-475', 'Player', 'LOOT_OPENED'), ('Creature-0-1-2-3-475-other', 'Wrong target', 'LOOT_OPENED'),
    ('Creature-0-1-2-3-0-abc', 'Invalid ID', 'LOOT_OPENED'),
    ('Creature-0-1-2-3-475-abc', None, 'LOOT_OPENED'),
    ('Creature-0-1-2-3-475-abc', 'Kobold', 'CHAT_MSG_LOOT')])
def test_npc_names_ignore_invalid_or_unmatched_capture(guid, name, event):
    row, machine = named_window(100)
    row.update(target_guid=guid, target_name=name, event=event)
    assert farming.history([(row, machine)])['npc_names'] == {}


def test_npc_names_use_scoped_imported_observations(tmp_path):
    from test_journal import entry, write
    from test_scans import NOW, addon_source

    from brownstone import professions
    from brownstone.config import MARKET_KEYS
    from brownstone.pipeline import import_scans

    row = entry('named-loot')
    captured, _ = named_window(row['captured_at'])
    row.update({k: v for k, v in captured.items() if k not in ('captured_at', 'entry_id', 'sequence')})
    source = addon_source(tmp_path / 'data', write(tmp_path / 'own.lua', [row]))
    import_scans(source, now=NOW)
    data = professions.latest_data(source)
    assert farming.history(data[('Alice', 'Beta', 'Alliance')]['observations'])['npc_names'] == {475: 'Kobold Tunneler'}
    for field in ('source_id', *MARKET_KEYS):
        foreign = professions.latest_data(source | {field: str(source[field]) + '_other'})
        assert not foreign
