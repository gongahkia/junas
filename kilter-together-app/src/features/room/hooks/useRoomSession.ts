import { useCallback, useState } from "react";
import { api } from "@/api";
import { getApiErrorDetails } from "@/lib/api-errors";
import { reportError, reportEvent } from "@/lib/observability";
import { clearRoomSession } from "@/lib/room-session";
import type { RoomSnapshot } from "@/types";

interface UseRoomSessionOptions {
  slug: string;
  navigateToJoin: (slug: string, reason?: string) => void;
  onLoaded: (snapshot: RoomSnapshot) => void;
}

export function useRoomSession({
  slug,
  navigateToJoin,
  onLoaded,
}: UseRoomSessionOptions) {
  const [snapshot, setSnapshot] = useState<RoomSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionError, setActionError] = useState("");

  const fetchSnapshot = useCallback(
    async (showLoader = false): Promise<RoomSnapshot | null> => {
      if (!slug) {
        return null;
      }

      if (showLoader) {
        setLoading(true);
      }
      setActionError("");

      try {
        const nextSnapshot = await api.getRoom(slug);
        setSnapshot(nextSnapshot);
        onLoaded(nextSnapshot);
        reportEvent("room.session", "room snapshot loaded", {
          providerId: nextSnapshot.provider_id,
          slug,
        });
        return nextSnapshot;
      } catch (caughtError) {
        console.error("Load room failed", caughtError);
        const statusCode = (
          caughtError as { response?: { status?: number } }
        )?.response?.status;
        const details = getApiErrorDetails(
          caughtError,
          "Unable to load this room. Join the invite first, or check whether the host has closed it."
        );
        if (
          details.code === "session_expired" ||
          details.code === "session_invalid" ||
          details.code === "session_required" ||
          details.status === 401 ||
          statusCode === 401
        ) {
          clearRoomSession(slug);
          navigateToJoin(slug, details.code ?? "session_required");
          return null;
        }
        setSnapshot(null);
        setActionError(details.message);
        reportError(caughtError, {
          extra: { slug },
          tags: {
            code: typeof details.code === "string" ? details.code : "unknown",
            flow: "room_session",
          },
        });
        return null;
      } finally {
        if (showLoader) {
          setLoading(false);
        }
      }
    },
    [navigateToJoin, onLoaded, slug]
  );

  return {
    actionError,
    fetchSnapshot,
    loading,
    setActionError,
    setSnapshot,
    snapshot,
  };
}
