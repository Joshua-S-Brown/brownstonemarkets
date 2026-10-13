"""Offline stock evidence, integer units/prices and Save-only targets."""
from datetime import timedelta

import pytest
from test_character_snapshots import snapshot as raw_snapshot
from test_character_snapshots import write
from test_scans import NOW, addon_source, listing, scan

from brownstone import stock
from brownstone.pipeline import import_scans

# A real-shaped base link (Forever bag slots); ADDON-08 resolves it to the base item.
BASE = '|cnIQ1:|Hitem:2589::::::::6:1482:::::::::|h[Linen Cloth]|h|r'


def snapshot(*args, **kwargs):
    record = raw_snapshot(*args, **kwargs)
    for slot in record['slots']:
        slot['item_link'] = BASE
    return record


def fixture(tmp_path):
    alice = snapshot()
    bank = snapshot('a-bank', 'bank')
    bob = snapshot('bob', character='Bob')
    bob['slots'][0]['count'] = 5
    unreadable = snapshot('bad', character='Cara')
    unreadable['containers'][0]['size'] = 0
    empty = snapshot('b-bank', 'bank', character='Bob')
    empty['slots'] = []
    config = addon_source(tmp_path / 'data', write(tmp_path / 'own.lua', [alice, bank, bob, unreadable, empty],
                          [scan('stock-scan', int(NOW.timestamp()) - 60, [listing(2589, 5, 100),
                                                                       listing(2589, 10, 400)])]))
    import_scans(config, now=NOW)
    return config


def test_two_characters_locations_unknown_unreadable_missing_stale_and_scope(tmp_path):
    config = fixture(tmp_path)
    result = stock.load_stock(config, [], NOW)
    assert result['rows'][0]['held'] == 11
    assert result['rows'][0]['name'] == 'Linen Cloth'
    assert result['rows'][0]['unit_copper'] == 20
    assert result['value_copper'] == 220
    assert len(result['holdings']) == 3
    captures = {(r['character'], r['kind']): r for r in result['captures']}
    assert captures['Alice', 'bank']['age_hours'] is not None
    assert captures['Cara', 'bank']['unknown']
    assert captures['Cara', 'bags']['excluded'] == 1
    assert not captures['Bob', 'bank']['unknown'] and captures['Bob', 'bank']['units'] == 0
    assert stock.load_stock(config, [], NOW + timedelta(days=3))['freshness']['stale']
    assert not stock.load_stock(config | {'source_id': 'another'}, [], NOW)['rows']
    assert not stock.load_stock(config | {'faction': 'horde'}, [], NOW)['rows']
    assert not stock.load_stock(config | {'market_id': 'another-house'}, [], NOW)['rows']
    arguments = {'snapshot': result['snapshot'], 'observations': {2589: {'min_buyout': 0, 'market_value': 0}}}
    missing = stock.build_stock({}, [stock.Entry(2589, 10)], arguments, config, [], NOW)
    assert missing['rows'][0]['unit_copper'] is None
    from brownstone.character_snapshots import latest_data
    missing = stock.build_stock(latest_data(config), [], arguments, config, [], NOW)
    assert missing['excluded_prices'] == 1 and missing['value_copper'] == 0
    assert missing['rows'][0]['value_copper'] is None
    no_scan = stock.build_stock(latest_data(config), [], None, config, [], NOW)
    assert no_scan['freshness'] is None and no_scan['excluded_prices'] == 1


def test_targets_roundtrip_rejected_save_and_source_separation(tmp_path):
    path = stock.targets_path(tmp_path, 'one')
    entries = [stock.Entry(2589, 20, buy_copper=30), stock.Entry(2996, 0, buy_percent=80)]
    assert stock.load_entries(path) == []
    stock.save_entries(path, entries)
    saved = path.read_bytes()
    assert stock.load_entries(path) == entries
    assert stock.load_entries(stock.targets_path(tmp_path, 'two')) == []
    with pytest.raises(ValueError, match='One entry'):
        stock.save_entries(path, entries + entries)
    assert path.read_bytes() == saved and stock.load_entries(path) == entries
    path.write_text('{}')
    with pytest.raises(ValueError, match='JSON list'):
        stock.save_entries(path, entries)
    assert path.read_text() == '{}'


