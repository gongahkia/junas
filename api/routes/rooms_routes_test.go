package routes_test

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"

	"github.com/lczm/kilter-together/api/config"
	"github.com/lczm/kilter-together/api/providers"
	"github.com/lczm/kilter-together/api/rooms"
	"github.com/lczm/kilter-together/api/routes"
	"github.com/lczm/kilter-together/api/testutil/testprovider"
)

func TestRoomRoutesContract(t *testing.T) {
	tempDir := t.TempDir()
	appDBPath := filepath.Join(tempDir, "app.db")
	config.SetRuntimeConfig(config.RuntimeConfig{
		DataDir:       tempDir,
		AppDBPath:     appDBPath,
		AppSecret:     "test-app-secret",
		EncryptionKey: base64.StdEncoding.EncodeToString(bytes.Repeat([]byte{5}, 32)),
	})
	if err := config.ConnectAppDB(appDBPath); err != nil {
		t.Fatalf("connect app database: %v", err)
	}

	provider := testprovider.New(providers.ProviderID("fake-route"))
	providers.Register(provider)
	rooms.DefaultService = rooms.NewService()
	if err := rooms.DefaultService.Migrate(context.Background()); err != nil {
		t.Fatalf("migrate app database: %v", err)
	}

	server := httptest.NewServer(routes.SetupRoutes())
	defer server.Close()

	createResponse := performJSONRequest(t, server, http.MethodPost, "/api/rooms", map[string]any{
		"provider_id":  string(provider.ID()),
		"room_name":    "Evening Session",
		"display_name": "Host",
		"secret": map[string]string{
			"token": "room-token",
		},
	}, nil)
	if createResponse.StatusCode != http.StatusCreated {
		t.Fatalf("expected create room status 201, got %d", createResponse.StatusCode)
	}

	var createdRoom struct {
		Slug             string `json:"slug"`
		RoomName         string `json:"room_name"`
		ProviderID       string `json:"provider_id"`
		FistBumpsEnabled bool   `json:"fist_bumps_enabled"`
		Connection       struct {
			Connected bool `json:"connected"`
		} `json:"connection"`
	}
	if err := json.NewDecoder(createResponse.Body).Decode(&createdRoom); err != nil {
		t.Fatalf("decode create room response: %v", err)
	}
	if createdRoom.ProviderID != string(provider.ID()) || createdRoom.Slug == "" {
		t.Fatalf("unexpected create room payload: %#v", createdRoom)
	}
	if createdRoom.RoomName != "Evening Session" {
		t.Fatalf("unexpected room name in create payload: %#v", createdRoom)
	}
	if !createdRoom.FistBumpsEnabled {
		t.Fatalf("expected fist bumps to default on: %#v", createdRoom)
	}
	if !createdRoom.Connection.Connected {
		t.Fatalf("expected room creation to return a connected provider state: %#v", createdRoom)
	}
	hostCookies := createResponse.Cookies()

	updateResponse := performJSONRequest(t, server, http.MethodPatch, "/api/rooms/"+createdRoom.Slug, map[string]string{
		"room_name": "Project Night",
	}, hostCookies)
	if updateResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected update room status 200, got %d", updateResponse.StatusCode)
	}
	var updatedRoom struct {
		RoomName string `json:"room_name"`
	}
	if err := json.NewDecoder(updateResponse.Body).Decode(&updatedRoom); err != nil {
		t.Fatalf("decode update room response: %v", err)
	}
	if updatedRoom.RoomName != "Project Night" {
		t.Fatalf("unexpected update room payload: %#v", updatedRoom)
	}

	connectResponse := performJSONRequest(t, server, http.MethodPost, "/api/rooms/"+createdRoom.Slug+"/provider/connect", map[string]any{
		"secret": map[string]string{"token": "room-token-2"},
	}, hostCookies)
	if connectResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected connect provider status 200, got %d", connectResponse.StatusCode)
	}

	surfaceResponse := performJSONRequest(t, server, http.MethodPost, "/api/rooms/"+createdRoom.Slug+"/surface", map[string]any{
		"surface_id": "wall-alpha",
		"context":    map[string]string{},
	}, hostCookies)
	if surfaceResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected set surface status 200, got %d", surfaceResponse.StatusCode)
	}

	climbsResponse := performJSONRequest(t, server, http.MethodGet, "/api/rooms/"+createdRoom.Slug+"/catalog/climbs?q=beta", nil, hostCookies)
	if climbsResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected room catalog climbs status 200, got %d", climbsResponse.StatusCode)
	}

	var climbsPayload struct {
		Climbs []struct {
			ID   string `json:"id"`
			Name string `json:"name"`
		} `json:"climbs"`
	}
	if err := json.NewDecoder(climbsResponse.Body).Decode(&climbsPayload); err != nil {
		t.Fatalf("decode room catalog climbs response: %v", err)
	}
	if len(climbsPayload.Climbs) != 1 || climbsPayload.Climbs[0].ID != "fake-route:beta" {
		t.Fatalf("unexpected room catalog climbs payload: %#v", climbsPayload.Climbs)
	}

	climbDetailResponse := performJSONRequest(
		t,
		server,
		http.MethodGet,
		"/api/rooms/"+createdRoom.Slug+"/catalog/climbs/fake-route%3Abeta",
		nil,
		hostCookies,
	)
	if climbDetailResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected encoded room catalog climb status 200, got %d", climbDetailResponse.StatusCode)
	}

	joinResponse := performJSONRequest(t, server, http.MethodPost, "/api/rooms/"+createdRoom.Slug+"/join", map[string]string{
		"display_name": "Guest",
	}, nil)
	if joinResponse.StatusCode != http.StatusCreated {
		t.Fatalf("expected join room status 201, got %d", joinResponse.StatusCode)
	}
	guestCookies := joinResponse.Cookies()

	unqueuedVoteResponse := performJSONRequest(t, server, http.MethodPut, "/api/rooms/"+createdRoom.Slug+"/votes/fake-route%3Abeta", nil, guestCookies)
	if unqueuedVoteResponse.StatusCode != http.StatusBadRequest {
		t.Fatalf("expected unqueued vote status 400, got %d", unqueuedVoteResponse.StatusCode)
	}

	queueResponse := performJSONRequest(t, server, http.MethodPost, "/api/rooms/"+createdRoom.Slug+"/queue", map[string]string{
		"climb_id": "fake-route:beta",
	}, guestCookies)
	if queueResponse.StatusCode != http.StatusCreated {
		t.Fatalf("expected queue add status 201, got %d", queueResponse.StatusCode)
	}

	voteResponse := performJSONRequest(t, server, http.MethodPut, "/api/rooms/"+createdRoom.Slug+"/votes/fake-route%3Abeta", nil, guestCookies)
	if voteResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected queued vote status 200, got %d", voteResponse.StatusCode)
	}

	finalistResponse := performJSONRequest(t, server, http.MethodPost, "/api/rooms/"+createdRoom.Slug+"/finalists", map[string]string{
		"climb_id": "fake-route:beta",
	}, hostCookies)
	if finalistResponse.StatusCode != http.StatusCreated {
		t.Fatalf("expected finalist add status 201, got %d", finalistResponse.StatusCode)
	}

	statusResponse := performJSONRequest(t, server, http.MethodPut, "/api/rooms/"+createdRoom.Slug+"/participants/me/status", map[string]string{
		"status": "ready",
	}, guestCookies)
	if statusResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected participant status update 200, got %d", statusResponse.StatusCode)
	}

	promoteResponse := performJSONRequest(t, server, http.MethodPost, "/api/rooms/"+createdRoom.Slug+"/queue/promote", map[string]string{
		"climb_id": "fake-route:beta",
		"status":   "current",
	}, hostCookies)
	if promoteResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected queue promote status 200, got %d", promoteResponse.StatusCode)
	}

	pickRandomResponse := performJSONRequest(t, server, http.MethodPost, "/api/rooms/"+createdRoom.Slug+"/pick-random", map[string]string{
		"source": "finalists",
	}, hostCookies)
	if pickRandomResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected pick random status 200, got %d", pickRandomResponse.StatusCode)
	}

	var pickRandomPayload struct {
		Climb struct {
			ID string `json:"id"`
		} `json:"climb"`
	}
	if err := json.NewDecoder(pickRandomResponse.Body).Decode(&pickRandomPayload); err != nil {
		t.Fatalf("decode pick random response: %v", err)
	}
	if pickRandomPayload.Climb.ID != "fake-route:beta" {
		t.Fatalf("expected random finalist fake-route:beta, got %#v", pickRandomPayload)
	}

	roomResponse := performJSONRequest(t, server, http.MethodGet, "/api/rooms/"+createdRoom.Slug, nil, guestCookies)
	if roomResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected room snapshot status 200, got %d", roomResponse.StatusCode)
	}

	var roomPayload struct {
		RoomName     string `json:"room_name"`
		Participants []struct {
			DisplayName string `json:"display_name"`
			Status      string `json:"status"`
		} `json:"participants"`
		CurrentClimb *struct {
			ID string `json:"id"`
		} `json:"current_climb"`
		VoteCounts map[string]int `json:"vote_counts"`
		Finalists  []struct {
			Climb struct {
				ID string `json:"id"`
			} `json:"climb"`
		} `json:"finalists"`
		Queue []struct {
			Status string `json:"status"`
			Climb  struct {
				ID string `json:"id"`
			} `json:"climb"`
		} `json:"queue"`
		FistBumpsEnabled bool `json:"fist_bumps_enabled"`
	}
	if err := json.NewDecoder(roomResponse.Body).Decode(&roomPayload); err != nil {
		t.Fatalf("decode room snapshot response: %v", err)
	}
	if roomPayload.RoomName != "Project Night" {
		t.Fatalf("expected room name to persist in snapshot, got %#v", roomPayload.RoomName)
	}
	if len(roomPayload.Participants) != 2 {
		t.Fatalf("expected two room participants, got %#v", roomPayload.Participants)
	}
	if roomPayload.Participants[1].Status != "ready" {
		t.Fatalf("expected guest status to be ready, got %#v", roomPayload.Participants)
	}
	if roomPayload.VoteCounts["fake-route:beta"] != 1 {
		t.Fatalf("expected fake-route:beta vote count, got %#v", roomPayload.VoteCounts)
	}
	if len(roomPayload.Queue) != 1 || roomPayload.Queue[0].Climb.ID != "fake-route:beta" {
		t.Fatalf("unexpected room queue payload: %#v", roomPayload.Queue)
	}
	if roomPayload.Queue[0].Status != "current" {
		t.Fatalf("expected promoted queue entry to be current, got %#v", roomPayload.Queue)
	}
	if roomPayload.CurrentClimb == nil || roomPayload.CurrentClimb.ID != "fake-route:beta" {
		t.Fatalf("expected current climb fake-route:beta, got %#v", roomPayload.CurrentClimb)
	}
	if len(roomPayload.Finalists) != 1 || roomPayload.Finalists[0].Climb.ID != "fake-route:beta" {
		t.Fatalf("unexpected finalists payload: %#v", roomPayload.Finalists)
	}
	if !roomPayload.FistBumpsEnabled {
		t.Fatalf("expected fist bumps to remain enabled, got %#v", roomPayload)
	}

	fistBumpsOffResponse := performJSONRequest(t, server, http.MethodPut, "/api/rooms/"+createdRoom.Slug+"/fist-bumps/settings", map[string]bool{
		"enabled": false,
	}, hostCookies)
	if fistBumpsOffResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected fist bumps settings update 200, got %d", fistBumpsOffResponse.StatusCode)
	}

	disabledVoteResponse := performJSONRequest(t, server, http.MethodPut, "/api/rooms/"+createdRoom.Slug+"/votes/fake-route:beta", nil, guestCookies)
	if disabledVoteResponse.StatusCode != http.StatusForbidden {
		t.Fatalf("expected disabled fist bumps to return 403, got %d", disabledVoteResponse.StatusCode)
	}
}

