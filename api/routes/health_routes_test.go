package routes_test

import (
	"encoding/json"
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

	runtimeStatusResponse, err := http.Get(server.URL + "/api/runtime/status")
	if err != nil {
		t.Fatalf("get runtime status: %v", err)
	}
	if runtimeStatusResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected runtime status 200, got %d", runtimeStatusResponse.StatusCode)
	}
	var runtimeStatusPayload struct {
		Status       string `json:"status"`
		RuntimeReady bool   `json:"runtime_ready"`
		Storage      struct {
			Severity     string  `json:"severity"`
			MountPath    string  `json:"mount_path"`
			UsagePercent float64 `json:"usage_percent"`
		} `json:"storage"`
	}
	if err := json.NewDecoder(runtimeStatusResponse.Body).Decode(&runtimeStatusPayload); err != nil {
		t.Fatalf("decode runtime status response: %v", err)
	}
	if !runtimeStatusPayload.RuntimeReady {
		t.Fatalf("expected runtime status to report ready, got %#v", runtimeStatusPayload)
	}
	if runtimeStatusPayload.Storage.Severity == "" {
		t.Fatalf("expected storage severity to be set, got %#v", runtimeStatusPayload)
	}
	if runtimeStatusPayload.Storage.MountPath == "" {
		t.Fatalf("expected storage mount path to be set, got %#v", runtimeStatusPayload)
	}

	metricsResponse, err := http.Get(server.URL + "/api/metrics")
	if err != nil {
		t.Fatalf("get metrics: %v", err)
	}
	if metricsResponse.StatusCode != http.StatusNotFound {
		t.Fatalf("expected metrics 404 after observability removal, got %d", metricsResponse.StatusCode)
	}
}
