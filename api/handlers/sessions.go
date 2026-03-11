package handlers

import (
	"net/http"
	"strconv"

	"github.com/lczm/kilter-together/api/rooms"
)

type recentSessionsResponse struct {
	Sessions []rooms.SessionSummaryView `json:"sessions"`
}

// ListRecentSessions handles GET /api/sessions/recent.
// @Summary List recent closed room sessions
// @Description Return recent closed-room summaries for the landing page and operator review.
// @Tags sessions
// @Produce json
// @Param limit query int false "Number of sessions to return"
// @Success 200 {object} recentSessionsResponse
// @Failure 400 {object} map[string]string
// @Failure 500 {object} map[string]string
// @Router /sessions/recent [get]
func ListRecentSessions(w http.ResponseWriter, r *http.Request) {
	limit := 6
	if rawLimit := r.URL.Query().Get("limit"); rawLimit != "" {
		parsedLimit, err := strconv.Atoi(rawLimit)
		if err != nil || parsedLimit <= 0 {
			writeJSONError(w, http.StatusBadRequest, "invalid recent sessions limit")
			return
		}
		limit = parsedLimit
	}

	sessions, err := rooms.DefaultService.ListRecentSessionSummaries(r.Context(), limit)
	if err != nil {
		writeRequestError(
			w,
			r,
			http.StatusInternalServerError,
			"internal_error",
			"failed to load recent sessions",
			err,
		)
		return
	}

	writeJSON(w, http.StatusOK, recentSessionsResponse{Sessions: sessions})
}
