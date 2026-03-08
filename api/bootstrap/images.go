package bootstrap

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

const kilterImageBaseURL = "https://api.kilterboardapp.com/img"

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
	for _, asset := range assets {
		outputPath := filepath.Join(imageDir, asset.LocalName)
		if fileExists(outputPath) {
			continue
		}

		imageBytes, err := downloadImageAsset(ctx, defaultHTTPClient, asset.RemotePath)
		if err != nil {
			return err
		}

		if err := writeFileAtomically(outputPath, imageBytes); err != nil {
			return fmt.Errorf("write image %s: %w", asset.LocalName, err)
		}
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
