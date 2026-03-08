// @title Kilter Together API
// @version 1.0
// @description API for managing climbing board routes and data. Features cursor-based pagination, grade information for multiple board angles, and comprehensive filtering capabilities.
// @termsOfService http://swagger.io/terms/

// @contact.name API Support
// @contact.url http://www.swagger.io/support
// @contact.email support@swagger.io

// @license.name MIT
// @license.url https://opensource.org/licenses/MIT

// @host lczm.me
// @BasePath /api
// @schemes https

// @externalDocs.description Kilter Together API Documentation
// @externalDocs.url https://github.com/lczm/boardbuddy/blob/main/api/API.md

package main

import (
	"errors"
	"log"
	"net/http"
	"os"

	"github.com/lczm/boardbuddy/api/bootstrap"
	"github.com/lczm/boardbuddy/api/config"
	docs "github.com/lczm/boardbuddy/api/docs"
	"github.com/lczm/boardbuddy/api/routes"
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

			if bootstrapIfMissing && bootstrap.NeedsBootstrap(runtimeConfig.DBPath, runtimeConfig.ImageDir) {
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
		KilterUsername: runtimeConfig.KilterUsername,
		KilterPassword: runtimeConfig.KilterPassword,
		MaxSyncPages:   maxSyncPages,
	}
}

func ensureRuntimeData(runtimeConfig config.RuntimeConfig) error {
	if !bootstrap.NeedsBootstrap(runtimeConfig.DBPath, runtimeConfig.ImageDir) {
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
