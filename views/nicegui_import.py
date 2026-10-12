"""Explicit, read-only addon review and import in the main app."""
from nicegui import app, ui

from brownstone import import_review as review
from brownstone import pipeline, scan_inputs
from views.nicegui_today import watchlist_hits


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
    with ui.expansion('Imported character data').classes('w-full'):
        for label, rows in review.holdings_sections(config):
            if rows:
                ui.label(label)
                rows_table(rows, label)


def render(config):
    if config['provider'] != 'addon':
        ui.label("Use the old app's Refresh from TSM for this source.")
        return
    ImportPage(config)


class ImportPage:
    def __init__(self, config):
        # nicegui_app discards the review whenever the source identity changes, on every place.
        state = app.storage.tab.setdefault('import-review', {})
        self.config, self.state = config, state
        self.area = ui.column().classes('w-full')
        self.update()

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
            holdings(config)
            ui.button('Preview addon scans', on_click=self.preview)
            messages = state.get('messages', [])
            for kind, message in messages:
                if kind != 'info':
                    ui.label(message).classes('text-negative' if kind == 'error' else '')
            if any(kind == 'success' for kind, _ in messages):
                watchlist_hits(config, [])
            reviewed = state.get('preview')
            if reviewed is None:
                if any(kind == 'info' for kind, _ in messages):
                    with ui.expansion('Details'):
                        detail_messages(messages)
                return
            if config.get('drop_folder'):
                input_review(reviewed, state, self.collect, self.selection, messages)
            else:
                single_review(config, reviewed, state, self.collect, self.selection, messages)


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
        ui.button('Import addon scan', on_click=collect)
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
        ui.button('Import addon scan', on_click=collect)
    if messages:
        for line in review.clear_lines(preview):
            ui.label(line)
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