@pytest.mark.parametrize('args', [(True, 1), (0, 1), (1, -1), (1, 1.5), (1, 1, 0),
                                 (1, 1, None, 0), (1, 1, 10, 80)])
def test_invalid_targets(args):
    with pytest.raises(ValueError):
        stock.Entry(*args)


def test_shortfall_fixed_percentage_limits_whole_stacks_and_too_few():
    listings = [(5, 100, 20), (10, 400, 40)]
    fixed = stock.fill(stock.Entry(2589, 12, buy_copper=30), 3, listings, {})
    assert (fixed['short'], fixed['buy_units'], fixed['wait_units']) == (9, 5, 4)
    assert fixed['buy_cost_copper'] == 100 and fixed['fill_cost_copper'] == 500
    assert fixed['wait_cost_copper'] == 400
    percent = stock.fill(stock.Entry(2589, 12, buy_percent=75), 3, listings, {2589: {'market_value': 41}})
    assert percent['limit_copper'] == 30 and percent['buy_units'] == 5
    unavailable = stock.fill(stock.Entry(2589, 12, buy_percent=75), 3, listings, {})
    assert unavailable['limit_unknown'] and unavailable['buy_units'] == 0 and unavailable['wait_units'] == 9
    few = stock.fill(stock.Entry(2589, 30), 3, listings, {})
    assert few['unlisted_units'] == 12 and few['fill_cost_copper'] is None
    assert few['buy_units'] == 15 and few['buy_cost_copper'] == 500
    surplus = stock.fill(stock.Entry(2589, 2), 0, listings, {})
    assert surplus['buy_units'] == 2 and surplus['purchased_units'] == 5
    enough = stock.fill(stock.Entry(2589, 2), 3, listings, {})
    assert enough['short'] == enough['buy_cost_copper'] == 0
    zero = stock.fill(stock.Entry(2589, 2, buy_percent=1), 0, listings, {2589: {'market_value': 20}})
    assert zero['limit_copper'] == 0 and zero['buy_units'] == 0


def test_at_most_filtering_and_evidence_read_once(tmp_path, monkeypatch):
    config = fixture(tmp_path)
    stock.save_entries(stock.targets_path(config['data_dir'], config['source_id']), [stock.Entry(2589, 20)])
    counts = {}
    for name, module in [('latest_data', stock.character_snapshots), ('load_today', stock), ('load_entries', stock)]:
        original = getattr(module, name)
        def counted(*args, _name=name, _original=original, **kwargs):
            counts[_name] = counts.get(_name, 0) + 1
            return _original(*args, **kwargs)
        monkeypatch.setattr(module, name, counted)
    result = stock.load_stock(config, [], NOW)
    assert result['rows'][0]['short'] == 9 and result['rows'][0]['at_most']
    assert stock.filter_rows(result, 'LINEN') == stock.filter_rows(result, '2589') == result['rows']
    assert stock.filter_rows(result, 'not here') == stock.filter_rows(result, chains_only=True) == []
    assert counts == {'latest_data': 1, 'load_today': 1, 'load_entries': 1}
    # Removing the unknown character makes the recorded empty bank definitive.
    from brownstone.character_snapshots import latest_data
    data = {k: v for k, v in latest_data(config).items() if k[0] != 'Cara'}
    definite = stock.build_stock(data, result['entries'], None, config, [], NOW)
    assert not definite['rows'][0]['at_most']


