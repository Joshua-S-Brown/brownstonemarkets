"""STORY-067: offline sell-only caps and scoped shown-output warnings."""
from copy import deepcopy
from unittest.mock import Mock

import pytest
from test_flood_signals import connection, fixture
from test_scans import FINISHED, NOW, listing, scan
from test_today import catalog, output_catalog, plan

from brownstone import flood_signals, removed_listings
from brownstone.action_board import rank_catalogs
from brownstone.today import TODAY_VERSION, apply_removals, build_today
from brownstone.today_loading import load_today, load_today_removals
from brownstone.today_settings import TodaySettings


def signal(item_id=3, label='high', crowding='contested', typical=100):
    return {'item_id': item_id, 'variant_id': None, 'variant_state': 'base',
            'min_buyout': 200, 'listings': 10, 'units': 10, 'largest_stack_units': 1,
            'crowding': crowding, 'churn': {'changed': 3, 'pairs': 5},
            'overshoot': {'label': label, 'typical_copper': typical, 'scans': 5, 'days': 3,
                          'ratio': {'numerator': 200, 'denominator': typical}}}


def test_high_sell_cap_reranks_before_sizing_and_does_not_change_board():
    observations = {1: {'min_buyout': 10, 'market_value': 20}, 3: {'min_buyout': 200}, 4: {'min_buyout': 150}}
    catalogs = [catalog(), output_catalog(4, 'second')]
    args = dict(catalogs=catalogs, observations=observations,
                settings=TodaySettings(1000, 1, 'fixed', max_crafts=1), listings=None)
    original = plan(**args)
    result = plan(**args, flood_evidence={'rows': [signal()]})
    assert [c['output_item_id'] for c in original['craft']] == [3, 4]
    assert [c['output_item_id'] for c in result['craft']] == [4, 3]
    assert result['craft'][1]['sale_price_copper'] == 100
    assert result['craft'][1]['net_revenue_copper'] == 95
    assert result['craft'][1]['batch_profit_copper'] == 45
    assert original['craft'][0]['sale_price_copper'] == 200
    from test_today import MARKET, SNAPSHOT
    from test_today import NOW as TODAY_NOW
    assert rank_catalogs(catalogs, observations, MARKET, SNAPSHOT, now=TODAY_NOW)['rows'][0][
        'sale_price_copper'] == 200
    assert observations[3]['min_buyout'] == 200


def test_same_output_as_material_keeps_buy_price_and_cautious_lower_price():
    second = output_catalog(4, 'second')
    second['recipes_by_id'][30]['inputs'] = [{'item_id': 3, 'quantity': 2}]
    second['items_by_id'][3] = deepcopy(catalog()['items_by_id'][3])
    result = plan(catalogs=[catalog(), second], listings=None,
                  observations={1: {'min_buyout': 10}, 3: {'min_buyout': 200, 'market_value': 220},
                                4: {'min_buyout': 1000}},
                  flood_evidence={'rows': [signal()]})
    consumer = next(c for c in result['craft'] if c['output_item_id'] == 4)
    assert consumer['shopping_choices'][0]['unit_cost_copper'] == 220
    assert consumer['craft_cost_copper'] == 440
    assert next(c for c in result['craft'] if c['output_item_id'] == 3)['sale_price_copper'] == 100
    cheaper = plan(observations={1: {'min_buyout': 10}, 3: {'min_buyout': 200, 'market_value': 80}},
                   flood_evidence={'rows': [signal()]})
    assert cheaper['craft'][0]['sale_price_copper'] == 80


@pytest.mark.parametrize('label', ['cheap', 'typical', 'too few days', 'no buyout'])
def test_nonhigh_outputs_unchanged(label):
    result = plan(flood_evidence={'rows': [signal(label=label)]})
    assert result['craft'][0]['sale_price_copper'] == 200
    assert result['sell'][0]['undercut_copper'] == 199
    assert result['sell'][0]['price_note'] is None


