"""Offline STORY-090 projection contracts: no identity aggregation or client ordering."""
from copy import deepcopy

import pytest

from brownstone import market_presentation as mp


def row(item=1, state='base', variant=None, price=90, typical=300, units=20, roles=('materials',)):
    return {'item_id': item, 'name': f'Item {item}', 'variant_state': state, 'variant_id': variant,
            'quality': 2, 'price_copper': price, 'typical_copper': typical,
            'gap_copper': price - typical if price and typical else None,
            'gap_percent': (price - typical) * 100 / typical if price and typical else None,
            'units': units, 'listings': 10, 'roles': list(roles), 'sparkline': [100, None, price],
            'signal': {'crowding': 'steady', 'overshoot': {'label': 'cheap'}}}


def test_grouping_preserves_every_identity_price_units_history_and_base_parent():
    rows = [row(state='unresolved', price=700, units=7), row(price=90, units=20),
            row(state='variant', variant='suffix', price=800, units=3), row(2, state=None),
            row(3, state='unresolved', price=None)]
    rows[0]['signal']['crowding'] = 'thin'
    saved = deepcopy(rows)
    groups = mp.grouped_rows(rows)
    assert len(groups) == 3
    first = next(r for r in groups if r['item_id'] == 1)
    assert first['variant_state'] == 'base' and first['units'] == 20 and first['price_copper'] == 90
    assert [(r['price_copper'], r['units']) for r in first['variants']] == [(700, 7), (800, 3)]
    flattened = [r for parent in groups for r in [parent, *parent['variants']]]
    assert len(flattened) == len(rows)
    for original in saved:
        actual = next(r for r in flattened if (r['item_id'], r['variant_state'], r['variant_id']) ==
                      (original['item_id'], original['variant_state'], original['variant_id']))
        assert {k: actual[k] for k in original} == original
    assert rows == saved  # Cached explorer data is immutable across queries.


def test_default_absolute_percentage_sort_unknown_last_and_deterministic_ties():
    rows = [row(3, price=None), row(4, price=0), row(5, price=600), row(1, price=600),
            row(2, price=30), row(6, typical=None)]
    assert [r['item_id'] for r in mp.grouped_rows(rows)] == [1, 5, 2, 3, 4, 6]
    assert [r['item_id'] for r in mp.grouped_rows(rows, sort='gap_percent', descending=False)] == [2, 1, 5, 3, 4, 6]
    assert mp.sort_rows(rows, sort='not-a-column') == mp.sort_rows(rows)
    assert mp.grouped_rows([row(state='variant', variant='z'), row(state=None)])[0]['variant_state'] is None


@pytest.mark.parametrize(('role', 'expected'), [('all', [1, 2, 3]), ('materials', [1, 3]),
    ('crafts', [2, 3]), ('intermediates', [3]), ('signal', [1])])
def test_server_filters_catalog_roles_and_signals(role, expected):
    rows = [row(1), row(2, roles=('crafts',)), row(3, roles=('materials', 'crafts', 'intermediates')),
            row(4, roles=())]
    rows[1]['signal'] = None
    rows[2]['signal']['overshoot']['label'] = 'usual'
    assert [r['item_id'] for r in mp.grouped_rows(rows, role)] == expected
    assert mp.grouped_rows(rows, role, '4')[0]['roles'] == []
    assert mp.grouped_rows(rows, role, 'ITEM 4')[0]['item_id'] == 4
    assert mp.grouped_rows(rows, role, 'absent') == []


def test_cards_three_plus_more_keep_ui11_order_exact_identity_and_missing_price():
    rows = [row(i) for i in range(1, 8)]
    rows[4]['roles'] = []
    signals = [{'item_id': i, 'item_name': f'Item {i}', 'variant_state': 'base', 'variant_id': None}
               for i in [4, 1, 3, 5, 2]]
    missing = signals[0] | {'variant_state': 'unresolved', 'early': {'units': 14}}
    page = {'rows': rows, 'pulse': {'cheap': signals, 'high': signals[::-1], 'early': [missing]}}
    projected = mp.project(page)
    for key in ('cheap', 'high'):
        card = projected['cards'][key]
        assert len(card['preview']) == 3 and len(card['more']) == 2
        assert [r['item_id'] for r in card['preview'] + card['more']] == [r['item_id'] for r in page['pulse'][key]]
    assert projected['cards']['cheap']['more'][0]['outside_chains']
    early = projected['cards']['early']['preview'][0]
    assert early['price_copper'] is None and early['typical_copper'] is None and early['sparkline'] == []
    assert early['removed_units'] == 14 and not early['outside_chains']
    assert (projected['item_count'], projected['identity_count'], projected['listed_chain_count']) == (7, 7, 6)
    assert mp.sort_rows(rows, 'signal')


def test_signal_filter_keeps_parent_when_only_a_separate_identity_has_signal():
    base, variant = row(), row(state='variant', variant='suffix')
    base['signal'] = None
    groups = mp.grouped_rows([base, variant], role='signal')
    assert len(groups) == 1 and groups[0]['signal'] is None
    assert groups[0]['variants'] == [variant]


def test_removed_chain_item_absent_now_is_still_in_our_chains():
    signal = {'item_id': 9, 'item_name': 'Gone', 'variant_state': 'base', 'variant_id': None,
              'early': {'units': 10}}
    card = mp.cards({'rows': [], 'chain_ids': [9], 'pulse': {'early': [signal]}})['early']['preview'][0]
    assert not card['outside_chains']
    assert card['price_copper'] is None


def test_levels_use_catalog_bands_profession_ids_and_team_window_without_changing_grid_evidence():
    from test_progression import evidence, progression_catalog

    catalog = progression_catalog()
    catalog['profession'] = 'tailoring'
    recipes = list(catalog['recipes_by_id'].values())
    recipes[0]['skillup_colors'] = [1, 20, 25, 40]
    for recipe in recipes[1:]:
        recipe['skillup_colors'] = [50, 60, 75, 100]
    character = evidence(catalog)
    character['recipes']['Arbitrary title']['known_recipes']['skill_id'] = 197
    result = {'catalogs': [catalog], 'characters': {'owner': character}}
    low = mp.level_items(result, 5)
    high = mp.level_items(result, 50)
    assert recipes[0]['output_item_id'] in low
    assert recipes[1]['output_item_id'] not in low
    assert recipes[1]['output_item_id'] in high
    assert {i['item_id'] for i in recipes[0]['inputs']} <= low
    page = {'rows': [row(i) for i in high], 'pulse': {}}
    saved = deepcopy(page)
    filtered = mp.project(page, role='levels', level_ids=low)
    assert {r['item_id'] for r in filtered['rows']} == low
    assert len(mp.project(page, role='all')['rows']) == len(high)
    item = recipes[1]['output_item_id']
    assert mp.project(page, role='levels', q=str(item), level_ids=low)['rows'][0]['item_id'] == item
    assert page == saved
    # Names do not map professions, and unknown ranks/bands never imply rank one.
    surface = character['recipes']['Arbitrary title']['known_recipes']
    surface['skill_id'] = 171
    assert mp.level_items(result, 50) == set()
    surface['skill_id'], surface['rank'] = 197, None
    assert mp.level_items(result, 50) == set()
    assert mp.level_items(result | {'characters': {}}, 50) == set()
    surface['rank'] = 8
    for recipe in recipes:
        recipe['required_skill'] = None
        recipe.pop('skillup_colors')
    assert mp.level_items(result, 50) == set()
