"""Today UI uses only synthetic sources/catalogs and local preferences."""
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from conftest import make_source
from test_today import catalog

from brownstone.pipeline import run
from brownstone.today_settings import TodaySettings, load_settings, save_settings, settings_path

pytest.importorskip('streamlit')
from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def app(tmp_path, monkeypatch, *, stale=False, corrupt=False):
    source = make_source(tmp_path / 'data', game_version='classic', realm='mankrik', faction='alliance',
                         rules_version='fixture-v1', allow_missing_updated_at=True)
    time = (datetime.now(UTC) - timedelta(hours=25)).isoformat() if stale else ''
    csv = tmp_path / 'items.csv'
    csv.write_text('itemId,name,marketValue,minBuyout,recent,historical,updatedAt\n'
                   f'1,Material,20,10,0,0,{time}\n3,Output,2000,2000,0,0,{time}\n')
    source["max_age_hours"] = 48
    run(source, csv)
    source["max_age_hours"] = 24
    path = settings_path(source['data_dir'], source['source_id'])
    save_settings(path, TodaySettings(100000, 1, 'fixed'))
    if corrupt:
        path.write_text('not json')
    monkeypatch.setattr('brownstone.config.read_sources', lambda *args: [source])
    monkeypatch.setattr('brownstone.recipe_catalogs.find_catalogs',
                        lambda *args: [{'name': 'fixture', 'catalog': catalog()}])
    return AppTest.from_file(str(ROOT / 'app.py')).run(), source, path


def widget(widgets, label):
    return next(w for w in widgets if w.label == label)


def test_today_default_settings_save_rejection_and_new_session(tmp_path, monkeypatch):
    at, _, path = app(tmp_path, monkeypatch)
    assert not at.exception and at.radio[0].value == 'Today'
    assert any('not available for this source' in i.value for i in at.info)
    assert [tab.label for tab in at.tabs] == ['Craft', 'Buy', 'Sell', 'Below vendor', 'Queue']
    settings = next(e for e in at.expander if e.label == 'Today settings')
    assert not settings.proto.expanded and len(settings.text_input) == 2
    assert any(c.value == 'Gold available: 10g · Minimum batch gain: 1c · Most crafts per item: 5'
               for c in at.caption)
    assert any('Batch profit (g)' in t.value.columns for t in at.dataframe)
    widget(at.text_input, 'Gold available').set_value('12')
    widget(at.button, 'Save Today settings').click().run()
    assert any('bare numbers' in e.value for e in at.error)
    assert load_settings(path).gold_copper == 100000
    # A rejected save keeps the plan visible, still sized by the last saved settings.
    assert any('Batch profit (g)' in t.value.columns for t in at.dataframe)
    widget(at.text_input, 'Gold available').set_value('12g 50s')
    widget(at.text_input, 'Fixed minimum gain').set_value('10s')
    widget(at.selectbox, 'Minimum gain mode').set_value('scaled')
    widget(at.number_input, 'Most crafts per item').set_value(3)
    widget(at.button, 'Save Today settings').click().run()
    assert not at.exception and load_settings(path) == TodaySettings(125000, 1000, 'scaled', 100, 3)
    again = AppTest.from_file(str(ROOT / 'app.py')).run()
    assert widget(again.text_input, 'Gold available').value == '12g 50s'
    assert widget(again.number_input, 'Most crafts per item').value == 3


def test_today_stale_banner_inspection_and_corrupt_settings(tmp_path, monkeypatch):
    at, _, _ = app(tmp_path, monkeypatch, stale=True)
    assert not at.exception and any('stale' in w.value for w in at.warning)
    for table in at.dataframe:
        assert set(table.value['State']) == {'stale — inspect only'}
    at, _, _ = app(tmp_path, monkeypatch, corrupt=True)
    assert not at.exception and any('Could not read Today settings' in w.value for w in at.warning)
    assert widget(at.text_input, 'Gold available').value == '0c'
    assert next(e for e in at.expander if e.label == 'Today settings').proto.expanded


def test_today_reports_calculation_and_persistence_errors(tmp_path, monkeypatch):
    at, _, _ = app(tmp_path, monkeypatch)
    def fail(*args, **kwargs):
        raise OSError('fixture failure')
    monkeypatch.setattr('views.today.save_settings', fail)
    widget(at.button, 'Save Today settings').click().run()
    assert any('Settings not saved' in e.value for e in at.error)
    monkeypatch.setattr('views.today.build_today', fail)
    at.run()
    assert any('Unable to build Today' in e.value for e in at.error)


