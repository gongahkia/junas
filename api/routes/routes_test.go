package routes_test

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"

	"github.com/lczm/boardbuddy/api/config"
	"github.com/lczm/boardbuddy/api/routes"

	_ "github.com/mattn/go-sqlite3"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

func TestSetupRoutesSmoke(t *testing.T) {
	tempDir := t.TempDir()
	dbPath := filepath.Join(tempDir, "kilter.db")
	imageDir := filepath.Join(tempDir, "images")
	if err := os.MkdirAll(imageDir, 0755); err != nil {
		t.Fatalf("create image directory: %v", err)
	}
	if err := os.WriteFile(filepath.Join(imageDir, "test-a.png"), []byte("image-a"), 0644); err != nil {
		t.Fatalf("write first image fixture: %v", err)
	}
	if err := os.WriteFile(filepath.Join(imageDir, "test-b.png"), []byte("image-b"), 0644); err != nil {
		t.Fatalf("write second image fixture: %v", err)
	}

	seedSmokeDatabase(t, dbPath)
	config.SetRuntimeConfig(config.RuntimeConfig{
		DataDir:  tempDir,
		DBPath:   dbPath,
		ImageDir: imageDir,
		Port:     "8082",
	})
	if err := config.ConnectKilterDB(dbPath); err != nil {
		t.Fatalf("connect kilter database: %v", err)
	}

	server := httptest.NewServer(routes.SetupRoutes())
	defer server.Close()

	response, err := http.Get(server.URL + "/api/healthz")
	if err != nil {
		t.Fatalf("GET /api/healthz: %v", err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		t.Fatalf("expected /api/healthz status 200, got %d", response.StatusCode)
	}

	response, err = http.Get(server.URL + "/api/boards")
	if err != nil {
		t.Fatalf("GET /api/boards: %v", err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		t.Fatalf("expected /api/boards status 200, got %d", response.StatusCode)
	}
	var boardsResponse struct {
		Boards []struct {
			ID   int    `json:"id"`
			Name string `json:"name"`
		} `json:"boards"`
	}
	if err := json.NewDecoder(response.Body).Decode(&boardsResponse); err != nil {
		t.Fatalf("decode /api/boards response: %v", err)
	}
	if len(boardsResponse.Boards) == 0 {
		t.Fatal("expected at least one board in /api/boards response")
	}

	response, err = http.Get(server.URL + "/api/climbs?board_id=14&angle=40&page_size=2")
	if err != nil {
		t.Fatalf("GET /api/climbs: %v", err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		t.Fatalf("expected /api/climbs status 200, got %d", response.StatusCode)
	}
	var climbsResponse struct {
		Climbs []struct {
			ClimbName string `json:"climb_name"`
			Grades    map[string]struct {
				Boulder string `json:"boulder"`
			} `json:"grades"`
			ImageFilenames []string `json:"image_filenames"`
		} `json:"climbs"`
	}
	if err := json.NewDecoder(response.Body).Decode(&climbsResponse); err != nil {
		t.Fatalf("decode /api/climbs response: %v", err)
	}
	if len(climbsResponse.Climbs) != 1 {
		t.Fatalf("expected one climb in /api/climbs response, got %d", len(climbsResponse.Climbs))
	}
	if climbsResponse.Climbs[0].ClimbName != "Sample Problem" {
		t.Fatalf("unexpected climb name %q", climbsResponse.Climbs[0].ClimbName)
	}
	if climbsResponse.Climbs[0].Grades["40"].Boulder != "7a/V6" {
		t.Fatalf("unexpected climb grade payload: %#v", climbsResponse.Climbs[0].Grades)
	}
	if len(climbsResponse.Climbs[0].ImageFilenames) != 2 {
		t.Fatalf("expected two image filenames, got %#v", climbsResponse.Climbs[0].ImageFilenames)
	}

	response, err = http.Get(server.URL + "/api/images/test-a.png")
	if err != nil {
		t.Fatalf("GET /api/images/test-a.png: %v", err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		t.Fatalf("expected /api/images status 200, got %d", response.StatusCode)
	}
}

func seedSmokeDatabase(t *testing.T, dbPath string) {
	t.Helper()

	db, err := gorm.Open(sqlite.Open(dbPath), &gorm.Config{})
	if err != nil {
		t.Fatalf("open smoke sqlite database: %v", err)
	}

	statements := []string{
		`CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, is_listed INTEGER)`,
		`CREATE TABLE product_sizes (
			id INTEGER PRIMARY KEY,
			name TEXT,
			product_id INTEGER,
			is_listed INTEGER,
			position INTEGER,
			edge_left INTEGER,
			edge_right INTEGER,
			edge_bottom INTEGER,
			edge_top INTEGER
		)`,
		`CREATE TABLE layouts (id INTEGER PRIMARY KEY, product_id INTEGER)`,
		`CREATE TABLE climbs (
			uuid TEXT PRIMARY KEY,
			setter_username TEXT,
			name TEXT,
			description TEXT,
			frames TEXT,
			created_at TEXT,
			layout_id INTEGER,
			edge_left INTEGER,
			edge_right INTEGER,
			edge_bottom INTEGER,
			edge_top INTEGER,
			is_listed INTEGER
		)`,
		`CREATE TABLE product_sizes_layouts_sets (
			product_size_id INTEGER,
			layout_id INTEGER,
			image_filename TEXT
		)`,
		`CREATE TABLE climb_stats (
			climb_uuid TEXT,
			angle INTEGER,
			display_difficulty REAL,
			ascensionist_count INTEGER
		)`,
		`CREATE TABLE difficulty_grades (
			difficulty INTEGER PRIMARY KEY,
			boulder_name TEXT,
			route_name TEXT
		)`,
		`INSERT INTO products (id, name, is_listed) VALUES (1, 'Kilter Board Original', 1)`,
		`INSERT INTO product_sizes (id, name, product_id, is_listed, position, edge_left, edge_right, edge_bottom, edge_top)
		 VALUES (14, '7 x 10', 1, 1, 0, 0, 10, 0, 10)`,
		`INSERT INTO layouts (id, product_id) VALUES (1, 1)`,
		`INSERT INTO climbs (uuid, setter_username, name, description, frames, created_at, layout_id, edge_left, edge_right, edge_bottom, edge_top, is_listed)
		 VALUES ('uuid-1', 'setter', 'Sample Problem', 'sample description', 'frames', '2026-01-01 00:00:00.000000', 1, 0, 10, 0, 10, 1)`,
		`INSERT INTO product_sizes_layouts_sets (product_size_id, layout_id, image_filename) VALUES
			(14, 1, 'product_sizes_layouts_sets/test-a.png'),
			(14, 1, 'product_sizes_layouts_sets/test-b.png')`,
		`INSERT INTO climb_stats (climb_uuid, angle, display_difficulty, ascensionist_count) VALUES ('uuid-1', 40, 12, 5)`,
		`INSERT INTO difficulty_grades (difficulty, boulder_name, route_name) VALUES (12, '7a/V6', '5.12d')`,
	}

	for _, statement := range statements {
		if err := db.Exec(statement).Error; err != nil {
			t.Fatalf("execute smoke seed statement %q: %v", statement, err)
		}
	}
}
