ALTER TABLE board_locations ADD COLUMN source_name TEXT NOT NULL DEFAULT 'bundled_sample';
ALTER TABLE board_locations ADD COLUMN source_url TEXT;
ALTER TABLE board_locations ADD COLUMN source_version TEXT;
ALTER TABLE board_locations ADD COLUMN source_updated_at TEXT;
ALTER TABLE board_locations ADD COLUMN ingestion_run_id TEXT;

CREATE INDEX IF NOT EXISTS idx_board_locations_source_name ON board_locations(source_name);
CREATE INDEX IF NOT EXISTS idx_board_locations_source_version ON board_locations(source_version);
CREATE INDEX IF NOT EXISTS idx_board_locations_ingestion_run_id ON board_locations(ingestion_run_id);

CREATE TABLE IF NOT EXISTS board_ingestions (
    run_id TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    source_url TEXT,
    source_version TEXT,
    source_updated_at TEXT,
    ingestion_mode TEXT NOT NULL,
    status TEXT NOT NULL,
    loaded_count INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_board_ingestions_started_at ON board_ingestions(started_at);
