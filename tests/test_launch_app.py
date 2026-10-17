"""Main app launch is tested without opening a window or contacting a live server."""
import argparse
import json
import sys
import time
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import brownstone_app
import launch_app


@pytest.mark.parametrize('native_ok,browser_ok,result', [(True, False, 0), (False, True, 0), (False, False, 1)])
def test_launcher_native_failure_browser_fallback(monkeypatch, tmp_path, capsys, native_ok, browser_ok, result):
    monkeypatch.setattr(launch_app, 'code_fingerprint', lambda: 'current')
    monkeypatch.setattr(launch_app, 'ROOT', tmp_path)
    monkeypatch.setattr(launch_app, 'reuse', lambda path: False)
    starts = []
    def start(args, ready_file, log, *, native):
        starts.append((native, args.data_dir))
        return MagicMock()
    def ready(process, path):
        if (native_ok if len(starts) == 1 else browser_ok):
            path.write_text(json.dumps({'url': 'http://127.0.0.1:12345'}))
            return True
        return False
    monkeypatch.setattr(launch_app, 'start', start)
    monkeypatch.setattr(launch_app, 'await_ready', ready)
    browser = MagicMock()
    monkeypatch.setattr(launch_app.webbrowser, 'open', browser)
    assert launch_app.main(['--data-dir', str(tmp_path)]) == result
    assert starts[0] == (True, tmp_path)
    if not native_ok:
        assert starts[1] == (False, tmp_path)
        assert 'Native window could not start' in capsys.readouterr().out
    assert browser.called == (not native_ok and browser_ok)


def test_reuse_focus_browser_and_invalid_state(monkeypatch, tmp_path):
    monkeypatch.setattr(launch_app, 'code_fingerprint', lambda: 'current')
    path = tmp_path / 'ready.json'
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b'{"focused": true}'
    opener = MagicMock(return_value=response)
    monkeypatch.setattr(launch_app.urllib.request, 'urlopen', opener)
    browser = MagicMock()
    monkeypatch.setattr(launch_app.webbrowser, 'open', browser)
    state = {'url': 'http://127.0.0.1:12345', 'token': 'test-token', 'native': True, 'code': 'current'}
    path.write_text(json.dumps(state))
    assert launch_app.reuse(path) and not browser.called
    assert opener.call_args.args[0].method == 'POST'
    response.__enter__.return_value.read.return_value = b'{"focused": false}'
    assert not launch_app.reuse(path)
    path.write_text(json.dumps(state | {'native': False}))
    assert launch_app.reuse(path) and browser.called
    path.write_text(json.dumps(state | {'url': 'http://example.com'}))
    assert not launch_app.reuse(path)
    path.write_text('broken')
    assert not launch_app.reuse(path)


def test_launcher_reuses_and_child_command(monkeypatch, tmp_path):
    monkeypatch.setattr(launch_app, 'code_fingerprint', lambda: 'current')
    monkeypatch.setattr(launch_app, 'ROOT', tmp_path)
    monkeypatch.setattr(launch_app, 'reuse', lambda path: True)
    assert launch_app.main([]) == 0
    popen = MagicMock()
    monkeypatch.setattr(launch_app.subprocess, 'Popen', popen)
    listener = MagicMock()
    listener.__enter__.return_value = listener
    listener.getsockname.return_value = ('127.0.0.1', 12345)
    monkeypatch.setattr(launch_app.socket, 'socket', lambda: listener)
    args = argparse.Namespace(data_dir=tmp_path)
    launch_app.start(args, tmp_path / 'ready', None, native=False)
    command = popen.call_args.args[0]
    assert '--port' in command and int(command[command.index('--port') + 1]) > 0 and '--data-dir' in command
    launch_app.start(args, tmp_path / 'ready', None, native=True)
    assert '--native' in popen.call_args.args[0] and '--port' not in popen.call_args.args[0]


def test_ready_wait_exit_success_timeout(monkeypatch, tmp_path):
    process = MagicMock()
    path = tmp_path / 'ready'
    process.poll.return_value = 1
    assert not launch_app.await_ready(process, path)
    path.touch()
    assert launch_app.await_ready(process, path)
    path.unlink()
    process.poll.return_value = None
    monkeypatch.setattr(launch_app.time, 'sleep', lambda _: None)
    assert not launch_app.await_ready(process, path)
    process.terminate.assert_called_once()
    process.wait.assert_called_once()


