package routes_test

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
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
		Room struct {
			Slug             string `json:"slug"`
			RoomName         string `json:"room_name"`
			ProviderID       string `json:"provider_id"`
			FistBumpsEnabled bool   `json:"fist_bumps_enabled"`
			Connection       struct {
				Connected bool `json:"connected"`
			} `json:"connection"`
		} `json:"room"`
		Session struct {
			Token string `json:"token"`
		} `json:"session"`
	}
	if err := json.NewDecoder(createResponse.Body).Decode(&createdRoom); err != nil {
		t.Fatalf("decode create room response: %v", err)
	}
	if createdRoom.Room.ProviderID != string(provider.ID()) || createdRoom.Room.Slug == "" {
		t.Fatalf("unexpected create room payload: %#v", createdRoom)
	}
	if createdRoom.Room.RoomName != "Evening Session" {
		t.Fatalf("unexpected room name in create payload: %#v", createdRoom)
	}
	if !createdRoom.Room.FistBumpsEnabled {
		t.Fatalf("expected fist bumps to default on: %#v", createdRoom)
	}
	if !createdRoom.Room.Connection.Connected {
		t.Fatalf("expected room creation to return a connected provider state: %#v", createdRoom)
	}
	if createdRoom.Session.Token == "" {
		t.Fatalf("expected create room session token, got %#v", createdRoom)
	}
	hostSessionToken := createdRoom.Session.Token

	updateResponse := performAuthenticatedJSONRequest(t, server, http.MethodPatch, "/api/rooms/"+createdRoom.Room.Slug, map[string]string{
		"room_name": "Project Night",
	}, hostSessionToken)
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

	connectResponse := performAuthenticatedJSONRequest(t, server, http.MethodPost, "/api/rooms/"+createdRoom.Room.Slug+"/provider/connect", map[string]any{
		"secret": map[string]string{"token": "room-token-2"},
	}, hostSessionToken)
	if connectResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected connect provider status 200, got %d", connectResponse.StatusCode)
	}

	surfaceResponse := performAuthenticatedJSONRequest(t, server, http.MethodPost, "/api/rooms/"+createdRoom.Room.Slug+"/surface", map[string]any{
		"surface_id": "wall-alpha",
		"context":    map[string]string{},
	}, hostSessionToken)
	if surfaceResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected set surface status 200, got %d", surfaceResponse.StatusCode)
	}

	climbsResponse := performAuthenticatedJSONRequest(t, server, http.MethodGet, "/api/rooms/"+createdRoom.Room.Slug+"/catalog/climbs?q=beta", nil, hostSessionToken)
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

	climbDetailResponse := performAuthenticatedJSONRequest(
		t,
		server,
		http.MethodGet,
		"/api/rooms/"+createdRoom.Room.Slug+"/catalog/climbs/fake-route%3Abeta",
		nil,
		hostSessionToken,
	)
	if climbDetailResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected encoded room catalog climb status 200, got %d", climbDetailResponse.StatusCode)
	}

	joinResponse := performJSONRequest(t, server, http.MethodPost, "/api/rooms/"+createdRoom.Room.Slug+"/join", map[string]string{
		"display_name": "Guest",
	}, nil)
	if joinResponse.StatusCode != http.StatusCreated {
		t.Fatalf("expected join room status 201, got %d", joinResponse.StatusCode)
	}
	var joinPayload struct {
		Session struct {
			Token string `json:"token"`
		} `json:"session"`
	}
	if err := json.NewDecoder(joinResponse.Body).Decode(&joinPayload); err != nil {
		t.Fatalf("decode join room envelope: %v", err)
	}
	guestSessionToken := joinPayload.Session.Token
	if guestSessionToken == "" {
		t.Fatalf("expected join room session token, got %#v", joinPayload)
	}

	unqueuedVoteResponse := performAuthenticatedJSONRequest(t, server, http.MethodPut, "/api/rooms/"+createdRoom.Room.Slug+"/votes/fake-route%3Abeta", nil, guestSessionToken)
	if unqueuedVoteResponse.StatusCode != http.StatusBadRequest {
		t.Fatalf("expected unqueued vote status 400, got %d", unqueuedVoteResponse.StatusCode)
	}

	queueResponse := performAuthenticatedJSONRequest(t, server, http.MethodPost, "/api/rooms/"+createdRoom.Room.Slug+"/queue", map[string]string{
		"climb_id": "fake-route:beta",
	}, guestSessionToken)
	if queueResponse.StatusCode != http.StatusCreated {
		t.Fatalf("expected queue add status 201, got %d", queueResponse.StatusCode)
	}

	voteResponse := performAuthenticatedJSONRequest(t, server, http.MethodPut, "/api/rooms/"+createdRoom.Room.Slug+"/votes/fake-route%3Abeta", nil, guestSessionToken)
	if voteResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected queued vote status 200, got %d", voteResponse.StatusCode)
	}

	finalistResponse := performAuthenticatedJSONRequest(t, server, http.MethodPost, "/api/rooms/"+createdRoom.Room.Slug+"/finalists", map[string]string{
		"climb_id": "fake-route:beta",
	}, hostSessionToken)
	if finalistResponse.StatusCode != http.StatusCreated {
		t.Fatalf("expected finalist add status 201, got %d", finalistResponse.StatusCode)
	}

	statusResponse := performAuthenticatedJSONRequest(t, server, http.MethodPut, "/api/rooms/"+createdRoom.Room.Slug+"/participants/me/status", map[string]string{
		"status": "ready",
	}, guestSessionToken)
	if statusResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected participant status update 200, got %d", statusResponse.StatusCode)
	}

	promoteResponse := performAuthenticatedJSONRequest(t, server, http.MethodPost, "/api/rooms/"+createdRoom.Room.Slug+"/queue/promote", map[string]string{
		"climb_id": "fake-route:beta",
		"status":   "current",
	}, hostSessionToken)
	if promoteResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected queue promote status 200, got %d", promoteResponse.StatusCode)
	}

	pickRandomResponse := performAuthenticatedJSONRequest(t, server, http.MethodPost, "/api/rooms/"+createdRoom.Room.Slug+"/pick-random", map[string]string{
		"source": "finalists",
	}, hostSessionToken)
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

	roomResponse := performAuthenticatedJSONRequest(t, server, http.MethodGet, "/api/rooms/"+createdRoom.Room.Slug, nil, guestSessionToken)
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

	fistBumpsOffResponse := performAuthenticatedJSONRequest(t, server, http.MethodPut, "/api/rooms/"+createdRoom.Room.Slug+"/fist-bumps/settings", map[string]bool{
		"enabled": false,
	}, hostSessionToken)
	if fistBumpsOffResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected fist bumps settings update 200, got %d", fistBumpsOffResponse.StatusCode)
	}

	disabledVoteResponse := performAuthenticatedJSONRequest(t, server, http.MethodPut, "/api/rooms/"+createdRoom.Room.Slug+"/votes/fake-route:beta", nil, guestSessionToken)
	if disabledVoteResponse.StatusCode != http.StatusForbidden {
		t.Fatalf("expected disabled fist bumps to return 403, got %d", disabledVoteResponse.StatusCode)
	}

	closeResponse := performAuthenticatedJSONRequest(t, server, http.MethodPost, "/api/rooms/"+createdRoom.Room.Slug+"/close", nil, hostSessionToken)
	if closeResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected close room status 200, got %d", closeResponse.StatusCode)
	}

	recentSessionsResponse := performJSONRequest(t, server, http.MethodGet, "/api/sessions/recent?limit=3", nil, nil)
	if recentSessionsResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected recent sessions status 200, got %d", recentSessionsResponse.StatusCode)
	}
	var recentSessionsPayload struct {
		Sessions []struct {
			RoomSlug         string `json:"room_slug"`
			RoomName         string `json:"room_name"`
			ProviderID       string `json:"provider_id"`
			ParticipantCount int    `json:"participant_count"`
			TopVoted         []struct {
				VoteCount int `json:"vote_count"`
				Climb     struct {
					ID string `json:"id"`
				} `json:"climb"`
			} `json:"top_voted"`
		} `json:"sessions"`
	}
	if err := json.NewDecoder(recentSessionsResponse.Body).Decode(&recentSessionsPayload); err != nil {
		t.Fatalf("decode recent sessions response: %v", err)
	}
	if len(recentSessionsPayload.Sessions) != 1 {
		t.Fatalf("expected one recent session, got %#v", recentSessionsPayload.Sessions)
	}
	if recentSessionsPayload.Sessions[0].RoomSlug != createdRoom.Room.Slug ||
		recentSessionsPayload.Sessions[0].RoomName != "Project Night" ||
		recentSessionsPayload.Sessions[0].ProviderID != string(provider.ID()) {
		t.Fatalf("unexpected recent session identity: %#v", recentSessionsPayload.Sessions[0])
	}
	if recentSessionsPayload.Sessions[0].ParticipantCount != 2 {
		t.Fatalf("expected participant count 2 in recent session, got %#v", recentSessionsPayload.Sessions[0])
	}
	if len(recentSessionsPayload.Sessions[0].TopVoted) != 1 ||
		recentSessionsPayload.Sessions[0].TopVoted[0].Climb.ID != "fake-route:beta" ||
		recentSessionsPayload.Sessions[0].TopVoted[0].VoteCount != 1 {
		t.Fatalf("unexpected recent session top-voted payload: %#v", recentSessionsPayload.Sessions[0].TopVoted)
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
	if payload["code"] != "runtime_unavailable" {
		t.Fatalf("expected runtime_unavailable code, got %#v", payload)
	}
}

