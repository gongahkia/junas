import { useCallback, useState } from "react";
import { api } from "@/api";
import { getApiErrorMessage } from "@/lib/api-errors";
import type { RoomSnapshot } from "@/types";

interface UseRoomSessionOptions {
  slug: string;
  navigateToJoin: (slug: string) => void;
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
        return nextSnapshot;
      } catch (caughtError) {
        console.error("Load room failed", caughtError);
        const statusCode = (
          caughtError as { response?: { status?: number } }
        )?.response?.status;
        if (statusCode === 401) {
          navigateToJoin(slug);
          return null;
        }
        setSnapshot(null);
        setActionError(
          getApiErrorMessage(
            caughtError,
            "Unable to load this room. Join the invite first, or check whether the host has closed it."
          )
        );
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
