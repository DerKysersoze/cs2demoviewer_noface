#!/usr/bin/env python3
"""
CS2 Demo Viewer - Web Backend
Run: python app.py
Then open http://localhost:5000
"""

import argparse
import datetime
import json
import logging
import os
import sqlite3
import time
import zlib
import tempfile
import traceback
import uuid
from collections import OrderedDict
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request, send_file

# ── Logging setup ──────────────────────────────────────────────────────────────
# Enabled only when launched with --verbose.
# Use parse_known_args so Flask's own argv flags are not rejected.
_ap = argparse.ArgumentParser(add_help=False)
_ap.add_argument("--verbose", action="store_true", help="Enable verbose logging to core.log")
_args, _ = _ap.parse_known_args()
_verbose = _args.verbose

_LOG_PATH = Path(__file__).parent / "core.log"
log = logging.getLogger("cs2viewer")

if _verbose:
    _fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    _fh = logging.FileHandler(_LOG_PATH, encoding="utf-8")
    _fh.setFormatter(_fmt)
    _sh = logging.StreamHandler()
    _sh.setFormatter(_fmt)
    log.setLevel(logging.DEBUG)
    log.addHandler(_fh)
    log.addHandler(_sh)
else:
    log.addHandler(logging.NullHandler())

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024  # 512 MB


@app.before_request
def _before():
    g._req_t0 = time.monotonic()


@app.after_request
def _after(response):
    elapsed_ms = round((time.monotonic() - g._req_t0) * 1000, 1)
    log.debug("HTTP %s %s %s — %sms", request.method, request.path,
              response.status_code, elapsed_ms)
    return response


# ── SQLite demo history ────────────────────────────────────────────────────────
DB_PATH       = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demos.db")
STRUCT_DB_DIR = Path(__file__).parent / "struct_db"




def _blob(obj) -> sqlite3.Binary:
    return sqlite3.Binary(zlib.compress(json.dumps(obj, ensure_ascii=False).encode(), level=6))


def _unblob(raw) -> object:
    return json.loads(zlib.decompress(bytes(raw)).decode())


