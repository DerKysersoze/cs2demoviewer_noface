CREATE TABLE IF NOT EXISTS sticker_slabs (
    id               TEXT PRIMARY KEY,
    name             TEXT,
    description      TEXT,
    def_index        TEXT,
    rarity_id        TEXT,
    rarity_name      TEXT,
    rarity_color     TEXT,
    type             TEXT,
    market_hash_name TEXT,
    effect           TEXT,
    tournament_id    TEXT,
    tournament_name  TEXT,
    image            TEXT,
    original_name    TEXT,
    original_image   TEXT,
    crates           TEXT,  -- JSON array [{id, name, image}]
    collections      TEXT   -- JSON array [{id, name, image}]
);
