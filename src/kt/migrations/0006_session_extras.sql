CREATE TABLE IF NOT EXISTS climb_votes (
    session_code TEXT NOT NULL,
    participant_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    climb_id TEXT NOT NULL,
    quality REAL,
    grade_v INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (session_code, participant_id, provider, climb_id),
    FOREIGN KEY (session_code) REFERENCES sessions(code) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_votes_climb ON climb_votes(session_code, provider, climb_id);
