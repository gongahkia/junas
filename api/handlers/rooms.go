package handlers

import (
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/lczm/kilter-together/api/config"
	"github.com/lczm/kilter-together/api/observability"
	"github.com/lczm/kilter-together/api/providers"
	"github.com/lczm/kilter-together/api/rooms"
	"github.com/lczm/kilter-together/api/security"
)

type createRoomRequest struct {
	ProviderID  string            `json:"provider_id"`
	RoomName    string            `json:"room_name"`
	DisplayName string            `json:"display_name"`
	Secret      map[string]string `json:"secret"`
}

type updateRoomRequest struct {
	RoomName string `json:"room_name"`
}

type updateFistBumpsRequest struct {
	Enabled bool `json:"enabled"`
}

type joinRoomRequest struct {
	DisplayName string `json:"display_name"`
}

type connectProviderRequest struct {
	Secret map[string]string `json:"secret"`
}

type setSurfaceRequest struct {
	SurfaceID string            `json:"surface_id"`
	Context   map[string]string `json:"context"`
}

type reorderQueueRequest struct {
	EntryIDs []uint `json:"entry_ids"`
}

type reorderFinalistsRequest struct {
	EntryIDs []uint `json:"entry_ids"`
}

type updateQueueEntryRequest struct {
	Status string `json:"status"`
}

type addQueueEntryRequest struct {
	ClimbID string `json:"climb_id"`
}

type addFinalistRequest struct {
	ClimbID string `json:"climb_id"`
}

type pickRandomRequest struct {
	Source string `json:"source"`
}

type promoteQueueRequest struct {
	ClimbID string `json:"climb_id"`
	Status  string `json:"status"`
}

type participantStatusRequest struct {
	Status string `json:"status"`
}

type updateParticipantRoleRequest struct {
	Role string `json:"role"`
}

type viewerAccessMode string

const (
	viewerAccessAny     viewerAccessMode = "any"
	viewerAccessManager viewerAccessMode = "manager"
	viewerAccessHost    viewerAccessMode = "host"
)

// CreateRoom handles POST /api/rooms.
// @Summary Create a collaborative room
// @Description Create a room, validate the provider secret, persist the host session, and return the initial room snapshot.
// @Tags rooms
// @Accept json
// @Produce json
// @Param request body createRoomRequest true "Create room payload"
// @Success 201 {object} rooms.RoomSnapshot
// @Failure 400 {object} map[string]string
// @Failure 500 {object} map[string]string
// @Router /rooms [post]
func CreateRoom(w http.ResponseWriter, r *http.Request) {
	if strings.TrimSpace(config.GetRuntimeConfig().AppSecret) == "" {
		writeRequestError(
			w,
			r,
			http.StatusInternalServerError,
			"runtime_unavailable",
			"KILTER_TOGETHER_APP_SECRET is required to create rooms",
			nil,
		)
		return
	}
	if strings.TrimSpace(config.GetRuntimeConfig().EncryptionKey) == "" {
		writeRequestError(
			w,
			r,
			http.StatusInternalServerError,
			"runtime_unavailable",
			"KILTER_TOGETHER_ENCRYPTION_KEY is required to create rooms",
			nil,
		)
		return
	}

	var request createRoomRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid request body")
		return
	}
	if len(request.RoomName) > 80 {
		request.RoomName = request.RoomName[:80]
	}
	if len(request.DisplayName) > 50 {
		request.DisplayName = request.DisplayName[:50]
	}

	snapshot, hostSessionID, err := rooms.DefaultService.CreateRoom(
		r.Context(),
		providers.ProviderID(strings.ToLower(strings.TrimSpace(request.ProviderID))),
		request.RoomName,
		request.DisplayName,
		request.Secret,
	)
	if err != nil {
		observability.RecordRoomAction("create_room", request.ProviderID, err)
		writeRoomError(w, r, err, http.StatusBadRequest, "provider_auth_failed")
		return
	}
	observability.RecordRoomAction("create_room", request.ProviderID, nil)

	if err := setSignedCookie(w, rooms.HostCookieName, hostSessionID); err != nil {
		writeRequestError(
			w,
			r,
			http.StatusInternalServerError,
			"session_cookie_failed",
			"failed to set session cookie",
			err,
		)
		return
	}

	writeJSON(w, http.StatusCreated, snapshot)
}