def _cosmetics_insert_rows(con, demo_id: str, swag: list):
    """Insert swag_breakdown items for one demo into demo_cosmetics."""
    for player in swag:
        sid  = player.get("steamid")
        name = player.get("name")
        team = player.get("team")
        seen: set = set()
        all_items: list = []
        for item in (
            ([player["ct_agent"]] if player.get("ct_agent") else [])
            + ([player["t_agent"]] if player.get("t_agent") else [])
            + player.get("ct_weapons", [])
            + player.get("t_weapons", [])
        ):
            key = (item.get("def_index"), item.get("paint_index"), item.get("paint_seed"))
            if key not in seen:
                seen.add(key)
                all_items.append(item)
        for item in all_items:
            con.execute(
                """INSERT INTO demo_cosmetics
                   (demo_id, steamid, player_name, team,
                    def_index, item_name, skin_name, paint_index, paint_seed,
                    wear, wear_tier, custom_name, stattrak, is_agent, side)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    demo_id, sid, name, team,
                    item.get("def_index"), item.get("item_name"), item.get("skin_name"),
                    item.get("paint_index"), item.get("paint_seed"),
                    item.get("wear"), item.get("wear_tier"), item.get("custom_name"),
                    item.get("stattrak"), int(bool(item.get("is_agent"))),
                    item.get("side"),
                ),
            )


def _cosmetics_to_swag(rows) -> list:
    """Reconstruct swag_breakdown list from demo_cosmetics rows."""
    players: dict = OrderedDict()
    for r in rows:
        sid = r["steamid"] or ""
        key = (sid, r["player_name"] or "")
        if key not in players:
            players[key] = {
                "steamid":    sid,
                "name":       r["player_name"],
                "team":       r["team"],
                "ct_agent":   None,
                "t_agent":    None,
                "ct_weapons": [],
                "t_weapons":  [],
            }
        p = players[key]
        item = {
            "def_index":   r["def_index"],
            "item_name":   r["item_name"],
            "skin_name":   r["skin_name"],
            "paint_index": r["paint_index"],
            "paint_seed":  r["paint_seed"],
            "wear":        r["wear"],
            "wear_tier":   r["wear_tier"],
            "custom_name": r["custom_name"],
            "stattrak":    r["stattrak"],
            "is_agent":    bool(r["is_agent"]),
            "side":        r["side"],
            "weapon_cat":  "knife" if r["def_index"] in _KNIFE_DEF_INDICES else None,
        }
        if item["is_agent"]:
            if r["side"] == "T":
                p["t_agent"] = item
            else:
                p["ct_agent"] = item
        elif r["side"] == "T":
            p["t_weapons"].append(item)
        else:
            p["ct_weapons"].append(item)
    return list(players.values())


_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS demos (
    id            TEXT    PRIMARY KEY,
    filename      TEXT    NOT NULL,
    map           TEXT    NOT NULL,
    uploaded_at   TEXT    NOT NULL,
    tickrate      TEXT,
    duration      TEXT,
    ct_team       TEXT,
    t_team        TEXT,
    ct_wins       INTEGER,
    t_wins        INTEGER,
    total_rounds  INTEGER,
    has_ticks     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS demo_cosmetics (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    demo_id      TEXT    NOT NULL,
    steamid      TEXT,
    player_name  TEXT,
    team         TEXT,
    def_index    INTEGER,
    item_name    TEXT,
    skin_name    TEXT,
    paint_index  INTEGER,
    paint_seed   INTEGER,
    wear         REAL,
    wear_tier    TEXT,
    custom_name  TEXT,
    stattrak     INTEGER,
    is_agent     INTEGER,
    side         TEXT,
    FOREIGN KEY (demo_id) REFERENCES demos(id)
);
CREATE INDEX IF NOT EXISTS idx_demo_cosmetics_demo_id ON demo_cosmetics(demo_id);

CREATE TABLE IF NOT EXISTS demo_rounds (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    demo_id     TEXT    NOT NULL,
    round_num   INTEGER,
    winner_side TEXT,
    reason      TEXT,
    ct_score    INTEGER,
    t_score     INTEGER,
    FOREIGN KEY (demo_id) REFERENCES demos(id)
);
CREATE INDEX IF NOT EXISTS idx_demo_rounds_demo_id ON demo_rounds(demo_id);

CREATE TABLE IF NOT EXISTS demo_kills (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    demo_id       TEXT    NOT NULL,
    round_num     INTEGER,
    tick          INTEGER,
    attacker      TEXT,
    attacker_team TEXT,
    victim        TEXT,
    victim_team   TEXT,
    weapon        TEXT,
    headshot      INTEGER,
    through_smoke INTEGER,
    no_scope      INTEGER,
    penetrated    INTEGER,
    assister      TEXT,
    FOREIGN KEY (demo_id) REFERENCES demos(id)
);
CREATE INDEX IF NOT EXISTS idx_demo_kills_demo_id ON demo_kills(demo_id);

CREATE TABLE IF NOT EXISTS demo_scoreboard (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    demo_id     TEXT    NOT NULL,
    player_name TEXT,
    steamid     TEXT,
    team        TEXT,
    kills       INTEGER,
    deaths      INTEGER,
    assists     INTEGER,
    kd          REAL,
    hs_pct      INTEGER,
    dmg         INTEGER,
    FOREIGN KEY (demo_id) REFERENCES demos(id)
);
CREATE INDEX IF NOT EXISTS idx_demo_scoreboard_demo_id ON demo_scoreboard(demo_id);

CREATE TABLE IF NOT EXISTS demo_aim (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    demo_id     TEXT    NOT NULL,
    player_name TEXT,
    total_hits  INTEGER,
    total_shots INTEGER,
    accuracy    INTEGER,
    total_dmg   INTEGER,
    avg_dmg     REAL,
    hs_hit_pct  INTEGER,
    kast        INTEGER,
    FOREIGN KEY (demo_id) REFERENCES demos(id)
);
CREATE INDEX IF NOT EXISTS idx_demo_aim_demo_id ON demo_aim(demo_id);

CREATE TABLE IF NOT EXISTS demo_aim_weapons (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    demo_id     TEXT    NOT NULL,
    player_name TEXT,
    weapon      TEXT,
    hits        INTEGER,
    dmg         INTEGER,
    kills       INTEGER,
    hs_kills    INTEGER,
    shots       INTEGER,
    FOREIGN KEY (demo_id) REFERENCES demos(id)
);
CREATE INDEX IF NOT EXISTS idx_demo_aim_weapons_demo_id ON demo_aim_weapons(demo_id);

CREATE TABLE IF NOT EXISTS demo_aim_hitgroups (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    demo_id     TEXT    NOT NULL,
    player_name TEXT,
    hit_group   TEXT,
    hits        INTEGER,
    dmg         INTEGER,
    FOREIGN KEY (demo_id) REFERENCES demos(id)
);
CREATE INDEX IF NOT EXISTS idx_demo_aim_hitgroups_demo_id ON demo_aim_hitgroups(demo_id);

CREATE TABLE IF NOT EXISTS demo_ticks (
    demo_id    TEXT PRIMARY KEY,
    ticks_data BLOB NOT NULL,
    FOREIGN KEY (demo_id) REFERENCES demos(id)
);
"""


def _db_init():
    log.info("DB: initialising — %s", DB_PATH)
    con = sqlite3.connect(DB_PATH)
    con.executescript(_DB_SCHEMA)

    # ---- Drop stale reference/struct tables from old schema ----
    stale_tables = {
        "skin_names", "skins", "inventory", "agents", "base_weapons", "collectibles",
        "collections", "crates", "graffiti", "highlights", "keychains",
        "keys", "music_kits", "patches", "skins_not_grouped",
        "sticker_slabs", "stickers", "tools",
    }
    existing = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    for tbl in stale_tables & existing:
        con.execute(f"DROP TABLE {tbl}")
        log.info("DB: dropped stale table %s", tbl)

    # ---- Migrate old weapon_cat column from demo_cosmetics ----
    dc_cols = {r[1] for r in con.execute("PRAGMA table_info(demo_cosmetics)").fetchall()}
    if "weapon_cat" in dc_cols:
        con.execute("ALTER TABLE demo_cosmetics DROP COLUMN weapon_cat")
        log.info("DB: dropped demo_cosmetics.weapon_cat")

    # ---- Migrate old swag_breakdown BLOB → demo_cosmetics rows ----
    cols = {r[1] for r in con.execute("PRAGMA table_info(demos)").fetchall()}
    if "swag_breakdown" in cols:
        log.info("DB: migrating swag_breakdown blobs → demo_cosmetics…")
        blob_rows = con.execute(
            "SELECT id, swag_breakdown FROM demos WHERE swag_breakdown IS NOT NULL"
        ).fetchall()
        migrated = 0
        for demo_id, blob in blob_rows:
            if con.execute(
                "SELECT 1 FROM demo_cosmetics WHERE demo_id = ? LIMIT 1", (demo_id,)
            ).fetchone():
                continue
            try:
                _cosmetics_insert_rows(con, demo_id, _unblob(blob))
                migrated += 1
            except Exception as e:
                log.warning("DB: swag migration failed for %s: %s", demo_id, e)
        con.execute("ALTER TABLE demos DROP COLUMN swag_breakdown")
        log.info("DB: migrated swag blobs for %d demos; dropped column", migrated)
        cols = {r[1] for r in con.execute("PRAGMA table_info(demos)").fetchall()}

    # ---- Migrate BLOB columns → relational tables ----
    if "rounds" in cols:
        log.info("DB: migrating BLOB columns → relational tables…")
        demo_rows = con.execute(
            "SELECT id, rounds, kills, scoreboard, aim_breakdown, ticks_data FROM demos"
        ).fetchall()
        migrated = 0
        for demo_id, r_blob, k_blob, sb_blob, aim_blob, ticks_blob in demo_rows:
            try:
                if r_blob:
                    rounds = _unblob(r_blob)
                    con.executemany(
                        "INSERT INTO demo_rounds (demo_id,round_num,winner_side,reason,ct_score,t_score)"
                        " VALUES (?,?,?,?,?,?)",
                        [(demo_id, r["round_num"], r["winner_side"], r.get("reason"),
                          r.get("ct_score"), r.get("t_score")) for r in rounds],
                    )
                if k_blob:
                    kills = _unblob(k_blob)
                    con.executemany(
                        "INSERT INTO demo_kills"
                        " (demo_id,round_num,tick,attacker,attacker_team,victim,victim_team,"
                        "  weapon,headshot,through_smoke,no_scope,penetrated,assister)"
                        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        [(demo_id, k["round_num"], k.get("tick"), k.get("attacker"),
                          k.get("attacker_team"), k.get("victim"), k.get("victim_team"),
                          k.get("weapon"), int(bool(k.get("headshot"))),
                          int(bool(k.get("through_smoke"))), int(bool(k.get("no_scope"))),
                          int(bool(k.get("penetrated"))), k.get("assister")) for k in kills],
                    )
                if sb_blob:
                    scoreboard = _unblob(sb_blob)
                    con.executemany(
                        "INSERT INTO demo_scoreboard"
                        " (demo_id,player_name,steamid,team,kills,deaths,assists,kd,hs_pct,dmg)"
                        " VALUES (?,?,?,?,?,?,?,?,?,?)",
                        [(demo_id, s["name"], s.get("steamid"), s.get("team"),
                          s.get("kills"), s.get("deaths"), s.get("assists"),
                          s.get("kd"), s.get("hs_pct"), s.get("dmg")) for s in scoreboard],
                    )
                if aim_blob:
                    aim = _unblob(aim_blob)
                    for a in aim:
                        con.execute(
                            "INSERT INTO demo_aim"
                            " (demo_id,player_name,total_hits,total_shots,accuracy,"
                            "  total_dmg,avg_dmg,hs_hit_pct,kast)"
                            " VALUES (?,?,?,?,?,?,?,?,?)",
                            (demo_id, a["name"], a.get("total_hits"), a.get("total_shots"),
                             a.get("accuracy"), a.get("total_dmg"), a.get("avg_dmg"),
                             a.get("hs_hit_pct"), a.get("kast")),
                        )
                        for w in a.get("weapons", []):
                            con.execute(
                                "INSERT INTO demo_aim_weapons"
                                " (demo_id,player_name,weapon,hits,dmg,kills,hs_kills,shots)"
                                " VALUES (?,?,?,?,?,?,?,?)",
                                (demo_id, a["name"], w["weapon"], w.get("hits"),
                                 w.get("dmg"), w.get("kills"), w.get("hs_kills"), w.get("shots")),
                            )
                        for hg, cnt in (a.get("hit_groups") or {}).items():
                            dmg = (a.get("dmg_groups") or {}).get(hg, 0)
                            con.execute(
                                "INSERT INTO demo_aim_hitgroups"
                                " (demo_id,player_name,hit_group,hits,dmg)"
                                " VALUES (?,?,?,?,?)",
                                (demo_id, a["name"], hg, cnt, dmg),
                            )
                if ticks_blob:
                    con.execute(
                        "INSERT OR IGNORE INTO demo_ticks (demo_id, ticks_data) VALUES (?,?)",
                        (demo_id, ticks_blob),
                    )
                migrated += 1
            except Exception as e:
                log.warning("DB: blob migration failed for %s: %s", demo_id, e)

        for col in ("rounds", "kills", "scoreboard", "aim_breakdown", "ticks_data", "session_id"):
            if col in cols:
                con.execute(f"ALTER TABLE demos DROP COLUMN {col}")
        log.info("DB: migrated %d demos from BLOBs to relational tables", migrated)

    elif "session_id" in cols:
        con.execute("ALTER TABLE demos DROP COLUMN session_id")
        log.info("DB: dropped demos.session_id")

    # ---- Fix item_name from struct_db JSON (corrects wrong knife names from old hardcoded dict) ----
    fix_lookup: dict = {}
    for _p, _is_agent in ((STRUCT_DB_DIR / "base_weapons.json", False),
                          (STRUCT_DB_DIR / "agents.json",       True)):
        if _p.exists():
            try:
                with open(_p, encoding="utf-8") as _f:
                    for _item in json.load(_f):
                        _di = _item.get("def_index")
                        _nm = _item.get("name")
                        if _di is not None and _nm:
                            if _is_agent:
                                _nm = _nm.split(" | ")[0]
                            fix_lookup[int(_di)] = _nm
            except Exception as _e:
                log.warning("DB: item_name fix: failed to load %s: %s", _p.name, _e)
    if fix_lookup:
        fixed = sum(
            con.execute(
                "UPDATE demo_cosmetics SET item_name = ? WHERE def_index = ? AND (item_name != ? OR item_name IS NULL)",
                (nm, di, nm),
            ).rowcount
            for di, nm in fix_lookup.items()
        )
        if fixed:
            log.info("DB: corrected %d demo_cosmetics.item_name rows from struct_db JSON", fixed)

    con.commit()
    con.close()
    log.info("DB: schema ready")


def _db_save(demo_id: str, filename: str, map_name: str, data_dict: dict,
             ticks_by_round: dict = None):
    h = data_dict.get("header") or {}
    has_ticks = bool(ticks_by_round)
    log.info("db_save: starting — demo_id=%s filename=%s map=%s", demo_id, filename, map_name)
    con = sqlite3.connect(DB_PATH)

    # ---- demos (metadata only) ----
    con.execute(
        "INSERT OR REPLACE INTO demos"
        " (id,filename,map,uploaded_at,tickrate,duration,ct_team,t_team,"
        "  ct_wins,t_wins,total_rounds,has_ticks)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            demo_id, filename, map_name,
            datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
            h.get("tickrate"), h.get("duration"),
            data_dict.get("ct_team"), data_dict.get("t_team"),
            data_dict.get("ct_wins"), data_dict.get("t_wins"),
            data_dict.get("total_rounds"), int(has_ticks),
        ),
    )

    # ---- demo_rounds ----
    con.execute("DELETE FROM demo_rounds WHERE demo_id = ?", (demo_id,))
    rounds = data_dict.get("rounds") or []
    if rounds:
        con.executemany(
            "INSERT INTO demo_rounds (demo_id,round_num,winner_side,reason,ct_score,t_score)"
            " VALUES (?,?,?,?,?,?)",
            [(demo_id, r["round_num"], r["winner_side"], r.get("reason"),
              r.get("ct_score"), r.get("t_score")) for r in rounds],
        )

    # ---- demo_kills ----
    con.execute("DELETE FROM demo_kills WHERE demo_id = ?", (demo_id,))
    kills = data_dict.get("kills") or []
    if kills:
        con.executemany(
            "INSERT INTO demo_kills"
            " (demo_id,round_num,tick,attacker,attacker_team,victim,victim_team,"
            "  weapon,headshot,through_smoke,no_scope,penetrated,assister)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(demo_id, k["round_num"], k.get("tick"), k.get("attacker"),
              k.get("attacker_team"), k.get("victim"), k.get("victim_team"),
              k.get("weapon"), int(bool(k.get("headshot"))),
              int(bool(k.get("through_smoke"))), int(bool(k.get("no_scope"))),
              int(bool(k.get("penetrated"))), k.get("assister")) for k in kills],
        )

    # ---- demo_scoreboard ----
    con.execute("DELETE FROM demo_scoreboard WHERE demo_id = ?", (demo_id,))
    scoreboard = data_dict.get("scoreboard") or []
    if scoreboard:
        con.executemany(
            "INSERT INTO demo_scoreboard"
            " (demo_id,player_name,steamid,team,kills,deaths,assists,kd,hs_pct,dmg)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            [(demo_id, s["name"], s.get("steamid"), s.get("team"),
              s.get("kills"), s.get("deaths"), s.get("assists"),
              s.get("kd"), s.get("hs_pct"), s.get("dmg")) for s in scoreboard],
        )

    # ---- demo_aim + demo_aim_weapons + demo_aim_hitgroups ----
    con.execute("DELETE FROM demo_aim WHERE demo_id = ?", (demo_id,))
    con.execute("DELETE FROM demo_aim_weapons WHERE demo_id = ?", (demo_id,))
    con.execute("DELETE FROM demo_aim_hitgroups WHERE demo_id = ?", (demo_id,))
    for a in (data_dict.get("aim_breakdown") or []):
        con.execute(
            "INSERT INTO demo_aim"
            " (demo_id,player_name,total_hits,total_shots,accuracy,"
            "  total_dmg,avg_dmg,hs_hit_pct,kast)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (demo_id, a["name"], a.get("total_hits"), a.get("total_shots"),
             a.get("accuracy"), a.get("total_dmg"), a.get("avg_dmg"),
             a.get("hs_hit_pct"), a.get("kast")),
        )
        if a.get("weapons"):
            con.executemany(
                "INSERT INTO demo_aim_weapons"
                " (demo_id,player_name,weapon,hits,dmg,kills,hs_kills,shots)"
                " VALUES (?,?,?,?,?,?,?,?)",
                [(demo_id, a["name"], w["weapon"], w.get("hits"),
                  w.get("dmg"), w.get("kills"), w.get("hs_kills"), w.get("shots"))
                 for w in a["weapons"]],
            )
        hit_groups = a.get("hit_groups") or {}
        dmg_groups = a.get("dmg_groups") or {}
        if hit_groups:
            con.executemany(
                "INSERT INTO demo_aim_hitgroups (demo_id,player_name,hit_group,hits,dmg)"
                " VALUES (?,?,?,?,?)",
                [(demo_id, a["name"], hg, cnt, dmg_groups.get(hg, 0))
                 for hg, cnt in hit_groups.items()],
            )

    # ---- demo_ticks ----
    con.execute("DELETE FROM demo_ticks WHERE demo_id = ?", (demo_id,))
    if ticks_by_round:
        con.execute(
            "INSERT INTO demo_ticks (demo_id, ticks_data) VALUES (?,?)",
            (demo_id, _blob(ticks_by_round)),
        )

    # ---- demo_cosmetics ----
    con.execute("DELETE FROM demo_cosmetics WHERE demo_id = ?", (demo_id,))
    swag = data_dict.get("swag_breakdown")
    log.info("db_save: swag_breakdown players=%s", len(swag) if swag else 0)
    if swag:
        _cosmetics_insert_rows(con, demo_id, swag)

    con.commit()
    log.info("db_save: committed — demo_id=%s", demo_id)
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
    con.row_factory = sqlite3.Row
    row = con.execute("SELECT * FROM demos WHERE id = ?", (demo_id,)).fetchone()
    if not row:
        con.close()
        return None

    rounds_rows    = con.execute(
        "SELECT * FROM demo_rounds WHERE demo_id = ? ORDER BY round_num", (demo_id,)
    ).fetchall()
    kills_rows     = con.execute(
        "SELECT * FROM demo_kills WHERE demo_id = ? ORDER BY round_num, tick", (demo_id,)
    ).fetchall()
    sb_rows        = con.execute(
        "SELECT * FROM demo_scoreboard WHERE demo_id = ?", (demo_id,)
    ).fetchall()
    aim_rows       = con.execute(
        "SELECT * FROM demo_aim WHERE demo_id = ?", (demo_id,)
    ).fetchall()
    aim_wpn_rows   = con.execute(
        "SELECT * FROM demo_aim_weapons WHERE demo_id = ?", (demo_id,)
    ).fetchall()
    aim_hg_rows    = con.execute(
        "SELECT * FROM demo_aim_hitgroups WHERE demo_id = ?", (demo_id,)
    ).fetchall()
    cosmetic_rows  = con.execute(
        "SELECT * FROM demo_cosmetics WHERE demo_id = ? ORDER BY id", (demo_id,)
    ).fetchall()
    ticks_row      = con.execute(
        "SELECT ticks_data FROM demo_ticks WHERE demo_id = ?", (demo_id,)
    ).fetchone()
    con.close()

    # Reconstruct rounds
    rounds = [dict(r) for r in rounds_rows]

    # Reconstruct kills
    kills = [dict(r) for r in kills_rows]
    for k in kills:
        k["headshot"]      = bool(k["headshot"])
        k["through_smoke"] = bool(k["through_smoke"])
        k["no_scope"]      = bool(k["no_scope"])
        k["penetrated"]    = bool(k["penetrated"])
        k.pop("id", None)
        k.pop("demo_id", None)

    # Reconstruct scoreboard
    scoreboard = [dict(r) for r in sb_rows]
    for s in scoreboard:
        s["name"] = s.pop("player_name", s.get("name"))
        s.pop("id", None)
        s.pop("demo_id", None)

    # Reconstruct aim_breakdown (group weapons and hitgroups per player)
    wpn_by_player: dict = {}
    for r in aim_wpn_rows:
        wpn_by_player.setdefault(r["player_name"], []).append({
            "weapon":   r["weapon"],
            "hits":     r["hits"],
            "dmg":      r["dmg"],
            "kills":    r["kills"],
            "hs_kills": r["hs_kills"],
            "shots":    r["shots"],
        })
    hg_by_player: dict = {}
    for r in aim_hg_rows:
        hg_by_player.setdefault(r["player_name"], {"hit_groups": {}, "dmg_groups": {}})
        hg_by_player[r["player_name"]]["hit_groups"][r["hit_group"]] = r["hits"]
        hg_by_player[r["player_name"]]["dmg_groups"][r["hit_group"]] = r["dmg"]
    aim_breakdown = []
    for r in aim_rows:
        pname = r["player_name"]
        hg = hg_by_player.get(pname, {"hit_groups": {}, "dmg_groups": {}})
        aim_breakdown.append({
            "name":        pname,
            "total_hits":  r["total_hits"],
            "total_shots": r["total_shots"],
            "accuracy":    r["accuracy"],
            "total_dmg":   r["total_dmg"],
            "avg_dmg":     r["avg_dmg"],
            "hs_hit_pct":  r["hs_hit_pct"],
            "kast":        r["kast"],
            "hit_groups":  hg["hit_groups"],
            "dmg_groups":  hg["dmg_groups"],
            "weapons":     wpn_by_player.get(pname, []),
        })

    data = {
        "header": {
            "map":      row["map"],
            "tickrate": row["tickrate"],
            "duration": row["duration"],
        },
        "ct_team":       row["ct_team"],
        "t_team":        row["t_team"],
        "ct_wins":       row["ct_wins"],
        "t_wins":        row["t_wins"],
        "total_rounds":  row["total_rounds"],
        "session_id":    demo_id,
        "has_ticks":     bool(row["has_ticks"]),
        "filename":      row["filename"],
        "rounds":        rounds,
        "kills":         kills,
        "scoreboard":    scoreboard,
        "aim_breakdown": aim_breakdown,
        "swag_breakdown": _cosmetics_to_swag(cosmetic_rows),
    }

    if ticks_row and ticks_row["ticks_data"]:
        ticks_by_round = {int(k): v for k, v in _unblob(ticks_row["ticks_data"]).items()}
        if len(_session_cache) >= MAX_SESSIONS:
            _session_cache.popitem(last=False)
        _session_cache[demo_id] = {
            "ticks":    ticks_by_round,
            "map_name": row["map"],
        }
        data["has_ticks"] = True

    return data


