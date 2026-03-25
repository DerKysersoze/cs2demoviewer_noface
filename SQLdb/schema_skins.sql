-- Skins grouped by paint_index (one row per skin, multiple wear tiers stored in wears JSON).
-- Replaces the old 23-column ByMykel API schema (which had paint_index INTEGER PRIMARY KEY).
CREATE TABLE IF NOT EXISTS skins (
    id               TEXT PRIMARY KEY,
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
    rarity_id        TEXT,
    rarity_name      TEXT,
    rarity_color     TEXT,
    stattrak         INTEGER,  -- 0/1
    souvenir         INTEGER,  -- 0/1
    paint_index      TEXT,
    team_id          TEXT,
    team_name        TEXT,
    legacy_model     INTEGER,  -- 0/1
    image            TEXT,
    original_name    TEXT,
    wears            TEXT,     -- JSON array [{id, name}]
    collections      TEXT,     -- JSON array [{id, name, image}]
    crates           TEXT      -- JSON array [{id, name, image}]
);
