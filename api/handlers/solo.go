package handlers

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strings"

	"github.com/go-chi/chi/v5"
	"github.com/lczm/kilter-together/api/observability"
	"github.com/lczm/kilter-together/api/providers"
)

type soloListSurfacesRequest struct {
	Secret   map[string]string `json:"secret"`
	ParentID string            `json:"parent_id"`
}

type soloListClimbsRequest struct {
	Secret    map[string]string `json:"secret"`
	SurfaceID string            `json:"surface_id"`
	Context   map[string]string `json:"context"`
	Query     string            `json:"q"`
	Sort      string            `json:"sort"`
	Cursor    string            `json:"cursor"`
	PageSize  int               `json:"page_size"`
}

type soloGetClimbRequest struct {
	Secret    map[string]string `json:"secret"`
	SurfaceID string            `json:"surface_id"`
	Context   map[string]string `json:"context"`
}

func ListSoloProviderSurfaces(w http.ResponseWriter, r *http.Request) {
	providerID, provider, err := loadSoloProvider(r)
	if err != nil {
		writeRequestError(w, r, http.StatusBadRequest, "unsupported_provider", err.Error(), err)
		return
	}

	var request soloListSurfacesRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	surfaces, err := provider.ListSurfaces(r.Context(), request.Secret, providers.SurfaceFilter{
		ParentID: strings.TrimSpace(request.ParentID),
	})
	if err != nil {
		observability.RecordSoloAction("list_surfaces", string(providerID), err)
		statusCode := soloProviderErrorStatus(err)
		writeRequestError(
			w,
			r,
			statusCode,
			inferErrorCode(statusCode, err.Error(), "provider_auth_failed"),
			err.Error(),
			err,
		)
		return
	}
	observability.RecordSoloAction("list_surfaces", string(providerID), nil)

	writeJSON(w, http.StatusOK, map[string]any{"surfaces": surfaces})
}

func ListSoloProviderClimbs(w http.ResponseWriter, r *http.Request) {
	providerID, provider, err := loadSoloProvider(r)
	if err != nil {
		writeRequestError(w, r, http.StatusBadRequest, "unsupported_provider", err.Error(), err)
		return
	}

	var request soloListClimbsRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	pageSize := request.PageSize
	if pageSize <= 0 {
		pageSize = 10
	}
	query := strings.TrimSpace(request.Query)
	if len(query) > 200 {
		query = query[:200]
	}

	response, err := provider.ListClimbs(r.Context(), request.Secret, providers.ListClimbsInput{
		SurfaceID: strings.TrimSpace(request.SurfaceID),
		Context:   request.Context,
		Search:    query,
		Sort:      strings.TrimSpace(request.Sort),
		Cursor:    strings.TrimSpace(request.Cursor),
		PageSize:  pageSize,
	})
	if err != nil {
		observability.RecordSoloAction("list_climbs", string(providerID), err)
		statusCode := soloProviderErrorStatus(err)
		writeRequestError(
			w,
			r,
			statusCode,
			inferErrorCode(statusCode, err.Error(), "provider_auth_failed"),
			err.Error(),
			err,
		)
		return
	}
	observability.RecordSoloAction("list_climbs", string(providerID), nil)

	writeJSON(w, http.StatusOK, response)
}

func GetSoloProviderClimb(w http.ResponseWriter, r *http.Request) {
	providerID, provider, err := loadSoloProvider(r)
	if err != nil {
		writeRequestError(w, r, http.StatusBadRequest, "unsupported_provider", err.Error(), err)
		return
	}

	var request soloGetClimbRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	climbID, err := url.PathUnescape(chi.URLParam(r, "climbId"))
	if err != nil {
		writeJSONError(w, http.StatusBadRequest, "invalid climb id")
		return
	}

	climb, err := provider.GetClimb(r.Context(), request.Secret, providers.ListClimbsInput{
		SurfaceID: strings.TrimSpace(request.SurfaceID),
		Context:   request.Context,
	}, climbID)
	if err != nil {
		observability.RecordSoloAction("get_climb", string(providerID), err)
		statusCode := soloProviderErrorStatus(err)
		writeRequestError(
			w,
			r,
			statusCode,
			inferErrorCode(statusCode, err.Error(), "provider_auth_failed"),
			err.Error(),
			err,
		)
		return
	}
	observability.RecordSoloAction("get_climb", string(providerID), nil)

	writeJSON(w, http.StatusOK, map[string]any{"climb": climb})
}

func loadSoloProvider(r *http.Request) (providers.ProviderID, providers.Provider, error) {
	providerID := providers.ProviderID(strings.ToLower(strings.TrimSpace(chi.URLParam(r, "providerId"))))
	capability, ok := providers.CapabilityForProvider(providerID)
	if !ok || !capability.SoloSupported {
		return "", nil, fmt.Errorf("unsupported provider %q", providerID)
	}

	provider, err := providers.Get(providerID)
	if err != nil {
		return "", nil, err
	}

	return providerID, provider, nil
}

func soloProviderErrorStatus(err error) int {
	switch {
	case err == nil:
		return http.StatusOK
	case strings.Contains(strings.ToLower(err.Error()), "not found"):
		return http.StatusNotFound
	case strings.Contains(strings.ToLower(err.Error()), "too many requests"):
		return http.StatusTooManyRequests
	default:
		return connectProviderStatus(err)
	}
}
