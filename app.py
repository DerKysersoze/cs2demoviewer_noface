#!/usr/bin/env python3
"""
CS2 Demo Viewer - Web Backend
"""

import argparse
import datetime
import json
import logging
import math
import os
import re
import shutil
import sqlite3
import tempfile
import threading
import time
import traceback
import uuid
import zlib

import numpy as np
from collections import OrderedDict
from pathlib import Path

from flask import Flask, g, jsonify, request, send_file, send_from_directory

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
DEMOS_DIR     = Path(__file__).parent / "demos_store"
DEMOS_DIR.mkdir(exist_ok=True)




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
    start_tick  INTEGER,
    end_tick    INTEGER,
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

CREATE TABLE IF NOT EXISTS demo_data_blobs (
    demo_id       TEXT PRIMARY KEY,
    ticks_data    BLOB,
    grenades_data BLOB,
    events_data   BLOB,
    shots_data    BLOB,
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

    # ---- Phase 4: add demo_data_blobs.shots_data ----
    # Pre-existing DBs keep their old table shape — CREATE TABLE IF NOT EXISTS
    # won't add the column, so migrate explicitly (idempotent).
    ddb_cols = {r[1] for r in con.execute("PRAGMA table_info(demo_data_blobs)").fetchall()}
    if "shots_data" not in ddb_cols:
        con.execute("ALTER TABLE demo_data_blobs ADD COLUMN shots_data BLOB")
        log.info("DB: added demo_data_blobs.shots_data column")

    # ---- Phase 5: add demo_rounds.start_tick / end_tick ----
    # Same pattern: existing rows keep NULL until reparsed; the reparse
    # endpoint backfills them from the .dem's round_start/round_end events.
    dr_cols = {r[1] for r in con.execute("PRAGMA table_info(demo_rounds)").fetchall()}
    if "start_tick" not in dr_cols:
        con.execute("ALTER TABLE demo_rounds ADD COLUMN start_tick INTEGER")
        log.info("DB: added demo_rounds.start_tick column")
    if "end_tick" not in dr_cols:
        con.execute("ALTER TABLE demo_rounds ADD COLUMN end_tick INTEGER")
        log.info("DB: added demo_rounds.end_tick column")

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
                        "INSERT INTO demo_rounds (demo_id,round_num,winner_side,reason,ct_score,t_score,start_tick,end_tick)"
                        " VALUES (?,?,?,?,?,?,?,?)",
                        [(demo_id, r["round_num"], r["winner_side"], r.get("reason"),
                          r.get("ct_score"), r.get("t_score"),
                          r.get("start_tick"), r.get("end_tick")) for r in rounds],
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
             ticks_by_round: dict = None, grenades_by_round: dict = None,
             events_by_round: dict = None, shots_by_round: dict = None):
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
            datetime.datetime.now(datetime.UTC).isoformat(),  # explicit string — avoids the deprecated sqlite datetime adapter
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
            "INSERT INTO demo_rounds (demo_id,round_num,winner_side,reason,ct_score,t_score,start_tick,end_tick)"
            " VALUES (?,?,?,?,?,?,?,?)",
            [(demo_id, r["round_num"], r["winner_side"], r.get("reason"),
              r.get("ct_score"), r.get("t_score"),
              r.get("start_tick"), r.get("end_tick")) for r in rounds],
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

    # ---- demo_data_blobs ----
    con.execute("DELETE FROM demo_data_blobs WHERE demo_id = ?", (demo_id,))
    if ticks_by_round or grenades_by_round or events_by_round or shots_by_round:
        con.execute(
            "INSERT INTO demo_data_blobs"
            " (demo_id, ticks_data, grenades_data, events_data, shots_data)"
            " VALUES (?,?,?,?,?)",
            (
                demo_id,
                _blob(ticks_by_round)    if ticks_by_round    else None,
                _blob(grenades_by_round) if grenades_by_round else None,
                _blob(events_by_round)   if events_by_round   else None,
                _blob(shots_by_round)    if shots_by_round    else None,
            ),
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
    """Demo library feed. Beyond the basic identity, each demo carries the
    final score (CT/T wins), teams, round count, duration and the match's top
    performer (highest kills, K/D tiebreak) so the front-page cards can show
    quick stats without a second request per demo."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        SELECT d.id, d.filename, d.map, d.uploaded_at,
               d.ct_team, d.t_team, d.ct_wins, d.t_wins, d.total_rounds, d.duration,
               s.player_name AS mvp_name, s.team AS mvp_team,
               s.kills AS mvp_kills, s.kd AS mvp_kd
        FROM demos d
        LEFT JOIN (
            SELECT demo_id, player_name, team, kills, kd,
                   ROW_NUMBER() OVER (
                       PARTITION BY demo_id
                       ORDER BY kills DESC, kd DESC, player_name
                   ) AS rn
            FROM demo_scoreboard
            WHERE kills IS NOT NULL
        ) s ON s.demo_id = d.id AND s.rn = 1
        ORDER BY d.uploaded_at DESC
        """
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def _db_load_session(demo_id: str):
    """Hydrate the in-memory ticks/grenades/events session for a demo from the DB.

    Called after a server restart (or whenever the in-memory cache is cold) so
    the 2D replay works for previously-parsed demos.  Returns the session dict,
    or None if the demo has no stored tick data.
    """
    if demo_id in _session_cache:
        _session_cache.move_to_end(demo_id)  # LRU: a hit refreshes recency
        return _session_cache[demo_id]
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    row = con.execute(
        "SELECT d.ticks_data, d.grenades_data, d.events_data, d.shots_data, m.map "
        "FROM demo_data_blobs d JOIN demos m ON m.id = d.demo_id "
        "WHERE d.demo_id = ?", (demo_id,)
    ).fetchone()
    con.close()
    if not row or not row["ticks_data"]:
        return None
    if len(_session_cache) >= MAX_SESSIONS:
        _session_cache.popitem(last=False)
    _stored = DEMOS_DIR / f"{demo_id}.dem"
    session = {
        "ticks":    {int(k): v for k, v in _unblob(row["ticks_data"]).items()},
        "grenades": {int(k): v for k, v in _unblob(row["grenades_data"]).items()} if row["grenades_data"] else {},
        "events":   {int(k): v for k, v in _unblob(row["events_data"]).items()}   if row["events_data"]   else {},
        "map_name": row["map"],
        "dem_path": str(_stored) if _stored.exists() else None,
    }
    if row["shots_data"]:
        session["shots"] = {int(k): v for k, v in _unblob(row["shots_data"]).items()}
    # No shots blob (row saved before Phase 4)? Leave "shots" unset so
    # api_ticks' lazy extract_shots fallback can rebuild it from the .dem.
    _session_cache[demo_id] = session
    return session


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
    blob_row       = con.execute(
        "SELECT ticks_data, grenades_data, events_data FROM demo_data_blobs WHERE demo_id = ?", (demo_id,)
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

    if blob_row and blob_row["ticks_data"]:
        if _db_load_session(demo_id) is not None:
            data["has_ticks"] = True

    return data


def _db_delete(demo_id: str) -> bool:
    con = sqlite3.connect(DB_PATH)
    for tbl in ("demo_rounds", "demo_kills", "demo_scoreboard", "demo_aim",
                "demo_aim_weapons", "demo_aim_hitgroups", "demo_data_blobs", "demo_cosmetics"):
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
    "de_train":    {"pos_x": -2308, "pos_y":  2078, "scale": 4.082077},
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


def _parse_overview_txt(path) -> dict | None:
    """Parse an HLTV-style overview description file (maps/<map>.txt).

    Returns {"pos_x", "pos_y", "scale", "sections": {name: {"alt_min", "alt_max"}}}.
    The file format is nested quoted key/value blocks, optionally with
    ``//`` comments.  ``verticalsections`` gives the altitude range of each
    floor; the primary floor is the section named ``default``.
    """
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    # Strip // comments outside of quoted strings.
    out: list[str] = []
    in_str = False
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == '"' and (i == 0 or text[i - 1] != "\\"):
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        out.append(ch)
        i += 1
    text = "".join(out)

    # Tokenize quoted strings and braces.
    tokens = []
    for m in re.finditer(r'"((?:[^"\\]|\\.)*)"|\{|\}', text):
        tokens.append(m.group(1) if m.group(1) is not None else m.group(0))

    # Walk tokens into a nested dict (key → value | key → block).
    root: dict = {}
    stack: list[dict] = [root]
    key = None
    for tok in tokens:
        if tok == "{":
            child: dict = {}
            if key is not None:
                stack[-1][key] = child
                key = None
            stack.append(child)
        elif tok == "}":
            if len(stack) > 1:
                stack.pop()
            if key is not None and stack:
                stack[-1][key] = ""
                key = None
        else:
            if key is None:
                key = tok
            else:
                stack[-1][key] = tok
                key = None

    # The map name is the first key and wraps all the data ("de_nuke" { ... }).
    if len(root) == 1:
        only = next(iter(root.values()))
        if isinstance(only, dict):
            root = only

    def _f(k):
        try:
            return float(root.get(k, ""))
        except (TypeError, ValueError):
            return None

    pos_x, pos_y, scale = _f("pos_x"), _f("pos_y"), _f("scale")
    if pos_x is None or pos_y is None or scale is None:
        return None

    sections: dict = {}
    vs = root.get("verticalsections")
    if isinstance(vs, dict):
        for sname, sbody in vs.items():
            if not isinstance(sbody, dict):
                continue
            try:
                sections[sname] = {
                    "alt_min": float(sbody.get("AltitudeMin", -16384)),
                    "alt_max": float(sbody.get("AltitudeMax", 16384)),
                }
            except (TypeError, ValueError):
                continue
    if not sections:
        sections = {"default": {"alt_min": -16384, "alt_max": 16384}}

    return {"pos_x": pos_x, "pos_y": pos_y, "scale": scale, "sections": sections}


def _map_floors(map_name: str) -> list[dict]:
    """Floors for a map = overview sections that have an image in maps/.

    Section ``default`` → maps/<map>.png, section ``x`` → maps/<map>_x.png.
    Sorted by altitude (lowest floor first).  One anonymous floor is returned
    when the map has no local data (image then comes from the awpy fallback).
    """
    maps_dir = Path(__file__).parent / "maps"
    txt = maps_dir / f"{map_name}.txt"
    parsed = _parse_overview_txt(txt) if txt.exists() else None
    sections = parsed["sections"] if parsed else {"default": {"alt_min": -16384, "alt_max": 16384}}

    floors = []
    for sname, rng in sections.items():
        fname = map_name if sname == "default" else f"{map_name}_{sname}"
        if not (maps_dir / f"{fname}.png").exists():
            continue
        floors.append({
            "name":    sname,
            "label":   "Main" if sname == "default" else sname.title(),
            "image":   f"/api/map_image/{map_name}" + ("" if sname == "default" else f"/{sname}"),
            "alt_min": rng["alt_min"],
            "alt_max": rng["alt_max"],
        })
    if not floors:
        floors = [{
            "name": "default", "label": "Main",
            "image": f"/api/map_image/{map_name}",
            "alt_min": -16384, "alt_max": 16384,
        }]
    floors.sort(key=lambda f: f["alt_min"])
    return floors


def _get_map_bounds(map_name: str) -> dict:
    """Return pos_x, pos_y, scale for the map.

    Order: maps/<map>.txt (single source of truth) → awpy MAP_DATA →
    hardcoded bounds → dust2 default.
    """
    txt = Path(__file__).parent / "maps" / f"{map_name}.txt"
    if txt.exists():
        parsed = _parse_overview_txt(txt)
        if parsed:
            return {"pos_x": parsed["pos_x"], "pos_y": parsed["pos_y"], "scale": parsed["scale"]}
    try:
        from awpy.data.map_data import MAP_DATA  # noqa: F401
        if map_name in MAP_DATA:
            d = MAP_DATA[map_name]
            return {"pos_x": d["pos_x"], "pos_y": d["pos_y"], "scale": d["scale"]}
    except Exception:
        pass
    return MAP_BOUNDS.get(map_name, {"pos_x": -2476, "pos_y": 3239, "scale": 4.4})


_NADE_EVENT_TYPE = {
    "smokegrenade_detonate": "smoke",
    "flashbang_detonate":    "flash",
    "hegrenade_detonate":    "he",
    "molotov_detonate":      "fire",
    "inferno_startburn":     "fire",
}
_NADE_DURATIONS = {
    "smoke": 1152,   # ~18 s × 64 hz
    "flash":   96,   # ~1.5 s visual
    "he":      48,   # ~0.75 s blast marker
    "fire":   512,   # ~8 s fire
}


def extract_grenades(dem_path, ticks_by_round: dict) -> dict:
    """
    Returns {round_num: [{type, x, y, from_tick, to_tick}]}.
    Requires dem_path for a second demoparser2 pass.
    """
    if not dem_path:
        return {}

    # Build per-round tick ranges so we can assign events to rounds
    round_ranges = {}
    for rnum, frames in ticks_by_round.items():
        if frames:
            ticks = [f["t"] for f in frames]
            round_ranges[rnum] = (min(ticks), max(ticks))

    def _tick_to_round(tick):
        for rnum, (start, end) in round_ranges.items():
            if start <= tick <= end + 1000:
                return rnum
        return None

    result = {}
    try:
        from demoparser2 import DemoParser
        parser = DemoParser(str(dem_path))

        for event_name, nade_type in _NADE_EVENT_TYPE.items():
            try:
                result_list = parser.parse_events([event_name], other=["round_num"])
                if not result_list:
                    continue
                # result_list is [(event_name, DataFrame), ...]
                item = result_list[0]
                df = item[1] if isinstance(item, tuple) else item
                if df is None or df.empty:
                    continue
                cols = list(df.columns)
                tick_col = next((c for c in ["tick"] if c in cols), None)
                x_col    = next((c for c in ["x", "X"] if c in cols), None)
                y_col    = next((c for c in ["y", "Y"] if c in cols), None)
                rnum_col = "round_num" if "round_num" in cols else None
                name_col = next((c for c in ["user_name", "player_name", "name", "attacker_name"] if c in cols), None)
                if not tick_col or not x_col or not y_col:
                    log.debug("extract_grenades: %s missing pos columns — %s", event_name, cols)
                    continue
                duration = _NADE_DURATIONS[nade_type]
                for _, row in df.iterrows():
                    try:
                        tick = int(row[tick_col])
                        x    = float(row[x_col])
                        y    = float(row[y_col])
                        rnum = int(row[rnum_col]) if rnum_col else _tick_to_round(tick)
                        if rnum is None:
                            continue
                        result.setdefault(int(rnum), []).append({
                            "type":      nade_type,
                            "x":         x,
                            "y":         y,
                            "from_tick": tick,
                            "to_tick":   tick + duration,
                            "player":    str(row[name_col]) if name_col else None,
                        })
                    except Exception:
                        continue
            except Exception as e:
                log.debug("extract_grenades: event %s failed — %s", event_name, e)

    except Exception as e:
        log.warning("extract_grenades failed: %s", e)

    total = sum(len(v) for v in result.values())
    log.info("extract_grenades: %d grenades across %d rounds", total, len(result))
    return result


# Friendly display names for bought items
_BUY_ITEM_NAMES = {
    "item_kevlar":          "Kevlar",
    "item_assaultsuit":     "Kevlar + Helmet",
    "item_defuser":         "Defuse Kit",
    "weapon_ak47":          "AK-47",
    "weapon_m4a1":          "M4A4",
    "weapon_m4a1_silencer": "M4A1-S",
    "weapon_awp":           "AWP",
    "weapon_deagle":        "Desert Eagle",
    "weapon_usp_silencer":  "USP-S",
    "weapon_glock":         "Glock",
    "weapon_p250":          "P250",
    "weapon_fiveseven":     "Five-SeveN",
    "weapon_tec9":          "Tec-9",
    "weapon_cz75a":         "CZ75-Auto",
    "weapon_revolver":      "R8 Revolver",
    "weapon_mp9":           "MP9",
    "weapon_mp5sd":         "MP5-SD",
    "weapon_mac10":         "MAC-10",
    "weapon_mp7":           "MP7",
    "weapon_p90":           "P90",
    "weapon_bizon":         "PP-Bizon",
    "weapon_ump45":         "UMP-45",
    "weapon_famas":         "FAMAS",
    "weapon_galilar":       "Galil AR",
    "weapon_sg556":         "SG 553",
    "weapon_aug":           "AUG",
    "weapon_ssg08":         "SSG 08",
    "weapon_g3sg1":         "G3SG1",
    "weapon_scar20":        "SCAR-20",
    "weapon_xm1014":        "XM1014",
    "weapon_nova":          "Nova",
    "weapon_sawedoff":      "Sawed-Off",
    "weapon_mag7":          "MAG-7",
    "weapon_m249":          "M249",
    "weapon_negev":         "Negev",
    "weapon_flashbang":     "Flashbang",
    "weapon_smokegrenade":  "Smoke Grenade",
    "weapon_hegrenade":     "HE Grenade",
    "weapon_molotov":       "Molotov",
    "weapon_incgrenade":    "Incendiary Grenade",
    "weapon_decoy":         "Decoy Grenade",
}

# Items that are never purchased — filter these out of item_pickup events
_NON_PURCHASE_ITEMS = {
    "knife", "knife_t", "knife_ct", "knife_ghost",
    "c4", "healthshot", "taser",
    "glock", "hkp2000", "usp_silencer",  # default pistols given free at round start
}

def _extract_buy_from_item_pickup(parser, round_ranges: dict) -> dict:
    """
    Primary buy-event fallback using item_pickup events.
    item_pickup fires for every item a player receives — purchases, floor picks, spawns.
    We filter to purchases by:
      1. Excluding silent=True pickups (round-start loadout equips)
      2. Excluding known non-purchasable items (knife, c4, default pistols)
      3. Cross-referencing with cash_spent_this_round tick data: a pickup is a
         purchase if cash_spent increased at/near the same tick for that player.
    Returns {round_num: [{type, tick, player, item}]}.
    """
    import pandas as pd

    result = {}
    try:
        # ── Parse item_pickup events ──────────────────────────────────────────
        rows = parser.parse_events(["item_pickup"])
        if not rows:
            return {}
        raw = rows[0]
        pickup_df = raw[1] if isinstance(raw, tuple) else raw
        if pickup_df is None or pickup_df.empty:
            return {}

        cols = list(pickup_df.columns)
        name_col  = next((c for c in ["user_name", "player_name", "name"] if c in cols), None)
        item_col  = next((c for c in ["item", "weapon", "weapon_name"] if c in cols), None)
        rnum_col  = "round_num" if "round_num" in cols else None
        silent_col = "silent" if "silent" in cols else None

        if not name_col or not item_col:
            log.info("_extract_buy_from_item_pickup: missing name/item cols — %s", cols)
            return {}

        # Filter: drop silent equips and non-purchasable items
        if silent_col:
            pickup_df = pickup_df[pickup_df[silent_col] == False]  # noqa: E712
        pickup_df = pickup_df[~pickup_df[item_col].isin(_NON_PURCHASE_ITEMS)]

        if pickup_df.empty:
            return {}

        # ── Parse cash_spent_this_round ticks to confirm purchases ────────────
        # Build a set of (player, tick) where cash_spent increased — these are buys
        purchase_ticks: set[tuple] = set()
        try:
            tdf = parser.parse_ticks(["cash_spent_this_round"])
            if tdf is not None and not tdf.empty:
                tcols    = list(tdf.columns)
                tname_col = next((c for c in ["name", "player_name", "user_name"] if c in tcols), None)
                if tname_col and "cash_spent_this_round" in tcols:
                    for player, pdf in tdf.groupby(tname_col):
                        pdf = pdf.sort_values("tick")
                        prev_spent = None
                        prev_rnum  = None
                        for _, trow in pdf.iterrows():
                            try:
                                spent = int(trow["cash_spent_this_round"]) if pd.notna(trow["cash_spent_this_round"]) else 0
                                rnum  = int(trow["round_num"]) if "round_num" in tcols and pd.notna(trow.get("round_num")) else None
                            except (ValueError, TypeError):
                                continue
                            if prev_spent is None or (rnum != prev_rnum and spent < prev_spent):
                                prev_spent = spent
                                prev_rnum  = rnum
                                continue
                            if spent > prev_spent:
                                # Cash increased — record this tick ±64 ticks as a purchase window
                                tick = int(trow["tick"])
                                for dt in range(-64, 65):
                                    purchase_ticks.add((str(player), tick + dt))
                            prev_spent = spent
                            prev_rnum  = rnum
        except Exception as e:
            log.debug("_extract_buy_from_item_pickup: cash tick parse failed — %s", e)

        # ── Assign each pickup to a round ─────────────────────────────────────
        def _tick_to_round(tick):
            for rnum, (start, end) in round_ranges.items():
                if start - 5000 <= tick <= end + 1000:
                    return rnum
            return None

        for _, row in pickup_df.iterrows():
            try:
                tick   = int(row["tick"])
                player = str(row[name_col])
                raw_item = str(row[item_col]).lower()

                # If we have cash data, only include confirmed purchases
                if purchase_ticks and (player, tick) not in purchase_ticks:
                    continue

                rnum = int(row[rnum_col]) if rnum_col and pd.notna(row.get(rnum_col)) else _tick_to_round(tick)
                if rnum is None:
                    continue
                # Reject pickups beyond the round's last frame tick (next-round bleed)
                _rstart, _rend = round_ranges.get(rnum, (0, 0))
                if tick > _rend:
                    continue

                display = _BUY_ITEM_NAMES.get(
                    f"weapon_{raw_item}",
                    _BUY_ITEM_NAMES.get(
                        f"item_{raw_item}",
                        _BUY_ITEM_NAMES.get(
                            raw_item,
                            raw_item.replace("_", " ").title()
                        )
                    )
                )

                result.setdefault(int(rnum), []).append({
                    "type":   "buy",
                    "tick":   tick,
                    "player": player,
                    "item":   display,
                })
            except Exception as _row_e:
                log.debug("_extract_buy_from_item_pickup: row error — %s", _row_e)
                continue

    except Exception as e:
        log.warning("_extract_buy_from_item_pickup failed: %s", e)

    return result


def extract_shots(dem_path, ticks_by_round: dict) -> dict:
    """
    Returns {round_num: [{tick, player, x, y, yaw}]} from weapon_fire events.
    Excludes knife/grenade non-hitscan weapons.
    """
    if not dem_path:
        return {}
    _NON_TRACER = {"weapon_knife","weapon_knife_t","weapon_knife_ct","weapon_knife_ghost",
                   "weapon_hegrenade","weapon_smokegrenade","weapon_flashbang",
                   "weapon_molotov","weapon_incgrenade","weapon_decoy","weapon_c4","weapon_taser"}
    # Build round tick ranges for assignment
    round_ranges = {}
    for rnum, frames in ticks_by_round.items():
        if frames:
            ticks = [f["t"] for f in frames]
            round_ranges[rnum] = (min(ticks), max(ticks))

    def _tick_to_round(tick):
        for rnum, (start, end) in round_ranges.items():
            if start - 5000 <= tick <= end + 1000:
                return rnum
        return None

    result = {}
    try:
        from demoparser2 import DemoParser
        parser = DemoParser(str(dem_path))
        df = parser.parse_event("weapon_fire", player=["name", "yaw", "X", "Y"])
        if df is None or (hasattr(df, "empty") and df.empty):
            return {}
        import pandas as pd
        if isinstance(df, list):
            df = df[0][1] if df and isinstance(df[0], tuple) else pd.DataFrame(df)
        cols = list(df.columns)
        for _, row in df.iterrows():
            try:
                weapon = str(row.get("weapon","")).lower()
                if weapon in _NON_TRACER:
                    continue
                tick   = int(row["tick"])
                player = str(row.get("user_name") or row.get("name","?"))
                x      = float(row["user_X"])
                y      = float(row["user_Y"])
                yaw    = float(row["user_yaw"])
                rnum   = _tick_to_round(tick)
                if rnum is None:
                    continue
                result.setdefault(int(rnum), []).append({
                    "tick": tick, "player": player,
                    "x": x, "y": y, "yaw": yaw,
                })
            except Exception:
                continue
    except Exception as e:
        log.warning("extract_shots failed: %s", e)
    return result


def extract_events(dem_path, ticks_by_round: dict) -> dict:
    """
    Returns {round_num: [{type, tick, player, item?}]}.
    Parses player_buy, bomb_planted, bomb_defused via demoparser2.
    Gracefully returns {} if demoparser2 is unavailable.
    """
    if not dem_path:
        return {}

    round_ranges = {}
    for rnum, frames in ticks_by_round.items():
        if frames:
            ticks = [f["t"] for f in frames]
            round_ranges[rnum] = (min(ticks), max(ticks))

    def _tick_to_round(tick, buy_phase=False):
        # buy_phase=True extends the window backwards to cover freeze time
        # (~15s = ~1920 ticks at 128hz; use 5000 to be safe across tickrates)
        lookback = 5000 if buy_phase else 0
        for rnum, (start, end) in round_ranges.items():
            if start - lookback <= tick <= end + 1000:
                return rnum
        return None

    result = {}
    try:
        from demoparser2 import DemoParser
        parser = DemoParser(str(dem_path))

        # ---- Buy events ----
        try:
            _rows = parser.parse_events(["player_buy"])
            buy_df = None
            if _rows:
                _item = _rows[0]
                buy_df = _item[1] if isinstance(_item, tuple) else _item

            if buy_df is None or buy_df.empty:
                # CS2 demos use 'item_purchase' instead of 'player_buy'
                _item_purchase_df = None
                try:
                    _ip_rows = parser.parse_events(["item_purchase"])
                    if _ip_rows:
                        _ip_item = _ip_rows[0]
                        _item_purchase_df = _ip_item[1] if isinstance(_ip_item, tuple) else _ip_item
                except Exception as _ip_e:
                    log.debug("extract_events: item_purchase parse failed — %s", _ip_e)

                if _item_purchase_df is not None and not _item_purchase_df.empty:
                    _ip_cols = list(_item_purchase_df.columns)
                    log.info("extract_events: item_purchase — %d rows, cols=%s", len(_item_purchase_df), _ip_cols)
                    _ip_skipped = 0
                    for _, _ip_row in _item_purchase_df.iterrows():
                        try:
                            # Skip items that were sold back
                            if "was_sold" in _ip_cols and _ip_row.get("was_sold"):
                                continue
                            _ip_tick   = int(_ip_row["tick"])
                            _ip_player = str(_ip_row["name"]) if "name" in _ip_cols else "?"
                            _ip_raw    = str(_ip_row["item_name"]).lower() if "item_name" in _ip_cols else ""
                            _ip_rnum   = _tick_to_round(_ip_tick, buy_phase=True)
                            if _ip_rnum is None:
                                _ip_skipped += 1
                                continue
                            # Reject buys whose tick exceeds the round's last frame — these
                            # are next-round freeze-phase buys captured by the +1000 tolerance.
                            _rstart, _rend = round_ranges.get(_ip_rnum, (0, 0))
                            if _ip_tick > _rend:
                                _ip_skipped += 1
                                continue
                            _ip_display = _BUY_ITEM_NAMES.get(
                                _ip_raw,
                                _ip_raw.replace("weapon_", "").replace("item_", "").replace("_", " ").title()
                            )
                            result.setdefault(int(_ip_rnum), []).append({
                                "type":   "buy",
                                "tick":   _ip_tick,
                                "player": _ip_player,
                                "item":   _ip_display,
                            })
                        except Exception as _ip_row_e:
                            log.debug("extract_events: item_purchase row error — %s", _ip_row_e)
                            _ip_skipped += 1
                    _ip_total = sum(1 for evts in result.values() for e in evts if e["type"] == "buy")
                    log.info("extract_events: item_purchase added %d events, skipped %d rows", _ip_total, _ip_skipped)
                else:
                    log.info("extract_events: player_buy/item_purchase returned no data — falling back to item_pickup")
                    _buy_from_pickup = _extract_buy_from_item_pickup(parser, round_ranges)
                    for rnum, evts in _buy_from_pickup.items():
                        result.setdefault(rnum, []).extend(evts)
                    log.info("extract_events: item_pickup fallback added %d buy events across %d rounds",
                             sum(len(v) for v in _buy_from_pickup.values()), len(_buy_from_pickup))
            else:
                cols     = list(buy_df.columns)
                name_col = next((c for c in ["user_name", "player_name", "name"] if c in cols), None)
                item_col = next((c for c in [
                    "weapon", "item", "weaponItemId", "weapon_name", "weapon_id",
                    "weaponId", "item_name", "defindex", "wep_type",
                ] if c in cols), None)
                if item_col is None:
                    skip_cols = {"tick", "name", "player_name", "user_name", "steamid", "round_num"}
                    candidates = [c for c in cols if c not in skip_cols]
                    item_col = candidates[0] if candidates else None
                rnum_col = "round_num" if "round_num" in cols else None
                log.info("extract_events: player_buy %d rows — name_col=%s item_col=%s rnum_col=%s cols=%s",
                         len(buy_df), name_col, item_col, rnum_col, cols)
                skipped = 0
                for _, row in buy_df.iterrows():
                    try:
                        tick = int(row["tick"])
                        rnum = None
                        if rnum_col:
                            try:
                                rnum = int(row[rnum_col])
                            except (ValueError, TypeError):
                                pass
                        if rnum is None:
                            rnum = _tick_to_round(tick, buy_phase=True)
                        if rnum is None:
                            skipped += 1
                            continue
                        raw_item = str(row[item_col]).lower() if item_col else ""
                        display  = _BUY_ITEM_NAMES.get(raw_item, raw_item.replace("weapon_", "").replace("item_", "").replace("_", " ").title())
                        player   = str(row[name_col]) if name_col else "?"
                        result.setdefault(int(rnum), []).append({
                            "type":   "buy",
                            "tick":   tick,
                            "player": player,
                            "item":   display,
                        })
                    except Exception as _row_e:
                        log.warning("extract_events: buy row error — %s", _row_e)
                        skipped += 1
                buy_total = sum(1 for evts in result.values() for e in evts if e["type"] == "buy")
                log.info("extract_events: player_buy added %d events, skipped %d rows", buy_total, skipped)
        except Exception as e:
            log.warning("extract_events: player_buy failed — %s", e)

        # ---- Bomb planted ----
        try:
            rows = parser.parse_events(["bomb_planted"], other=["round_num"])
            if rows:
                item = rows[0]
                df = item[1] if isinstance(item, tuple) else item
                if df is not None and not df.empty:
                    cols = list(df.columns)
                    name_col = next((c for c in ["user_name", "player_name", "name"] if c in cols), None)
                    rnum_col = "round_num" if "round_num" in cols else None
                    for _, row in df.iterrows():
                        try:
                            tick  = int(row["tick"])
                            rnum  = int(row[rnum_col]) if rnum_col else _tick_to_round(tick)
                            if rnum is None:
                                continue
                            result.setdefault(int(rnum), []).append({
                                "type":   "plant",
                                "tick":   tick,
                                "player": str(row[name_col]) if name_col else "?",
                            })
                        except Exception:
                            continue
        except Exception as e:
            log.debug("extract_events: bomb_planted failed — %s", e)

        # ---- Bomb defused ----
        try:
            rows = parser.parse_events(["bomb_defused"], other=["round_num"])
            if rows:
                item = rows[0]
                df = item[1] if isinstance(item, tuple) else item
                if df is not None and not df.empty:
                    cols = list(df.columns)
                    name_col = next((c for c in ["user_name", "player_name", "name"] if c in cols), None)
                    rnum_col = "round_num" if "round_num" in cols else None
                    for _, row in df.iterrows():
                        try:
                            tick  = int(row["tick"])
                            rnum  = int(row[rnum_col]) if rnum_col else _tick_to_round(tick)
                            if rnum is None:
                                continue
                            result.setdefault(int(rnum), []).append({
                                "type":   "defuse",
                                "tick":   tick,
                                "player": str(row[name_col]) if name_col else "?",
                            })
                        except Exception:
                            continue
        except Exception as e:
            log.debug("extract_events: bomb_defused failed — %s", e)

    except ImportError:
        log.debug("extract_events: demoparser2 not available — skipping")
    except Exception as e:
        log.warning("extract_events failed: %s", e)

    total = sum(len(v) for v in result.values())
    log.info("extract_events: %d events across %d rounds", total, len(result))
    return result


def extract_ticks(demo, dem_path=None) -> dict:
    """
    Returns {round_num: [{"t": tick, "p": [{"n": name, "x": x, "y": y, "z": z,
                                            "hp": hp, "alive": bool, "side": side,
                                            "armor": int, "helmet": bool,
                                            "w": weapon name or null}]}]}
    Downsampled by TICK_SAMPLE for reasonable data size.

    """
    ticks_df = _to_pd(getattr(demo, "ticks", None))
    if ticks_df is None:
        return {}

    cols = list(ticks_df.columns)
    log.info("extract_ticks columns: %s", cols)

    # Augment with armor/helmet via a second demoparser2 pass (the wrapper
    # already includes these when supported — skip the extra pass then).
    if dem_path and not ({"armor_value", "has_helmet"} <= set(cols)):
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
    z_col      = next((c for c in ["Z", "z", "pos_z"] if c in cols), None)  # altitude — floor selection
    hp_col     = next((c for c in ["health", "hp", "Health"] if c in cols), None)
    alive_col  = next((c for c in ["is_alive", "alive", "isAlive"] if c in cols), None)
    side_col   = next((c for c in ["side", "team_side", "Side"] if c in cols), None)
    armor_col  = next((c for c in ["armor", "armor_value", "kevlar"] if c in cols), None)
    helmet_col = next((c for c in ["has_helmet", "helmet"] if c in cols), None)
    weapon_col = next((c for c in ["weapon_name", "weaponName"] if c in cols), None)  # per-tick weapon (optional)

    if not (name_col and x_col and y_col and "tick" in cols and "round_num" in cols):
        log.warning("missing required tick columns — map tracker disabled")
        return {}

    import pandas as pd
    import numpy as np

    ROUND_START_SKIP = 160  # freeze-time / buy-phase ticks to skip each round

    def _fnum(series):
        """Numeric float64 array (non-numeric → NaN), for vectorised conversion."""
        return pd.to_numeric(series, errors="coerce").to_numpy(dtype="float64")

    def _flag(series, default):
        """Bool array; NaN → default (mirrors the old per-row try/except)."""
        arr = series.to_numpy()
        if arr.dtype == bool:
            return arr
        v = _fnum(series)
        return np.where(np.isnan(v), default, v.astype(bool))

    def _wstr(v):
        """Weapon name or None (NaN / empty → None; NaN in buy/respawn windows)."""
        if v is None:
            return None
        try:
            if pd.isna(v):
                return None
        except (TypeError, ValueError):
            pass
        s = str(v).strip()
        return s if s.lower() not in ("nan", "none", "", "<na>") else None

    # Vectorised rewrite of the old iterrows loop (Phase 4): identical output
    # semantics — NaN → same defaults, int() truncation, stable row order
    # within each tick, frames in ascending tick order — but no per-row Series
    # construction. Guarded by tests/test_ticks_equivalence.py against the
    # stored golden blob.
    result = {}
    for round_num, rdf in ticks_df.groupby("round_num"):
        tick_all  = rdf["tick"].to_numpy()
        all_ticks = np.unique(tick_all)  # == np.sort(rdf["tick"].unique())
        if len(all_ticks) > ROUND_START_SKIP:
            all_ticks = all_ticks[ROUND_START_SKIP:]
        sampled = all_ticks[::TICK_SAMPLE]
        mask    = np.isin(tick_all, sampled)
        if not mask.any():
            result[int(round_num)] = []
            continue

        # Selected rows, sorted by tick with *stable* order inside each tick —
        # exactly the order the old groupby("tick") + row iteration produced.
        idx   = np.nonzero(mask)[0]
        order = idx[np.argsort(tick_all[idx], kind="stable")]

        n      = rdf[name_col].to_numpy()[order]
        xs     = _fnum(rdf[x_col])[order]
        ys     = _fnum(rdf[y_col])[order]
        zs     = _fnum(rdf[z_col])[order] if z_col else None
        hpv    = _fnum(rdf[hp_col])[order] if hp_col else None
        if hpv is not None:
            hpv = np.where(np.isnan(hpv), 100, hpv)
            hp = np.trunc(hpv).astype("int64")
        else:
            hp = np.full(len(order), 100, dtype="int64")
        alive  = (_flag(rdf[alive_col], hp > 0)[order] if alive_col
                  else (hp > 0))
        px     = np.where(np.isnan(xs), 0.0, xs)
        py     = np.where(np.isnan(ys), 0.0, ys)
        armv   = _fnum(rdf[armor_col])[order] if armor_col else None
        if armv is not None:
            armv = np.where(np.isnan(armv), 0, armv)
            armor = np.trunc(armv).astype("int64")
        else:
            armor = np.zeros(len(order), dtype="int64")
        helmet = (_flag(rdf[helmet_col], False)[order] if helmet_col
                  else np.zeros(len(order), dtype=bool))
        side   = (rdf[side_col].where(rdf[side_col].notna(), "?").astype(str).to_numpy()[order]
                  if side_col else np.full(len(order), "?"))
        wname  = (rdf[weapon_col].to_numpy()[order] if weapon_col else None)

        # Single linear pass: start a new frame whenever the tick changes.
        frames = []
        cur_tick = None
        players  = None
        for i in range(len(order)):
            t = int(tick_all[order[i]])
            if t != cur_tick:
                if players is not None:
                    frames.append({"t": cur_tick, "p": players})
                cur_tick, players = t, []
            players.append({
                "n":      str(n[i]),
                "x":      float(px[i]),
                "y":      float(py[i]),
                "z":      (None if (zs is None or math.isnan(zs[i])) else float(zs[i])),
                "hp":     int(hp[i]),
                "alive":  bool(alive[i]),
                "side":   str(side[i]),
                "armor":  int(armor[i]),
                "helmet": bool(helmet[i]),
                "w":      (_wstr(wname[i]) if wname is not None else None),
            })
        if players is not None:
            frames.append({"t": cur_tick, "p": players})

        result[int(round_num)] = frames  # already in ascending tick order

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
_SKIN_IDS:   dict = {}   # paint_index (str) -> skin id (e.g. "skin-f64cdaac0b90")
_SKIN_NAMES_LOADED = False

_BASE_WEAPON_IDS: dict = {}  # def_index (int) -> base weapon image id (e.g. "base_weapon-weapon_ak47")


def _load_skin_names() -> dict:
    """Build paint_index -> skin name and paint_index -> skin id dicts from struct_db/skins.json."""
    global _SKIN_NAMES, _SKIN_IDS, _SKIN_NAMES_LOADED
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
        _SKIN_NAMES = {}
        _SKIN_IDS   = {}
        for item in skins:
            if not isinstance(item, dict) or not item.get("paint_index"):
                continue
            pi         = str(item["paint_index"])
            weapon_id  = str(item.get("weapon", {}).get("weapon_id", ""))
            _SKIN_NAMES[pi] = _strip_prefix(item.get("name", ""))
            if item.get("id"):
                # Key by (paint_index, weapon_id) to avoid collisions where the
                # same paint design exists on multiple weapon types (113 such cases).
                _SKIN_IDS[f"{pi}:{weapon_id}"] = item["id"]
        log.info("skin names: loaded %d entries from skins.json", len(_SKIN_NAMES))
    except Exception as e:
        log.warning("skin names: failed to load from skins.json: %s", e)
        _SKIN_NAMES = {}
        _SKIN_IDS   = {}
    return _SKIN_NAMES


def _load_base_weapon_ids() -> None:
    """Build def_index -> base weapon image id from struct_db/base_weapons.json."""
    global _BASE_WEAPON_IDS
    p = STRUCT_DB_DIR / "base_weapons.json"
    if not p.exists():
        log.warning("base weapons: base_weapons.json not found at %s", p)
        return
    try:
        with open(p, encoding="utf-8") as f:
            items = json.load(f)
        _BASE_WEAPON_IDS = {
            item["def_index"]: item["id"]
            for item in items
            if isinstance(item, dict) and item.get("def_index") and item.get("id")
        }
        log.info("base weapons: loaded %d entries from base_weapons.json", len(_BASE_WEAPON_IDS))
    except Exception as e:
        log.warning("base weapons: failed to load from base_weapons.json: %s", e)


# defindex values that appear in the buy stream but are gear, not loadout
# weapons (grenades, armor, defuse kit, C4) — never stored in demo_cosmetics.
# 43-49 grenade/C4 defindices per struct_db/base_weapons.json.
_NON_LOADOUT_DEFIDX = frozenset({43, 44, 45, 46, 47, 48, 49, 50, 51, 55})

# Full buytime is 15 s; +1 s of slack so late purchases still land in-cluster.
_BUY_WINDOW_SECS = 16


def _make_cosmetic_item(def_idx: int, paint, st_count, skin_names: dict) -> dict:
    """Build one demo_cosmetics item row, merging optional paint data."""
    paint      = paint or {}
    paint_idx  = int(paint.get("paint_index") or 0)
    paint_seed = paint.get("paint_seed")
    wear_f     = paint.get("wear")
    custom     = paint.get("custom_name")
    is_agent   = def_idx >= 4600 and wear_f is None
    if is_agent:
        item_name = _AGENT_NAMES.get(def_idx, f"Agent #{def_idx}")
        side      = _AGENT_SIDE.get(def_idx, "both")
        skin_name = None
    else:
        item_name = _WEAPON_NAMES.get(def_idx, f"Item #{def_idx}")
        side      = _WEAPON_SIDE.get(def_idx, "both")
        skin_name = skin_names.get(str(paint_idx)) if paint_idx else None
    return {
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
        "side":        side,
        "weapon_cat":  "knife" if def_idx in _KNIFE_DEF_INDICES else None,
    }


def _side_purchase_loadouts(parser, sid_info: dict):
    """Per-player CT/T loadout def_index sets from the demo's buy stream.

    Round boundaries come from ``cs_pre_restart``, the side timeline from
    ``player_team`` (initial side inferred when a player buys before their
    first logged switch), and ``item_pickup`` events inside the buy window
    after each boundary are that round's actual purchases.

    Returns ``{sid: {"CT": set(defidx), "T": set(defidx)}}`` or ``None``
    when the purchase events are unavailable (caller uses the fallback).
    """
    import bisect
    try:
        bounds_df = parser.parse_event("cs_pre_restart")
        team_df   = parser.parse_event("player_team", player=["steamid"])
        pick_df   = parser.parse_event("item_pickup", player=["steamid"])
    except Exception as e:
        log.warning("extract_cosmetics: purchase events unavailable (%s)", e)
        return None

    try:
        boundaries = sorted({int(t) for t in bounds_df["tick"]})
    except Exception:
        boundaries = []
    if not boundaries:
        return None

    def _sid_col(df):
        return "user_steamid" if "user_steamid" in df.columns else "steamid"

    # side timeline: sid -> [(tick, side)] sorted by tick
    switches: dict = {}
    try:
        sid_col = _sid_col(team_df)
        for _, r in team_df.iterrows():
            sid = str(r.get(sid_col, ""))
            if not sid:
                continue
            switches.setdefault(sid, []).append(
                (int(r["tick"]), "CT" if int(r["team"]) == 3 else "T"))
    except Exception:
        pass
    for sid in switches:
        switches[sid].sort()

    def _initial_side(sid: str) -> str:
        """Side before the player's first logged switch.

        An odd number of switches means the demo ended on the opposite
        side it started on, so flip the end-of-demo side.
        """
        final = sid_info.get(sid, {}).get("team") or "CT"
        if len(switches.get(sid, [])) % 2 == 1:
            final = "T" if final == "CT" else "CT"
        return final

    def _side_at(sid: str, tick: int, cluster_defs) -> str:
        evs   = switches.get(sid, [])
        prior = [s for (t, s) in evs if t <= tick]
        if prior:
            return prior[-1]
        for di in cluster_defs:  # cross-check with side-specific items
            s = _WEAPON_SIDE.get(di)
            if s in ("CT", "T"):
                return s
        return _initial_side(sid)

    try:
        tickrate = int(parser.parse_header().get("tickrate", 128) or 128)
    except Exception:
        tickrate = 128
    buy_window = tickrate * _BUY_WINDOW_SECS

    try:
        loadouts = {sid: {"CT": set(), "T": set()} for sid in sid_info}
        sid_col  = _sid_col(pick_df)
        pick_df  = pick_df[pick_df["defindex"].isin(list(_WEAPON_NAMES.keys()))
                          & ~pick_df["defindex"].isin(_NON_LOADOUT_DEFIDX)]
        for sid, sides in loadouts.items():
            mine = pick_df[pick_df[sid_col].astype(str) == sid]
            clusters = {}  # boundary index -> [(tick, defidx)]
            for _, r in mine.iterrows():
                tick = int(r["tick"])
                bi = bisect.bisect_right(boundaries, tick) - 1
                if bi < 0 or tick - boundaries[bi] > buy_window:
                    continue  # mid-round pickup (dropped weapon), not a buy
                clusters.setdefault(bi, []).append((tick, int(r["defindex"])))
            for bi, entries in clusters.items():
                side = _side_at(sid, min(t for t, _ in entries),
                                [d for _, d in entries])
                sides[side].update(d for _, d in entries)
        return loadouts
    except Exception as e:
        log.warning("extract_cosmetics: purchase clustering failed (%s)", e)
        return None


def _extract_cosmetics_legacy(parser, skin_names, stattrak, sid_info, painted, agents) -> list:
    """Fallback loadout path: parse_skins snapshot + weapon_fire fill-in.

    Used only when the purchase events (item_pickup / player_team /
    cs_pre_restart) are unavailable; preserves the previous behavior.
    """
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

    sid_items: dict = {}
    for sid in agents:
        sid_items[sid] = list(agents[sid])
    for sid, paint_by_def in painted.items():
        for di, p in paint_by_def.items():
            sid_items.setdefault(sid, []).append(
                _make_cosmetic_item(di, p, stattrak.get(sid, {}).get(di), skin_names))

    for sid, used_defidxs in player_weapons_used.items():
        existing = {i["def_index"] for i in sid_items.get(sid, []) if not i["is_agent"]}
        for defidx in sorted(used_defidxs):
            if defidx not in existing:
                sid_items.setdefault(sid, []).append(
                    _make_cosmetic_item(defidx, None, None, skin_names))

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


def extract_cosmetics(dem_path: str) -> list:
    """Return per-player CT-side and T-side loadout data for a demo.

    Loadouts are rebuilt from the demo's purchase stream: ``item_pickup``
    events inside the buy window after each ``cs_pre_restart`` boundary,
    attributed to the player's side at that moment (``player_team`` switch
    timeline; initial side inferred).  Paint / seed / wear / custom names
    are joined in from ``parse_skins()`` by (steamid, def_index); painted
    items missing from the purchase stream are kept and assigned by
    weapon class (CT / T / both) so no data is lost versus the old
    snapshot parser.  StatTrak comes from the ``parse_ticks`` pass.

    Agents only exist in ``parse_skins()`` (demoparser2 exposes no agent
    field, so at most one per player) and are tagged ``ct_agent`` /
    ``t_agent`` via their class.  Falls back to the legacy
    parse_skins + weapon_fire snapshot when the purchase events are
    unavailable (older demos).
    """
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

    # steamid -> {name, team (end-of-demo side, used for ordering only)}
    sid_info: dict = {}
    for _, row in info_df.iterrows():
        sid_info[str(row["steamid"])] = {
            "name": str(row["name"]),
            "team": "CT" if int(row["team_number"]) == 3 else "T",
        }

    # ---- parse_skins snapshot: paint info per (sid, def) + agents ----
    painted: dict = {}  # sid -> {def_index -> paint dict}
    agents:  dict = {}  # sid -> [item, ...]
    for _, row in skins_df.iterrows():
        sid        = str(row["steamid"])
        def_idx    = int(row["def_index"])
        paint_idx  = int(row["paint_index"]) if not pd.isna(row["paint_index"]) else 0
        paint_seed = int(row["paint_seed"]) if not pd.isna(row.get("paint_seed", float("nan"))) else None
        wear_raw   = row.get("paint_wear")
        wear_f     = None
        if wear_raw is not None and not pd.isna(wear_raw):
            try:
                wear_f = round(struct.unpack("f", struct.pack("I", int(wear_raw)))[0], 4)
            except Exception:
                pass
        custom = row.get("custom_name")
        custom = str(custom) if custom is not None and not pd.isna(custom) else None

        # Agents have no wear and typically def_index >= 4600
        if def_idx >= 4600 and wear_f is None:
            agents.setdefault(sid, []).append(
                _make_cosmetic_item(def_idx, None, stattrak.get(sid, {}).get(def_idx), skin_names))
        else:
            painted.setdefault(sid, {})[def_idx] = {
                "paint_index": paint_idx,
                "paint_seed":  paint_seed,
                "wear":        wear_f,
                "custom_name": custom,
            }

    # ---- per-side purchase loadouts (authoritative) ----
    loadouts = _side_purchase_loadouts(parser, sid_info)
    if loadouts is None:
        return _extract_cosmetics_legacy(parser, skin_names, stattrak, sid_info, painted, agents)

    result = []
    for sid, info in sid_info.items():
        paint_by_def = painted.get(sid, {})
        ct_defs = set(loadouts[sid]["CT"])
        t_defs  = set(loadouts[sid]["T"])
        # Union safety: keep every painted item, assigned by weapon class
        # ('both'-class such as knives/gloves/SGs go to both sides).
        for di in paint_by_def:
            cls = _WEAPON_SIDE.get(di, "both")
            if cls in ("CT", "both"):
                ct_defs.add(di)
            if cls in ("T", "both"):
                t_defs.add(di)

        all_defs = ct_defs | t_defs
        items = []
        for di in sorted(all_defs):
            it = _make_cosmetic_item(di, paint_by_def.get(di),
                                     stattrak.get(sid, {}).get(di), skin_names)
            in_ct, in_t = di in ct_defs, di in t_defs
            it["side"] = "both" if (in_ct and in_t) else ("CT" if in_ct else "T")
            items.append(it)

        result.append({
            "steamid":    sid,
            "name":       info["name"],
            "team":       info["team"],
            "ct_agent":   next((a for a in agents.get(sid, []) if a["side"] in ("CT", "both")), None),
            "t_agent":    next((a for a in agents.get(sid, []) if a["side"] in ("T",  "both")), None),
            "ct_weapons": sorted([i for i in items if i["side"] in ("CT", "both")], key=lambda x: x["def_index"]),
            "t_weapons":  sorted([i for i in items if i["side"] in ("T", "both")],  key=lambda x: x["def_index"]),
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
        killers   = {k["attacker"] for k in rk if k["attacker"] not in _nan and k["attacker"] != k["victim"]}
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


def _duration(h: dict) -> str:
    try:
        return f"{float(h['playback_time']):.1f}s"
    except Exception:
        try:
            return f"{int(h['ticks_played']) / int(h['tick_rate']):.1f}s"
        except Exception:
            return "?"


# ── Parse jobs ─────────────────────────────────────────────────────────────────
# Parsing a demo takes ~30–60 s of CPU work.  Uploads therefore return
# immediately with a job id; the parse runs in a background thread and clients
# poll /api/jobs/<job_id>.  Jobs live in memory (bounded, newest kept);
# an in-flight job is lost if the server restarts, which is acceptable for
# the dev server (the upload can simply be retried).
_parse_jobs: "OrderedDict[str, dict]" = OrderedDict()
_jobs_lock = threading.Lock()
_MAX_JOBS = 32


def _register_job(job_id: str, filename: str, tmp_path: str):
    with _jobs_lock:
        _parse_jobs[job_id] = {
            "status":   "parsing",
            "filename": filename,
            "tmp_path": tmp_path,
            "created":  time.time(),
        }
        while len(_parse_jobs) > _MAX_JOBS:
            _parse_jobs.popitem(last=False)


def _finish_job(job_id: str, status: str, **extra):
    with _jobs_lock:
        job = _parse_jobs.get(job_id)
        if job is None:
            return
        job["status"] = status
        job["finished"] = time.time()
        job.update(extra)


def _run_parse_job(job_id: str):
    with _jobs_lock:
        job = dict(_parse_jobs.get(job_id, {}))
    tmp_path = job.get("tmp_path", "")
    filename = job.get("filename", "")
    try:
        data = parse_demo(tmp_path)
        # Guard: a file that isn't a real CS2 demo parses to an *empty* result
        # (demoparser2 doesn't raise on foreign files). Refuse it explicitly so
        # invalid uploads don't become phantom empty demos in the library.
        if not (data.get("rounds") or data.get("kills")):
            raise ValueError(
                "no rounds or kills parsed — file does not look like a valid CS2 demo"
            )
        data["filename"] = filename
        session_id = data["session_id"]
        if session_id in _session_cache:
            _session_cache.move_to_end(session_id)  # LRU: a read refreshes recency
        cached = _session_cache.get(session_id, {})
        ticks    = cached.get("ticks", {})
        grenades = cached.get("grenades", {})
        events   = cached.get("events", {})
        shots    = cached.get("shots", {})
        _db_save(session_id, filename, data["header"]["map"], data, ticks, grenades, events, shots)

        # Persist the .dem so re-parse endpoints (tracers etc.) can reuse it
        stored_path = DEMOS_DIR / f"{session_id}.dem"
        shutil.copy2(tmp_path, stored_path)
        if session_id in _session_cache:
            _session_cache[session_id]["dem_path"] = str(stored_path)

        log.info("parse job %s: completed %s — map=%s rounds=%s (%.2fs)",
                 job_id, filename, data["header"].get("map"),
                 data.get("total_rounds"), time.monotonic() - job.get("created", time.time()))
        _finish_job(job_id, "done", data=data)
    except Exception as e:
        log.error("parse job %s: failed for %s — %s", job_id, filename, e, exc_info=True)
        traceback.print_exc()
        _finish_job(job_id, "error", error=str(e))
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def _tick_side_lookup(demo) -> dict:
    """Build a per-player (steamid → (tick array, team array)) lookup from the
    tick data so any kill can be attributed to a side using the player's actual
    team at that moment (survives half-time side swaps)."""
    ticks_df = _to_pd(getattr(demo, "ticks", None))
    if ticks_df is None or not ({"steamid", "tick", "team_num"} <= set(ticks_df.columns)):
        return {}
    lookup = {}
    for sid, grp in ticks_df.groupby("steamid"):
        grp = grp.sort_values("tick")
        try:
            lookup[str(int(sid))] = (grp["tick"].to_numpy(), grp["team_num"].to_numpy())
        except (TypeError, ValueError):
            continue
    return lookup


def _side_at(lookup: dict, sid: str, tick: int):
    """Return 'CT'/'T' for a steamid at a tick (nearest earlier sample), else None."""
    entry = lookup.get(str(int(sid))) if sid and sid not in ("0", "nan") else None
    if not entry:
        return None
    ticks, teams = entry
    i = int(np.searchsorted(ticks, tick, side="right")) - 1
    if i < 0:
        return None
    t = int(teams[i])
    return "CT" if t == 3 else ("T" if t == 2 else None)


def parse_demo(dem_path: str, session_id: str = None) -> dict:
    from parser_foundation import Demo

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

    # Team labels are fixed in CS2: one side is CT, the other T — the
    # frontend colors players by these labels, so they are constants.
    ct_team = "CT"
    t_team  = "T"

    kills_df = _to_pd(demo.kills)

    rounds_df = _to_pd(demo.rounds)
    # Per-round winning side — fallback attribution only (see _kill_sides below).
    round_winner = {}
    if rounds_df is not None:
        for _, row in rounds_df.iterrows():
            round_winner[int(row.get("round_num", 0) or 0)] = str(row.get("winner", "") or "").upper()

    def _opposite(side: str) -> str:
        return "T" if side == "CT" else "CT"

    # Ground truth for kill-team attribution: each player's actual team at the
    # kill tick (per-tick team_num tracks half-time swaps).  This is required
    # because in timer/defuse endings the losing side can have survivors and
    # the winning side can have victims, so the round winner alone is not a
    # reliable side source.
    tick_side = _tick_side_lookup(demo)

    # ---- Rounds ----
    # Per-round start/end ticks come from demoparser2's round_start/round_end
    # events (parser_foundation.round_index: (round, start_tick, end_tick)).
    # 0 means "unknown" (e.g. last round still running) → None in the payload.
    # Used by the results page for kill-feed timestamps and jump-list times.
    round_ticks = {
        ri[0]: (ri[1] or None, ri[2] or None) for ri in (demo.round_index or [])
    }
    rounds = []
    if rounds_df is not None:
        ct_score = t_score = 0
        for _, row in rounds_df.iterrows():
            rnum   = int(row.get("round_num", 0) or 0)
            winner = str(row.get("winner", "?") or "?").upper()
            if winner == "CT":
                winner_side = "CT"; ct_score += 1
            elif winner == "T":
                winner_side = "T";  t_score  += 1
            else:
                winner_side = winner
            reason = str(row.get("reason", "?") or "?").replace("_", " ").title()
            st, et = round_ticks.get(rnum, (None, None))
            rounds.append({
                "round_num":   rnum,
                "winner_side": winner_side,
                "reason":      reason,
                "ct_score":    ct_score,
                "t_score":     t_score,
                "start_tick":  st,
                "end_tick":    et,
            })

    ct_wins = sum(1 for r in rounds if r["winner_side"] == "CT")
    t_wins  = sum(1 for r in rounds if r["winner_side"] == "T")

    # ---- Kills ----
    kills = []
    if kills_df is not None and not kills_df.empty:
        for _, row in kills_df.iterrows():
            attacker_sid = str(row.get("attacker_steamid", "") or "")
            victim_sid   = str(row.get("victim_steamid", "") or "")
            rnum          = int(row.get("round_num", 0) or 0)
            tick          = int(row.get("tick", 0) or 0)
            winner        = round_winner.get(rnum, "")

            # 1) Prefer per-tick team data (ground truth, swap-aware; also the
            #    only source that is correct when a match has friendly fire on).
            vic_team = _side_at(tick_side, victim_sid, tick)
            att_team = _side_at(tick_side, attacker_sid, tick)
            # Cross-fill from the other player's side only as a last resort:
            # correct for the overwhelmingly common FF-off case, approximate
            # otherwise.
            if vic_team and not att_team:
                att_team = _opposite(vic_team)
            if att_team and not vic_team:
                vic_team = _opposite(att_team)
            # 2) Fallback: infer from the round winner (killer → winning side,
            #    victim → losing side; both same side on a suicide).
            if (not vic_team or not att_team) and winner in ("CT", "T"):
                v = _opposite(winner)
                vic_team = vic_team or v
                att_team = att_team or (v if (attacker_sid and victim_sid and attacker_sid == victim_sid) else winner)
            vic_team = vic_team or "?"
            att_team = att_team or "?"

            kills.append({
                "tick":          int(row.get("tick", 0) or 0),
                "round_num":     rnum,
                "attacker":      _safe(row.get("attacker_name"), "?"),
                "attacker_team": att_team,
                "victim":        _safe(row.get("victim_name"), "?"),
                "victim_team":   vic_team,
                "weapon":        _safe(row.get("weapon"), "?"),
                "headshot":      bool(row.get("headshot")),
                "through_smoke": bool(row.get("thrusmoke")),
                "no_scope":      bool(row.get("noscope")),
                "penetrated":    bool(row.get("penetrated")),
                "assister":      _safe(row.get("assister_name"), "") or "",
            })

    # ---- Steam ID map (name -> steamid64) ----
    steamids: dict = {}
    if kills_df is not None and not kills_df.empty:
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
        # Self-kill: attacker and victim are the same player — count the
        # death, but do not credit a kill (or headshot).
        self_kill = bool(att and vic and att == vic)
        if att and att != "nan" and att != "?" and not self_kill:
            inc(att, "kills")
            if k["headshot"]: inc(att, "hs")
        if vic and vic != "nan" and vic != "?":
            inc(vic, "deaths")
        # Team label: use the player's side in their LAST recorded action so
        # players who swapped sides at half-time show under their final side.
        for p, side in ((att, k["attacker_team"]), (vic, k["victim_team"])):
            if p and p not in ("nan", "?") and side in ("CT", "T"):
                stats.setdefault(p, {})["team"] = side
        assister = k.get("assister") or ""
        if assister and assister not in ("nan", "?"):
            inc(assister, "assists")

    damages_df = _to_pd(demo.damages)
    if damages_df is not None and not damages_df.empty:
        for _, row in damages_df.iterrows():
            att = row.get("attacker_name")
            # "?" is the bomb (planted_c4) or an unattributed entity — not a player.
            if att and str(att) not in ("nan", "?"):
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
    session_id = session_id or str(uuid.uuid4())
    ticks_by_round    = extract_ticks(demo, dem_path)
    grenades_by_round = extract_grenades(dem_path, ticks_by_round)
    events_by_round   = extract_events(dem_path, ticks_by_round)
    shots_by_round    = extract_shots(dem_path, ticks_by_round)
    if len(_session_cache) >= MAX_SESSIONS:
        _session_cache.popitem(last=False)
    _session_cache[session_id] = {
        "ticks":    ticks_by_round,
        "grenades": grenades_by_round,
        "events":   events_by_round,
        "shots":    shots_by_round,
        "map_name": header["map"],
        "dem_path": str(dem_path) if dem_path else None,
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


# ── Static frontend (built React SPA) ──────────────────────────────────────────
# The React app is built into static_react/ (`npm run build` inside frontend/).
# Client-side routes: /, /loadout/:demoId, /results/:demoId, /map/:demoId,
# /aim/:demoId, /admin — all served by index.html, so unknown non-API paths
# fall back to the SPA entry point.
STATIC_DIR = Path(__file__).parent / "static_react"
_SPA_FIRST_SEGMENTS = {"loadout", "results", "map", "aim", "admin"}


def _serve_spa_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return (
            "<h1>Frontend not built</h1>"
            "<p>Run <code>npm run build</code> inside <code>frontend/</code> to produce "
            "<code>static_react/</code>.</p>",
            503,
        )
    return send_from_directory(str(STATIC_DIR), "index.html")


@app.route("/")
def index():
    return _serve_spa_index()


@app.route("/<path:subpath>")
def spa_or_static(subpath):
    """Serve built-frontend assets; fall back to the SPA for client routes."""
    # 1) Static file from the build output (assets/, favicon.svg, icons.svg, …).
    #    send_from_directory already guards against path traversal; the prefix
    #    check is belt-and-braces.
    static_root = STATIC_DIR.resolve()
    candidate = (STATIC_DIR / subpath).resolve()
    if candidate.is_file() and str(candidate).startswith(str(static_root)):
        return send_from_directory(str(STATIC_DIR), subpath)
    # 2) Client-side SPA routes (e.g. /viewer/abc-123, /loadout/xyz, /admin).
    if subpath.split("/", 1)[0] in _SPA_FIRST_SEGMENTS:
        return _serve_spa_index()
    return jsonify({"error": "Not found"}), 404


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

    job_id = str(uuid.uuid4())
    _register_job(job_id, f.filename, tmp_path)
    threading.Thread(target=_run_parse_job, args=(job_id,), daemon=True).start()
    return jsonify({"job_id": job_id, "status": "parsing"}), 202


@app.route("/api/jobs/<job_id>")
def api_jobs_status(job_id):
    """Poll the status of a background parse job (started by /api/parse)."""
    with _jobs_lock:
        job = _parse_jobs.get(job_id)
        if job is None:
            return jsonify({"error": "Unknown job — the server may have restarted"}), 404
        snapshot = dict(job)
    snapshot.pop("tmp_path", None)
    return jsonify(snapshot)


@app.route("/api/ticks/<session_id>/<int:round_num>")
def api_ticks(session_id, round_num):
    session = _session_cache.get(session_id)
    if session is None:
        session = _db_load_session(session_id)
    else:
        _session_cache.move_to_end(session_id)  # LRU: a hit refreshes recency
    if not session:
        return jsonify({"error": "Session expired — please re-upload the demo"}), 404
    frames   = session["ticks"].get(round_num, [])
    grenades = session.get("grenades", {}).get(round_num, [])
    events   = session.get("events",   {}).get(round_num, [])
    # Lazy-parse shots if missing (session loaded from DB cache before this feature existed)
    if "shots" not in session:
        dem_path = session.get("dem_path") or (
            str(DEMOS_DIR / f"{session_id}.dem")
            if (DEMOS_DIR / f"{session_id}.dem").exists() else None
        )
        session["shots"] = extract_shots(dem_path, session["ticks"]) if dem_path else {}
    shots = session["shots"].get(round_num, [])
    return jsonify({"frames": frames, "count": len(frames), "grenades": grenades, "events": events, "shots": shots})


@app.route("/api/map_info/<map_name>")
def api_map_info(map_name):
    data = _get_map_bounds(map_name)
    data["floors"] = _map_floors(map_name)
    return jsonify(data)


@app.route("/api/maps_ready")
def api_maps_ready():
    # Check for map images in local directories first (no awpy dependency)
    for search_dir in [
        Path(__file__).parent / "maps",
        Path(__file__).parent / "images" / "maps",
    ]:
        if search_dir.exists() and any(search_dir.glob("*.png")):
            return jsonify({"ready": True})
    # Fallback to awpy if installed
    try:
        import awpy.data
        maps_dir = awpy.data.MAPS_DIR
        ready = maps_dir.exists() and any(maps_dir.glob("*.png"))
        return jsonify({"ready": ready})
    except Exception:
        return jsonify({"ready": False})


@app.route("/api/download_maps", methods=["POST"])
def api_download_maps():
    # Map images can be placed in maps/ or images/maps/ directories.
    # If awpy is installed, use it to fetch; otherwise return success (user may have placed images manually).
    try:
        import awpy.data, awpy.data.utils
        awpy.data.utils.create_data_dir_if_not_exists()
        awpy.data.utils.fetch_resource("maps", awpy.data.CURRENT_BUILD_ID)
        return jsonify({"success": True})
    except ImportError:
        # No awpy — user can place map images manually in maps/ or images/maps/
        return jsonify({"success": True, "message": "awpy not installed; place map images manually"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/images/<path:filename>")
def serve_image(filename):
    images_dir = Path(__file__).parent / "images"
    return send_from_directory(str(images_dir), filename)


@app.route("/api/map_image/<map_name>")
def api_map_image(map_name):
    return _serve_map_image(map_name, "default")


@app.route("/api/map_image/<map_name>/<floor>")
def api_map_image_floor(map_name, floor):
    return _serve_map_image(map_name, floor)


def _serve_map_image(map_name: str, floor: str):
    """Serve a map floor image. Floor ``default`` → <map>.png, otherwise
    <map>_<floor>.png.  Local maps/ first; awpy is a last-resort fallback."""
    fname = map_name if floor == "default" else f"{map_name}_{floor}"
    for search_dir in [
        Path(__file__).parent / "maps",
        Path(__file__).parent / "images" / "maps",
        Path(__file__).parent / "images",
    ]:
        img_path = search_dir / f"{fname}.png"
        if img_path.exists():
            return send_file(str(img_path), mimetype="image/png")
    try:
        import awpy.data
        img_path = awpy.data.MAPS_DIR / f"{fname}.png"
        if img_path.exists():
            return send_file(str(img_path), mimetype="image/png")
    except Exception:
        pass
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


@app.route("/api/demos/<demo_id>/loadout")
def api_demos_loadout(demo_id):
    """Get player loadout data for a demo."""
    data = _db_get(demo_id)
    if data is None:
        return jsonify({"error": "Demo not found"}), 404
    
    # Extract loadout information from the demo data
    loadout_data = {
        "demo_id": demo_id,
        "map": data.get("header", {}).get("map", "Unknown Map"),
        "filename": data.get("filename", "Unknown Demo"),
        "players": []
    }
    
    # Connect to database to get cosmetics data
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    try:
        # Get all cosmetics for this demo
        cosmetics = con.execute(
            "SELECT * FROM demo_cosmetics WHERE demo_id = ? ORDER BY steamid, player_name",
            (demo_id,)
        ).fetchall()
        
        # Group cosmetics by player
        player_cosmetics = {}
        for cosmetic in cosmetics:
            key = (cosmetic["steamid"], cosmetic["player_name"])
            if key not in player_cosmetics:
                player_cosmetics[key] = {
                    "name": cosmetic["player_name"],
                    "steamid": cosmetic["steamid"],
                    "team": cosmetic["team"],
                    "kills": 0,
                    "deaths": 0,
                    "assists": 0,
                    "kd_ratio": 0.0,
                    "headshot_pct": 0.0,
                    "total_damage": 0,
                    "weapons": [],
                    "ct_agent": None,
                    "t_agent": None,
                    "skins": []
                }
            
            p = player_cosmetics[key]
            
            # Add scoreboard data if available
            if data.get("scoreboard"):
                for scoreboard_player in data["scoreboard"]:
                    if scoreboard_player["name"] == cosmetic["player_name"] and scoreboard_player["steamid"] == cosmetic["steamid"]:
                        p["kills"] = scoreboard_player.get("kills", 0)
                        p["deaths"] = scoreboard_player.get("deaths", 0)
                        p["assists"] = scoreboard_player.get("assists", 0)
                        p["kd_ratio"] = scoreboard_player.get("kd", 0.0)
                        p["headshot_pct"] = scoreboard_player.get("hs_pct", 0.0)
                        p["total_damage"] = scoreboard_player.get("dmg", 0)
            
            # Process cosmetics
            if cosmetic["is_agent"]:
                # Agents split by side (a 'both'-class agent goes to both) —
                # the old single p["agent"] slot overwrote per row (last won).
                agent = {
                    "def_index": cosmetic["def_index"],
                    "item_name": cosmetic["item_name"],
                    "skin_name": cosmetic["skin_name"],
                    "paint_index": cosmetic["paint_index"],
                    "paint_seed": cosmetic["paint_seed"],
                    "wear": cosmetic["wear"],
                    "wear_tier": cosmetic["wear_tier"],
                    "custom_name": cosmetic["custom_name"],
                    "stattrak": cosmetic["stattrak"],
                    "side": cosmetic["side"]
                }
                if cosmetic["side"] in ("CT", "both"):
                    p["ct_agent"] = agent
                if cosmetic["side"] in ("T", "both"):
                    p["t_agent"] = agent
            else:
                # Add to skins list
                p["skins"].append({
                    "def_index": cosmetic["def_index"],
                    "item_name": cosmetic["item_name"],
                    "skin_name": cosmetic["skin_name"],
                    "paint_index": cosmetic["paint_index"],
                    "paint_seed": cosmetic["paint_seed"],
                    "wear": cosmetic["wear"],
                    "wear_tier": cosmetic["wear_tier"],
                    "custom_name": cosmetic["custom_name"],
                    "stattrak": cosmetic["stattrak"],
                    "side": cosmetic["side"],
                    "skin_image_id":    _SKIN_IDS.get(f"{cosmetic['paint_index']}:{cosmetic['def_index']}") if cosmetic["paint_index"] else None,
                    "base_weapon_key": _BASE_WEAPON_IDS.get(cosmetic["def_index"]),
                })
        
        # Convert to list for JSON serialization
        loadout_data["players"] = list(player_cosmetics.values())
        
        # Add weapon stats from aim breakdown if available
        if data.get("aim_breakdown"):
            for aim_player in data["aim_breakdown"]:
                key = (None, aim_player["name"])  # Use name as key for lookup
                for player in loadout_data["players"]:
                    if player["name"] == aim_player["name"]:
                        # Add weapon stats from aim breakdown
                        if aim_player.get("weapons"):
                            for weapon in aim_player["weapons"]:
                                player["weapons"].append({
                                    "weapon": weapon["weapon"],
                                    "kills": weapon.get("kills", 0),
                                    "shots": weapon.get("shots", 0),
                                    "hits": weapon.get("hits", 0),
                                    "dmg": weapon.get("dmg", 0),
                                    "hs_kills": weapon.get("hs_kills", 0)
                                })
        
    except Exception as e:
        log.error(f"Error in loadout API: {e}")
        return jsonify({"error": "Failed to process loadout data"}), 500
    finally:
        con.close()
    
    return jsonify(loadout_data)


@app.route("/api/demos/<demo_id>/reparse", methods=["POST"])
def api_demos_reparse(demo_id):
    """Re-run the parser over the stored .dem and replace this demo's data.

    Used to fix demos parsed with an older/buggy parser version (e.g. rows
    with round_num=0).  Requires the original .dem to still be in demos_store/.
    """
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    row = con.execute("SELECT id, filename FROM demos WHERE id = ?", (demo_id,)).fetchone()
    con.close()
    if not row:
        return jsonify({"error": "Demo not found"}), 404

    dem_path = DEMOS_DIR / f"{demo_id}.dem"
    if not dem_path.exists():
        return jsonify({"error": "Stored .dem file not found in demos_store — re-upload to rebuild this demo"}), 410

    log.info("reparse: starting — demo_id=%s", demo_id)
    t0 = time.monotonic()
    try:
        data = parse_demo(str(dem_path), session_id=demo_id)
    except Exception as e:
        log.error("reparse: failed for %s — %s", demo_id, e, exc_info=True)
        return jsonify({"error": f"Re-parse failed: {e}"}), 500

    filename = row["filename"] or f"{demo_id}.dem"
    data["filename"] = filename
    if demo_id in _session_cache:
        _session_cache.move_to_end(demo_id)  # LRU: a read refreshes recency
    cached = _session_cache.get(demo_id, {})
    _db_save(demo_id, filename, data["header"]["map"], data,
             cached.get("ticks"), cached.get("grenades"), cached.get("events"),
             cached.get("shots"))

    elapsed = time.monotonic() - t0
    log.info("reparse: completed %s — rounds=%s ticks=%d (%.2fs)",
             demo_id, data.get("total_rounds"), len(cached.get("ticks", {})), elapsed)
    return jsonify(data)


@app.route("/api/demos/<demo_id>", methods=["DELETE"])
def api_demos_delete(demo_id):
    if _db_delete(demo_id):
        # Remove the stored .dem so the library doesn't orphan gigabytes
        dem_file = DEMOS_DIR / f"{demo_id}.dem"
        if dem_file.exists():
            try:
                dem_file.unlink()
            except OSError as e:
                log.warning("delete: could not remove %s — %s", dem_file, e)
        # Drop the in-memory session, if any
        _session_cache.pop(demo_id, None)
        return jsonify({"deleted": demo_id})
    return jsonify({"error": "Demo not found"}), 404


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


@app.route("/api/admin/schema_map")
def api_admin_schema_map():
    return send_file(str(STRUCT_DB_DIR / "schema_map.html"), mimetype="text/html")


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
_load_base_weapon_ids()

log.info("startup complete — cs2demviewer ready")

if __name__ == "__main__":
    if _verbose:
        log.info("Flask dev server starting on http://localhost:5000")
    app.run(debug=True, port=5000, threaded=True)
