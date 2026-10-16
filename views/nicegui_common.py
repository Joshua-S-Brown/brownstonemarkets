"""Shared tables and freshness help for the surviving native places."""
from nicegui import ui

from views import nicegui_theme as theme
from views import today_rows as tr


def table(rows, *, label, row_key='id'):
    rows = [{**row, 'id': i} for i, row in enumerate(rows)]
    keys = list(dict.fromkeys(key for row in rows for key in row
                              if key != 'id' and not key.endswith('_copper') and not key.startswith('_')))
    decisions = keys

    def columns(selected):
        return [{'name': key, 'label': key, 'field': key, 'sortable': True, 'align': 'left',
                 **({':sort': f'(a, b, rowA, rowB) => {{ const x = rowA["{key}_copper"] ?? Infinity, '
                             f'y = rowB["{key}_copper"] ?? Infinity; return x === y ? 0 : (x < y ? -1 : 1) }}'}
                    if any(key + '_copper' in r for r in rows) else {})}
                for key in selected if key in keys]

    with ui.row():
        search = ui.input(f'Filter {label}').props('dense clearable')
        evidence = ui.switch('Show evidence columns')
    widget = ui.table(columns=columns(decisions), rows=rows, row_key=row_key, pagination=10)
    widget.props('dense flat bordered')
    widget.classes('w-full').mark(label)
    evidence.on_value_change(lambda e: setattr(widget, 'columns', columns(keys if e.value else decisions)))
    search.bind_value_to(widget, 'filter')
    if not rows:
        ui.label('No rows clear these settings with the available evidence.')
    return widget


def freshness_caption(freshness, config, *, banner=True):
    with ui.row().classes('bs-chip'):
        if freshness['stale']:
            theme.badge('Stale', 'warn')
        ui.label(tr.scan_status(freshness))
    if freshness['stale'] and banner:
        scan_banner(freshness)


def scan_banner(freshness):
    theme.banner(tr.stale_banner(freshness), 'How to scan', scan_help)


def scan_help():
    with theme.dialog('How to scan') as popup:
        ui.label('Open the auction house and run /bscan. Wait for the scan to finish, then /reload '
                 'or log out to save the file. Use Data → Import to check for new scans and import.')
        ui.label("Don't /bscan clear until the new scan is imported.")
    popup.on('hide', popup.delete)
    popup.open()
