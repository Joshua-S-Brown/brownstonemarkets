"""Trial launch is tested without opening a window or contacting a live server."""
import argparse
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import launch_trial
import nicegui_app


def test_native_and_browser_arguments(monkeypatch, tmp_path):
    run = MagicMock()
    monkeypatch.setattr(nicegui_app.ui, 'run', run)
    monkeypatch.setattr(nicegui_app, 'configure_launch', lambda args: None)
    original = nicegui_app.configuration.read_sources
    monkeypatch.delenv('NICEGUI_USER_SIMULATION', raising=False)
    monkeypatch.setattr(nicegui_app.configuration, 'read_sources', lambda *args: [{'data_dir': Path('data')}])
    nicegui_app.main(['--native', '--data-dir', str(tmp_path)])
    assert run.call_args.kwargs['native'] and run.call_args.kwargs['port'] is None
    assert run.call_args.kwargs['host'] == '127.0.0.1'
    assert nicegui_app.configuration.read_sources()[0]['data_dir'] == tmp_path.resolve()
    nicegui_app.main(['--port', '9123'])
    assert run.call_args.kwargs['port'] == 9123 and not run.call_args.kwargs['native']
    monkeypatch.setattr(nicegui_app.configuration, 'read_sources', original)


@pytest.mark.parametrize('native_ok,browser_ok,result', [(True, False, 0), (False, True, 0), (False, False, 1)])
def test_launcher_native_failure_browser_fallback(monkeypatch, tmp_path, capsys, native_ok, browser_ok, result):
    monkeypatch.setattr(launch_trial, 'ROOT', tmp_path)
    monkeypatch.setattr(launch_trial, 'reuse', lambda path: False)
    starts = []
    def start(args, ready_file, log, *, native):
        starts.append((native, args.data_dir))
        return MagicMock()
    def ready(process, path):
        if (native_ok if len(starts) == 1 else browser_ok):
            path.write_text(json.dumps({'url': 'http://127.0.0.1:12345'}))
            return True
        return False
    monkeypatch.setattr(launch_trial, 'start', start)
    monkeypatch.setattr(launch_trial, 'await_ready', ready)
    browser = MagicMock()
    monkeypatch.setattr(launch_trial.webbrowser, 'open', browser)
    assert launch_trial.main(['--data-dir', str(tmp_path)]) == result
    assert starts[0] == (True, tmp_path)
    if not native_ok:
        assert starts[1] == (False, tmp_path)
        assert 'Native window could not start' in capsys.readouterr().out
    assert browser.called == (not native_ok and browser_ok)


def test_reuse_focus_browser_and_invalid_state(monkeypatch, tmp_path):
    path = tmp_path / 'ready.json'
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b'{"focused": true}'
    opener = MagicMock(return_value=response)
    monkeypatch.setattr(launch_trial.urllib.request, 'urlopen', opener)
    browser = MagicMock()
    monkeypatch.setattr(launch_trial.webbrowser, 'open', browser)
    state = {'url': 'http://127.0.0.1:12345', 'token': 'test-token', 'native': True}
    path.write_text(json.dumps(state))
    assert launch_trial.reuse(path) and not browser.called
    assert opener.call_args.args[0].method == 'POST'
    response.__enter__.return_value.read.return_value = b'{"focused": false}'
    assert not launch_trial.reuse(path)
    path.write_text(json.dumps(state | {'native': False}))
    assert launch_trial.reuse(path) and browser.called
    path.write_text(json.dumps(state | {'url': 'http://example.com'}))
    assert not launch_trial.reuse(path)
    path.write_text('broken')
    assert not launch_trial.reuse(path)


def test_launcher_reuses_and_child_command(monkeypatch, tmp_path):
    monkeypatch.setattr(launch_trial, 'ROOT', tmp_path)
    monkeypatch.setattr(launch_trial, 'reuse', lambda path: True)
    assert launch_trial.main([]) == 0
    popen = MagicMock()
    monkeypatch.setattr(launch_trial.subprocess, 'Popen', popen)
    monkeypatch.setattr('nicegui.native.find_open_port', lambda: 12345)
    args = argparse.Namespace(data_dir=tmp_path)
    launch_trial.start(args, tmp_path / 'ready', None, native=False)
    command = popen.call_args.args[0]
    assert '--port' in command and '12345' in command and '--data-dir' in command
    launch_trial.start(args, tmp_path / 'ready', None, native=True)
    assert '--native' in popen.call_args.args[0] and '--port' not in popen.call_args.args[0]


def test_ready_wait_exit_success_timeout(monkeypatch, tmp_path):
    process = MagicMock()
    path = tmp_path / 'ready'
    process.poll.return_value = 1
    assert not launch_trial.await_ready(process, path)
    path.touch()
    assert launch_trial.await_ready(process, path)
    path.unlink()
    process.poll.return_value = None
    monkeypatch.setattr(launch_trial.time, 'sleep', lambda _: None)
    assert not launch_trial.await_ready(process, path)
    process.terminate.assert_called_once()
    process.wait.assert_called_once()


@pytest.mark.parametrize('native', [False, True])
def test_readiness_and_focus_endpoint(monkeypatch, tmp_path, native):
    handlers = {}
    monkeypatch.setattr(type(nicegui_app.app.native), 'on',
                        lambda self, event, handler: handlers.update({event: handler}))
    monkeypatch.setattr(nicegui_app.app, 'on_startup', lambda handler: handlers.update(startup=handler))
    monkeypatch.setattr(nicegui_app.app, 'post', lambda path: lambda handler: handlers.update(focus=handler))
    monkeypatch.setenv('NICEGUI_PORT', '12345')
    args = argparse.Namespace(native=native, ready_file=tmp_path / 'ready', focus_token='token')
    nicegui_app.configure_launch(args)
    handlers['loaded' if native else 'startup']()
    state = json.loads(args.ready_file.read_text())
    assert state == {'url': 'http://127.0.0.1:12345', 'native': native, 'token': 'token'}
    assert not handlers['focus']('wrong')['focused']
    window = MagicMock()
    monkeypatch.setattr(nicegui_app.app.native, 'main_window', window)
    assert handlers['focus']('token')['focused']
    window.restore.assert_called_once()
    window.show.assert_called_once()
    monkeypatch.setattr(nicegui_app.app.native, 'main_window', None)
    assert not handlers['focus']('token')['focused']