// JoinRoom handles POST /api/rooms/{slug}/join.
// @Summary Join an existing room
// @Description Create a participant session for the room and return the room snapshot for the joining guest.
// @Tags rooms
// @Accept json
// @Produce json
// @Param slug path string true "Room slug"
// @Param request body joinRoomRequest true "Join room payload"
// @Success 201 {object} rooms.RoomSnapshot
// @Failure 400 {object} map[string]string
// @Failure 500 {object} map[string]string
// @Router /rooms/{slug}/join [post]
func JoinRoom(w http.ResponseWriter, r *http.Request) {
	if strings.TrimSpace(config.GetRuntimeConfig().AppSecret) == "" {
		writeRequestError(
			w,
			r,
			http.StatusInternalServerError,
			"runtime_unavailable",
			"KILTER_TOGETHER_APP_SECRET is required to join rooms",
			nil,
		)
		return
	}

	roomSlug := chi.URLParam(r, "slug")
	var request joinRoomRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid request body")
		return
	}
	if len(request.DisplayName) > 50 {
		request.DisplayName = request.DisplayName[:50]
	}

	snapshot, participantSessionID, err := rooms.DefaultService.JoinRoom(r.Context(), roomSlug, request.DisplayName)
	if err != nil {
		observability.RecordRoomAction("join_room", "", err)
		writeRoomError(w, r, err, http.StatusBadRequest, "")
		return
	}
	observability.RecordRoomAction("join_room", string(snapshot.ProviderID), nil)

	if err := setSignedCookie(w, rooms.ParticipantCookieName, participantSessionID); err != nil {
		writeRequestError(
			w,
			r,
			http.StatusInternalServerError,
			"session_cookie_failed",
			"failed to set session cookie",
			err,
		)
		return
	}

	writeJSON(w, http.StatusCreated, snapshot)
}

// GetRoom handles GET /api/rooms/{slug}.
// @Summary Get a room snapshot
// @Description Return the current collaborative room snapshot for the authenticated viewer.
// @Tags rooms
// @Produce json
// @Param slug path string true "Room slug"
// @Success 200 {object} rooms.RoomSnapshot
// @Failure 401 {object} map[string]string
// @Failure 400 {object} map[string]string
// @Router /rooms/{slug} [get]
func GetRoom(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, viewerAccessAny)
	if err != nil {
		writeRoomError(w, r, err, http.StatusUnauthorized, "")
		return
	}

	snapshot, err := rooms.DefaultService.GetSnapshot(r.Context(), viewer)
	if err != nil {
		writeRoomError(w, r, err, http.StatusBadRequest, "")
		return
	}

	writeJSON(w, http.StatusOK, snapshot)
}

// UpdateRoom handles PATCH /api/rooms/{slug}.
// @Summary Update room metadata
// @Description Update the room name for the host-managed collaborative room.
// @Tags rooms
// @Accept json
// @Produce json
// @Param slug path string true "Room slug"
// @Param request body updateRoomRequest true "Room update payload"
// @Success 200 {object} rooms.RoomSnapshot
// @Failure 401 {object} map[string]string
// @Failure 400 {object} map[string]string
// @Router /rooms/{slug} [patch]
func UpdateRoom(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, viewerAccessHost)
	if err != nil {
		writeRoomError(w, r, err, http.StatusUnauthorized, "")
		return
	}

	var request updateRoomRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid request body")
		return
	}
	if len(request.RoomName) > 80 {
		request.RoomName = request.RoomName[:80]
	}

	snapshot, err := rooms.DefaultService.UpdateRoomName(r.Context(), viewer, request.RoomName)
	if err != nil {
		writeRoomError(w, r, err, http.StatusBadRequest, "")
		return
	}

	writeJSON(w, http.StatusOK, snapshot)
}

