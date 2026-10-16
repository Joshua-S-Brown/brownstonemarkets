"""UI-17 charts, scan selection, single/empty/error states and item-only loading."""
import pytest
from nicegui import ui

from brownstone import item_history as ih
from views.nicegui_item_history import history_options, ladder_options

from .test_nicegui_market import market_app

pytestmark = pytest.mark.asyncio


async def test_charts_picker_money_sortable_table_and_lazy_loading(user, tmp_path, monkeypatch):
    config, _ = market_app(tmp_path, monkeypatch)
    calls = []
    original = ih.load_history
    def tracked(config, item_id):
        calls.append(item_id)
        return original(config, item_id)
    monkeypatch.setattr(ih, 'load_history', tracked)
    await user.open('/?place=Market')
    assert calls == []
    await user.open('/?place=Today')
    assert calls == []
    await user.open('/?place=Market&item=2589')
    await user.should_see('Price history and listing ladder')
    assert calls == [2589]
    await user.should_see('1 buyout listings · 11 units · 1 price levels')
    await user.should_see('Units listed are supply, never sales, demand or volume.')
    charts = sorted(user.find(ui.echart).elements, key=lambda e: e.id)
    assert len(charts) == 2
    options = charts[0].options
    assert options['xAxis']['type'] == 'time'
    assert options['yAxis'][1]['name'] == 'Units listed'
    first = options['series'][0]['data'][0]
    assert first['value'][1] == 10
    assert 'Scan scan-0' in first['detail'] and 'UTC' in first['detail'] and 'local' in first['detail']
    assert 'Lowest / unit: 10c' in first['detail']
    assert all(s['showSymbol'] and not s['connectNulls'] for s in options['series'])
    picker = next(iter(user.find(marker='item-ladder-scan').elements))
    assert list(picker.options) == ['scan-1', 'scan-0']
    picker.set_value('scan-0')
    await user.should_see('1 buyout listings · 10 units · 1 price levels')
    table = next(iter(user.find(marker='item-ladder-table').elements))
    assert all(c['sortable'] for c in table.columns)
    assert table.rows[0]['price_label'] == '0.0010'
    assert table.rows[0]['price_copper'] == 10
    assert next(e for e in user.find(ui.echart).elements if 'item-ladder-chart' in e._markers).options[
        'series'][0]['step'] == 'end'
    assert 'Made from' in [e.text for e in user.find(ui.label).elements]
    # Unchanged identity page remains available after changing ladder.
    await user.should_see('Item 2589')
    assert config['provider'] == 'addon'


async def test_single_scan_no_buyout_absent_tsm_and_other_identities(user, tmp_path, monkeypatch):
    import duckdb
    config, _ = market_app(tmp_path, monkeypatch, count=1)
    await user.open('/?place=Market&item=2589')
    await user.should_see('More scans with compatible item evidence are needed for a trend.')
    await user.open('/?place=Market&item=99999')
    await user.should_see('Without a buyout: 1 listings · 1 units (excluded from prices)')
    await user.should_see('No buyout prices to chart. Choose another scan.')
    await user.open('/?place=Market&item=123456')
    await user.should_see('Base item absent or legacy identity incompatible in this scan.')
    monkeypatch.setattr('brownstone.config.read_sources', lambda *args: [config | {'provider': 'tsm'}])
    await user.open('/?place=Market&item=2589')
    await user.should_see('TSM source: no addon price history.')
    monkeypatch.setattr('brownstone.config.read_sources', lambda *args: [config])
    with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb')) as db:
        db.execute("UPDATE scan_metrics SET variant_state='unresolved' WHERE item_id=2589")
    await user.open('/?place=Market&item=2589')
    await user.should_see('Newest scan: 1 other identities, excluded')


async def test_failures_are_local_and_empty_scan_guidance(user, tmp_path, monkeypatch):
    market_app(tmp_path, monkeypatch)
    original = ih.load_history
    def broken(*args):
        raise OSError('fixture read failure')
    monkeypatch.setattr(ih, 'load_history', broken)
    await user.open('/?place=Market&item=2996')
    await user.should_see('Unable to read item history: fixture read failure')
    await user.should_see('Use Data to check saved scans, then reopen this item.')
    await user.should_see('Made from')
    await user.should_see('Removed between scans')
    monkeypatch.setattr(ih, 'load_history', original)
    monkeypatch.setattr(ih, 'load_ladder', broken)
    await user.open('/?place=Market&item=2996')
    await user.should_see('Unable to read listing ladder: fixture read failure')
    assert len(user.find(ui.echart).elements) == 1
    monkeypatch.setattr(ih, 'load_history', lambda *args: {'note': 'No eligible scans. Use Data to import scans.'})
    await user.open('/?place=Market&item=2996')
    await user.should_see('No eligible scans. Use Data to import scans.')


async def test_option_gaps_nulls_and_theme_colors(user):
    from datetime import UTC, datetime

    from views import nicegui_theme as theme
    point = {'scan_id': 'gap', 'finished_at': datetime(2026, 10, 15, tzinfo=UTC), 'metrics': None}
    options = history_options({'points': [point, point | {'metrics': {
        'min_buyout': None, 'market_value': None, 'units': 12}}]})
    assert [p['value'][1] for p in options['series'][0]['data']] == [None, None]
    assert [p['value'][1] for p in options['series'][2]['data']] == [None, 12]
    assert 'gap' in options['series'][0]['data'][0]['detail']
    assert options['color'] == theme.CHART_COLORS
    assert not options['legend']['selectedMode']
    assert options['dataZoom'][0]['height'] >= 44
    assert options['media'][0]['query']['maxWidth'] == 400
    options = ladder_options({'rows': [{'price_copper': 12345, 'listings': 2, 'units': 3,
                                       'cumulative_units': 3}]})
    assert options['xAxis']['axisLabel']['hideOverlap']
    assert options['series'][0]['data'][0]['value'] == [12345, 3]
    assert '1g 23s 45c' in options['series'][0]['data'][0]['detail']
    assert 'endValue' not in options['dataZoom'][0]


async def test_ladder_zooms_past_outlier_asks():
    rows = [{'price_copper': p, 'listings': 1, 'units': u, 'cumulative_units': c}
            for p, u, c in [(20, 90, 90), (25, 6, 96), (500_000, 4, 100)]]
    options = ladder_options({'rows': rows})
    assert options['dataZoom'][0]['endValue'] == 25
    assert options['dataZoom'][0]['filterMode'] == 'none'
