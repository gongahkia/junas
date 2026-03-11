CREATE TABLE IF NOT EXISTS room_session_summaries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  room_id INTEGER NOT NULL UNIQUE,
  room_slug TEXT NOT NULL,
  room_name TEXT,
  provider_id TEXT NOT NULL,
  surface_name TEXT,
  surface_kind TEXT,
  participant_count INTEGER NOT NULL DEFAULT 0,
  top_voted_json TEXT,
  final_queue_json TEXT,
  finalists_json TEXT,
  closed_at DATETIME NOT NULL,
  created_at DATETIME,
  updated_at DATETIME,
  FOREIGN KEY(room_id) REFERENCES rooms(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_room_session_summaries_closed_at ON room_session_summaries(closed_at);
CREATE INDEX IF NOT EXISTS idx_room_session_summaries_provider_id ON room_session_summaries(provider_id);
