CREATE TABLE IF NOT EXISTS rooms (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT NOT NULL UNIQUE,
  name TEXT,
  provider_id TEXT NOT NULL,
  status TEXT NOT NULL,
  assistant_mode TEXT NOT NULL DEFAULT 'manual',
  surface_id TEXT,
  surface_kind TEXT,
  surface_name TEXT,
  surface_description TEXT,
  surface_context_json TEXT,
  current_climb_id TEXT,
  current_climb_json TEXT,
  emoji_reactions_enabled NUMERIC NOT NULL DEFAULT 1,
  version INTEGER NOT NULL DEFAULT 1,
  last_active_at DATETIME NOT NULL,
  closed_at DATETIME,
  created_at DATETIME,
  updated_at DATETIME
);

CREATE INDEX IF NOT EXISTS idx_rooms_provider_id ON rooms(provider_id);
CREATE INDEX IF NOT EXISTS idx_rooms_status ON rooms(status);
CREATE INDEX IF NOT EXISTS idx_rooms_last_active_at ON rooms(last_active_at);

CREATE TABLE IF NOT EXISTS room_participants (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  room_id INTEGER NOT NULL,
  display_name TEXT NOT NULL,
  role TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'watching',
  last_seen_at DATETIME NOT NULL,
  created_at DATETIME,
  updated_at DATETIME,
  FOREIGN KEY(room_id) REFERENCES rooms(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_room_display_name ON room_participants(room_id, display_name);
CREATE INDEX IF NOT EXISTS idx_room_participants_role ON room_participants(role);
CREATE INDEX IF NOT EXISTS idx_room_participants_status ON room_participants(status);
CREATE INDEX IF NOT EXISTS idx_room_participants_last_seen_at ON room_participants(last_seen_at);

CREATE TABLE IF NOT EXISTS room_sessions (
  id TEXT PRIMARY KEY,
  room_id INTEGER NOT NULL,
  participant_id INTEGER NOT NULL,
  role TEXT NOT NULL,
  expires_at DATETIME NOT NULL,
  created_at DATETIME,
  updated_at DATETIME,
  FOREIGN KEY(room_id) REFERENCES rooms(id) ON DELETE CASCADE,
  FOREIGN KEY(participant_id) REFERENCES room_participants(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_room_sessions_room_id ON room_sessions(room_id);
CREATE INDEX IF NOT EXISTS idx_room_sessions_participant_id ON room_sessions(participant_id);
CREATE INDEX IF NOT EXISTS idx_room_sessions_role ON room_sessions(role);
CREATE INDEX IF NOT EXISTS idx_room_sessions_expires_at ON room_sessions(expires_at);

CREATE TABLE IF NOT EXISTS room_provider_connections (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  room_id INTEGER NOT NULL UNIQUE,
  provider_id TEXT NOT NULL,
  secret_ciphertext TEXT NOT NULL,
  metadata_json TEXT,
  last_validated_at DATETIME NOT NULL,
  created_at DATETIME,
  updated_at DATETIME,
  FOREIGN KEY(room_id) REFERENCES rooms(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_room_provider_connections_provider_id ON room_provider_connections(provider_id);
CREATE INDEX IF NOT EXISTS idx_room_provider_connections_last_validated_at ON room_provider_connections(last_validated_at);

CREATE TABLE IF NOT EXISTS room_queue_entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  room_id INTEGER NOT NULL,
  climb_id TEXT NOT NULL,
  added_by_participant_id INTEGER NOT NULL,
  status TEXT NOT NULL,
  position INTEGER NOT NULL,
  climb_json TEXT,
  created_at DATETIME,
  updated_at DATETIME,
  FOREIGN KEY(room_id) REFERENCES rooms(id) ON DELETE CASCADE,
  FOREIGN KEY(added_by_participant_id) REFERENCES room_participants(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_room_queue_climb ON room_queue_entries(room_id, climb_id);
CREATE INDEX IF NOT EXISTS idx_room_queue_entries_room_id ON room_queue_entries(room_id);
CREATE INDEX IF NOT EXISTS idx_room_queue_entries_status ON room_queue_entries(status);
CREATE INDEX IF NOT EXISTS idx_room_queue_entries_position ON room_queue_entries(position);
CREATE INDEX IF NOT EXISTS idx_room_queue_entries_added_by_participant_id ON room_queue_entries(added_by_participant_id);

CREATE TABLE IF NOT EXISTS room_finalist_entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  room_id INTEGER NOT NULL,
  climb_id TEXT NOT NULL,
  added_by_participant_id INTEGER NOT NULL,
  position INTEGER NOT NULL,
  climb_json TEXT,
  created_at DATETIME,
  updated_at DATETIME,
  FOREIGN KEY(room_id) REFERENCES rooms(id) ON DELETE CASCADE,
  FOREIGN KEY(added_by_participant_id) REFERENCES room_participants(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_room_finalist_climb ON room_finalist_entries(room_id, climb_id);
CREATE INDEX IF NOT EXISTS idx_room_finalist_entries_room_id ON room_finalist_entries(room_id);
CREATE INDEX IF NOT EXISTS idx_room_finalist_entries_position ON room_finalist_entries(position);
CREATE INDEX IF NOT EXISTS idx_room_finalist_entries_added_by_participant_id ON room_finalist_entries(added_by_participant_id);

CREATE TABLE IF NOT EXISTS provider_cache_entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  provider_id TEXT NOT NULL,
  cache_key TEXT NOT NULL,
  payload TEXT,
  expires_at DATETIME,
  created_at DATETIME,
  updated_at DATETIME
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_provider_cache_key ON provider_cache_entries(provider_id, cache_key);
CREATE INDEX IF NOT EXISTS idx_provider_cache_entries_expires_at ON provider_cache_entries(expires_at);

CREATE TABLE IF NOT EXISTS room_session_summaries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  room_id INTEGER NOT NULL UNIQUE,
  room_slug TEXT NOT NULL,
  room_name TEXT,
  provider_id TEXT NOT NULL,
  surface_name TEXT,
  surface_kind TEXT,
  participant_count INTEGER NOT NULL DEFAULT 0,
  recap_share_id TEXT,
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
