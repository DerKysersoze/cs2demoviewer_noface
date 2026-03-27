CREATE TABLE IF NOT EXISTS demo_ticks (
    demo_id    TEXT PRIMARY KEY,
    ticks_data BLOB NOT NULL,
    FOREIGN KEY (demo_id) REFERENCES demos(id)
);
