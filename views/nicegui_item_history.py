"""Item charts over UI-17 evidence; NiceGUI stays outside the calculation module."""
from datetime import UTC

from nicegui import ui

from brownstone import item_history
from brownstone.freshness import age_caption
from brownstone.money import COPPER_PER_GOLD, GOLD_TABLE_FORMAT, format_money, to_gold
from views import nicegui_theme as theme

GOLD_AXIS_FORMATTER = f'(v) => (v / {COPPER_PER_GOLD}).toFixed(4)'


def scan_label(scan):
    finished = scan['finished_at']
    return f"{finished.astimezone(UTC):%Y-%m-%d %H:%M:%S} UTC · {finished.astimezone():%Y-%m-%d %H:%M:%S %Z} local"


def chart_options():
    return {'color': theme.CHART_COLORS, 'backgroundColor': theme.CHART_SURFACE,
            'textStyle': {'color': theme.CHART_INK},
            'grid': {'left': 12, 'right': 16, 'top': 64, 'bottom': 90, 'containLabel': True},
            'legend': {'type': 'plain', 'selectedMode': False, 'top': 4, 'textStyle': {'color': theme.CHART_INK}},
            'tooltip': {'trigger': 'axis', 'renderMode': 'richText', 'confine': True,
                        ':formatter': '(params) => params.length ? params[0].data.detail : ""'},
            'media': [{'query': {'maxWidth': 400}, 'option': {'grid': {'top': 96}}}],
            'dataZoom': [{'type': 'slider', 'height': 44, 'bottom': 4}]}


def history_options(evidence):
    series = []
    for key, name, axis in [('min_buyout', 'Lowest unit buyout', 0), ('market_value', 'Market value (p25)', 0),
                             ('units', 'Units listed', 1)]:
        data = []
        for point in evidence['points']:
            metrics = point['metrics']
            detail = f"Scan {point['scan_id']}\n{scan_label(point)}\n"
            detail += (f"Lowest / unit: {format_money(metrics['min_buyout'])}\n"
                       f"Market value (p25): {format_money(metrics['market_value'])}\n"
                       f"Units listed: {metrics['units']:,}" if metrics else 'Base item absent or incompatible: gap')
            data.append({'value': [int(point['finished_at'].timestamp()) * 1000,
                                   metrics[key] if metrics else None], 'detail': detail})
        series.append({'name': name, 'type': 'line', 'yAxisIndex': axis, 'data': data,
                       'connectNulls': False, 'showSymbol': True, 'symbolSize': 6})
    return {**chart_options(), 'xAxis': {'type': 'time'}, 'yAxis': [
        {'type': 'value', 'name': 'Price (gold)', 'axisLabel': {':formatter': GOLD_AXIS_FORMATTER},
         'splitLine': {'lineStyle': {'color': theme.CHART_LINE}}},
        {'type': 'value', 'name': 'Units listed', 'minInterval': 1, 'splitLine': {'show': False}}], 'series': series}


def zoom_end(rows, share=95):
    """Cheapest price covering `share`% of buyout units, so outlier asks don't flatten the ladder."""
    total = rows[-1]['cumulative_units']
    return next(r['price_copper'] for r in rows if r['cumulative_units'] * 100 >= total * share)


def ladder_options(result):
    rows = result['rows']
    zoom = {**chart_options()['dataZoom'][0], 'filterMode': 'none'}
    end = zoom_end(rows) if rows else None
    if end is not None and end < rows[-1]['price_copper']:
        zoom['endValue'] = end
    data = [{'value': [r['price_copper'], r['cumulative_units']],
             'detail': f"{format_money(r['price_copper'])} / unit\n{r['listings']:,} listings · "
                       f"{r['units']:,} units\n{r['cumulative_units']:,} cumulative units"} for r in result['rows']]
    return {**chart_options(), 'xAxis': {'type': 'value', 'name': 'Unit price (gold)', 'nameLocation': 'middle',
                                        'nameGap': 28, 'axisLabel': {
                                            'hideOverlap': True, ':formatter': GOLD_AXIS_FORMATTER}},
            'yAxis': {'type': 'value', 'name': 'Cumulative units', 'minInterval': 1}, 'dataZoom': [zoom],
            'series': [{'name': 'Cumulative units', 'type': 'line', 'step': 'end', 'data': data}]}