def _db_delete(demo_id: str) -> bool:
    con = sqlite3.connect(DB_PATH)
    for tbl in ("demo_rounds", "demo_kills", "demo_scoreboard", "demo_aim",
                "demo_aim_weapons", "demo_aim_hitgroups", "demo_ticks", "demo_cosmetics"):
        con.execute(f"DELETE FROM {tbl} WHERE demo_id = ?", (demo_id,))
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


def extract_ticks(demo, dem_path=None) -> dict:
    """
    Returns {round_num: [{"t": tick, "p": [{"n": name, "x": x, "y": y, "hp": hp, "alive": bool, "side": side}]}]}
    Downsampled by TICK_SAMPLE for reasonable data size.
    """
    ticks_df = _to_pd(getattr(demo, "ticks", None))
    if ticks_df is None:
        return {}

    cols = list(ticks_df.columns)
    log.info("extract_ticks columns: %s", cols)

    # Augment with armor/helmet via a second demoparser2 pass
    if dem_path:
        try:
            from demoparser2 import DemoParser
            armor_df = DemoParser(dem_path).parse_ticks(["armor_value", "has_helmet"])
            if armor_df is not None:
                merge_on = [c for c in ["tick", "steamid"] if c in armor_df.columns and c in ticks_df.columns]
                extra    = [c for c in ["armor_value", "has_helmet"] if c in armor_df.columns]
                if merge_on and extra:
                    ticks_df = ticks_df.merge(armor_df[merge_on + extra], on=merge_on, how="left")
                    cols = list(ticks_df.columns)
                    log.info("extract_ticks columns after armor merge: %s", cols)
        except Exception as e:
            log.warning("extract_ticks: armor merge failed — %s", e)

    name_col   = next((c for c in ["name", "player_name", "steamid"] if c in cols), None)
    x_col      = next((c for c in ["X", "x", "pos_x"] if c in cols), None)
    y_col      = next((c for c in ["Y", "y", "pos_y"] if c in cols), None)
    hp_col     = next((c for c in ["health", "hp", "Health"] if c in cols), None)
    alive_col  = next((c for c in ["is_alive", "alive", "isAlive"] if c in cols), None)
    side_col   = next((c for c in ["side", "team_side", "Side"] if c in cols), None)
    armor_col  = next((c for c in ["armor", "armor_value", "kevlar"] if c in cols), None)
    helmet_col = next((c for c in ["has_helmet", "helmet"] if c in cols), None)

    if not (name_col and x_col and y_col and "tick" in cols and "round_num" in cols):
        log.warning("missing required tick columns — map tracker disabled")
        return {}

    import pandas as pd
    import numpy as np

    ROUND_START_SKIP = 160  # freeze-time / buy-phase ticks to skip each round

    result = {}
    for round_num, rdf in ticks_df.groupby("round_num"):
        all_ticks = np.sort(rdf["tick"].unique())
        if len(all_ticks) > ROUND_START_SKIP:
            all_ticks = all_ticks[ROUND_START_SKIP:]
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
                try:
                    armor = int(row[armor_col]) if armor_col and not pd.isna(row[armor_col]) else 0
                except Exception:
                    armor = 0
                try:
                    helmet = bool(row[helmet_col]) if helmet_col and not pd.isna(row[helmet_col]) else False
                except Exception:
                    helmet = False
                players.append({
                    "n":      str(row[name_col]),
                    "x":      px,
                    "y":      py,
                    "hp":     hp,
                    "alive":  alive,
                    "side":   str(row[side_col]) if side_col and not pd.isna(row.get(side_col, None)) else "?",
                    "armor":  armor,
                    "helmet": helmet,
                })
            frames.append({"t": int(tick_val), "p": players})

        result[int(round_num)] = sorted(frames, key=lambda f: f["t"])

    return result