func TestCreateRoomCanStartWithFistBumpsDisabled(t *testing.T) {
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

	provider := testprovider.New(providers.ProviderID("fake-fist-bumps"))
	providers.Register(provider)
	rooms.DefaultService = rooms.NewService()
	if err := rooms.DefaultService.Migrate(context.Background()); err != nil {
		t.Fatalf("migrate app database: %v", err)
	}

	server := httptest.NewServer(routes.SetupRoutes())
	defer server.Close()

	response := performJSONRequest(t, server, http.MethodPost, "/api/rooms", map[string]any{
		"provider_id":        string(provider.ID()),
		"display_name":       "Host",
		"fist_bumps_enabled": false,
		"secret":             map[string]string{"token": "room-token"},
	}, nil)
	if response.StatusCode != http.StatusCreated {
		t.Fatalf("expected create room status 201, got %d", response.StatusCode)
	}

	var payload struct {
		Room struct {
			FistBumpsEnabled bool `json:"fist_bumps_enabled"`
		} `json:"room"`
	}
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		t.Fatalf("decode create room response: %v", err)
	}
	if payload.Room.FistBumpsEnabled {
		t.Fatalf("expected fist bumps to start disabled, got %#v", payload)
	}
}

func TestRoomErrorCodesAndCapabilities(t *testing.T) {
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

	provider := testprovider.New(providers.ProviderID("fake-errors"))
	providers.Register(provider)
	rooms.DefaultService = rooms.NewService()
	if err := rooms.DefaultService.Migrate(context.Background()); err != nil {
		t.Fatalf("migrate app database: %v", err)
	}

	server := httptest.NewServer(routes.SetupRoutes())
	defer server.Close()

	capabilitiesResponse := performJSONRequest(t, server, http.MethodGet, "/api/providers/capabilities", nil, nil)
	if capabilitiesResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected capabilities status 200, got %d", capabilitiesResponse.StatusCode)
	}
	var capabilitiesPayload struct {
		Providers []struct {
			ID            string `json:"id"`
			RoomSupported bool   `json:"room_supported"`
			SoloSupported bool   `json:"solo_supported"`
		} `json:"providers"`
	}
	if err := json.NewDecoder(capabilitiesResponse.Body).Decode(&capabilitiesPayload); err != nil {
		t.Fatalf("decode capabilities response: %v", err)
	}
	if len(capabilitiesPayload.Providers) < 2 {
		t.Fatalf("expected built-in providers in capabilities payload, got %#v", capabilitiesPayload)
	}

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
		Room struct {
			Slug string `json:"slug"`
		} `json:"room"`
	}
	if err := json.NewDecoder(createResponse.Body).Decode(&createdRoom); err != nil {
		t.Fatalf("decode create room response: %v", err)
	}

	duplicateJoinResponse := performJSONRequest(t, server, http.MethodPost, "/api/rooms/"+createdRoom.Room.Slug+"/join", map[string]string{
		"display_name": "Host",
	}, nil)
	if duplicateJoinResponse.StatusCode != http.StatusBadRequest {
		t.Fatalf("expected duplicate join status 400, got %d", duplicateJoinResponse.StatusCode)
	}
	var duplicateJoinPayload map[string]string
	if err := json.NewDecoder(duplicateJoinResponse.Body).Decode(&duplicateJoinPayload); err != nil {
		t.Fatalf("decode duplicate join response: %v", err)
	}
	if duplicateJoinPayload["code"] != "display_name_taken" {
		t.Fatalf("expected display_name_taken code, got %#v", duplicateJoinPayload)
	}

	unauthorizedRoomResponse := performJSONRequest(t, server, http.MethodGet, "/api/rooms/"+createdRoom.Room.Slug, nil, nil)
	if unauthorizedRoomResponse.StatusCode != http.StatusUnauthorized {
		t.Fatalf("expected unauthorized room load status 401, got %d", unauthorizedRoomResponse.StatusCode)
	}
	var unauthorizedRoomPayload map[string]string
	if err := json.NewDecoder(unauthorizedRoomResponse.Body).Decode(&unauthorizedRoomPayload); err != nil {
		t.Fatalf("decode unauthorized room response: %v", err)
	}
	if unauthorizedRoomPayload["code"] != "session_required" {
		t.Fatalf("expected session_required code, got %#v", unauthorizedRoomPayload)
	}
	if unauthorizedRoomPayload["request_id"] == "" {
		t.Fatalf("expected request_id in error payload, got %#v", unauthorizedRoomPayload)
	}
}

