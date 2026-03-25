CREATE TABLE IF NOT EXISTS agents (
    id               TEXT PRIMARY KEY,
    name             TEXT,
    description      TEXT,
    def_index        TEXT,
    rarity_id        TEXT,
    rarity_name      TEXT,
    rarity_color     TEXT,
    team_id          TEXT,
    team_name        TEXT,
    market_hash_name TEXT,
    image            TEXT,
    model_player     TEXT,
    original_name    TEXT,
    original_image   TEXT,
    collections      TEXT  -- JSON array [{id, name, image}]
);
