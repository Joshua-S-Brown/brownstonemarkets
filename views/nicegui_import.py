"""Explicit, read-only addon review and import in the main app."""
from datetime import UTC, datetime

import duckdb
from nicegui import app, ui

from brownstone import import_review as review
from brownstone import pipeline, scan_inputs
from brownstone.watchlist import hit_text, known_names, load_entries, read_watchlist, watchlist_path
from views import nicegui_theme as theme


def rows_table(rows, label):
    if not rows:
        return
    keys = list(dict.fromkeys(key for row in rows for key in row))
    ui.table(columns=[{'name': k, 'label': k, 'field': k, 'align': 'left'} for k in keys],
             rows=[{**row, '_row': i} for i, row in enumerate(rows)], row_key='_row',
             pagination=10).classes('w-full').props('dense flat bordered').mark(label)


def show_preview(preview, machine=None, drop_time=None):
    for label, rows in review.preview_sections(preview, machine, drop_time):
        rows_table(rows, label)
    for note in review.preview_notes(preview):
        ui.label(note)


def holdings(config):
    with ui.expansion("What's imported").classes('w-full'):
        for label, rows in review.holdings_sections(config):
            if rows:
                ui.label(label)
                rows_table(rows, label)


def render(config):
    if config['provider'] != 'addon':
        theme.info_button('Source details', lambda: theme.source_info(config))
        ui.label(f"Refresh this source with: python -m brownstone --source {config['source_id']}")
        return
    ImportPage(config)


class ImportPage:
    def __init__(self, config):
        # nicegui_app discards the review whenever the source identity changes, on every place.
        state = app.storage.tab.setdefault('import-review', {})
        self.config, self.state = config, state
        self.area = ui.column().classes('w-full')
        theme.info_button('Import details', self.info)
        self.update()

    def info(self):
        with theme.dialog('Import details') as popup:
            for key in ('source_id', 'market_id', 'scan_path', 'machine', 'drop_folder'):
                ui.label(f'{key}: {self.config.get(key, "not configured")}')
            ui.label('Partial scans are preserved but never feed prices. Reads use best-effort change detection. '
                     'If the drop folder is still syncing, check again in a minute.')
        popup.on('hide', popup.delete)
        popup.open()

    def preview(self):
        config, state = self.config, self.state
        state.clear()
        try:
            state['preview'] = (scan_inputs.preview_inputs(config) if config.get('drop_folder')
                                else pipeline.preview_scans(config))
        except Exception as error:
            state['messages'] = review.preview_failure(error)
        self.update()

    def collect(self):
        config, state = self.config, self.state
        reviewed = state.pop('preview', None)
        selected = state.pop('selected', [])
        state.pop('details', None)
        try:
            if config.get('drop_folder'):
                results = scan_inputs.import_inputs(config, reviewed, selected)
                state['messages'] = review.file_messages(results)
                state['preview'] = scan_inputs.preview_inputs(config)
            else:
                manifest = pipeline.import_scans(config, scan_ids=selected, reviewed=reviewed)
                state['messages'] = review.import_messages(config, manifest)
        except pipeline.StalePreviewError as error:
            state['messages'] = review.import_failure(error, stale=True)
        except Exception as error:
            state['messages'] = review.import_failure(error, drops=bool(config.get('drop_folder')))
        self.update()

    def selection(self, event):
        self.state['selected'] = event.value
        self.update()

    def update(self):
        config, state, area = self.config, self.state, self.area
        area.clear()
        with area:
            with ui.row().classes('gap-3'):
                for text in review.status_chips(config, state.get('preview')):
                    theme.chip(text)
            with ui.card().classes('bs-card'), ui.row().classes('w-full items-center justify-between'):
                with ui.column().classes('gap-2 flex-1 min-w-64'):
                    ui.label('Bring in new scans').classes('text-xl font-bold')
                    ui.label("Reads this Mac's game file and the drop folder. "
                             'Nothing is saved until you choose Import.')
                ui.button('Check for new scans', on_click=self.preview)
            messages = state.get('messages', [])
            for kind, message in messages:
                if kind != 'info':
                    ui.label(message).classes('text-negative' if kind == 'error' else '')
            if any(kind == 'success' for kind, _ in messages):
                watchlist_hits(config, [])
            reviewed = state.get('preview')
            if reviewed is None:
                holdings(config)
                if any(kind == 'info' for kind, _ in messages):
                    with ui.expansion('Details'):
                        detail_messages(messages)
                return
            with ui.card().classes('bs-card'):
                new = bool(reviewed.new_files) if config.get('drop_folder') else bool(
                    reviewed.new_ids or reviewed.new_record_ids)
                with ui.row().classes('items-center'):
                    theme.badge('New' if new else 'Up to date', 'warn' if new else 'good')
                    ui.label('New evidence waiting' if new else 'Nothing new for this source').classes(
                        'text-xl font-bold')
                if config.get('drop_folder'):
                    input_review(reviewed, state, self.collect, self.selection, messages)
                else:
                    single_review(config, reviewed, state, self.collect, self.selection, messages)
            holdings(config)


