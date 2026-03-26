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
import threading
import time
import zlib
import tempfile
import traceback
import uuid
from collections import OrderedDict
from pathlib import Path

import requests
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
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demos.db")
SQL_DIR = Path(__file__).parent / "SQLdb"


STRUCT_DB_DIR = Path(__file__).parent / "struct_db"
IMAGES_DIR    = Path(__file__).parent / "images"


def _load_sql(name: str) -> str:
    return (SQL_DIR / name).read_text(encoding="utf-8")


def _j(v):
    """Serialize to compact JSON string; return None for empty/null values."""
    if v is None:
        return None
    s = json.dumps(v, ensure_ascii=False, separators=(",", ":"))
    return None if s in ("[]", "null") else s


def _cache_table_images(table: str, col: str = "image"):
    """Download images for one table/column and save to images/<table>/.
    Skips files that already exist."""
    table_dir = IMAGES_DIR / table
    table_dir.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(DB_PATH)
    try:
        rows = con.execute(
            f"SELECT id, {col} FROM {table} WHERE {col} IS NOT NULL"
        ).fetchall()
    except Exception as e:
        log.warning("image cache skipped [%s.%s]: %s", table, col, e)
        con.close()
        return
    con.close()

    suffix = f"_{col}" if col != "image" else ""
    cached = skipped = failed = 0
    for row_id, url in rows:
        if not url.startswith(("http://", "https://")):
            skipped += 1
            continue
        existing = list(table_dir.glob(f"{row_id}{suffix}.*"))
        if existing:
            skipped += 1
            continue
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            ct = resp.headers.get("Content-Type", "image/jpeg")
            ext = ".png" if "png" in ct else ".jpg"
            (table_dir / f"{row_id}{suffix}{ext}").write_bytes(resp.content)
            cached += 1
            log.debug("%s.%s cached: %s%s%s", table, col, row_id, suffix, ext)
        except Exception as e:
            failed += 1
            log.warning("%s.%s fetch failed [%s]: %s", table, col, row_id, e)

    log.info("%s.%s images: cached=%d  skipped=%d  failed=%d", table, col, cached, skipped, failed)


# Tables and columns to cache; tuples of (table, col)
_IMAGE_COLUMNS = [
    ("agents",           "image"),
    ("agents",           "original_image"),
    ("base_weapons",     "image"),
    ("collectibles",     "image"),
    ("collectibles",     "original_image"),
    ("collections",      "image"),
    ("collections",      "original_image"),
    ("crates",           "image"),
    ("crates",           "original_image"),
    ("graffiti",         "image"),
    ("graffiti",         "original_image"),
    ("highlights",       "image"),
    ("highlights",       "thumbnail"),
    ("highlights",       "original_image"),
    ("keychains",        "image"),
    ("keychains",        "original_image"),
    ("keys",             "image"),
    ("keys",             "original_image"),
    ("music_kits",       "image"),
    ("music_kits",       "original_image"),
    ("patches",          "image"),
    ("patches",          "original_image"),
    ("skins",            "image"),
    ("skins_not_grouped","image"),
    ("skins_not_grouped","original_image"),
    ("sticker_slabs",    "image"),
    ("sticker_slabs",    "original_image"),
    ("stickers",         "image"),
    ("stickers",         "original_image"),
    ("tools",            "image"),
    ("tools",            "original_image"),
]


def _cache_all_images():
    """Download and cache images for all reference tables. Runs in a background thread."""
    log.info("image cache: starting for %d table/column pairs", len(_IMAGE_COLUMNS))
    for table, col in _IMAGE_COLUMNS:
        _cache_table_images(table, col)
    log.info("image cache: all done")