def _build_item_lookups() -> tuple:
    """
    Load weapon/knife names from base_weapons.json and agent names+sides from agents.json.
    Returns (weapon_names, agent_names, agent_sides).
    Gloves are not in any struct_db JSON so they are hardcoded here as a supplement.
    """
    _GLOVE_NAMES = {
        5027: "Sport Gloves", 5028: "Driver Gloves", 5029: "Hand Wraps",
        5030: "Moto Gloves", 5031: "Specialist Gloves", 5032: "Hydra Gloves",
        5033: "Broken Fang Gloves", 5034: "Bloodhound Gloves",
    }
    weapon_names: dict = dict(_GLOVE_NAMES)
    agent_names:  dict = {}
    agent_sides:  dict = {}

    p = STRUCT_DB_DIR / "base_weapons.json"
    if p.exists():
        try:
            with open(p, encoding="utf-8") as f:
                items = json.load(f)
            for item in items:
                di = item.get("def_index")
                nm = item.get("name")
                if di is not None and nm:
                    weapon_names[int(di)] = nm
            log.info("item lookup: loaded %d weapon/knife names from base_weapons.json", len(weapon_names))
        except Exception as e:
            log.warning("item lookup: failed to load base_weapons.json: %s", e)
    else:
        log.warning("item lookup: base_weapons.json not found — knife names will be incorrect")

    p = STRUCT_DB_DIR / "agents.json"
    if p.exists():
        try:
            with open(p, encoding="utf-8") as f:
                items = json.load(f)
            for item in items:
                di = item.get("def_index")
                nm = item.get("name")
                if di is not None and nm:
                    di = int(di)
                    # Strip collection suffix: "Agent Name | Collection" → "Agent Name"
                    agent_names[di] = nm.split(" | ")[0]
                    team_id = (item.get("team") or {}).get("id", "")
                    if "terrorist" in team_id and "counter" not in team_id:
                        agent_sides[di] = "T"
                    elif "counter-terrorist" in team_id:
                        agent_sides[di] = "CT"
            log.info("item lookup: loaded %d agent names from agents.json", len(agent_names))
        except Exception as e:
            log.warning("item lookup: failed to load agents.json: %s", e)
    else:
        log.warning("item lookup: agents.json not found — agent names unavailable")

    return weapon_names, agent_names, agent_sides


