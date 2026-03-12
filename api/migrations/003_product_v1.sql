ALTER TABLE rooms ADD COLUMN assistant_mode TEXT NOT NULL DEFAULT 'manual';

ALTER TABLE room_session_summaries ADD COLUMN recap_share_id TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_room_session_summaries_recap_share_id
  ON room_session_summaries(recap_share_id);

CREATE TABLE IF NOT EXISTS analytics_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  room_id INTEGER,
  room_slug TEXT,
  event_name TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'server',
  viewer_role TEXT,
  route TEXT,
  properties_json TEXT,
  created_at DATETIME NOT NULL,
  FOREIGN KEY(room_id) REFERENCES rooms(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_analytics_events_created_at
  ON analytics_events(created_at);
CREATE INDEX IF NOT EXISTS idx_analytics_events_room_slug
  ON analytics_events(room_slug);
CREATE INDEX IF NOT EXISTS idx_analytics_events_event_name
  ON analytics_events(event_name);

CREATE TABLE IF NOT EXISTS room_session_recaps (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  room_id INTEGER NOT NULL UNIQUE,
  share_id TEXT NOT NULL UNIQUE,
  room_slug TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  closed_at DATETIME NOT NULL,
  created_at DATETIME,
  updated_at DATETIME,
  FOREIGN KEY(room_id) REFERENCES rooms(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_room_session_recaps_closed_at
  ON room_session_recaps(closed_at);

CREATE TABLE IF NOT EXISTS solo_plan_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  share_id TEXT NOT NULL UNIQUE,
  provider_id TEXT NOT NULL,
  title TEXT NOT NULL,
  notes TEXT,
  surface_id TEXT,
  surface_name TEXT,
  surface_kind TEXT,
  context_json TEXT,
  filters_json TEXT,
  climbs_json TEXT NOT NULL,
  open_path TEXT,
  created_by TEXT,
  created_at DATETIME NOT NULL,
  updated_at DATETIME
);

CREATE INDEX IF NOT EXISTS idx_solo_plan_snapshots_provider_id
  ON solo_plan_snapshots(provider_id);
CREATE INDEX IF NOT EXISTS idx_solo_plan_snapshots_created_at
  ON solo_plan_snapshots(created_at);

CREATE TABLE IF NOT EXISTS feedback_entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  room_id INTEGER,
  room_slug TEXT,
  share_id TEXT,
  prompt_family TEXT NOT NULL,
  sentiment TEXT NOT NULL,
  message TEXT,
  route TEXT,
  metadata_json TEXT,
  created_at DATETIME NOT NULL,
  FOREIGN KEY(room_id) REFERENCES rooms(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_feedback_entries_created_at
  ON feedback_entries(created_at);
CREATE INDEX IF NOT EXISTS idx_feedback_entries_prompt_family
  ON feedback_entries(prompt_family);