def _load_struct_db():
    """Populate reference tables from struct_db JSON files.
    Each table is only populated once — skipped if already has rows."""
    log.info("struct_db: starting reference table load from %s", STRUCT_DB_DIR)
    _t0 = time.monotonic()
    con = sqlite3.connect(DB_PATH)

    def _json(fname):
        p = STRUCT_DB_DIR / fname
        if not p.exists():
            return []
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def _ensure(sql_file, table, columns, rows):
        con.executescript(_load_sql(sql_file))
        if con.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0] > 0:
            return
        if not rows:
            return
        ph = ", ".join(["?"] * len(columns))
        col_str = ", ".join(columns)
        con.executemany(
            f"INSERT OR IGNORE INTO [{table}] ({col_str}) VALUES ({ph})", rows
        )
        con.commit()
        log.info("struct_db: loaded %d rows → %s", len(rows), table)

    # ── agents ────────────────────────────────────────────────────────────────
    cols = ["id", "name", "description", "def_index",
            "rarity_id", "rarity_name", "rarity_color",
            "team_id", "team_name", "market_hash_name", "image", "model_player",
            "original_name", "original_image", "collections"]
    rows = []
    for i in _json("agents.json"):
        r = i.get("rarity") or {}; t = i.get("team") or {}; o = i.get("original") or {}
        rows.append((i["id"], i.get("name"), i.get("description"), i.get("def_index"),
                     r.get("id"), r.get("name"), r.get("color"),
                     t.get("id"), t.get("name"),
                     i.get("market_hash_name"), i.get("image"), i.get("model_player"),
                     o.get("name"), o.get("image_inventory"), _j(i.get("collections"))))
    _ensure("schema_agents.sql", "agents", cols, rows)

    # ── base_weapons ──────────────────────────────────────────────────────────
    cols = ["id", "name", "description", "def_index", "category_id", "category_name", "image"]
    rows = []
    for i in _json("base_weapons.json"):
        c = i.get("category") or {}
        rows.append((i["id"], i.get("name"), i.get("description"), str(i.get("def_index", "")),
                     c.get("id"), c.get("name"), i.get("image")))
    _ensure("schema_base_weapons.sql", "base_weapons", cols, rows)

    # ── collectibles ─────────────────────────────────────────────────────────
    cols = ["id", "name", "description", "def_index",
            "rarity_id", "rarity_name", "rarity_color",
            "type", "genuine", "market_hash_name", "image",
            "original_item_name", "original_image"]
    rows = []
    for i in _json("collectibles.json"):
        r = i.get("rarity") or {}; o = i.get("original") or {}
        rows.append((i["id"], i.get("name"), i.get("description"), i.get("def_index"),
                     r.get("id"), r.get("name"), r.get("color"),
                     i.get("type"), int(bool(i.get("genuine"))), i.get("market_hash_name"),
                     i.get("image"), o.get("item_name"), o.get("image_inventory")))
    _ensure("schema_collectibles.sql", "collectibles", cols, rows)

    # ── collections ───────────────────────────────────────────────────────────
    cols = ["id", "name", "image", "original_name", "original_image", "crates", "contains"]
    rows = []
    for i in _json("collections.json"):
        o = i.get("original") or {}
        rows.append((i["id"], i.get("name"), i.get("image"),
                     o.get("name"), o.get("image_inventory"),
                     _j(i.get("crates")), _j(i.get("contains"))))
    _ensure("schema_collections.sql", "collections", cols, rows)

    # ── crates ────────────────────────────────────────────────────────────────
    cols = ["id", "name", "description", "def_index", "type", "first_sale_date",
            "rarity_id", "rarity_name", "rarity_color",
            "market_hash_name", "rental", "image", "model_player", "loot_list",
            "original_item_name", "original_image", "contains", "contains_rare"]
    rows = []
    for i in _json("crates.json"):
        r = i.get("rarity") or {}; o = i.get("original") or {}
        rows.append((i["id"], i.get("name"), i.get("description"), i.get("def_index"),
                     i.get("type"), i.get("first_sale_date"),
                     r.get("id"), r.get("name"), r.get("color"),
                     i.get("market_hash_name"), int(bool(i.get("rental"))),
                     i.get("image"), i.get("model_player"), _j(i.get("loot_list")),
                     o.get("item_name"), o.get("image_inventory"),
                     _j(i.get("contains")), _j(i.get("contains_rare"))))
    _ensure("schema_crates.sql", "crates", cols, rows)

    # ── graffiti ──────────────────────────────────────────────────────────────
    cols = ["id", "name", "description", "def_index",
            "rarity_id", "rarity_name", "rarity_color",
            "market_hash_name", "image", "original_name", "original_image", "crates"]
    rows = []
    for i in _json("graffiti.json"):
        r = i.get("rarity") or {}; o = i.get("original") or {}
        rows.append((i["id"], i.get("name"), i.get("description"), i.get("def_index"),
                     r.get("id"), r.get("name"), r.get("color"),
                     i.get("market_hash_name"), i.get("image"),
                     o.get("name"), o.get("image_inventory"), _j(i.get("crates"))))
    _ensure("schema_graffiti.sql", "graffiti", cols, rows)

    # ── highlights ────────────────────────────────────────────────────────────
    cols = ["id", "def_index", "name", "description",
            "tournament_event", "team0", "team1", "stage", "tournament_player", "map",
            "market_hash_name", "image", "video", "thumbnail",
            "original_id", "original_image"]
    rows = []
    for i in _json("highlights.json"):
        o = i.get("original") or {}
        rows.append((i["id"], i.get("def_index"), i.get("name"), i.get("description"),
                     i.get("tournament_event"), i.get("team0"), i.get("team1"),
                     i.get("stage"), i.get("tournament_player"), i.get("map"),
                     i.get("market_hash_name"), i.get("image"), i.get("video"), i.get("thumbnail"),
                     o.get("id"), o.get("image_inventory")))
    _ensure("schema_highlights.sql", "highlights", cols, rows)

    # ── inventory (nested dict: {skins: {weapon_id: {paint_index: {...}}}}) ──
    cols = ["weapon_id", "paint_index", "name",
            "rarity_id", "rarity_name", "rarity_color", "marketable", "image"]
    rows = []
    inv = _json("inventory.json")
    if isinstance(inv, dict):
        for weapon_id, paints in inv.get("skins", {}).items():
            for paint_index, info in paints.items():
                r = info.get("rarity") or {}
                rows.append((weapon_id, paint_index, info.get("name"),
                             r.get("id"), r.get("name"), r.get("color"),
                             int(bool(info.get("marketable"))), info.get("image")))
    _ensure("schema_inventory.sql", "inventory", cols, rows)

    # ── keychains ─────────────────────────────────────────────────────────────
    cols = ["id", "name", "description", "def_index",
            "rarity_id", "rarity_name", "rarity_color",
            "market_hash_name", "image", "original_loc_name", "original_image", "collections"]
    rows = []
    for i in _json("keychains.json"):
        r = i.get("rarity") or {}; o = i.get("original") or {}
        rows.append((i["id"], i.get("name"), i.get("description"), i.get("def_index"),
                     r.get("id"), r.get("name"), r.get("color"),
                     i.get("market_hash_name"), i.get("image"),
                     o.get("loc_name"), o.get("image_inventory"), _j(i.get("collections"))))
    _ensure("schema_keychains.sql", "keychains", cols, rows)

    # ── keys ──────────────────────────────────────────────────────────────────
    cols = ["id", "name", "description", "def_index",
            "market_hash_name", "marketable", "image",
            "original_item_name", "original_image", "crates"]
    rows = []
    for i in _json("keys.json"):
        o = i.get("original") or {}
        rows.append((i["id"], i.get("name"), i.get("description"), i.get("def_index"),
                     i.get("market_hash_name"), int(bool(i.get("marketable"))),
                     i.get("image"), o.get("item_name"), o.get("image_inventory"),
                     _j(i.get("crates"))))
    _ensure("schema_keys.sql", "keys", cols, rows)

    # ── music_kits ────────────────────────────────────────────────────────────
    cols = ["id", "name", "description", "def_index",
            "rarity_id", "rarity_name", "rarity_color",
            "market_hash_name", "exclusive", "image", "original_name", "original_image"]
    rows = []
    for i in _json("music_kits.json"):
        r = i.get("rarity") or {}; o = i.get("original") or {}
        rows.append((i["id"], i.get("name"), i.get("description"), i.get("def_index"),
                     r.get("id"), r.get("name"), r.get("color"),
                     i.get("market_hash_name"), int(bool(i.get("exclusive"))),
                     i.get("image"), o.get("name"), o.get("image_inventory")))
    _ensure("schema_music_kits.sql", "music_kits", cols, rows)

    # ── patches ───────────────────────────────────────────────────────────────
    cols = ["id", "name", "description", "def_index",
            "rarity_id", "rarity_name", "rarity_color",
            "market_hash_name", "image", "original_name", "original_image"]
    rows = []
    for i in _json("patches.json"):
        r = i.get("rarity") or {}; o = i.get("original") or {}
        rows.append((i["id"], i.get("name"), i.get("description"), i.get("def_index"),
                     r.get("id"), r.get("name"), r.get("color"),
                     i.get("market_hash_name"), i.get("image"),
                     o.get("name"), o.get("image_inventory")))
    _ensure("schema_patches.sql", "patches", cols, rows)

    # ── skins ─────────────────────────────────────────────────────────────────
    cols = ["id", "name", "description",
            "weapon_id", "weapon_weapon_id", "weapon_name",
            "category_id", "category_name", "pattern_id", "pattern_name",
            "min_float", "max_float",
            "rarity_id", "rarity_name", "rarity_color",
            "stattrak", "souvenir", "paint_index",
            "team_id", "team_name", "legacy_model", "image", "original_name",
            "wears", "collections", "crates"]
    rows = []
    for i in _json("skins.json"):
        w = i.get("weapon") or {}; c = i.get("category") or {}; p = i.get("pattern") or {}
        r = i.get("rarity") or {}; t = i.get("team") or {}; o = i.get("original") or {}
        rows.append((i["id"], i.get("name"), i.get("description"),
                     w.get("id"), w.get("weapon_id"), w.get("name"),
                     c.get("id"), c.get("name"), p.get("id"), p.get("name"),
                     i.get("min_float"), i.get("max_float"),
                     r.get("id"), r.get("name"), r.get("color"),
                     int(bool(i.get("stattrak"))), int(bool(i.get("souvenir"))),
                     i.get("paint_index"),
                     t.get("id"), t.get("name"), int(bool(i.get("legacy_model"))),
                     i.get("image"), o.get("name"),
                     _j(i.get("wears")), _j(i.get("collections")), _j(i.get("crates"))))
    _ensure("schema_skins.sql", "skins", cols, rows)

    # ── skins_not_grouped ─────────────────────────────────────────────────────
    cols = ["id", "skin_id", "name", "description",
            "weapon_id", "weapon_weapon_id", "weapon_name",
            "category_id", "category_name", "pattern_id", "pattern_name",
            "min_float", "max_float", "wear_id", "wear_name",
            "stattrak", "souvenir", "paint_index",
            "rarity_id", "rarity_name", "rarity_color", "market_hash_name",
            "team_id", "team_name", "style_id", "style_name", "style_url",
            "legacy_model", "image", "original_name", "original_image"]
    rows = []
    for i in _json("skins_not_grouped.json"):
        w = i.get("weapon") or {}; c = i.get("category") or {}; p = i.get("pattern") or {}
        r = i.get("rarity") or {}; ww = i.get("wear") or {}
        t = i.get("team") or {}; s = i.get("style") or {}; o = i.get("original") or {}
        rows.append((i["id"], i.get("skin_id"), i.get("name"), i.get("description"),
                     w.get("id"), w.get("weapon_id"), w.get("name"),
                     c.get("id"), c.get("name"), p.get("id"), p.get("name"),
                     i.get("min_float"), i.get("max_float"),
                     ww.get("id"), ww.get("name"),
                     int(bool(i.get("stattrak"))), int(bool(i.get("souvenir"))),
                     i.get("paint_index"),
                     r.get("id"), r.get("name"), r.get("color"),
                     i.get("market_hash_name"),
                     t.get("id"), t.get("name"), s.get("id"), s.get("name"), s.get("url"),
                     int(bool(i.get("legacy_model"))), i.get("image"),
                     o.get("name"), o.get("image_inventory")))
    _ensure("schema_skins_not_grouped.sql", "skins_not_grouped", cols, rows)

    # ── sticker_slabs & stickers (identical structure) ────────────────────────
    for table, sql_file in [("sticker_slabs", "schema_sticker_slabs.sql"),
                             ("stickers",      "schema_stickers.sql")]:
        cols = ["id", "name", "description", "def_index",
                "rarity_id", "rarity_name", "rarity_color",
                "type", "market_hash_name", "effect",
                "tournament_id", "tournament_name",
                "image", "original_name", "original_image", "crates", "collections"]
        rows = []
        for i in _json(f"{table}.json"):
            r = i.get("rarity") or {}; tt = i.get("tournament") or {}; o = i.get("original") or {}
            rows.append((i["id"], i.get("name"), i.get("description"), i.get("def_index"),
                         r.get("id"), r.get("name"), r.get("color"),
                         i.get("type"), i.get("market_hash_name"), i.get("effect"),
                         tt.get("id"), tt.get("name"),
                         i.get("image"), o.get("name"), o.get("image_inventory"),
                         _j(i.get("crates")), _j(i.get("collections"))))
        _ensure(sql_file, table, cols, rows)

    # ── tools ─────────────────────────────────────────────────────────────────
    cols = ["id", "name", "description", "def_index", "image", "original_image"]
    rows = []
    for i in _json("tools.json"):
        o = i.get("original") or {}
        rows.append((i["id"], i.get("name"), i.get("description"), i.get("def_index"),
                     i.get("image"), o.get("image_inventory")))
    _ensure("schema_tools.sql", "tools", cols, rows)

    con.close()
    log.info("struct_db: reference tables ready (%.2fs)", time.monotonic() - _t0)


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
        all_items = (
            [player["ct_agent"]] if player.get("ct_agent") else []
        ) + (
            [player["t_agent"]]  if player.get("t_agent")  else []
        ) + player.get("ct_weapons", []) + player.get("t_weapons", [])
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
    from collections import OrderedDict
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


