package config

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

var defaultAllowedOrigins = []string{
	"http://localhost:5173",
	"http://127.0.0.1:5173",
	"http://localhost:8080",
	"http://127.0.0.1:8080",
}

type RuntimeConfig struct {
	DataDir                string
	DBPath                 string
	AppDBPath              string
	ImageDir               string
	StatePath              string
	KilterUsername         string
	KilterPassword         string
	AppSecret              string
	EncryptionKey          string
	Port                   string
	SecureCookies          bool
	AllowedOrigins         []string
	PreviousEncryptionKey  string
	EnableTestProvider     bool
	OperatorToken          string
	OTLPTracesEndpoint     string
	OTLPTracesInsecure     bool
	OTELServiceName        string
	SentryDSN              string
	SentryEnvironment      string
	SentryRelease          string
	StorageWarnPercent     int
	StorageCriticalPercent int
}

var runtimeConfig *RuntimeConfig

func LoadRuntimeConfig() RuntimeConfig {
	dataDir := cleanPath(firstNonEmpty(
		os.Getenv("RAILWAY_VOLUME_MOUNT_PATH"),
		os.Getenv("KILTER_TOGETHER_DATA_DIR"),
		"data",
	))
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

	secureCookies := true
	if v := strings.TrimSpace(os.Getenv("KILTER_TOGETHER_SECURE_COOKIES")); v == "false" || v == "0" {
		secureCookies = false
	}

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
		Port: normalizePort(firstNonEmpty(
			os.Getenv("KILTER_TOGETHER_PORT"),
			os.Getenv("PORT"),
		)),
		SecureCookies:         secureCookies,
		AllowedOrigins:        parseAllowedOrigins(os.Getenv("KILTER_TOGETHER_ALLOWED_ORIGINS")),
		PreviousEncryptionKey: strings.TrimSpace(os.Getenv("KILTER_TOGETHER_PREVIOUS_ENCRYPTION_KEY")),
		EnableTestProvider:    parseBoolEnv(os.Getenv("KILTER_TOGETHER_ENABLE_TEST_PROVIDER")),
		OperatorToken:         strings.TrimSpace(os.Getenv("KILTER_TOGETHER_OPERATOR_TOKEN")),
		OTLPTracesEndpoint:    strings.TrimSpace(os.Getenv("KILTER_TOGETHER_OTEL_EXPORTER_OTLP_ENDPOINT")),
		OTLPTracesInsecure:    parseBoolEnv(os.Getenv("KILTER_TOGETHER_OTEL_EXPORTER_OTLP_INSECURE")),
		OTELServiceName: firstNonEmpty(
			strings.TrimSpace(os.Getenv("KILTER_TOGETHER_OTEL_SERVICE_NAME")),
			"kilter-together-api",
		),
		SentryDSN:              strings.TrimSpace(os.Getenv("KILTER_TOGETHER_SENTRY_DSN")),
		SentryEnvironment:      strings.TrimSpace(os.Getenv("KILTER_TOGETHER_SENTRY_ENVIRONMENT")),
		SentryRelease:          strings.TrimSpace(os.Getenv("KILTER_TOGETHER_SENTRY_RELEASE")),
		StorageWarnPercent:     parseIntEnv(os.Getenv("KILTER_TOGETHER_STORAGE_WARN_PERCENT"), 80),
		StorageCriticalPercent: parseIntEnv(os.Getenv("KILTER_TOGETHER_STORAGE_CRITICAL_PERCENT"), 90),
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

func (cfg RuntimeConfig) CORSAllowedOrigins() []string {
	if len(cfg.AllowedOrigins) == 0 {
		return append([]string{}, defaultAllowedOrigins...)
	}

	return append([]string{}, cfg.AllowedOrigins...)
}

func (cfg RuntimeConfig) Validate() error {
	for _, origin := range cfg.CORSAllowedOrigins() {
		if origin == "*" {
			return fmt.Errorf("KILTER_TOGETHER_ALLOWED_ORIGINS cannot include * when cookie auth is enabled")
		}
	}
	if cfg.StorageWarnPercent <= 0 || cfg.StorageWarnPercent >= 100 {
		return fmt.Errorf("KILTER_TOGETHER_STORAGE_WARN_PERCENT must be between 1 and 99")
	}
	if cfg.StorageCriticalPercent <= 0 || cfg.StorageCriticalPercent > 100 {
		return fmt.Errorf("KILTER_TOGETHER_STORAGE_CRITICAL_PERCENT must be between 1 and 100")
	}
	if cfg.StorageCriticalPercent <= cfg.StorageWarnPercent {
		return fmt.Errorf("KILTER_TOGETHER_STORAGE_CRITICAL_PERCENT must be greater than KILTER_TOGETHER_STORAGE_WARN_PERCENT")
	}

	return nil
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

func parseAllowedOrigins(value string) []string {
	trimmed := strings.TrimSpace(value)
	if trimmed == "" {
		return append([]string{}, defaultAllowedOrigins...)
	}
	parts := strings.Split(trimmed, ",")
	origins := make([]string, 0, len(parts))
	for _, p := range parts {
		if o := strings.TrimSpace(p); o != "" {
			origins = append(origins, o)
		}
	}
	if len(origins) == 0 {
		return append([]string{}, defaultAllowedOrigins...)
	}
	return origins
}

func parseBoolEnv(value string) bool {
	switch strings.ToLower(strings.TrimSpace(value)) {
	case "1", "true", "yes", "on":
		return true
	default:
		return false
	}
}

func parseIntEnv(value string, fallback int) int {
	trimmed := strings.TrimSpace(value)
	if trimmed == "" {
		return fallback
	}
	parsed, err := strconv.Atoi(trimmed)
	if err != nil {
		return fallback
	}
	return parsed
}
