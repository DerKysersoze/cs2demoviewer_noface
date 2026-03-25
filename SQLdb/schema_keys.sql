CREATE TABLE IF NOT EXISTS keys (
    id                 TEXT PRIMARY KEY,
    name               TEXT,
    description        TEXT,
    def_index          TEXT,
    market_hash_name   TEXT,
    marketable         INTEGER,  -- 0/1
    image              TEXT,
    original_item_name TEXT,
    original_image     TEXT,
    crates             TEXT  -- JSON array [{id, name, image}]
);