def _db_init():
    log.info("DB: initialising — %s", DB_PATH)
    con = sqlite3.connect(DB_PATH)

    # Create schemas
    con.executescript(_load_sql("schema_demos.sql"))
    con.executescript(_load_sql("schema_demo_cosmetics.sql"))

    # ---- Migrate old skin_names table (drop it; skins will be populated from struct_db) ----
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "skin_names" in tables:
        con.execute("DROP TABLE skin_names")

    # ---- Migrate old skins table (paint_index INTEGER PK → new id TEXT PK schema) ----
    skins_col0 = con.execute("PRAGMA table_info(skins)").fetchone()
    if skins_col0 and skins_col0[1] == "paint_index":
        con.execute("DROP TABLE skins")
        log.info("DB: dropped old skins table (will be repopulated from struct_db/skins.json)")

    # ---- Migrate old schema (single `data` TEXT column) ----
    cols = {r[1] for r in con.execute("PRAGMA table_info(demos)").fetchall()}
    if "data" in cols:
        log.info("DB: migrating old schema to normalised columns…")
        rows = con.execute("SELECT id, filename, map, uploaded_at, data, ticks_data FROM demos").fetchall()
        con.executescript(_load_sql("migrate_demos_v1_v2.sql"))
        for row in rows:
            rid, filename, map_name, uploaded_at, data_json, ticks_blob = row
            try:
                d = json.loads(data_json)
            except Exception:
                continue
            h = d.get("header") or {}
            con.execute(
                "INSERT INTO demos VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    rid, filename, map_name, uploaded_at,
                    h.get("tickrate"), h.get("duration"),
                    d.get("ct_team"), d.get("t_team"),
                    d.get("ct_wins"), d.get("t_wins"), d.get("total_rounds"),
                    d.get("session_id"), int(bool(d.get("has_ticks"))),
                    _blob(d["rounds"])        if d.get("rounds")        else None,
                    _blob(d["kills"])         if d.get("kills")         else None,
                    _blob(d["scoreboard"])    if d.get("scoreboard")    else None,
                    _blob(d["aim_breakdown"]) if d.get("aim_breakdown") else None,
                    ticks_blob,
                ),
            )
            if d.get("swag_breakdown"):
                _cosmetics_insert_rows(con, rid, d["swag_breakdown"])
        log.info("DB: migrated %d rows", len(rows))

    # ---- Migrate swag_breakdown blob → demo_cosmetics rows ----
    cols = {r[1] for r in con.execute("PRAGMA table_info(demos)").fetchall()}
    if "swag_breakdown" in cols:
        log.info("DB: migrating swag_breakdown blobs → demo_cosmetics…")
        blob_rows = con.execute(
            "SELECT id, swag_breakdown FROM demos WHERE swag_breakdown IS NOT NULL"
        ).fetchall()
        migrated = 0
        for demo_id, blob in blob_rows:
            already = con.execute(
                "SELECT 1 FROM demo_cosmetics WHERE demo_id = ? LIMIT 1", (demo_id,)
            ).fetchone()
            if already:
                continue
            try:
                swag = _unblob(blob)
                _cosmetics_insert_rows(con, demo_id, swag)
                migrated += 1
            except Exception as e:
                log.warning("DB: swag migration failed for %s: %s", demo_id, e)
        log.info("DB: migrated swag blobs for %d demos", migrated)
        con.execute("ALTER TABLE demos DROP COLUMN swag_breakdown")
        log.info("DB: dropped demos.swag_breakdown column")

    # ---- Drop weapon_cat column from demo_cosmetics if it still exists ----
    dc_cols = {r[1] for r in con.execute("PRAGMA table_info(demo_cosmetics)").fetchall()}
    if "weapon_cat" in dc_cols:
        con.execute("ALTER TABLE demo_cosmetics DROP COLUMN weapon_cat")
        log.info("DB: dropped demo_cosmetics.weapon_cat column")

    con.commit()
    con.close()

    log.info("DB: schema ready")
    # Populate all struct_db reference tables from JSON files
    _load_struct_db()


