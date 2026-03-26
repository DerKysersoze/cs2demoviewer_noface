-- Per-demo cosmetic items (agents + weapon skins) extracted from each uploaded demo.
-- One row per item per player per demo. Replaces the swag_breakdown BLOB column in demos.
CREATE TABLE IF NOT EXISTS demo_cosmetics (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    demo_id      TEXT    NOT NULL,
    steamid      TEXT,
    player_name  TEXT,
    team         TEXT,       -- player's match team (CT/T)
    def_index    INTEGER,
    item_name    TEXT,
    skin_name    TEXT,
    paint_index  INTEGER,
    paint_seed   INTEGER,
    wear         REAL,
    wear_tier    TEXT,
    custom_name  TEXT,
    stattrak     INTEGER,    -- StatTrak count or NULL
    is_agent     INTEGER,    -- 0/1
    side         TEXT,       -- CT, T, or both
    FOREIGN KEY (demo_id) REFERENCES demos(id)
);
CREATE INDEX IF NOT EXISTS idx_demo_cosmetics_demo_id ON demo_cosmetics(demo_id);