func TestCreateRoomRequiresEncryptionKey(t *testing.T) {
	tempDir := t.TempDir()
	appDBPath := filepath.Join(tempDir, "app.db")
	config.SetRuntimeConfig(config.RuntimeConfig{
		DataDir:   tempDir,
		AppDBPath: appDBPath,
		AppSecret: "test-app-secret",
	})
	if err := config.ConnectAppDB(appDBPath); err != nil {
		t.Fatalf("connect app database: %v", err)
	}

	provider := testprovider.New(providers.ProviderID("fake-misconfig"))
	providers.Register(provider)
	rooms.DefaultService = rooms.NewService()
	if err := rooms.DefaultService.Migrate(context.Background()); err != nil {
		t.Fatalf("migrate app database: %v", err)
	}

	server := httptest.NewServer(routes.SetupRoutes())
	defer server.Close()

	response := performJSONRequest(t, server, http.MethodPost, "/api/rooms", map[string]any{
		"provider_id":  string(provider.ID()),
		"display_name": "Host",
		"secret": map[string]string{
			"token": "room-token",
		},
	}, nil)
	if response.StatusCode != http.StatusInternalServerError {
		t.Fatalf("expected create room status 500, got %d", response.StatusCode)
	}

	var payload map[string]string
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		t.Fatalf("decode error response: %v", err)
	}
	if payload["error"] != "KILTER_TOGETHER_ENCRYPTION_KEY is required to create rooms" {
		t.Fatalf("unexpected error payload: %#v", payload)
	}
}