def test_restart_changed_code_uses_authenticated_stop(monkeypatch, tmp_path):
    path = tmp_path / 'ready'
    path.write_text(json.dumps({'url': 'http://127.0.0.1:12345', 'token': 'secret',
                                'native': True, 'code': 'old'}))
    monkeypatch.setattr(launch_app, 'code_fingerprint', lambda: 'new')
    actions = []

    def request(state, action):
        actions.append(action)
        assert state['token'] == 'secret'
        if action == 'stop':
            return {'stopping': True}
        raise OSError('server closed')

    monkeypatch.setattr(launch_app, 'request_state', request)
    assert not launch_app.reuse(path)
    assert actions == ['stop', 'focus']


@pytest.mark.parametrize('name', ['brownstone_app.py', 'launch_app.py',
                                  'brownstone/cli.py', 'brownstone/nested/module.py', 'views/today_rows.py'])
def test_fingerprint_covers_surviving_code_without_old_entry(monkeypatch, tmp_path, name):
    monkeypatch.setattr(launch_app, 'ROOT', tmp_path)
    for filename in ('brownstone_app.py', 'launch_app.py', name):
        path = tmp_path / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('initial')
    before = launch_app.code_fingerprint()
    (tmp_path / name).write_text('changed')
    assert launch_app.code_fingerprint() != before
    (tmp_path / name).write_text('initial')
    assert launch_app.code_fingerprint() == before
    if name not in ('brownstone_app.py', 'launch_app.py'):
        moved = tmp_path / (name + '.moved.py')
        (tmp_path / name).rename(moved)
        assert launch_app.code_fingerprint() != before


@pytest.mark.parametrize('query,target', [
    ('', '/app/today'), ('source=missing&place=Market', '/app/today'),
    ('source=test', '/app/today?source=test&view=route'),
    ('source=test&place=unknown', '/app/today?source=test&view=route'),
    ('source=test&view=This+session', '/app/today?source=test&view=level-up'),
    ('source=test&view=Today+plan&tab=Plan', '/app/today?source=test&view=opportunities'),
    ('source=test&view=bad&tab=Queue', '/app/today?source=test&view=route'),
    ('source=test&view=opportunities', '/app/today?source=test&view=opportunities'),
    ('source=test&view=route', '/app/today?source=test&view=route'),
    ('source=test&view=level-up', '/app/today?source=test&view=level-up'),
    ('source=test&place=Team', '/app/team?source=test'),
    ('source=test&place=Stock', '/app/ledger?source=test'),
    ('source=test&place=Data', '/app/today?source=test&sheet=data'),
    ('source=test&place=Market&item=123&origin_place=Today&origin_tab=Queue&origin_view=This+session',
     '/app/market?source=test&inspect=123&origin_place=Today&origin_tab=Queue&origin_view=This+session'),
    ('source=test&place=Market&item=123&origin_place=Market&origin_item=42&origin_name=Cloth',
     '/app/market?source=test&inspect=123&origin_place=Market&origin_item=42&origin_name=Cloth'),
    ('source=test&place=Market&item=123&origin_place=Market&origin_item=-1&origin_name=bad',
     '/app/market?source=test&inspect=123'),
    ('source=test&place=Market&origin_place=Today&origin_tab=bad&origin_view=This+session',
     '/app/market?source=test'),
])
def test_legacy_redirect(monkeypatch, tmp_path, query, target):
    monkeypatch.setattr(brownstone_app.context, 'enabled', lambda: [{'source_id': 'test'}])
    args = argparse.Namespace(native=True, ready_file=None, focus_token='token', code_fingerprint='code')
    with TestClient(brownstone_app.configure_launch(args, 'http://127.0.0.1:1234')) as client:
        response = client.get('/?' + query, follow_redirects=False)
        assert response.status_code == 307
        assert response.headers['location'] == target


def test_legacy_redirect_with_unreadable_config(monkeypatch):
    def broken():
        raise ValueError('bad config')
    monkeypatch.setattr(brownstone_app.context, 'enabled', broken)
    assert brownstone_app.legacy_url('test', 'Market', 2589) == '/app/today'


