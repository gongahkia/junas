package routes_test

import (
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"

	"github.com/lczm/kilter-together/api/config"
	"github.com/lczm/kilter-together/api/routes"
)

func TestHealthRoutesAndDisabledMetrics(t *testing.T) {
	tempDir := t.TempDir()
	appDBPath := filepath.Join(tempDir, "app.db")
	config.SetRuntimeConfig(config.RuntimeConfig{
		DataDir:            tempDir,
		AppDBPath:          appDBPath,
		EnableTestProvider: true,
	})
	if err := config.ConnectAppDB(appDBPath); err != nil {
		t.Fatalf("connect app db: %v", err)
	}

	server := httptest.NewServer(routes.SetupRoutes())
	defer server.Close()

	livezResponse, err := http.Get(server.URL + "/api/livez")
	if err != nil {
		t.Fatalf("get livez: %v", err)
	}
	if livezResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected livez 200, got %d", livezResponse.StatusCode)
	}

	readyzResponse, err := http.Get(server.URL + "/api/readyz")
	if err != nil {
		t.Fatalf("get readyz: %v", err)
	}
	if readyzResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected readyz 200, got %d", readyzResponse.StatusCode)
	}

	metricsResponse, err := http.Get(server.URL + "/api/metrics")
	if err != nil {
		t.Fatalf("get metrics: %v", err)
	}
	if metricsResponse.StatusCode != http.StatusNotFound {
		t.Fatalf("expected metrics 404 after observability removal, got %d", metricsResponse.StatusCode)
	}
}
