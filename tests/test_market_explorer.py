"""STORY-055: existing evidence composed without another pricing path."""
from copy import deepcopy
from datetime import timedelta
from pathlib import Path

import duckdb
import pytest
from test_scans import FINISHED, NOW, addon_source, listing, scan, write_scans

from brownstone import market_explorer as me
from brownstone.crafting import load_recipe_catalog
from brownstone.markets import MARKET_KEYS
from brownstone.pipeline import import_scans


def explorer_fixture(tmp_path, count=2):
    config = addon_source(tmp_path / 'data')
    catalog = load_recipe_catalog(Path('config/forever-tailoring.toml'))
    catalog['catalog_id'] = 'tailoring'
    # Preserve real catalog quantities, restrict to a small chain for offline display.
    chosen = [r for r in catalog['recipes_by_id'].values() if r['output_item_id'] in (2996, 2576)]
    catalog['recipes_by_id'] = {r['recipe_id']: r for r in chosen}
    catalog['recipe_for_output'] = {r['output_item_id']: r['recipe_id'] for r in chosen}
    ids = {2589, 2996, 2576, *(i['item_id'] for r in chosen for i in r['inputs'])}
    catalog['items_by_id'] = {i: catalog['items_by_id'][i] for i in ids}
    records = []
    for index in range(count):
        rows = [listing(2589, 10 + index, (10 + index) * (10 + index), 'Linen Cloth'),
                listing(2996, 2, 200, 'Bolt of Linen Cloth'), listing(2576, 1, 2000, 'White Linen Shirt'),
                listing(99999, 1, 0, 'Unpriced curiosity'), listing(2324, 1, 30, 'Bleach')]
        records.append(scan(f'scan-{index}', FINISHED - (count - index - 1) * 3600, rows))
    import_scans(config, write_scans(tmp_path / 'scans.lua', *records), now=NOW)
    return config, catalog


def test_search_chains_quantities_prices_and_unknown_team(tmp_path):
    config, catalog = explorer_fixture(tmp_path)
    result = me.load_explorer(config, [catalog], NOW)
    assert [r['item_id'] for r in me.search_items(result, 'linen cloth')] == [2996, 2589]
    assert [r['item_id'] for r in me.search_items(result, '2589')] == [2589]
    bolt = me.item_page(result, 2996)
    assert bolt['made_from'] and bolt['used_in'] and bolt['demand']
    assert bolt['made_from'][0]['materials'][0]['quantity'] == 2
    assert bolt['made_from'][0]['materials'][0]['unit_cost_copper'] == 11
    assert bolt['made_from'][0]['value']['profit_copper'] is None
    shirt = me.item_page(result, 2576)
    material = next(m for m in shirt['made_from'][0]['materials'] if m['item_id'] == 2996)
    assert material['method'] == 'craft'
    assert [m['item_id'] for m in shirt['made_from'][0]['materials']] == [2996, 2589, 2320, 2324]
    assert any(m['item_id'] == 2589 and m['depth'] == 1 for m in shirt['made_from'][0]['materials'])
    assert shirt['made_from'][0]['value']['profit_copper'] is not None
    assert bolt['used_in'][0]['characters'] == []  # UI labels absent evidence Unknown.
    unknown = me.item_page(result, 99999)
    assert not unknown['in_chain'] and not unknown['made_from']
    assert unknown['observed'][0]['min_buyout'] is None
    assert me.item_page(result, 123456)['observed'] == []
    assert not result['freshness']['stale']
    assert me.load_explorer(config, [catalog], NOW + timedelta(days=2))['freshness']['stale']


def test_movement_two_one_tsm_and_no_compatible_catalogs(tmp_path):
    config, catalog = explorer_fixture(tmp_path)
    result = me.load_explorer(config, [catalog], NOW)
    moved = result['movement']
    assert len(moved['rows']) == 1
    assert moved['rows'][0]['item_id'] == 2589
    assert moved['rows'][0]['change']['min_buyout'] == 1
    assert moved['rows'][0]['change']['units'] == 1
    assert moved['comparison']['gap'].total_seconds() == 3600
    incompatible = deepcopy(catalog)
    incompatible['rules_version'] = 'other'
    empty = me.load_explorer(config, [incompatible], NOW)
    assert empty['catalogs'] == [] and empty['movement']['rows'] == []
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb'), read_only=True) as db:
        assert me.scan_movement(db, config | {'provider': 'tsm'}, [catalog], NOW)['note'].startswith('TSM')
    # Isolate a one-scan source from the two-scan evidence.
    single_dir = tmp_path / 'single'
    single_dir.mkdir()
    one, catalog = explorer_fixture(single_dir, count=1)
    assert me.load_explorer(one, [catalog], NOW)['movement']['note'] == 'No earlier scan'


