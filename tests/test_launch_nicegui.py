"""Main app launch is tested without opening a window or contacting a live server."""
import argparse
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import launch_nicegui
import nicegui_app


def test_native_and_browser_arguments(monkeypatch, tmp_path):
    run = MagicMock()
    monkeypatch.setattr(nicegui_app.ui, 'run', run)
    monkeypatch.setattr(nicegui_app, 'configure_launch', lambda args: None)
    original = nicegui_app.configuration.read_sources
    monkeypatch.delenv('NICEGUI_USER_SIMULATION', raising=False)
    monkeypatch.setattr(nicegui_app.configuration, 'read_sources', lambda *args: [{'data_dir': Path('data')}])
    nicegui_app.main(['--native', '--data-dir', str(tmp_path)])
    assert nicegui_app.app.native.window_args['text_select'] is True
    assert run.call_args.kwargs['native'] and run.call_args.kwargs['port'] is None
    assert run.call_args.kwargs['host'] == '127.0.0.1'
    assert nicegui_app.configuration.read_sources()[0]['data_dir'] == tmp_path.resolve()
    nicegui_app.main(['--port', '9123'])
    assert run.call_args.kwargs['port'] == 9123 and not run.call_args.kwargs['native']
    monkeypatch.setattr(nicegui_app.configuration, 'read_sources', original)


@pytest.mark.parametrize('native_ok,browser_ok,result', [(True, False, 0), (False, True, 0), (False, False, 1)])
def test_launcher_native_failure_browser_fallback(monkeypatch, tmp_path, capsys, native_ok, browser_ok, result):
    monkeypatch.setattr(launch_nicegui, 'code_fingerprint', lambda: 'current')
    monkeypatch.setattr(launch_nicegui, 'ROOT', tmp_path)
    monkeypatch.setattr(launch_nicegui, 'reuse', lambda path: False)
    starts = []
    def start(args, ready_file, log, *, native):
        starts.append((native, args.data_dir))
        return MagicMock()
    def ready(process, path):
        if (native_ok if len(starts) == 1 else browser_ok):
            path.write_text(json.dumps({'url': 'http://127.0.0.1:12345'}))
            return True
        return False
    monkeypatch.setattr(launch_nicegui, 'start', start)
    monkeypatch.setattr(launch_nicegui, 'await_ready', ready)
    browser = MagicMock()
    monkeypatch.setattr(launch_nicegui.webbrowser, 'open', browser)
    assert launch_nicegui.main(['--data-dir', str(tmp_path)]) == result
    assert starts[0] == (True, tmp_path)
    if not native_ok:
        assert starts[1] == (False, tmp_path)
        assert 'Native window could not start' in capsys.readouterr().out
    assert browser.called == (not native_ok and browser_ok)


def test_reuse_focus_browser_and_invalid_state(monkeypatch, tmp_path):
    monkeypatch.setattr(launch_nicegui, 'code_fingerprint', lambda: 'current')
    path = tmp_path / 'ready.json'
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b'{"focused": true}'
    opener = MagicMock(return_value=response)
    monkeypatch.setattr(launch_nicegui.urllib.request, 'urlopen', opener)
    browser = MagicMock()
    monkeypatch.setattr(launch_nicegui.webbrowser, 'open', browser)
    state = {'url': 'http://127.0.0.1:12345', 'token': 'test-token', 'native': True, 'code': 'current'}
    path.write_text(json.dumps(state))
    assert launch_nicegui.reuse(path) and not browser.called
    assert opener.call_args.args[0].method == 'POST'
    response.__enter__.return_value.read.return_value = b'{"focused": false}'
    assert not launch_nicegui.reuse(path)
    path.write_text(json.dumps(state | {'native': False}))
    assert launch_nicegui.reuse(path) and browser.called
    path.write_text(json.dumps(state | {'url': 'http://example.com'}))
    assert not launch_nicegui.reuse(path)
    path.write_text('broken')
    assert not launch_nicegui.reuse(path)