func TestObservabilityRoutesAreDisabled(t *testing.T) {
	tempDir := t.TempDir()
	config.SetRuntimeConfig(config.RuntimeConfig{
		DataDir:       tempDir,
		AppDBPath:     filepath.Join(tempDir, "app.db"),
		AppSecret:     "test-app-secret",
		EncryptionKey: base64.StdEncoding.EncodeToString(bytes.Repeat([]byte{5}, 32)),
	})

	server := httptest.NewServer(routes.SetupRoutes())
	defer server.Close()

	testCases := []struct {
		method string
		path   string
	}{
		{method: http.MethodGet, path: "/api/operator/status"},
		{method: http.MethodGet, path: "/api/operator/product"},
		{method: http.MethodGet, path: "/api/metrics"},
		{method: http.MethodPost, path: "/api/analytics/events"},
	}

	for _, tc := range testCases {
		request, err := http.NewRequest(tc.method, server.URL+tc.path, nil)
		if err != nil {
			t.Fatalf("new %s %s request: %v", tc.method, tc.path, err)
		}
		response, err := http.DefaultClient.Do(request)
		if err != nil {
			t.Fatalf("%s %s request: %v", tc.method, tc.path, err)
		}
		response.Body.Close()
		if response.StatusCode != http.StatusNotFound {
			t.Fatalf("expected %s %s to return 404, got %d", tc.method, tc.path, response.StatusCode)
		}
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
		Room struct {
			Slug string `json:"slug"`
		} `json:"room"`
		Session struct {
			Token string `json:"token"`
		} `json:"session"`
	}
	if err := json.NewDecoder(createResponse.Body).Decode(&createdRoom); err != nil {
		t.Fatalf("decode create room response: %v", err)
	}
	hostSessionToken := createdRoom.Session.Token
	slug := createdRoom.Room.Slug

	// join room as guest
	joinResponse := performJSONRequest(t, server, http.MethodPost, "/api/rooms/"+slug+"/join", map[string]string{
		"display_name": "Guest",
	}, nil)
	if joinResponse.StatusCode != http.StatusCreated {
		t.Fatalf("expected join room status 201, got %d", joinResponse.StatusCode)
	}
	var joinPayload struct {
		Room struct {
			Participants []struct {
				ID          uint   `json:"id"`
				DisplayName string `json:"display_name"`
			} `json:"participants"`
		} `json:"room"`
		Session struct {
			Token string `json:"token"`
		} `json:"session"`
	}
	if err := json.NewDecoder(joinResponse.Body).Decode(&joinPayload); err != nil {
		t.Fatalf("decode join room response: %v", err)
	}
	guestSessionToken := joinPayload.Session.Token
	var guestParticipantID uint
	for _, participant := range joinPayload.Room.Participants {
		if participant.DisplayName == "Guest" {
			guestParticipantID = participant.ID
			break
		}
	}
	if guestParticipantID == 0 {
		t.Fatalf("expected to find guest participant id in join response")
	}

	// connect provider and set surface as host
	connectResponse := performAuthenticatedJSONRequest(t, server, http.MethodPost, "/api/rooms/"+slug+"/provider/connect", map[string]any{
		"secret": map[string]string{"token": "room-token"},
	}, hostSessionToken)
	if connectResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected connect provider status 200, got %d", connectResponse.StatusCode)
	}
	surfaceResponse := performAuthenticatedJSONRequest(t, server, http.MethodPost, "/api/rooms/"+slug+"/surface", map[string]any{
		"surface_id": "wall-alpha",
		"context":    map[string]string{},
	}, hostSessionToken)
	if surfaceResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected set surface status 200, got %d", surfaceResponse.StatusCode)
	}

	promoteResponse := performAuthenticatedJSONRequest(
		t,
		server,
		http.MethodPatch,
		fmt.Sprintf("/api/rooms/%s/participants/%d/role", slug, guestParticipantID),
		map[string]string{"role": "co_host"},
		hostSessionToken,
	)
	if promoteResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected co-host promotion status 200, got %d", promoteResponse.StatusCode)
	}

	// guest must NOT be able to perform host-only operations
	hostOnlyCases := []struct {
		name           string
		method         string
		path           string
		body           any
		expectedStatus int
	}{
		{"rename room", http.MethodPatch, "/api/rooms/" + slug, map[string]string{"room_name": "Guest Rename"}, http.StatusForbidden},
		{"update fist bumps setting", http.MethodPut, "/api/rooms/" + slug + "/fist-bumps/settings", map[string]bool{"enabled": false}, http.StatusForbidden},
		{"close room", http.MethodPost, "/api/rooms/" + slug + "/close", nil, http.StatusForbidden},
		{"kick participant", http.MethodDelete, "/api/rooms/" + slug + "/participants/1", nil, http.StatusForbidden},
		{"assign cohost", http.MethodPatch, fmt.Sprintf("/api/rooms/%s/participants/%d/role", slug, guestParticipantID), map[string]string{"role": "participant"}, http.StatusForbidden},
	}
	for _, tc := range hostOnlyCases {
		t.Run("guest_denied_"+tc.name, func(t *testing.T) {
			resp := performAuthenticatedJSONRequest(t, server, tc.method, tc.path, tc.body, guestSessionToken)
			if resp.StatusCode != tc.expectedStatus {
				t.Fatalf("expected %d for %s, got %d", tc.expectedStatus, tc.name, resp.StatusCode)
			}
		})
	}

	// guest CAN perform participant-level operations
	t.Run("guest_allowed_queue_add", func(t *testing.T) {
		resp := performAuthenticatedJSONRequest(t, server, http.MethodPost, "/api/rooms/"+slug+"/queue", map[string]string{"climb_id": "fake-perm:beta"}, guestSessionToken)
		if resp.StatusCode != http.StatusCreated {
			t.Fatalf("expected queue add status 201, got %d", resp.StatusCode)
		}
	})
	t.Run("cohost_allowed_finalist_add", func(t *testing.T) {
		resp := performAuthenticatedJSONRequest(t, server, http.MethodPost, "/api/rooms/"+slug+"/finalists", map[string]string{"climb_id": "fake-perm:beta"}, guestSessionToken)
		if resp.StatusCode != http.StatusCreated {
			t.Fatalf("expected finalist add status 201, got %d", resp.StatusCode)
		}
	})
	t.Run("cohost_allowed_surface_change", func(t *testing.T) {
		resp := performAuthenticatedJSONRequest(t, server, http.MethodPost, "/api/rooms/"+slug+"/surface", map[string]any{
			"surface_id": "wall-beta",
			"context":    map[string]string{},
		}, guestSessionToken)
		if resp.StatusCode != http.StatusOK {
			t.Fatalf("expected co-host surface update status 200, got %d", resp.StatusCode)
		}
	})
	t.Run("guest_allowed_vote", func(t *testing.T) {
		queueResponse := performAuthenticatedJSONRequest(t, server, http.MethodPost, "/api/rooms/"+slug+"/queue", map[string]string{"climb_id": "fake-perm:gamma"}, guestSessionToken)
		if queueResponse.StatusCode != http.StatusCreated {
			t.Fatalf("expected second queue add status 201, got %d", queueResponse.StatusCode)
		}
		resp := performAuthenticatedJSONRequest(t, server, http.MethodPut, "/api/rooms/"+slug+"/votes/fake-perm:gamma", nil, guestSessionToken)
		if resp.StatusCode != http.StatusOK {
			t.Fatalf("expected vote status 200, got %d", resp.StatusCode)
		}
	})
	t.Run("guest_allowed_status_update", func(t *testing.T) {
		resp := performAuthenticatedJSONRequest(t, server, http.MethodPut, "/api/rooms/"+slug+"/participants/me/status", map[string]string{"status": "ready"}, guestSessionToken)
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
	_ []*http.Cookie,
) *http.Response {
	return performJSONRequestWithHeaders(t, server, method, path, body, nil)
}

func performAuthenticatedJSONRequest(
	t *testing.T,
	server *httptest.Server,
	method string,
	path string,
	body any,
	sessionToken string,
) *http.Response {
	headers := map[string]string{
		"Authorization": "Bearer " + sessionToken,
	}
	return performJSONRequestWithHeaders(t, server, method, path, body, headers)
}

func performJSONRequestWithHeaders(
	t *testing.T,
	server *httptest.Server,
	method string,
	path string,
	body any,
	headers map[string]string,
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
	for key, value := range headers {
		request.Header.Set(key, value)
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
