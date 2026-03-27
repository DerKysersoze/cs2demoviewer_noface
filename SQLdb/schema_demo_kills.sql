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
