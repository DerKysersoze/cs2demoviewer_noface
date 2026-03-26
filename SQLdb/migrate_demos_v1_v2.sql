-- Migration: old single 'data' TEXT column -> normalised 18-column schema
-- Executed by _db_init() in app.py when PRAGMA table_info detects a 'data' column.
-- The Python layer reads all rows and re-inserts them; this file only supplies the DDL.

DROP TABLE IF EXISTS demos;

CREATE TABLE demos (
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
    session_id    TEXT,
    has_ticks     INTEGER NOT NULL DEFAULT 0,
    rounds        BLOB,
    kills         BLOB,
    scoreboard    BLOB,
    aim_breakdown  BLOB,
    ticks_data    BLOB
);