@pytest.mark.parametrize('key', ['source_id', *MARKET_KEYS])
def test_scope_never_uses_another_observer_or_market(tmp_path, key):
    config, catalog = explorer_fixture(tmp_path)
    wrong = config | {key: 'another'}
    result = me.load_explorer(wrong, [catalog], NOW)
    assert result['snapshot'] is None and result['items'] == []
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb'), read_only=True) as db:
        assert me.scan_movement(db, wrong, [catalog], NOW)['note'] == 'No earlier scan'


def test_board_reasons_missing_routes_character_status_and_duplicate_catalogs(tmp_path):
    config, catalog = explorer_fixture(tmp_path)
    from brownstone.today_loading import load_today
    from brownstone.today_settings import TodaySettings
    _, arguments = load_today(config, [catalog], TodaySettings(), {}, NOW)
    arguments['observations'] = {}
    data = {('Maker', 'Realm', 'Alliance'): {'recipes': {}, 'seen': {}, 'bags': {}}}
    rows = me.recipe_rows([catalog], arguments, data)
    shirt = next(r for r in rows if r['recipe']['output_item_id'] == 2576)
    assert shirt['value']['action'] == 'missing prices'
    assert shirt['value']['profit_copper'] is None
    assert any(m['unit_cost_copper'] is None for m in shirt['materials'])
    assert shirt['characters'][0]['craft_status'] == 'Unknown'
    assert len(shirt['characters'][0]['character']) == 3
    other = deepcopy(catalog)
    other['catalog_id'] = 'other-tailoring'
    assert len(me.recipe_rows([catalog, other], arguments, {})) == len(rows) * 2
    cyclic = deepcopy(catalog)
    cyclic['recipes_by_id'][2963]['inputs'] = [{'item_id': 2996, 'quantity': 1}]
    broken = me.recipe_rows([cyclic], arguments, {})
    assert all('unsupported recipe' in row['value']['action'] for row in broken)


def test_movement_limit_order_identity_dedup_and_missing_changes(monkeypatch):
    from datetime import UTC, datetime
    config = {'provider': 'addon', 'max_age_hours': 24}
    scans = [{'scan_id': 'later'}, {'scan_id': 'earlier'}]
    monkeypatch.setattr(me.scan_changes, 'eligible_scans', lambda db, cfg: scans)
    rows = []
    for item_id in range(1, 15):
        earlier = {'min_buyout': 10, 'units': 5}
        later = {'min_buyout': 10 + item_id, 'units': 6}
        rows.append({'item_id': item_id, 'earlier': earlier, 'later': later,
                     'change': {'min_buyout': item_id, 'units': 1}, 'variant_state': 'base', 'variant_id': None})
    duplicate = deepcopy(rows[-1])
    duplicate.update(variant_state='unresolved', change={'min_buyout': 14, 'units': 20})
    missing = {'item_id': 15, 'earlier': {'min_buyout': None, 'units': 2},
               'later': {'min_buyout': 10, 'units': 2}, 'change': {'min_buyout': None, 'units': 0},
               'variant_state': 'base', 'variant_id': None}
    rows.extend([duplicate, missing])
    comparison = {'items': rows, 'later': {'finished_at': datetime(2026, 1, 1, tzinfo=UTC)}}
    def compare(db, cfg, a, b, ids):
        assert (a, b) == ('later', 'earlier') and ids == list(range(1, 16))
        return comparison
    monkeypatch.setattr(me.scan_changes, 'compare_scans', compare)
    catalog = {'items_by_id': dict.fromkeys(range(1, 16))}
    moved = me.scan_movement(None, config, [catalog], NOW)
    assert len(moved['rows']) == 10
    assert [r['item_id'] for r in moved['rows']] == list(range(14, 4, -1))
    assert moved['rows'][0]['variant_state'] == 'unresolved'
    comparison['items'] = [missing]
    assert me.scan_movement(None, config, [catalog], NOW)['rows'] == [missing]


def test_captured_quality_uses_exact_identity_and_scope(tmp_path):
    config = addon_source(tmp_path / 'data')
    from test_scan_v3 import rich
    import_scans(config, write_scans(tmp_path / 'quality.lua', rich()), now=NOW)
    result = me.load_explorer(config, [], NOW)
    assert next(r for r in result['items'] if r['item_id'] == 2589)['quality'] == 1
    assert {r['quality'] for r in result['items'] if r['item_id'] == 6538} == {2, None}
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb'), read_only=True) as db:
        assert me.captured_qualities(db, config | {'source_id': 'other'}, result['snapshot']['snapshot_id']) == {}
        assert me.captured_qualities(db, config | {'environment': 'other'}, result['snapshot']['snapshot_id']) == {}


