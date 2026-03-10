package observability

import (
	"context"

	"github.com/go-chi/chi/v5/middleware"
	"go.opentelemetry.io/otel/trace"
)

const TraceIDHeader = "X-Trace-Id"

func RequestIDFromContext(ctx context.Context) string {
	return middleware.GetReqID(ctx)
}

func TraceIDFromContext(ctx context.Context) string {
	spanContext := trace.SpanContextFromContext(ctx)
	if !spanContext.IsValid() {
		return ""
	}

	return spanContext.TraceID().String()
}