def test_today_zero_gold_opens_settings_without_writing(tmp_path, monkeypatch):
    at, _, path = app(tmp_path, monkeypatch)
    path.unlink()
    at.run()
    assert not at.exception and not path.exists()
    assert next(e for e in at.expander if e.label == 'Today settings').proto.expanded
    assert any('Gold available: 0c' in c.value for c in at.caption)


def test_today_unsaved_edits_keep_summary_plan_and_file(tmp_path, monkeypatch):
    at, _, path = app(tmp_path, monkeypatch)
    before = path.read_bytes()
    table = at.tabs[0].dataframe[0].value
    widget(at.text_input, 'Gold available').set_value('99g')
    at.run()
    assert path.read_bytes() == before
    assert at.tabs[0].dataframe[0].value.equals(table)
    assert any('Gold available: 10g' in c.value for c in at.caption)


def listing_evidence_app(tmp_path, monkeypatch, hours):
    from test_scans import addon_source, listing, scan, write_scans

    from brownstone.pipeline import import_scans
    source = addon_source(tmp_path / 'addon-data', game_version='classic', realm='mankrik', server_type='',
                         faction='alliance', rules_version='fixture-v1', max_age_hours=48,
                         scan_evidence={'faction': 'Alliance'})
    finish = int((datetime.now(UTC) + timedelta(hours=hours)).timestamp())
    path = write_scans(tmp_path / 'evidence.lua', scan('evidence', finish,
                       [listing(1, 2, 20), listing(1, 4, 80), listing(3, 8, 16000)]))
    source['scan_path'] = path
    # Import under that clock, then render under the current clock to exercise clock rollback.
    import_scans(source, path, now=datetime.fromtimestamp(finish + 1, UTC))
    source['max_age_hours'] = 24
    save_settings(settings_path(source['data_dir'], source['source_id']), TodaySettings(100000, 1, 'fixed'))
    monkeypatch.setattr('brownstone.config.read_sources', lambda *args: [source])
    monkeypatch.setattr('brownstone.recipe_catalogs.find_catalogs',
                        lambda *args: [{'name': 'fixture', 'catalog': catalog()}])
    original = __import__('views.today', fromlist=['read_today_evidence']).read_today_evidence

    def evidence(db, config, sid, ids):
        observations, listings, metrics, _ = original(db, config, sid, ids)
        return observations, listings, metrics, {1: 21}

    monkeypatch.setattr('views.today.read_today_evidence', evidence)
    return AppTest.from_file(str(ROOT / 'app.py')).run(), source


@pytest.mark.parametrize('hours', [0, -25, 1])
def test_today_all_tabs_decision_columns_evidence_and_stale_state(tmp_path, monkeypatch, hours):
    at, source = listing_evidence_app(tmp_path, monkeypatch, hours)
    assert not at.exception
    assert [t.label for t in at.tabs] == ['Craft', 'Buy', 'Sell', 'Below vendor', 'Queue']
    columns = [
        ['Item', 'Profession', 'Batch', 'Limited by', 'Material cost (g)', 'Batch profit (g)',
         'Profit per craft (g)', 'Thin', 'State'],
        ['Material', 'Route', 'Required units', 'Purchased units', 'Cost (g)', 'Highest unit price (g)',
         'Cheap now', 'State'],
        ['Output', 'Batch', 'Lowest competing unit (g)', 'Listings', 'Units', 'Undercut unit (g)',
         'Profit at undercut for batch (g)', 'Thin', 'State'],
        ['Item', 'Units', 'Cost (g)', 'Vendor pays per unit (g)', 'Gain (g)', 'State']]
    originals = [tab.dataframe[0].value.copy() for tab in at.tabs[:4]]
    for tab, expected in zip(at.tabs[:4], columns, strict=True):
        assert list(tab.dataframe[0].value.columns) == expected
        assert any('more rows' in c.value for c in tab.caption)
        assert set(tab.dataframe[0].value['State']) == ({'stale — inspect only'} if hours else {'potential gain'})
    assert bool(at.warning) == bool(hours)
    assert not any('not available for this source' in i.value for i in at.info)
    assert any('Hidden recipes:' in c.value for c in at.tabs[0].caption)
    assert any('Whole shopping list:' in c.value and 'Cheap now means' in c.value for c in at.tabs[1].caption)
    provenance = [c.value for c in at.main.caption if c.value.startswith('Today rules v')]
    assert len(provenance) == 1
    assert all(text in provenance[0] for text in [source['source_id'], source['market_id'],
                                                'snapshot', 'scan evidence', 'UTC', 'time basis upstream scan'])
    for toggle in at.toggle:
        if toggle.label == "Show evidence columns":
            toggle.set_value(True)
    at.run()
    assert not at.exception
    for tab, original in zip(at.tabs[:4], originals, strict=True):
        table = tab.dataframe[0].value
        assert table[original.columns].equals(original)
        assert len(table.columns) > len(original.columns)
        assert not {'Source', 'Scan / snapshot', 'Evidence time (UTC)', 'Time basis'} & set(table.columns)
    assert {'Catalog', 'Recipe', 'Availability', 'Evidence notes', 'Recipe source'} <= set(
        at.tabs[0].dataframe[0].value.columns)
    assert 'Scan p25 (g)' in at.tabs[1].dataframe[0].value.columns
    assert at.tabs[1].dataframe[0].value['Scan p25 (g)'].isna().sum() == 1  # Vendor evidence remains missing.
    assert 'Largest stack units' in at.tabs[2].dataframe[0].value.columns
    assert 'Listings' in at.tabs[3].dataframe[0].value.columns