def detail_messages(messages):
    for kind, message in messages:
        if kind == 'info':
            ui.label(message)


def details(state, problems, messages):
    if problems or any(kind == 'error' for kind, _ in messages):
        state['details'] = True
    if problems:
        ui.label('; '.join(problems)).classes('text-warning')
    return ui.expansion('Details', value=state.get('details', False),
                        on_value_change=lambda e: state.update(details=e.value)).classes('w-full')


def single_review(config, preview, state, collect, selection, messages):
    default = preview.new_ids
    selected = state.setdefault('selected', default)
    ui.label(review.summary(preview, config.get('machine')))
    problems = review.scan_problems(preview)
    if set(selected) != set(default):
        problems.append('Selection differs from the default')
    if selected or preview.new_record_ids:
        ui.button('Import', on_click=collect).mark('import-action')
    with details(state, problems, messages):
        detail_messages(messages)
        show_preview(preview, config.get('machine'))
        if preview.new_ids or preview.new_record_ids:
            ui.select(default, value=selected, multiple=True, label='New scans to import',
                      on_change=selection).classes('w-full')
            if preview.new_record_ids:
                ui.label('All new matching character records in this file will also be imported.')


def input_review(preview, state, collect, selection, messages):
    selected = state.setdefault('selected', preview.new_files)
    lines, problems = review.input_summary(preview, selected)
    for line in lines:
        ui.label(line)
    if set(selected) != set(preview.new_files):
        problems.append('Selection differs from the default')
    if selected:
        ui.button('Import', on_click=collect).mark('import-action')
    for line in review.file_status_lines(preview):
        ui.label(line).classes('bs-note')
    for line in review.clear_lines(preview):
        theme.chip(line)
    with details(state, problems, messages):
        detail_messages(messages)
        rows_table(scan_inputs.file_rows(preview), 'Files')
        for file in preview.files:
            if file.preview:
                ui.label(f'{file.path.name} — machine: {file.machine}; drop UTC: {file.drop_time or "local file"}')
                show_preview(file.preview, file.machine, file.drop_time)
        rows_table(scan_inputs.latest_rows(preview), 'Latest drops')
        ui.label(scan_inputs.CLEAR_REMINDER)
        choices = [str(f.path) for f in preview.files if f.matching_ids or f.matching_records]
        if choices:
            ui.select(choices, value=selected, multiple=True, label='Files to import (each archived separately)',
                      on_change=selection).classes('w-full')


def watchlist_hits(config, catalogs):
    try:
        entries = load_entries(watchlist_path(config['data_dir'], config['source_id']))
        if not entries:
            return
        with duckdb.connect(str(config['data_dir'] / 'brownstone.duckdb'), read_only=True) as db:
            result = read_watchlist(db, config, entries, datetime.now(UTC))
            names = known_names(db, config, catalogs)
        hits = [r for r in result['rows'] if r['buy_hit'] or r['sell_hit']]
        if hits:
            with ui.expansion(f'Watchlist hits ({len(hits)})', value=True):
                for row in hits:
                    ui.label(hit_text(row, names))
    except Exception as error:
        ui.label(f'Watchlist evidence unavailable: {error}')