// UpdateRoomFistBumps handles PUT /api/rooms/{slug}/fist-bumps/settings.
// @Summary Update room fist bump settings
// @Description Enable or disable room fist bumps for the host-managed collaborative room.
// @Tags rooms
// @Accept json
// @Produce json
// @Param slug path string true "Room slug"
// @Param request body updateFistBumpsRequest true "Fist bump settings payload"
// @Success 200 {object} rooms.RoomSnapshot
// @Failure 401 {object} map[string]string
// @Failure 400 {object} map[string]string
// @Router /rooms/{slug}/fist-bumps/settings [put]
func UpdateRoomFistBumps(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, viewerAccessHost)
	if err != nil {
		writeRoomError(w, r, err, http.StatusUnauthorized, "")
		return
	}

	var request updateFistBumpsRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	snapshot, err := rooms.DefaultService.SetFistBumpsEnabled(r.Context(), viewer, request.Enabled)
	if err != nil {
		writeRoomError(w, r, err, http.StatusBadRequest, "")
		return
	}

	writeJSON(w, http.StatusOK, snapshot)
}

func StreamRoomEvents(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, viewerAccessAny)
	if err != nil {
		writeRoomError(w, r, err, http.StatusUnauthorized, "")
		return
	}

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache, no-transform")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("X-Accel-Buffering", "no")

	flusher, ok := w.(http.Flusher)
	if !ok {
		writeJSONError(w, http.StatusInternalServerError, "streaming unsupported")
		return
	}

	roomSlug := viewer.Room.Slug
	eventChannel := rooms.DefaultService.Hub().Subscribe(roomSlug)
	defer rooms.DefaultService.Hub().Unsubscribe(roomSlug, eventChannel)

	initialEvent := rooms.EventPayload{
		Type:     "room.connected",
		RoomSlug: roomSlug,
		Version:  viewer.Room.Version,
	}
	if !writeSSEEvent(w, initialEvent) {
		return
	}
	flusher.Flush()

	ticker := time.NewTicker(15 * time.Second)
	defer ticker.Stop()

	ctx := r.Context()
	for {
		select {
		case <-ctx.Done():
			return
		case event, ok := <-eventChannel:
			if !ok {
				return
			}
			if !writeSSEEvent(w, event) {
				return
			}
			flusher.Flush()
		case <-ticker.C:
			if _, err := fmt.Fprintf(w, ": heartbeat\n\n"); err != nil {
				return
			}
			flusher.Flush()
		}
	}
}

// ConnectRoomProvider handles POST /api/rooms/{slug}/provider/connect.
// @Summary Connect or refresh a room provider
// @Description Validate and persist provider credentials for the host-managed collaborative room.
// @Tags rooms
// @Accept json
// @Produce json
// @Param slug path string true "Room slug"
// @Param request body connectProviderRequest true "Provider connect payload"
// @Success 200 {object} providers.ProviderConnectionState
// @Failure 401 {object} map[string]string
// @Failure 400 {object} map[string]string
// @Failure 500 {object} map[string]string
// @Router /rooms/{slug}/provider/connect [post]
func ConnectRoomProvider(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, viewerAccessHost)
	if err != nil {
		writeRoomError(w, r, err, http.StatusUnauthorized, "")
		return
	}

	var request connectProviderRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	state, err := rooms.DefaultService.ConnectProvider(r.Context(), viewer, request.Secret)
	if err != nil {
		observability.RecordRoomAction("connect_provider", viewer.Room.ProviderID, err)
		writeRoomError(w, r, err, connectProviderStatus(err), "provider_auth_failed")
		return
	}
	observability.RecordRoomAction("connect_provider", viewer.Room.ProviderID, nil)

	writeJSON(w, http.StatusOK, state)
}