_WEAPON_NAMES, _AGENT_NAMES, _AGENT_SIDE = _build_item_lookups()

# Side each weapon def_index belongs to ('CT', 'T', or 'both')
_WEAPON_SIDE: dict = {
    # CT-only
    8: "CT", 10: "CT", 16: "CT", 32: "CT", 34: "CT", 41: "CT", 60: "CT", 61: "CT",
    # T-only
    4: "T", 7: "T", 13: "T", 17: "T", 30: "T", 39: "T", 59: "T",
    # Special knives and gloves: T or CT depending on player choice —
    # resolved at runtime from parse_skins inventory slot; default both
}
# Knives 500-526: require inventory slot analysis; mark as both for now,
# resolved below via agent-side lookup if only one knife entry exists.

_KNIFE_DEF_INDICES: frozenset = frozenset({
    41, 59,  # default CT/T knife
    500, 505, 506, 507, 508, 509, 512, 514, 515, 516,
    517, 518, 519, 520, 521, 522, 523, 525, 526,
})

# CS2 event weapon class name -> def_index (for weapon_fire fallback)
_WEAPON_CLASS_TO_DEFIDX: dict = {
    "weapon_deagle":        1,
    "weapon_elite":         2,
    "weapon_fiveseven":     3,
    "weapon_glock":         4,
    "weapon_ak47":          7,
    "weapon_aug":           8,
    "weapon_awp":           9,
    "weapon_famas":         10,
    "weapon_g3sg1":         11,
    "weapon_galilar":       13,
    "weapon_m249":          14,
    "weapon_m4a1":          16,   # M4A4
    "weapon_mac10":         17,
    "weapon_p90":           19,
    "weapon_mp5sd":         23,
    "weapon_ump45":         24,
    "weapon_xm1014":        25,
    "weapon_bizon":         26,
    "weapon_mag7":          27,
    "weapon_negev":         28,
    "weapon_sawedoff":      29,
    "weapon_tec9":          30,
    "weapon_taser":         31,
    "weapon_hkp2000":       32,
    "weapon_mp7":           33,
    "weapon_mp9":           34,
    "weapon_nova":          35,
    "weapon_p250":          36,
    "weapon_scar20":        38,
    "weapon_sg556":         39,
    "weapon_ssg08":         40,
    "weapon_knife":         41,   # CT default knife
    "weapon_knife_t":       59,   # T default knife
    "weapon_m4a1_silencer": 60,   # M4A1-S
    "weapon_usp_silencer":  61,   # USP-S
    "weapon_cz75a":         62,
    "weapon_revolver":      63,
}