def test_today_addon_without_listing_evidence_says_so(tmp_path, monkeypatch):
    # An addon snapshot without eligible scan metrics has no listing evidence, like TSM.
    monkeypatch.setattr('brownstone.today_data.read_scan_metrics', lambda *args: None)
    at, _ = listing_evidence_app(tmp_path, monkeypatch, 0)
    assert not at.exception
    assert any('not available for this source' in i.value for i in at.info)
    assert not len(at.tabs[3].dataframe)  # No listing ladders, so no below-vendor rows.


def test_crafting_groups_unsupported_recipes_and_explanations(tmp_path, monkeypatch):
    from copy import deepcopy

    at, _, _ = app(tmp_path, monkeypatch)
    unsupported = deepcopy(catalog())
    unsupported['recipes_by_id'][30]['inputs'].append({'item_id': 3, 'quantity': 1})
    unsupported['recipes'] = list(unsupported['recipes_by_id'].values())
    entries = [{'name': name, 'catalog': deepcopy(unsupported)} for name in ['one', 'two', 'three']]
    monkeypatch.setattr('brownstone.recipe_catalogs.find_catalogs', lambda *args: entries)
    at.radio[0].set_value('Crafting').run()
    assert not at.exception
    errors = next(e for e in at.expander if e.label == '3 recipes could not be evaluated')
    assert not errors.proto.expanded
    table = errors.dataframe[0].value
    assert list(table.columns) == ['Output', 'Profession', 'Catalog', 'Reason']
    assert list(table['Catalog']) == ['one', 'three', 'two']
    assert all('Recipe cycle' in reason for reason in table['Reason'])
    assert not any('could not be evaluated' in w.value for w in at.warning)
    catalogs = next(e for e in at.expander if e.label == 'Catalogs on this board (3)')
    how = next(e for e in at.expander if e.label == 'How to read this board')
    assert not catalogs.proto.expanded and len(catalogs.caption) == 3
    assert not how.proto.expanded and len(how.caption) == 3
    visible = [c.value for c in at.main.children.values() if c.type == 'caption']
    assert any(c.startswith('Policy ') and 'SHA-256' in c for c in visible)
    assert any(c.startswith('Price age unknown:') for c in visible)
    assert not any('Depth counts' in c or 'Margin = ' in c or 'Selected catalogs' in c for c in visible)


def select_craft(at):
    key = at.session_state['today-craft-selection-key']
    at.session_state[key] = {'selection': {'rows': [0], 'columns': [], 'cells': []}}
    return at.run()


def test_today_craft_selection_details_and_plan_change_reset(tmp_path, monkeypatch):
    at, _, _ = app(tmp_path, monkeypatch)
    assert len(at.tabs[0].dataframe) == 1  # No selection by default.
    key = at.session_state['today-craft-selection-key']
    assert at.tabs[0].dataframe[0].proto.selection_mode
    select_craft(at)
    assert not at.exception and len(at.tabs[0].dataframe) == 2
    details = at.tabs[0].dataframe[1].value
    assert list(details['Route']) == ['auction house', 'vendor']
    assert list(details['Required units']) == [10, 5]
    assert details['Cost (g)'].sum() == at.tabs[0].dataframe[0].value['Material cost (g)'][0]
    buy = at.tabs[1].dataframe[0].value.copy()
    widget(at.toggle, 'Show evidence columns').set_value(True).run()
    assert at.session_state['today-craft-selection-key'] == key
    select_craft(at)
    assert len(at.tabs[0].dataframe) == 2
    assert at.tabs[1].dataframe[0].value.equals(buy)
    widget(at.number_input, 'Most crafts per item').set_value(2)
    widget(at.button, 'Save Today settings').click().run()
    assert not at.exception and at.session_state['today-craft-selection-key'] != key
    assert len(at.tabs[0].dataframe) == 1
    assert key not in at.session_state


