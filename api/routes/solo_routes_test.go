package routes_test

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"

	"github.com/lczm/kilter-together/api/config"
	"github.com/lczm/kilter-together/api/providers"
	"github.com/lczm/kilter-together/api/routes"
)

func TestSoloProviderRoutesContract(t *testing.T) {
	tempDir := t.TempDir()
	config.SetRuntimeConfig(config.RuntimeConfig{
		DataDir:            tempDir,
		AppDBPath:          filepath.Join(tempDir, "app.db"),
		AppSecret:          "test-app-secret",
		EncryptionKey:      base64.StdEncoding.EncodeToString(bytes.Repeat([]byte{5}, 32)),
		EnableTestProvider: true,
	})
	providers.RegisterTestProviderIfEnabled(true)

	server := httptest.NewServer(routes.SetupRoutes())
	defer server.Close()

	capabilitiesResponse := performJSONRequest(t, server, http.MethodGet, "/api/providers/capabilities", nil, nil)
	if capabilitiesResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected capabilities status 200, got %d", capabilitiesResponse.StatusCode)
	}

	var capabilitiesPayload struct {
		Providers []struct {
			ID            string `json:"id"`
			SoloSupported bool   `json:"solo_supported"`
		} `json:"providers"`
	}
	if err := json.NewDecoder(capabilitiesResponse.Body).Decode(&capabilitiesPayload); err != nil {
		t.Fatalf("decode capabilities response: %v", err)
	}

	soloSupport := map[string]bool{}
	for _, provider := range capabilitiesPayload.Providers {
		soloSupport[provider.ID] = provider.SoloSupported
	}
	if !soloSupport["crux"] {
		t.Fatalf("expected crux solo support to be enabled, got %#v", soloSupport)
	}
	if !soloSupport["test"] {
		t.Fatalf("expected test provider solo support to be enabled, got %#v", soloSupport)
	}

	surfacesResponse := performJSONRequest(t, server, http.MethodPost, "/api/solo/providers/test/surfaces", map[string]any{
		"secret": map[string]string{"token": "solo-token"},
	}, nil)
	if surfacesResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected solo surfaces status 200, got %d", surfacesResponse.StatusCode)
	}

	var surfacesPayload struct {
		Surfaces []struct {
			ID   string `json:"id"`
			Kind string `json:"kind"`
		} `json:"surfaces"`
	}
	if err := json.NewDecoder(surfacesResponse.Body).Decode(&surfacesPayload); err != nil {
		t.Fatalf("decode surfaces response: %v", err)
	}
	if len(surfacesPayload.Surfaces) != 1 || surfacesPayload.Surfaces[0].ID != "gym-test" {
		t.Fatalf("unexpected top-level surfaces payload: %#v", surfacesPayload.Surfaces)
	}

	wallsResponse := performJSONRequest(t, server, http.MethodPost, "/api/solo/providers/test/surfaces", map[string]any{
		"secret":    map[string]string{"token": "solo-token"},
		"parent_id": "gym-test",
	}, nil)
	if wallsResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected solo walls status 200, got %d", wallsResponse.StatusCode)
	}

	var wallsPayload struct {
		Surfaces []struct {
			ID       string `json:"id"`
			ParentID string `json:"parent_id"`
		} `json:"surfaces"`
	}
	if err := json.NewDecoder(wallsResponse.Body).Decode(&wallsPayload); err != nil {
		t.Fatalf("decode walls response: %v", err)
	}
	if len(wallsPayload.Surfaces) != 2 || wallsPayload.Surfaces[0].ParentID != "gym-test" {
		t.Fatalf("unexpected wall payload: %#v", wallsPayload.Surfaces)
	}

	climbsResponse := performJSONRequest(t, server, http.MethodPost, "/api/solo/providers/test/climbs", map[string]any{
		"secret":     map[string]string{"token": "solo-token"},
		"surface_id": "wall-alpha",
		"q":          "beta",
		"sort":       "popular",
		"page_size":  1,
	}, nil)
	if climbsResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected solo climbs status 200, got %d", climbsResponse.StatusCode)
	}

	var climbsPayload struct {
		Climbs []struct {
			ID   string `json:"id"`
			Name string `json:"name"`
		} `json:"climbs"`
		HasMore    bool   `json:"has_more"`
		PageSize   int    `json:"page_size"`
		NextCursor string `json:"next_cursor"`
	}
	if err := json.NewDecoder(climbsResponse.Body).Decode(&climbsPayload); err != nil {
		t.Fatalf("decode solo climbs response: %v", err)
	}
	if len(climbsPayload.Climbs) != 1 || climbsPayload.Climbs[0].ID != "test:beta" {
		t.Fatalf("unexpected solo climbs payload: %#v", climbsPayload.Climbs)
	}
	if climbsPayload.PageSize != 1 {
		t.Fatalf("expected page size 1, got %#v", climbsPayload)
	}

	climbResponse := performJSONRequest(t, server, http.MethodPost, "/api/solo/providers/test/climbs/test%3Abeta", map[string]any{
		"secret":     map[string]string{"token": "solo-token"},
		"surface_id": "wall-alpha",
	}, nil)
	if climbResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected solo climb detail status 200, got %d", climbResponse.StatusCode)
	}

	var climbPayload struct {
		Climb struct {
			ID        string `json:"id"`
			SurfaceID string `json:"surface_id"`
		} `json:"climb"`
	}
	if err := json.NewDecoder(climbResponse.Body).Decode(&climbPayload); err != nil {
		t.Fatalf("decode solo climb detail response: %v", err)
	}
	if climbPayload.Climb.ID != "test:beta" || climbPayload.Climb.SurfaceID != "wall-alpha" {
		t.Fatalf("unexpected solo climb detail payload: %#v", climbPayload)
	}

	missingTokenResponse := performJSONRequest(t, server, http.MethodPost, "/api/solo/providers/test/surfaces", map[string]any{}, nil)
	if missingTokenResponse.StatusCode != http.StatusBadRequest {
		t.Fatalf("expected missing token status 400, got %d", missingTokenResponse.StatusCode)
	}

	var missingTokenPayload map[string]string
	if err := json.NewDecoder(missingTokenResponse.Body).Decode(&missingTokenPayload); err != nil {
		t.Fatalf("decode missing token response: %v", err)
	}
	if missingTokenPayload["code"] != "invalid_request" {
		t.Fatalf("expected invalid_request code, got %#v", missingTokenPayload)
	}
}
