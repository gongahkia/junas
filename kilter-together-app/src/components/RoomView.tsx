import {
  type DragEvent,
  useCallback,
  startTransition,
  useDeferredValue,
  useEffect,
  useRef,
  useState,
} from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  ArrowLeft,
  Copy,
  GripVertical,
  RefreshCw,
  Trash2,
  UserMinus,
} from "lucide-react";
import { api } from "@/api";
import type {
  ParticipantStatus,
  ProviderClimb,
  ProviderSurface,
  QueueStatus,
  RoomReactionCode,
  RoomCatalogClimbsResponse,
  RoomSnapshot,
} from "@/types";
import { DEFAULT_ANGLE, normalizeSort } from "@/lib/climbs";
import { getApiErrorMessage } from "@/lib/api-errors";
import { buildInviteLink } from "@/lib/room-links";
import { cn } from "@/lib/utils";
import {
  dismissOnboarding,
  loadUserPrefs,
  markGuestParticipated,
  markHostProviderConnected,
  rememberCruxToken,
  rememberKilterCredentials,
  markHostSurfaceSelected,
  rememberLastCruxSurface,
  rememberLastKilterSurface,
  rememberLastProvider,
  rememberRoomVisit,
} from "@/lib/user-prefs";
import OnboardingCallout from "@/components/OnboardingCallout";
import DetailGrid, { type DetailGridItem } from "@/components/DetailGrid";
import RoomProblemView from "@/components/RoomProblemView";
import InviteQRCodeCard from "@/components/InviteQRCodeCard";
import AngleSelector from "@/components/AngleSelector";
import LoadingSlideshow from "@/components/LoadingSlideshow";
import SortSelector from "@/components/SortSelector";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useErrorToast } from "@/hooks/use-toast";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const PAGE_SIZE = 12;
const ROOM_EVENTS_INITIAL_RETRY_MS = 1000;
const ROOM_EVENTS_MAX_RETRY_MS = 30000;

function formatProviderName(providerId: RoomSnapshot["provider_id"]) {
  return providerId === "crux" ? "Crux" : "Kilter";
}

function reorderEntryIDs(entryIDs: number[], sourceEntryID: number, targetEntryID: number) {
  const sourceIndex = entryIDs.indexOf(sourceEntryID);
  const targetIndex = entryIDs.indexOf(targetEntryID);
  if (sourceIndex < 0 || targetIndex < 0 || sourceIndex === targetIndex) {
    return null;
  }

  const reordered = [...entryIDs];
  const [movedEntryID] = reordered.splice(sourceIndex, 1);
  reordered.splice(targetIndex, 0, movedEntryID);
  return reordered;
}