def test_today_selected_stale_craft_details_and_indented_steps(tmp_path, monkeypatch):
    from test_today import chain_catalog

    at, _, _ = app(tmp_path, monkeypatch, stale=True)
    monkeypatch.setattr('brownstone.recipe_catalogs.find_catalogs',
                        lambda *args: [{'name': 'chain', 'catalog': chain_catalog()}])
    at.run()
    select_craft(at)
    assert not at.exception and len(at.tabs[0].dataframe) == 2
    assert set(at.tabs[0].dataframe[1].value['State']) == {'stale — inspect only'}
    steps = at.text[0].value.splitlines()
    assert steps[1].startswith('    ↳ Intermediate 5: 10 crafts → 10 units')
    assert steps[2].startswith('        ↳ Intermediate 6: 20 crafts → 20 units')
    assert all('stale — inspect only' in line for line in steps[1:])


def test_today_choices_queue_ticks_copy_and_resets(tmp_path, monkeypatch):
    at, _, path = app(tmp_path, monkeypatch)
    before = path.read_bytes()
    craft_check = at.tabs[0].checkbox[0]
    assert craft_check.value is True
    batch = widget(at.number_input, 'Batch for Fixture 3')
    assert batch.value == 5 and batch.min == 1 and batch.max == 5
    queue = at.tabs[4]
    assert len(queue.checkbox) == 4
    queue.checkbox[0].check().run()
    assert at.tabs[4].checkbox[0].value
    original = at.tabs[1].dataframe[0].value.copy()
    at.tabs[4].checkbox[1].check().run()
    assert at.tabs[1].dataframe[0].value.equals(original)
    widget(at.toggle, 'Copy as text').set_value(True).run()
    copied = at.code[0].value
    assert all(w.label in copied for w in at.tabs[4].checkbox)
    assert 'Gold needed:' in copied and 'Expected profit at undercut: unavailable' in copied
    batch = widget(at.number_input, 'Batch for Fixture 3')
    batch.set_value(2).run()
    assert not at.exception
    assert not any(w.value for w in at.tabs[4].checkbox)
    assert at.tabs[2].dataframe[0].value['Batch'][0] == 2
    assert at.tabs[0].dataframe[0].value['Batch profit (g)'][0] < .935
    assert path.read_bytes() == before
    at.tabs[0].checkbox[0].uncheck().run()
    assert not at.tabs[1].dataframe and not at.tabs[2].dataframe and not at.tabs[4].checkbox
    widget(at.number_input, 'Most crafts per item').set_value(3)
    widget(at.button, 'Save Today settings').click().run()
    assert at.tabs[0].checkbox[0].value and widget(at.number_input, 'Batch for Fixture 3').value == 3
    assert any('session choices and queue ticks reset' in i.value for i in at.info)
    again = AppTest.from_file(str(ROOT / 'app.py')).run()
    assert again.tabs[0].checkbox[0].value and not any(w.value for w in again.tabs[4].checkbox)


def test_today_queue_ticks_survive_evidence_turning_stale(tmp_path, monkeypatch):
    at, _, _ = app(tmp_path, monkeypatch)
    at.tabs[4].checkbox[0].check().run()
    from brownstone.today import build_today

    def aged(**args):
        result = build_today(**args)
        result['craft'] = [{**row, 'stale': True} for row in result['craft']]
        return result
    monkeypatch.setattr('views.today.build_today', aged)
    at.run()
    assert not at.exception and at.tabs[4].checkbox[0].value


