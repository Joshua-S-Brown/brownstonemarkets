"""Optional web build; failures never prevent the existing desktop app opening."""
import hashlib
import os
import shutil
import subprocess
from pathlib import Path


def web_paths(root: Path) -> list[Path]:
    web = root / 'web'
    return sorted([*web.glob('src/**/*'), *web.glob('public/**/*'),
                   *web.glob('scripts/*'), *web.glob('*.json'), *web.glob('*.ts'),
                   web / 'index.html', web / '.nvmrc'])


def fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    for path in web_paths(root):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def find_tool(name: str) -> str | None:
    return shutil.which(name) or next((str(path) for folder in ('/usr/local/bin', '/opt/homebrew/bin')
                                      if (path := Path(folder) / name).is_file()), None)


def build_web(root: Path) -> str:
    web = root / 'web'
    if not (web / 'package.json').exists():
        return ''
    try:
        return _ensure_web(root, web)
    except (OSError, subprocess.SubprocessError) as error:
        return f'Web build failed: run npm ci and npm run build in web/, then reopen Brownstone ({error}).'


def _ensure_web(root: Path, web: Path) -> str:
    current = fingerprint(root)
    stamp = web / 'dist/.fingerprint'
    if stamp.exists() and stamp.read_text() == current and (web / 'dist/index.html').exists():
        return ''
    node, npm = find_tool('node'), find_tool('npm')
    if not node or not npm:
        return 'Web app unavailable: install Node 24 LTS, then reopen Brownstone.'
    _build(web, node, npm)
    stamp.parent.mkdir(exist_ok=True)
    stamp.write_text(current)
    return ''


def _build(web: Path, node: str, npm: str):
    env = {**os.environ, 'PATH': str(Path(node).parent) + os.pathsep + os.environ.get('PATH', '')}
    version = subprocess.run([node, '--version'], check=True, capture_output=True, text=True, env=env, timeout=180)
    if not version.stdout.startswith('v24.'):
        raise OSError('install Node 24 LTS')
    lock = hashlib.sha256((web / 'package-lock.json').read_bytes()).hexdigest()
    installed = web / 'node_modules/.brownstone-lock'
    if not installed.exists() or installed.read_text() != lock:
        subprocess.run([npm, 'ci'], cwd=web, check=True, capture_output=True, text=True, env=env, timeout=180)
        installed.write_text(lock)
    subprocess.run([npm, 'run', 'build'], cwd=web, check=True, capture_output=True, text=True, env=env, timeout=180)