_WEAR_TIERS = [
    (0.07,  "Factory New"),
    (0.15,  "Minimal Wear"),
    (0.38,  "Field-Tested"),
    (0.45,  "Well-Worn"),
    (1.01,  "Battle-Scarred"),
]


def _wear_tier(f: float) -> str:
    for limit, label in _WEAR_TIERS:
        if f <= limit:
            return label
    return "Battle-Scarred"


_SKIN_NAMES: dict = {}
_SKIN_NAMES_LOADED = False


def _load_skin_names() -> dict:
    """Build paint_index -> skin name dict from struct_db/skins.json."""
    global _SKIN_NAMES, _SKIN_NAMES_LOADED
    if _SKIN_NAMES_LOADED:
        return _SKIN_NAMES
    _SKIN_NAMES_LOADED = True
    p = STRUCT_DB_DIR / "skins.json"
    if not p.exists():
        log.warning("skin names: skins.json not found at %s", p)
        return _SKIN_NAMES
    try:
        with open(p, encoding="utf-8") as f:
            skins = json.load(f)
        def _strip_prefix(name: str) -> str:
            return name.split(" | ", 1)[-1] if name and " | " in name else name
        _SKIN_NAMES = {
            str(item["paint_index"]): _strip_prefix(item.get("name", ""))
            for item in skins
            if isinstance(item, dict) and item.get("paint_index")
        }
        log.info("skin names: loaded %d entries from skins.json", len(_SKIN_NAMES))
    except Exception as e:
        log.warning("skin names: failed to load from skins.json: %s", e)
        _SKIN_NAMES = {}
    return _SKIN_NAMES


