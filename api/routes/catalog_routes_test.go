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
)

func TestKilterCatalogRoutesContract(t *testing.T) {
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
		Port:      "8085",
	})
	if err := config.ConnectKilterDB(dbPath); err != nil {
		t.Fatalf("connect kilter database: %v", err)
	}

	server := httptest.NewServer(routes.SetupRoutes())
	defer server.Close()

	manifestResponse, err := http.Get(server.URL + "/api/catalog/kilter/manifest")
	if err != nil {
		t.Fatalf("GET manifest: %v", err)
	}
	defer manifestResponse.Body.Close()
	if manifestResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected manifest status 200, got %d", manifestResponse.StatusCode)
	}

	var manifestPayload struct {
		Revision           string `json:"revision"`
		GeneratedAt        string `json:"generated_at"`
		ClimbCount         int    `json:"climb_count"`
		ImageCount         int    `json:"image_count"`
		EstimatedBytes     int64  `json:"estimated_bytes"`
		RequiresFullResync bool   `json:"requires_full_resync"`
	}
	if err := json.NewDecoder(manifestResponse.Body).Decode(&manifestPayload); err != nil {
		t.Fatalf("decode manifest: %v", err)
	}
	if manifestPayload.Revision == "" || manifestPayload.GeneratedAt == "" {
		t.Fatalf("expected manifest revision and generated_at, got %#v", manifestPayload)
	}
	if manifestPayload.ClimbCount != 3 {
		t.Fatalf("expected manifest climb_count 3, got %#v", manifestPayload)
	}
	if manifestPayload.ImageCount != 2 {
		t.Fatalf("expected image_count 2, got %#v", manifestPayload)
	}
	if manifestPayload.EstimatedBytes <= 0 || manifestPayload.RequiresFullResync {
		t.Fatalf("unexpected manifest payload: %#v", manifestPayload)
	}

	bootstrapResponse, err := http.Get(server.URL + "/api/catalog/kilter/bootstrap?page_size=2")
	if err != nil {
		t.Fatalf("GET bootstrap: %v", err)
	}
	defer bootstrapResponse.Body.Close()
	if bootstrapResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected bootstrap status 200, got %d", bootstrapResponse.StatusCode)
	}

	var bootstrapPayload struct {
		Boards []struct {
			ID int `json:"id"`
		} `json:"boards"`
		Climbs []struct {
			UUID      string         `json:"uuid"`
			ClimbName string         `json:"climb_name"`
			CreatedAt string         `json:"created_at"`
			Ascends   map[string]int `json:"ascends"`
			Grades    map[string]struct {
				Boulder string `json:"boulder"`
			} `json:"grades"`
			ImageFiles []string `json:"image_filenames"`
		} `json:"climbs"`
		SyncToken  string `json:"sync_token"`
		HasMore    bool   `json:"has_more"`
		NextCursor string `json:"next_cursor"`
		PageSize   int    `json:"page_size"`
	}
	if err := json.NewDecoder(bootstrapResponse.Body).Decode(&bootstrapPayload); err != nil {
		t.Fatalf("decode bootstrap: %v", err)
	}
	if len(bootstrapPayload.Boards) != 2 {
		t.Fatalf("expected boards in bootstrap payload, got %#v", bootstrapPayload.Boards)
	}
	if len(bootstrapPayload.Climbs) != 2 || bootstrapPayload.Climbs[0].ClimbName != "Sample Problem" || bootstrapPayload.Climbs[1].ClimbName != "Popular Problem" {
		t.Fatalf("unexpected bootstrap ordering: %#v", bootstrapPayload.Climbs)
	}
	if bootstrapPayload.Climbs[0].Grades["45"].Boulder != "7b/V8" {
		t.Fatalf("expected multi-angle grades in bootstrap payload, got %#v", bootstrapPayload.Climbs[0].Grades)
	}
	if bootstrapPayload.Climbs[1].Ascends["40"] != 10 {
		t.Fatalf("expected angle ascends in bootstrap payload, got %#v", bootstrapPayload.Climbs[1].Ascends)
	}
	if len(bootstrapPayload.Climbs[0].ImageFiles) != 2 || bootstrapPayload.SyncToken == "" || !bootstrapPayload.HasMore || bootstrapPayload.NextCursor == "" || bootstrapPayload.PageSize != 2 {
		t.Fatalf("unexpected bootstrap page metadata: %#v", bootstrapPayload)
	}

	bootstrapNextResponse, err := http.Get(server.URL + "/api/catalog/kilter/bootstrap?page_size=2&cursor=" + url.QueryEscape(bootstrapPayload.NextCursor))
	if err != nil {
		t.Fatalf("GET bootstrap next page: %v", err)
	}
	defer bootstrapNextResponse.Body.Close()
	if bootstrapNextResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected bootstrap next page status 200, got %d", bootstrapNextResponse.StatusCode)
	}

	var bootstrapNextPayload struct {
		Climbs []struct {
			ClimbName string `json:"climb_name"`
		} `json:"climbs"`
		HasMore bool `json:"has_more"`
	}
	if err := json.NewDecoder(bootstrapNextResponse.Body).Decode(&bootstrapNextPayload); err != nil {
		t.Fatalf("decode bootstrap next page: %v", err)
	}
	if len(bootstrapNextPayload.Climbs) != 1 || bootstrapNextPayload.Climbs[0].ClimbName != "Newest Problem" || bootstrapNextPayload.HasMore {
		t.Fatalf("unexpected bootstrap next page: %#v", bootstrapNextPayload)
	}

	invalidCursorResponse, err := http.Get(server.URL + "/api/catalog/kilter/bootstrap?cursor=broken")
	if err != nil {
		t.Fatalf("GET bootstrap invalid cursor: %v", err)
	}
	defer invalidCursorResponse.Body.Close()
	if invalidCursorResponse.StatusCode != http.StatusBadRequest {
		t.Fatalf("expected invalid bootstrap cursor status 400, got %d", invalidCursorResponse.StatusCode)
	}

	deltaResponse, err := http.Get(server.URL + "/api/catalog/kilter/delta")
	if err != nil {
		t.Fatalf("GET initial delta: %v", err)
	}
	defer deltaResponse.Body.Close()
	if deltaResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected initial delta status 200, got %d", deltaResponse.StatusCode)
	}

	var deltaPayload struct {
		Climbs []struct {
			ClimbName string `json:"climb_name"`
		} `json:"climbs"`
		NextToken string `json:"next_token"`
	}
	if err := json.NewDecoder(deltaResponse.Body).Decode(&deltaPayload); err != nil {
		t.Fatalf("decode initial delta: %v", err)
	}
	if len(deltaPayload.Climbs) != 3 || deltaPayload.NextToken == "" {
		t.Fatalf("unexpected initial delta payload: %#v", deltaPayload)
	}

	nextDeltaResponse, err := http.Get(server.URL + "/api/catalog/kilter/delta?after_token=" + url.QueryEscape(deltaPayload.NextToken))
	if err != nil {
		t.Fatalf("GET follow-up delta: %v", err)
	}
	defer nextDeltaResponse.Body.Close()
	if nextDeltaResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected follow-up delta status 200, got %d", nextDeltaResponse.StatusCode)
	}

	var nextDeltaPayload struct {
		Climbs             []any  `json:"climbs"`
		NextToken          string `json:"next_token"`
		RequiresFullResync bool   `json:"requires_full_resync"`
	}
	if err := json.NewDecoder(nextDeltaResponse.Body).Decode(&nextDeltaPayload); err != nil {
		t.Fatalf("decode follow-up delta: %v", err)
	}
	if len(nextDeltaPayload.Climbs) != 0 || nextDeltaPayload.NextToken != deltaPayload.NextToken || nextDeltaPayload.RequiresFullResync {
		t.Fatalf("unexpected follow-up delta payload: %#v", nextDeltaPayload)
	}

	invalidDeltaResponse, err := http.Get(server.URL + "/api/catalog/kilter/delta?after_token=broken")
	if err != nil {
		t.Fatalf("GET invalid delta token: %v", err)
	}
	defer invalidDeltaResponse.Body.Close()
	if invalidDeltaResponse.StatusCode != http.StatusBadRequest {
		t.Fatalf("expected invalid delta token status 400, got %d", invalidDeltaResponse.StatusCode)
	}
}
