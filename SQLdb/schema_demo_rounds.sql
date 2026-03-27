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