def extract_cosmetics(dem_path: str) -> list:
    """Return per-player agent + weapon skin data using demoparser2 directly."""
    import struct
    import pandas as pd
    try:
        from demoparser2 import DemoParser
    except ImportError:
        return []

    skin_names = _load_skin_names()

    try:
        parser   = DemoParser(dem_path)
        skins_df = parser.parse_skins()
        info_df  = parser.parse_player_info()
    except Exception as e:
        log.warning("extract_cosmetics parse failed: %s", e)
        return []

    log.debug("parse_skins columns: %s", list(skins_df.columns))
    def_cols = [c for c in skins_df.columns if "def" in c.lower()]
    log.debug("parse_skins def-related columns: %s", def_cols)
    log.debug("parse_skins sample:\n%s", skins_df.head().to_string())

    # ---- StatTrak: steamid -> {def_index -> count} ----
    stattrak: dict = {}
    try:
        st_df = parser.parse_ticks(["Weapon.m_nFallbackStatTrak", "Weapon.m_iItemDefinitionIndex"])
        st_df = st_df[st_df["Weapon.m_nFallbackStatTrak"].notna() &
                      (st_df["Weapon.m_nFallbackStatTrak"] > 0)]
        for _, row in st_df.drop_duplicates(subset=["steamid", "Weapon.m_iItemDefinitionIndex"]).iterrows():
            sid = str(row["steamid"])
            didx = int(row["Weapon.m_iItemDefinitionIndex"])
            stattrak.setdefault(sid, {})[didx] = int(row["Weapon.m_nFallbackStatTrak"])
    except Exception:
        pass

    # ---- Weapons fired per player (fallback for unskinned weapons) ----
    player_weapons_used: dict = {}  # steamid -> set of def_indices
    try:
        fire_df = parser.parse_event("weapon_fire", player=["steamid"])
        sid_col = "user_steamid" if "user_steamid" in fire_df.columns else "steamid"
        for _, row in fire_df.iterrows():
            sid = str(row.get(sid_col, ""))
            defidx = _WEAPON_CLASS_TO_DEFIDX.get(str(row.get("weapon", "")))
            if defidx and sid:
                player_weapons_used.setdefault(sid, set()).add(defidx)
    except Exception:
        pass

    # steamid -> {name, team}
    sid_info: dict = {}
    for _, row in info_df.iterrows():
        sid_info[str(row["steamid"])] = {
            "name": str(row["name"]),
            "team": "CT" if int(row["team_number"]) == 3 else "T",
        }

    # steamid -> items list
    sid_items: dict = {}
    for _, row in skins_df.iterrows():
        sid       = str(row["steamid"])
        def_idx   = int(row["def_index"])
        paint_idx = int(row["paint_index"]) if not pd.isna(row["paint_index"]) else 0
        paint_seed = int(row["paint_seed"]) if not pd.isna(row.get("paint_seed", float("nan"))) else None
        wear_raw  = row.get("paint_wear")
        wear_f    = None
        if wear_raw is not None and not pd.isna(wear_raw):
            try:
                wear_f = round(struct.unpack("f", struct.pack("I", int(wear_raw)))[0], 4)
            except Exception:
                pass
        custom = row.get("custom_name")
        custom = str(custom) if custom is not None and not pd.isna(custom) else None

        # Agents have no wear and typically def_index >= 4600
        is_agent = (def_idx >= 4600 and wear_f is None)

        if is_agent:
            item_name = _AGENT_NAMES.get(def_idx, f"Agent #{def_idx}")
            item_side = _AGENT_SIDE.get(def_idx, "both")
            skin_name = None
        else:
            item_name = _WEAPON_NAMES.get(def_idx, f"Item #{def_idx}")
            item_side = _WEAPON_SIDE.get(def_idx, "both")
            skin_name = skin_names.get(str(paint_idx)) if paint_idx else None

        st_count = stattrak.get(sid, {}).get(def_idx)

        sid_items.setdefault(sid, []).append({
            "def_index":   def_idx,
            "item_name":   item_name,
            "skin_name":   skin_name,
            "paint_index": paint_idx,
            "paint_seed":  paint_seed,
            "wear":        wear_f,
            "wear_tier":   _wear_tier(wear_f) if wear_f is not None else None,
            "custom_name": custom,
            "stattrak":    st_count,
            "is_agent":    is_agent,
            "side":        item_side,
            "weapon_cat":  "knife" if def_idx in _KNIFE_DEF_INDICES else None,
        })

    # Fill in default (no-skin) entries for weapons used in-game but absent from parse_skins
    for sid, used_defidxs in player_weapons_used.items():
        existing = {i["def_index"] for i in sid_items.get(sid, []) if not i["is_agent"]}
        for defidx in sorted(used_defidxs):
            if defidx not in existing:
                sid_items.setdefault(sid, []).append({
                    "def_index":   defidx,
                    "item_name":   _WEAPON_NAMES.get(defidx, f"Item #{defidx}"),
                    "skin_name":   None,
                    "paint_index": 0,
                    "paint_seed":  None,
                    "wear":        None,
                    "wear_tier":   None,
                    "custom_name": None,
                    "stattrak":    None,
                    "is_agent":    False,
                    "side":        _WEAPON_SIDE.get(defidx, "both"),
                })

    result = []
    for sid, info in sid_info.items():
        items = sid_items.get(sid, [])

        def _weapons_for(side: str):
            return sorted(
                [i for i in items if not i["is_agent"] and i["side"] in (side, "both")],
                key=lambda x: x["def_index"],
            )

        result.append({
            "steamid":    sid,
            "name":       info["name"],
            "team":       info["team"],
            "ct_agent":   next((i for i in items if i["is_agent"] and i["side"] in ("CT", "both")), None),
            "t_agent":    next((i for i in items if i["is_agent"] and i["side"] in ("T",  "both")), None),
            "ct_weapons": _weapons_for("CT"),
            "t_weapons":  _weapons_for("T"),
        })

    result.sort(key=lambda p: (0 if p["team"] == "CT" else 1, p["name"]))
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


# Weapons that fire projectiles but aren't bullets — excluded from accuracy
_GRENADE_WEAPONS = {
    "flashbang", "smokegrenade", "hegrenade", "molotov",
    "incgrenade", "decoy", "tagrenade", "c4",
}