def test_beta_reference_quotes_missing_prices_fade_and_plan_independence(tmp_path):
    from brownstone.today import build_today
    from brownstone.today_loading import load_today
    from brownstone.today_settings import TodaySettings
    config, catalog = explorer_fixture(tmp_path)
    beta = addon_source(config['data_dir'], source_id='beta', environment='beta', enabled=False, label='Frozen beta')
    records = [scan(f'beta-{i}', FINISHED - (15 - i) * 86400,
                    [listing(2589, 1, 30), listing(2996, 1, 0), listing(99999, 1, 20)]) for i in range(4)]
    import_scans(beta, write_scans(tmp_path / 'beta.lua', *records), now=NOW)
    baseline = me.load_explorer(config, [catalog], NOW)
    assert baseline['market']['reference'] is None
    assert all(r['beta_typical_copper'] is None and r['beta_ratio'] is None for r in baseline['market']['rows'])
    paired = config | {'reference_source': 'beta'}
    result = me.load_explorer(paired, [catalog], NOW, reference=beta)
    assert result['reference'] == {'source_id': 'beta', 'label': 'Frozen beta',
                                   'market_id': beta['market_id'],
                                   'newest_scan': NOW - timedelta(days=12, minutes=10)}
    rows = {r['item_id']: r for r in result['market']['rows']}
    assert rows[2589]['beta_typical_copper'] == 30
    assert rows[2589]['beta_ratio'] == {'numerator': 11, 'denominator': 30}
    assert result['beta_prices'][(2589, None, None)] == {'typical_copper': 30, 'days': 3, 'scans': 3}
    for item_id in (2996, 99999, 2576):  # Unpriced beta, unpriced live, absent beta.
        assert rows[item_id]['beta_typical_copper'] is None and rows[item_id]['beta_ratio'] is None
    assert result['recipes'] == baseline['recipes']  # Board/crafting values and reasons.
    assert result['observations'] == baseline['observations']
    assert result['floods'] == baseline['floods']
    plans = []
    for source in (config, paired):
        _, args = load_today(source, [catalog], TodaySettings(), {}, NOW, flood=True)
        plans.append(build_today(**args))
    assert plans[0] == plans[1]
    assert not any(r['beta_faded'] for r in result['market']['rows'])
    earlier = [scan(f'live-day-{i}', FINISHED - (i + 1) * 86400, [listing(2589, 1, 15), listing(99999, 1, 25)])
               for i in range(3)]
    import_scans(config, write_scans(tmp_path / 'earlier.lua', *earlier), now=NOW)
    faded = me.load_explorer(paired, [catalog], NOW, reference=beta)
    unpaired = me.load_explorer(config, [catalog], NOW)
    rows = {r['item_id']: r for r in faded['market']['rows']}
    assert [(r['typical_copper'], r['gap_copper']) for r in faded['market']['rows']] == [
        (r['typical_copper'], r['gap_copper']) for r in unpaired['market']['rows']]  # Live values never move.
    linen = rows[2589]
    assert linen['typical_copper'] == 15 and linen['beta_faded'] and rows[99999]['beta_faded']
    assert linen['beta_typical_copper'] is None and linen['beta_ratio'] is None
    assert faded['beta_prices'][(2589, None, None)]['typical_copper'] == 30
    missing = me.load_explorer(config | {'source_id': 'empty'}, [catalog], NOW, reference=beta)
    assert missing['market']['reference']['source_id'] == 'beta' and missing['market']['rows'] == []


def test_beta_reference_exact_identity_and_scope(tmp_path):
    from test_scan_v3 import BASE, rich

    from brownstone import beta_reference
    config = addon_source(tmp_path / 'data')
    beta = addon_source(config['data_dir'], source_id='beta', environment='beta')
    records = [rich(f'beta-{i}', FINISHED - (15 - i) * 86400) for i in range(4)]
    import_scans(beta, write_scans(tmp_path / 'beta.lua', *records), now=NOW)
    live = rich()
    live['links'][1] = BASE.replace('2589', '6538')  # Base robe, no matching beta base quote.
    live['links'][2] = BASE.replace('2589::::::::', '2589:10:::::::')  # Variant cloth cannot borrow base.
    import_scans(config, write_scans(tmp_path / 'live.lua', live), now=NOW)
    result = me.load_explorer(config, [], NOW, reference=beta)
    rows = result['market']['rows']
    monkey = next(r for r in rows if r['item_id'] == 6538 and r['variant_state'] == 'variant')
    assert monkey['beta_typical_copper'] == 500
    assert all(r['beta_typical_copper'] is None for r in rows if r is not monkey and r['variant_state'] != 'unresolved')
    assert (6538, None, 'base') not in result['beta_prices']
    assert not any(key[0] == 2589 for key in result['beta_prices'])
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb'), read_only=True) as db:
        keys = {me.identity(r) for r in result['items']}
        for field in ('source_id', *MARKET_KEYS):
            block, prices = beta_reference.read(db, beta | {field: 'foreign'}, keys)
            assert block['newest_scan'] is None and prices == {}
