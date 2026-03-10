import * as Sentry from "@sentry/react";
import { getApiErrorDetails } from "@/lib/api-errors";

let initialized = false;

export function initClientObservability() {
  if (initialized) {
    return;
  }

  const dsn = import.meta.env.VITE_SENTRY_DSN?.trim();
  if (!dsn) {
    initialized = true;
    return;
  }

  Sentry.init({
    dsn,
    enabled: true,
    environment: import.meta.env.VITE_SENTRY_ENVIRONMENT?.trim() || undefined,
    release: import.meta.env.VITE_APP_RELEASE?.trim() || undefined,
  });

  initialized = true;
}

export function reportEvent(
  category: string,
  message: string,
  data?: Record<string, unknown>
) {
  Sentry.addBreadcrumb({
    category,
    data,
    level: "info",
    message,
  });
}

export function reportError(
  error: unknown,
  context?: {
    tags?: Record<string, string>;
    extra?: Record<string, unknown>;
  }
) {
  Sentry.withScope((scope) => {
    for (const [key, value] of Object.entries(context?.tags ?? {})) {
      scope.setTag(key, value);
    }
    for (const [key, value] of Object.entries(context?.extra ?? {})) {
      scope.setExtra(key, value);
    }

    if (error instanceof Error) {
      Sentry.captureException(error);
      return;
    }

    Sentry.captureMessage(String(error));
  });
}

export function reportApiFailure(error: unknown, action: string) {
  const details = getApiErrorDetails(error, action);
  reportError(error, {
    tags: {
      action,
      code: typeof details.code === "string" ? details.code : "unknown",
      status: details.status ? String(details.status) : "unknown",
    },
    extra: {
      requestId: details.requestId,
      traceId: details.traceId,
      message: details.message,
    },
  });
}
