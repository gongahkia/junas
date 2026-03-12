import { api } from "@/api";
import { reportError, reportEvent } from "@/lib/observability";

export function trackProductEvent(
  eventName: string,
  payload?: {
    roomSlug?: string;
    viewerRole?: string;
    route?: string;
    properties?: Record<string, unknown>;
  }
) {
  reportEvent("product", eventName, payload?.properties);
  void api
    .recordAnalyticsEvent({
      roomSlug: payload?.roomSlug,
      eventName,
      viewerRole: payload?.viewerRole,
      route:
        payload?.route ||
        (typeof window !== "undefined" ? window.location.pathname : undefined),
      properties: payload?.properties,
    })
    .catch((error) => {
      reportError(error, {
        tags: {
          flow: "product_analytics",
        },
        extra: {
          eventName,
        },
      });
    });
}