@pytest.mark.parametrize('stack,typical,expected', [(1, 155, 100), (20, 155, 155), (None, 155, 155),
                                                  (1, 50, None), (1, 500, 100)])
def test_post_price_lower_of_undercut_and_typical_rounds_down(stack, typical, expected):
    result = plan(flood_evidence={'rows': [signal(typical=typical)]},
                  metrics={3: {'min_buyout': 200, 'listings': 10, 'units': 10,
                               'largest_stack_units': 1, 'max_stack_size': stack}})
    sell = result['sell'][0]
    assert sell['undercut_copper'] == expected
    assert sell['price_note'] == 'priced at the typical earlier price, not the current lowest'
    post = next(line for line in result['queue']['lines'] if line['stage'] == 'post')
    assert post['unit_copper'] == expected and post['signal'] == sell['signal']
    assert post['price_note'] == sell['price_note']


@pytest.mark.parametrize('crowding', ['contested', 'thin', 'steady'])
def test_actionable_signals_propagate_and_contested_is_medium(crowding):
    result = plan(flood_evidence={'rows': [signal(label='typical', crowding=crowding)]})
    craft, sell = result['craft'][0], result['sell'][0]
    assert craft['signal']['crowding'] == sell['signal']['crowding'] == crowding
    assert ('contested' in craft['confidence_reasons']) == (crowding == 'contested')
    assert next(r for r in result['queue']['lines'] if r['stage'] == 'post')['signal'] == sell['signal']
    assert 'pricier than usual' not in craft['confidence_reasons']


@pytest.mark.parametrize('state,variant', [('variant', 'suffix:-1'), ('unresolved', None)])
def test_variant_signals_never_cap_base_output(state, variant):
    foreign = signal() | {'variant_state': state, 'variant_id': variant}
    result = plan(flood_evidence={'rows': [foreign]})
    assert result['craft'][0]['sale_price_copper'] == 200
    assert result['craft'][0]['signal'] is None


@pytest.mark.parametrize('pairs,units,low', [(3, 0, True), (2, 0, False), (3, 1, False)])
def test_no_early_removals_threshold_confidence_and_queue(pairs, units, low):
    result = plan()
    original_cost = result['shopping_total_copper']
    apply_removals(result, {3: {'pairs': pairs, 'units': units}})
    craft = result['craft'][0]
    assert any(r.startswith('no early removals') for r in craft['confidence_reasons']) == low
    if low:
        assert craft['confidence'] == result['sell'][0]['confidence'] == 'Low'
        assert all(r['confidence'] == 'Low' for r in result['queue']['lines'])
    assert result['shopping_total_copper'] == original_cost


def loaded_fixture(tmp_path, pairs=3, removed=False):
    records = [scan(f's{i}', FINISHED - (pairs - i) * 3600,
                    [listing(1, 1, 100)] * (2 if removed and i == 0 else 1)) for i in range(pairs + 1)]
    config = fixture(tmp_path, records)
    with connection(config) as db:
        db.execute('UPDATE scan_listings SET time_left=4')
    return config


@pytest.mark.parametrize('pairs,removed,expected', [(3, False, (3, 0)), (2, False, (2, 0)), (3, True, (3, 1))])
def test_loaded_removals_same_pairs_only_shown_outputs(tmp_path, monkeypatch, pairs, removed, expected):
    config = loaded_fixture(tmp_path, pairs, removed)
    with connection(config) as db:
        evidence = flood_signals.signals(db, config, [1], NOW)
    shown = {'craft': [{'output_item_id': 1, 'signal': evidence['rows'][0]}]}
    compare = Mock(wraps=removed_listings._compare)
    listed = Mock(wraps=removed_listings.scan_pairs)
    monkeypatch.setattr(removed_listings, '_compare', compare)
    monkeypatch.setattr(removed_listings, 'scan_pairs', listed)
    totals = load_today_removals(config, shown)
    assert (totals[1]['pairs'], totals[1]['units']) == expected
    assert compare.call_count == pairs and listed.call_count == 1
    assert all(call.args[3] == [1] for call in compare.call_args_list)
    with connection(config) as db:
        # The same pairs as UI-11's churn.
        assert [r['earlier']['scan_id'] for r in removed_listings.recent_comparisons(db, config, [1])] == \
            [p['earlier']['scan_id'] for p in removed_listings.qualifying_pairs(db, config)]
    assert load_today_removals(config, {'craft': []}) == {}
    assert load_today_removals(config | {'provider': 'tsm'}, shown) == {}


