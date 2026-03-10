package handlers

import (
	"crypto/subtle"
	"net/http"
	"strings"
	"time"

	"github.com/lczm/kilter-together/api/bootstrap"
	"github.com/lczm/kilter-together/api/config"
	"github.com/lczm/kilter-together/api/observability"
	"github.com/lczm/kilter-together/api/providers"
)

type providerCacheStatus struct {
	Entries          int64      `json:"entries"`
	LatestExpiration *time.Time `json:"latest_expiration,omitempty"`
}

type databaseStatus struct {
	Configured bool   `json:"configured"`
	Path       string `json:"path"`
	Error      string `json:"error,omitempty"`
}

type operatorStatusResponse struct {
	Status        string              `json:"status"`
	GeneratedAt   time.Time           `json:"generated_at"`
	RuntimeData   databaseStatus      `json:"runtime_data"`
	AppDB         databaseStatus      `json:"app_db"`
	KilterDB      databaseStatus      `json:"kilter_db"`
	ProviderCache providerCacheStatus `json:"provider_cache"`
	Observability struct {
		ActiveSSESubscribers int64                             `json:"active_sse_subscribers"`
		TraceExportEnabled   bool                              `json:"trace_export_enabled"`
		ErrorReporting       bool                              `json:"error_reporting_enabled"`
		Maintenance          []observability.MaintenanceStatus `json:"maintenance"`
	} `json:"observability"`
	SupportedProviders []providers.Capability `json:"supported_providers"`
}

func ProviderCapabilities(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"providers": providers.SupportedCapabilities(),
	})
}

func OperatorStatus(w http.ResponseWriter, r *http.Request) {
	runtimeConfig := config.GetRuntimeConfig()
	if strings.TrimSpace(runtimeConfig.OperatorToken) == "" {
		http.NotFound(w, r)
		return
	}
	if !operatorAuthorized(r, runtimeConfig.OperatorToken) {
		writeRequestError(
			w,
			r,
			http.StatusUnauthorized,
			"operator_auth_required",
			"Operator token is required",
			nil,
		)
		return
	}

	response := operatorStatusResponse{
		Status:             "ok",
		GeneratedAt:        time.Now().UTC(),
		SupportedProviders: providers.SupportedCapabilities(),
	}

	response.AppDB = databaseStatus{
		Configured: config.AppDB != nil,
		Path:       runtimeConfig.AppDBPath,
	}
	if config.AppDB == nil {
		response.Status = "degraded"
		response.AppDB.Error = "app database is not configured"
	}

	response.KilterDB = databaseStatus{
		Configured: config.KilterDB != nil || runtimeConfig.EnableTestProvider,
		Path:       runtimeConfig.DBPath,
	}
	if config.KilterDB == nil && !runtimeConfig.EnableTestProvider {
		response.Status = "degraded"
		response.KilterDB.Error = "kilter runtime database is not configured"
	}

	response.RuntimeData = databaseStatus{
		Configured: true,
		Path:       runtimeConfig.StatePath,
	}
	if !runtimeConfig.EnableTestProvider {
		if err := bootstrap.RuntimeReady(runtimeConfig.DBPath, runtimeConfig.ImageDir, runtimeConfig.StatePath); err != nil {
			response.Status = "degraded"
			response.RuntimeData.Configured = false
			response.RuntimeData.Error = err.Error()
		}
	}

	response.ProviderCache = lookupProviderCacheStatus()
	response.Observability.ActiveSSESubscribers = observability.ActiveSSESubscribers()
	response.Observability.TraceExportEnabled = strings.TrimSpace(runtimeConfig.OTLPTracesEndpoint) != ""
	response.Observability.ErrorReporting = strings.TrimSpace(runtimeConfig.SentryDSN) != ""
	response.Observability.Maintenance = observability.MaintenanceSnapshot()

	writeJSON(w, http.StatusOK, response)
}

func operatorAuthorized(r *http.Request, expectedToken string) bool {
	candidate := strings.TrimSpace(r.Header.Get("X-Operator-Token"))
	if candidate == "" {
		authorizationHeader := strings.TrimSpace(r.Header.Get("Authorization"))
		if strings.HasPrefix(strings.ToLower(authorizationHeader), "bearer ") {
			candidate = strings.TrimSpace(authorizationHeader[len("Bearer "):])
		}
	}
	if candidate == "" {
		return false
	}

	return subtle.ConstantTimeCompare([]byte(candidate), []byte(expectedToken)) == 1
}

func lookupProviderCacheStatus() providerCacheStatus {
	if config.AppDB == nil {
		return providerCacheStatus{}
	}

	status := providerCacheStatus{}
	_ = config.AppDB.Model(&providers.ProviderCacheEntry{}).Count(&status.Entries).Error
	var latestExpiration time.Time
	if err := config.AppDB.Model(&providers.ProviderCacheEntry{}).
		Select("MAX(expires_at)").
		Scan(&latestExpiration).Error; err == nil && !latestExpiration.IsZero() {
		status.LatestExpiration = &latestExpiration
	}

	return status
}
