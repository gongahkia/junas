package bootstrap

import (
	"context"
	"errors"
	"fmt"

	"github.com/lczm/kilter-together/api/config"
)

type Options struct {
	DBPath         string
	ImageDir       string
	StatePath      string
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
	if options.StatePath == "" {
		return errors.New("state path is required")
	}

	hasUsername := options.KilterUsername != ""
	hasPassword := options.KilterPassword != ""
	if hasUsername != hasPassword {
		return errors.New("both KILTER_TOGETHER_KILTER_USERNAME and KILTER_TOGETHER_KILTER_PASSWORD must be set together")
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

	if err := validateDatabase(options.DBPath); err != nil {
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

	if err := writeManifest(options.StatePath, assets); err != nil {
		return err
	}

	return nil
}
