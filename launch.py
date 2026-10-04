"""Double-click launcher: reuse the local server or start it in the background."""
import os
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


def main():
    if healthy():
        print("Brownstone is already running. Opening your browser...")
        webbrowser.open(URL)
        return 0
    log_dir = ROOT / "work"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / "launcher.log"
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
            (log_dir / "server.pid").write_text(str(process.pid), encoding="utf-8")
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
