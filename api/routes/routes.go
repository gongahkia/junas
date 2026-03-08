package routes

import (
	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/lczm/boardbuddy/api/handlers"
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
	})

	r.Get("/swagger/*", httpSwagger.Handler(
		httpSwagger.URL("/swagger/doc.json"),
	))

	return r
}