@pytest.mark.parametrize('native', [False, True])
def test_readiness_tokens_and_shutdown(monkeypatch, tmp_path, native):
    args = argparse.Namespace(native=native, ready_file=tmp_path / 'ready.json', focus_token='token',
                              code_fingerprint='current')
    app = brownstone_app.configure_launch(args, 'http://127.0.0.1:12345')
    app.state.server = MagicMock(should_exit=False)
    window = MagicMock()
    if native:
        app.state.window = window
    replacements = []
    original = type(tmp_path).replace
    def replace(partial, target):
        assert not target.exists()
        replacements.append(json.loads(partial.read_text()))
        return original(partial, target)
    monkeypatch.setattr(type(tmp_path), 'replace', replace)
    with TestClient(app) as client:
        if native:
            assert not args.ready_file.exists()
            app.state.ready()
            app.state.ready()
            window.show.assert_called_once()
        expected = {'url': 'http://127.0.0.1:12345', 'native': native, 'token': 'token', 'code': 'current'}
        assert json.loads(args.ready_file.read_text()) == expected
        assert replacements == [expected]
        assert not args.ready_file.with_suffix('.tmp').exists()
        assert client.post('/_brownstone/focus?token=wrong').json() == {'focused': False}
        assert client.post('/_brownstone/stop?token=wrong').json() == {'stopping': False}
        assert not app.state.server.should_exit
        assert client.post('/_brownstone/focus?token=token').json() == {'focused': native}
        assert client.post('/api/data/review?source=test').status_code == 403
        # A valid token passes the boundary even when the requested API route does not exist.
        assert client.post('/api/unknown', headers={'X-Brownstone-Token': 'token'}).status_code == 404
        assert client.post('/_brownstone/stop?token=token').json() == {'stopping': True}
        deadline = time.monotonic() + 5
        while not app.state.server.should_exit and time.monotonic() < deadline:
            time.sleep(.02)
        assert app.state.server.should_exit
        if native:
            window.restore.assert_called_once()
            assert window.show.call_count == 2
            window.destroy.assert_called_once()


def test_browser_idle_stops_only_after_five_minutes_without_presence(monkeypatch):
    now = [0.0]
    shutdown = MagicMock()
    monkeypatch.setattr(brownstone_app.time, 'monotonic', lambda: now[0])
    tabs = {object()}
    monkeypatch.setattr(brownstone_app, 'connected', tabs)
    idle = brownstone_app.BrowserIdle(shutdown)
    now[0] = 1000
    idle.check()
    shutdown.assert_not_called()
    tabs.clear()
    idle.check()
    now[0] = 1299
    idle.check()
    shutdown.assert_not_called()
    now[0] = 1300
    idle.check()
    shutdown.assert_called_once()


@pytest.mark.parametrize('native', [False, True])
def test_main_loopback_window_and_copied_data(monkeypatch, tmp_path, native):
    listener = MagicMock()
    listener.__enter__.return_value = listener
    listener.getsockname.return_value = ('127.0.0.1', 12345)
    monkeypatch.setattr(brownstone_app.socket, 'socket', lambda: listener)
    server = MagicMock()
    monkeypatch.setattr(brownstone_app.uvicorn, 'Server', lambda config: server)
    thread = MagicMock()
    monkeypatch.setattr(brownstone_app.threading, 'Thread', lambda **kwargs: thread)
    webview = MagicMock()
    monkeypatch.setitem(sys.modules, 'webview', webview)
    monkeypatch.setattr(brownstone_app.configuration, 'read_sources', lambda *args: [{'data_dir': 'live'}])
    args = ['--data-dir', str(tmp_path), '--port', '9123'] + (['--native'] if native else [])
    brownstone_app.main(args)
    listener.bind.assert_called_once_with(('127.0.0.1', 0 if native else 9123))
    listener.listen.assert_called_once()
    assert brownstone_app.configuration.read_sources()[0]['data_dir'] == tmp_path.resolve()
    if native:
        webview.create_window.assert_called_once_with('Brownstone Markets', 'http://127.0.0.1:12345',
                                                       width=1280, height=900, text_select=True)
        webview.start.assert_called_once()
        thread.start.assert_called_once()
        thread.join.assert_called_once()
        assert server.should_exit
    else:
        server.run.assert_called_once_with(sockets=[listener])
        webview.start.assert_not_called()
