"""Brownstone Markets, the loopback-only main app. Run: python nicegui_app.py."""
import argparse
import json
import os
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode

from nicegui import Client, app, ui

from brownstone import config as configuration
from brownstone import pipeline, recipe_catalogs
from brownstone.navigation import EXPERIENCES, QUESTIONS, experiences
from brownstone.today_loading import load_today_characters
from views.nicegui_import import render as render_import
from views.nicegui_team import render as render_team
from views.nicegui_today import render

ROOT = Path(__file__).resolve().parent


def read_catalogs():
    catalogs, errors = recipe_catalogs.parse_catalogs(recipe_catalogs.find_catalogs(recipe_catalogs.CONFIG_DIR))
    for message in errors:
        ui.label(message)
    return catalogs


@ui.page('/')
async def today_page(game: str = '', source: str = '', tab: str = 'Craft', place: str = 'Today'):
    place = place if place in ('Today', 'Team', 'Market', 'Data') else 'Today'
    ui.colors(primary='#594235', secondary='#8b7355', accent='#42766b')
    with ui.header():
        menu = ui.button(icon='menu').props('flat aria-label="Open navigation"')
        ui.label('Brownstone Markets')
    try:
        sources = [s for s in configuration.read_sources(ROOT / 'config/market.toml',
                   ROOT / 'config' / configuration.LOCAL_OVERRIDES) if s['enabled']]
    except Exception as error:
        ui.label(f'Could not read configuration: {error}')
        return
    if not sources:
        ui.label('No enabled data source.')
        return
    chosen, selected_game, drawer = sidebar(sources, game, source, place, tab)
    menu.on_click(drawer.toggle)
    if chosen is None:
        await ui.context.client.connected()
        app.storage.tab['import-identity'] = None
        app.storage.tab['import-review'] = {}
        ui.label('This experience has several enabled sources. Choose one above.')
        return
    ui.label(place).classes('text-h4')
    ui.label(QUESTIONS[place])
    ui.label(f"Showing {EXPERIENCES.get(selected_game, selected_game)} · "
             f"source {chosen.get('label', chosen['source_id'])} · market {chosen['market_id']}")
    await ui.context.client.connected()
    # Switching sources, including TSM, invalidates any active addon review.
    identity = pipeline.preview_configuration(chosen) if chosen['provider'] == 'addon' else None
    if app.storage.tab.get('import-identity') != identity:
        app.storage.tab['import-identity'] = identity
        app.storage.tab['import-review'] = {}
    if place == 'Data':
        ui.label('Import').classes('text-h5')
        ui.label(QUESTIONS['Import'])
        render_import(chosen)
        return
    if place == 'Team':
        render_team(chosen, read_catalogs())
        return
    if place == 'Market':
        ui.label('Materials, crafts, supply chains and scan changes are coming in STORY-055.')
        return
    ui.label(QUESTIONS['Today plan'])
    character_data, warning = load_today_characters(chosen)
    if warning:
        ui.label(warning)
    render(chosen, read_catalogs(), character_data, tab)


def sidebar(sources, game, source, place, tab):
    games = experiences(sources)
    selected_game = game if game in games else games[0]
    options = [s for s in sources if s['game_version'] == selected_game]
    chosen = next((s for s in options if s['source_id'] == source), options[0] if len(options) == 1 else None)
    def navigate(**changes):
        values = {'game': selected_game, 'source': chosen['source_id'] if chosen else '',
                  'place': place, 'tab': app.storage.tab.get('today-active-tab', tab)}
        values.update(changes)
        ui.navigate.to('/?' + urlencode(values))

    with ui.left_drawer() as drawer:
        ui.select({g: EXPERIENCES.get(g, g) for g in games}, value=selected_game, label='Experience',
                  on_change=lambda e: navigate(game=e.value, source=''))
        if len(options) > 1:
            ui.select({s['source_id']: s.get('label', s['source_id']) for s in options},
                      value=chosen['source_id'] if chosen else None, label='Data source',
                      on_change=lambda e: navigate(source=e.value))
        for name in ('Today', 'Team', 'Market', 'Data'):
            if name == 'Data':
                ui.separator().classes('my-3')
            ui.button(name, on_click=lambda n=name: navigate(place=n)).props(
                'flat' if name != place else 'unelevated').classes('w-full').mark('place-' + name)
        with ui.expansion('Source details'):
            if chosen:
                ui.label(f"Source {chosen['source_id']} · market {chosen['market_id']} · {chosen['provider']} feed")
            ui.label('Configure sources in config/market.toml')
    return chosen, selected_game, drawer


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
    configure_launch(args)
    ui.run(host='127.0.0.1', port=None if args.native else args.port, native=args.native,
           window_size=(1280, 900) if args.native else None, reload=False, show=False,
           title='Brownstone Markets', show_welcome_message=False)


def configure_launch(args):
    def ready():
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
