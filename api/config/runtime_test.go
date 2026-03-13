package config

import (
	"slices"
	"testing"
)

func TestLoadRuntimeConfigDefaults(t *testing.T) {
	t.Setenv("KILTER_TOGETHER_DATA_DIR", "")
	t.Setenv("RAILWAY_VOLUME_MOUNT_PATH", "")
	t.Setenv("KILTER_TOGETHER_DB_PATH", "")
	t.Setenv("KILTER_TOGETHER_APP_DB_PATH", "")
	t.Setenv("KILTER_TOGETHER_IMAGE_DIR", "")
	t.Setenv("KILTER_TOGETHER_KILTER_USERNAME", "")
	t.Setenv("KILTER_TOGETHER_KILTER_PASSWORD", "")
	t.Setenv("KILTER_TOGETHER_APP_SECRET", "")
	t.Setenv("KILTER_TOGETHER_ENCRYPTION_KEY", "")
	t.Setenv("KILTER_TOGETHER_PORT", "")
	t.Setenv("PORT", "")
	t.Setenv("KILTER_TOGETHER_STORAGE_WARN_PERCENT", "")
	t.Setenv("KILTER_TOGETHER_STORAGE_CRITICAL_PERCENT", "")
	t.Setenv("KILTER_TOGETHER_ENABLE_TEST_PROVIDER", "")

	runtimeConfig := LoadRuntimeConfig()

	if runtimeConfig.DataDir != "data" {
		t.Fatalf("expected default data dir, got %q", runtimeConfig.DataDir)
	}
	if runtimeConfig.DBPath != "data/kilter.db" {
		t.Fatalf("expected default db path, got %q", runtimeConfig.DBPath)
	}
	if runtimeConfig.AppDBPath != "data/app.db" {
		t.Fatalf("expected default app db path, got %q", runtimeConfig.AppDBPath)
	}
	if runtimeConfig.ImageDir != "data/images" {
		t.Fatalf("expected default image dir, got %q", runtimeConfig.ImageDir)
	}
	if runtimeConfig.StatePath != "data/bootstrap-state.json" {
		t.Fatalf("expected default state path, got %q", runtimeConfig.StatePath)
	}
	if runtimeConfig.Port != "8082" {
		t.Fatalf("expected default port, got %q", runtimeConfig.Port)
	}
	if runtimeConfig.StorageWarnPercent != 80 {
		t.Fatalf("expected default storage warning threshold, got %d", runtimeConfig.StorageWarnPercent)
	}
	if runtimeConfig.StorageCriticalPercent != 90 {
		t.Fatalf("expected default storage critical threshold, got %d", runtimeConfig.StorageCriticalPercent)
	}
	if runtimeConfig.ListenAddr() != ":8082" {
		t.Fatalf("expected default listen addr, got %q", runtimeConfig.ListenAddr())
	}
	if !slices.Equal(runtimeConfig.CORSAllowedOrigins(), defaultAllowedOrigins) {
		t.Fatalf("expected default allowed origins %v, got %v", defaultAllowedOrigins, runtimeConfig.CORSAllowedOrigins())
	}
	if err := runtimeConfig.Validate(); err != nil {
		t.Fatalf("expected default runtime config to validate, got %v", err)
	}
	if runtimeConfig.EnableTestProvider {
		t.Fatalf("expected test provider to default off")
	}
}

