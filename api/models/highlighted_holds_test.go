package models

import (
	"testing"

	"github.com/lczm/kilter-together/api/config"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

func TestPopulateClimbHighlightedHolds(t *testing.T) {
	db, err := gorm.Open(sqlite.Open("file::memory:?cache=shared"), &gorm.Config{})
	if err != nil {
		t.Fatalf("open sqlite db: %v", err)
	}

	previousDB := config.KilterDB
	config.KilterDB = db
	t.Cleanup(func() {
		config.KilterDB = previousDB
		resetHighlightedHoldCaches()
	})

	resetHighlightedHoldCaches()

	statements := []string{
		`CREATE TABLE product_sizes (id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL);`,
		`CREATE TABLE layouts (id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL);`,
		`CREATE TABLE placement_roles (id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL, name TEXT NOT NULL, screen_color TEXT NOT NULL);`,
		`CREATE TABLE holes (id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL, name TEXT NOT NULL, x INTEGER NOT NULL, y INTEGER NOT NULL);`,
		`CREATE TABLE placements (id INTEGER PRIMARY KEY, layout_id INTEGER NOT NULL, hole_id INTEGER NOT NULL, set_id INTEGER NOT NULL, default_placement_role_id INTEGER);`,
		`INSERT INTO product_sizes (id, product_id) VALUES (28, 1);`,
		`INSERT INTO layouts (id, product_id) VALUES (11, 1);`,
		`INSERT INTO placement_roles (id, product_id, name, screen_color) VALUES (12, 1, 'start', '00DD00'), (15, 1, 'foot', 'FFA500');`,
		`INSERT INTO holes (id, product_id, name, x, y) VALUES
			(1, 1, '0,0', 0, 0),
			(2, 1, '100,100', 100, 100),
			(3, 1, '100,0', 100, 0);`,
		`INSERT INTO placements (id, layout_id, hole_id, set_id, default_placement_role_id) VALUES
			(100, 11, 1, 1, NULL),
			(200, 11, 2, 1, NULL),
			(300, 11, 3, 1, NULL);`,
	}
	for _, statement := range statements {
		if err := db.Exec(statement).Error; err != nil {
			t.Fatalf("exec statement: %v", err)
		}
	}

	climbs := []Climb{{
		UUID:          "uuid-1",
		ProductSizeID: 28,
		Frames:        "p200r12p300r15",
	}}

	if err := populateClimbHighlightedHolds(climbs); err != nil {
		t.Fatalf("populate highlighted holds: %v", err)
	}

	if len(climbs[0].HighlightedHolds) != 2 {
		t.Fatalf("expected 2 highlighted holds, got %d", len(climbs[0].HighlightedHolds))
	}

	first := climbs[0].HighlightedHolds[0]
	if first.Position != 200 || first.X != 100 || first.Y != 0 || first.Role != "start" || first.Color != "#00DD00" {
		t.Fatalf("unexpected first hold: %+v", first)
	}

	second := climbs[0].HighlightedHolds[1]
	if second.Position != 300 || second.X != 100 || second.Y != 100 || second.Role != "foot" || second.Color != "#FFA500" {
		t.Fatalf("unexpected second hold: %+v", second)
	}
}

func resetHighlightedHoldCaches() {
	highlightCacheMu.Lock()
	defer highlightCacheMu.Unlock()

	boardPlacementCache = map[uint]map[int]boardLED{}
	boardBoundsCache = map[uint]boardBounds{}
	roleStyleCache = map[uint]map[int]roleStyle{}
}
