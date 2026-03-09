package observability

import (
	"net/http"
	"strconv"
	"sync/atomic"
	"time"

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
	sseSubscribers = promauto.NewGauge(prometheus.GaugeOpts{
		Name: "kilter_together_room_sse_subscribers",
		Help: "Current number of active room SSE subscribers.",
	})
)

var activeSubscribers atomic.Int64

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
	if err != nil {
		status = "error"
	}
	maintenanceRuns.WithLabelValues(job, status).Inc()
}

func RecordProviderCache(provider, outcome string) {
	providerCacheRequests.WithLabelValues(provider, outcome).Inc()
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
