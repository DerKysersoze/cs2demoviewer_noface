CREATE TABLE IF NOT EXISTS keychains (
    id               TEXT PRIMARY KEY,
    name             TEXT,
    description      TEXT,
    def_index        TEXT,
    rarity_id        TEXT,
    rarity_name      TEXT,
    rarity_color     TEXT,
    market_hash_name TEXT,
    image            TEXT,
    original_loc_name TEXT,
    original_image   TEXT,
    collections      TEXT  -- JSON array [{id, name, image}]
);
