CREATE TABLE IF NOT EXISTS inventory (
    weapon_id   TEXT NOT NULL,
    paint_index TEXT NOT NULL,
    name        TEXT,
    rarity_id   TEXT,
    rarity_name TEXT,
    rarity_color TEXT,
    marketable  INTEGER,  -- 0/1
    image       TEXT,
    PRIMARY KEY (weapon_id, paint_index)
);
