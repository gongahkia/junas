package handlers

import (
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strconv"
	"strings"

	"github.com/lczm/kilter-together/api/observability"
	"github.com/lczm/kilter-together/api/rooms"
)

type apiErrorPayload struct {
	Error     string `json:"error"`
	Status    string `json:"status"`
	Code      string `json:"code,omitempty"`
	RequestID string `json:"request_id,omitempty"`
	TraceID   string `json:"trace_id,omitempty"`
}

func WriteRateLimitError(w http.ResponseWriter, r *http.Request) {
	writeRequestError(
		w,
		r,
		http.StatusTooManyRequests,
		"rate_limited",
		"Too Many Requests",
		nil,
	)
}

func writeJSONError(w http.ResponseWriter, statusCode int, message string) {
	writeErrorPayload(w, statusCode, inferErrorCode(statusCode, message, ""), message, "", "")
}

func writeRoomError(w http.ResponseWriter, r *http.Request, err error, defaultStatus int, defaultCode string) {
	statusCode := defaultStatus
	message := strings.TrimSpace(err.Error())
	if message == "" {
		message = http.StatusText(defaultStatus)
	}

	switch {
	case errors.Is(err, rooms.ErrForbidden):
		statusCode = http.StatusForbidden
	case errors.Is(err, rooms.ErrRoomNotFound):
		statusCode = http.StatusNotFound
	case errors.Is(err, rooms.ErrRoomClosed):
		statusCode = http.StatusGone
	case errors.Is(err, rooms.ErrSessionExpired):
		statusCode = http.StatusUnauthorized
	case errors.Is(err, rooms.ErrSessionInvalid):
		statusCode = http.StatusUnauthorized
	case errors.Is(err, rooms.ErrFistBumpsOff):
		statusCode = http.StatusForbidden
	case errors.Is(err, rooms.ErrProviderNotConnected):
		statusCode = http.StatusConflict
	}

	writeRequestError(
		w,
		r,
		statusCode,
		inferErrorCode(statusCode, message, defaultCode),
		message,
		err,
	)
}

func writeRequestError(
	w http.ResponseWriter,
	r *http.Request,
	statusCode int,
	code string,
	message string,
	cause error,
) {
	requestID := ""
	traceID := ""
	if r != nil {
		requestID = observability.RequestIDFromContext(r.Context())
		traceID = observability.TraceIDFromContext(r.Context())
	}

	if traceID != "" {
		w.Header().Set(observability.TraceIDHeader, traceID)
	}

	writeErrorPayload(w, statusCode, code, message, requestID, traceID)

	if r != nil && statusCode >= http.StatusInternalServerError {
		if cause == nil {
			cause = fmt.Errorf("%s", message)
		}
		observability.CaptureError(r.Context(), cause, map[string]string{
			"status": strconv.Itoa(statusCode),
			"code":   code,
		})
	}
}

func writeErrorPayload(
	w http.ResponseWriter,
	statusCode int,
	code string,
	message string,
	requestID string,
	traceID string,
) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	_ = json.NewEncoder(w).Encode(apiErrorPayload{
		Error:     message,
		Status:    strconv.Itoa(statusCode),
		Code:      code,
		RequestID: requestID,
		TraceID:   traceID,
	})
}

func inferErrorCode(statusCode int, message string, defaultCode string) string {
	normalizedMessage := strings.ToLower(strings.TrimSpace(message))

	switch {
	case normalizedMessage == "":
		if defaultCode != "" {
			return defaultCode
		}
	case strings.Contains(normalizedMessage, "display name is already taken"):
		return "display_name_taken"
	case strings.Contains(normalizedMessage, "display name is required"):
		return "display_name_required"
	case strings.Contains(normalizedMessage, "room session expired"):
		return "session_expired"
	case strings.Contains(normalizedMessage, "invalid room session"):
		return "session_invalid"
	case strings.Contains(normalizedMessage, "room session is required"):
		return "session_required"
	case strings.Contains(normalizedMessage, "room not found"):
		return "room_not_found"
	case strings.Contains(normalizedMessage, "room is closed"):
		return "room_closed"
	case strings.Contains(normalizedMessage, "provider is not connected"):
		return "provider_not_connected"
	case strings.Contains(normalizedMessage, "fist bumps are disabled"):
		return "fist_bumps_disabled"
	case strings.Contains(normalizedMessage, "unsupported provider"):
		return "unsupported_provider"
	case strings.Contains(normalizedMessage, "kilter username and password are required"),
		strings.Contains(normalizedMessage, "crux token is required"),
		strings.Contains(normalizedMessage, "token is required"),
		strings.Contains(normalizedMessage, "invalid request body"),
		strings.Contains(normalizedMessage, "invalid request"):
		return "invalid_request"
	case strings.Contains(normalizedMessage, "app database is not configured"),
		strings.Contains(normalizedMessage, "kilter runtime data is not available"),
		strings.Contains(normalizedMessage, "local kilter data is missing"),
		strings.Contains(normalizedMessage, "bootstrap manifest"),
		strings.Contains(normalizedMessage, "kilter_together_app_secret is required"),
		strings.Contains(normalizedMessage, "kilter_together_encryption_key is required"):
		return "runtime_unavailable"
	case statusCode == http.StatusTooManyRequests:
		return "rate_limited"
	case defaultCode != "":
		return defaultCode
	case statusCode >= http.StatusInternalServerError:
		return "internal_error"
	case statusCode == http.StatusForbidden:
		return "forbidden"
	case statusCode == http.StatusUnauthorized:
		return "unauthorized"
	default:
		return "bad_request"
	}

	return defaultCode
}
