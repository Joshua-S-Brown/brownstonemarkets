"""Double-click launcher: reuse the local server if its code is current, else (re)start it.

Streamlit reloads app.py on each rerun but not imported modules, so a server left running
across code changes fails with confusing import errors. The launcher fingerprints the
Python sources it started with and restarts its own server when they change.
"""
import hashlib
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
URL = "http://127.0.0.1:8501"


def healthy():
    try:
        with urllib.request.urlopen(URL + "/_stcore/health", timeout=1) as response:
            return response.status == 200 and response.read().strip() == b"ok"
    except (OSError, urllib.error.URLError):
        return False


def code_fingerprint():
    digest = hashlib.sha256()
    for path in sorted([ROOT / "app.py", *ROOT.glob("brownstone/**/*.py"), *ROOT.glob("views/**/*.py")]):
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def stop_own_server(work):
    """Stop the server this launcher started. Returns False if it cannot be identified."""
    pid_file, code_file = work / "server.pid", work / "server.code"
    if not pid_file.exists():
        return False
    try:
        os.kill(int(pid_file.read_text(encoding="utf-8")), signal.SIGTERM)
    except (OSError, ValueError):
        pass  # Already gone; the health check below decides.
    pid_file.unlink(missing_ok=True)
    code_file.unlink(missing_ok=True)
    for _ in range(40):
        if not healthy():
            return True
        time.sleep(.25)
    return False


def main():
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    fingerprint = code_fingerprint()
    code_file = work / "server.code"
    if healthy():
        if code_file.exists() and code_file.read_text(encoding="utf-8") == fingerprint:
            print("Brownstone is already running. Opening your browser...")
            webbrowser.open(URL)
            return 0
        print("Brownstone's code changed since the server started. Restarting...")
        if not stop_own_server(work):
            print(f"Another server is using {URL} and was not started by this launcher. "
                  "Close it (Ctrl+C in its terminal) and try again.")
            return 1
    log_path = work / "launcher.log"
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py"),
             "--server.address", "127.0.0.1", "--server.port", "8501",
             "--server.headless", "true", "--browser.gatherUsageStats", "false"],
            cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
            creationflags=flags,
        )
    print("Starting Brownstone Markets...")
    for _ in range(60):
        if healthy():
            (work / "server.pid").write_text(str(process.pid), encoding="utf-8")
            code_file.write_text(fingerprint, encoding="utf-8")
            webbrowser.open(URL)
            print("Brownstone is ready. You can close this window.")
            return 0
        if process.poll() is not None:
            break
        time.sleep(.5)
    print("Brownstone could not start. Details:")
    print(log_path.read_text(encoding="utf-8", errors="replace"))
    print(f"Startup log: {log_path}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