// SetRoomSurface handles POST /api/rooms/{slug}/surface.
// @Summary Select the shared room surface
// @Description Persist the provider-specific board, gym, or wall selection for the room.
// @Tags rooms
// @Accept json
// @Produce json
// @Param slug path string true "Room slug"
// @Param request body setSurfaceRequest true "Surface selection payload"
// @Success 200 {object} providers.ProviderSurface
// @Failure 401 {object} map[string]string
// @Failure 400 {object} map[string]string
// @Router /rooms/{slug}/surface [post]
func SetRoomSurface(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, viewerAccessManager)
	if err != nil {
		writeRoomError(w, r, err, http.StatusUnauthorized, "")
		return
	}

	var request setSurfaceRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	surface, err := rooms.DefaultService.SetSurface(r.Context(), viewer, request.SurfaceID, request.Context)
	if err != nil {
		observability.RecordRoomAction("set_surface", viewer.Room.ProviderID, err)
		writeRoomError(w, r, err, http.StatusBadRequest, "")
		return
	}
	observability.RecordRoomAction("set_surface", viewer.Room.ProviderID, nil)

	writeJSON(w, http.StatusOK, surface)
}

// ListRoomCatalogSurfaces handles GET /api/rooms/{slug}/catalog/surfaces.
// @Summary List provider surfaces for the room
// @Description Return provider-specific selectable surfaces for the room, optionally filtered by parent id.
// @Tags rooms
// @Produce json
// @Param slug path string true "Room slug"
// @Param parent_id query string false "Parent surface id"
// @Success 200 {object} listSurfacesResponse
// @Failure 401 {object} map[string]string
// @Failure 400 {object} map[string]string
// @Router /rooms/{slug}/catalog/surfaces [get]
func ListRoomCatalogSurfaces(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, viewerAccessAny)
	if err != nil {
		writeRoomError(w, r, err, http.StatusUnauthorized, "")
		return
	}

	surfaces, err := rooms.DefaultService.ListSurfaces(r.Context(), viewer, providers.SurfaceFilter{
		ParentID: strings.TrimSpace(r.URL.Query().Get("parent_id")),
	})
	if err != nil {
		writeRoomError(w, r, err, http.StatusBadRequest, "")
		return
	}

	writeJSON(w, http.StatusOK, map[string]any{"surfaces": surfaces})
}

// ListRoomCatalogClimbs handles GET /api/rooms/{slug}/catalog/climbs.
// @Summary List room catalog climbs
// @Description Return provider climbs for the room surface along with room vote metadata.
// @Tags rooms
// @Produce json
// @Param slug path string true "Room slug"
// @Param q query string false "Search query"
// @Param sort query string false "Sort order"
// @Param cursor query string false "Pagination cursor"
// @Param page_size query int false "Page size"
// @Success 200 {object} rooms.CatalogClimbsResponse
// @Failure 401 {object} map[string]string
// @Failure 400 {object} map[string]string
// @Router /rooms/{slug}/catalog/climbs [get]
func ListRoomCatalogClimbs(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, viewerAccessAny)
	if err != nil {
		writeRoomError(w, r, err, http.StatusUnauthorized, "")
		return
	}

	pageSize := 10
	if rawPageSize := strings.TrimSpace(r.URL.Query().Get("page_size")); rawPageSize != "" {
		if parsedPageSize, err := strconv.Atoi(rawPageSize); err == nil && parsedPageSize > 0 {
			pageSize = parsedPageSize
		}
	}

	search := r.URL.Query().Get("q")
	if len(search) > 200 {
		search = search[:200]
	}

	response, err := rooms.DefaultService.ListCatalogClimbs(
		r.Context(),
		viewer,
		search,
		r.URL.Query().Get("sort"),
		r.URL.Query().Get("cursor"),
		pageSize,
	)
	if err != nil {
		writeRoomError(w, r, err, http.StatusBadRequest, "")
		return
	}

	writeJSON(w, http.StatusOK, response)
}

