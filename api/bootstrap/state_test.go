package bootstrap

import (
	"os"
	"path/filepath"
	"testing"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

func TestRuntimeReadyPassesWithoutManifestWhenAssetsExist(t *testing.T) {
	tempDir := t.TempDir()
	dbPath := filepath.Join(tempDir, "kilter.db")
	imageDir := filepath.Join(tempDir, "images")
	if err := os.MkdirAll(imageDir, 0755); err != nil {
		t.Fatalf("create image directory: %v", err)
	}
	if err := os.WriteFile(filepath.Join(imageDir, "a.png"), []byte("a"), 0644); err != nil {
		t.Fatalf("write a.png: %v", err)
	}
	if err := os.WriteFile(filepath.Join(imageDir, "b.png"), []byte("b"), 0644); err != nil {
		t.Fatalf("write b.png: %v", err)
	}

	seedRuntimeValidationDB(t, dbPath)
	if err := RuntimeReady(dbPath, imageDir, filepath.Join(tempDir, "missing-manifest.json")); err != nil {
		t.Fatalf("RuntimeReady returned error: %v", err)
	}
}

func TestRuntimeReadyFailsWhenImageIsMissing(t *testing.T) {
	tempDir := t.TempDir()
	dbPath := filepath.Join(tempDir, "kilter.db")
	imageDir := filepath.Join(tempDir, "images")
	if err := os.MkdirAll(imageDir, 0755); err != nil {
		t.Fatalf("create image directory: %v", err)
	}
	if err := os.WriteFile(filepath.Join(imageDir, "a.png"), []byte("a"), 0644); err != nil {
		t.Fatalf("write a.png: %v", err)
	}

	seedRuntimeValidationDB(t, dbPath)
	if err := RuntimeReady(dbPath, imageDir, filepath.Join(tempDir, "missing-manifest.json")); err == nil {
		t.Fatal("expected RuntimeReady to fail when image assets are missing")
	}
}

func TestRuntimeReadyFailsWhenManifestIsStale(t *testing.T) {
	tempDir := t.TempDir()
	dbPath := filepath.Join(tempDir, "kilter.db")
	imageDir := filepath.Join(tempDir, "images")
	statePath := filepath.Join(tempDir, "bootstrap-state.json")
	if err := os.MkdirAll(imageDir, 0755); err != nil {
		t.Fatalf("create image directory: %v", err)
	}
	if err := os.WriteFile(filepath.Join(imageDir, "a.png"), []byte("a"), 0644); err != nil {
		t.Fatalf("write a.png: %v", err)
	}
	if err := os.WriteFile(filepath.Join(imageDir, "b.png"), []byte("b"), 0644); err != nil {
		t.Fatalf("write b.png: %v", err)
	}

	seedRuntimeValidationDB(t, dbPath)
	if err := writeManifest(statePath, []ImageAsset{{LocalName: "a.png", RemotePath: "product_sizes_layouts_sets/a.png"}}); err != nil {
		t.Fatalf("write manifest: %v", err)
	}

	if err := RuntimeReady(dbPath, imageDir, statePath); err == nil {
		t.Fatal("expected RuntimeReady to fail when manifest contents are stale")
	}
}

func seedRuntimeValidationDB(t *testing.T, dbPath string) {
	t.Helper()

	db, err := gorm.Open(sqlite.Open(dbPath), &gorm.Config{})
	if err != nil {
		t.Fatalf("open sqlite database: %v", err)
	}

	statements := []string{
		`CREATE TABLE climbs (uuid TEXT PRIMARY KEY)`,
		`CREATE TABLE climb_stats (climb_uuid TEXT, angle INTEGER, display_difficulty REAL, ascensionist_count INTEGER)`,
		`CREATE TABLE difficulty_grades (difficulty INTEGER PRIMARY KEY, boulder_name TEXT, route_name TEXT)`,
		`CREATE TABLE layouts (id INTEGER PRIMARY KEY, product_id INTEGER)`,
		`CREATE TABLE product_sizes (id INTEGER PRIMARY KEY, product_id INTEGER, edge_left INTEGER, edge_right INTEGER, edge_bottom INTEGER, edge_top INTEGER, is_listed INTEGER, position INTEGER, name TEXT)`,
		`CREATE TABLE product_sizes_layouts_sets (product_size_id INTEGER, layout_id INTEGER, image_filename TEXT)`,
		`CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, is_listed INTEGER)`,
		`INSERT INTO product_sizes_layouts_sets (product_size_id, layout_id, image_filename) VALUES
			(14, 1, 'product_sizes_layouts_sets/a.png'),
			(14, 1, 'product_sizes_layouts_sets/b.png')`,
	}

	for _, statement := range statements {
		if err := db.Exec(statement).Error; err != nil {
			t.Fatalf("execute statement %q: %v", statement, err)
		}
	}
}
