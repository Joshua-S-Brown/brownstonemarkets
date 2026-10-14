"""Shared, always-light presentation for the main app (UI-08)."""
from contextlib import contextmanager

from nicegui import ui

CSS = '''
:root {
 --ground:#F6F3EF; --surface:#FFFFFF; --ink:#1F1A17; --muted:#5E554F; --faint:#6B625C;
 --line:#E4DDD5; --line-soft:#F0EBE5; --brand:#594235; --brand-dark:#4A362B; --nav-text:#EADFD6;
 --good:#1D5A40; --good-bg:#DDEFE6; --warn:#7A3410; --warn-bg:#FCE5D4;
 --banner:#6E3410; --banner-bg:#FFF3E6; --banner-line:#F2C9A5; --neutral-bg:#EFE9E3;
 color-scheme:light;
}
body,.q-page {background:var(--ground);color:var(--ink);font-family:Manrope,system-ui,sans-serif}
body {user-select:text} .q-layout__section--marginal {background:var(--brand);color:white}
.q-header {box-shadow:none} .bs-bar {max-width:1200px;margin:auto;width:100%;padding:12px 24px;
 gap:16px;align-items:center;flex-wrap:wrap}
.bs-brand {font-size:18px;font-weight:800} .bs-nav {flex:1;gap:4px;flex-wrap:wrap}
.bs-nav .q-btn {color:var(--nav-text)!important;border-radius:8px;padding:0 14px}
.bs-nav .selected {background:#ffffff29;color:white!important}
.bs-source {font-size:13px;color:var(--nav-text)!important}
.bs-icon {color:white!important;border:1px solid #ffffff40;border-radius:10px;width:44px;height:44px}
.bs-main {max-width:1200px;margin:auto;width:100%;padding:32px 24px 64px;gap:24px}
.bs-title {font-size:34px;font-weight:800;line-height:1.2} .bs-question {color:var(--muted);font-size:15px}
.q-btn {min-height:44px;text-transform:none;border-radius:10px;font-weight:600}
.q-field {min-height:44px} .q-card {box-shadow:none;border:1px solid var(--line);border-radius:16px;
 background:var(--surface)} .bs-card {padding:20px 22px;gap:14px;width:100%}
.bs-chip {display:inline-flex;align-items:center;gap:8px;padding:8px 14px;border-radius:999px;
 background:var(--surface);border:1px solid var(--line);font-weight:600;color:#3A322D}
.bs-badge {padding:3px 10px;border-radius:999px;font-size:12px;font-weight:700;letter-spacing:.02em}
.bs-good {background:var(--good-bg);color:var(--good)} .bs-warn {background:var(--warn-bg);color:var(--warn)}
.bs-neutral {background:var(--neutral-bg);color:#4A3A30}
.bs-banner {padding:14px 18px;border-radius:12px;background:var(--banner-bg);border:1px solid var(--banner-line);
 color:var(--banner);align-items:center;gap:14px;width:100%}
.bs-tiles {display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;width:100%}
.bs-tile {padding:18px 20px;gap:6px} .bs-label {font-size:12px;font-weight:700;letter-spacing:.06em;
 text-transform:uppercase;color:var(--faint)} .bs-big {font-size:28px;font-weight:800;font-variant-numeric:tabular-nums}
.bs-profit {color:var(--good)} .bs-note {font-size:13px;color:var(--faint)}
.bs-tabs .q-tabs__content {justify-content:flex-start}
.bs-tabs {width:100%;border-bottom:1px solid var(--line);color:var(--faint)}
.q-tab {text-transform:none}
.q-tab-panels {background:transparent;width:100%}
.q-tab-panel {padding:0;display:flex;flex-direction:column;gap:14px}
.q-table__container {border:1px solid var(--line);border-radius:16px;background:white}
.q-table th {color:var(--faint);font-size:12px;text-transform:uppercase;font-weight:700}
.q-table td {font-size:14px} .q-table tbody td {height:48px}
.bs-settings-grid {display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;width:100%}
.bs-dialog {width:640px;max-width:calc(100vw - 48px)!important;padding:26px 28px;gap:16px}
.bs-empty {padding:48px 32px;align-items:center;text-align:center;gap:14px}
.bs-empty .bs-sentence {max-width:560px;line-height:1.6;font-size:15px;color:#4A413B}
.bs-roster {display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;width:100%}
.bs-person {cursor:pointer;padding:20px;gap:12px;width:100%} .bs-person.selected {border:2px solid var(--brand)}
.bs-next {padding:10px 12px;border-radius:10px;background:var(--ground);font-size:14px;width:100%}
.q-checkbox,.q-toggle,.q-slider {min-height:44px}
.bs-dialog,.bs-card {overflow-wrap:anywhere}
.bs-details {display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:20px;width:100%}
.q-expansion-item {width:100%} .q-item {min-height:44px} .q-linear-progress {color:var(--brand)}
'''


def install():
    ui.dark_mode(False)
    ui.colors(primary='#594235', secondary='#5E554F', positive='#1D5A40', warning='#7A3410')
    ui.add_css(CSS)


def chip(text, *, on_click=None):
    if on_click:
        return ui.button(text, on_click=on_click).props('flat').classes('bs-chip')
    return ui.label(text).classes('bs-chip')


def badge(text, tone='neutral'):
    return ui.label(text).classes('bs-badge bs-' + tone)


def tile(label, value, *, profit=False, note=None, compact=False):
    with ui.card().classes('bs-tile'):
        ui.label(label).classes('bs-label')
        ui.label(value).classes(('text-xl font-extrabold' if compact else 'bs-big') +
                                (' bs-profit' if profit else ''))
        if note:
            ui.label(note).classes('bs-note')


@contextmanager
def dialog(title):
    with ui.dialog() as popup, ui.card().classes('bs-dialog'):
        with ui.row().classes('w-full items-center justify-between'):
            ui.label(title).classes('text-xl font-bold')
            ui.button('Close', on_click=popup.close).props('flat')
        yield popup


def info_button(title, on_click):
    buttons = [e for e in ui.context.client.elements.values() if 'page-info' in e._markers]
    if buttons:
        button = buttons[0]
        button.on_click(on_click)
        button.props(f'aria-label="{title}"')
        button.tooltip(title)
    else:
        ui.button(title, on_click=on_click).props('flat')


def settings_button(on_click):
    buttons = [e for e in ui.context.client.elements.values() if 'page-settings' in e._markers]
    if buttons:
        buttons[0].set_visibility(True)
        buttons[0].on_click(on_click)
    else:
        ui.button('Today settings', on_click=on_click)


def empty(sentence, settings, reasons):
    with ui.card().classes('bs-card bs-empty').mark('empty-plan'):
        ui.icon('search', size='40px').classes('bs-note')
        ui.label('No craft clears your settings today').classes('text-xl font-bold')
        ui.label(sentence).classes('bs-sentence')
        with ui.row().classes('justify-center'):
            ui.button('Review settings', on_click=settings)
            ui.button('See all reasons', on_click=reasons).props('outline')


def source_info(config):
    with dialog('Source details') as popup:
        ui.label(f"source {config['source_id']} · market {config['market_id']} · {config['provider']} feed")
        ui.label('Configure sources in config/market.toml')
    popup.on('hide', popup.delete)
    popup.open()


def banner(text, action_label, on_click):
    with ui.row().classes('bs-banner'):
        ui.icon('warning')
        ui.label(text).classes('flex-1')
        ui.button(action_label, on_click=on_click).props('flat')


def farming_table(widget):
    """Use the shared table treatment for the per-character farming comparison."""
    widget.props('dense flat bordered').mark('farming-spots')