// GetRoomCatalogClimb handles GET /api/rooms/{slug}/catalog/climbs/{climbId}.
// @Summary Get a room catalog climb
// @Description Return a single provider climb for the room surface along with room vote metadata.
// @Tags rooms
// @Produce json
// @Param slug path string true "Room slug"
// @Param climbId path string true "Provider climb id"
// @Success 200 {object} rooms.CatalogClimbResponse
// @Failure 401 {object} map[string]string
// @Failure 400 {object} map[string]string
// @Router /rooms/{slug}/catalog/climbs/{climbId} [get]
func GetRoomCatalogClimb(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, viewerAccessAny)
	if err != nil {
		writeRoomError(w, r, err, http.StatusUnauthorized, "")
		return
	}

	climbID, err := url.PathUnescape(chi.URLParam(r, "climbId"))
	if err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid climb id")
		return
	}

	response, err := rooms.DefaultService.GetCatalogClimb(
		r.Context(),
		viewer,
		climbID,
	)
	if err != nil {
		writeRoomError(w, r, err, http.StatusBadRequest, "")
		return
	}

	writeJSON(w, http.StatusOK, response)
}

func ToggleRoomVote(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, viewerAccessAny)
	if err != nil {
		writeRoomError(w, r, err, http.StatusUnauthorized, "")
		return
	}

	climbID, err := url.PathUnescape(chi.URLParam(r, "climbId"))
	if err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid climb id")
		return
	}

	if err := rooms.DefaultService.ToggleVote(r.Context(), viewer, climbID); err != nil {
		if errors.Is(err, rooms.ErrFistBumpsOff) || errors.Is(err, rooms.ErrForbidden) {
			writeRoomError(w, r, err, http.StatusForbidden, "")
			return
		}
		writeRoomError(w, r, err, http.StatusBadRequest, "")
		return
	}
	observability.RecordRoomAction("toggle_vote", viewer.Room.ProviderID, nil)

	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func AddRoomQueueEntry(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, viewerAccessAny)
	if err != nil {
		writeRoomError(w, r, err, http.StatusUnauthorized, "")
		return
	}

	var request addQueueEntryRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	if err := rooms.DefaultService.AddQueueEntry(r.Context(), viewer, request.ClimbID); err != nil {
		observability.RecordRoomAction("queue_add", viewer.Room.ProviderID, err)
		writeRoomError(w, r, err, http.StatusBadRequest, "")
		return
	}
	observability.RecordRoomAction("queue_add", viewer.Room.ProviderID, nil)

	writeJSON(w, http.StatusCreated, map[string]string{"status": "ok"})
}

func AddRoomFinalist(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, viewerAccessManager)
	if err != nil {
		writeRoomError(w, r, err, http.StatusUnauthorized, "")
		return
	}

	var request addFinalistRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	if err := rooms.DefaultService.AddFinalist(r.Context(), viewer, request.ClimbID); err != nil {
		writeJSONError(w, http.StatusBadRequest, err.Error())
		return
	}

	writeJSON(w, http.StatusCreated, map[string]string{"status": "ok"})
}

