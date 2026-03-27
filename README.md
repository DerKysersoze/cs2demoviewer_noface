# CS2 Demo Viewer

A local web application for parsing and visualising CS2 demo files (`.dem`).
Upload a demo to get per-round kill feeds, scoreboard, map view with player positions, aim breakdown, timeline, and cosmetic/inventory data.

---

## Prerequisites

Install these before anything else.

| Tool | Minimum version | Download |
|------|----------------|---------|
| Python | 3.10+ | https://www.python.org/downloads/ |
| Node.js | 18+ | https://nodejs.org/ |
| npm | 9+ (comes with Node.js) | — |

> **Windows users:** during Python install, tick "Add Python to PATH".

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/DerKysersoze/cs2demoviewer_noface.git
cd cs2demoviewer_noface
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

This installs:
- **flask** — web server
- **awpy** — CS2 demo parser (pulls in pandas and protobuf automatically)
- **pandas** — data processing
- **rich** — terminal output formatting

**Optional but recommended** — improves parsing performance and unlocks additional data fields (armor, weapon skins):

```bash
pip install polars demoparser2
```

> `demoparser2` is a compiled C extension. Pre-built wheels are available for Windows/macOS/Linux on PyPI — no compiler needed.

### 3. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

---

## Running the app

### Development mode (recommended for local use)

Starts both the Flask backend (port 5000) and the Vite dev server (port 3000) together:

```bash
python start.py
```

Then open **http://localhost:3000** in your browser.

> Press `Ctrl+C` to stop both servers.

### Backend only (uses pre-built frontend)

If you don't want to run the Vite dev server, the pre-built frontend in `static_react/` is served directly by Flask:

```bash
python app.py
```

Open **http://localhost:5000**.

### Build the frontend yourself (optional)

If you modify the React source and want to rebuild the static files:

```bash
cd frontend
npm run build
cd ..
```

Output goes to `static_react/`.

---

## First run

1. Open the app in your browser.
2. On the **Upload** page, click **Download Maps** — this fetches the map radar images from the awpy package (~50 MB, one-time download).
3. Upload a `.dem` file (up to 512 MB).
4. Parsing takes a few seconds to a minute depending on demo size.

The SQLite database (`demos.db`) and any generated images are created automatically — no manual database setup needed.

---

## Ports

| Service | Port | URL |
|---------|------|-----|
| Flask backend | 5000 | http://localhost:5000 |
| Vite dev server | 3000 | http://localhost:3000 |

API calls from the frontend are proxied from port 3000 → 5000 automatically.

---

## Project structure

```
cs2demoviewer_noface/
├── app.py              # Flask backend + demo parsing
├── start.py            # Launches both servers together
├── requirements.txt    # Python dependencies
├── frontend/           # React/Vite source
│   ├── src/
│   └── package.json
├── static_react/       # Pre-built frontend (served by Flask)
└── struct_db/          # CS2 item data (agents, skins, stickers, etc.)
```

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'awpy'`**
Run `pip install -r requirements.txt` again. If using a virtual environment make sure it is activated.

**`npm: command not found`**
Node.js is not installed or not on PATH. Install from https://nodejs.org/.

**Map images not showing**
Use the "Download Maps" button on the Upload page. Requires an internet connection on first use.

**Port already in use**
Another process is using port 5000 or 3000. Stop it or change the port in `app.py` (line ~1797) and `frontend/vite.config.js`.

**`demoparser2` install fails**
This is optional. The app works without it; some per-player cosmetic/armor fields will be absent.
