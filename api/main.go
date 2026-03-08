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
	"errors"
	"log"
	"net/http"
	"os"

	"github.com/lczm/kilter-together/api/bootstrap"
	"github.com/lczm/kilter-together/api/config"
	docs "github.com/lczm/kilter-together/api/docs"
	_ "github.com/lczm/kilter-together/api/providers"
	"github.com/lczm/kilter-together/api/rooms"
	"github.com/lczm/kilter-together/api/routes"
	"github.com/spf13/cobra"
)

func main() {
	rootCmd := &cobra.Command{
		Use: "kilter-together",
	}

	var maxSyncPages int
	bootstrapCmd := &cobra.Command{
		Use:   "bootstrap",
		Short: "Download or refresh the local Kilter database and board images",
		RunE: func(cmd *cobra.Command, args []string) error {
			runtimeConfig := loadRuntimeConfig()
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
			runtimeConfig := loadRuntimeConfig()

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
			return http.ListenAndServe(runtimeConfig.ListenAddr(), r)
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
		log.Fatalf("Error executing command: %v", err)
		os.Exit(1)
	}
}

func loadRuntimeConfig() config.RuntimeConfig {
	runtimeConfig := config.LoadRuntimeConfig()
	config.SetRuntimeConfig(runtimeConfig)
	return runtimeConfig
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
