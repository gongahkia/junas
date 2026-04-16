CREATE TABLE IF NOT EXISTS logbook_entries (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    climb_id TEXT NOT NULL,
    name TEXT,
    session_code TEXT,
    grade_at_send TEXT,
    grade_v_at_send INTEGER,
    result TEXT NOT NULL,
    attempts INTEGER,
    rpe INTEGER,
    duration_seconds INTEGER,
    angle INTEGER,
    notes TEXT,
    climbed_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_logbook_user_time ON logbook_entries(user_id, climbed_at DESC);
CREATE INDEX IF NOT EXISTS idx_logbook_user_provider_climb ON logbook_entries(user_id, provider, climb_id);

CREATE TABLE IF NOT EXISTS favorites (
    user_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    climb_id TEXT NOT NULL,
    list TEXT NOT NULL DEFAULT 'favorites',
    position INTEGER NOT NULL DEFAULT 0,
    added_at TEXT NOT NULL,
    PRIMARY KEY (user_id, provider, climb_id, list),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_favorites_user_list ON favorites(user_id, list, position);

CREATE TABLE IF NOT EXISTS climb_notes (
    user_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    climb_id TEXT NOT NULL,
    body TEXT NOT NULL,
    tags_json TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, provider, climb_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
