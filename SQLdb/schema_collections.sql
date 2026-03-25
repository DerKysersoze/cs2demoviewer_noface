CREATE TABLE IF NOT EXISTS collections (
    id             TEXT PRIMARY KEY,
    name           TEXT,
    image          TEXT,
    original_name  TEXT,
    original_image TEXT,
    crates         TEXT,  -- JSON array [{id, name, image}]
    contains       TEXT   -- JSON array [{id, name, rarity{...}, paint_index, image}]
);
