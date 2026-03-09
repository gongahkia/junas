// @title Kilter Together API
// @version 1.0
// @description API for solo Kilter browsing plus collaborative room sessions with Kilter and Crux provider adapters.
// @termsOfService http://swagger.io/terms/

// @contact.name API Support
// @contact.url https://github.com/lczm/kilter-together
// @contact.email opensource@lczm.me

// @license.name MIT
// @license.url https://opensource.org/licenses/MIT

// @host localhost:8082
// @BasePath /api
// @schemes http https

// @externalDocs.description Kilter Together API Documentation
// @externalDocs.url https://github.com/lczm/kilter-together/blob/main/api/README.md

package main

import (
	"context"
	"errors"
	"log/slog"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/lczm/kilter-together/api/bootstrap"
	"github.com/lczm/kilter-together/api/config"
	docs "github.com/lczm/kilter-together/api/docs"
	_ "github.com/lczm/kilter-together/api/providers"
	"github.com/lczm/kilter-together/api/rooms"
	"github.com/lczm/kilter-together/api/routes"
	"github.com/spf13/cobra"
)

const (
	serverReadHeaderTimeout = 10 * time.Second
	serverReadTimeout       = 30 * time.Second
	serverWriteTimeout      = 24 * time.Hour
	serverIdleTimeout       = 2 * time.Minute
	serverShutdownTimeout   = 20 * time.Second
)

func main() {
	slog.SetDefault(slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo})))

	rootCmd := &cobra.Command{
		Use: "kilter-together",
	}

	var maxSyncPages int
	bootstrapCmd := &cobra.Command{
		Use:   "bootstrap",
		Short: "Download or refresh the local Kilter database and board images",
		RunE: func(cmd *cobra.Command, args []string) error {
			runtimeConfig, err := loadRuntimeConfig()
			if err != nil {
				return err
			}
			return bootstrap.Run(cmd.Context(), bootstrapOptions(runtimeConfig, maxSyncPages))
		},
	}
	bootstrapCmd.Flags().IntVar(
		&maxSyncPages,
		"max-sync-pages",
		bootstrap.DefaultMaxSyncPages,
		"Maximum number of Kilter shared-sync pages to fetch when credentials are provided",
	)

	var bootstrapIfMissing bool
	serveCmd := &cobra.Command{
		Use:   "serve",
		Short: "Start the API server",
		RunE: func(cmd *cobra.Command, args []string) error {
			runtimeConfig, err := loadRuntimeConfig()
			if err != nil {
				return err
			}

			if bootstrapIfMissing && bootstrap.NeedsBootstrap(
				runtimeConfig.DBPath,
				runtimeConfig.ImageDir,
				runtimeConfig.StatePath,
			) {
				if err := bootstrap.Run(cmd.Context(), bootstrapOptions(runtimeConfig, maxSyncPages)); err != nil {
					return err
				}
			}

			if err := ensureRuntimeData(runtimeConfig); err != nil {
				return err
			}

			if err := config.ConnectKilterDB(runtimeConfig.DBPath); err != nil {
				return err
			}
			if err := config.ConnectAppDB(runtimeConfig.AppDBPath); err != nil {
				return err
			}
			if err := rooms.DefaultService.Migrate(cmd.Context()); err != nil {
				return err
			}

			configureSwagger()
			r := routes.SetupRoutes()

			serverCtx, stop := signal.NotifyContext(cmd.Context(), os.Interrupt, syscall.SIGTERM)
			defer stop()

			listener, err := net.Listen("tcp", runtimeConfig.ListenAddr())
			if err != nil {
				return err
			}

			server := newHTTPServer(runtimeConfig.ListenAddr(), r)
			server.RegisterOnShutdown(func() {
				rooms.DefaultService.Hub().CloseAll()
			})

			slog.Info("http server listening",
				"addr", listener.Addr().String(),
				"read_header_timeout", server.ReadHeaderTimeout.String(),
				"read_timeout", server.ReadTimeout.String(),
				"write_timeout", server.WriteTimeout.String(),
				"idle_timeout", server.IdleTimeout.String(),
			)

			return serveHTTPServer(serverCtx, server, listener)
		},
	}
	serveCmd.Flags().BoolVar(
		&bootstrapIfMissing,
		"bootstrap-if-missing",
		false,
		"Download the database and images before serving when local data is missing",
	)
	serveCmd.Flags().IntVar(
		&maxSyncPages,
		"max-sync-pages",
		bootstrap.DefaultMaxSyncPages,
		"Maximum number of Kilter shared-sync pages to fetch when credentials are provided",
	)

	rootCmd.AddCommand(bootstrapCmd, serveCmd)

	if err := rootCmd.Execute(); err != nil {
		slog.Error("command failed", "error", err)
		os.Exit(1)
	}
}

func loadRuntimeConfig() (config.RuntimeConfig, error) {
	runtimeConfig := config.LoadRuntimeConfig()
	if err := runtimeConfig.Validate(); err != nil {
		return config.RuntimeConfig{}, err
	}
	config.SetRuntimeConfig(runtimeConfig)
	return runtimeConfig, nil
}

func bootstrapOptions(runtimeConfig config.RuntimeConfig, maxSyncPages int) bootstrap.Options {
	return bootstrap.Options{
		DBPath:         runtimeConfig.DBPath,
		ImageDir:       runtimeConfig.ImageDir,
		StatePath:      runtimeConfig.StatePath,
		KilterUsername: runtimeConfig.KilterUsername,
		KilterPassword: runtimeConfig.KilterPassword,
		MaxSyncPages:   maxSyncPages,
	}
}

func ensureRuntimeData(runtimeConfig config.RuntimeConfig) error {
	if !bootstrap.NeedsBootstrap(runtimeConfig.DBPath, runtimeConfig.ImageDir, runtimeConfig.StatePath) {
		return nil
	}

	return errors.New(
		"local Kilter data is missing; run `kilter-together bootstrap` or start with `serve --bootstrap-if-missing`",
	)
}

func configureSwagger() {
	docs.SwaggerInfo.Host = ""
	docs.SwaggerInfo.BasePath = "/api"
	docs.SwaggerInfo.Schemes = []string{}
}

func newHTTPServer(addr string, handler http.Handler) *http.Server {
	return &http.Server{
		Addr:              addr,
		Handler:           handler,
		ReadHeaderTimeout: serverReadHeaderTimeout,
		ReadTimeout:       serverReadTimeout,
		// SSE responses stay open for long periods, so the write timeout is intentionally high.
		WriteTimeout: serverWriteTimeout,
		IdleTimeout:  serverIdleTimeout,
	}
}

func serveHTTPServer(ctx context.Context, server *http.Server, listener net.Listener) error {
	errCh := make(chan error, 1)

	go func() {
		if err := server.Serve(listener); err != nil && !errors.Is(err, http.ErrServerClosed) {
			errCh <- err
			return
		}

		errCh <- nil
	}()

	select {
	case err := <-errCh:
		return err
	case <-ctx.Done():
		slog.Info("shutdown signal received", "signal", context.Cause(ctx))
	}

	shutdownCtx, cancel := context.WithTimeout(context.Background(), serverShutdownTimeout)
	defer cancel()

	if err := server.Shutdown(shutdownCtx); err != nil {
		_ = server.Close()
		return err
	}

	return <-errCh
}
