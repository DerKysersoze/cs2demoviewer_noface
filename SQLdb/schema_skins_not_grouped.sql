-- One row per skin+wear variant (each skin appears once per wear tier).
CREATE TABLE IF NOT EXISTS skins_not_grouped (
    id               TEXT PRIMARY KEY,
    skin_id          TEXT,  -- references skins.id
    name             TEXT,
    description      TEXT,
    weapon_id        TEXT,
    weapon_weapon_id TEXT,
    weapon_name      TEXT,
    category_id      TEXT,
    category_name    TEXT,
    pattern_id       TEXT,
    pattern_name     TEXT,
    min_float        REAL,
    max_float        REAL,
    wear_id          TEXT,
    wear_name        TEXT,
    stattrak         INTEGER,  -- 0/1
    souvenir         INTEGER,  -- 0/1
    paint_index      TEXT,
    rarity_id        TEXT,
    rarity_name      TEXT,
    rarity_color     TEXT,
    market_hash_name TEXT,
    team_id          TEXT,
    team_name        TEXT,
    style_id         TEXT,
    style_name       TEXT,
    style_url        TEXT,
    legacy_model     INTEGER,  -- 0/1
    image            TEXT,
    original_name    TEXT,
    original_image   TEXT
);
