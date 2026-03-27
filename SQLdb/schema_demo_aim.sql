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
