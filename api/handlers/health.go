package handlers

import (
	"net/http"

	"github.com/lczm/kilter-together/api/observability"
)

var metricsHandler = observability.Handler()

func metricsUnavailable() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		writeJSONError(w, http.StatusServiceUnavailable, "metrics are unavailable")
	})
}