def _db_save(demo_id: str, filename: str, map_name: str, data_dict: dict,
             ticks_by_round: dict = None):
    h = data_dict.get("header") or {}
    has_ticks = bool(ticks_by_round)
    ticks_blob = _blob(ticks_by_round) if ticks_by_round else None
    log.info("db_save: starting — demo_id=%s filename=%s map=%s", demo_id, filename, map_name)
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "INSERT OR REPLACE INTO demos VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            demo_id, filename, map_name,
            datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
            h.get("tickrate"), h.get("duration"),
            data_dict.get("ct_team"), data_dict.get("t_team"),
            data_dict.get("ct_wins"), data_dict.get("t_wins"),
            data_dict.get("total_rounds"),
            demo_id,  # session_id == demo_id
            int(has_ticks),
            _blob(data_dict["rounds"])        if data_dict.get("rounds")        else None,
            _blob(data_dict["kills"])         if data_dict.get("kills")         else None,
            _blob(data_dict["scoreboard"])    if data_dict.get("scoreboard")    else None,
            _blob(data_dict["aim_breakdown"]) if data_dict.get("aim_breakdown") else None,
            ticks_blob,
        ),
    )
    log.info("db_save: INSERT done — demo_id=%s", demo_id)
    # Replace cosmetics rows for this demo
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

    cosmetic_rows = con.execute(
        "SELECT * FROM demo_cosmetics WHERE demo_id = ? ORDER BY id", (demo_id,)
    ).fetchall()
    con.close()

    data = {
        "header": {
            "map":      row["map"],
            "tickrate": row["tickrate"],
            "duration": row["duration"],
        },
        "ct_team":      row["ct_team"],
        "t_team":       row["t_team"],
        "ct_wins":      row["ct_wins"],
        "t_wins":       row["t_wins"],
        "total_rounds": row["total_rounds"],
        "session_id":   row["session_id"],
        "has_ticks":    bool(row["has_ticks"]),
        "filename":     row["filename"],
        "rounds":        _unblob(row["rounds"])        if row["rounds"]        else [],
        "kills":         _unblob(row["kills"])         if row["kills"]         else [],
        "scoreboard":    _unblob(row["scoreboard"])    if row["scoreboard"]    else [],
        "aim_breakdown": _unblob(row["aim_breakdown"]) if row["aim_breakdown"] else [],
        "swag_breakdown": _cosmetics_to_swag(cosmetic_rows),
    }

    if row["ticks_data"]:
        ticks_by_round = {int(k): v for k, v in _unblob(row["ticks_data"]).items()}
        session_id = row["session_id"]
        if session_id:
            if len(_session_cache) >= MAX_SESSIONS:
                _session_cache.popitem(last=False)
            _session_cache[session_id] = {
                "ticks":    ticks_by_round,
                "map_name": row["map"],
            }
        data["has_ticks"] = True

    return data


