package routes

import (
	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/lczm/kilter-together/api/handlers"
	httpSwagger "github.com/swaggo/http-swagger"
)

// SetupRoutes configures all the routes for the application
func SetupRoutes() *chi.Mux {
	r := chi.NewRouter()

	// middleware stack
	r.Use(middleware.Logger)
	r.Use(middleware.Recoverer)
	r.Use(middleware.RequestID)
	r.Use(middleware.RealIP)

	// Define routes
	r.Route("/api", func(r chi.Router) {
		r.Get("/healthz", handlers.Healthz)
		r.Get("/climbs", handlers.GetClimbs)
		r.Get("/boards", handlers.GetBoardOptions)
		r.Get("/images/{filename}", handlers.ServeImage)
		r.Post("/rooms", handlers.CreateRoom)
		r.Route("/rooms/{slug}", func(r chi.Router) {
			r.Post("/join", handlers.JoinRoom)
			r.Get("/", handlers.GetRoom)
			r.Get("/events", handlers.StreamRoomEvents)
			r.Post("/provider/connect", handlers.ConnectRoomProvider)
			r.Post("/surface", handlers.SetRoomSurface)
			r.Get("/catalog/surfaces", handlers.ListRoomCatalogSurfaces)
			r.Get("/catalog/climbs", handlers.ListRoomCatalogClimbs)
			r.Get("/catalog/climbs/{climbId}", handlers.GetRoomCatalogClimb)
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