def test_latest_readable_dedup_and_only_target_quotes(tmp_path, monkeypatch):
    old = snapshot('old')
    new = snapshot('new')
    new['captured_at'] += 10
    new.pop('captured_at_utc')
    new['slots'][0]['count'] = 7
    bad = snapshot('bad')
    bad['captured_at'] += 20
    bad.pop('captured_at_utc')
    bad['containers'][0]['size'] = 0
    config = addon_source(tmp_path / 'data', write(tmp_path / 'own.lua', [old, new, bad]))
    import_scans(config, now=NOW)
    import_scans(config, now=NOW)
    from brownstone.character_snapshots import latest_data
    calls = []
    original = stock.fill
    def fill(*args):
        calls.append(args[0].item_id)
        return original(*args)
    monkeypatch.setattr(stock, 'fill', fill)
    catalog = {'game_version': config['game_version'], 'rules_version': config['rules_version'],
               'items_by_id': {2589: {'name': 'Linen Cloth'}}}
    data = latest_data(config)
    result = stock.build_stock(data, [], None, config, [catalog], NOW)
    assert result['rows'][0]['held'] == 7 and calls == []
    assert result['captures'][0]['snapshot_id'] == 'new' and result['captures'][0]['excluded'] == 1
    assert stock.filter_rows(result, chains_only=True) == result['rows']
    result = stock.build_stock(data, [stock.Entry(2589, 20)], None, config, [catalog], NOW)
    assert calls == [2589] and result['rows'][0]['unlisted_units'] == 13


def test_percentage_limit_uses_the_scan_market_value_through_the_real_loader(tmp_path):
    config = fixture(tmp_path)
    stock.save_entries(stock.targets_path(config['data_dir'], config['source_id']),
                       [stock.Entry(2589, 30, buy_percent=150)])
    from brownstone.today_loading import load_today
    from brownstone.today_settings import TodaySettings
    _, arguments = load_today(config, [], TodaySettings(), {}, NOW, item_ids={2589})
    assert 'market_value' not in arguments['metrics'][2589]  # metrics never carried it
    reference = arguments['observations'][2589]['market_value']
    row = stock.load_stock(config, [], NOW)['rows'][0]
    assert not row['limit_unknown'] and row['limit_copper'] == reference * 150 // 100


def test_variants_and_unresolved_links_never_pool_with_the_base_item(tmp_path):
    base = snapshot()
    suffix = '|cnIQ2:|Hitem:2589::::::::6:1482:::1:12721::::::|h[Linen Cloth]|h|r'  # a bonus-ID variant
    base['slots'] += [dict(container_id=0, slot=2, item_id=2589, count=4, item_link=suffix),
                      dict(container_id=0, slot=3, item_id=2589, count=2, item_link='|Hitem:2589|h')]
    config = addon_source(tmp_path / 'data', write(tmp_path / 'own.lua', [base], [
        scan('stock-scan', int(NOW.timestamp()) - 60, [listing(2589, 5, 100)])]))
    import_scans(config, now=NOW)
    stock.save_entries(stock.targets_path(config['data_dir'], config['source_id']), [stock.Entry(2589, 10)])
    rows = {r['variant_state']: r for r in stock.load_stock(config, [], NOW)['rows']}
    assert (rows['base']['held'], rows['variant']['held'], rows['unresolved']['held']) == (3, 4, 2)
    assert rows['base']['short'] == 7  # only base units count toward the base target
    assert rows['variant']['unit_copper'] is None and rows['unresolved']['value_copper'] is None
    assert rows['variant']['name'] == 'Linen Cloth (variant, not priced)'


def test_partly_readable_capture_is_the_shared_latest_and_makes_shortfalls_at_most(tmp_path):
    partial = snapshot()
    partial['containers'] = [dict(container_id=0, size=2), dict(container_id=1, size=6, slots_readable=False)]
    config = addon_source(tmp_path / 'data', write(tmp_path / 'own.lua', [partial, snapshot('bank', 'bank')]))
    import_scans(config, now=NOW)
    stock.save_entries(stock.targets_path(config['data_dir'], config['source_id']), [stock.Entry(2589, 10)])
    result = stock.load_stock(config, [], NOW)
    bags = next(c for c in result['captures'] if c['kind'] == 'bags')
    assert bags['snapshot_id'] == partial['snapshot_id'] and bags['partial']  # same capture Team uses
    assert result['rows'][0]['held'] == 6 and result['rows'][0]['at_most']