def _extract_aim(kills: list, damages_df, rounds: list, shots_df=None) -> list:
    """Per-player aim breakdown: hit groups, avg damage, per-weapon stats, KAST, accuracy."""
    players: dict = {}

    def _norm_wpn(s):
        return str(s or "?").lower().replace("weapon_", "").strip()

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
            wpn = _norm_wpn(row.get("weapon"))

            p = players.setdefault(att, {"hit_groups": {}, "dmg_groups": {}, "weapons": {}, "total_hits": 0, "total_dmg": 0})
            p["hit_groups"][hg]  = p["hit_groups"].get(hg, 0) + 1
            p["dmg_groups"][hg]  = p["dmg_groups"].get(hg, 0) + dmg
            p["total_hits"]     += 1
            p["total_dmg"]      += dmg
            w = p["weapons"].setdefault(wpn, {"hits": 0, "dmg": 0, "kills": 0, "hs_kills": 0, "shots": 0})
            w["hits"] += 1
            w["dmg"]  += dmg

    for k in kills:
        att = k.get("attacker")
        if not att or att in ("nan", "?"):
            continue
        if att in players:
            wpn = _norm_wpn(k.get("weapon", "?"))
            w = players[att]["weapons"].setdefault(wpn, {"hits": 0, "dmg": 0, "kills": 0, "hs_kills": 0, "shots": 0})
            w["kills"] += 1
            if k.get("headshot"):
                w["hs_kills"] += 1

    # Build case-insensitive player name index for cross-DataFrame matching
    name_idx = {n.lower(): n for n in players}

    # ---- Count shots fired (bullets only, no grenades) ----
    player_shots: dict = {n: {} for n in players}  # {canonical_name: {weapon: count}}
    if shots_df is not None:
        for _, row in shots_df.iterrows():
            pname = row.get("player_name")
            if not pname or str(pname) == "nan":
                continue
            wpn = _norm_wpn(row.get("weapon"))
            if wpn in _GRENADE_WEAPONS:
                continue
            canonical = name_idx.get(str(pname).lower())
            if canonical is None:
                continue  # player not in damages data, skip
            player_shots[canonical][wpn] = player_shots[canonical].get(wpn, 0) + 1
            w = players[canonical]["weapons"].setdefault(wpn, {"hits": 0, "dmg": 0, "kills": 0, "hs_kills": 0, "shots": 0})
            w["shots"] += 1

    kast = _calc_kast(kills, rounds)

    result = []
    for name, p in players.items():
        th = p["total_hits"]
        td = p["total_dmg"]
        total_shots = sum(player_shots.get(name, {}).values())
        weapons_sorted = sorted(
            [{"weapon": w, **s} for w, s in p["weapons"].items()],
            key=lambda x: x["kills"], reverse=True
        )
        result.append({
            "name":          name,
            "total_hits":    th,
            "total_shots":   total_shots,
            "accuracy":      min(100, round(100 * th / total_shots)) if total_shots else None,
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

    # ---- Steam ID map (name -> steamid64) ----
    steamids: dict = {}
    if kills_df is not None:
        for col_name, col_id in [("attacker_name", "attacker_steamid"), ("victim_name", "victim_steamid")]:
            if col_name in kills_df.columns and col_id in kills_df.columns:
                for name, sid in zip(kills_df[col_name], kills_df[col_id]):
                    if name and str(name) not in ("nan", "?") and sid and str(sid) not in ("nan", "0", ""):
                        # Strip decimal without going through float to avoid SteamID64 precision loss
                        sid_str = str(sid).split('.')[0]
                        if sid_str and sid_str not in ("0", "nan"):
                            steamids[str(name)] = sid_str

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
    shots_df = _to_pd(getattr(demo, "shots", None))
    aim_breakdown = _extract_aim(kills, damages_df, rounds, shots_df)

    scoreboard = []
    for player, s in stats.items():
        k_val  = s.get("kills", 0)
        d_val  = s.get("deaths", 0)
        hs_val = s.get("hs", 0)
        scoreboard.append({
            "name":     player,
            "steamid":  steamids.get(player),
            "team":     str(s.get("team", "?")),
            "kills":    k_val,
            "deaths":   d_val,
            "assists":  s.get("assists", 0),
            "kd":       round(k_val / d_val, 2) if d_val else float(k_val),
            "hs_pct":   round(100 * hs_val / k_val) if k_val else 0,
            "dmg":      s.get("dmg", 0),
        })
    scoreboard.sort(key=lambda x: x["kills"], reverse=True)

    # ---- Cosmetics (agent + weapon skins) ----
    swag_breakdown = extract_cosmetics(dem_path)

    # ---- Tick data (player positions) ----
    session_id = str(uuid.uuid4())
    ticks_by_round = extract_ticks(demo, dem_path)
    if len(_session_cache) >= MAX_SESSIONS:
        _session_cache.popitem(last=False)
    _session_cache[session_id] = {
        "ticks":    ticks_by_round,
        "map_name": header["map"],
    }

    return {
        "header":         header,
        "ct_team":        ct_team,
        "t_team":         t_team,
        "ct_wins":        ct_wins,
        "t_wins":         t_wins,
        "total_rounds":   len(rounds),
        "rounds":         rounds,
        "kills":          kills,
        "scoreboard":     scoreboard,
        "aim_breakdown":  aim_breakdown,
        "swag_breakdown": swag_breakdown,
        "session_id":     session_id,
        "has_ticks":      bool(ticks_by_round),
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

    log.info("parse: received upload — %s", f.filename)
    with tempfile.NamedTemporaryFile(suffix=".dem", delete=False) as tmp:
        tmp_path = tmp.name
        f.save(tmp_path)

    _t0 = time.monotonic()
    try:
        data = parse_demo(tmp_path)
        data["filename"] = f.filename
        ticks = _session_cache.get(data["session_id"], {}).get("ticks", {})
        _db_save(data["session_id"], f.filename, data["header"]["map"], data, ticks)
        elapsed = time.monotonic() - _t0
        log.info("parse: completed %s — map=%s rounds=%s ticks=%s (%.2fs)",
                 f.filename, data["header"].get("map"),
                 data.get("total_rounds"), len(ticks), elapsed)
        return jsonify(data)
    except Exception as e:
        log.error("parse: failed for %s — %s", f.filename, e, exc_info=True)
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


_load_skin_names()

log.info("startup complete — cs2demviewer ready")

if __name__ == "__main__":
    if _verbose:
        log.info("Flask dev server starting on http://localhost:5000")
    app.run(debug=True, port=5000, threaded=True)