func TestRoomPermissionBoundaries(t *testing.T) {
	tempDir := t.TempDir()
	appDBPath := filepath.Join(tempDir, "app.db")
	config.SetRuntimeConfig(config.RuntimeConfig{
		DataDir:       tempDir,
		AppDBPath:     appDBPath,
		AppSecret:     "test-app-secret",
		EncryptionKey: base64.StdEncoding.EncodeToString(bytes.Repeat([]byte{5}, 32)),
	})
	if err := config.ConnectAppDB(appDBPath); err != nil {
		t.Fatalf("connect app database: %v", err)
	}

	provider := testprovider.New(providers.ProviderID("fake-perm"))
	providers.Register(provider)
	rooms.DefaultService = rooms.NewService()
	if err := rooms.DefaultService.Migrate(context.Background()); err != nil {
		t.Fatalf("migrate app database: %v", err)
	}

	server := httptest.NewServer(routes.SetupRoutes())
	defer server.Close()

	// create room as host
	createResponse := performJSONRequest(t, server, http.MethodPost, "/api/rooms", map[string]any{
		"provider_id":  string(provider.ID()),
		"display_name": "Host",
		"secret": map[string]string{
			"token": "room-token",
		},
	}, nil)
	if createResponse.StatusCode != http.StatusCreated {
		t.Fatalf("expected create room status 201, got %d", createResponse.StatusCode)
	}
	var createdRoom struct {
		Slug string `json:"slug"`
	}
	if err := json.NewDecoder(createResponse.Body).Decode(&createdRoom); err != nil {
		t.Fatalf("decode create room response: %v", err)
	}
	hostCookies := createResponse.Cookies()
	slug := createdRoom.Slug

	// join room as guest
	joinResponse := performJSONRequest(t, server, http.MethodPost, "/api/rooms/"+slug+"/join", map[string]string{
		"display_name": "Guest",
	}, nil)
	if joinResponse.StatusCode != http.StatusCreated {
		t.Fatalf("expected join room status 201, got %d", joinResponse.StatusCode)
	}
	guestCookies := joinResponse.Cookies()

	// connect provider and set surface as host
	connectResponse := performJSONRequest(t, server, http.MethodPost, "/api/rooms/"+slug+"/provider/connect", map[string]any{
		"secret": map[string]string{"token": "room-token"},
	}, hostCookies)
	if connectResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected connect provider status 200, got %d", connectResponse.StatusCode)
	}
	surfaceResponse := performJSONRequest(t, server, http.MethodPost, "/api/rooms/"+slug+"/surface", map[string]any{
		"surface_id": "wall-alpha",
		"context":    map[string]string{},
	}, hostCookies)
	if surfaceResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected set surface status 200, got %d", surfaceResponse.StatusCode)
	}

	// guest must NOT be able to perform host-only operations
	hostOnlyCases := []struct {
		name   string
		method string
		path   string
		body   any
	}{
		{"rename room", http.MethodPatch, "/api/rooms/" + slug, map[string]string{"room_name": "Guest Rename"}},
		{"add finalist", http.MethodPost, "/api/rooms/" + slug + "/finalists", map[string]string{"climb_id": "fake-perm:beta"}},
		{"reorder finalists", http.MethodPatch, "/api/rooms/" + slug + "/finalists/reorder", nil},
		{"promote queue", http.MethodPost, "/api/rooms/" + slug + "/queue/promote", nil},
		{"reorder queue", http.MethodPatch, "/api/rooms/" + slug + "/queue/reorder", nil},
		{"update fist bumps setting", http.MethodPut, "/api/rooms/" + slug + "/fist-bumps/settings", map[string]bool{"enabled": false}},
		{"close room", http.MethodPost, "/api/rooms/" + slug + "/close", nil},
		{"kick participant", http.MethodDelete, "/api/rooms/" + slug + "/participants/1", nil},
	}
	for _, tc := range hostOnlyCases {
		t.Run("guest_denied_"+tc.name, func(t *testing.T) {
			resp := performJSONRequest(t, server, tc.method, tc.path, tc.body, guestCookies)
			if resp.StatusCode != http.StatusUnauthorized {
				t.Fatalf("expected 401 for %s, got %d", tc.name, resp.StatusCode)
			}
		})
	}

	// guest CAN perform participant-level operations
	t.Run("guest_allowed_queue_add", func(t *testing.T) {
		resp := performJSONRequest(t, server, http.MethodPost, "/api/rooms/"+slug+"/queue", map[string]string{"climb_id": "fake-perm:beta"}, guestCookies)
		if resp.StatusCode != http.StatusCreated {
			t.Fatalf("expected queue add status 201, got %d", resp.StatusCode)
		}
	})
	t.Run("guest_allowed_vote", func(t *testing.T) {
		resp := performJSONRequest(t, server, http.MethodPut, "/api/rooms/"+slug+"/votes/fake-perm:beta", nil, guestCookies)
		if resp.StatusCode != http.StatusOK {
			t.Fatalf("expected vote status 200, got %d", resp.StatusCode)
		}
	})
	t.Run("guest_allowed_status_update", func(t *testing.T) {
		resp := performJSONRequest(t, server, http.MethodPut, "/api/rooms/"+slug+"/participants/me/status", map[string]string{"status": "ready"}, guestCookies)
		if resp.StatusCode != http.StatusOK {
			t.Fatalf("expected participant status update 200, got %d", resp.StatusCode)
		}
	})
}

func performJSONRequest(
	t *testing.T,
	server *httptest.Server,
	method string,
	path string,
	body any,
	cookies []*http.Cookie,
) *http.Response {
	t.Helper()

	var payloadReader *bytes.Reader
	if body == nil {
		payloadReader = bytes.NewReader(nil)
	} else {
		payloadBytes, err := json.Marshal(body)
		if err != nil {
			t.Fatalf("marshal request body: %v", err)
		}
		payloadReader = bytes.NewReader(payloadBytes)
	}

	request, err := http.NewRequest(method, server.URL+path, payloadReader)
	if err != nil {
		t.Fatalf("new %s %s request: %v", method, path, err)
	}
	if body != nil {
		request.Header.Set("Content-Type", "application/json")
	}
	for _, cookie := range cookies {
		request.AddCookie(cookie)
	}

	response, err := http.DefaultClient.Do(request)
	if err != nil {
		t.Fatalf("%s %s request: %v", method, path, err)
	}
	t.Cleanup(func() {
		response.Body.Close()
	})

	return response
}
