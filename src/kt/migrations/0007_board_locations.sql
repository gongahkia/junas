CREATE TABLE IF NOT EXISTS board_locations (
    id TEXT PRIMARY KEY,
    provider_key TEXT NOT NULL DEFAULT '',
    gym_name TEXT NOT NULL,
    country TEXT,
    city TEXT,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    angle_min INTEGER,
    angle_max INTEGER,
    board_type TEXT,
    updated_at TEXT NOT NULL,
    raw_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_board_locations_type ON board_locations(board_type);
CREATE INDEX IF NOT EXISTS idx_board_locations_country ON board_locations(country);
