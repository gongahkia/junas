package handlers

import (
	"encoding/json"
	"net/http"
	"strings"

	"github.com/go-chi/chi/v5"
	"github.com/lczm/kilter-together/api/providers"
	"github.com/lczm/kilter-together/api/rooms"
)

type analyticsEventRequest struct {
	RoomSlug   string         `json:"room_slug"`
	EventName  string         `json:"event_name"`
	Source     string         `json:"source"`
	ViewerRole string         `json:"viewer_role"`
	Route      string         `json:"route"`
	Properties map[string]any `json:"properties"`
}

type feedbackRequest struct {
	RoomSlug     string         `json:"room_slug"`
	ShareID      string         `json:"share_id"`
	PromptFamily string         `json:"prompt_family"`
	Sentiment    string         `json:"sentiment"`
	Message      string         `json:"message"`
	Route        string         `json:"route"`
	Metadata     map[string]any `json:"metadata"`
}

type createSoloPlanRequest struct {
	ProviderID string                    `json:"provider_id"`
	Title      string                    `json:"title"`
	Notes      string                    `json:"notes"`
	Surface    providers.ProviderSurface `json:"surface"`
	Context    map[string]string         `json:"context"`
	Filters    map[string]string         `json:"filters"`
	Climbs     []providers.ProviderClimb `json:"climbs"`
	OpenPath   string                    `json:"open_path"`
	CreatedBy  string                    `json:"created_by"`
}

func RecordAnalyticsEvent(w http.ResponseWriter, r *http.Request) {
	var request analyticsEventRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	if err := rooms.DefaultService.RecordAnalyticsEvent(r.Context(), rooms.AnalyticsEventInput{
		RoomSlug:   request.RoomSlug,
		EventName:  request.EventName,
		Source:     request.Source,
		ViewerRole: request.ViewerRole,
		Route:      request.Route,
		Properties: request.Properties,
	}); err != nil {
		writeRequestError(w, r, http.StatusBadRequest, "invalid_request", err.Error(), err)
		return
	}

	writeJSON(w, http.StatusAccepted, map[string]string{"status": "accepted"})
}

func SubmitFeedback(w http.ResponseWriter, r *http.Request) {
	var request feedbackRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	if err := rooms.DefaultService.SubmitFeedback(r.Context(), rooms.FeedbackInput{
		RoomSlug:     request.RoomSlug,
		ShareID:      request.ShareID,
		PromptFamily: request.PromptFamily,
		Sentiment:    request.Sentiment,
		Message:      request.Message,
		Route:        request.Route,
		Metadata:     request.Metadata,
	}); err != nil {
		writeRequestError(w, r, http.StatusBadRequest, "invalid_request", err.Error(), err)
		return
	}

	writeJSON(w, http.StatusCreated, map[string]string{"status": "ok"})
}

func GetRoomRecap(w http.ResponseWriter, r *http.Request) {
	recap, err := rooms.DefaultService.GetRecapByShareID(r.Context(), chi.URLParam(r, "shareId"))
	if err != nil {
		writeRoomError(w, r, err, http.StatusNotFound, "")
		return
	}

	writeJSON(w, http.StatusOK, recap)
}

func CreateSoloPlan(w http.ResponseWriter, r *http.Request) {
	var request createSoloPlanRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	plan, err := rooms.DefaultService.CreateSoloPlanSnapshot(r.Context(), rooms.SoloPlanCreateInput{
		ProviderID: providers.ProviderID(strings.ToLower(strings.TrimSpace(request.ProviderID))),
		Title:      request.Title,
		Notes:      request.Notes,
		Surface:    request.Surface,
		Context:    request.Context,
		Filters:    request.Filters,
		Climbs:     request.Climbs,
		OpenPath:   request.OpenPath,
		CreatedBy:  request.CreatedBy,
	})
	if err != nil {
		writeRequestError(w, r, http.StatusBadRequest, "invalid_request", err.Error(), err)
		return
	}

	writeJSON(w, http.StatusCreated, plan)
}

func GetSoloPlan(w http.ResponseWriter, r *http.Request) {
	plan, err := rooms.DefaultService.GetSoloPlanByShareID(r.Context(), chi.URLParam(r, "shareId"))
	if err != nil {
		writeRoomError(w, r, err, http.StatusNotFound, "")
		return
	}

	writeJSON(w, http.StatusOK, plan)
}
