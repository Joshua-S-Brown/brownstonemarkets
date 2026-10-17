"""Brownstone Markets, the loopback-only app. Run: python brownstone_app.py."""
import argparse
import asyncio
import json
import os
import secrets
import socket
import threading
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from urllib.parse import urlencode

import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from api import context, install
from api.presence import connected
from brownstone import config as configuration

ROOT = Path(__file__).resolve().parent


def legacy_url(source='', place='Today', item=None, view='', tab='Craft', origin_place='',
               origin_tab='', origin_view='', origin_item='', origin_name=''):
    try:
        known = any(s['source_id'] == source for s in context.enabled())
    except (OSError, ValueError):  # The web app explains an unreadable config.
        known = False
    if not source or not known:
        return '/app/today'
    values = {'source': source}
    target = {'Market': 'market', 'Team': 'team', 'Stock': 'ledger'}.get(place, 'today')
    if place == 'Market':
        if item is not None:
            values['inspect'] = item
        if (origin_place == 'Today' and origin_tab in ('Plan', 'Shopping list', 'Sell', 'Queue', 'Extras')
                and origin_view in ('Today plan', 'This session')):
            values.update(origin_place=origin_place, origin_tab=origin_tab, origin_view=origin_view)
        elif (origin_place == 'Market' and origin_item.isascii() and origin_item.isdecimal()
              and len(origin_item) <= 10 and 0 < int(origin_item) < 2**32 and origin_name.strip()):
            values.update(origin_place=origin_place, origin_item=origin_item, origin_name=origin_name[:200])
    elif place == 'Data':
        values['sheet'] = 'data'
    elif target == 'today':
        values['view'] = view if view in ('route', 'opportunities', 'level-up') else (
            'level-up' if view == 'This session' else
            'opportunities' if view == 'Today plan' and tab in ('Craft', 'Plan') else 'route')
    return '/app/' + target + '?' + urlencode(values)


class BrowserIdle:
    """Stop browser fallback after five minutes without any connected tab."""

    def __init__(self, shutdown):
        self.shutdown = shutdown
        self.disconnected_since: float | None = time.monotonic()

    def check(self):
        if connected:
            self.disconnected_since = None
        elif self.disconnected_since is None:
            self.disconnected_since = time.monotonic()
        elif time.monotonic() - self.disconnected_since >= 300:
            self.shutdown()

    async def watch(self):
        """Poll presence on the browser server lifecycle."""
        while True:
            await asyncio.sleep(10)
            self.check()


def launch_lifespan(app, args, url):
    activated = False
    app.state.window = None

    def shutdown():
        app.state.server.should_exit = True
        if app.state.window is not None:
            app.state.window.destroy()

    def ready():
        nonlocal activated
        if activated:
            return
        activated = True
        # Activate once after first load: macOS otherwise dropped clicks until switching apps (2026-10-13).
        if app.state.window is not None:
            app.state.window.show()
        if args.ready_file:
            partial = args.ready_file.with_suffix('.tmp')
            partial.write_text(json.dumps({'url': url, 'token': args.focus_token, 'native': args.native,
                                           'code': args.code_fingerprint}), encoding='utf-8')
            partial.replace(args.ready_file)

    @asynccontextmanager
    async def lifespan(app):
        if args.native:
            yield
            return
        ready()
        task = asyncio.create_task(BrowserIdle(shutdown).watch())
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    app.state.ready = ready
    app.state.shutdown = shutdown
    return lifespan


def configure_launch(args, url):
    app = FastAPI()
    app.router.lifespan_context = launch_lifespan(app, args, url)
    install(app, ROOT / 'web/dist', args.focus_token)

    @app.get('/', include_in_schema=False)
    def redirect(source: str = '', place: str = 'Today', item: int | None = None, view: str = '',
                 tab: str = 'Craft', origin_place: str = '', origin_tab: str = '', origin_view: str = '',
                 origin_item: str = '', origin_name: str = ''):
        return RedirectResponse(legacy_url(source, place, item, view, tab, origin_place, origin_tab,
                                           origin_view, origin_item, origin_name))

    @app.post('/_brownstone/stop', include_in_schema=False)
    async def stop(token: str = ''):
        allowed = bool(args.focus_token and secrets.compare_digest(token, args.focus_token))
        if allowed:
            asyncio.get_running_loop().call_later(.1, app.state.shutdown)
        return {'stopping': allowed}

    @app.post('/_brownstone/focus', include_in_schema=False)
    def focus(token: str = ''):
        if not args.focus_token or not secrets.compare_digest(token, args.focus_token) or app.state.window is None:
            return {'focused': False}
        app.state.window.restore()
        app.state.window.show()
        return {'focused': True}

    return app


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8081)
    parser.add_argument('--data-dir', type=Path, help='Use a copied data directory')
    parser.add_argument('--native', action='store_true', help='Open a desktop window on a free loopback port')
    parser.add_argument('--ready-file', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--focus-token', default='', help=argparse.SUPPRESS)
    parser.add_argument('--code-fingerprint', default='', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.data_dir:
        original = configuration.read_sources

        def sources(*arguments):
            return [{**s, 'data_dir': args.data_dir.resolve()} for s in original(*arguments)]

        configuration.read_sources = sources
    with socket.socket() as listener:
        if os.name != 'nt':  # As uvicorn does, so a fixed --port rebinds while the last run is in TIME_WAIT.
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(('127.0.0.1', 0 if args.native else args.port))
        # Listen now: the ready file and the native window's first load can come before uvicorn accepts,
        # and the backlog holds those connections instead of refusing them.
        listener.listen()
        url = f'http://127.0.0.1:{listener.getsockname()[1]}'
        app = configure_launch(args, url)
        server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=listener.getsockname()[1]))
        app.state.server = server
        if not args.native:
            server.run(sockets=[listener])
            return
        import webview
        window = webview.create_window('Brownstone Markets', url, width=1280, height=900, text_select=True)
        app.state.window = window
        window.events.loaded += app.state.ready
        thread = threading.Thread(target=server.run, kwargs={'sockets': [listener]})
        thread.start()
        try:
            webview.start()
        finally:
            server.should_exit = True
            thread.join()


if __name__ == '__main__':
    main()
