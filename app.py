#!/usr/bin/env python3
"""
CS2 Demo Viewer - Web Backend
Run: python app.py
Then open http://localhost:5000
"""

import datetime
import json
import os
import sqlite3
import zlib
import tempfile
import traceback
import uuid
from collections import OrderedDict

from flask import Flask, jsonify, render_template, request, send_file

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024  # 512 MB

# ── SQLite demo history ────────────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demos.db")


def _db_init():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS demos (
            id          TEXT PRIMARY KEY,
            filename    TEXT NOT NULL,
            map         TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            data        TEXT NOT NULL,
            ticks_data  BLOB
        )
    """)
    # Migrate existing databases that pre-date the ticks_data column
    try:
        con.execute("ALTER TABLE demos ADD COLUMN ticks_data BLOB")
    except sqlite3.OperationalError:
        pass  # column already exists
    con.commit()
    con.close()


def _db_save(demo_id: str, filename: str, map_name: str, data_dict: dict,
             ticks_by_round: dict = None):
    storable = dict(data_dict)
    storable["has_ticks"] = bool(ticks_by_round)
    # session_id is kept so _db_get can restore the cache entry
    ticks_blob = None
    if ticks_by_round:
        ticks_blob = sqlite3.Binary(
            zlib.compress(json.dumps(ticks_by_round, ensure_ascii=False).encode(), level=6)
        )
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "INSERT OR REPLACE INTO demos (id, filename, map, uploaded_at, data, ticks_data)"
        " VALUES (?,?,?,?,?,?)",
        (
            demo_id,
            filename,
            map_name,
            datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
            json.dumps(storable, ensure_ascii=False),
            ticks_blob,
        ),
    )
    con.commit()
    con.close()


def _db_list() -> list:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, filename, map, uploaded_at FROM demos ORDER BY uploaded_at DESC"
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def _db_get(demo_id: str):
    con = sqlite3.connect(DB_PATH)
    row = con.execute("SELECT data, ticks_data FROM demos WHERE id = ?", (demo_id,)).fetchone()
    con.close()
    if not row:
        return None
    data = json.loads(row[0])
    if row[1]:
        # Decompress and restore tick data to the session cache
        ticks_by_round = {
            int(k): v
            for k, v in json.loads(zlib.decompress(bytes(row[1])).decode()).items()
        }
        session_id = data.get("session_id")
        if session_id:
            if len(_session_cache) >= MAX_SESSIONS:
                _session_cache.popitem(last=False)
            _session_cache[session_id] = {
                "ticks":    ticks_by_round,
                "map_name": data.get("header", {}).get("map", ""),
            }
        data["has_ticks"] = True
    return data


def _db_delete(demo_id: str) -> bool:
    con = sqlite3.connect(DB_PATH)
    cur = con.execute("DELETE FROM demos WHERE id = ?", (demo_id,))
    con.commit()
    con.close()
    return cur.rowcount > 0


_db_init()

# ── Session cache for tick data (keep last 3 parsed demos in memory) ──────────
_session_cache = OrderedDict()
MAX_SESSIONS = 3
TICK_SAMPLE = 8   # keep 1 in every N ticks (~8-16 fps depending on tickrate)

# Hardcoded map bounds (pos_x, pos_y = top-left corner in game units; scale = units/pixel)
MAP_BOUNDS = {
    "de_dust2":    {"pos_x": -2476, "pos_y":  3239, "scale": 4.4},
    "de_mirage":   {"pos_x": -3230, "pos_y":  1713, "scale": 5.0},
    "de_inferno":  {"pos_x": -2087, "pos_y":  3870, "scale": 4.9},
    "de_nuke":     {"pos_x": -3453, "pos_y":  2887, "scale": 7.0},
    "de_ancient":  {"pos_x": -2953, "pos_y":  2164, "scale": 5.0},
    "de_anubis":   {"pos_x": -2796, "pos_y":  3328, "scale": 5.22},
    "de_vertigo":  {"pos_x": -3168, "pos_y":  1762, "scale": 4.0},
    "de_overpass": {"pos_x": -4831, "pos_y":  1781, "scale": 5.2},
}


def _to_pd(df):
    """Convert a Polars or pandas DataFrame to pandas, or return None if empty/missing."""
    if df is None:
        return None
    try:
        import polars as pl
        if isinstance(df, pl.DataFrame):
            return df.to_pandas() if not df.is_empty() else None
    except ImportError:
        pass
    try:
        if df.empty:
            return None
        return df
    except AttributeError:
        return None


def _col(row, *names, default=None):
    """Return the first non-null value among the given column names."""
    for name in names:
        try:
            v = row.get(name)
            if v is not None and str(v) != "nan":
                return v
        except Exception:
            pass
    return default


def _safe(val, default="?"):
    try:
        if val is None or (isinstance(val, float) and val != val):
            return default
        return val
    except Exception:
        return default


def _get_map_bounds(map_name: str) -> dict:
    """Return pos_x, pos_y, scale for the map. Tries awpy first, falls back to hardcoded."""
    try:
        from awpy.data import MAP_DATA
        if map_name in MAP_DATA:
            d = MAP_DATA[map_name]
            return {"pos_x": d["pos_x"], "pos_y": d["pos_y"], "scale": d["scale"]}
    except Exception:
        pass
    return MAP_BOUNDS.get(map_name, {"pos_x": -2476, "pos_y": 3239, "scale": 4.4})


def extract_ticks(demo) -> dict:
    """
    Returns {round_num: [{"t": tick, "p": [{"n": name, "x": x, "y": y, "hp": hp, "alive": bool, "side": side}]}]}
    Downsampled by TICK_SAMPLE for reasonable data size.
    """
    ticks_df = _to_pd(getattr(demo, "ticks", None))
    if ticks_df is None:
        return {}

    cols = list(ticks_df.columns)

    name_col  = next((c for c in ["name", "player_name", "steamid"] if c in cols), None)
    x_col     = next((c for c in ["X", "x", "pos_x"] if c in cols), None)
    y_col     = next((c for c in ["Y", "y", "pos_y"] if c in cols), None)
    hp_col    = next((c for c in ["health", "hp", "Health"] if c in cols), None)
    alive_col = next((c for c in ["is_alive", "alive", "isAlive"] if c in cols), None)
    side_col  = next((c for c in ["side", "team_side", "Side"] if c in cols), None)

    if not (name_col and x_col and y_col and "tick" in cols and "round_num" in cols):
        print(f"[WARN] Missing required tick columns — map tracker disabled")
        return {}

    import pandas as pd
    import numpy as np

    result = {}
    for round_num, rdf in ticks_df.groupby("round_num"):
        all_ticks = np.sort(rdf["tick"].unique())
        sampled   = set(all_ticks[::TICK_SAMPLE])
        sdf       = rdf[rdf["tick"].isin(sampled)].copy()

        frames = []
        for tick_val, tdf in sdf.groupby("tick"):
            players = []
            for _, row in tdf.iterrows():
                try:
                    hp = int(row[hp_col]) if hp_col and not pd.isna(row[hp_col]) else 100
                except Exception:
                    hp = 100
                try:
                    alive = bool(row[alive_col]) if alive_col and not pd.isna(row[alive_col]) else hp > 0
                except Exception:
                    alive = hp > 0
                try:
                    px = float(row[x_col]) if not pd.isna(row[x_col]) else 0.0
                    py = float(row[y_col]) if not pd.isna(row[y_col]) else 0.0
                except Exception:
                    px = py = 0.0
                players.append({
                    "n":     str(row[name_col]),
                    "x":     px,
                    "y":     py,
                    "hp":    hp,
                    "alive": alive,
                    "side":  str(row[side_col]) if side_col and not pd.isna(row.get(side_col, None)) else "?",
                })
            frames.append({"t": int(tick_val), "p": players})

        result[int(round_num)] = sorted(frames, key=lambda f: f["t"])

    return result


_HITGROUP = {
    # integer keys (older awpy / fallback)
    0: "Generic", 1: "Head", 2: "Chest", 3: "Stomach",
    4: "L Arm", 5: "R Arm", 6: "L Leg", 7: "R Leg",
    8: "Neck", 10: "Gear",
    # string keys (awpy v2)
    "generic": "Generic", "head": "Head", "chest": "Chest", "stomach": "Stomach",
    "left_arm": "L Arm", "right_arm": "R Arm", "left_leg": "L Leg", "right_leg": "R Leg",
    "neck": "Neck", "gear": "Gear",
}
_HITGROUP_ORDER = ["Head", "Neck", "Chest", "Stomach", "L Arm", "R Arm", "L Leg", "R Leg", "Gear", "Generic"]


def _calc_kast(kills: list, rounds: list) -> dict:
    """
    Returns {player_name: kast_pct} where KAST = % of rounds with a Kill,
    Assist, Survived, or Trade (killed within 5 s of being killed).
    """
    if not rounds:
        return {}
    total_rounds = len(rounds)
    round_nums   = {r["round_num"] for r in rounds}
    TRADE_TICKS  = 640  # ~5 s at 128 tick

    kills_by_round: dict = {}
    for k in kills:
        kills_by_round.setdefault(k["round_num"], []).append(k)

    # Collect every player name seen across kills
    _nan = {"?", "nan", ""}
    players: set = set()
    for k in kills:
        if k["attacker"]          not in _nan: players.add(k["attacker"])
        if k["victim"]            not in _nan: players.add(k["victim"])
        if k.get("assister", "") not in _nan: players.add(k["assister"])

    kast_count = {p: 0 for p in players}

    for rnum in round_nums:
        rk = kills_by_round.get(rnum, [])
        killers   = {k["attacker"] for k in rk if k["attacker"] not in _nan}
        assisters = {k["assister"] for k in rk if k.get("assister", "") not in _nan}
        victims   = {k["victim"]   for k in rk if k["victim"]   not in _nan}
        # map: killed player -> (their killer, tick they died)
        death_info = {k["victim"]: (k["attacker"], k["tick"]) for k in rk if k["victim"] not in _nan}

        for p in players:
            if p in killers or p in assisters:
                kast_count[p] += 1  # K or A
            elif p not in victims:
                kast_count[p] += 1  # S — survived
            else:
                # T — check if killer was killed within trade window
                killer, death_tick = death_info.get(p, (None, 0))
                if killer and killer in death_info:
                    _, killer_death_tick = death_info[killer]
                    if 0 <= killer_death_tick - death_tick <= TRADE_TICKS:
                        kast_count[p] += 1

    return {p: round(100 * kast_count[p] / total_rounds) for p in players}


def _extract_aim(kills: list, damages_df, rounds: list) -> list:
    """Per-player aim breakdown: hit groups, avg damage, per-weapon stats, KAST."""
    players: dict = {}

    if damages_df is not None:
        for _, row in damages_df.iterrows():
            att = row.get("attacker_name")
            vic = row.get("victim_name")
            if not att or str(att) == "nan" or str(att) == str(vic):
                continue  # skip self-damage
            att = str(att)
            dmg = int(row.get("dmg_health_real") or row.get("dmg_health") or 0)
            raw_hg = row.get("hitgroup") or 0
            hg_key = str(raw_hg).lower() if isinstance(raw_hg, str) else raw_hg
            hg  = _HITGROUP.get(hg_key, _HITGROUP.get(raw_hg, "Generic"))
            wpn = str(row.get("weapon") or "?")

            p = players.setdefault(att, {"hit_groups": {}, "dmg_groups": {}, "weapons": {}, "total_hits": 0, "total_dmg": 0})
            p["hit_groups"][hg]  = p["hit_groups"].get(hg, 0) + 1
            p["dmg_groups"][hg]  = p["dmg_groups"].get(hg, 0) + dmg
            p["total_hits"]     += 1
            p["total_dmg"]      += dmg
            w = p["weapons"].setdefault(wpn, {"hits": 0, "dmg": 0, "kills": 0, "hs_kills": 0})
            w["hits"] += 1
            w["dmg"]  += dmg

    for k in kills:
        att = k.get("attacker")
        if not att or att in ("nan", "?"):
            continue
        if att in players:
            wpn = k.get("weapon", "?")
            w = players[att]["weapons"].setdefault(wpn, {"hits": 0, "dmg": 0, "kills": 0, "hs_kills": 0})
            w["kills"] += 1
            if k.get("headshot"):
                w["hs_kills"] += 1

    kast = _calc_kast(kills, rounds)

    result = []
    for name, p in players.items():
        th = p["total_hits"]
        td = p["total_dmg"]
        weapons_sorted = sorted(
            [{"weapon": w, **s} for w, s in p["weapons"].items()],
            key=lambda x: x["kills"], reverse=True
        )
        result.append({
            "name":          name,
            "total_hits":    th,
            "total_dmg":     td,
            "avg_dmg":       round(td / th, 1) if th else 0,
            "hs_hit_pct":    round(100 * p["hit_groups"].get("Head", 0) / th) if th else 0,
            "kast":          kast.get(name, 0),
            "hit_groups":    p["hit_groups"],
            "dmg_groups":    p["dmg_groups"],
            "weapons":       weapons_sorted,
        })
    result.sort(key=lambda x: x["total_dmg"], reverse=True)
    return result


def parse_demo(dem_path: str) -> dict:
    from awpy import Demo

    demo = Demo(dem_path)
    demo.parse()

    # ---- Header ----
    h = demo.header or {}
    header = {
        "map":      _safe(h.get("map_name"), "unknown"),
        "tickrate": _safe(h.get("tick_rate"), "?"),
        "ticks":    _safe(h.get("ticks_played"), "?"),
        "client":   _safe(h.get("client_name"), "?"),
        "server":   _safe(h.get("server_name"), "?"),
        "duration": _duration(h),
    }

    # ---- Build per-round side mapping from kills ----
    kills_df = _to_pd(demo.kills)
    round_sides = {}
    ct_team = "CT"
    t_team  = "T"
    if kills_df is not None and "ct_side" in kills_df.columns:
        for _, row in kills_df.iterrows():
            rnum = int(row.get("round_num", 0) or 0)
            if rnum not in round_sides:
                round_sides[rnum] = {
                    "ct": str(row.get("ct_side") or "CT"),
                    "t":  str(row.get("t_side")  or "T"),
                }
        if round_sides:
            last   = round_sides[max(round_sides)]
            ct_team = last["ct"]
            t_team  = last["t"]

    # ---- Rounds ----
    rounds = []
    rounds_df = _to_pd(demo.rounds)
    if rounds_df is not None:
        ct_score = t_score = 0
        for _, row in rounds_df.iterrows():
            rnum   = int(row.get("round_num", 0) or 0)
            winner = str(row.get("winner", "?") or "?")
            sides  = round_sides.get(rnum, {"ct": ct_team, "t": t_team})
            if winner == sides["ct"]:
                winner_side = "CT"; ct_score += 1
            elif winner == sides["t"]:
                winner_side = "T";  t_score  += 1
            else:
                winner_side = winner
            reason = str(row.get("reason", "?") or "?").replace("_", " ").title()
            rounds.append({
                "round_num":   rnum,
                "winner_side": winner_side,
                "reason":      reason,
                "ct_score":    ct_score,
                "t_score":     t_score,
            })

    ct_wins = sum(1 for r in rounds if r["winner_side"] == "CT")
    t_wins  = sum(1 for r in rounds if r["winner_side"] == "T")

    # ---- Kills ----
    kills = []
    if kills_df is not None:
        for _, row in kills_df.iterrows():
            attacker_side = str(row.get("attacker_side") or "")
            victim_side   = str(row.get("victim_side")   or "")
            rnum          = int(row.get("round_num", 0) or 0)
            sides         = round_sides.get(rnum, {"ct": ct_team, "t": t_team})
            att_team = sides["ct"] if attacker_side.upper() == "CT" else sides["t"]
            vic_team = sides["ct"] if victim_side.upper()   == "CT" else sides["t"]
            kills.append({
                "tick":          int(row.get("tick", 0) or 0),
                "round_num":     rnum,
                "attacker":      str(row.get("attacker_name") or "?"),
                "attacker_team": att_team,
                "victim":        str(row.get("victim_name") or "?"),
                "victim_team":   vic_team,
                "weapon":        str(row.get("weapon") or "?"),
                "headshot":      bool(row.get("headshot")),
                "through_smoke": bool(row.get("thrusmoke")),
                "no_scope":      bool(row.get("noscope")),
                "penetrated":    bool(row.get("penetrated")),
                "assister":      str(row.get("assister_name") or ""),
            })

    # ---- Scoreboard ----
    stats: dict = {}

    def inc(player, key, amount=1):
        entry = stats.setdefault(player, {})
        entry[key] = entry.get(key, 0) + amount

    for k in kills:
        att, vic = k["attacker"], k["victim"]
        if att and att != "nan" and att != "?":
            inc(att, "kills")
            if k["headshot"]: inc(att, "hs")
            stats[att].setdefault("team", k["attacker_team"])
        if vic and vic != "nan" and vic != "?":
            inc(vic, "deaths")
            stats.setdefault(vic, {}).setdefault("team", k["victim_team"])

    damages_df = _to_pd(demo.damages)
    if damages_df is not None:
        for _, row in damages_df.iterrows():
            att = row.get("attacker_name")
            if att and str(att) != "nan":
                dmg = int(row.get("dmg_health_real") or row.get("dmg_health") or 0)
                inc(str(att), "dmg", dmg)

    # ---- Aim breakdown ----
    aim_breakdown = _extract_aim(kills, damages_df, rounds)

    scoreboard = []
    for player, s in stats.items():
        k_val  = s.get("kills", 0)
        d_val  = s.get("deaths", 0)
        hs_val = s.get("hs", 0)
        scoreboard.append({
            "name":    player,
            "team":    str(s.get("team", "?")),
            "kills":   k_val,
            "deaths":  d_val,
            "assists": s.get("assists", 0),
            "kd":      round(k_val / d_val, 2) if d_val else float(k_val),
            "hs_pct":  round(100 * hs_val / k_val) if k_val else 0,
            "dmg":     s.get("dmg", 0),
        })
    scoreboard.sort(key=lambda x: x["kills"], reverse=True)

    # ---- Tick data (player positions) ----
    session_id = str(uuid.uuid4())
    ticks_by_round = extract_ticks(demo)
    if len(_session_cache) >= MAX_SESSIONS:
        _session_cache.popitem(last=False)
    _session_cache[session_id] = {
        "ticks":    ticks_by_round,
        "map_name": header["map"],
    }

    return {
        "header":        header,
        "ct_team":       ct_team,
        "t_team":        t_team,
        "ct_wins":       ct_wins,
        "t_wins":        t_wins,
        "total_rounds":  len(rounds),
        "rounds":        rounds,
        "kills":         kills,
        "scoreboard":    scoreboard,
        "aim_breakdown": aim_breakdown,
        "session_id":    session_id,
        "has_ticks":     bool(ticks_by_round),
    }


def _duration(h: dict) -> str:
    try:
        return f"{float(h['playback_time']):.1f}s"
    except Exception:
        try:
            return f"{int(h['ticks_played']) / int(h['tick_rate']):.1f}s"
        except Exception:
            return "?"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/viewer")
def viewer():
    return render_template("viewer.html")


@app.route("/api/parse", methods=["POST"])
def api_parse():
    if "demo" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    f = request.files["demo"]
    if not f.filename.lower().endswith(".dem"):
        return jsonify({"error": "File must be a .dem file"}), 400

    with tempfile.NamedTemporaryFile(suffix=".dem", delete=False) as tmp:
        tmp_path = tmp.name
        f.save(tmp_path)

    try:
        data = parse_demo(tmp_path)
        data["filename"] = f.filename
        ticks = _session_cache.get(data["session_id"], {}).get("ticks", {})
        _db_save(data["session_id"], f.filename, data["header"]["map"], data, ticks)
        return jsonify(data)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


@app.route("/api/ticks/<session_id>/<int:round_num>")
def api_ticks(session_id, round_num):
    session = _session_cache.get(session_id)
    if not session:
        return jsonify({"error": "Session expired — please re-upload the demo"}), 404
    frames = session["ticks"].get(round_num, [])
    return jsonify({"frames": frames, "count": len(frames)})


@app.route("/api/map_info/<map_name>")
def api_map_info(map_name):
    return jsonify(_get_map_bounds(map_name))


@app.route("/api/maps_ready")
def api_maps_ready():
    import awpy.data
    maps_dir = awpy.data.MAPS_DIR
    ready = maps_dir.exists() and any(maps_dir.glob("*.png"))
    return jsonify({"ready": ready})


@app.route("/api/download_maps", methods=["POST"])
def api_download_maps():
    try:
        import awpy.data, awpy.data.utils
        awpy.data.utils.create_data_dir_if_not_exists()
        awpy.data.utils.fetch_resource("maps", awpy.data.CURRENT_BUILD_ID)
        return jsonify({"success": True})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/map_image/<map_name>")
def api_map_image(map_name):
    import awpy.data
    maps_dir = awpy.data.MAPS_DIR
    for name in [map_name, f"{map_name}_lower"]:
        img_path = maps_dir / f"{name}.png"
        if img_path.exists():
            return send_file(str(img_path), mimetype="image/png")
    return "", 404


@app.route("/api/demos")
def api_demos_list():
    return jsonify(_db_list())


@app.route("/api/demos/<demo_id>")
def api_demos_get(demo_id):
    data = _db_get(demo_id)
    if data is None:
        return jsonify({"error": "Demo not found"}), 404
    return jsonify(data)


@app.route("/api/demos/<demo_id>", methods=["DELETE"])
def api_demos_delete(demo_id):
    if _db_delete(demo_id):
        return jsonify({"deleted": demo_id})
    return jsonify({"error": "Demo not found"}), 404


@app.route("/admin")
def admin():
    return render_template("admin.html")


@app.route("/api/admin/query", methods=["POST"])
def api_admin_query():
    sql = (request.json or {}).get("sql", "").strip()
    if not sql:
        return jsonify({"error": "No query provided"}), 400
    try:
        import time
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
        t0 = time.monotonic()
        cur = con.execute(sql)
        elapsed = round((time.monotonic() - t0) * 1000, 2)
        if cur.description:
            columns = [d[0] for d in cur.description]
            rows = [list(r) for r in cur.fetchall()]
            con.close()
            return jsonify({"columns": columns, "rows": rows,
                            "rowcount": len(rows), "elapsed_ms": elapsed})
        else:
            con.commit()
            rowcount = cur.rowcount
            con.close()
            return jsonify({"columns": [], "rows": [],
                            "rowcount": rowcount, "elapsed_ms": elapsed,
                            "message": f"{rowcount} row(s) affected"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/admin/schema")
def api_admin_schema():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    tables = [r["name"] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()]
    schema = {}
    for tbl in tables:
        cols = con.execute(f"PRAGMA table_info({tbl})").fetchall()
        schema[tbl] = [{"cid": c["cid"], "name": c["name"], "type": c["type"],
                        "notnull": c["notnull"], "pk": c["pk"]} for c in cols]
    con.close()
    return jsonify(schema)


if __name__ == "__main__":
    app.run(debug=True, port=5000, threaded=True)
