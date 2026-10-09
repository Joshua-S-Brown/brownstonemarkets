"""Offline confidence boundaries and reserved-plan invariance."""
from datetime import timedelta

import pytest
from test_today import NOW, SNAPSHOT, catalog, output_catalog, plan

from brownstone.today import Ladder
from brownstone.today_confidence import confidence, route_notes
from brownstone.today_settings import TodaySettings


def label(*, age=0, stale=False, listings=5, thin=False, lowest=200, bought=2, units=100, notes=(), depth=True):
    row = {"purchases": [{"item_id": 1, "method": "buy", "purchased_units": bought, "end": 1}],
           "evidence_notes": notes}
    sell = {"thin": thin, "lowest_copper": lowest, "listings": listings}
    return confidence(row, sell, {"stale": stale, "age_hours": age}, 24,
                      {1: {"units": units}}, {1: Ladder([(bought, bought, 1)])} if depth else None)


@pytest.mark.parametrize('arguments,level,reasons', [
    ({}, 'High', []),
    ({'stale': True}, 'Low', ['stale']),
    ({'thin': True}, 'Low', ['thin']),
    ({'lowest': None}, 'Low', ['no competing listing']),
    ({'lowest': 0}, 'Low', ['no competing listing']),
    ({'age': 12}, 'High', []),
    ({'age': 12.001}, 'Medium', ['older scan']),
    ({'listings': 4}, 'Medium', ['few listings']),
    ({'listings': 5}, 'High', []),
    ({'bought': 40}, 'High', []),
    ({'bought': 41}, 'Medium', ['material share >40%']),
    ({'bought': 75}, 'Medium', ['material share >40%']),
    ({'bought': 76}, 'Low', ['material share >75%']),
    ({'depth': False}, 'Medium', ['depth not available for this source']),
    ({'notes': ['Thread: vendor price verified']}, 'Medium', ['unconfirmed vendor price']),
    ({'notes': ['Coarse Thread: vendor verified']}, 'Medium', ['unconfirmed vendor price']),
    ({'notes': ['Recipe: output quantity verified']}, 'Medium', ['unconfirmed yield']),
])
def test_each_reason_and_exact_boundaries(arguments, level, reasons):
    assert label(**arguments) == {'confidence': level, 'confidence_reasons': reasons}


def test_worst_reason_and_stale_tsm():
    assert label(thin=True, age=13, notes=['R: output quantity verified'])['confidence'] == 'Low'
    assert label(stale=True, depth=False) == {
        'confidence': 'Low', 'confidence_reasons': ['stale', 'depth not available for this source']}


@pytest.mark.parametrize('upstream', [False, True])
def test_freshness_basis_limit_future_and_tsm(upstream):
    snap = {**SNAPSHOT, 'collected_at': (NOW - timedelta(hours=13)).isoformat()}
    if upstream:
        snap['updated_at'] = NOW.isoformat()
    row = plan(snapshot=snap, listings=None, metrics=None)['craft'][0]
    assert row['time_basis'] == ('upstream scan' if upstream else 'collection')
    assert ('older scan' in row['confidence_reasons']) is not upstream
    assert row['confidence'] == 'Medium'
    for hours, level in [(24, 'Medium'), (24.001, 'Low'), (-1, 'Low')]:
        row = plan(snapshot={**SNAPSHOT, 'updated_at': (NOW - timedelta(hours=hours)).isoformat()},
                   listings=None, metrics=None)['craft'][0]
        assert row['confidence'] == level
        assert row['actionable'] is (level != 'Low')


def test_material_share_includes_prior_reservations_and_no_buyout_units():
    metrics = {1: {'units': 10}, **{i: {'listings': 5, 'units': 10, 'largest_stack_units': 2,
                                     'min_buyout': 200} for i in (3, 4)}}
    result = plan(catalogs=[catalog(), output_catalog(4, 'second')],
                  observations={1: {'min_buyout': 10}, 3: {'min_buyout': 200}, 4: {'min_buyout': 200}},
                  settings=TodaySettings(10000, 1, 'fixed', max_crafts=1),
                  listings={1: [(4, 40, 10), (4, 80, 20)]}, metrics=metrics)
    assert [r['confidence'] for r in result['craft']] == ['High', 'Low']
    # Eight priced units plus two no-buyout units: the first complete stack is exactly 40%.
    assert result['craft'][0]['confidence_reasons'] == []
    assert result['craft'][1]['confidence_reasons'] == ['material share >75%']


def test_vendor_and_unbought_materials_no_share():
    row = {'purchases': [{'item_id': 2, 'method': 'vendor', 'purchased_units': 10000},
                         {'item_id': 1, 'method': 'buy', 'purchased_units': 0}], 'evidence_notes': []}
    result = confidence(row, {'thin': False, 'lowest_copper': 10, 'listings': 5},
                        {'stale': False, 'age_hours': 0}, 24, {}, {})
    assert result['confidence'] == 'High'


@pytest.mark.parametrize('record,marker', [('recipe', 'output_quantity_verified'), ('item', 'vendor_price_verified'),
                                         ('output', 'vendor_verified')])
