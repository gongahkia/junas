package routes_test

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"testing"

	"github.com/lczm/kilter-together/api/config"
	"github.com/lczm/kilter-together/api/routes"

	_ "github.com/mattn/go-sqlite3"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

func TestSetupRoutesContract(t *testing.T) {
	tempDir := t.TempDir()
	dbPath := filepath.Join(tempDir, "kilter.db")
	imageDir := filepath.Join(tempDir, "images")
	statePath := filepath.Join(tempDir, "bootstrap-state.json")
	if err := os.MkdirAll(imageDir, 0755); err != nil {
		t.Fatalf("create image directory: %v", err)
	}
	if err := os.WriteFile(filepath.Join(imageDir, "test-a.png"), []byte("image-a"), 0644); err != nil {
		t.Fatalf("write first image fixture: %v", err)
	}
	if err := os.WriteFile(filepath.Join(imageDir, "test-b.png"), []byte("image-b"), 0644); err != nil {
		t.Fatalf("write second image fixture: %v", err)
	}

	seedContractDatabase(t, dbPath)
	config.SetRuntimeConfig(config.RuntimeConfig{
		DataDir:   tempDir,
		DBPath:    dbPath,
		ImageDir:  imageDir,
		StatePath: statePath,
		Port:      "8082",
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
			ID                   int    `json:"id"`
			Name                 string `json:"name"`
			PreviewImageFilename string `json:"preview_image_filename"`
			ClimbCount           int    `json:"climb_count"`
		} `json:"boards"`
	}
	if err := json.NewDecoder(response.Body).Decode(&boardsResponse); err != nil {
		t.Fatalf("decode /api/boards response: %v", err)
	}
	if len(boardsResponse.Boards) != 2 {
		t.Fatalf("expected two boards in /api/boards response, got %d", len(boardsResponse.Boards))
	}
	if boardsResponse.Boards[0].ID != 99 || boardsResponse.Boards[1].ID != 14 {
		t.Fatalf("expected dynamically discovered board id 99, got %#v", boardsResponse.Boards)
	}
	if boardsResponse.Boards[0].ClimbCount != 0 {
		t.Fatalf("expected board 99 climb count 0, got %#v", boardsResponse.Boards[0])
	}
	if boardsResponse.Boards[1].PreviewImageFilename == "" || boardsResponse.Boards[1].ClimbCount != 3 {
		t.Fatalf("expected board 14 to expose preview image and climb count, got %#v", boardsResponse.Boards[1])
	}

	response, err = http.Get(server.URL + "/api/climbs?board_id=14&page_size=2")
	if err != nil {
		t.Fatalf("GET /api/climbs without angle: %v", err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusBadRequest {
		t.Fatalf("expected /api/climbs without angle status 400, got %d", response.StatusCode)
	}

	response, err = http.Get(server.URL + "/api/climbs?board_id=14&angle=40&sort=broken")
	if err != nil {
		t.Fatalf("GET /api/climbs invalid sort: %v", err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusBadRequest {
		t.Fatalf("expected /api/climbs invalid sort status 400, got %d", response.StatusCode)
	}

	response, err = http.Get(server.URL + "/api/climbs?board_id=14&angle=40&page_size=2&sort=popular")
	if err != nil {
		t.Fatalf("GET /api/climbs popular: %v", err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		t.Fatalf("expected /api/climbs status 200, got %d", response.StatusCode)
	}

	var popularResponse struct {
		Climbs []struct {
			UUID           string   `json:"uuid"`
			ClimbName      string   `json:"climb_name"`
			SetterName     string   `json:"setter_name"`
			ImageFilenames []string `json:"image_filenames"`
			Grades         map[string]struct {
				Boulder string `json:"boulder"`
			} `json:"grades"`
		} `json:"climbs"`
		HasMore    bool   `json:"has_more"`
		NextCursor string `json:"next_cursor"`
	}
	if err := json.NewDecoder(response.Body).Decode(&popularResponse); err != nil {
		t.Fatalf("decode /api/climbs popular response: %v", err)
	}
	if len(popularResponse.Climbs) != 2 {
		t.Fatalf("expected two climbs in popular response, got %d", len(popularResponse.Climbs))
	}
	if popularResponse.Climbs[0].ClimbName != "Popular Problem" || popularResponse.Climbs[1].ClimbName != "Sample Problem" {
		t.Fatalf("unexpected popular ordering: %#v", popularResponse.Climbs)
	}
	if popularResponse.Climbs[1].Grades["45"].Boulder != "7b/V8" {
		t.Fatalf("expected multi-angle grades in payload, got %#v", popularResponse.Climbs[1].Grades)
	}
	if len(popularResponse.Climbs[1].ImageFilenames) != 2 {
		t.Fatalf("expected two image filenames, got %#v", popularResponse.Climbs[1].ImageFilenames)
	}
	if !popularResponse.HasMore || popularResponse.NextCursor == "" {
		t.Fatalf("expected next page cursor in popular response, got %#v", popularResponse)
	}

	response, err = http.Get(server.URL + "/api/climbs?board_id=14&angle=40&page_size=2&sort=popular&cursor=" + url.QueryEscape(popularResponse.NextCursor))
	if err != nil {
		t.Fatalf("GET /api/climbs popular cursor page: %v", err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		t.Fatalf("expected /api/climbs cursor status 200, got %d", response.StatusCode)
	}

	var nextPageResponse struct {
		Climbs []struct {
			ClimbName string `json:"climb_name"`
		} `json:"climbs"`
	}
	if err := json.NewDecoder(response.Body).Decode(&nextPageResponse); err != nil {
		t.Fatalf("decode /api/climbs cursor response: %v", err)
	}
	if len(nextPageResponse.Climbs) != 1 || nextPageResponse.Climbs[0].ClimbName != "Newest Problem" {
		t.Fatalf("unexpected popular cursor page: %#v", nextPageResponse.Climbs)
	}

	response, err = http.Get(server.URL + "/api/climbs?board_id=14&angle=40&sort=newest")
	if err != nil {
		t.Fatalf("GET /api/climbs newest: %v", err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		t.Fatalf("expected /api/climbs newest status 200, got %d", response.StatusCode)
	}

	var newestResponse struct {
		Climbs []struct {
			ClimbName string `json:"climb_name"`
		} `json:"climbs"`
	}
	if err := json.NewDecoder(response.Body).Decode(&newestResponse); err != nil {
		t.Fatalf("decode /api/climbs newest response: %v", err)
	}
	if newestResponse.Climbs[0].ClimbName != "Newest Problem" {
		t.Fatalf("expected newest sort to lead with Newest Problem, got %#v", newestResponse.Climbs)
	}

	response, err = http.Get(server.URL + "/api/climbs?board_id=14&angle=40&name=Popular&setter=setter-a")
	if err != nil {
		t.Fatalf("GET /api/climbs filtered: %v", err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		t.Fatalf("expected /api/climbs filtered status 200, got %d", response.StatusCode)
	}

	var filteredResponse struct {
		Climbs []struct {
			ClimbName string `json:"climb_name"`
			Setter    string `json:"setter_name"`
		} `json:"climbs"`
	}
	if err := json.NewDecoder(response.Body).Decode(&filteredResponse); err != nil {
		t.Fatalf("decode /api/climbs filtered response: %v", err)
	}
	if len(filteredResponse.Climbs) != 1 || filteredResponse.Climbs[0].ClimbName != "Popular Problem" {
		t.Fatalf("unexpected filtered response: %#v", filteredResponse.Climbs)
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

func TestClimbsPaginationEdgeCases(t *testing.T) {
	tempDir := t.TempDir()
	dbPath := filepath.Join(tempDir, "kilter.db")
	imageDir := filepath.Join(tempDir, "images")
	statePath := filepath.Join(tempDir, "bootstrap-state.json")
	if err := os.MkdirAll(imageDir, 0755); err != nil {
		t.Fatalf("create image directory: %v", err)
	}

	seedContractDatabase(t, dbPath)
	config.SetRuntimeConfig(config.RuntimeConfig{
		DataDir:   tempDir,
		DBPath:    dbPath,
		ImageDir:  imageDir,
		StatePath: statePath,
		Port:      "8083",
	})
	if err := config.ConnectKilterDB(dbPath); err != nil {
		t.Fatalf("connect kilter database: %v", err)
	}

	server := httptest.NewServer(routes.SetupRoutes())
	defer server.Close()

	t.Run("page_size=0 defaults to 10", func(t *testing.T) {
		resp, err := http.Get(server.URL + "/api/climbs?angle=40&page_size=0")
		if err != nil {
			t.Fatalf("GET page_size=0: %v", err)
		}
		defer resp.Body.Close()
		if resp.StatusCode != http.StatusOK {
			t.Fatalf("expected 200, got %d", resp.StatusCode)
		}
		var body struct {
			PageSize int `json:"page_size"`
		}
		if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
			t.Fatalf("decode: %v", err)
		}
		if body.PageSize != 10 {
			t.Fatalf("expected page_size 10, got %d", body.PageSize)
		}
	})

	t.Run("page_size=999 clamped to 10", func(t *testing.T) {
		resp, err := http.Get(server.URL + "/api/climbs?angle=40&page_size=999")
		if err != nil {
			t.Fatalf("GET page_size=999: %v", err)
		}
		defer resp.Body.Close()
		if resp.StatusCode != http.StatusOK {
			t.Fatalf("expected 200, got %d", resp.StatusCode)
		}
		var body struct {
			PageSize int `json:"page_size"`
		}
		if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
			t.Fatalf("decode: %v", err)
		}
		if body.PageSize != 10 {
			t.Fatalf("expected page_size 10, got %d", body.PageSize)
		}
	})

	t.Run("invalid cursor returns 400", func(t *testing.T) {
		resp, err := http.Get(server.URL + "/api/climbs?angle=40&cursor=" + url.QueryEscape("!!!INVALID!!!"))
		if err != nil {
			t.Fatalf("GET invalid cursor: %v", err)
		}
		defer resp.Body.Close()
		if resp.StatusCode != http.StatusBadRequest {
			t.Fatalf("expected 400, got %d", resp.StatusCode)
		}
	})

	t.Run("nonexistent name returns empty climbs", func(t *testing.T) {
		resp, err := http.Get(server.URL + "/api/climbs?angle=40&name=ZZZZNONEXISTENT")
		if err != nil {
			t.Fatalf("GET nonexistent name: %v", err)
		}
		defer resp.Body.Close()
		if resp.StatusCode != http.StatusOK {
			t.Fatalf("expected 200, got %d", resp.StatusCode)
		}
		var body struct {
			Climbs  []json.RawMessage `json:"climbs"`
			HasMore bool              `json:"has_more"`
		}
		if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
			t.Fatalf("decode: %v", err)
		}
		if len(body.Climbs) != 0 {
			t.Fatalf("expected 0 climbs, got %d", len(body.Climbs))
		}
		if body.HasMore {
			t.Fatalf("expected has_more false")
		}
	})

	t.Run("page_size=1 full pagination", func(t *testing.T) {
		var allNames []string
		cursor := ""
		for i := 0; i < 20; i++ { // safety cap
			u := server.URL + "/api/climbs?angle=40&page_size=1"
			if cursor != "" {
				u += "&cursor=" + url.QueryEscape(cursor)
			}
			resp, err := http.Get(u)
			if err != nil {
				t.Fatalf("GET page %d: %v", i, err)
			}
			defer resp.Body.Close()
			if resp.StatusCode != http.StatusOK {
				t.Fatalf("page %d: expected 200, got %d", i, resp.StatusCode)
			}
			var body struct {
				Climbs []struct {
					ClimbName string `json:"climb_name"`
				} `json:"climbs"`
				HasMore    bool   `json:"has_more"`
				NextCursor string `json:"next_cursor"`
			}
			if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
				t.Fatalf("decode page %d: %v", i, err)
			}
			for _, c := range body.Climbs {
				allNames = append(allNames, c.ClimbName)
			}
			if !body.HasMore {
				break
			}
			if body.NextCursor == "" {
				t.Fatalf("has_more=true but next_cursor is empty on page %d", i)
			}
			cursor = body.NextCursor
		}
		if len(allNames) != 3 { // 3 climbs seeded at angle 40
			t.Fatalf("expected 3 climbs across pages, got %d: %v", len(allNames), allNames)
		}
	})
}

func TestServeImagePathTraversal(t *testing.T) {
	tempDir := t.TempDir()
	dbPath := filepath.Join(tempDir, "kilter.db")
	imageDir := filepath.Join(tempDir, "images")
	statePath := filepath.Join(tempDir, "bootstrap-state.json")
	if err := os.MkdirAll(imageDir, 0755); err != nil {
		t.Fatalf("create image directory: %v", err)
	}
	if err := os.WriteFile(filepath.Join(imageDir, "valid.png"), []byte("valid-image"), 0644); err != nil {
		t.Fatalf("write test image: %v", err)
	}
	// write a secret file outside imageDir
	if err := os.WriteFile(filepath.Join(tempDir, "secret.txt"), []byte("secret-data"), 0644); err != nil {
		t.Fatalf("write secret file: %v", err)
	}

	seedContractDatabase(t, dbPath)
	config.SetRuntimeConfig(config.RuntimeConfig{
		DataDir:   tempDir,
		DBPath:    dbPath,
		ImageDir:  imageDir,
		StatePath: statePath,
		Port:      "8084",
	})
	if err := config.ConnectKilterDB(dbPath); err != nil {
		t.Fatalf("connect kilter database: %v", err)
	}

	server := httptest.NewServer(routes.SetupRoutes())
	defer server.Close()

	t.Run("valid filename", func(t *testing.T) {
		resp, err := http.Get(server.URL + "/api/images/valid.png")
		if err != nil {
			t.Fatalf("request: %v", err)
		}
		defer resp.Body.Close()
		if resp.StatusCode != http.StatusOK {
			t.Fatalf("expected 200, got %d", resp.StatusCode)
		}
	})

	t.Run("path traversal ../secret.txt", func(t *testing.T) {
		resp, err := http.Get(server.URL + "/api/images/../secret.txt")
		if err != nil {
			t.Fatalf("request: %v", err)
		}
		defer resp.Body.Close()
		// filepath.Base sanitizes to "secret.txt" which doesn't exist in imageDir
		if resp.StatusCode == http.StatusOK {
			t.Fatalf("expected non-200 for path traversal, got 200")
		}
	})

	t.Run("encoded path traversal", func(t *testing.T) {
		resp, err := http.Get(server.URL + "/api/images/" + url.PathEscape("../secret.txt"))
		if err != nil {
			t.Fatalf("request: %v", err)
		}
		defer resp.Body.Close()
		if resp.StatusCode == http.StatusOK {
			t.Fatalf("expected non-200 for encoded traversal, got 200")
		}
	})

	t.Run("nonexistent file", func(t *testing.T) {
		resp, err := http.Get(server.URL + "/api/images/nonexistent.png")
		if err != nil {
			t.Fatalf("request: %v", err)
		}
		defer resp.Body.Close()
		if resp.StatusCode != http.StatusNotFound {
			t.Fatalf("expected 404, got %d", resp.StatusCode)
		}
	})

	t.Run("null byte in filename", func(t *testing.T) {
		resp, err := http.Get(server.URL + "/api/images/test%00.png")
		if err != nil {
			t.Fatalf("request: %v", err)
		}
		defer resp.Body.Close()
		if resp.StatusCode == http.StatusOK {
			t.Fatalf("expected non-200 for null byte filename, got 200")
		}
	})
}

func seedContractDatabase(t *testing.T, dbPath string) {
	t.Helper()

	db, err := gorm.Open(sqlite.Open(dbPath), &gorm.Config{})
	if err != nil {
		t.Fatalf("open sqlite contract database: %v", err)
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
		`INSERT INTO products (id, name, is_listed) VALUES
			(1, 'Kilter Board Original', 1),
			(2, 'Kilter Board Homewall', 1)`,
		`INSERT INTO product_sizes (id, name, product_id, is_listed, position, edge_left, edge_right, edge_bottom, edge_top) VALUES
			(14, '7 x 10', 1, 1, 0, 0, 10, 0, 10),
			(99, 'Custom Homewall', 2, 1, 1, 0, 10, 0, 10)`,
		`INSERT INTO layouts (id, product_id) VALUES (1, 1)`,
		`INSERT INTO climbs (uuid, setter_username, name, description, frames, created_at, layout_id, edge_left, edge_right, edge_bottom, edge_top, is_listed) VALUES
			('uuid-1', 'setter-a', 'Sample Problem', 'sample description', 'frames', '2026-01-01 00:00:00.000000', 1, 0, 10, 0, 10, 1),
			('uuid-2', 'setter-b', 'Newest Problem', 'newest description', 'frames', '2026-04-01 00:00:00.000000', 1, 0, 10, 0, 10, 1),
			('uuid-3', 'setter-a', 'Popular Problem', 'popular description', 'frames', '2026-03-01 00:00:00.000000', 1, 0, 10, 0, 10, 1)`,
		`INSERT INTO product_sizes_layouts_sets (product_size_id, layout_id, image_filename) VALUES
			(14, 1, 'product_sizes_layouts_sets/test-a.png'),
			(14, 1, 'product_sizes_layouts_sets/test-b.png')`,
		`INSERT INTO climb_stats (climb_uuid, angle, display_difficulty, ascensionist_count) VALUES
			('uuid-1', 40, 12, 5),
			('uuid-1', 45, 13, 5),
			('uuid-2', 40, 10, 2),
			('uuid-3', 40, 14, 10)`,
		`INSERT INTO difficulty_grades (difficulty, boulder_name, route_name) VALUES
			(10, '6c+/V5', '5.12b'),
			(12, '7a/V6', '5.12d'),
			(13, '7b/V8', '5.13a'),
			(14, '7b+/V8', '5.13b')`,
	}

	for _, statement := range statements {
		if err := db.Exec(statement).Error; err != nil {
			t.Fatalf("execute contract seed statement %q: %v", statement, err)
		}
	}
}
