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
		r.Use(httprate.LimitByIP(100, time.Minute))
	}

	// Define routes
	r.Route("/api", func(r chi.Router) {
		r.Get("/healthz", handlers.Healthz)
		r.Get("/livez", handlers.Livez)
		r.Get("/readyz", handlers.Readyz)
		r.Get("/metrics", handlers.Metrics)
		r.Get("/climbs", handlers.GetClimbs)
		r.Get("/boards", handlers.GetBoardOptions)
		r.Get("/images/{filename}", handlers.ServeImage)
		if runtimeConfig.EnableTestProvider {
			r.Post("/rooms", handlers.CreateRoom)
		} else {
			r.With(httprate.LimitByIP(10, time.Minute)).Post("/rooms", handlers.CreateRoom)
		}
		r.Route("/rooms/{slug}", func(r chi.Router) {
			r.Post("/join", handlers.JoinRoom)
			r.Get("/", handlers.GetRoom)
			r.Patch("/", handlers.UpdateRoom)
			r.Get("/events", handlers.StreamRoomEvents)
			if runtimeConfig.EnableTestProvider {
				r.Post("/provider/connect", handlers.ConnectRoomProvider)
			} else {
				r.With(httprate.LimitByIP(5, time.Minute)).Post("/provider/connect", handlers.ConnectRoomProvider)
			}
			r.Post("/surface", handlers.SetRoomSurface)
			r.Get("/catalog/surfaces", handlers.ListRoomCatalogSurfaces)
			r.Get("/catalog/climbs", handlers.ListRoomCatalogClimbs)
			r.Get("/catalog/climbs/{climbId}", handlers.GetRoomCatalogClimb)
			r.Put("/fist-bumps/settings", handlers.UpdateRoomFistBumps)
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
			"remote_addr", r.RemoteAddr,
		)
	})
}
