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
