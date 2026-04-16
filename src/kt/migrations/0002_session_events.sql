CREATE TABLE IF NOT EXISTS session_events (
    session_code TEXT NOT NULL,
    seq INTEGER NOT NULL,
    type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (session_code, seq),
    FOREIGN KEY (session_code) REFERENCES sessions(code) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_session_events_seq ON session_events(session_code, seq);
