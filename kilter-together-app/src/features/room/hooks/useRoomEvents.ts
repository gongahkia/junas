import { useEffect, useRef } from "react";
import { api } from "@/api";
import { parseRoomEventPayload, shouldRefreshCatalogOnly, shouldRefreshRoomAndCatalog, shouldRefreshRoomOnly } from "@/features/room/room-events";
import { reportError, reportEvent } from "@/lib/observability";
import type { RoomStatus } from "@/types";

const ROOM_EVENTS_INITIAL_RETRY_MS = 1000;
const ROOM_EVENTS_MAX_RETRY_MS = 30000;

interface UseRoomEventsOptions {
  slug: string;
  roomStatus?: RoomStatus;
  refreshRoom: () => Promise<void>;
  refreshCatalog: () => Promise<void>;
  refreshRoomAndCatalog: () => Promise<void>;
}

export function useRoomEvents({
  slug,
  roomStatus,
  refreshRoom,
  refreshCatalog,
  refreshRoomAndCatalog,
}: UseRoomEventsOptions) {
  const refreshRoomRef = useRef(refreshRoom);
  const refreshCatalogRef = useRef(refreshCatalog);
  const refreshRoomAndCatalogRef = useRef(refreshRoomAndCatalog);

  useEffect(() => {
    refreshRoomRef.current = refreshRoom;
    refreshCatalogRef.current = refreshCatalog;
    refreshRoomAndCatalogRef.current = refreshRoomAndCatalog;
  }, [refreshCatalog, refreshRoom, refreshRoomAndCatalog]);

  useEffect(() => {
    if (!slug || !roomStatus || roomStatus === "closed" || typeof EventSource === "undefined") {
      return;
    }

    let disposed = false;
    let retryTimeout: number | undefined;
    let currentSource: EventSource | null = null;
    let retryDelay = ROOM_EVENTS_INITIAL_RETRY_MS;
    let retryCount = 0;

    const connect = () => {
      if (disposed) {
        return;
      }

      const eventSource = new EventSource(api.getRoomEventsUrl(slug), {
        withCredentials: true,
      });
      currentSource = eventSource;

      eventSource.addEventListener("room", (event) => {
        retryDelay = ROOM_EVENTS_INITIAL_RETRY_MS;
        retryCount = 0;

        const payload = parseRoomEventPayload((event as MessageEvent<string>).data);
        if (shouldRefreshCatalogOnly(payload)) {
          void refreshCatalogRef.current();
          return;
        }

        if (shouldRefreshRoomAndCatalog(payload)) {
          void refreshRoomAndCatalogRef.current();
          return;
        }

        if (shouldRefreshRoomOnly(payload)) {
          void refreshRoomRef.current();
          return;
        }

        void refreshRoomAndCatalogRef.current();
      });

      eventSource.onerror = () => {
        eventSource.close();
        if (currentSource === eventSource) {
          currentSource = null;
        }
        if (disposed) {
          return;
        }

        const nextDelay = retryDelay;
        retryCount += 1;
        reportEvent("room.sse", "room event stream reconnect scheduled", {
          nextDelay,
          retryCount,
          slug,
        });
        if (retryCount >= 3) {
          reportError(new Error("Room SSE reconnect storm"), {
            extra: {
              nextDelay,
              retryCount,
              slug,
            },
            tags: {
              flow: "room_sse",
            },
          });
        }
        retryDelay = Math.min(retryDelay * 2, ROOM_EVENTS_MAX_RETRY_MS);
        if (retryTimeout !== undefined) {
          window.clearTimeout(retryTimeout);
        }
        retryTimeout = window.setTimeout(connect, nextDelay);
      };
    };

    connect();

    return () => {
      disposed = true;
      if (retryTimeout !== undefined) {
        window.clearTimeout(retryTimeout);
      }
      currentSource?.close();
    };
  }, [roomStatus, slug]);
}
