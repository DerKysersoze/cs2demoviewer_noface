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
