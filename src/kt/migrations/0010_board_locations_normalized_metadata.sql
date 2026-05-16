ALTER TABLE board_locations ADD COLUMN board_family TEXT;
ALTER TABLE board_locations ADD COLUMN setup_year INTEGER;
ALTER TABLE board_locations ADD COLUMN layout_type TEXT;
ALTER TABLE board_locations ADD COLUMN holdset_version TEXT;
ALTER TABLE board_locations ADD COLUMN is_adjustable INTEGER;

UPDATE board_locations
SET board_family = LOWER(COALESCE(NULLIF(board_type, ''), 'unknown'))
WHERE board_family IS NULL OR board_family = '';

UPDATE board_locations
SET is_adjustable = CASE
    WHEN angle_min IS NULL OR angle_max IS NULL THEN NULL
    WHEN angle_min != angle_max THEN 1
    ELSE 0
END
WHERE is_adjustable IS NULL;

CREATE INDEX IF NOT EXISTS idx_board_locations_family ON board_locations(board_family);
