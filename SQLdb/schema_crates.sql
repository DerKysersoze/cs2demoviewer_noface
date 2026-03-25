CREATE TABLE IF NOT EXISTS crates (
    id                 TEXT PRIMARY KEY,
    name               TEXT,
    description        TEXT,
    def_index          TEXT,
    type               TEXT,
    first_sale_date    TEXT,
    rarity_id          TEXT,
    rarity_name        TEXT,
    rarity_color       TEXT,
    market_hash_name   TEXT,
    rental             INTEGER,  -- 0/1
    image              TEXT,
    model_player       TEXT,
    loot_list          TEXT,
    original_item_name TEXT,
    original_image     TEXT,
    contains           TEXT,     -- JSON array
    contains_rare      TEXT      -- JSON array
);
