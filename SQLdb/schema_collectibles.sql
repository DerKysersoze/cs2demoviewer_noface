CREATE TABLE IF NOT EXISTS collectibles (
    id                  TEXT PRIMARY KEY,
    name                TEXT,
    description         TEXT,
    def_index           TEXT,
    rarity_id           TEXT,
    rarity_name         TEXT,
    rarity_color        TEXT,
    type                TEXT,
    genuine             INTEGER,  -- 0/1
    market_hash_name    TEXT,
    image               TEXT,
    original_item_name  TEXT,
    original_image      TEXT
);