def test_launcher_reuses_and_child_command(monkeypatch, tmp_path):
    monkeypatch.setattr(launch_nicegui, 'code_fingerprint', lambda: 'current')
    monkeypatch.setattr(launch_nicegui, 'ROOT', tmp_path)
    monkeypatch.setattr(launch_nicegui, 'reuse', lambda path: True)
    assert launch_nicegui.main([]) == 0
    popen = MagicMock()
    monkeypatch.setattr(launch_nicegui.subprocess, 'Popen', popen)
    monkeypatch.setattr('nicegui.native.find_open_port', lambda: 12345)
    args = argparse.Namespace(data_dir=tmp_path)
    launch_nicegui.start(args, tmp_path / 'ready', None, native=False)
    command = popen.call_args.args[0]
    assert '--port' in command and '12345' in command and '--data-dir' in command
    launch_nicegui.start(args, tmp_path / 'ready', None, native=True)
    assert '--native' in popen.call_args.args[0] and '--port' not in popen.call_args.args[0]


def test_ready_wait_exit_success_timeout(monkeypatch, tmp_path):
    process = MagicMock()
    path = tmp_path / 'ready'
    process.poll.return_value = 1
    assert not launch_nicegui.await_ready(process, path)
    path.touch()
    assert launch_nicegui.await_ready(process, path)
    path.unlink()
    process.poll.return_value = None
    monkeypatch.setattr(launch_nicegui.time, 'sleep', lambda _: None)
    assert not launch_nicegui.await_ready(process, path)
    process.terminate.assert_called_once()
    process.wait.assert_called_once()


@pytest.mark.parametrize('native', [False, True])
def test_readiness_and_focus_endpoint(monkeypatch, tmp_path, native):
    handlers = {}
    monkeypatch.setattr(type(nicegui_app.app.native), 'on',
                        lambda self, event, handler: handlers.update({event: handler}))
    monkeypatch.setattr(nicegui_app.app, 'on_startup', lambda handler: handlers.setdefault('startup', handler))
    monkeypatch.setattr(nicegui_app.app, 'post',
                        lambda path: lambda handler: handlers.update({path.rsplit('/', 1)[-1]: handler}))
    monkeypatch.setenv('NICEGUI_PORT', '12345')
    args = argparse.Namespace(native=native, ready_file=tmp_path / 'ready', focus_token='token',
                              code_fingerprint='current')
    opened = MagicMock()
    monkeypatch.setattr(nicegui_app.app.native, 'main_window', opened)
    nicegui_app.configure_launch(args)
    handlers['loaded' if native else 'startup']()
    if native:
        handlers['loaded']()  # later page loads never re-activate the window
    assert opened.show.call_count == (1 if native else 0)
    state = json.loads(args.ready_file.read_text())
    assert state == {'url': 'http://127.0.0.1:12345', 'native': native, 'token': 'token', 'code': 'current'}
    assert not handlers['focus']('wrong')['focused']
    window = MagicMock()
    monkeypatch.setattr(nicegui_app.app.native, 'main_window', window)
    assert handlers['focus']('token')['focused']
    window.restore.assert_called_once()
    window.show.assert_called_once()
    monkeypatch.setattr(nicegui_app.app.native, 'main_window', None)
    assert not handlers['focus']('token')['focused']


def test_restart_changed_code_uses_authenticated_stop(monkeypatch, tmp_path):
    path = tmp_path / 'ready'
    path.write_text(json.dumps({'url': 'http://127.0.0.1:12345', 'token': 'secret',
                                'native': True, 'code': 'old'}))
    monkeypatch.setattr(launch_nicegui, 'code_fingerprint', lambda: 'new')
    actions = []

    def request(state, action):
        actions.append(action)
        assert state['token'] == 'secret'
        if action == 'stop':
            return {'stopping': True}
        raise OSError('server closed')

    monkeypatch.setattr(launch_nicegui, 'request_state', request)
    assert not launch_nicegui.reuse(path)
    assert actions == ['stop', 'focus']


