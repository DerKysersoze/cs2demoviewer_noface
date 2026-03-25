CREATE TABLE IF NOT EXISTS music_kits (
    id               TEXT PRIMARY KEY,
    name             TEXT,
    description      TEXT,
    def_index        TEXT,
    rarity_id        TEXT,
    rarity_name      TEXT,
    rarity_color     TEXT,
    market_hash_name TEXT,
    exclusive        INTEGER,  -- 0/1
    image            TEXT,
    original_name    TEXT,
    original_image   TEXT
);
