CREATE TABLE IF NOT EXISTS base_weapons (
    id            TEXT PRIMARY KEY,
    name          TEXT,
    description   TEXT,
    def_index     TEXT,
    category_id   TEXT,
    category_name TEXT,
    image         TEXT
);