@pytest.mark.asyncio
async def test_foreign_app_is_never_stopped(monkeypatch, tmp_path):
    path = tmp_path / 'ready'
    path.write_text(json.dumps({'url': 'http://127.0.0.1:12345', 'token': 'wrong', 'code': 'old'}))
    monkeypatch.setattr(launch_nicegui, 'code_fingerprint', lambda: 'new')
    monkeypatch.setattr(launch_nicegui, 'request_state', lambda *args: {'stopping': False})
    assert not launch_nicegui.reuse(path)
    timers = []
    handlers = {}
    monkeypatch.setattr(nicegui_app.app, 'post',
                        lambda path: lambda handler: handlers.update({path.rsplit('/', 1)[-1]: handler}))
    monkeypatch.setattr(nicegui_app.app, 'timer', lambda *args, **kwargs: timers.append((args, kwargs)))
    monkeypatch.setattr(type(nicegui_app.app.native), 'on', lambda *args: None)
    args = argparse.Namespace(native=True, ready_file=None, focus_token='ours', code_fingerprint='new')
    nicegui_app.configure_launch(args)
    assert await handlers['stop']('wrong') == {'stopping': False}
    assert not timers
    assert await handlers['stop']('ours') == {'stopping': True}
    assert timers[0][0][1] == nicegui_app.app.shutdown


def test_browser_idle_stops_after_five_disconnected_minutes(monkeypatch):
    now = [0.0]
    shutdown = MagicMock()
    monkeypatch.setattr(nicegui_app.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(nicegui_app.app, 'shutdown', shutdown)
    clients = {'one': MagicMock(has_socket_connection=True), 'two': MagicMock(has_socket_connection=False)}
    monkeypatch.setattr(nicegui_app.Client, 'instances', clients)
    idle = nicegui_app.BrowserIdle()
    now[0] = 1000
    idle.check()
    shutdown.assert_not_called()
    clients['one'].has_socket_connection = False
    idle.check()
    now[0] = 1299
    idle.check()
    shutdown.assert_not_called()
    now[0] = 1300
    idle.check()
    shutdown.assert_called_once()


@pytest.mark.parametrize('name', ['nicegui_app.py', 'launch_nicegui.py',
                                  'brownstone/cli.py', 'brownstone/nested/module.py', 'views/today_rows.py'])
def test_fingerprint_covers_surviving_code_without_old_entry(monkeypatch, tmp_path, name):
    monkeypatch.setattr(launch_nicegui, 'ROOT', tmp_path)
    for filename in ('nicegui_app.py', 'launch_nicegui.py', name):
        path = tmp_path / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('initial')
    before = launch_nicegui.code_fingerprint()
    (tmp_path / name).write_text('changed')
    assert launch_nicegui.code_fingerprint() != before
    (tmp_path / name).write_text('initial')
    assert launch_nicegui.code_fingerprint() == before
    if name not in ('nicegui_app.py', 'launch_nicegui.py'):
        moved = tmp_path / (name + '.moved.py')
        (tmp_path / name).rename(moved)
        assert launch_nicegui.code_fingerprint() != before


def test_web_socket_keeps_browser_fallback_alive(monkeypatch):
    import nicegui_app
    from api import presence
    clock = [0]
    stopped = []
    monkeypatch.setattr(nicegui_app.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(nicegui_app.Client, 'instances', {})
    monkeypatch.setattr(nicegui_app.app, 'shutdown', lambda: stopped.append(True))
    tabs = {object()}
    monkeypatch.setattr(nicegui_app, 'web_tabs', tabs)
    assert not presence.connected
    idle = nicegui_app.BrowserIdle()
    clock[0] = 600
    idle.check()
    assert not stopped
    tabs.clear()
    idle.check()
    clock[0] = 899
    idle.check()
    assert not stopped
    clock[0] = 900
    idle.check()
    assert stopped