def _db_delete(demo_id: str) -> bool:
    con = sqlite3.connect(DB_PATH)
    con.execute("DELETE FROM demo_cosmetics WHERE demo_id = ?", (demo_id,))
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


_AGENT_NAMES = {
    4613: "Bloody Darryl The Strapped", 4619: "'Blueberries' Buckshot",
    4680: "'Two Times' McCoy", 4711: "Cmdr. Mae 'Dead Cold' Jamison",
    4712: "1st Lieutenant Farlow", 4713: "John 'Van Healen' Kask",
    4714: "Bio-Haz Specialist", 4715: "Sergeant Bombson",
    4716: "Chem-Haz Specialist", 4718: "Rezan the Redshirt",
    4726: "Sir Bloody Miami Darryl", 4727: "Safecracker Voltzmann",
    4728: "Little Kev", 4730: "Getaway Sally", 4732: "Number K",
    4733: "Sir Bloody Silent Darryl", 4734: "Sir Bloody Skullhead Darryl",
    4735: "Sir Bloody Darryl Royale", 4736: "Sir Bloody Loudmouth Darryl",
    4749: "Sous-Lieutenant Medic", 4750: "Chem-Haz Capitaine",
    4751: "Chef d'Escadron Rouchard", 4752: "Aspirant",
    4753: "Officer Jacques Beltram", 4756: "Lieutenant 'Tree Hugger' Farlow",
    4757: "Cmdr. Davida 'Goggles' Fernandez", 4771: "Cmdr. Frank 'Wet Sox' Baroud",
    4772: "Lieutenant Rex Krikey", 4773: "Elite Trapper Solman",
    4774: "Crasswater The Forgotten", 4775: "Arno The Overgrown",
    4776: "Col. Mangos Dabisi", 4777: "Vypa Sista of the Revolution",
    4778: "Trapper Aggressor", 4780: "'Medium Rare' Crasswater", 4781: "Trapper",
    5105: "Ground Rebel", 5106: "Osiris", 5107: "Prof. Shahmat",
    5108: "The Elite Mr. Muhlik", 5109: "Jungle Rebel",
    5205: "Soldier", 5206: "Enforcer", 5207: "Slingshot", 5208: "Street Soldier",
    5305: "Operator", 5306: "Markus Delrow", 5307: "Michael Syfers",
    5308: "Special Agent Ava", 5400: "3rd Commando Company",
    5401: "Seal Team 6 Soldier", 5402: "Buckshot", 5403: "'Two Times' McCoy",
    5404: "Lt. Commander Ricksaw", 5405: "Primeiro Tenente",
    5500: "Dragomir", 5501: "Maximus", 5502: "Rezan The Ready",
    5503: "Blackwolf", 5504: "'The Doctor' Romanov", 5505: "Dragomir",
    5601: "B Squadron Officer", 5602: "D Squadron Officer",
}

