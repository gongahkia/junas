package bootstrap

import (
	"path/filepath"
	"testing"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

func TestCollectImageAssetsDeduplicatesBasenames(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "images.db")
	db, err := gorm.Open(sqlite.Open(dbPath), &gorm.Config{})
	if err != nil {
		t.Fatalf("open sqlite database: %v", err)
	}

	if err := db.Exec(`
		CREATE TABLE product_sizes_layouts_sets (
			product_size_id INTEGER,
			layout_id INTEGER,
			image_filename TEXT
		)
	`).Error; err != nil {
		t.Fatalf("create product_sizes_layouts_sets table: %v", err)
	}

	if err := db.Exec(`
		INSERT INTO product_sizes_layouts_sets (product_size_id, layout_id, image_filename) VALUES
			(14, 1, 'product_sizes_layouts_sets/a.png'),
			(14, 1, 'product_sizes_layouts_sets/a.png'),
			(14, 1, 'product_sizes_layouts_sets/b.png')
	`).Error; err != nil {
		t.Fatalf("seed product_sizes_layouts_sets: %v", err)
	}

	assets, err := CollectImageAssets(db)
	if err != nil {
		t.Fatalf("CollectImageAssets returned error: %v", err)
	}
	if len(assets) != 2 {
		t.Fatalf("expected 2 unique assets, got %d", len(assets))
	}
	if assets[0].LocalName != "a.png" || assets[1].LocalName != "b.png" {
		t.Fatalf("unexpected local names: %#v", assets)
	}
}

func TestCollectImageAssetsRejectsBasenameCollisions(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "images.db")
	db, err := gorm.Open(sqlite.Open(dbPath), &gorm.Config{})
	if err != nil {
		t.Fatalf("open sqlite database: %v", err)
	}

	if err := db.Exec(`
		CREATE TABLE product_sizes_layouts_sets (
			product_size_id INTEGER,
			layout_id INTEGER,
			image_filename TEXT
		)
	`).Error; err != nil {
		t.Fatalf("create product_sizes_layouts_sets table: %v", err)
	}

	if err := db.Exec(`
		INSERT INTO product_sizes_layouts_sets (product_size_id, layout_id, image_filename) VALUES
			(14, 1, 'foo/a.png'),
			(14, 1, 'bar/a.png')
	`).Error; err != nil {
		t.Fatalf("seed collision rows: %v", err)
	}

	if _, err := CollectImageAssets(db); err == nil {
		t.Fatal("expected basename collision error, got nil")
	}
}
