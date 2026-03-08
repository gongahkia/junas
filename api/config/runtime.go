package config

import (
	"os"
	"path/filepath"
	"strings"
)

type RuntimeConfig struct {
	DataDir        string
	DBPath         string
	AppDBPath      string
	ImageDir       string
	StatePath      string
	KilterUsername string
	KilterPassword string
	AppSecret      string
	EncryptionKey  string
	Port           string
}

var runtimeConfig *RuntimeConfig

func LoadRuntimeConfig() RuntimeConfig {
	dataDir := cleanPath(firstNonEmpty(os.Getenv("KILTER_TOGETHER_DATA_DIR"), "data"))
	dbPath := cleanPath(firstNonEmpty(
		os.Getenv("KILTER_TOGETHER_DB_PATH"),
		filepath.Join(dataDir, "kilter.db"),
	))
	appDBPath := cleanPath(firstNonEmpty(
		os.Getenv("KILTER_TOGETHER_APP_DB_PATH"),
		filepath.Join(dataDir, "app.db"),
	))
	imageDir := cleanPath(firstNonEmpty(
		os.Getenv("KILTER_TOGETHER_IMAGE_DIR"),
		filepath.Join(dataDir, "images"),
	))
	statePath := cleanPath(filepath.Join(dataDir, "bootstrap-state.json"))

	return RuntimeConfig{
		DataDir:        dataDir,
		DBPath:         dbPath,
		AppDBPath:      appDBPath,
		ImageDir:       imageDir,
		StatePath:      statePath,
		KilterUsername: strings.TrimSpace(os.Getenv("KILTER_TOGETHER_KILTER_USERNAME")),
		KilterPassword: os.Getenv("KILTER_TOGETHER_KILTER_PASSWORD"),
		AppSecret:      strings.TrimSpace(os.Getenv("KILTER_TOGETHER_APP_SECRET")),
		EncryptionKey:  strings.TrimSpace(os.Getenv("KILTER_TOGETHER_ENCRYPTION_KEY")),
		Port:           normalizePort(os.Getenv("KILTER_TOGETHER_PORT")),
	}
}

func SetRuntimeConfig(cfg RuntimeConfig) {
	runtimeConfig = &cfg
}

func GetRuntimeConfig() RuntimeConfig {
	if runtimeConfig == nil {
		cfg := LoadRuntimeConfig()
		runtimeConfig = &cfg
	}

	return *runtimeConfig
}

func (cfg RuntimeConfig) ListenAddr() string {
	if strings.HasPrefix(cfg.Port, ":") {
		return cfg.Port
	}

	return ":" + cfg.Port
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return value
		}
	}

	return ""
}

func cleanPath(path string) string {
	return filepath.Clean(path)
}

func normalizePort(value string) string {
	trimmedValue := strings.TrimSpace(value)
	if trimmedValue == "" {
		return "8082"
	}

	return strings.TrimPrefix(trimmedValue, ":")
}
