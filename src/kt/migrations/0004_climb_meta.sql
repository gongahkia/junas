CREATE TABLE IF NOT EXISTS climb_meta (
    provider TEXT NOT NULL,
    climb_id TEXT NOT NULL,
    grade_raw TEXT,
    grade_v INTEGER,
    stars REAL,
    ascents INTEGER,
    tags_json TEXT NOT NULL DEFAULT '[]',
    media_json TEXT NOT NULL DEFAULT '[]',
    setter_json TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (provider, climb_id)
);

CREATE INDEX IF NOT EXISTS idx_climb_meta_grade_v ON climb_meta(provider, grade_v);
CREATE INDEX IF NOT EXISTS idx_climb_meta_stars ON climb_meta(provider, stars);
