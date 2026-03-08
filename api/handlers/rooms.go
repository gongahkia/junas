package handlers

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/lczm/kilter-together/api/config"
	"github.com/lczm/kilter-together/api/providers"
	"github.com/lczm/kilter-together/api/rooms"
	"github.com/lczm/kilter-together/api/security"
)

type createRoomRequest struct {
	ProviderID  string `json:"provider_id"`
	DisplayName string `json:"display_name"`
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

func CreateRoom(w http.ResponseWriter, r *http.Request) {
	if strings.TrimSpace(config.GetRuntimeConfig().AppSecret) == "" {
		writeJSONError(w, http.StatusInternalServerError, "KILTER_TOGETHER_APP_SECRET is required to create rooms")
		return
	}

	var request createRoomRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	snapshot, hostSessionID, err := rooms.DefaultService.CreateRoom(
		r.Context(),
		providers.ProviderID(strings.ToLower(strings.TrimSpace(request.ProviderID))),
		request.DisplayName,
	)
	if err != nil {
		writeJSONError(w, http.StatusBadRequest, err.Error())
		return
	}

	if err := setSignedCookie(w, rooms.HostCookieName, hostSessionID); err != nil {
		writeJSONError(w, http.StatusInternalServerError, err.Error())
		return
	}

	writeJSON(w, http.StatusCreated, snapshot)
}

func JoinRoom(w http.ResponseWriter, r *http.Request) {
	if strings.TrimSpace(config.GetRuntimeConfig().AppSecret) == "" {
		writeJSONError(w, http.StatusInternalServerError, "KILTER_TOGETHER_APP_SECRET is required to join rooms")
		return
	}

	roomSlug := chi.URLParam(r, "slug")
	var request joinRoomRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	snapshot, participantSessionID, err := rooms.DefaultService.JoinRoom(r.Context(), roomSlug, request.DisplayName)
	if err != nil {
		writeJSONError(w, http.StatusBadRequest, err.Error())
		return
	}

	if err := setSignedCookie(w, rooms.ParticipantCookieName, participantSessionID); err != nil {
		writeJSONError(w, http.StatusInternalServerError, err.Error())
		return
	}

	writeJSON(w, http.StatusCreated, snapshot)
}

func GetRoom(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, false)
	if err != nil {
		writeJSONError(w, http.StatusUnauthorized, err.Error())
		return
	}

	snapshot, err := rooms.DefaultService.GetSnapshot(r.Context(), viewer)
	if err != nil {
		writeJSONError(w, http.StatusBadRequest, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, snapshot)
}

func StreamRoomEvents(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, false)
	if err != nil {
		writeJSONError(w, http.StatusUnauthorized, err.Error())
		return
	}

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")

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
	writeSSEEvent(w, initialEvent)
	flusher.Flush()

	ctx := r.Context()
	for {
		select {
		case <-ctx.Done():
			return
		case event := <-eventChannel:
			writeSSEEvent(w, event)
			flusher.Flush()
		}
	}
}

func ConnectRoomProvider(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, true)
	if err != nil {
		writeJSONError(w, http.StatusUnauthorized, err.Error())
		return
	}

	var request connectProviderRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	state, err := rooms.DefaultService.ConnectProvider(r.Context(), viewer, request.Secret)
	if err != nil {
		writeJSONError(w, http.StatusBadRequest, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, state)
}

func SetRoomSurface(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, true)
	if err != nil {
		writeJSONError(w, http.StatusUnauthorized, err.Error())
		return
	}

	var request setSurfaceRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	surface, err := rooms.DefaultService.SetSurface(r.Context(), viewer, request.SurfaceID, request.Context)
	if err != nil {
		writeJSONError(w, http.StatusBadRequest, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, surface)
}

func ListRoomCatalogSurfaces(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, false)
	if err != nil {
		writeJSONError(w, http.StatusUnauthorized, err.Error())
		return
	}

	surfaces, err := rooms.DefaultService.ListSurfaces(r.Context(), viewer, providers.SurfaceFilter{
		ParentID: strings.TrimSpace(r.URL.Query().Get("parent_id")),
	})
	if err != nil {
		writeJSONError(w, http.StatusBadRequest, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, map[string]any{"surfaces": surfaces})
}

func ListRoomCatalogClimbs(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, false)
	if err != nil {
		writeJSONError(w, http.StatusUnauthorized, err.Error())
		return
	}

	pageSize := 10
	if rawPageSize := strings.TrimSpace(r.URL.Query().Get("page_size")); rawPageSize != "" {
		if parsedPageSize, err := strconv.Atoi(rawPageSize); err == nil && parsedPageSize > 0 {
			pageSize = parsedPageSize
		}
	}

	response, err := rooms.DefaultService.ListCatalogClimbs(
		r.Context(),
		viewer,
		r.URL.Query().Get("q"),
		r.URL.Query().Get("sort"),
		r.URL.Query().Get("cursor"),
		pageSize,
	)
	if err != nil {
		writeJSONError(w, http.StatusBadRequest, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, response)
}

