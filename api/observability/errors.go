package observability

import (
	"context"
	"strings"
	"time"

	"github.com/getsentry/sentry-go"
	"github.com/lczm/kilter-together/api/config"
)

func InitErrorReporting(cfg config.RuntimeConfig) error {
	dsn := strings.TrimSpace(cfg.SentryDSN)
	if dsn == "" {
		return nil
	}

	return sentry.Init(sentry.ClientOptions{
		Dsn:         dsn,
		Environment: cfg.SentryEnvironment,
		Release:     cfg.SentryRelease,
	})
}

func FlushErrors(timeout time.Duration) bool {
	return sentry.Flush(timeout)
}

func CaptureError(ctx context.Context, err error, attributes map[string]string) {
	if err == nil {
		return
	}

	sentry.WithScope(func(scope *sentry.Scope) {
		if requestID := RequestIDFromContext(ctx); requestID != "" {
			scope.SetTag("request_id", requestID)
		}
		if traceID := TraceIDFromContext(ctx); traceID != "" {
			scope.SetTag("trace_id", traceID)
		}
		for key, value := range attributes {
			if strings.TrimSpace(value) == "" {
				continue
			}
			scope.SetTag(key, value)
		}
		sentry.CaptureException(err)
	})
}