export default function RoomView() {
  const { slug = "" } = useParams();
  const navigate = useNavigate();
  const showErrorToast = useErrorToast();
  const savedPrefsRef = useRef(loadUserPrefs());
  const [searchParams, setSearchParams] = useSearchParams();
  const [snapshot, setSnapshot] = useState<RoomSnapshot | null>(null);
  const [catalog, setCatalog] = useState<RoomCatalogClimbsResponse | null>(null);
  const [selectedExternalClimb, setSelectedExternalClimb] = useState<ProviderClimb | null>(null);
  const [loading, setLoading] = useState(true);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [surfaceLoading, setSurfaceLoading] = useState(false);
  const [actionError, setActionError] = useState("");
  const [roomNameInput, setRoomNameInput] = useState("");
  const [roomNameSaving, setRoomNameSaving] = useState(false);
  const [emojiReactionsSaving, setEmojiReactionsSaving] = useState(false);
  const [reactionSendingCode, setReactionSendingCode] = useState<RoomReactionCode | null>(null);
  const [showRoomSettings, setShowRoomSettings] = useState(false);
  const [showSurfaceEditor, setShowSurfaceEditor] = useState(false);
  const [connectionFields, setConnectionFields] = useState(() => ({
    username: savedPrefsRef.current.savedCredentials.kilter.remember
      ? savedPrefsRef.current.savedCredentials.kilter.username
      : "",
    password: "",
    token: "",
  }));
  const [rememberCredentials, setRememberCredentials] = useState(() => ({
    kilter: savedPrefsRef.current.savedCredentials.kilter.remember,
    crux: savedPrefsRef.current.savedCredentials.crux.remember,
  }));
  const [boardSurfaces, setBoardSurfaces] = useState<ProviderSurface[]>([]);
  const [cruxGyms, setCruxGyms] = useState<ProviderSurface[]>([]);
  const [cruxWalls, setCruxWalls] = useState<ProviderSurface[]>([]);
  const [selectedBoardId, setSelectedBoardId] = useState(
    () => savedPrefsRef.current.lastKilter.boardId
  );
  const [selectedAngle, setSelectedAngle] = useState(
    () => savedPrefsRef.current.lastKilter.angle || DEFAULT_ANGLE
  );
  const [selectedGymSlug, setSelectedGymSlug] = useState(
    () => savedPrefsRef.current.lastCrux.gymSlug
  );
  const [selectedWallId, setSelectedWallId] = useState(
    () => savedPrefsRef.current.lastCrux.wallId
  );
  const [showOnboarding, setShowOnboarding] = useState(
    () =>
      savedPrefsRef.current.settings.autoGuidesEnabled &&
      !savedPrefsRef.current.onboarding.dismissed
  );
  const [manualOnboardingReplay, setManualOnboardingReplay] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [copiedInvite, setCopiedInvite] = useState(false);
  const [dragState, setDragState] = useState<{
    kind: "finalist" | "queue";
    entryId: number;
  } | null>(null);
  const [dragTarget, setDragTarget] = useState<{
    kind: "finalist" | "queue";
    entryId: number;
  } | null>(null);
  const cursorsRef = useRef<Record<number, string>>({});
  const lastFilterKeyRef = useRef("");
  const refreshRoomStateRef = useRef<() => Promise<void>>(async () => {});
  const kilterUsernameInputRef = useRef<HTMLInputElement>(null);
  const kilterPasswordInputRef = useRef<HTMLInputElement>(null);
  const cruxTokenInputRef = useRef<HTMLInputElement>(null);

  const search = searchParams.get("q") ?? "";
  const sort = normalizeSort(searchParams.get("sort"));
  const selectedClimbId = searchParams.get("climb") ?? "";
  const deferredSearch = useDeferredValue(search);
  const selectedClimbIdRef = useRef(selectedClimbId);
  const selectedExternalClimbRef = useRef<ProviderClimb | null>(selectedExternalClimb);
  const searchParamsRef = useRef(searchParams);

  const selectedClimb =
    catalog?.climbs.find((climb) => climb.id === selectedClimbId) ||
    (selectedExternalClimb?.id === selectedClimbId ? selectedExternalClimb : null) ||
    catalog?.climbs[0] ||
    null;
  const hasSurface = !!snapshot?.surface;
  const roomStatus = snapshot?.status;

  useEffect(() => {
    selectedClimbIdRef.current = selectedClimbId;
    selectedExternalClimbRef.current = selectedExternalClimb;
    searchParamsRef.current = searchParams;
  }, [searchParams, selectedClimbId, selectedExternalClimb]);

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
        rememberRoomVisit(nextSnapshot);
        rememberLastProvider(nextSnapshot.provider_id);
        if (nextSnapshot.can_manage && nextSnapshot.connection.connected) {
          markHostProviderConnected();
        }
        if (nextSnapshot.can_manage && nextSnapshot.surface) {
          markHostSurfaceSelected();
        }

        if (nextSnapshot.provider_id === "kilter") {
          const boardId =
            nextSnapshot.surface?.meta?.board_id || nextSnapshot.surface?.id || "";
          const angle = Number(nextSnapshot.surface?.meta?.angle ?? DEFAULT_ANGLE);
          setSelectedBoardId(boardId);
          setSelectedAngle(angle);
          if (boardId) {
            rememberLastKilterSurface(boardId, angle);
          }
        }

        if (nextSnapshot.provider_id === "crux") {
          const gymSlug =
            nextSnapshot.surface?.meta?.gym_slug || nextSnapshot.surface?.parent_id || "";
          setSelectedGymSlug(gymSlug);
          setSelectedWallId(nextSnapshot.surface?.id || "");
          if (gymSlug || nextSnapshot.surface?.id) {
            rememberLastCruxSurface(gymSlug, nextSnapshot.surface?.id || "");
          }
        }

        return nextSnapshot;
      } catch (caughtError) {
        console.error("Load room failed", caughtError);
        const statusCode = (
          caughtError as { response?: { status?: number } }
        )?.response?.status;
        if (statusCode === 401) {
          navigate(`/join/${encodeURIComponent(slug)}`, { replace: true });
          return null;
        }
        setSnapshot(null);
        setCatalog(null);
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
    [navigate, slug]
  );

  const fetchCatalog = useCallback(
    async (
      roomSnapshot: RoomSnapshot | null,
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
          pageSize: PAGE_SIZE,
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
        setActionError(
          getApiErrorMessage(caughtError, "Unable to load the climb catalog for this room.")
        );
        return null;
      } finally {
        if (showLoader) {
          setCatalogLoading(false);
        }
      }
    },
    [
      currentPage,
      deferredSearch,
      setSearchParams,
      slug,
      sort,
    ]
  );

  const refreshRoomState = useCallback(async () => {
    const nextSnapshot = await fetchSnapshot(false);
    if (nextSnapshot?.surface) {
      await fetchCatalog(nextSnapshot, false);
    }
  }, [fetchCatalog, fetchSnapshot]);

  useEffect(() => {
    refreshRoomStateRef.current = refreshRoomState;
  }, [refreshRoomState]);

  useEffect(() => {
    void fetchSnapshot(true);
  }, [fetchSnapshot]);

  useEffect(() => {
    if (!snapshot?.surface) {
      setCatalog(null);
      return;
    }

    const filterKey = JSON.stringify({
      slug,
      surfaceId: snapshot.surface.id,
      search: deferredSearch,
      sort,
    });
    const filtersChanged = lastFilterKeyRef.current !== filterKey;
    if (filtersChanged) {
      lastFilterKeyRef.current = filterKey;
      cursorsRef.current = {};
      if (currentPage !== 1) {
        setCurrentPage(1);
        return;
      }
    }

    void fetchCatalog(snapshot, true);
  }, [currentPage, deferredSearch, fetchCatalog, slug, snapshot, sort]);

  useEffect(() => {
    if (
      !slug ||
      !snapshot?.can_manage ||
      !snapshot.connection.connected ||
      (hasSurface && !showSurfaceEditor)
    ) {
      return;
    }

    const loadSurfaces = async () => {
      setSurfaceLoading(true);
      setActionError("");

      try {
        if (snapshot.provider_id === "kilter") {
          const nextBoards = await api.getRoomCatalogSurfaces(slug);
          setBoardSurfaces(nextBoards);
          setSelectedBoardId((currentValue) => {
            if (currentValue) {
              return currentValue;
            }
            const preferredBoardID = savedPrefsRef.current.lastKilter.boardId;
            if (preferredBoardID && nextBoards.some((surface) => surface.id === preferredBoardID)) {
              return preferredBoardID;
            }
            return nextBoards[0]?.id || "";
          });
          return;
        }

        const nextGyms = await api.getRoomCatalogSurfaces(slug);
        setCruxGyms(nextGyms);
        setSelectedGymSlug((currentValue) => {
          if (currentValue) {
            return currentValue;
          }
          const preferredGymSlug = savedPrefsRef.current.lastCrux.gymSlug;
          if (preferredGymSlug && nextGyms.some((surface) => surface.id === preferredGymSlug)) {
            return preferredGymSlug;
          }
          return nextGyms[0]?.id || "";
        });
      } catch (caughtError) {
        console.error("Load room surfaces failed", caughtError);
        setActionError(
          getApiErrorMessage(caughtError, "Unable to load provider surfaces for this room.")
        );
      } finally {
        setSurfaceLoading(false);
      }
    };

    void loadSurfaces();
  }, [
    hasSurface,
    showSurfaceEditor,
    slug,
    snapshot?.can_manage,
    snapshot?.connection.connected,
    snapshot?.provider_id,
    snapshot?.surface?.id,
  ]);

  useEffect(() => {
    if (
      !slug ||
      snapshot?.provider_id !== "crux" ||
      !snapshot.can_manage ||
      !snapshot.connection.connected ||
      (hasSurface && !showSurfaceEditor) ||
      !selectedGymSlug
    ) {
      return;
    }

    const loadWalls = async () => {
      setSurfaceLoading(true);

      try {
        const nextWalls = await api.getRoomCatalogSurfaces(slug, selectedGymSlug);
        setCruxWalls(nextWalls);
        setSelectedWallId((currentValue) => {
          if (currentValue) {
            return currentValue;
          }
          const preferredWallID = savedPrefsRef.current.lastCrux.wallId;
          if (preferredWallID && nextWalls.some((surface) => surface.id === preferredWallID)) {
            return preferredWallID;
          }
          return nextWalls[0]?.id || "";
        });
      } catch (caughtError) {
        console.error("Load room walls failed", caughtError);
        setActionError(
          getApiErrorMessage(caughtError, "Unable to load Crux walls for the selected gym.")
        );
      } finally {
        setSurfaceLoading(false);
      }
    };

    void loadWalls();
  }, [
    hasSurface,
    selectedGymSlug,
    showSurfaceEditor,
    slug,
    snapshot?.can_manage,
    snapshot?.connection.connected,
    snapshot?.provider_id,
    snapshot?.surface?.id,
  ]);

  useEffect(() => {
    if (
      !slug ||
      !roomStatus ||
      roomStatus === "closed" ||
      typeof EventSource === "undefined"
    ) {
      return;
    }

    let disposed = false;
    let retryTimeout: number | undefined;
    let currentSource: EventSource | null = null;
    let retryDelay = ROOM_EVENTS_INITIAL_RETRY_MS;

    const connect = () => {
      if (disposed) {
        return;
      }

      const eventSource = new EventSource(api.getRoomEventsUrl(slug), {
        withCredentials: true,
      });
      currentSource = eventSource;
      eventSource.addEventListener("room", () => {
        retryDelay = ROOM_EVENTS_INITIAL_RETRY_MS;
        void refreshRoomStateRef.current();
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
      if (retryTimeout !== undefined) window.clearTimeout(retryTimeout);
      currentSource?.close();
    };
  }, [roomStatus, slug]);

  useEffect(() => {
    if (!copiedInvite) {
      return;
    }

    const timeoutID = window.setTimeout(() => setCopiedInvite(false), 1800);
    return () => window.clearTimeout(timeoutID);
  }, [copiedInvite]);

  useEffect(() => {
    setRoomNameInput(snapshot?.room_name ?? "");
  }, [slug, snapshot?.room_name]);

  useEffect(() => {
    if (!actionError) {
      return;
    }

    showErrorToast(actionError);
  }, [actionError, showErrorToast]);

  const updateLocalFilters = (updates: Record<string, string | undefined>) => {
    startTransition(() => {
      const nextSearchParams = new URLSearchParams(searchParams);
      for (const [key, value] of Object.entries(updates)) {
        if (value && value.trim() !== "") {
          nextSearchParams.set(key, value);
        } else {
          nextSearchParams.delete(key);
        }
      }

      nextSearchParams.delete("climb");
      cursorsRef.current = {};
      setCurrentPage(1);
      setSelectedExternalClimb(null);
      setSearchParams(nextSearchParams);
    });
  };

  const selectClimb = (climb: ProviderClimb) => {
    const nextSearchParams = new URLSearchParams(searchParams);
    nextSearchParams.set("climb", climb.id);
    setSelectedExternalClimb(climb);
    setSearchParams(nextSearchParams, { replace: true });
  };

  const handleConnectProvider = async () => {
    if (!slug || !snapshot) {
      return;
    }

    setSurfaceLoading(true);
    setActionError("");

    try {
      if (snapshot.provider_id === "kilter") {
        const username =
          kilterUsernameInputRef.current?.value ?? connectionFields.username;
        const password =
          kilterPasswordInputRef.current?.value ?? connectionFields.password;
        setConnectionFields((previousState) => ({
          ...previousState,
          username,
          password,
        }));
        await api.connectRoomProvider(slug, {
          username,
          password,
        });
        savedPrefsRef.current = rememberKilterCredentials(
          username,
          password,
          rememberCredentials.kilter
        );
      } else {
        const token = cruxTokenInputRef.current?.value ?? connectionFields.token;
        setConnectionFields((previousState) => ({
          ...previousState,
          token,
        }));
        await api.connectRoomProvider(slug, {
          token,
        });
        savedPrefsRef.current = rememberCruxToken(token, rememberCredentials.crux);
      }
      markHostProviderConnected();
      await refreshRoomState();
    } catch (caughtError) {
      console.error("Connect provider failed", caughtError);
      setActionError(
        getApiErrorMessage(
          caughtError,
          "Unable to validate the provider credentials for this room."
        )
      );
    } finally {
      setSurfaceLoading(false);
    }
  };

  const handleSetSurface = async () => {
    if (!slug || !snapshot) {
      return;
    }

    setSurfaceLoading(true);
    setActionError("");

    try {
      if (snapshot.provider_id === "kilter") {
        await api.setRoomSurface(slug, {
          surfaceId: selectedBoardId,
          context: {
            angle: String(selectedAngle),
            board_id: selectedBoardId,
            parent_id: "",
          },
        });
      } else {
        await api.setRoomSurface(slug, {
          surfaceId: selectedWallId,
          context: {
            gym_slug: selectedGymSlug,
            parent_id: selectedGymSlug,
          },
        });
      }

      cursorsRef.current = {};
      setCurrentPage(1);
      markHostSurfaceSelected();
      await refreshRoomState();
      setShowSurfaceEditor(false);
    } catch (caughtError) {
      console.error("Set room surface failed", caughtError);
      setActionError(
        getApiErrorMessage(caughtError, "Unable to save the provider surface for this room.")
      );
    } finally {
      setSurfaceLoading(false);
    }
  };

  const handleCatalogRefresh = async () => {
    await refreshRoomState();
  };

  const handleEmojiReactionsToggle = async (enabled: boolean) => {
    if (!slug || !snapshot?.can_manage) {
      return;
    }

    setEmojiReactionsSaving(true);
    setActionError("");

    try {
      const updatedSnapshot = await api.setRoomEmojiReactionsEnabled(slug, enabled);
      setSnapshot(updatedSnapshot);
      rememberRoomVisit(updatedSnapshot);
    } catch (caughtError) {
      console.error("Update emoji reactions failed", caughtError);
      setActionError(
        getApiErrorMessage(caughtError, "Unable to update emoji reactions for this room.")
      );
    } finally {
      setEmojiReactionsSaving(false);
    }
  };

  const handleSendRoomReaction = async (emojiCode: RoomReactionCode) => {
    if (!slug) {
      return;
    }
    if (!snapshot?.emoji_reactions_enabled) {
      setActionError("The host has paused emoji reactions for this room.");
      return;
    }

    setReactionSendingCode(emojiCode);
    setActionError("");

    try {
      await api.sendRoomReaction(slug, emojiCode);
      if (!snapshot?.can_manage) {
        markGuestParticipated();
      }
      await refreshRoomState();
    } catch (caughtError) {
      console.error("Send room reaction failed", caughtError);
      setActionError(getApiErrorMessage(caughtError, "Unable to send this room reaction."));
    } finally {
      setReactionSendingCode(null);
    }
  };

  const handleVoteToggle = async (climbId: string) => {
    if (!slug) {
      return;
    }

    try {
      await api.toggleRoomVote(slug, climbId);
      if (!snapshot?.can_manage) {
        markGuestParticipated();
      }
      await refreshRoomState();
    } catch (caughtError) {
      console.error("Toggle vote failed", caughtError);
      setActionError("Unable to update the vote for this climb.");
    }
  };

  const handleQueueAdd = async (climbId: string) => {
    if (!slug) {
      return;
    }

    try {
      await api.addRoomQueueEntry(slug, climbId);
      if (!snapshot?.can_manage) {
        markGuestParticipated();
      }
      await refreshRoomState();
    } catch (caughtError) {
      console.error("Add queue entry failed", caughtError);
      setActionError("Unable to add this climb to the room queue.");
    }
  };

  const handleAddFinalist = async (climbId: string) => {
    if (!slug) {
      return;
    }

    try {
      await api.addRoomFinalist(slug, climbId);
      await refreshRoomState();
    } catch (caughtError) {
      console.error("Add finalist failed", caughtError);
      setActionError("Unable to add this climb to the finalists list.");
    }
  };

  const handleDeleteFinalist = async (entryId: number) => {
    if (!slug) {
      return;
    }

    try {
      await api.deleteRoomFinalist(slug, entryId);
      await refreshRoomState();
    } catch (caughtError) {
      console.error("Delete finalist failed", caughtError);
      setActionError("Unable to remove this finalist.");
    }
  };

  const handleReorderFinalists = async (sourceEntryId: number, targetEntryId: number) => {
    if (!slug || !snapshot) {
      return;
    }

    const entryIDs = snapshot.finalists.map((entry) => entry.id);
    const reordered = reorderEntryIDs(entryIDs, sourceEntryId, targetEntryId);
    if (!reordered) {
      return;
    }

    try {
      await api.reorderRoomFinalists(slug, reordered);
      await refreshRoomState();
    } catch (caughtError) {
      console.error("Reorder finalists failed", caughtError);
      setActionError("Unable to reorder finalists.");
    }
  };

  const handlePickRandom = async (source: "finalists" | "top_voted") => {
    if (!slug) {
      return;
    }

    try {
      const climb = await api.pickRandomRoomClimb(slug, source);
      selectClimb(climb);
    } catch (caughtError) {
      console.error("Random pick failed", caughtError);
      setActionError("Unable to pick a random climb for this room.");
    }
  };

  const handlePromoteClimb = async (climbId: string, status: "current" | "next") => {
    if (!slug) {
      return;
    }

    try {
      await api.promoteRoomQueueClimb(slug, climbId, status);
      await refreshRoomState();
    } catch (caughtError) {
      console.error("Promote climb failed", caughtError);
      setActionError("Unable to promote this climb in the queue.");
    }
  };

  const handleParticipantStatusUpdate = async (status: ParticipantStatus) => {
    if (!slug) {
      return;
    }

    try {
      await api.updateMyParticipantStatus(slug, status);
      await refreshRoomState();
    } catch (caughtError) {
      console.error("Participant status update failed", caughtError);
      setActionError("Unable to update your participation status.");
    }
  };

  const handleQueueStatusUpdate = async (entryId: number, status: QueueStatus) => {
    if (!slug) {
      return;
    }

    try {
      await api.updateRoomQueueEntry(slug, entryId, status);
      await refreshRoomState();
    } catch (caughtError) {
      console.error("Update queue entry failed", caughtError);
      setActionError("Unable to update the queue state.");
    }
  };

  const handleQueueDelete = async (entryId: number) => {
    if (!slug) {
      return;
    }

    try {
      await api.deleteRoomQueueEntry(slug, entryId);
      await refreshRoomState();
    } catch (caughtError) {
      console.error("Delete queue entry failed", caughtError);
      setActionError("Unable to remove this queue entry.");
    }
  };

  const handleReorderQueueEntry = async (sourceEntryId: number, targetEntryId: number) => {
    if (!slug || !snapshot) {
      return;
    }

    const entryIDs = snapshot.queue.map((queueEntry) => queueEntry.id);
    const reordered = reorderEntryIDs(entryIDs, sourceEntryId, targetEntryId);
    if (!reordered) {
      return;
    }

    try {
      await api.reorderRoomQueue(slug, reordered);
      await refreshRoomState();
    } catch (caughtError) {
      console.error("Reorder queue failed", caughtError);
      setActionError("Unable to reorder the queue.");
    }
  };

  const handleDragStart = (
    event: DragEvent<HTMLButtonElement>,
    kind: "finalist" | "queue",
    entryId: number
  ) => {
    setDragState({ kind, entryId });
    setDragTarget({ kind, entryId });
    if (event.dataTransfer) {
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", `${kind}:${entryId}`);
    }
  };

  const handleDragOver = (
    event: DragEvent<HTMLDivElement>,
    kind: "finalist" | "queue",
    entryId: number
  ) => {
    if (!dragState || dragState.kind !== kind || dragState.entryId === entryId) {
      return;
    }
    event.preventDefault();
    if (event.dataTransfer) {
      event.dataTransfer.dropEffect = "move";
    }
    setDragTarget({ kind, entryId });
  };

  const handleDragEnd = () => {
    setDragState(null);
    setDragTarget(null);
  };

  const handleDropReorder = async (
    event: DragEvent<HTMLDivElement>,
    kind: "finalist" | "queue",
    entryId: number
  ) => {
    if (!dragState || dragState.kind !== kind || dragState.entryId === entryId) {
      return;
    }

    event.preventDefault();
    try {
      if (kind === "finalist") {
        await handleReorderFinalists(dragState.entryId, entryId);
      } else {
        await handleReorderQueueEntry(dragState.entryId, entryId);
      }
    } finally {
      setDragState(null);
      setDragTarget(null);
    }
  };

  const handleClearVotes = async () => {
    if (!slug) {
      return;
    }

    try {
      await api.clearRoomVotes(slug);
      await refreshRoomState();
    } catch (caughtError) {
      console.error("Clear votes failed", caughtError);
      setActionError("Unable to clear votes for this room.");
    }
  };

  const handleCloseRoom = async () => {
    if (!slug) {
      return;
    }

    try {
      await api.closeRoom(slug);
      await refreshRoomState();
    } catch (caughtError) {
      console.error("Close room failed", caughtError);
      setActionError("Unable to close this room.");
    }
  };

  const handleRemoveParticipant = async (participantId: number) => {
    if (!slug) {
      return;
    }

    try {
      await api.removeRoomParticipant(slug, participantId);
      await refreshRoomState();
    } catch (caughtError) {
      console.error("Remove participant failed", caughtError);
      setActionError("Unable to remove this participant.");
    }
  };

  const copyInviteLink = async () => {
    if (typeof window === "undefined") {
      return;
    }

    const inviteLink = `${window.location.origin}/join/${slug}`;
    try {
      await navigator.clipboard.writeText(inviteLink);
      setCopiedInvite(true);
    } catch (caughtError) {
      console.error("Copy invite failed", caughtError);
      setActionError("Unable to copy the invite link from this browser.");
    }
  };

  const handleUpdateRoomName = async () => {
    if (!slug || !snapshot?.can_manage) {
      return;
    }

    setRoomNameSaving(true);
    setActionError("");

    try {
      const updatedSnapshot = await api.updateRoom(slug, {
        roomName: roomNameInput,
      });
      setSnapshot(updatedSnapshot);
      rememberRoomVisit(updatedSnapshot);
      setShowRoomSettings(false);
    } catch (caughtError) {
      console.error("Update room name failed", caughtError);
      setActionError(getApiErrorMessage(caughtError, "Unable to save the room name."));
    } finally {
      setRoomNameSaving(false);
    }
  };

  if (loading) {
    return (
      <LoadingSlideshow
        title="Loading room"
        description="Syncing the live session, invite state, and shared climb data."
        detail="This includes the room snapshot, participant list, and any shared board or wall context already selected by the host."
      />
    );
  }

  if (!snapshot) {
    return (
      <div className="min-h-screen px-6 py-10">
        <div className="mx-auto max-w-xl">
          <Button asChild variant="ghost" className="mb-6">
            <Link to="/">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Link>
          </Button>
          <Card>
            <CardHeader>
              <CardTitle>Room unavailable</CardTitle>
              <CardDescription>
                This room could not be loaded. Try the invite again or ask the host for a fresh
                link.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button asChild>
                <Link to={`/join/${slug}`}>Join room</Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  const selectedVoteCount =
    (selectedClimb ? catalog?.vote_counts[selectedClimb.id] : undefined) ??
    (selectedClimb ? snapshot.vote_counts[selectedClimb.id] : 0) ??
    0;
  const myVotes = catalog?.my_votes ?? snapshot.my_votes;
  const selectedHasMyVote = selectedClimb ? myVotes.includes(selectedClimb.id) : false;
  const selectedIsQueued = selectedClimb
    ? snapshot.queue.some((entry) => entry.climb.id === selectedClimb.id)
    : false;
  const selectedQueueEntry = selectedClimb
    ? snapshot.queue.find((entry) => entry.climb.id === selectedClimb.id)
    : undefined;
  const selectedIsFinalist = selectedClimb
    ? snapshot.finalists.some((entry) => entry.climb.id === selectedClimb.id)
    : false;
  const inviteLink = buildInviteLink(slug);
  const shouldShowRoomOnboarding =
    manualOnboardingReplay ||
    (showOnboarding &&
      (snapshot.can_manage
        ? !snapshot.connection.connected || !snapshot.surface
        : !loadUserPrefs().onboarding.guestCompleted));
  const myParticipant =
    snapshot.participants.find(
      (participant) => participant.display_name === snapshot.display_name
    ) ?? snapshot.participants[0];
  const liveParticipants = snapshot.participants.filter((participant) => participant.is_online);
  const readinessCounts = snapshot.participants.reduce(
    (totals, participant) => {
      totals[participant.status] += 1;
      return totals;
    },
    {
      watching: 0,
      ready: 0,
      resting: 0,
      away: 0,
    } as Record<ParticipantStatus, number>
  );

  const climbByID = new Map<string, ProviderClimb>();
  for (const climb of catalog?.climbs ?? []) {
    climbByID.set(climb.id, climb);
  }
  for (const entry of snapshot.queue) {
    climbByID.set(entry.climb.id, entry.climb);
  }
  for (const entry of snapshot.finalists) {
    climbByID.set(entry.climb.id, entry.climb);
  }
  if (snapshot.current_climb) {
    climbByID.set(snapshot.current_climb.id, snapshot.current_climb);
  }
  if (selectedExternalClimb) {
    climbByID.set(selectedExternalClimb.id, selectedExternalClimb);
  }

  const leaderboard = Array.from(climbByID.values())
    .filter((climb) => (snapshot.vote_counts[climb.id] ?? 0) > 0)
    .sort((left, right) => {
      const voteDelta =
        (snapshot.vote_counts[right.id] ?? 0) - (snapshot.vote_counts[left.id] ?? 0);
      if (voteDelta !== 0) {
        return voteDelta;
      }
      return left.name.localeCompare(right.name);
    })
    .slice(0, 5);
  const topVoteCount = leaderboard[0] ? snapshot.vote_counts[leaderboard[0].id] ?? 0 : 0;
  const topVoteTieCount = leaderboard.filter(
    (climb) => (snapshot.vote_counts[climb.id] ?? 0) === topVoteCount
  ).length;
  const roomTitle = snapshot.room_name?.trim() || `Room ${snapshot.slug}`;
  const roomNameChanged = roomNameInput.trim() !== (snapshot.room_name ?? "").trim();
  const providerLabel = formatProviderName(snapshot.provider_id);
  const motionEnabled = loadUserPrefs().settings.playfulMotionEnabled;
  const recentReactions = Array.isArray(snapshot.recent_reactions) ? snapshot.recent_reactions : [];
  const showSurfaceCard = snapshot.connection.connected && (snapshot.can_manage || !snapshot.surface);
  const surfaceEditorOpen =
    snapshot.can_manage && snapshot.connection.connected && (!snapshot.surface || showSurfaceEditor);
  const currentGymLabel =
    snapshot.provider_id === "crux"
      ? cruxGyms.find(
          (surface) =>
            surface.id === (snapshot.surface?.meta?.gym_slug || snapshot.surface?.parent_id || "")
        )?.name ||
        snapshot.surface?.meta?.gym_slug ||
        snapshot.surface?.parent_id ||
        "Choose a gym"
      : null;
  const roomSummaryItems: DetailGridItem[] = [
    {
      label: "Room slug",
      value: snapshot.slug,
      valueClassName: "break-all",
    },
    {
      label: "Signed in as",
      value: snapshot.display_name || "guest",
    },
    {
      label: "Shared surface",
      value: snapshot.surface?.name ?? (snapshot.can_manage ? "Not selected yet" : "Waiting for host"),
    },
    {
      label: "Current climb",
      value: snapshot.current_climb?.name ?? "Nothing live yet",
    },
    {
      label: "Readiness",
      value: `${readinessCounts.ready} ready · ${readinessCounts.resting} resting · ${readinessCounts.away} away`,
    },
  ];
  const surfaceSummaryItems: DetailGridItem[] = [
    {
      label: "Provider",
      value: providerLabel,
    },
    {
      label: snapshot.provider_id === "kilter" ? "Board" : "Wall",
      value: snapshot.surface?.name ?? "Not selected yet",
    },
    ...(snapshot.provider_id === "kilter"
      ? [
          {
            label: "Angle",
            value: snapshot.surface?.meta?.angle
              ? `${snapshot.surface.meta.angle}\u00b0`
              : "Choose an angle",
          },
        ]
      : [
          {
            label: "Gym",
            value: currentGymLabel ?? "Choose a gym",
          },
        ]),
  ];

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,_rgba(250,250,249,1),_rgba(240,249,255,0.8))] px-4 py-5 sm:px-6">
      <div className="mx-auto flex max-w-7xl flex-col gap-5">
        <header className="rounded-3xl border bg-card/95 px-5 py-5 shadow-sm">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-start xl:justify-between">
            <div className="min-w-0 flex-1 space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <Button asChild variant="ghost" className="-ml-3">
                  <Link to="/">
                    <ArrowLeft className="mr-2 h-4 w-4" />
                    Back
                  </Link>
                </Button>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-3xl font-semibold tracking-tight">{roomTitle}</h1>
                <Badge variant="secondary">{snapshot.provider_id}</Badge>
                <Badge variant={snapshot.status === "open" ? "default" : "secondary"}>
                  {snapshot.status}
                </Badge>
                {snapshot.surface ? <Badge variant="outline">{snapshot.surface.name}</Badge> : null}
              </div>
              <DetailGrid items={roomSummaryItems} className="lg:grid-cols-3 2xl:grid-cols-5" />
              <div className="rounded-2xl border bg-muted/20 px-4 py-3">
                <div className="space-y-3">
                  <div className="space-y-1">
                    <p className="text-[11px] uppercase tracking-[0.24em] text-muted-foreground">
                      Live participants
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {liveParticipants.length > 0
                        ? `${liveParticipants.length} currently online`
                        : "No participants are currently online."}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {liveParticipants.length > 0 ? (
                      liveParticipants.map((participant) => (
                        <Badge
                          key={participant.id}
                          variant="outline"
                          className="gap-2 rounded-full px-3 py-1 text-sm"
                        >
                          <span className="h-2 w-2 rounded-full bg-emerald-500" aria-hidden />
                          <span>{participant.display_name}</span>
                          <span className="text-xs text-muted-foreground">
                            {participant.status}
                          </span>
                        </Badge>
                      ))
                    ) : (
                      <Badge variant="outline" className="rounded-full px-3 py-1 text-sm">
                        Waiting for guests
                      </Badge>
                    )}
                  </div>
                </div>
              </div>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                {myParticipant ? (
                  <div className="flex max-w-xs items-center gap-3">
                    <span className="text-sm text-muted-foreground">My status</span>
                    <Select
                      value={myParticipant.status}
                      onValueChange={(value) =>
                        void handleParticipantStatusUpdate(value as ParticipantStatus)
                      }
                    >
                      <SelectTrigger className="h-9">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="watching">Watching</SelectItem>
                        <SelectItem value="ready">Ready</SelectItem>
                        <SelectItem value="resting">Resting</SelectItem>
                        <SelectItem value="away">Away</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                ) : (
                  <div />
                )}
                {snapshot.can_manage ? (
                  <Button
                    type="button"
                    variant={showRoomSettings ? "secondary" : "outline"}
                    onClick={() => setShowRoomSettings((currentValue) => !currentValue)}
                  >
                    {showRoomSettings ? "Hide room details" : "Edit room details"}
                  </Button>
                ) : null}
              </div>
              {snapshot.can_manage && showRoomSettings ? (
                <div className="rounded-2xl border bg-muted/20 p-4">
                  <div className="mb-3 space-y-1">
                    <p className="text-sm font-medium text-foreground">Room details</p>
                    <p className="text-sm text-muted-foreground">
                      Keep optional host settings tucked away until you need them.
                    </p>
                  </div>
                  <div className="grid max-w-xl gap-2">
                    <label htmlFor="room-name-input" className="text-sm text-muted-foreground">
                      Room name
                    </label>
                    <form
                      className="flex flex-col gap-2 sm:flex-row"
                      onSubmit={(event) => {
                        event.preventDefault();
                        void handleUpdateRoomName();
                      }}
                    >
                      <Input
                        id="room-name-input"
                        value={roomNameInput}
                        onChange={(event) => setRoomNameInput(event.target.value)}
                        placeholder="Name this room"
                      />
                      <Button
                        type="submit"
                        variant="outline"
                        disabled={roomNameSaving || !roomNameChanged}
                      >
                        {roomNameSaving
                          ? "Saving..."
                          : snapshot.room_name?.trim()
                            ? "Save name"
                            : "Set room name"}
                      </Button>
                    </form>
                  </div>
                </div>
              ) : null}
            </div>

            <div className="grid w-full min-w-0 gap-3 xl:w-[26rem] xl:shrink-0">
              <div className="flex flex-wrap justify-start gap-2 xl:justify-end">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setManualOnboardingReplay(true);
                    setShowOnboarding(true);
                  }}
                >
                  Help
                </Button>
                <Button asChild variant="ghost">
                  <Link to="/about">About</Link>
                </Button>
                <Button asChild variant="ghost">
                  <Link to="/settings">Settings</Link>
                </Button>
              </div>
              <div className="grid min-w-0 gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
                <div className="rounded-2xl border bg-muted/30 px-4 py-3">
                  <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
                    Invite link
                  </p>
                  <p className="mt-1 break-words text-sm leading-6">{inviteLink}</p>
                </div>
                <Button variant="outline" onClick={copyInviteLink}>
                  <Copy className="mr-2 h-4 w-4" />
                  {copiedInvite ? "Copied" : "Copy invite"}
                </Button>
              </div>
              <InviteQRCodeCard slug={slug} />
            </div>
          </div>
        </header>

        {shouldShowRoomOnboarding ? (
          <OnboardingCallout
            title={
              snapshot.can_manage
                ? snapshot.connection.connected
                  ? "Host flow: choose, then share"
                  : "Host flow: connect, choose, then share"
                : "Guest flow: vote and queue from your phone"
            }
            description={
              snapshot.can_manage
                ? snapshot.connection.connected
                  ? "You are the room host. The provider is already authenticated for this room, so the next step is picking the shared surface before you invite everyone else."
                  : "You are the room host. Finish the provider setup once, then everyone else can join through the invite link or QR code."
                : "You are already inside the room. The next useful action is to vote for a climb or add one to the shared queue."
            }
            steps={
              snapshot.can_manage
                ? [
                    snapshot.connection.connected
                      ? "Provider connected. Move on to the shared surface selection."
                      : "Connect the provider account for this room first.",
                    snapshot.surface
                      ? `Surface selected: ${snapshot.surface.name}.`
                      : "Choose the Kilter board plus angle, or the Crux gym plus wall.",
                    "Share the invite link or QR code, then watch votes and queue picks as guests join.",
                  ]
                : [
                    "Use Vote for climb to signal what you want to try next.",
                    "Use Add to queue when you want to propose a concrete running order.",
                    "Follow the current climb and next climb indicators to stay synced with the group.",
                  ]
            }
            onDismiss={() => {
              dismissOnboarding();
              setManualOnboardingReplay(false);
              setShowOnboarding(false);
            }}
          />
        ) : null}

        {!snapshot.connection.connected ? (
          <Card>
            <CardHeader>
              <CardTitle>Connect the host account</CardTitle>
              <CardDescription>
                {snapshot.can_manage
                  ? snapshot.provider_id === "kilter"
                    ? "Authenticate one Kilter account so the room can browse a shared board."
                    : "Enter one Crux API token so the room can browse a shared gym and wall."
                  : "Waiting for the host to connect the provider account before guests can browse climbs."}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {snapshot.can_manage ? (
                <>
                  {snapshot.provider_id === "kilter" ? (
                    <div className="grid gap-4 md:grid-cols-2">
                      <Input
                        ref={kilterUsernameInputRef}
                        value={connectionFields.username}
                        onChange={(event) =>
                          setConnectionFields((previousState) => ({
                            ...previousState,
                            username: event.target.value,
                          }))
                        }
                        autoComplete="username"
                        placeholder="Kilter username"
                      />
                      <Input
                        ref={kilterPasswordInputRef}
                        type="password"
                        value={connectionFields.password}
                        onChange={(event) =>
                          setConnectionFields((previousState) => ({
                            ...previousState,
                            password: event.target.value,
                          }))
                        }
                        autoComplete="current-password"
                        placeholder="Kilter password"
                      />
                      <div className="space-y-2 md:col-span-2">
                        <label className="flex items-center gap-3 text-sm font-medium">
                          <input
                            type="checkbox"
                            checked={rememberCredentials.kilter}
                            onChange={(event) =>
                              setRememberCredentials((previousState) => ({
                                ...previousState,
                                kilter: event.target.checked,
                              }))
                            }
                            className="h-4 w-4 rounded border-slate-300"
                          />
                          Remember Kilter username on this browser
                        </label>
                        <p className="text-xs text-muted-foreground">
                          Stores the username and this preference locally. You still enter the password each time.
                        </p>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <Input
                        ref={cruxTokenInputRef}
                        value={connectionFields.token}
                        onChange={(event) =>
                          setConnectionFields((previousState) => ({
                            ...previousState,
                            token: event.target.value,
                          }))
                        }
                        autoComplete="off"
                        placeholder="Crux API token"
                      />
                      <p className="text-sm text-muted-foreground">
                        Paste either the raw Crux token or the full <code>Bearer ...</code> value.
                      </p>
                      <label className="flex items-center gap-3 pt-1 text-sm font-medium">
                        <input
                          type="checkbox"
                          checked={rememberCredentials.crux}
                          onChange={(event) =>
                            setRememberCredentials((previousState) => ({
                              ...previousState,
                              crux: event.target.checked,
                            }))
                          }
                          className="h-4 w-4 rounded border-slate-300"
                        />
                        Remember this Crux auth preference on this browser
                      </label>
                      <p className="text-xs text-muted-foreground">
                        Stores this preference locally. You still enter the Crux token each time.
                      </p>
                    </div>
                  )}
                  <Button onClick={handleConnectProvider} disabled={surfaceLoading}>
                    {surfaceLoading ? "Connecting..." : "Connect provider"}
                  </Button>
                </>
              ) : null}
            </CardContent>
          </Card>
        ) : null}

        {showSurfaceCard ? (
          <Card>
            <CardHeader>
              <CardTitle>
                {snapshot.surface ? "Shared climbing surface" : "Choose the shared climbing surface"}
              </CardTitle>
              <CardDescription>
                {snapshot.can_manage
                  ? snapshot.surface
                    ? "Everyone in the room is browsing this board or wall. Open edit when you need to switch it."
                    : "This becomes the shared board or wall for everyone in the room."
                  : "Waiting for the host to choose the shared board or wall."}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <DetailGrid items={surfaceSummaryItems} className="lg:grid-cols-3" />
              {snapshot.can_manage && snapshot.surface ? (
                <Button
                  type="button"
                  variant={surfaceEditorOpen ? "secondary" : "outline"}
                  onClick={() => setShowSurfaceEditor((currentValue) => !currentValue)}
                >
                  {surfaceEditorOpen ? "Hide surface editor" : "Edit surface"}
                </Button>
              ) : null}
              {snapshot.can_manage && surfaceEditorOpen ? (
                snapshot.provider_id === "kilter" ? (
                  <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto]">
                    <div className="grid gap-4 md:grid-cols-2">
                      <Select value={selectedBoardId} onValueChange={setSelectedBoardId}>
                        <SelectTrigger>
                          <SelectValue placeholder="Select a Kilter board" />
                        </SelectTrigger>
                        <SelectContent>
                          {boardSurfaces.map((surface) => (
                            <SelectItem key={surface.id} value={surface.id}>
                              {surface.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <AngleSelector angle={selectedAngle} onAngleChange={setSelectedAngle} />
                    </div>
                    <Button
                      onClick={handleSetSurface}
                      disabled={!selectedBoardId || surfaceLoading}
                    >
                      {surfaceLoading
                        ? snapshot.surface
                          ? "Updating..."
                          : "Saving..."
                        : snapshot.surface
                          ? "Update board"
                          : "Save board"}
                    </Button>
                  </div>
                ) : (
                  <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto]">
                    <div className="grid gap-4 md:grid-cols-2">
                      <Select
                        value={selectedGymSlug}
                        onValueChange={(value) => {
                          setSelectedGymSlug(value);
                          setSelectedWallId("");
                        }}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select a Crux gym" />
                        </SelectTrigger>
                        <SelectContent>
                          {cruxGyms.map((surface) => (
                            <SelectItem key={surface.id} value={surface.id}>
                              {surface.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <Select value={selectedWallId} onValueChange={setSelectedWallId}>
                        <SelectTrigger>
                          <SelectValue placeholder="Select a wall" />
                        </SelectTrigger>
                        <SelectContent>
                          {cruxWalls.map((surface) => (
                            <SelectItem key={surface.id} value={surface.id}>
                              {surface.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <Button
                      onClick={handleSetSurface}
                      disabled={!selectedGymSlug || !selectedWallId || surfaceLoading}
                    >
                      {surfaceLoading
                        ? snapshot.surface
                          ? "Updating..."
                          : "Saving..."
                        : snapshot.surface
                          ? "Update wall"
                          : "Save wall"}
                    </Button>
                  </div>
                )
              ) : null}
            </CardContent>
          </Card>
        ) : null}

        {snapshot.surface ? (
          <>
            <section className="grid gap-4 lg:grid-cols-[18rem_minmax(0,1fr)_18rem]">
              <Card className="gap-4">
                <CardHeader className="pb-0">
                  <CardTitle>Catalog</CardTitle>
                  <CardDescription>Local filters for this device.</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3">
                  <Input
                    value={search}
                    onChange={(event) =>
                      updateLocalFilters({ q: event.target.value, sort })
                    }
                    placeholder="Search climbs"
                  />
                  <SortSelector
                    sort={sort}
                    onSortChange={(nextSort) =>
                      updateLocalFilters({ q: search, sort: nextSort })
                    }
                  />
                  <Button variant="outline" onClick={handleCatalogRefresh}>
                    <RefreshCw className="mr-2 h-4 w-4" />
                    Refresh room
                  </Button>

                  <div className="space-y-2 pt-2">
                    {catalogLoading ? (
                      <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
                        Loading climbs...
                      </div>
                    ) : catalog?.climbs.length ? (
                      catalog.climbs.map((climb) => {
                        const voteCount = catalog.vote_counts[climb.id] ?? 0;
                        const isQueued = snapshot.queue.some(
                          (entry) => entry.climb.id === climb.id
                        );
                        const finalistEntry = snapshot.finalists.find(
                          (entry) => entry.climb.id === climb.id
                        );
                        const queueEntry = snapshot.queue.find(
                          (entry) => entry.climb.id === climb.id
                        );

                        return (
                          <button
                            key={climb.id}
                            type="button"
                            onClick={() => selectClimb(climb)}
                            className={`w-full rounded-2xl border p-3 text-left transition-colors ${
                              selectedClimb?.id === climb.id
                                ? "border-primary bg-primary/5"
                                : "bg-card hover:bg-muted/40"
                            }`}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <p className="font-medium">{climb.name}</p>
                                <p className="mt-1 text-xs text-muted-foreground">
                                  {climb.setter_name || "Unknown setter"}
                                </p>
                              </div>
                              <div className="flex flex-col items-end gap-1">
                                <Badge variant="secondary">
                                  {climb.primary_grade || "Unknown"}
                                </Badge>
                                <Badge variant="outline">{voteCount} votes</Badge>
                                {isQueued ? <Badge variant="outline">Queued</Badge> : null}
                                {queueEntry?.status === "current" ? (
                                  <Badge>Current</Badge>
                                ) : null}
                                {queueEntry?.status === "next" ? (
                                  <Badge variant="outline">Next</Badge>
                                ) : null}
                                {finalistEntry ? <Badge variant="outline">Finalist</Badge> : null}
                              </div>
                            </div>
                          </button>
                        );
                      })
                    ) : (
                      <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
                        No climbs match the current search.
                      </div>
                    )}
                  </div>

                  <div className="flex items-center justify-between gap-2 pt-3">
                    <Button
                      variant="outline"
                      onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
                      disabled={currentPage === 1 || catalogLoading}
                    >
                      Previous
                    </Button>
                    <span className="text-sm text-muted-foreground">Page {currentPage}</span>
                    <Button
                      variant="outline"
                      onClick={() => setCurrentPage((page) => page + 1)}
                      disabled={!catalog?.has_more || catalogLoading}
                    >
                      Next
                    </Button>
                  </div>
                </CardContent>
              </Card>

              <div className="grid gap-4">
                <Card className="gap-4">
                  <CardHeader className="flex flex-row items-center justify-between gap-4 space-y-0">
                    <div>
                      <CardTitle>Climb detail</CardTitle>
                      <CardDescription>
                        Votes and queue actions affect the shared room state.
                      </CardDescription>
                    </div>
                    {selectedClimb ? (
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="secondary">{selectedVoteCount} votes</Badge>
                        {selectedIsQueued ? <Badge variant="outline">Queued</Badge> : null}
                        {selectedQueueEntry?.status === "current" ? <Badge>Current</Badge> : null}
                        {selectedQueueEntry?.status === "next" ? (
                          <Badge variant="outline">Next</Badge>
                        ) : null}
                        {selectedIsFinalist ? <Badge variant="outline">Finalist</Badge> : null}
                      </div>
                    ) : null}
                  </CardHeader>
                  <CardContent className="grid gap-4">
                    {selectedClimb ? (
                      <div className="flex flex-wrap gap-3">
                        <Button
                          onClick={() => handleVoteToggle(selectedClimb.id)}
                          disabled={snapshot.status === "closed"}
                        >
                          {selectedHasMyVote ? "Remove vote" : "Vote for climb"}
                        </Button>
                        <Button
                          variant="outline"
                          onClick={() => handleQueueAdd(selectedClimb.id)}
                          disabled={selectedIsQueued || snapshot.status === "closed"}
                        >
                          {selectedIsQueued ? "Already queued" : "Add to queue"}
                        </Button>
                        {snapshot.can_manage ? (
                          <>
                            <Button
                              variant="outline"
                              onClick={() => handleAddFinalist(selectedClimb.id)}
                              disabled={selectedIsFinalist || snapshot.status === "closed"}
                            >
                              {selectedIsFinalist ? "Already finalist" : "Add finalist"}
                            </Button>
                            <Button
                              variant="outline"
                              onClick={() => handlePromoteClimb(selectedClimb.id, "next")}
                              disabled={snapshot.status === "closed"}
                            >
                              Promote to next
                            </Button>
                            <Button
                              variant="outline"
                              onClick={() => handlePromoteClimb(selectedClimb.id, "current")}
                              disabled={snapshot.status === "closed"}
                            >
                              Promote to current
                            </Button>
                          </>
                        ) : null}
                      </div>
                    ) : null}
                    <RoomProblemView
                      climb={selectedClimb}
                      providerId={snapshot.provider_id}
                      hasResults={(catalog?.climbs.length ?? 0) > 0}
                      reactionsEnabled={snapshot.emoji_reactions_enabled}
                      canManage={snapshot.can_manage}
                      roomStatus={snapshot.status}
                      recentReactions={recentReactions}
                      motionEnabled={motionEnabled}
                      emojiReactionsSaving={emojiReactionsSaving}
                      reactionSendingCode={reactionSendingCode}
                      onSendReaction={(emojiCode) => void handleSendRoomReaction(emojiCode)}
                      onToggleReactions={(enabled) => void handleEmojiReactionsToggle(enabled)}
                    />
                  </CardContent>
                </Card>

                <Card className="gap-4">
                  <CardHeader>
                    <CardTitle>Leaderboard</CardTitle>
                    <CardDescription>
                      Highest-voted climbs visible in this room snapshot.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {leaderboard.length === 0 ? (
                      <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
                        Votes will surface the leaderboard once the group starts choosing climbs.
                      </div>
                    ) : (
                      <>
                        {topVoteCount > 0 && topVoteTieCount > 1 ? (
                          <div className="rounded-2xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-950">
                            There is currently a tie for first place across {topVoteTieCount} climbs.
                          </div>
                        ) : null}
                        {leaderboard.map((climb, index) => (
                          <button
                            key={climb.id}
                            type="button"
                            onClick={() => selectClimb(climb)}
                            className="flex w-full items-center justify-between rounded-2xl border p-3 text-left transition-colors hover:bg-muted/30"
                          >
                            <div>
                              <p className="font-medium">
                                #{index + 1} {climb.name}
                              </p>
                              <p className="mt-1 text-xs text-muted-foreground">
                                {climb.setter_name || "Unknown setter"}
                              </p>
                            </div>
                            <Badge variant="secondary">
                              {snapshot.vote_counts[climb.id] ?? 0} votes
                            </Badge>
                          </button>
                        ))}
                        {snapshot.can_manage ? (
                          <div className="flex flex-wrap gap-2 pt-2">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handlePickRandom("finalists")}
                              disabled={snapshot.finalists.length === 0}
                            >
                              Pick random finalist
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handlePickRandom("top_voted")}
                              disabled={leaderboard.length === 0}
                            >
                              Pick random top vote
                            </Button>
                          </div>
                        ) : null}
                      </>
                    )}
                  </CardContent>
                </Card>
              </div>

              <div className="grid gap-4">
                <Card className="gap-4">
                  <CardHeader>
                    <CardTitle>Finalists</CardTitle>
                    <CardDescription>
                      Host-managed shortlist for narrowing down the vote.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {snapshot.finalists.length === 0 ? (
                      <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
                        No finalists yet. Add one from the selected climb to narrow the field.
                      </div>
                    ) : (
                      snapshot.finalists.map((entry) => (
                        <div
                          key={entry.id}
                          role="group"
                          aria-label={`Finalist ${entry.climb.name}`}
                          onDragOver={(event) => handleDragOver(event, "finalist", entry.id)}
                          onDrop={(event) => void handleDropReorder(event, "finalist", entry.id)}
                          className={cn(
                            "rounded-2xl border p-3 transition-colors",
                            dragTarget?.kind === "finalist" && dragTarget.entryId === entry.id
                              ? "border-teal-500/60 bg-teal-50/50"
                              : ""
                          )}
                        >
                          <div className="flex items-start gap-3">
                            {snapshot.can_manage ? (
                              <Button
                                type="button"
                                size="icon"
                                variant="ghost"
                                draggable
                                aria-label={`Drag ${entry.climb.name} in finalists`}
                                className="mt-0.5 cursor-grab text-muted-foreground active:cursor-grabbing"
                                onDragStart={(event) => handleDragStart(event, "finalist", entry.id)}
                                onDragEnd={handleDragEnd}
                              >
                                <GripVertical className="h-4 w-4" />
                              </Button>
                            ) : null}
                            <button
                              type="button"
                              className="w-full min-w-0 text-left"
                              onClick={() => selectClimb(entry.climb)}
                            >
                              <div className="flex items-start justify-between gap-3">
                                <div className="min-w-0">
                                  <p className="font-medium">{entry.climb.name}</p>
                                  <p className="text-xs text-muted-foreground">
                                    Added by {entry.added_by}
                                  </p>
                                </div>
                                <Badge variant="secondary">
                                  {snapshot.vote_counts[entry.climb.id] ?? 0} votes
                                </Badge>
                              </div>
                            </button>
                          </div>
                          {snapshot.can_manage ? (
                            <div className="mt-3 flex flex-wrap gap-2">
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handlePromoteClimb(entry.climb.id, "next")}
                              >
                                Next
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handlePromoteClimb(entry.climb.id, "current")}
                              >
                                Current
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => handleDeleteFinalist(entry.id)}
                              >
                                <Trash2 className="mr-1 h-3.5 w-3.5" />
                                Remove
                              </Button>
                            </div>
                          ) : null}
                        </div>
                      ))
                    )}
                  </CardContent>
                </Card>

                <Card className="gap-4">
                  <CardHeader>
                    <CardTitle>Queue</CardTitle>
                    <CardDescription>
                      Shared running order for the session.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {snapshot.queue.length === 0 ? (
                      <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
                        Nothing is queued yet.
                      </div>
                    ) : (
                      snapshot.queue.map((entry) => (
                        <div
                          key={entry.id}
                          role="group"
                          aria-label={`Queue entry ${entry.climb.name}`}
                          onDragOver={(event) => handleDragOver(event, "queue", entry.id)}
                          onDrop={(event) => void handleDropReorder(event, "queue", entry.id)}
                          className={cn(
                            "rounded-2xl border p-3 transition-colors",
                            dragTarget?.kind === "queue" && dragTarget.entryId === entry.id
                              ? "border-teal-500/60 bg-teal-50/50"
                              : ""
                          )}
                        >
                          <div className="flex items-start gap-3">
                            {snapshot.can_manage ? (
                              <Button
                                type="button"
                                size="icon"
                                variant="ghost"
                                draggable
                                aria-label={`Drag ${entry.climb.name} in queue`}
                                className="mt-0.5 cursor-grab text-muted-foreground active:cursor-grabbing"
                                onDragStart={(event) => handleDragStart(event, "queue", entry.id)}
                                onDragEnd={handleDragEnd}
                              >
                                <GripVertical className="h-4 w-4" />
                              </Button>
                            ) : null}
                            <div className="flex-1 min-w-0">
                              <div className="flex items-start justify-between gap-3">
                                <div className="min-w-0">
                                  <p className="font-medium">{entry.climb.name}</p>
                                  <p className="text-xs text-muted-foreground">
                                    Added by {entry.added_by}
                                  </p>
                                </div>
                                <Badge variant="outline">{entry.status}</Badge>
                              </div>
                            </div>
                          </div>
                          {snapshot.can_manage ? (
                            <div className="mt-3 flex flex-wrap gap-2">
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() =>
                                  handleQueueStatusUpdate(entry.id, "current")
                                }
                              >
                                Current
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleQueueStatusUpdate(entry.id, "next")}
                              >
                                Next
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleQueueStatusUpdate(entry.id, "done")}
                              >
                                Done
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => handleQueueDelete(entry.id)}
                              >
                                <Trash2 className="mr-1 h-3.5 w-3.5" />
                                Remove
                              </Button>
                            </div>
                          ) : null}
                        </div>
                      ))
                    )}
                  </CardContent>
                </Card>

                <Card className="gap-4">
                  <CardHeader>
                    <CardTitle>Participants</CardTitle>
                    <CardDescription>
                      {snapshot.participants.length} devices currently joined.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {snapshot.participants.map((participant) => (
                        <div
                          key={participant.id}
                          className="flex items-center justify-between gap-3 rounded-2xl border p-3"
                        >
                          <div>
                            <p className="font-medium">{participant.display_name}</p>
                            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                              <span>
                                {participant.role} · {participant.is_online ? "online" : "idle"}
                              </span>
                              <Badge variant="outline">{participant.status}</Badge>
                            </div>
                          </div>
                          {snapshot.can_manage && participant.role !== "host" ? (
                            <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleRemoveParticipant(participant.id)}
                          >
                            <UserMinus className="mr-1 h-3.5 w-3.5" />
                            Remove
                          </Button>
                        ) : null}
                      </div>
                    ))}

                    {snapshot.can_manage ? (
                      <div className="flex flex-wrap gap-2 pt-2">
                        <Button variant="outline" onClick={handleClearVotes}>
                          Clear votes
                        </Button>
                        <Button variant="destructive" onClick={handleCloseRoom}>
                          Close room
                        </Button>
                      </div>
                    ) : null}
                  </CardContent>
                </Card>
              </div>
            </section>
          </>
        ) : null}
      </div>
    </div>
  );
}