func GetRoomCatalogClimb(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, false)
	if err != nil {
		writeJSONError(w, http.StatusUnauthorized, err.Error())
		return
	}

	response, err := rooms.DefaultService.GetCatalogClimb(
		r.Context(),
		viewer,
		chi.URLParam(r, "climbId"),
	)
	if err != nil {
		writeJSONError(w, http.StatusBadRequest, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, response)
}

func ToggleRoomVote(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, false)
	if err != nil {
		writeJSONError(w, http.StatusUnauthorized, err.Error())
		return
	}

	if err := rooms.DefaultService.ToggleVote(r.Context(), viewer, chi.URLParam(r, "climbId")); err != nil {
		writeJSONError(w, http.StatusBadRequest, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func AddRoomQueueEntry(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, false)
	if err != nil {
		writeJSONError(w, http.StatusUnauthorized, err.Error())
		return
	}

	var request addQueueEntryRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	if err := rooms.DefaultService.AddQueueEntry(r.Context(), viewer, request.ClimbID); err != nil {
		writeJSONError(w, http.StatusBadRequest, err.Error())
		return
	}

	writeJSON(w, http.StatusCreated, map[string]string{"status": "ok"})
}

func AddRoomFinalist(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, true)
	if err != nil {
		writeJSONError(w, http.StatusUnauthorized, err.Error())
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
	viewer, err := authenticateViewer(r, true)
	if err != nil {
		writeJSONError(w, http.StatusUnauthorized, err.Error())
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
	viewer, err := authenticateViewer(r, true)
	if err != nil {
		writeJSONError(w, http.StatusUnauthorized, err.Error())
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
	viewer, err := authenticateViewer(r, true)
	if err != nil {
		writeJSONError(w, http.StatusUnauthorized, err.Error())
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
	viewer, err := authenticateViewer(r, true)
	if err != nil {
		writeJSONError(w, http.StatusUnauthorized, err.Error())
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
	viewer, err := authenticateViewer(r, true)
	if err != nil {
		writeJSONError(w, http.StatusUnauthorized, err.Error())
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

func PickRandomRoomClimb(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, true)
	if err != nil {
		writeJSONError(w, http.StatusUnauthorized, err.Error())
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
	viewer, err := authenticateViewer(r, true)
	if err != nil {
		writeJSONError(w, http.StatusUnauthorized, err.Error())
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
	viewer, err := authenticateViewer(r, true)
	if err != nil {
		writeJSONError(w, http.StatusUnauthorized, err.Error())
		return
	}

	if err := rooms.DefaultService.ClearVotes(r.Context(), viewer); err != nil {
		writeJSONError(w, http.StatusBadRequest, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func UpdateMyParticipantStatus(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, false)
	if err != nil {
		writeJSONError(w, http.StatusUnauthorized, err.Error())
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

func CloseRoom(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, true)
	if err != nil {
		writeJSONError(w, http.StatusUnauthorized, err.Error())
		return
	}

	if err := rooms.DefaultService.CloseRoom(r.Context(), viewer); err != nil {
		writeJSONError(w, http.StatusBadRequest, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func RemoveRoomParticipant(w http.ResponseWriter, r *http.Request) {
	viewer, err := authenticateViewer(r, true)
	if err != nil {
		writeJSONError(w, http.StatusUnauthorized, err.Error())
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

func authenticateViewer(r *http.Request, requireHost bool) (*rooms.Viewer, error) {
	roomSlug := chi.URLParam(r, "slug")
	secret := config.GetRuntimeConfig().AppSecret
	if strings.TrimSpace(secret) == "" {
		return nil, fmt.Errorf("KILTER_TOGETHER_APP_SECRET is required")
	}

	cookieNames := []string{rooms.HostCookieName, rooms.ParticipantCookieName}
	if requireHost {
		cookieNames = []string{rooms.HostCookieName}
	}

	for _, cookieName := range cookieNames {
		cookie, err := r.Cookie(cookieName)
		if err != nil {
			continue
		}
		sessionID, err := security.VerifySignedCookie(secret, cookie.Value)
		if err != nil {
			continue
		}
		requiredRole := ""
		if requireHost {
			requiredRole = "host"
		}
		viewer, err := rooms.DefaultService.Authenticate(r.Context(), roomSlug, sessionID, requiredRole)
		if err == nil {
			return viewer, nil
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
		Path:     "/",
		SameSite: http.SameSiteLaxMode,
		Expires:  time.Now().UTC().Add(30 * 24 * time.Hour),
	})
	return nil
}

func writeJSON(w http.ResponseWriter, statusCode int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	_ = json.NewEncoder(w).Encode(payload)
}

func writeSSEEvent(w http.ResponseWriter, payload rooms.EventPayload) {
	eventBytes, _ := json.Marshal(payload)
	_, _ = fmt.Fprintf(w, "event: room\n")
	_, _ = fmt.Fprintf(w, "data: %s\n\n", string(eventBytes))
}

func requestContext(r *http.Request) context.Context {
	return r.Context()
}