def test_removal_variants_not_pooled_and_incompatible_legacy_not_counted(tmp_path):
    config = loaded_fixture(tmp_path, removed=True)
    with connection(config) as db:
        db.execute("UPDATE scan_listings SET variant_state='base'")
        db.execute("UPDATE scan_metrics SET variant_state='base'")
        db.execute("UPDATE scan_listings SET variant_state='variant', variant_id='suffix:-1' "
                   "WHERE scan_id='s0' AND listing_index=2")
        evidence = flood_signals.signals(db, config, [1], NOW)
    totals = load_today_removals(config, {'craft': [{'output_item_id': 1, 'signal': evidence['rows'][0]}]})
    assert totals[1] == {'pairs': 3, 'units': 0}
    with connection(config) as db:
        db.execute("UPDATE scan_metrics SET variant_state=NULL WHERE scan_id='s0'")
        db.execute("UPDATE scan_metrics SET variant_state='variant', variant_id='suffix:-1' WHERE scan_id='s3'")
        evidence = flood_signals.signals(db, config, [1], NOW)
    # Variant-only newest cannot supply catalog-output evidence.
    result = plan(flood_evidence=evidence)
    assert result['craft'][0]['signal'] is None


def test_one_flood_read_loader_and_pure_build(tmp_path, monkeypatch):
    config = loaded_fixture(tmp_path)
    c = output_catalog(1, 'fixture')
    c.update(game_version=config['game_version'], rules_version=config['rules_version'])
    spy = Mock(wraps=flood_signals.signals)
    monkeypatch.setattr(flood_signals, 'signals', spy)
    _, other = load_today(config, [c], TodaySettings(1000, 1, 'fixed'), {}, NOW)
    # Team, Market and Stock share the loader but never use the signals.
    assert spy.call_count == 0 and other['flood_evidence'] is None
    _, args = load_today(config, [c], TodaySettings(1000, 1, 'fixed'), {}, NOW, flood=True)
    assert spy.call_count == 1 and 1 in spy.call_args.args[2]
    assert args['flood_evidence']['rows'][0]['item_id'] == 1
    monkeypatch.setattr(flood_signals, 'signals', Mock(side_effect=AssertionError('pure build must not read')))
    build_today(**args)
    assert TODAY_VERSION == 12


def test_cap_changes_batch_peak_and_can_remove_unprofitable_craft():
    args = {'listings': {1: [(2, 20, 10), (8, 600, 75)]}}
    assert plan(**args)['craft'][0]['batch_size'] == 5
    capped = plan(**args, flood_evidence={'rows': [signal(typical=100)]})
    assert capped['craft'][0]['batch_size'] == 1
    assert capped['craft'][0]['batch_profit_copper'] == 65
    assert not plan(**args, flood_evidence={'rows': [signal(typical=20)]})['craft']


def test_removal_confidence_retains_complete_queue_shopping_tail():
    c = catalog()
    for i in range(10, 22):
        c['items_by_id'][i] = {**c['items_by_id'][2], 'item_id': i, 'name': f'Vendor {i}'}
    c['recipes_by_id'][30]['inputs'] = [{'item_id': i, 'quantity': 1} for i in range(10, 22)]
    result = plan(catalogs=[c], metrics=None)
    assert len(result['buy']) == 10
    apply_removals(result, {3: {'pairs': 3, 'units': 0}})
    assert len([r for r in result['queue']['lines'] if r['stage'] == 'vendor']) == 12
    assert result['queue']['gold_needed_copper'] == result['shopping_total_copper'] == 600
    assert all(r['confidence'] == 'Low' for r in result['queue']['lines'])
