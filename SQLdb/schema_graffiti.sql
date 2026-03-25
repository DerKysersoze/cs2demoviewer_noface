CREATE TABLE IF NOT EXISTS graffiti (
    id               TEXT PRIMARY KEY,
    name             TEXT,
    description      TEXT,
    def_index        TEXT,
    rarity_id        TEXT,
    rarity_name      TEXT,
    rarity_color     TEXT,
    market_hash_name TEXT,
    image            TEXT,
    original_name    TEXT,
    original_image   TEXT,
    crates           TEXT  -- JSON array [{id, name, image}]
);
