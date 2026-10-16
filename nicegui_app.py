"""Brownstone Markets, the loopback-only main app. Run: python nicegui_app.py."""
import argparse
import json
import os
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode

from nicegui import Client, app, ui

from api import install as install_web
from brownstone import config as configuration
from brownstone import pipeline, recipe_catalogs
from brownstone.navigation import EXPERIENCES, QUESTIONS, experiences, source_label
from brownstone.today_loading import load_today_characters
from views import nicegui_theme as theme
from views.nicegui_import import render as render_import
from views.nicegui_market import render as render_market
from views.nicegui_navigation import back_link, read_origin
from views.nicegui_stock import render as render_stock
from views.nicegui_team import render as render_team
from views.nicegui_today import render

ROOT = Path(__file__).resolve().parent
install_web(app, ROOT / "web/dist")


def web_warning():
    if os.environ.get("BROWNSTONE_WEB_WARNING"):
        ui.label(os.environ["BROWNSTONE_WEB_WARNING"]).classes("bs-note")


def read_catalogs():
    catalogs, errors = recipe_catalogs.parse_catalogs(recipe_catalogs.find_catalogs(recipe_catalogs.CONFIG_DIR))
    for message in errors:
        ui.label(message)
    return catalogs


@ui.page('/')
async def today_page(game: str = '', source: str = '', tab: str = 'Craft', place: str = 'Today',
                     item: int | None = None, view: str = '', origin_place: str = '', origin_tab: str = '',
                     origin_view: str = '', origin_item: str = '', origin_name: str = ''):
    place = place if place in ('Today', 'Team', 'Market', 'Stock', 'Data') else 'Today'
    theme.install()
    web_warning()
    try:
        sources = [s for s in configuration.read_sources(ROOT / 'config/market.toml',
                   ROOT / 'config' / configuration.LOCAL_OVERRIDES) if s['enabled']]
    except Exception as error:
        ui.label(f'Could not read configuration: {error}')
        return
    if not sources:
        ui.label('No enabled data source.')
        return
    chosen, selected_game = header(sources, game, source, place, tab)
    if chosen is None:
        await ui.context.client.connected()
        app.storage.tab['import-identity'] = None
        app.storage.tab['import-review'] = {}
        ui.label('This experience has several enabled sources. Choose one above.')
        return
    ui.context.client.content.classes('bs-main')
    origin = read_origin(origin_place, origin_tab, origin_view, origin_item, origin_name)
    back_link(chosen, origin if place in ('Market', 'Team') else {})
    with ui.column().classes('gap-1'):
        ui.label(place).classes('bs-title')
        ui.label(QUESTIONS[place]).classes('bs-question')
    # The web app (UI-18) grows beside these pages; the native window has no address bar to reach it.
    ui.link('Open the new app (preview) →', '/app?' + urlencode({'source': chosen['source_id']})).mark('web-app')
    await ui.context.client.connected()
    # Switching sources, including TSM, invalidates any active addon review.
    identity = pipeline.preview_configuration(chosen) if chosen['provider'] == 'addon' else None
    if app.storage.tab.get('import-identity') != identity:
        app.storage.tab['import-identity'] = identity
        app.storage.tab['import-review'] = {}
    if place == 'Data':
        render_import(chosen)
        return
    if place == 'Team':
        render_team(chosen, read_catalogs())
        return
    if place == 'Stock':
        render_stock(chosen, read_catalogs())
        return
    if place == 'Market':
        render_market(chosen, read_catalogs(), item, origin)
        return
    character_data, warning = load_today_characters(chosen)
    if warning:
        ui.label(warning)
    render(chosen, read_catalogs(), character_data, tab, view)


