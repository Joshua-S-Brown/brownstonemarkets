"""Detached native main-app launcher with reuse and a browser fallback."""
import argparse
import hashlib
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def code_fingerprint():
    digest = hashlib.sha256()
    paths = [ROOT / 'nicegui_app.py', ROOT / 'launch_nicegui.py',
             *ROOT.glob('brownstone/**/*.py'), *ROOT.glob('views/**/*.py')]
    for path in sorted(paths):
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def request_state(state, action):
    parsed = urllib.parse.urlparse(state['url'])
    if parsed.hostname != '127.0.0.1' or parsed.scheme != 'http':
        raise ValueError('Only loopback launcher-owned servers are allowed')
    request = urllib.request.Request(state['url'] + '/_brownstone/' + action + '?' +
                                     urllib.parse.urlencode({'token': state['token']}), method='POST')
    with urllib.request.urlopen(request, timeout=2) as response:
        return json.load(response)


def reuse(ready_file):
    try:
        state = json.loads(ready_file.read_text(encoding='utf-8'))
        if state.get('code') != code_fingerprint():
            # The server verifies the secret; no PID-based kill can hit an unrelated process.
            if not request_state(state, 'stop').get('stopping'):
                return False
            for _ in range(40):
                try:
                    request_state(state, 'focus')
                except (OSError, ValueError, KeyError, urllib.error.URLError):
                    return False
                time.sleep(.25)
            raise RuntimeError('The previous Brownstone server did not stop. Try again after it closes.')
        focused = request_state(state, 'focus')['focused']
        if not focused:
            if state['native']:
                return False
            webbrowser.open(state['url'])
        return True
    except (OSError, ValueError, KeyError, urllib.error.URLError):
        return False


def start(args, ready_file, log, *, native):
    from nicegui.native import find_open_port
    command = [sys.executable, str(ROOT / 'nicegui_app.py'), '--ready-file', str(ready_file),
               '--focus-token', secrets.token_urlsafe(32), '--code-fingerprint', code_fingerprint()]
    command += ['--native'] if native else ['--port', str(find_open_port())]
    if args.data_dir:
        command += ['--data-dir', str(args.data_dir.resolve())]
    return subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                            start_new_session=os.name != 'nt',
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)


def await_ready(process, ready_file):
    for _ in range(100):
        if ready_file.exists():
            return True
        if process.poll() is not None:
            return False
        time.sleep(.2)
    process.terminate()
    process.wait(timeout=5)
    return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path)
    args = parser.parse_args(argv)
    work = ROOT / 'work'
    work.mkdir(exist_ok=True)
    ready_file = work / 'app-ready.json'
    if reuse(ready_file):
        return 0
    ready_file.unlink(missing_ok=True)
    with (work / 'app-launcher.log').open('w', encoding='utf-8') as log:
        process = start(args, ready_file, log, native=True)
        if await_ready(process, ready_file):
            return 0
        print('Native window could not start; opening Brownstone in your browser instead.')
        ready_file.unlink(missing_ok=True)
        process = start(args, ready_file, log, native=False)
        if await_ready(process, ready_file):
            state = json.loads(ready_file.read_text(encoding='utf-8'))
            webbrowser.open(state['url'])
            return 0
    print(f'Brownstone could not start. See {work / "app-launcher.log"}.')
    return 1


if __name__ == '__main__':
    sys.exit(main())
