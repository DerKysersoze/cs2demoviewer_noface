CREATE TABLE IF NOT EXISTS highlights (
    id                TEXT PRIMARY KEY,
    def_index         TEXT,
    name              TEXT,
    description       TEXT,
    tournament_event  TEXT,
    team0             TEXT,
    team1             TEXT,
    stage             TEXT,
    tournament_player TEXT,
    map               TEXT,
    market_hash_name  TEXT,
    image             TEXT,
    video             TEXT,
    thumbnail         TEXT,
    original_id       TEXT,
    original_image    TEXT
);
