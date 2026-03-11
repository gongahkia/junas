package observability

import (
	"net/http"
	"strconv"
	"sync"
	"sync/atomic"
	"time"

	"github.com/lczm/kilter-together/api/bootstrap"
	"github.com/lczm/kilter-together/api/config"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
	httpRequests = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "kilter_together_http_requests_total",
		Help: "Total HTTP requests served by route, method, and status.",
	}, []string{"method", "route", "status"})
	httpLatency = promauto.NewHistogramVec(prometheus.HistogramOpts{
		Name:    "kilter_together_http_request_duration_seconds",
		Help:    "HTTP request latency by route and method.",
		Buckets: prometheus.DefBuckets,
	}, []string{"method", "route"})
	roomEvents = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "kilter_together_room_events_total",
		Help: "Room events broadcast to subscribers.",
	}, []string{"type"})
	maintenanceRuns = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "kilter_together_maintenance_runs_total",
		Help: "Maintenance job executions by job and status.",
	}, []string{"job", "status"})
	providerCacheRequests = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "kilter_together_provider_cache_requests_total",
		Help: "Provider cache activity by provider and outcome.",
	}, []string{"provider", "outcome"})
	roomActions = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "kilter_together_room_actions_total",
		Help: "Room create/join/provider/catalog actions by provider and outcome.",
	}, []string{"action", "provider", "outcome"})
	sseSubscribers = promauto.NewGauge(prometheus.GaugeOpts{
		Name: "kilter_together_room_sse_subscribers",
		Help: "Current number of active room SSE subscribers.",
	})
	runtimeReady = promauto.NewGaugeFunc(prometheus.GaugeOpts{
		Name: "kilter_together_runtime_ready",
		Help: "Whether runtime storage, databases, and provider prerequisites are currently ready.",
	}, func() float64 {
		runtimeConfig := config.GetRuntimeConfig()
		if config.AppDB == nil {
			return 0
		}
		if runtimeConfig.EnableTestProvider {
			return 1
		}
		if err := bootstrap.RuntimeReady(
			runtimeConfig.DBPath,
			runtimeConfig.ImageDir,
			runtimeConfig.StatePath,
		); err != nil {
			return 0
		}
		return 1
	})
)

var activeSubscribers atomic.Int64

type MaintenanceStatus struct {
	Job       string    `json:"job"`
	Status    string    `json:"status"`
	LastRunAt time.Time `json:"last_run_at"`
	LastError string    `json:"last_error,omitempty"`
}

var (
	maintenanceMu     sync.RWMutex
	maintenanceStatus = map[string]MaintenanceStatus{}
)

func Handler() http.Handler {
	return promhttp.Handler()
}

func ObserveHTTPRequest(method, route string, status int, duration time.Duration) {
	httpRequests.WithLabelValues(method, route, strconv.Itoa(status)).Inc()
	httpLatency.WithLabelValues(method, route).Observe(duration.Seconds())
}

func RecordRoomEvent(eventType string) {
	roomEvents.WithLabelValues(eventType).Inc()
}

func RecordMaintenanceRun(job string, err error) {
	status := "success"
	lastError := ""
	if err != nil {
		status = "error"
		lastError = err.Error()
	}
	maintenanceRuns.WithLabelValues(job, status).Inc()

	maintenanceMu.Lock()
	maintenanceStatus[job] = MaintenanceStatus{
		Job:       job,
		Status:    status,
		LastRunAt: time.Now().UTC(),
		LastError: lastError,
	}
	maintenanceMu.Unlock()
}

func RecordProviderCache(provider, outcome string) {
	providerCacheRequests.WithLabelValues(provider, outcome).Inc()
}

func RecordRoomAction(action, provider string, err error) {
	outcome := "success"
	if err != nil {
		outcome = "error"
	}
	roomActions.WithLabelValues(action, provider, outcome).Inc()
}

func SSESubscribed() {
	sseSubscribers.Set(float64(activeSubscribers.Add(1)))
}

func SSEUnsubscribed() {
	next := activeSubscribers.Add(-1)
	if next < 0 {
		activeSubscribers.Store(0)
		next = 0
	}
	sseSubscribers.Set(float64(next))
}

func ActiveSSESubscribers() int64 {
	return activeSubscribers.Load()
}

func MaintenanceSnapshot() []MaintenanceStatus {
	maintenanceMu.RLock()
	defer maintenanceMu.RUnlock()

	snapshot := make([]MaintenanceStatus, 0, len(maintenanceStatus))
	for _, status := range maintenanceStatus {
		snapshot = append(snapshot, status)
	}

	return snapshot
}
