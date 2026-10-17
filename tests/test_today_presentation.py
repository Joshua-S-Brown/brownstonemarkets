"""Framework-free display values never re-quote or invent evidence."""
from test_today_characters import CHARACTER, state

from views.today_rows import empty_sentence, planning_label, scan_status, stale_banner, summary_tiles


def test_undercut_summary_best_and_unavailable_are_from_sell():
    result = {'craft': [{}, {}], 'shopping_total_copper': 1263, 'sell': [
        {'output_name': 'Bag', 'undercut_batch_profit_copper': 838},
        {'output_name': 'Cloak', 'undercut_batch_profit_copper': 249}]}
    assert summary_tiles(result) == [('Crafts', '2'), ('Gold needed', '12s 63c'),
                                     ('Expected profit', '10s 87c'), ('Best craft', 'Bag · 8s 38c')]
    result['sell'][1]['undercut_batch_profit_copper'] = None
    assert summary_tiles(result)[2] == ('Expected profit', 'unavailable')
    result['sell'] = []
    assert summary_tiles(result)[3] == ('Best craft', 'none valued')


def test_empty_sentence_leads_with_funds_and_top_reasons():
    sentence = empty_sentence({'below minimum gain': 2, 'rank below required skill': 5,
                               'missing prices': 1, 'zero': 0}, 1000, 255)
    assert '10s minimum batch gain with 2s 55c available' in sentence
    assert 'profession ranks are below the required skill and profit is below minimum gain' in sentence
    assert 'missing prices' not in sentence and 'zero' not in sentence
    assert 'Review your settings' in empty_sentence({}, 1, 0)


def test_price_chips_distinguish_scan_download_and_future():
    assert scan_status({'age_hours': 33, 'upstream_known': True}) == 'Scan 33 hours old'
    assert 'price age unknown' in scan_status({'age_hours': 2, 'upstream_known': False})
    assert scan_status({'age_hours': -1}) == 'Scan dated in the future'
    assert 'future' in stale_banner({'age_hours': -1})
    assert 'scan again before you buy' in stale_banner({'age_hours': 33})


def test_planning_label_uses_scoped_rank_without_inference():
    data = {CHARACTER: state(learned=True)}
    assert planning_label(None, data) == 'Planning for Our team'
    assert planning_label(('Gone', 'Beta', 'Alliance'), data) == 'Planning for Our team'
    assert 'Basilly' in planning_label(CHARACTER, data)
    assert '8' in planning_label(CHARACTER, data)
    assert planning_label(CHARACTER, {CHARACTER: {'recipes': {}}}) == 'Planning for Basilly'


def test_material_card_rows_preserve_reserved_surplus_and_money():
    from views.today_rows import material_card_rows

    assert material_card_rows([{'item_name': 'Cloth', 'method': 'auction', 'purchased_units': 48,
                                'quantity': 30, 'cost_copper': 432, 'stale': False},
                               {'item_name': 'Thread', 'method': 'vendor', 'purchased_units': 15,
                                'quantity': 15, 'cost_copper': 150, 'stale': False}]) == [
        {'Material': 'Cloth', 'Where': 'Auction house', 'Units': '48 (30 needed)', 'Cost': '4s 32c',
         'State': 'potential gain'},
        {'Material': 'Thread', 'Where': 'Vendor', 'Units': '15', 'Cost': '1s 50c', 'State': 'potential gain'}]


def test_imported_scan_count_deduplicates_collections_and_excludes_stopped_or_other_house():
    from brownstone.import_review import imported_scan_count

    complete = {'scan_id': 'one', 'status': 'completed', 'outcome': 'imported'}
    manifests = [{'scans': [complete, {'scan_id': 'stopped', 'status': 'stopped', 'outcome': 'imported'},
                            {'scan_id': 'other', 'status': 'completed', 'outcome': 'other house'}]},
                 {'scans': [complete | {'outcome': 'duplicate'}]}]
    assert imported_scan_count(manifests) == 1
    assert imported_scan_count([{}, {}]) == 2
    assert imported_scan_count([]) == 0


def test_display_filter_counts_do_not_change_the_reserved_plan():
    from views.today_rows import display_hidden

    result = {'hidden': {'missing prices': 2}, 'craft': [{'confidence': 'Low'}, {'confidence': 'High'}]}
    assert display_hidden(result, False) == {'missing prices': 2}
    assert display_hidden(result, True) == {'missing prices': 2, 'low confidence': 1}
    assert result['hidden'] == {'missing prices': 2} and len(result['craft']) == 2


def test_recorded_gold_rows_show_capture_beside_entered_budget_without_making_missing_gold_free():
    from views.today_rows import recorded_gold_rows

    data = {CHARACTER: {'bags': {'gold_copper': 255, 'captured_at': 1791716241}},
            ('Other', 'Beta', 'Alliance'): {'bags': {'gold_copper': 0, 'captured_at': 1791716241}},
            ('Missing', 'Beta', 'Alliance'): {}}
    assert recorded_gold_rows(data, CHARACTER) == [
        {'Character': 'Basilly', 'Recorded gold': '2s 55c',
         'Captured (UTC)': '2026-10-11T10:57:21+00:00'}]
    rows = recorded_gold_rows(data, None)
    assert len(rows) == 3 and sum(r['Recorded gold'] == 'unknown' for r in rows) == 2
    assert data[CHARACTER]['bags']['gold_copper'] == 255


def test_summary_tiles_follow_hide_low_but_keep_reserved_gold():
    result = {'craft': [{'output_item_id': 1, 'confidence': 'High'}, {'output_item_id': 2, 'confidence': 'Low'}],
              'shopping_total_copper': 1263, 'sell': [
                  {'output_item_id': 1, 'output_name': 'Bag', 'undercut_batch_profit_copper': 249},
                  {'output_item_id': 2, 'output_name': 'Cloak', 'undercut_batch_profit_copper': 838}]}
    assert summary_tiles(result, hide_low=True) == [('Crafts', '1'), ('Gold needed', '12s 63c'),
                                                    ('Expected profit', '2s 49c'), ('Best craft', 'Bag · 2s 49c')]
    assert summary_tiles(result)[3] == ('Best craft', 'Cloak · 8s 38c')
