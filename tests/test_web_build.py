"""Launcher build invalidation and recoverable failure without live npm processes."""
import subprocess
from unittest.mock import MagicMock

import web_build as wb


def setup_web(tmp_path):
    web = tmp_path / 'web'
    (web / 'src').mkdir(parents=True)
    for name in ['package.json', 'package-lock.json', 'index.html', 'src/main.tsx']:
        (web / name).write_text(name)
    return web


def test_fingerprint_build_install_and_lock_change(tmp_path, monkeypatch):
    web = setup_web(tmp_path)
    commands = []
    monkeypatch.setattr(wb, 'find_tool', lambda name: '/usr/local/bin/' + name)
    def run(command, **kwargs):
        commands.append(command)
        if command[-1] == 'ci':
            (web / 'node_modules').mkdir(exist_ok=True)
        if command[-1] == 'build':
            (web / 'dist').mkdir(exist_ok=True)
            (web / 'dist/index.html').write_text('built')
        return subprocess.CompletedProcess(command, 0, 'v24.22.0', '')
    monkeypatch.setattr(wb.subprocess, 'run', run)
    assert wb.build_web(tmp_path) == ''
    assert [c[-1] for c in commands] == ['--version', 'ci', 'build']
    commands.clear()
    assert wb.build_web(tmp_path) == '' and not commands
    (web / 'src/main.tsx').write_text('changed')
    assert wb.build_web(tmp_path) == ''
    assert [c[-1] for c in commands] == ['--version', 'build']
    commands.clear()
    (web / 'package-lock.json').write_text('new lock')
    assert wb.build_web(tmp_path) == ''
    assert [c[-1] for c in commands] == ['--version', 'ci', 'build']


def test_missing_node_failed_build_and_wrong_version_are_fallbacks(tmp_path, monkeypatch):
    assert wb.build_web(tmp_path) == ''
    web = setup_web(tmp_path)
    monkeypatch.setattr(wb, 'find_tool', lambda name: None)
    assert 'install Node 24 LTS' in wb.build_web(tmp_path)
    monkeypatch.setattr(wb, 'find_tool', lambda name: name)
    monkeypatch.setattr(wb.subprocess, 'run', MagicMock(side_effect=OSError('broken')))
    assert 'run npm ci and npm run build' in wb.build_web(tmp_path)
    assert not (web / 'dist/.fingerprint').exists()
    monkeypatch.setattr(wb.subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess([], 0, 'v22.1', ''))
    assert 'install Node 24 LTS' in wb.build_web(tmp_path)


def test_finder_path_fallback(monkeypatch):
    monkeypatch.setattr(wb.shutil, 'which', lambda name: None)
    monkeypatch.setattr(wb.Path, 'is_file', lambda path: path.as_posix() == '/opt/homebrew/bin/npm')
    assert wb.Path(wb.find_tool('npm')).as_posix() == '/opt/homebrew/bin/npm'
    assert wb.find_tool('node') is None


def test_launcher_fallback_banner_still_opens_existing_app(tmp_path, monkeypatch, capsys):
    import launch_nicegui as launcher
    monkeypatch.setattr(launcher, 'ROOT', tmp_path)
    monkeypatch.setattr(launcher, 'build_web', lambda root: 'Web app unavailable: install Node 24 LTS.')
    monkeypatch.setattr(launcher, 'reuse', lambda path: True)
    monkeypatch.delenv('BROWNSTONE_WEB_WARNING', raising=False)
    assert launcher.main([]) == 0
    assert 'install Node 24 LTS' in capsys.readouterr().out
    assert 'install Node 24 LTS' in launcher.os.environ['BROWNSTONE_WEB_WARNING']
    monkeypatch.setattr(launcher, 'build_web', lambda root: '')
    assert launcher.main([]) == 0
    assert 'BROWNSTONE_WEB_WARNING' not in launcher.os.environ
