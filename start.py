#!/usr/bin/env python3
"""
start.py — launch Flask backend + Vite React frontend together.
Ctrl+C shuts both down cleanly.
"""

import subprocess
import sys
import threading
from pathlib import Path

ROOT     = Path(__file__).parent
FRONTEND = ROOT / "frontend"


def stream(proc, prefix):
    """Forward a process's stdout+stderr to our stdout with a prefix."""
    for line in proc.stdout:
        print(f"{prefix} {line}", end="", flush=True)


def main():
    flask = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    npm = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=FRONTEND,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        shell=sys.platform == "win32",   # needed on Windows for npm
    )

    threading.Thread(target=stream, args=(flask, "[flask]"), daemon=True).start()
    threading.Thread(target=stream, args=(npm,   "[react]"), daemon=True).start()

    print("Flask  → http://localhost:5000")
    print("React  → http://localhost:3000")
    print("Ctrl+C to stop both.\n")

    try:
        flask.wait()
        npm.wait()
    except KeyboardInterrupt:
        print("\nShutting down…")
        flask.terminate()
        npm.terminate()
        flask.wait()
        npm.wait()


if __name__ == "__main__":
    main()
