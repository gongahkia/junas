CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    code TEXT PRIMARY KEY,
    host_participant_id TEXT NOT NULL,
    host_secret_hash TEXT NOT NULL,
    enabled_providers TEXT NOT NULL,
    state_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    ended_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions(ended_at) WHERE ended_at IS NULL;

CREATE TABLE IF NOT EXISTS host_credentials (
    session_code TEXT NOT NULL,
    provider TEXT NOT NULL,
    ciphertext TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (session_code, provider),
    FOREIGN KEY (session_code) REFERENCES sessions(code) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS climbs_cache (
    provider TEXT NOT NULL,
    cache_key TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    PRIMARY KEY (provider, cache_key)
);

CREATE INDEX IF NOT EXISTS idx_cache_expiry ON climbs_cache(expires_at);

CREATE TABLE IF NOT EXISTS ws_tokens (
    token TEXT PRIMARY KEY,
    session_code TEXT NOT NULL,
    participant_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    FOREIGN KEY (session_code) REFERENCES sessions(code) ON DELETE CASCADE
);
