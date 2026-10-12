"""Optional loopback-only Today trial. Run: python nicegui_app.py."""
import argparse
import json
import os
import secrets
from pathlib import Path
from urllib.parse import urlencode

from nicegui import app, ui

from brownstone import config as configuration
from brownstone import recipe_catalogs
from brownstone.crafting import parse_recipe_catalog
from brownstone.today_loading import load_today_characters
from views.nicegui_today import render

ROOT = Path(__file__).resolve().parent
EXPERIENCES = {"forever": "WoW Forever", "classic": "Classic Era", "retail": "Retail (regression)"}


def read_catalogs():
    catalogs = []
    for entry in recipe_catalogs.find_catalogs(recipe_catalogs.CONFIG_DIR):
        if entry["catalog"]:
            try:
                catalogs.append({**parse_recipe_catalog(entry["catalog"]), "catalog_id": entry["name"]})
            except Exception as error:
                ui.label(f"Recipe catalog {entry['name']} unavailable: {error}")
    return catalogs


@ui.page('/')
async def today_page(game: str = '', source: str = '', tab: str = 'Craft'):
    ui.colors(primary='#594235', secondary='#8b7355', accent='#42766b')
    with ui.header():
        ui.label('Brownstone Markets · Today')
    try:
        sources = [s for s in configuration.read_sources(ROOT / 'config/market.toml',
                   ROOT / 'config' / configuration.LOCAL_OVERRIDES) if s['enabled']]
    except Exception as error:
        ui.label(f'Could not read configuration: {error}')
        return
    if not sources:
        ui.label('No enabled data source.')
        return
    order = list(EXPERIENCES)
    games = sorted({s['game_version'] for s in sources},
                   key=lambda g: order.index(g) if g in order else len(order))
    selected_game = game if game in games else games[0]
    options = [s for s in sources if s['game_version'] == selected_game]
    chosen = next((s for s in options if s['source_id'] == source), options[0] if len(options) == 1 else None)
    with ui.left_drawer():
        ui.select({g: EXPERIENCES.get(g, g) for g in games}, value=selected_game, label='Experience',
                  on_change=lambda e: ui.navigate.to('/?' + urlencode({'game': e.value})))
        if len(options) > 1:
            ui.select({s['source_id']: s.get('label', s['source_id']) for s in options},
                      value=chosen['source_id'] if chosen else None, label='Data source',
                      on_change=lambda e: ui.navigate.to('/?' + urlencode({'game': selected_game, 'source': e.value})))
        with ui.expansion('Source details'):
            if chosen:
                ui.label(f"Source {chosen['source_id']} · market {chosen['market_id']} · {chosen['provider']} feed")
            ui.label('Configure sources in config/market.toml')
    if chosen is None:
        ui.label('This experience has several enabled sources. Choose one above.')
        return
    ui.label(f"Showing {EXPERIENCES.get(selected_game, selected_game)} · "
             f"source {chosen.get('label', chosen['source_id'])} · market {chosen['market_id']}")
    ui.label('What should I craft, buy and sell today?')
    character_data, warning = load_today_characters(chosen)
    if warning:
        ui.label(warning)
    await ui.context.client.connected()
    render(chosen, read_catalogs(), character_data, tab)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8081)
    parser.add_argument('--data-dir', type=Path, help='Use a copied data directory for the trial')
    parser.add_argument('--native', action='store_true', help='Open a desktop window on a free loopback port')
    parser.add_argument('--ready-file', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--focus-token', default='', help=argparse.SUPPRESS)
    args = parser.parse_args([] if os.environ.get('NICEGUI_USER_SIMULATION') else argv)
    if args.data_dir:
        original = configuration.read_sources

        def sources(*arguments):
            return [{**s, 'data_dir': args.data_dir.resolve()} for s in original(*arguments)]

        configuration.read_sources = sources
    configure_launch(args)
    ui.run(host='127.0.0.1', port=None if args.native else args.port, native=args.native,
           window_size=(1280, 900), reload=False, show=False,
           title='Brownstone Markets', show_welcome_message=False)


def configure_launch(args):
    def ready():
        if args.ready_file:
            # Write then rename, so the launcher polling for this file never reads it half-written.
            partial = args.ready_file.with_suffix('.tmp')
            partial.write_text(json.dumps({'url': f"http://127.0.0.1:{os.environ['NICEGUI_PORT']}",
                                           'token': args.focus_token, 'native': args.native}), encoding='utf-8')
            partial.replace(args.ready_file)

    if args.native:
        app.native.on('loaded', ready)
    else:
        app.on_startup(ready)

    @app.post('/_trial/focus')
    def focus(token: str = ''):
        if not args.focus_token or not secrets.compare_digest(token, args.focus_token):
            return {'focused': False}
        if app.native.main_window is not None:
            app.native.main_window.restore()
            app.native.main_window.show()
            return {'focused': True}
        return {'focused': False}


if __name__ == '__main__':
    main()
