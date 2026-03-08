package bootstrap

import (
	"context"
	"database/sql"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"

	_ "github.com/mattn/go-sqlite3"
)

func TestLoginAcceptsCreatedStatus(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Fatalf("expected POST login request, got %s", r.Method)
		}
		if r.URL.Path != "/sessions" {
			t.Fatalf("expected /sessions path, got %s", r.URL.Path)
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusCreated)
		_, _ = w.Write([]byte(`{"session":{"token":"session-token"}}`))
	}))
	defer server.Close()

	previousBaseURL := kilterWebBaseURL
	previousClient := defaultHTTPClient
	kilterWebBaseURL = server.URL
	defaultHTTPClient = server.Client()
	t.Cleanup(func() {
		kilterWebBaseURL = previousBaseURL
		defaultHTTPClient = previousClient
	})

	token, err := Login(context.Background(), "host", "password")
	if err != nil {
		t.Fatalf("login returned error: %v", err)
	}
	if token != "session-token" {
		t.Fatalf("expected session token, got %q", token)
	}
}

func TestApplySyncResultUpdatesGenericAndClimbStatsTables(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "sync.db")
	connection, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		t.Fatalf("open sqlite database: %v", err)
	}
	defer connection.Close()

	statements := []string{
		`CREATE TABLE shared_syncs (table_name TEXT PRIMARY KEY, last_synchronized_at TEXT)`,
		`CREATE TABLE layouts (id INTEGER PRIMARY KEY, name TEXT)`,
		`CREATE TABLE climb_stats (
			climb_uuid TEXT,
			angle INTEGER,
			difficulty_average REAL,
			benchmark_difficulty REAL,
			display_difficulty REAL,
			ascensionist_count INTEGER,
			PRIMARY KEY (climb_uuid, angle)
		)`,
		`INSERT INTO climb_stats (climb_uuid, angle, difficulty_average, benchmark_difficulty, display_difficulty, ascensionist_count)
		 VALUES ('delete-me', 35, 10, NULL, 10, 1)`,
	}
	for _, statement := range statements {
		if _, err := connection.Exec(statement); err != nil {
			t.Fatalf("apply statement %q: %v", statement, err)
		}
	}

	err = applySyncResult(dbPath, map[string][]map[string]any{
		"shared_syncs": {
			{
				"table_name":           "climbs",
				"last_synchronized_at": "2026-02-01 00:00:00.000000",
			},
		},
		"layouts": {
			{
				"id":   1,
				"name": "Main",
			},
		},
		"climb_stats": {
			{
				"climb_uuid":           "keep-me",
				"angle":                40,
				"difficulty_average":   12.0,
				"benchmark_difficulty": nil,
				"ascensionist_count":   5,
			},
			{
				"climb_uuid":           "delete-me",
				"angle":                35,
				"difficulty_average":   nil,
				"benchmark_difficulty": nil,
				"ascensionist_count":   0,
			},
		},
	})
	if err != nil {
		t.Fatalf("applySyncResult returned error: %v", err)
	}

	var layoutName string
	if err := connection.QueryRow(`SELECT name FROM layouts WHERE id = 1`).Scan(&layoutName); err != nil {
		t.Fatalf("query inserted layout: %v", err)
	}
	if layoutName != "Main" {
		t.Fatalf("expected inserted layout, got %q", layoutName)
	}

	var displayDifficulty float64
	if err := connection.QueryRow(`SELECT display_difficulty FROM climb_stats WHERE climb_uuid = 'keep-me' AND angle = 40`).Scan(&displayDifficulty); err != nil {
		t.Fatalf("query inserted climb_stats row: %v", err)
	}
	if displayDifficulty != 12.0 {
		t.Fatalf("expected display_difficulty 12, got %v", displayDifficulty)
	}

	var deletedRowCount int
	if err := connection.QueryRow(`SELECT COUNT(*) FROM climb_stats WHERE climb_uuid = 'delete-me' AND angle = 35`).Scan(&deletedRowCount); err != nil {
		t.Fatalf("query deleted climb_stats row: %v", err)
	}
	if deletedRowCount != 0 {
		t.Fatalf("expected deleted climb_stats row, found %d rows", deletedRowCount)
	}
}
