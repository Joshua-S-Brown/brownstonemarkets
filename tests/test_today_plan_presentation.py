"""STORY-088 presentation evidence without changing selection or Queue identity."""
from copy import deepcopy

from test_today import catalog
from test_today_web import arguments, browser, request

from brownstone import today, today_session
from views import today_web

browser = browser


def test_adjacent_mail_stops_merge_across_stages_but_never_across_another_stop():
    mail = dict(stage='mail', name='Cloth', character='A', to='B', units=2)
    gold = dict(stage='gold mail', name='B', character='A', copper=50)
    lines = [mail, gold, gold | {'character': 'B'}, mail]
    stops = today_session.route_stops({'lines': lines}, [], {})
    assert [len(s['lines']) for s in stops] == [2, 1, 1]
    assert [line['index'] for s in stops for line in s['lines']] == [0, 1, 2, 3]
    assert [line['evidence'] for s in stops for line in s['lines']] == lines


def test_new_and_previously_planned_drop_wording_and_maximum_without_resizing():
    args = arguments()
    _, state, _ = today_session.session_plan(args, {})
    state['choices'] = [dict(catalog_id='fixture', recipe_id=30, batch_size=6)]
    result, changed, _ = today_session.session_plan(args, state)
    assert result['craft'] == [] and changed['choices'][0]['batch_size'] is None
    assert result['dropped_choices'][0]['reason'] == (
        'Requested batch does not fit tonight; at most 5 fit tonight; dropped, not resized.')
    state['feasible_choices'][0]['batch_size'] = 6
    result, _, _ = today_session.session_plan(args, state)
    assert result['dropped_choices'][0]['reason'].startswith('Choice is no longer feasible; at most 5')


def test_fresh_tab_and_empty_saved_state_have_no_reset_note_but_dropped_ticks_or_choices_do(browser):
    first = request(browser, {'window': 25}).json()
    assert first['reset_note'] == ''
    for extra in ({}, {'ticks': {'0': False}}, {'choices': []}):
        assert request(browser, first['state'] | extra | {'context': 'old'}).json()['reset_note'] == ''
    for extra in ({'ticks': {'0': True}}, {'choices': [dict(catalog_id='fixture', recipe_id=30, batch_size=1)]}):
        changed = request(browser, first['state'] | extra | {'context': 'old'}).json()
        assert 'reset' in changed['reset_note'] and not changed['state']['ticks']


def test_unplanned_board_rows_keep_rank_reasons_and_do_not_change_plan():
    c = catalog()
    c['items_by_id'][4] = c['items_by_id'][3] | {'item_id': 4, 'name': 'Another robe'}
    c['recipes_by_id'][40] = c['recipes_by_id'][30] | {'recipe_id': 40, 'output_item_id': 4}
    args = arguments(catalogs=[c], observations={1: {'min_buyout': 10}, 3: {'min_buyout': 2000}})
    result = today.build_today(**args)
    assert [r['recipe_id'] for r in result['craft']] == [30]
    row = result['unplanned'][0]
    assert row['recipe_id'] == 40 and row['tonight_reason'] == 'missing prices'
    assert row['profit_copper'] is None and row['rank'] == 2
    state = dict(context=today_session.plan_context(args), choices=[], rows=[], refill=False, ticks={})
    omitted, _, _ = today_session.session_plan(args, state)
    assert omitted['unplanned'][0]['recipe_id'] == 30
    assert omitted['unplanned'][0]['tonight_reason'] == 'refill is off'


def test_unplanned_reason_uses_eligibility_and_remaining_reservations():
    args = arguments()
    result = today.build_today(**args)
    row = result['craft'][0]
    assert today.unplanned_reason(row, None, {'character_reason': 'needs pattern or other source'},
                                  args['settings'], None, {}, 100, {}) == 'needs pattern or other source'
    assert today.unplanned_reason(row, row, {}, args['settings'], None, {}, 0, {}) == 'one craft exceeds funds'
    assert today.unplanned_reason(row, row, {}, args['settings'], {}, {}, 100000, {}) == 'insufficient listed materials'
    assert today.unplanned_reason(row, row | {'net_revenue_copper': 0}, {}, args['settings'], None,
                                  {}, 100000, {}) == 'below minimum gain'


def test_line_display_preserves_full_text_confidence_and_catalog_evidence(browser):
    data = request(browser).json()
    craft = next(line for s in data['stops'] for line in s['lines'] if line['evidence']['stage'] == 'craft')
    assert craft['display']['item_id'] == 3
    assert 'recipe 30 (fixture)' in craft['text']
    assert craft['evidence']['confidence_reasons']
    before = deepcopy(data['plan']['queue'])
    assert today_session.stable_queue(before) == today_session.stable_queue(data['plan']['queue'])
    qualities = {(3, None, 'base'): 2, (3, 'random', 'variant'): 4}
    assert today_web.base_quality(qualities, 3) == 2
    assert today_web.base_quality({(3, None, None): 1}, 3) == 1
    assert today_web.base_quality({(3, 'random', 'variant'): 4}, 3) is None


def test_last_accepted_custom_size_is_remembered_for_later_refusal():
    args = arguments()
    _, state, _ = today_session.session_plan(args, {})
    state['choices'] = [dict(catalog_id='fixture', recipe_id=30, batch_size=3)]
    _, accepted, _ = today_session.session_plan(args, state)
    assert accepted['rows'][0]['batch_size'] != 3
    assert accepted['feasible_choices'][0]['batch_size'] == 3
    dropped = {'choice_limits': [{'catalog_id': 'fixture', 'recipe_id': 30, 'maximum': 1}],
               'dropped_choices': [{'catalog_id': 'fixture', 'recipe_id': 30, 'batch_size': 3,
                                   'reason': 'Choice is no longer feasible; dropped, not resized.'}]}
    today_session.explain_drops(dropped, accepted)
    assert dropped['dropped_choices'][0]['reason'].startswith('Choice is no longer feasible; at most 1')
    unchecked = [dict(catalog_id='fixture', recipe_id=30, batch_size=None)]
    assert today.selection_reason(('fixture', 30), unchecked, True, 0) == 'unchecked for tonight'
    assert today.selection_reason(('fixture', 30), None, True, 10) == '10-craft plan limit'
