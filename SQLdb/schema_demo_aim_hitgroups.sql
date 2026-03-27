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