def test_today_source_scoping_and_scan_reset(tmp_path, monkeypatch):
    from copy import deepcopy

    at, source, _ = app(tmp_path, monkeypatch)
    other = deepcopy(source)
    other['source_id'] = 'other'
    # Keep fixtures scoped: the other source has no snapshot and cannot borrow this plan.
    monkeypatch.setattr('brownstone.config.read_sources', lambda *args: [source, other])
    at.run()
    widget(at.selectbox, 'Data source').set_value(0).run()
    at.tabs[4].checkbox[0].check().run()
    widget(at.number_input, 'Batch for Fixture 3').set_value(2).run()
    at.tabs[4].checkbox[0].check().run()
    widget(at.selectbox, 'Data source').set_value(1).run()
    assert not at.tabs and any('import a scan' in i.value for i in at.info)
    widget(at.selectbox, 'Data source').set_value(0).run()
    assert widget(at.number_input, 'Batch for Fixture 3').value == 2
    assert at.tabs[4].checkbox[0].value
    original = __import__('views.today', fromlist=['load_latest']).load_latest
    def changed(config, message):
        manifest, sid, count = original(config, message)
        return {**manifest, 'scan_id': 'new-scan'}, sid, count
    monkeypatch.setattr('views.today.load_latest', changed)
    at.run()
    assert not at.exception and widget(at.number_input, 'Batch for Fixture 3').value == 5
    assert not any(w.value for w in at.tabs[4].checkbox)
    assert any('Previous choices were dropped, not resized' in i.value for i in at.info)


def test_today_refill_added_row_edit_and_ticks_stable(tmp_path, monkeypatch):
    from test_today import two_plan

    at, source, _ = app(tmp_path, monkeypatch)
    source["max_age_hours"] = 48
    def fixture(**args):
        result = two_plan(settings=TodaySettings(130, 1, 'fixed', max_crafts=3),
                        listings={1: [(2, 20, 10), (4, 80, 20), (6, 180, 30)]},
                        **{k: args[k] for k in ('choices', 'refill') if k in args})
        for row in result['craft']:
            if row['catalog_id'] == 'second':
                row['output_name'] = 'Second craft'
        return result
    monkeypatch.setattr('views.today.build_today', fixture)
    at.run()
    at.tabs[0].checkbox[0].uncheck().run()
    assert len(at.tabs[0].checkbox) == 2 and at.tabs[0].checkbox[1].value
    assert at.tabs[0].dataframe[0].value['Item'][0] == 'Second craft'
    at.tabs[4].checkbox[0].check().run()
    assert at.tabs[4].checkbox[0].value  # New refill controls do not change the plan on the next rerun.
    at.tabs[0].checkbox[0].check().run()
    assert at.tabs[0].checkbox[0].value and not at.tabs[0].checkbox[1].value
    assert any(w.value.startswith('Second craft: ') and 'dropped, not resized' in w.value for w in at.warning)
    at.tabs[0].checkbox[0].uncheck().run()
    at.tabs[0].checkbox[1].check().run()
    widget(at.toggle, 'Refill freed gold with next-best crafts').set_value(False).run()
    assert len(at.tabs[0].dataframe[0].value) == 1  # Ticked refill row stays in the exact plan.
    assert any('refill is off' in c.value for c in at.tabs[0].caption)
    widget(at.number_input, 'Batch for Second craft').set_value(1).run()
    assert at.tabs[0].dataframe[0].value['Batch'][0] == 1

    at.tabs[0].checkbox[0].check().run()
    assert at.tabs[0].checkbox[0].value and not at.tabs[0].checkbox[1].value
    assert len(at.tabs[0].dataframe[0].value) == 1
    assert any('dropped, not resized' in w.value for w in at.warning)



def test_today_drops_infeasible_choice_with_note(tmp_path, monkeypatch):
    from streamlit.elements.lib import policies

    logged = []
    monkeypatch.setattr(policies, '_shown_default_value_warning', False)
    monkeypatch.setattr(policies._LOGGER, 'warning', lambda message, *args, **kwargs: logged.append(message))
    at, _, _ = app(tmp_path, monkeypatch)
    from brownstone.today import build_today

    def restricted(**args):
        return build_today(**{**args, 'settings': TodaySettings(100000, 1, 'fixed', max_crafts=3)})
    monkeypatch.setattr('views.today.build_today', restricted)
    # A previously editable quantity is now outside the calculation's feasible bound.
    widget(at.number_input, 'Batch for Fixture 3').set_value(4).run()
    assert not at.exception and not at.tabs[0].checkbox[0].value
    assert not at.tabs[1].dataframe and not at.tabs[2].dataframe
    assert any('dropped, not resized' in w.value for w in at.warning)
    assert not any('Session State API' in message for message in logged)
