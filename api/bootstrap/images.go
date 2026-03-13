package bootstrap

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"sync/atomic"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

const (
	imageDownloadWorkers          = 8
	imageDownloadProgressInterval = 25
)

var kilterImageBaseURL = "https://api.kilterboardapp.com/img"

type ImageAsset struct {
	RemotePath string
	LocalName  string
}

func CollectImageAssets(db *gorm.DB) ([]ImageAsset, error) {
	var remotePaths []string
	if err := db.Raw(
		`SELECT DISTINCT image_filename FROM product_sizes_layouts_sets WHERE image_filename != ''`,
	).Scan(&remotePaths).Error; err != nil {
		return nil, fmt.Errorf("query image filenames: %w", err)
	}

	assets := make([]ImageAsset, 0, len(remotePaths))
	seenLocalNames := make(map[string]string, len(remotePaths))

	for _, remotePath := range remotePaths {
		cleanRemotePath := strings.TrimSpace(strings.TrimPrefix(remotePath, "/"))
		if cleanRemotePath == "" {
			continue
		}

		localName := filepath.Base(cleanRemotePath)
		if existingRemotePath, exists := seenLocalNames[localName]; exists {
			if existingRemotePath != cleanRemotePath {
				return nil, fmt.Errorf(
					"image basename collision for %s between %s and %s",
					localName,
					existingRemotePath,
					cleanRemotePath,
				)
			}
			continue
		}

		seenLocalNames[localName] = cleanRemotePath
		assets = append(assets, ImageAsset{
			RemotePath: cleanRemotePath,
			LocalName:  localName,
		})
	}

	return assets, nil
}

func collectImageAssetsFromPath(dbPath string) ([]ImageAsset, error) {
	db, err := gorm.Open(sqlite.Open(dbPath), &gorm.Config{})
	if err != nil {
		return nil, fmt.Errorf("open sqlite database for image asset collection: %w", err)
	}

	return CollectImageAssets(db)
}

func DownloadImages(ctx context.Context, imageDir string, assets []ImageAsset) error {
	missingAssets := make([]ImageAsset, 0, len(assets))
	for _, asset := range assets {
		outputPath := filepath.Join(imageDir, asset.LocalName)
		if fileExists(outputPath) {
			continue
		}

		missingAssets = append(missingAssets, asset)
	}

	if len(missingAssets) == 0 {
		return nil
	}

	workerCount := imageDownloadWorkers
	if len(missingAssets) < workerCount {
		workerCount = len(missingAssets)
	}

	slog.Info(
		"downloading image assets",
		"missing", len(missingAssets),
		"cached", len(assets)-len(missingAssets),
		"workers", workerCount,
	)

	downloadCtx, cancel := context.WithCancel(ctx)
	defer cancel()

	jobs := make(chan ImageAsset)

	var (
		wg        sync.WaitGroup
		processed atomic.Int64
		errOnce   sync.Once
		firstErr  error
	)

	recordError := func(err error) {
		errOnce.Do(func() {
			firstErr = err
			cancel()
		})
	}

	worker := func() {
		defer wg.Done()

		for asset := range jobs {
			if downloadCtx.Err() != nil {
				return
			}

			imageBytes, err := downloadImageAsset(downloadCtx, defaultHTTPClient, asset.RemotePath)
			if err != nil {
				recordError(err)
				return
			}

			if err := writeFileAtomically(filepath.Join(imageDir, asset.LocalName), imageBytes); err != nil {
				recordError(fmt.Errorf("write image %s: %w", asset.LocalName, err))
				return
			}

			completed := processed.Add(1)
			if completed == int64(len(missingAssets)) || completed%imageDownloadProgressInterval == 0 {
				slog.Info("downloaded image assets", "completed", completed, "total", len(missingAssets))
			}
		}
	}

	for range workerCount {
		wg.Add(1)
		go worker()
	}

sendLoop:
	for _, asset := range missingAssets {
		select {
		case <-downloadCtx.Done():
			break sendLoop
		case jobs <- asset:
		}
	}
	close(jobs)

	wg.Wait()
	if firstErr != nil {
		return firstErr
	}
	if err := ctx.Err(); err != nil {
		return err
	}

	return nil
}

func downloadImageAsset(ctx context.Context, client *http.Client, remotePath string) ([]byte, error) {
	request, err := http.NewRequestWithContext(
		ctx,
		http.MethodGet,
		fmt.Sprintf("%s/%s", kilterImageBaseURL, remotePath),
		nil,
	)
	if err != nil {
		return nil, fmt.Errorf("create image request for %s: %w", remotePath, err)
	}

	response, err := client.Do(request)
	if err != nil {
		return nil, fmt.Errorf("download image %s: %w", remotePath, err)
	}
	defer response.Body.Close()

	if response.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("download image %s: unexpected status %s", remotePath, response.Status)
	}

	imageBytes, err := io.ReadAll(response.Body)
	if err != nil {
		return nil, fmt.Errorf("read image %s: %w", remotePath, err)
	}

	return imageBytes, nil
}

func fileExists(path string) bool {
	fileInfo, err := os.Stat(path)
	return err == nil && !fileInfo.IsDir()
}