def header(sources, game, source, place, tab):
    games = experiences(sources)
    selected_game = game if game in games else games[0]
    options = [s for s in sources if s['game_version'] == selected_game]
    chosen = next((s for s in options if s['source_id'] == source), options[0] if len(options) == 1 else None)
    def navigate(**changes):
        values = {'game': selected_game, 'source': chosen['source_id'] if chosen else '',
                  'place': place, 'tab': app.storage.tab.get('today-active-tab', tab)}
        if chosen and 'source' not in changes:  # a new source keeps its own saved view
            values['view'] = app.storage.tab.get('today-plan-' + chosen['source_id'], {}).get('view', 'Today plan')
        values.update(changes)
        ui.navigate.to('/?' + urlencode(values))

    with ui.header().classes('p-0'), ui.row().classes('bs-bar'):
        ui.label('Brownstone').classes('bs-brand')
        with ui.row().classes('bs-nav'):
            for name in ('Today', 'Team', 'Market', 'Stock', 'Data'):
                if name == 'Data':
                    ui.separator().props('vertical').classes('mx-2')
                ui.button(name, color=None, on_click=lambda n=name: navigate(place=n)).props('flat').classes(
                    'selected' if name == place else '').mark('place-' + name)
        with ui.row().classes('items-center gap-2'):
            with ui.button(source_label(chosen) if chosen else 'Choose source', color=None).props(
                    'flat').classes('bs-source'), ui.menu():
                ui.select({g: EXPERIENCES.get(g, g) for g in games}, value=selected_game, label='Experience',
                          on_change=lambda e: navigate(game=e.value, source=''))
                if len(options) > 1:
                    ui.select({s['source_id']: s.get('label', s['source_id']) for s in options},
                              value=chosen['source_id'] if chosen else None, label='Data source',
                              on_change=lambda e: navigate(source=e.value))
            ui.button(icon='info_outline', color=None).props('flat aria-label="Page information"').classes(
                'bs-icon').mark('page-info')
            ui.button(icon='settings', color=None).props('flat aria-label="Today settings"').classes(
                'bs-icon').mark('page-settings').set_visibility(False)
    return chosen, selected_game


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8081)
    parser.add_argument('--data-dir', type=Path, help='Use a copied data directory')
    parser.add_argument('--native', action='store_true', help='Open a desktop window on a free loopback port')
    parser.add_argument('--ready-file', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--focus-token', default='', help=argparse.SUPPRESS)
    parser.add_argument('--code-fingerprint', default='', help=argparse.SUPPRESS)
    args = parser.parse_args([] if os.environ.get('NICEGUI_USER_SIMULATION') else argv)
    if args.data_dir:
        original = configuration.read_sources

        def sources(*arguments):
            return [{**s, 'data_dir': args.data_dir.resolve()} for s in original(*arguments)]

        configuration.read_sources = sources
    app.native.window_args['text_select'] = True
    configure_launch(args)
    ui.run(host='127.0.0.1', port=None if args.native else args.port, native=args.native,
           window_size=(1280, 900) if args.native else None, reload=False, show=False,
           title='Brownstone Markets', show_welcome_message=False)


def configure_launch(args):
    activated = []

    def ready():
        # macOS opens the window without making it the active, key window, so clicks were dropped until the
        # owner switched away and back (2026-10-13). Activate it once, after its first page has loaded.
        if args.native and not activated and app.native.main_window is not None:
            activated.append(True)
            app.native.main_window.show()
        if args.ready_file:
            # Write then rename, so the launcher polling for this file never reads it half-written.
            partial = args.ready_file.with_suffix('.tmp')
            partial.write_text(json.dumps({'url': f"http://127.0.0.1:{os.environ['NICEGUI_PORT']}",
                                           'token': args.focus_token, 'native': args.native,
                                           'code': args.code_fingerprint}), encoding='utf-8')
            partial.replace(args.ready_file)

    if args.native:
        app.native.on('loaded', ready)
    else:
        app.on_startup(ready)
        idle = BrowserIdle()
        app.on_startup(lambda: app.timer(10, idle.check))

    @app.post('/_brownstone/stop')
    async def stop(token: str = ''):
        if not args.focus_token or not secrets.compare_digest(token, args.focus_token):
            return {'stopping': False}
        # Let the response leave before stopping the server, including native window handling.
        app.timer(.1, app.shutdown, once=True)
        return {'stopping': True}

    @app.post('/_brownstone/focus')
    def focus(token: str = ''):
        if not args.focus_token or not secrets.compare_digest(token, args.focus_token):
            return {'focused': False}
        if app.native.main_window is not None:
            app.native.main_window.restore()
            app.native.main_window.show()
            return {'focused': True}
        return {'focused': False}


class BrowserIdle:
    """Stop browser fallback after five minutes without any connected tab."""

    def __init__(self):
        self.disconnected_since = time.monotonic()

    def check(self):
        if any(client.has_socket_connection for client in Client.instances.values()):
            self.disconnected_since = None
        elif self.disconnected_since is None:
            self.disconnected_since = time.monotonic()
        elif time.monotonic() - self.disconnected_since >= 300:
            app.shutdown()



if __name__ == '__main__':
    main()