func ReorderRoomQueue(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, viewerAccessManager)
	if err != nil {
		writeRoomError(w, r, err, http.StatusUnauthorized, "")
		return
	}

	var request reorderQueueRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	if err := rooms.DefaultService.ReorderQueue(r.Context(), viewer, request.EntryIDs); err != nil {
		writeJSONError(w, http.StatusBadRequest, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func ReorderRoomFinalists(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, viewerAccessManager)
	if err != nil {
		writeRoomError(w, r, err, http.StatusUnauthorized, "")
		return
	}

	var request reorderFinalistsRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	if err := rooms.DefaultService.ReorderFinalists(r.Context(), viewer, request.EntryIDs); err != nil {
		writeJSONError(w, http.StatusBadRequest, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func UpdateRoomQueueEntry(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, viewerAccessManager)
	if err != nil {
		writeRoomError(w, r, err, http.StatusUnauthorized, "")
		return
	}

	var request updateQueueEntryRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	entryID, err := strconv.ParseUint(chi.URLParam(r, "entryId"), 10, 64)
	if err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid queue entry id")
		return
	}

	if err := rooms.DefaultService.UpdateQueueEntryStatus(r.Context(), viewer, uint(entryID), request.Status); err != nil {
		writeJSONError(w, http.StatusBadRequest, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func DeleteRoomFinalist(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, viewerAccessManager)
	if err != nil {
		writeRoomError(w, r, err, http.StatusUnauthorized, "")
		return
	}

	entryID, err := strconv.ParseUint(chi.URLParam(r, "entryId"), 10, 64)
	if err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid finalist entry id")
		return
	}

	if err := rooms.DefaultService.DeleteFinalist(r.Context(), viewer, uint(entryID)); err != nil {
		writeJSONError(w, http.StatusBadRequest, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func DeleteRoomQueueEntry(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, viewerAccessManager)
	if err != nil {
		writeRoomError(w, r, err, http.StatusUnauthorized, "")
		return
	}

	entryID, err := strconv.ParseUint(chi.URLParam(r, "entryId"), 10, 64)
	if err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid queue entry id")
		return
	}

	if err := rooms.DefaultService.DeleteQueueEntry(r.Context(), viewer, uint(entryID)); err != nil {
		writeJSONError(w, http.StatusBadRequest, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

// PickRandomRoomClimb handles POST /api/rooms/{slug}/pick-random.
// @Summary Pick a random room climb
// @Description Pick a random climb from finalists or top-voted climbs for the room.
// @Tags rooms
// @Accept json
// @Produce json
// @Param slug path string true "Room slug"
// @Param request body pickRandomRequest false "Random pick payload"
// @Success 200 {object} randomPickResponse
// @Failure 401 {object} map[string]string
// @Failure 400 {object} map[string]string
// @Router /rooms/{slug}/pick-random [post]
func PickRandomRoomClimb(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, viewerAccessManager)
	if err != nil {
		writeRoomError(w, r, err, http.StatusUnauthorized, "")
		return
	}

	var request pickRandomRequest
	if r.ContentLength > 0 {
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			writeJSONError(w, http.StatusBadRequest, "invalid request body")
			return
		}
	}

	climb, err := rooms.DefaultService.PickRandom(r.Context(), viewer, request.Source)
	if err != nil {
		writeJSONError(w, http.StatusBadRequest, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, map[string]any{"climb": climb})
}

func PromoteRoomQueueClimb(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, viewerAccessManager)
	if err != nil {
		writeRoomError(w, r, err, http.StatusUnauthorized, "")
		return
	}

	var request promoteQueueRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	if err := rooms.DefaultService.PromoteClimb(r.Context(), viewer, request.ClimbID, request.Status); err != nil {
		writeJSONError(w, http.StatusBadRequest, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func ClearRoomVotes(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, viewerAccessManager)
	if err != nil {
		writeRoomError(w, r, err, http.StatusUnauthorized, "")
		return
	}

	if err := rooms.DefaultService.ClearVotes(r.Context(), viewer); err != nil {
		writeJSONError(w, http.StatusBadRequest, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func UpdateMyParticipantStatus(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, viewerAccessAny)
	if err != nil {
		writeRoomError(w, r, err, http.StatusUnauthorized, "")
		return
	}

	var request participantStatusRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	if err := rooms.DefaultService.UpdateParticipantStatus(r.Context(), viewer, request.Status); err != nil {
		writeJSONError(w, http.StatusBadRequest, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func UpdateRoomParticipantRole(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, viewerAccessHost)
	if err != nil {
		writeRoomError(w, r, err, http.StatusUnauthorized, "")
		return
	}

	var request updateParticipantRoleRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	participantID, err := strconv.ParseUint(chi.URLParam(r, "participantId"), 10, 64)
	if err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid participant id")
		return
	}

	if err := rooms.DefaultService.UpdateParticipantRole(r.Context(), viewer, uint(participantID), request.Role); err != nil {
		writeRoomError(w, r, err, http.StatusBadRequest, "")
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func CloseRoom(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, viewerAccessHost)
	if err != nil {
		writeRoomError(w, r, err, http.StatusUnauthorized, "")
		return
	}

	if err := rooms.DefaultService.CloseRoom(r.Context(), viewer); err != nil {
		observability.RecordRoomAction("close_room", viewer.Room.ProviderID, err)
		writeRoomError(w, r, err, http.StatusBadRequest, "")
		return
	}
	observability.RecordRoomAction("close_room", viewer.Room.ProviderID, nil)

	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func RemoveRoomParticipant(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, viewerAccessHost)
	if err != nil {
		writeRoomError(w, r, err, http.StatusUnauthorized, "")
		return
	}

	participantID, err := strconv.ParseUint(chi.URLParam(r, "participantId"), 10, 64)
	if err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid participant id")
		return
	}

	if err := rooms.DefaultService.RemoveParticipant(r.Context(), viewer, uint(participantID)); err != nil {
		writeJSONError(w, http.StatusBadRequest, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func authenticateViewer(r *http.Request, accessMode viewerAccessMode) (*rooms.Viewer, error) {
	roomSlug := chi.URLParam(r, "slug")
	secret := config.GetRuntimeConfig().AppSecret
	if strings.TrimSpace(secret) == "" {
		return nil, fmt.Errorf("KILTER_TOGETHER_APP_SECRET is required")
	}

	cookieNames := []string{rooms.HostCookieName, rooms.ParticipantCookieName}
	for _, cookieName := range cookieNames {
		cookie, err := r.Cookie(cookieName)
		if err != nil {
			continue
		}
		sessionID, err := security.VerifySignedCookie(secret, cookie.Value)
		if err != nil {
			continue
		}

		viewer, err := rooms.DefaultService.Authenticate(r.Context(), roomSlug, sessionID, "")
		if err == nil {
			switch accessMode {
			case viewerAccessAny:
				return viewer, nil
			case viewerAccessManager:
				if viewer.CanManageSession() {
					return viewer, nil
				}
				return nil, rooms.ErrForbidden
			case viewerAccessHost:
				if viewer.IsHost() {
					return viewer, nil
				}
				return nil, rooms.ErrForbidden
			default:
				return viewer, nil
			}
		}
		if errors.Is(err, rooms.ErrForbidden) {
			return nil, err
		}
		if errors.Is(err, rooms.ErrSessionExpired) ||
			errors.Is(err, rooms.ErrSessionInvalid) ||
			errors.Is(err, rooms.ErrRoomClosed) ||
			errors.Is(err, rooms.ErrRoomNotFound) ||
			errors.Is(err, rooms.ErrForbidden) {
			return nil, err
		}
	}

	return nil, fmt.Errorf("room session is required")
}

func setSignedCookie(w http.ResponseWriter, name string, rawValue string) error {
	signedValue, err := security.SignCookie(config.GetRuntimeConfig().AppSecret, rawValue)
	if err != nil {
		return err
	}

	http.SetCookie(w, &http.Cookie{
		Name:     name,
		Value:    signedValue,
		HttpOnly: true,
		Secure:   config.GetRuntimeConfig().SecureCookies,
		Path:     "/",
		SameSite: http.SameSiteLaxMode,
		Expires:  time.Now().UTC().Add(30 * 24 * time.Hour),
	})
	return nil
}

func connectProviderStatus(err error) int {
	switch {
	case err == nil:
		return http.StatusOK
	case errors.Is(err, rooms.ErrForbidden):
		return http.StatusForbidden
	case strings.Contains(err.Error(), "KILTER_TOGETHER_ENCRYPTION_KEY is required"):
		return http.StatusInternalServerError
	case strings.Contains(strings.ToLower(err.Error()), "too many requests"):
		return http.StatusTooManyRequests
	default:
		return http.StatusBadRequest
	}
}

func writeJSON(w http.ResponseWriter, statusCode int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	_ = json.NewEncoder(w).Encode(payload)
}

func writeSSEEvent(w http.ResponseWriter, payload rooms.EventPayload) bool {
	eventBytes, err := json.Marshal(payload)
	if err != nil {
		return false
	}
	if _, err := fmt.Fprintf(w, "event: room\ndata: %s\n\n", string(eventBytes)); err != nil {
		return false
	}
	return true
}
