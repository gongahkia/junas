CREATE INDEX IF NOT EXISTS idx_board_locations_lat_lon ON board_locations(lat, lon);
CREATE INDEX IF NOT EXISTS idx_board_locations_type_lat_lon ON board_locations(board_type, lat, lon);
