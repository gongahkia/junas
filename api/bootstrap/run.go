package bootstrap

import (
	"context"
	"errors"
	"fmt"
	"os"

	"github.com/lczm/boardbuddy/api/config"
)

type Options struct {
	DBPath         string
	ImageDir       string
	KilterUsername string
	KilterPassword string
	MaxSyncPages   int
}

func (options Options) Validate() error {
	if options.DBPath == "" {
		return errors.New("database path is required")
	}
	if options.ImageDir == "" {
		return errors.New("image directory is required")
	}

	hasUsername := options.KilterUsername != ""
	hasPassword := options.KilterPassword != ""
	if hasUsername != hasPassword {
		return errors.New("both KILTER_TOGETHER_KILTER_USERNAME and KILTER_TOGETHER_KILTER_PASSWORD must be set together")
	}

	if options.MaxSyncPages <= 0 {
		options.MaxSyncPages = DefaultMaxSyncPages
	}

	return nil
}

func Run(ctx context.Context, options Options) error {
	if options.MaxSyncPages <= 0 {
		options.MaxSyncPages = DefaultMaxSyncPages
	}
	if err := options.Validate(); err != nil {
		return err
	}

	if !fileExists(options.DBPath) {
		if err := DownloadBaseDatabase(ctx, options.DBPath); err != nil {
			return err
		}
	}

	if options.KilterUsername != "" {
		token, err := Login(ctx, options.KilterUsername, options.KilterPassword)
		if err != nil {
			return err
		}

		if err := SyncSharedData(ctx, options.DBPath, token, options.MaxSyncPages); err != nil {
			return err
		}
	}

	if err := config.ConnectKilterDB(options.DBPath); err != nil {
		return err
	}

	assets, err := CollectImageAssets(config.KilterDB)
	if err != nil {
		return fmt.Errorf("collect image assets: %w", err)
	}

	if err := DownloadImages(ctx, options.ImageDir, assets); err != nil {
		return err
	}

	return nil
}

func NeedsBootstrap(dbPath, imageDir string) bool {
	return !fileExists(dbPath) || !directoryHasFiles(imageDir)
}

func directoryHasFiles(path string) bool {
	entries, err := os.ReadDir(path)
	return err == nil && len(entries) > 0
}