def draw_chart(options, marker):
    ui.echart(options).classes('w-full min-w-0').style('height:380px;max-width:100%').mark(marker)


def ladder_panel(config, item_id, evidence, scan_id):
    try:
        result = item_history.load_ladder(config, item_id, evidence, scan_id)
    except Exception as error:
        ui.label(f'Unable to read listing ladder: {error}. Use Data to check saved scans, then reopen this item.')
        return
    fresh = result['freshness']
    theme.chip(age_caption(fresh, config['max_age_hours']))
    if fresh['stale']:
        theme.badge('Stale', 'warn')
    if result['note']:
        ui.label(result['note'] + ' Choose another scan.').classes('bs-note')
        return
    rows = result['rows']
    ui.label(f"{sum(r['listings'] for r in rows):,} buyout listings · "
             f"{sum(r['units'] for r in rows):,} units · {len(rows):,} price levels")
    ui.label(f"Without a buyout: {result['no_buyout_listings']:,} listings · "
             f"{result['no_buyout_units']:,} units (excluded from prices)").classes('bs-note')
    if not rows:
        ui.label('No buyout prices to chart. Choose another scan.').classes('bs-note')
        return
    options = ladder_options(result)
    draw_chart(options, 'item-ladder-chart')
    if 'endValue' in options['dataZoom'][0]:
        ui.label('Zoomed to the cheapest 95% of units; drag the slider to see higher asks.').classes('bs-note')
    columns = [{'name': key, 'field': key, 'label': label, 'sortable': True,
                **({':format': '(value, row) => row.price_label'} if key == 'price_copper' else {})}
               for key, label in [('price_copper', 'Unit price (gold)'), ('listings', 'Listings'),
                                  ('units', 'Units'), ('cumulative_units', 'Cumulative units')]]
    table_rows = [r | {'price_label': GOLD_TABLE_FORMAT % to_gold(r['price_copper'])} for r in rows]
    ui.table(columns=columns, rows=table_rows, row_key='price_copper', pagination=10).classes(
        'w-full min-w-0').style('max-width:100%;overflow-x:auto').mark('item-ladder-table')


def item_charts(config, item_id):
    with ui.card().classes('bs-card min-w-0').mark('item-history'):
        ui.label('Price history and listing ladder').classes('text-xl font-bold')
        try:
            evidence = item_history.load_history(config, item_id)
        except Exception as error:
            ui.label(f'Unable to read item history: {error}. Use Data to check saved scans, then reopen this item.')
            return
        if evidence['note']:
            ui.label(evidence['note']).classes('bs-note')
            return
        draw_chart(history_options(evidence), 'item-history-chart')
        if len([p for p in evidence['points'] if p['metrics']]) < 2:
            ui.label('More scans with compatible item evidence are needed for a trend.').classes('bs-note')
        if evidence['other_identities']:
            theme.chip(f"Newest scan: {evidence['other_identities']} other identities, excluded")
        ui.label('Listing ladder').classes('text-lg font-bold')
        options = {s['scan_id']: scan_label(s) for s in evidence['scans']}
        picker = ui.select(options, value=evidence['scans'][0]['scan_id'], label='Ladder scan').classes(
            'w-full min-w-0').props('options-dense').mark('item-ladder-scan')
        picker.add_slot('selected-item', '<span style="white-space:normal">{{ props.opt.label }}</span>')
        picker.add_slot('option', '''
            <q-item v-bind="props.itemProps" style="min-height:44px">
              <q-item-section><q-item-label style="white-space:normal">{{ props.opt.label }}</q-item-label>
              </q-item-section>
            </q-item>''')
        area = ui.column().classes('w-full min-w-0')
        def update():
            area.clear()
            with area:
                ladder_panel(config, item_id, evidence, picker.value)
        picker.on_value_change(lambda _: update())
        update()
        ui.label('Units listed are supply, never sales, demand or volume.').classes('bs-note')
