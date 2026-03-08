package bootstrap

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"time"

	_ "github.com/mattn/go-sqlite3"
)

var requiredRuntimeTables = []string{
	"climbs",
	"climb_stats",
	"difficulty_grades",
	"layouts",
	"product_sizes",
	"product_sizes_layouts_sets",
	"products",
}

type RuntimeManifest struct {
	GeneratedAt time.Time `json:"generated_at"`
	Assets      []string  `json:"assets"`
}

func RuntimeReady(dbPath, imageDir, statePath string) error {
	assets, err := expectedAssets(dbPath, statePath)
	if err != nil {
		return err
	}

	for _, asset := range assets {
		if !fileExists(filepath.Join(imageDir, asset.LocalName)) {
			return fmt.Errorf("missing image asset %s", asset.LocalName)
		}
	}

	return nil
}

func NeedsBootstrap(dbPath, imageDir, statePath string) bool {
	return RuntimeReady(dbPath, imageDir, statePath) != nil
}

func expectedAssets(dbPath, statePath string) ([]ImageAsset, error) {
	if err := validateDatabase(dbPath); err != nil {
		return nil, err
	}

	assets, err := collectImageAssetsFromPath(dbPath)
	if err != nil {
		return nil, err
	}
	if len(assets) == 0 {
		return nil, fmt.Errorf("no image assets discovered from %s", dbPath)
	}

	if fileExists(statePath) {
		manifest, err := loadManifest(statePath)
		if err != nil {
			return nil, err
		}

		expected := make([]string, 0, len(assets))
		for _, asset := range assets {
			expected = append(expected, asset.LocalName)
		}
		slices.Sort(expected)

		manifestAssets := append([]string(nil), manifest.Assets...)
		slices.Sort(manifestAssets)

		if !slices.Equal(expected, manifestAssets) {
			return nil, fmt.Errorf("bootstrap manifest %s is stale", statePath)
		}
	}

	return assets, nil
}

func validateDatabase(dbPath string) error {
	if !fileExists(dbPath) {
		return fmt.Errorf("database file %s is missing", dbPath)
	}

	connection, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		return fmt.Errorf("open sqlite database: %w", err)
	}
	defer connection.Close()

	for _, tableName := range requiredRuntimeTables {
		var exists int
		if err := connection.QueryRow(
			`SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = ?`,
			tableName,
		).Scan(&exists); err != nil {
			return fmt.Errorf("inspect %s table: %w", tableName, err)
		}

		if exists == 0 {
			return fmt.Errorf("required table %s is missing", tableName)
		}
	}

	return nil
}

func writeManifest(statePath string, assets []ImageAsset) error {
	assetNames := make([]string, 0, len(assets))
	for _, asset := range assets {
		assetNames = append(assetNames, asset.LocalName)
	}
	slices.Sort(assetNames)

	manifestBytes, err := json.MarshalIndent(RuntimeManifest{
		GeneratedAt: time.Now().UTC(),
		Assets:      assetNames,
	}, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal bootstrap manifest: %w", err)
	}

	return writeFileAtomically(statePath, manifestBytes)
}

func loadManifest(statePath string) (*RuntimeManifest, error) {
	manifestBytes, err := os.ReadFile(statePath)
	if err != nil {
		return nil, err
	}

	var manifest RuntimeManifest
	if err := json.Unmarshal(manifestBytes, &manifest); err != nil {
		return nil, fmt.Errorf("decode bootstrap manifest: %w", err)
	}
	if len(manifest.Assets) == 0 {
		return nil, fmt.Errorf("bootstrap manifest %s does not declare any assets", statePath)
	}

	for _, assetName := range manifest.Assets {
		if strings.TrimSpace(assetName) == "" {
			return nil, fmt.Errorf("bootstrap manifest %s contains an empty asset name", statePath)
		}
	}

	return &manifest, nil
}