_WEAPON_NAMES = {
    1: "Desert Eagle", 2: "Dual Berettas", 3: "Five-SeveN", 4: "Glock-18",
    7: "AK-47", 8: "AUG", 9: "AWP", 10: "FAMAS", 11: "G3SG1",
    13: "Galil AR", 14: "M249", 16: "M4A4", 17: "MAC-10", 19: "P90",
    23: "MP5-SD", 24: "UMP-45", 25: "XM1014", 26: "PP-Bizon",
    27: "MAG-7", 28: "Negev", 29: "Sawed-Off", 30: "Tec-9",
    31: "Zeus x27", 32: "P2000", 33: "MP7", 34: "MP9", 35: "Nova",
    36: "P250", 38: "SCAR-20", 39: "SG 553", 40: "SSG 08",
    41: "Knife (CT)", 59: "Knife (T)",
    60: "M4A1-S", 61: "USP-S", 62: "CZ75-Auto", 63: "R8 Revolver",
    500: "Bayonet", 505: "Flip Knife", 506: "Gut Knife", 507: "Karambit",
    508: "M9 Bayonet", 509: "Huntsman Knife", 512: "Butterfly Knife",
    514: "Falchion Knife", 515: "Shadow Daggers", 516: "Bowie Knife",
    517: "Ursus Knife", 518: "Navaja Knife", 519: "Stiletto Knife",
    520: "Talon Knife", 521: "Classic Knife", 522: "Paracord Knife",
    523: "Survival Knife", 525: "Nomad Knife", 526: "Skeleton Knife",
    # Gloves
    5027: "Sport Gloves", 5028: "Driver Gloves", 5029: "Hand Wraps",
    5030: "Moto Gloves", 5031: "Specialist Gloves", 5032: "Hydra Gloves",
    5033: "Broken Fang Gloves", 5034: "Bloodhound Gloves",
}

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

