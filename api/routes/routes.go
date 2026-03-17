package routes

import (
	"log/slog"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/go-chi/cors"
	"github.com/go-chi/httprate"
	"github.com/lczm/kilter-together/api/config"
	"github.com/lczm/kilter-together/api/handlers"
	"github.com/lczm/kilter-together/api/observability"
	httpSwagger "github.com/swaggo/http-swagger"
)

// SetupRoutes configures all the routes for the application
func SetupRoutes() *chi.Mux {
	r := chi.NewRouter()
	runtimeConfig := config.GetRuntimeConfig()

	// middleware stack
	r.Use(middleware.Recoverer)
	r.Use(middleware.RequestID)
	r.Use(middleware.RealIP)
	r.Use(cors.Handler(cors.Options{
		AllowedOrigins:   config.GetRuntimeConfig().CORSAllowedOrigins(),
		AllowedMethods:   []string{"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"},
		AllowedHeaders:   []string{"Accept", "Content-Type", "Authorization"},
		AllowCredentials: true,
		MaxAge:           300,
	}))
	r.Use(structuredLogger)
	if !runtimeConfig.EnableTestProvider {
		r.Use(limitByIP(100, time.Minute))
	}

	// Define routes
	r.Route("/api", func(r chi.Router) {
		r.Get("/healthz", handlers.Healthz)
		r.Get("/livez", handlers.Livez)
		r.Get("/readyz", handlers.Readyz)
		r.Get("/runtime/status", handlers.GetRuntimeStatus)
		r.Get("/providers/capabilities", handlers.ProviderCapabilities)
		r.Get("/sessions/recent", handlers.ListRecentSessions)
		r.Post("/feedback", handlers.SubmitFeedback)
		r.Get("/recaps/{shareId}", handlers.GetRoomRecap)
		r.Post("/solo/plans", handlers.CreateSoloPlan)
		r.Get("/solo/plans/{shareId}", handlers.GetSoloPlan)
		r.Get("/climbs", handlers.GetClimbs)
		r.Get("/boards", handlers.GetBoardOptions)
		r.Get("/images/{filename}", handlers.ServeImage)
		r.Route("/catalog/kilter", func(r chi.Router) {
			r.Get("/manifest", handlers.GetKilterCatalogManifest)
			r.Get("/bootstrap", handlers.GetKilterCatalogBootstrap)
			r.Get("/delta", handlers.GetKilterCatalogDelta)
		})
		r.Route("/solo/providers/{providerId}", func(r chi.Router) {
			r.Post("/surfaces", handlers.ListSoloProviderSurfaces)
			r.Post("/climbs", handlers.ListSoloProviderClimbs)
			r.Post("/climbs/{climbId}", handlers.GetSoloProviderClimb)
		})
		if runtimeConfig.EnableTestProvider {
			r.Post("/rooms", handlers.CreateRoom)
		} else {
			r.With(limitByIP(10, time.Minute)).Post("/rooms", handlers.CreateRoom)
		}
		r.Route("/rooms/{slug}", func(r chi.Router) {
			r.Post("/join", handlers.JoinRoom)
			r.Get("/", handlers.GetRoom)
			r.Patch("/", handlers.UpdateRoom)
			r.Post("/events/ticket", handlers.CreateSSETicket)
			r.Get("/events", handlers.StreamRoomEvents)
			r.Post("/session/refresh", handlers.RefreshRoomSession)
			if runtimeConfig.EnableTestProvider {
				r.Post("/provider/connect", handlers.ConnectRoomProvider)
			} else {
				r.With(limitByIP(5, time.Minute)).Post("/provider/connect", handlers.ConnectRoomProvider)
			}
			r.Post("/surface", handlers.SetRoomSurface)
			r.Get("/catalog/surfaces", handlers.ListRoomCatalogSurfaces)
			r.Get("/catalog/climbs", handlers.ListRoomCatalogClimbs)
			r.Get("/catalog/climbs/{climbId}", handlers.GetRoomCatalogClimb)
			r.Put("/fist-bumps/settings", handlers.UpdateRoomFistBumps)
			r.Put("/assistant/settings", handlers.UpdateRoomAssistantSettings)
			r.Put("/votes/{climbId}", handlers.ToggleRoomVote)
			r.Put("/participants/me/status", handlers.UpdateMyParticipantStatus)
			r.Post("/finalists", handlers.AddRoomFinalist)
			r.Patch("/finalists/reorder", handlers.ReorderRoomFinalists)
			r.Delete("/finalists/{entryId}", handlers.DeleteRoomFinalist)
			r.Post("/queue", handlers.AddRoomQueueEntry)
			r.Post("/queue/promote", handlers.PromoteRoomQueueClimb)
			r.Patch("/queue/reorder", handlers.ReorderRoomQueue)
			r.Patch("/queue/{entryId}", handlers.UpdateRoomQueueEntry)
			r.Delete("/queue/{entryId}", handlers.DeleteRoomQueueEntry)
			r.Post("/pick-random", handlers.PickRandomRoomClimb)
			r.Post("/clear-votes", handlers.ClearRoomVotes)
			r.Post("/close", handlers.CloseRoom)
			r.Patch("/participants/{participantId}/role", handlers.UpdateRoomParticipantRole)
			r.Delete("/participants/{participantId}", handlers.RemoveRoomParticipant)
		})
	})

	r.Get("/swagger/*", httpSwagger.Handler(
		httpSwagger.URL("/swagger/doc.json"),
	))

	return r
}

func structuredLogger(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		if traceID := observability.TraceIDFromContext(r.Context()); traceID != "" {
			w.Header().Set(observability.TraceIDHeader, traceID)
		}
		ww := middleware.NewWrapResponseWriter(w, r.ProtoMajor)
		next.ServeHTTP(ww, r)
		routePattern := chi.RouteContext(r.Context()).RoutePattern()
		if routePattern == "" {
			routePattern = r.URL.Path
		}
		observability.ObserveHTTPRequest(r.Method, routePattern, ww.Status(), time.Since(start))
		slog.Info("http request",
			"method", r.Method,
			"path", r.URL.Path,
			"route", routePattern,
			"status", ww.Status(),
			"duration_ms", time.Since(start).Milliseconds(),
			"request_id", middleware.GetReqID(r.Context()),
			"trace_id", observability.TraceIDFromContext(r.Context()),
			"remote_addr", r.RemoteAddr,
		)
	})
}

func limitByIP(requestLimit int, windowLength time.Duration) func(next http.Handler) http.Handler {
	return httprate.Limit(
		requestLimit,
		windowLength,
		httprate.WithKeyFuncs(httprate.KeyByIP),
		httprate.WithLimitHandler(func(w http.ResponseWriter, r *http.Request) {
			handlers.WriteRateLimitError(w, r)
		}),
	)
}