def test_route_unconfirmed_recipe_vendor_and_output(record, marker):
    c = catalog()
    target = c['recipes_by_id'][30] if record == 'recipe' else c['items_by_id'][2 if record == 'item' else 3]
    target[marker] = False
    row = plan(catalogs=[c])['craft'][0]
    reason = "yield" if record == "recipe" else "vendor price"
    assert f"unconfirmed {reason}" in row["confidence_reasons"]


def test_route_notes_include_intermediates_but_not_unused_alternatives():
    c = catalog()
    c['recipes_by_id'][31] = {'recipe_id': 31, 'output_quantity_verified': False}
    c['recipes_by_id'][32] = {'recipe_id': 32, 'unused_verified': False}
    c['items_by_id'][4] = {'name': 'Intermediate', 'vendor_price_verified': False}
    row = {'output_item_id': 3, 'shopping_list': {1: 2, 2: 1},
           'intermediate_steps': [{'recipe_id': 31, 'item_id': 4}]}
    notes = route_notes(c, c['recipes_by_id'][30], row)
    assert any('output quantity verified' in n for n in notes)
    assert any(n == 'Intermediate: vendor price verified' for n in notes)
    assert not any('unused' in n for n in notes)


def test_labels_never_change_plan_and_carry_to_sell_queue(monkeypatch):
    import brownstone.today as today
    second = output_catalog(4, 'second')
    second['items_by_id'][4]['name'] = 'Second output'
    args = dict(catalogs=[catalog(), second],
                observations={1: {'min_buyout': 10}, 3: {'min_buyout': 200}, 4: {'min_buyout': 180}},
                settings=TodaySettings(1000, 1, 'fixed', max_crafts=1),
                listings={1: [(3, 30, 10), (4, 80, 20)]})
    actual = plan(**args)
    assert len(actual['craft']) == 2
    monkeypatch.setattr(today, 'confidence', lambda *args: {})
    without = plan(**args)
    def strip(value):
        if isinstance(value, dict):
            return {k: strip(v) for k, v in value.items() if k not in ('confidence', 'confidence_reasons')}
        if isinstance(value, list):
            return [strip(v) for v in value]
        return value
    assert strip(actual) == without
    for craft, sell in zip(actual['craft'], actual['sell'], strict=True):
        assert sell['confidence'] == craft['confidence']
        assert sell['confidence_reasons'] == craft['confidence_reasons']
    for line in actual['queue']['lines']:
        if line['stage'] in ('craft', 'post'):
            craft = next(r for r in actual['craft'] if r['output_name'] == line['name'])
            assert line['confidence'] == craft['confidence']
            assert line['confidence_reasons'] == craft['confidence_reasons']


@pytest.mark.parametrize('listings,units,largest,thin', [(2, 10, 2, True), (3, 10, 2, False),
                                                      (5, 10, 4, False), (5, 10, 5, True)])
def test_existing_thin_boundaries(listings, units, largest, thin):
    result = plan(metrics={1: {'units': 100},
                           3: {'min_buyout': 200, 'listings': listings,
                               'units': units, 'largest_stack_units': largest}},
                  listings={1: [(2, 20, 10)]}, settings=TodaySettings(10000, 1, 'fixed', max_crafts=1))
    assert result['sell'][0]['thin'] is thin
    assert ('thin' in result['craft'][0]['confidence_reasons']) is thin


def test_intermediate_markers_and_all_queue_lines():
    from test_today import chain_catalog
    c = chain_catalog()
    c['recipes_by_id'][60]['output_quantity_verified'] = False
    result = plan(catalogs=[c], settings=TodaySettings(10000, 1, 'fixed', max_crafts=2),
                  listings={1: [(30, 300, 10)]})
    row = next(r for r in result['craft'] if r['output_item_id'] == 3)
    assert 'unconfirmed yield' in row['confidence_reasons']
    assert [r['recipe_id'] for r in result['queue']['lines'] if r['stage'] == 'craft'] == [60, 50, 30]
    for line in result['queue']['lines']:
        assert line['confidence'] == row['confidence']
        assert line['confidence_reasons'] == row['confidence_reasons']


def test_merged_buy_queue_worst_label_and_missing_material_depth():
    from brownstone.today_confidence import purchase_confidence
    purchase = {'item_id': 1, 'method': 'buy', 'purchased_units': 1, 'end': 1}
    rows = [{'purchases': [purchase], 'confidence': level, 'confidence_reasons': [reason]}
            for level, reason in [('Medium', 'older scan'), ('Low', 'thin')]]
    assert purchase_confidence(rows, purchase) == {
        'confidence': 'Low', 'confidence_reasons': ['older scan', 'thin']}
    assert purchase_confidence([], purchase) == {}
    row = {'purchases': [purchase], 'evidence_notes': []}
    assert confidence(row, {'thin': False, 'lowest_copper': 10, 'listings': 5},
                      {'stale': False, 'age_hours': 0}, 24, {}, {}) == {
                          'confidence': 'Medium', 'confidence_reasons': ['depth not available for this source']}