# Side each agent def_index belongs to
_AGENT_SIDE: dict = {
    # T-side agents
    4613: "T", 4718: "T",
    4726: "T", 4727: "T", 4728: "T", 4730: "T", 4732: "T",
    4733: "T", 4734: "T", 4735: "T", 4736: "T",
    4773: "T", 4774: "T", 4775: "T", 4776: "T", 4777: "T",
    4778: "T", 4780: "T", 4781: "T",
    5105: "T", 5106: "T", 5107: "T", 5108: "T", 5109: "T",
    5205: "T", 5206: "T", 5207: "T", 5208: "T",
    5500: "T", 5501: "T", 5502: "T", 5503: "T", 5504: "T", 5505: "T",
    # CT-side agents
    4619: "CT", 4680: "CT",
    4711: "CT", 4712: "CT", 4713: "CT", 4714: "CT", 4715: "CT", 4716: "CT",
    4749: "CT", 4750: "CT", 4751: "CT", 4752: "CT", 4753: "CT", 4756: "CT",
    4757: "CT", 4771: "CT", 4772: "CT",
    5305: "CT", 5306: "CT", 5307: "CT", 5308: "CT",
    5400: "CT", 5401: "CT", 5402: "CT", 5403: "CT", 5404: "CT", 5405: "CT",
    5601: "CT", 5602: "CT",
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
    """Build paint_index -> skin name dict from the skins table (populated by _load_struct_db)."""
    global _SKIN_NAMES, _SKIN_NAMES_LOADED
    if _SKIN_NAMES_LOADED:
        return _SKIN_NAMES
    _SKIN_NAMES_LOADED = True
    con = sqlite3.connect(DB_PATH)
    try:
        rows = con.execute(
            "SELECT paint_index, name FROM skins WHERE paint_index IS NOT NULL AND paint_index != ''"
        ).fetchall()
        # Strip weapon prefix ("AK-47 | Redline" → "Redline") so the same pattern name
        # is stored regardless of which weapon row wins when paint_index is shared.
        def _strip_prefix(name: str) -> str:
            return name.split(" | ", 1)[-1] if name and " | " in name else name
        _SKIN_NAMES = {str(r[0]): _strip_prefix(r[1]) for r in rows}
        log.info("skin names: loaded %d entries from skins table", len(_SKIN_NAMES))
    except Exception as e:
        log.warning("skin names: failed to load from skins table: %s", e)
        _SKIN_NAMES = {}
    finally:
        con.close()
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
    ticks_by_round = extract_ticks(demo)
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


@app.route("/images/<table>/<path:filename>")
def serve_cached_image(table, filename):
    path = IMAGES_DIR / table / filename
    if not path.exists():
        return "", 404
    return send_file(str(path))


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


_load_skin_names()

threading.Thread(target=_cache_all_images, daemon=True, name="image-cache").start()

log.info("startup complete — cs2demviewer ready")

if __name__ == "__main__":
    if _verbose:
        log.info("Flask dev server starting on http://localhost:5000")
    app.run(debug=True, port=5000, threaded=True)
