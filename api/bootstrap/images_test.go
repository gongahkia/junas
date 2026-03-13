package bootstrap

import (
	"context"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"sync"
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

func TestDownloadImagesSkipsCachedAssets(t *testing.T) {
	tempDir := t.TempDir()
	if err := os.WriteFile(filepath.Join(tempDir, "a.png"), []byte("cached"), 0644); err != nil {
		t.Fatalf("write cached image: %v", err)
	}

	var (
		mu   sync.Mutex
		hits = map[string]int{}
	)

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		hits[r.URL.Path]++
		mu.Unlock()

		switch r.URL.Path {
		case "/img/product_sizes_layouts_sets/a.png":
			_, _ = w.Write([]byte("remote-a"))
		case "/img/product_sizes_layouts_sets/b.png":
			_, _ = w.Write([]byte("remote-b"))
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	originalBaseURL := kilterImageBaseURL
	originalClient := defaultHTTPClient
	kilterImageBaseURL = server.URL + "/img"
	defaultHTTPClient = server.Client()
	defer func() {
		kilterImageBaseURL = originalBaseURL
		defaultHTTPClient = originalClient
	}()

	assets := []ImageAsset{
		{RemotePath: "product_sizes_layouts_sets/a.png", LocalName: "a.png"},
		{RemotePath: "product_sizes_layouts_sets/b.png", LocalName: "b.png"},
	}

	if err := DownloadImages(context.Background(), tempDir, assets); err != nil {
		t.Fatalf("DownloadImages returned error: %v", err)
	}

	cachedBytes, err := os.ReadFile(filepath.Join(tempDir, "a.png"))
	if err != nil {
		t.Fatalf("read cached image: %v", err)
	}
	if string(cachedBytes) != "cached" {
		t.Fatalf("expected cached asset to be preserved, got %q", string(cachedBytes))
	}

	downloadedBytes, err := os.ReadFile(filepath.Join(tempDir, "b.png"))
	if err != nil {
		t.Fatalf("read downloaded image: %v", err)
	}
	if string(downloadedBytes) != "remote-b" {
		t.Fatalf("expected downloaded asset contents, got %q", string(downloadedBytes))
	}

	mu.Lock()
	defer mu.Unlock()
	if hits["/img/product_sizes_layouts_sets/a.png"] != 0 {
		t.Fatalf("expected cached asset to be skipped, got %d requests", hits["/img/product_sizes_layouts_sets/a.png"])
	}
	if hits["/img/product_sizes_layouts_sets/b.png"] != 1 {
		t.Fatalf("expected one request for missing asset, got %d", hits["/img/product_sizes_layouts_sets/b.png"])
	}
}
