"""Framework-free display values never re-quote or invent evidence."""
from views.today_rows import empty_sentence


def test_empty_sentence_leads_with_funds_and_top_reasons():
    sentence = empty_sentence({'below minimum gain': 2, 'rank below required skill': 5,
                               'missing prices': 1, 'zero': 0}, 1000, 255)
    assert '10s minimum batch gain with 2s 55c available' in sentence
    assert 'profession ranks are below the required skill and profit is below minimum gain' in sentence
    assert 'missing prices' not in sentence and 'zero' not in sentence
    assert 'Review your settings' in empty_sentence({}, 1, 0)


def test_imported_scan_count_deduplicates_collections_and_excludes_stopped_or_other_house():
    from brownstone.import_review import imported_scan_count

    complete = {'scan_id': 'one', 'status': 'completed', 'outcome': 'imported'}
    manifests = [{'scans': [complete, {'scan_id': 'stopped', 'status': 'stopped', 'outcome': 'imported'},
                            {'scan_id': 'other', 'status': 'completed', 'outcome': 'other house'}]},
                 {'scans': [complete | {'outcome': 'duplicate'}]}]
    assert imported_scan_count(manifests) == 1
    assert imported_scan_count([{}, {}]) == 2
    assert imported_scan_count([]) == 0
