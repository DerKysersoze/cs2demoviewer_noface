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
