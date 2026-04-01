#!/usr/bin/env python3
"""
start.py — launch Flask backend + Vite React frontend together.
Ctrl+C shuts both down cleanly.
"""

import json
import subprocess
import sys
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT     = Path(__file__).parent
FRONTEND = ROOT / "frontend"


def stream(proc, prefix):
    """Forward a process's stdout+stderr to our stdout with a prefix."""
    for line in proc.stdout:
        print(f"{prefix} {line}", end="", flush=True)


def ensure_images():
    """Download skin and agent images if their folders don't exist yet."""
    skins_dir  = ROOT / "images" / "skins"
    agents_dir = ROOT / "images" / "agents"

    to_download = []  # list of (url, dest_path)

    if not skins_dir.exists():
        skins_dir.mkdir(parents=True)
        skins = json.loads((ROOT / "struct_db" / "skins.json").read_text(encoding="utf-8"))
        for item in skins:
            if item.get("id") and item.get("image"):
                to_download.append((item["image"], skins_dir / f"{item['id']}.png"))

    if not agents_dir.exists():
        agents_dir.mkdir(parents=True)
        agents = json.loads((ROOT / "struct_db" / "agents.json").read_text(encoding="utf-8"))
        for item in agents:
            if item.get("id") and item.get("image"):
                to_download.append((item["image"], agents_dir / f"{item['id']}.png"))

    if not to_download:
        return

    total  = len(to_download)
    done   = 0
    failed = []
    print(f"Downloading {total} images…")

    def fetch(url, path):
        urllib.request.urlretrieve(url, path)

    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = {pool.submit(fetch, url, path): path for url, path in to_download}
        for future in as_completed(futures):
            done += 1
            try:
                future.result()
            except Exception as e:
                failed.append(futures[future].name)
            print(f"\r  {done}/{total}", end="", flush=True)

    print(f"\n  Done. {total - len(failed)} downloaded, {len(failed)} failed.")
    if failed:
        print(f"  Failed: {failed[:5]}")


def main():
    ensure_images()
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
