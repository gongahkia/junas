import { useCallback, useState, type MutableRefObject } from "react";
import { api } from "@/api";
import { getApiErrorMessage } from "@/lib/api-errors";
import type {
  ClimbSort,
  ProviderClimb,
  RoomCatalogClimbsResponse,
  RoomSnapshot,
} from "@/types";

interface UseRoomCatalogOptions {
  slug: string;
  currentPage: number;
  deferredSearch: string;
  searchParamsRef: MutableRefObject<URLSearchParams>;
  selectedClimbIdRef: MutableRefObject<string>;
  selectedExternalClimbRef: MutableRefObject<ProviderClimb | null>;
  setSearchParams: (
    nextInit: URLSearchParams,
    navigateOptions?: { replace?: boolean }
  ) => void;
  sort: ClimbSort;
}

export function useRoomCatalog({
  slug,
  currentPage,
  deferredSearch,
  searchParamsRef,
  selectedClimbIdRef,
  selectedExternalClimbRef,
  setSearchParams,
  sort,
}: UseRoomCatalogOptions) {
  const [catalog, setCatalog] = useState<RoomCatalogClimbsResponse | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(false);

  const fetchCatalog = useCallback(
    async (
      roomSnapshot: RoomSnapshot | null,
      cursorsRef: MutableRefObject<Record<number, string>>,
      showLoader = false
    ): Promise<RoomCatalogClimbsResponse | null> => {
      if (!slug || !roomSnapshot?.surface) {
        setCatalog(null);
        return null;
      }

      if (showLoader) {
        setCatalogLoading(true);
      }

      try {
        const nextCatalog = await api.getRoomCatalogClimbs(slug, {
          q: deferredSearch || undefined,
          sort,
          cursor: currentPage > 1 ? cursorsRef.current[currentPage] : undefined,
          pageSize: 12,
        });
        setCatalog(nextCatalog);

        if (nextCatalog.next_cursor) {
          cursorsRef.current = {
            ...cursorsRef.current,
            [currentPage + 1]: nextCatalog.next_cursor,
          };
        }

        const currentSelectedClimbId = selectedClimbIdRef.current;
        const currentSelectedExternalClimb = selectedExternalClimbRef.current;
        const nextSelectedClimb =
          nextCatalog.climbs.find((climb) => climb.id === currentSelectedClimbId) ||
          (currentSelectedExternalClimb?.id === currentSelectedClimbId
            ? currentSelectedExternalClimb
            : null) ||
          nextCatalog.climbs[0] ||
          null;
        if (nextSelectedClimb?.id !== currentSelectedClimbId) {
          const nextSearchParams = new URLSearchParams(searchParamsRef.current);
          if (nextSelectedClimb) {
            nextSearchParams.set("climb", nextSelectedClimb.id);
          } else {
            nextSearchParams.delete("climb");
          }
          setSearchParams(nextSearchParams, { replace: true });
        }

        return nextCatalog;
      } catch (caughtError) {
        console.error("Load room catalog failed", caughtError);
        setCatalog(null);
        throw new Error(
          getApiErrorMessage(caughtError, "Unable to load the climb catalog for this room.")
        );
      } finally {
        if (showLoader) {
          setCatalogLoading(false);
        }
      }
    },
    [
      currentPage,
      deferredSearch,
      searchParamsRef,
      selectedClimbIdRef,
      selectedExternalClimbRef,
      setSearchParams,
      slug,
      sort,
    ]
  );

  return {
    catalog,
    catalogLoading,
    fetchCatalog,
    setCatalog,
  };
}
