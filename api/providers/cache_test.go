package providers

import (
	"context"
	"path/filepath"
	"testing"
	"time"

	"github.com/lczm/kilter-together/api/config"
	"github.com/lczm/kilter-together/api/rooms"
)

func TestPruneExpiredCacheDeletesOnlyExpiredEntries(t *testing.T) {
	tempDir := t.TempDir()
	appDBPath := filepath.Join(tempDir, "app.db")
	config.SetRuntimeConfig(config.RuntimeConfig{
		DataDir:   tempDir,
		AppDBPath: appDBPath,
	})
	if err := config.ConnectAppDB(appDBPath); err != nil {
		t.Fatalf("connect app db: %v", err)
	}

	service := rooms.NewService()
	if err := service.Migrate(context.Background()); err != nil {
		t.Fatalf("migrate app db: %v", err)
	}

	expired := ProviderCacheEntry{
		ProviderID: string(ProviderCrux),
		CacheKey:   "expired",
		Payload:    `{"value":"old"}`,
		ExpiresAt:  time.Now().UTC().Add(-time.Hour),
	}
	active := ProviderCacheEntry{
		ProviderID: string(ProviderCrux),
		CacheKey:   "active",
		Payload:    `{"value":"new"}`,
		ExpiresAt:  time.Now().UTC().Add(time.Hour),
	}
	if err := config.AppDB.Create(&expired).Error; err != nil {
		t.Fatalf("create expired cache entry: %v", err)
	}
	if err := config.AppDB.Create(&active).Error; err != nil {
		t.Fatalf("create active cache entry: %v", err)
	}

	pruned, err := PruneExpiredCache(context.Background())
	if err != nil {
		t.Fatalf("prune expired cache: %v", err)
	}
	if pruned != 1 {
		t.Fatalf("expected one pruned cache row, got %d", pruned)
	}

	var count int64
	if err := config.AppDB.Model(&ProviderCacheEntry{}).Count(&count).Error; err != nil {
		t.Fatalf("count cache entries: %v", err)
	}
	if count != 1 {
		t.Fatalf("expected one active cache entry to remain, got %d", count)
	}
}