func TestLoadRuntimeConfigOverrides(t *testing.T) {
	t.Setenv("KILTER_TOGETHER_DATA_DIR", "/tmp/kilter-data")
	t.Setenv("RAILWAY_VOLUME_MOUNT_PATH", "/mnt/railway-volume")
	t.Setenv("KILTER_TOGETHER_DB_PATH", "/tmp/custom.db")
	t.Setenv("KILTER_TOGETHER_APP_DB_PATH", "/tmp/app.db")
	t.Setenv("KILTER_TOGETHER_IMAGE_DIR", "/tmp/custom-images")
	t.Setenv("KILTER_TOGETHER_KILTER_USERNAME", "climber")
	t.Setenv("KILTER_TOGETHER_KILTER_PASSWORD", "secret")
	t.Setenv("KILTER_TOGETHER_APP_SECRET", "app-secret")
	t.Setenv("KILTER_TOGETHER_ENCRYPTION_KEY", "base64-key")
	t.Setenv("KILTER_TOGETHER_PORT", "")
	t.Setenv("PORT", "9090")
	t.Setenv("KILTER_TOGETHER_ALLOWED_ORIGINS", "https://app.example.com,https://admin.example.com")
	t.Setenv("KILTER_TOGETHER_ENABLE_TEST_PROVIDER", "true")
	t.Setenv("KILTER_TOGETHER_STORAGE_WARN_PERCENT", "75")
	t.Setenv("KILTER_TOGETHER_STORAGE_CRITICAL_PERCENT", "92")

	runtimeConfig := LoadRuntimeConfig()

	if runtimeConfig.DataDir != "/mnt/railway-volume" {
		t.Fatalf("expected Railway volume mount to take precedence, got %q", runtimeConfig.DataDir)
	}
	if runtimeConfig.DBPath != "/tmp/custom.db" {
		t.Fatalf("expected overridden db path, got %q", runtimeConfig.DBPath)
	}
	if runtimeConfig.AppDBPath != "/tmp/app.db" {
		t.Fatalf("expected overridden app db path, got %q", runtimeConfig.AppDBPath)
	}
	if runtimeConfig.ImageDir != "/tmp/custom-images" {
		t.Fatalf("expected overridden image dir, got %q", runtimeConfig.ImageDir)
	}
	if runtimeConfig.StatePath != "/mnt/railway-volume/bootstrap-state.json" {
		t.Fatalf("expected derived state path, got %q", runtimeConfig.StatePath)
	}
	if runtimeConfig.KilterUsername != "climber" {
		t.Fatalf("expected overridden username, got %q", runtimeConfig.KilterUsername)
	}
	if runtimeConfig.KilterPassword != "secret" {
		t.Fatalf("expected overridden password, got %q", runtimeConfig.KilterPassword)
	}
	if runtimeConfig.AppSecret != "app-secret" {
		t.Fatalf("expected app secret, got %q", runtimeConfig.AppSecret)
	}
	if runtimeConfig.EncryptionKey != "base64-key" {
		t.Fatalf("expected encryption key, got %q", runtimeConfig.EncryptionKey)
	}
	if runtimeConfig.Port != "9090" {
		t.Fatalf("expected normalized port, got %q", runtimeConfig.Port)
	}
	if runtimeConfig.StorageWarnPercent != 75 {
		t.Fatalf("expected overridden warning threshold, got %d", runtimeConfig.StorageWarnPercent)
	}
	if runtimeConfig.StorageCriticalPercent != 92 {
		t.Fatalf("expected overridden critical threshold, got %d", runtimeConfig.StorageCriticalPercent)
	}
	if runtimeConfig.ListenAddr() != ":9090" {
		t.Fatalf("expected normalized listen addr, got %q", runtimeConfig.ListenAddr())
	}
	expectedOrigins := []string{"https://app.example.com", "https://admin.example.com"}
	if !slices.Equal(runtimeConfig.CORSAllowedOrigins(), expectedOrigins) {
		t.Fatalf("expected overridden allowed origins %v, got %v", expectedOrigins, runtimeConfig.CORSAllowedOrigins())
	}
	if err := runtimeConfig.Validate(); err != nil {
		t.Fatalf("expected overridden runtime config to validate, got %v", err)
	}
	if !runtimeConfig.EnableTestProvider {
		t.Fatalf("expected test provider override to be enabled")
	}
}

func TestRuntimeConfigValidateRejectsWildcardOrigins(t *testing.T) {
	cfg := RuntimeConfig{
		AllowedOrigins:         []string{"*"},
		StorageWarnPercent:     80,
		StorageCriticalPercent: 90,
	}

	if err := cfg.Validate(); err == nil {
		t.Fatalf("expected wildcard origins to be rejected")
	}
}

func TestRuntimeConfigValidateRejectsInvalidStorageThresholds(t *testing.T) {
	cfg := RuntimeConfig{
		AllowedOrigins:         []string{"https://app.example.com"},
		StorageWarnPercent:     95,
		StorageCriticalPercent: 90,
	}

	if err := cfg.Validate(); err == nil {
		t.Fatalf("expected invalid thresholds to be rejected")
	}
}
