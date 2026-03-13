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
  CircleHelp,
  ChevronDown,
  ChevronUp,
  Copy,
  GripVertical,
  Info,
  RefreshCw,
  Settings2,
  Share2,
  Sparkles,
  Trash2,
  UserMinus,
} from "lucide-react";
import { api } from "@/api";
import type {
  ParticipantStatus,
  PendingRoomSeed,
  ProviderClimb,
  ProviderSurface,
  QueueStatus,
  RoomSnapshot,
} from "@/types";
import { copyTextToClipboard, isShareAbortError } from "@/lib/clipboard";
import { DEFAULT_ANGLE, normalizeSort } from "@/lib/climbs";
import { getApiErrorMessage } from "@/lib/api-errors";
import { buildInviteLink } from "@/lib/room-links";
import { cn } from "@/lib/utils";
import { useRoomCatalog } from "@/features/room/hooks/useRoomCatalog";
import { useRoomEvents } from "@/features/room/hooks/useRoomEvents";
import { useRoomSession } from "@/features/room/hooks/useRoomSession";
import {
  clearPendingSoloRoomSeed,
  completeGuideBranch,
  loadUserPrefs,
  markFeedbackPromptSeen,
  rememberCruxToken,
  rememberKilterCredentials,
  rememberLastCruxSurface,
  rememberLastKilterSurface,
  rememberLastProvider,
  rememberRoomVisit,
  resetGuides,
  shouldShowFeedbackPrompt,
} from "@/lib/user-prefs";
import CoachMarkOverlay, { type CoachMarkStep } from "@/components/CoachMarkOverlay";
import DetailGrid, { type DetailGridItem } from "@/components/DetailGrid";
import FeedbackPrompt from "@/components/FeedbackPrompt";
import RoomProblemView from "@/components/RoomProblemView";
import RoomFistBumpButton from "@/components/RoomFistBumpButton";
import InviteQRCodeCard from "@/components/InviteQRCodeCard";
import HeaderNavRail from "@/components/HeaderNavRail";
import MobilePageHeader from "@/components/MobilePageHeader";
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
import { SecretInput } from "@/components/ui/secret-input";
import { useErrorToast } from "@/hooks/use-toast";
import { useIsMobile } from "@/hooks/use-mobile";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useProviderCapabilities } from "@/hooks/useProviderCapabilities";
import {
  getProviderLabel,
  usesNestedSurfaceHierarchy,
} from "@/lib/provider-capabilities";
import { trackProductEvent } from "@/lib/product-analytics";

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

function formatParticipantRole(role: string) {
  return role === "co_host" ? "co-host" : role;
}

function formatProviderCatalogMeta(climb: ProviderClimb) {
  const parts = [
    climb.meta?.source_label,
    climb.meta?.color,
    climb.meta?.foot_rules,
  ].filter((value): value is string => Boolean(value?.trim()));

  if (parts.length > 0) {
    return parts.join(" · ");
  }

  if (climb.provider_id === "crux" && climb.meta?.gym_name) {
    return climb.meta.gym_name;
  }

  return null;
}

const HOST_ROOM_GUIDE_STEPS: CoachMarkStep[] = [
  {
    target: '[data-guide="room-share"]',
    title: "Share from the room header",
    description: "Hosts can copy or share the invite from the same mobile screen they use to run the session.",
  },
  {
    target: '[data-guide="room-current"]',
    title: "Keep the current climb visible",
    description: "This section is the host control point for what is live now and what should go next.",
  },
  {
    target: '[data-guide="room-queue"]',
    title: "Use the queue as the running order",
    description: "Votes and finalists suggest what matters, but the queue is the committed order for the round.",
  },
  {
    target: '[data-guide="room-people"]',
    title: "Watch readiness before you switch climbs",
    description: "The people section shows who is ready, resting, or away so the host can pace the session.",
    placement: "top",
  },
];

const GUEST_ROOM_GUIDE_STEPS: CoachMarkStep[] = [
  {
    target: '[data-guide="room-current"]',
    title: "Stay synced from current and next",
    description: "This section tells you what is on the wall now and what is likely to follow.",
  },
  {
    target: '[data-guide="room-vote"]',
    title: "Vote and queue from the climb detail",
    description: "Guests use fist bumps and queue actions here instead of relying on the host device.",
  },
  {
    target: '[data-guide="room-queue"]',
    title: "The queue is the room contract",
    description: "Check this list to understand what is actually coming up after the current climb.",
  },
  {
    target: '[data-guide="room-people"]',
    title: "Update your status as the round changes",
    description: "Mark yourself ready, resting, or away so the room can make better next-pick decisions.",
    placement: "top",
  },
];

function pendingSeedMatchesSurface(
  snapshot: RoomSnapshot,
  pendingRoomSeed?: PendingRoomSeed
) {
  if (!pendingRoomSeed || !snapshot.surface || snapshot.provider_id !== pendingRoomSeed.provider_id) {
    return false;
  }

  if ((snapshot.surface.id || "") !== (pendingRoomSeed.surface.id || "")) {
    return false;
  }

  const roomAngle = snapshot.surface.meta?.angle || "";
  const seedAngle = pendingRoomSeed.surface.meta?.angle || "";
  if ((roomAngle || seedAngle) && roomAngle !== seedAngle) {
    return false;
  }

  const roomParent =
    snapshot.surface.meta?.gym_slug ||
    snapshot.surface.meta?.parent_id ||
    snapshot.surface.parent_id ||
    "";
  const seedParent =
    pendingRoomSeed.surface.meta?.gym_slug ||
    pendingRoomSeed.surface.meta?.parent_id ||
    pendingRoomSeed.surface.parent_id ||
    "";

  return !(roomParent || seedParent) || roomParent === seedParent;
}

export default function RoomView() {
  const { slug = "" } = useParams();
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const { capabilities } = useProviderCapabilities();
  const showErrorToast = useErrorToast();
  const savedPrefsRef = useRef(loadUserPrefs());
  const [prefs, setPrefs] = useState(() => savedPrefsRef.current);
  const [searchParams, setSearchParams] = useSearchParams();
  const [pendingRoomSeed, setPendingRoomSeed] = useState(
    () => savedPrefsRef.current.pendingRoomSeed
  );
  const [selectedExternalClimb, setSelectedExternalClimb] = useState<ProviderClimb | null>(null);
  const [surfaceLoading, setSurfaceLoading] = useState(false);
  const [roomNameInput, setRoomNameInput] = useState("");
  const [roomNameSaving, setRoomNameSaving] = useState(false);
  const [fistBumpsSaving, setFistBumpsSaving] = useState(false);
  const [pendingFistBumpClimbId, setPendingFistBumpClimbId] = useState("");
  const [showRoomSettings, setShowRoomSettings] = useState(false);
  const [showSurfaceEditor, setShowSurfaceEditor] = useState(false);
  const [showConnectionEditor, setShowConnectionEditor] = useState(true);
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
  const [showGuide, setShowGuide] = useState(false);
  const [showCloseFeedback, setShowCloseFeedback] = useState(false);
  const [importingSoloSeed, setImportingSoloSeed] = useState(false);
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
  const wakeLockRef = useRef<{ release?: () => Promise<void> } | null>(null);

  const search = searchParams.get("q") ?? "";
  const sort = normalizeSort(searchParams.get("sort"));
  const selectedClimbId = searchParams.get("climb") ?? "";
  const deferredSearch = useDeferredValue(search);
  const selectedClimbIdRef = useRef(selectedClimbId);
  const selectedExternalClimbRef = useRef<ProviderClimb | null>(selectedExternalClimb);
  const searchParamsRef = useRef(searchParams);
  const capabilitiesRef = useRef(capabilities);

  useEffect(() => {
    capabilitiesRef.current = capabilities;
  }, [capabilities]);

  const handleSnapshotLoaded = useCallback(
    (nextSnapshot: RoomSnapshot) => {
      rememberRoomVisit(nextSnapshot);
      rememberLastProvider(nextSnapshot.provider_id);

      if (nextSnapshot.provider_id === "kilter") {
        const boardId = nextSnapshot.surface?.meta?.board_id || nextSnapshot.surface?.id || "";
        const angle = Number(nextSnapshot.surface?.meta?.angle ?? DEFAULT_ANGLE);
        setSelectedBoardId(boardId);
        setSelectedAngle(angle);
        if (boardId) {
          rememberLastKilterSurface(boardId, angle);
        }
      }

      if (
        usesNestedSurfaceHierarchy(
          nextSnapshot.provider_id,
          capabilitiesRef.current
        )
      ) {
        const gymSlug =
          nextSnapshot.surface?.meta?.gym_slug || nextSnapshot.surface?.parent_id || "";
        setSelectedGymSlug(gymSlug);
        setSelectedWallId(nextSnapshot.surface?.id || "");
        if (gymSlug || nextSnapshot.surface?.id) {
          rememberLastCruxSurface(gymSlug, nextSnapshot.surface?.id || "");
        }
      }
    },
    []
  );

  const navigateToJoin = useCallback(
    (nextSlug: string, reason?: string) => {
      const nextPath = reason
        ? `/join/${encodeURIComponent(nextSlug)}?reason=${encodeURIComponent(reason)}`
        : `/join/${encodeURIComponent(nextSlug)}`;
      navigate(nextPath, { replace: true });
    },
    [navigate]
  );

  const {
    actionError,
    fetchSnapshot,
    loading,
    setActionError,
    setSnapshot,
    snapshot,
  } = useRoomSession({
    slug,
    navigateToJoin,
    onLoaded: handleSnapshotLoaded,
  });

  const {
    catalog,
    catalogLoading,
    fetchCatalog,
    setCatalog,
  } = useRoomCatalog({
    slug,
    currentPage,
    deferredSearch,
    searchParamsRef,
    selectedClimbIdRef,
    selectedExternalClimbRef,
    setSearchParams,
    sort,
  });

  const selectedClimb =
    catalog?.climbs.find((climb) => climb.id === selectedClimbId) ||
    (selectedExternalClimb?.id === selectedClimbId ? selectedExternalClimb : null) ||
    catalog?.climbs[0] ||
    null;
  const hasSurface = !!snapshot?.surface;
  const roomStatus = snapshot?.status;
  const fistBumpsBlocked =
    snapshot?.status === "closed" || snapshot?.fist_bumps_enabled === false;

  useEffect(() => {
    selectedClimbIdRef.current = selectedClimbId;
    selectedExternalClimbRef.current = selectedExternalClimb;
    searchParamsRef.current = searchParams;
  }, [searchParams, selectedClimbId, selectedExternalClimb]);

  const refreshRoomState = useCallback(async () => {
    const nextSnapshot = await fetchSnapshot(false);
    if (nextSnapshot?.surface) {
      try {
        await fetchCatalog(nextSnapshot, cursorsRef, false);
      } catch (caughtError) {
        setActionError(
          caughtError instanceof Error
            ? caughtError.message
            : "Unable to load the climb catalog for this room."
        );
      }
    }
  }, [fetchCatalog, fetchSnapshot, setActionError]);

  const refreshCatalogOnly = useCallback(async () => {
    if (!snapshot?.surface) {
      setCatalog(null);
      return;
    }

    try {
      await fetchCatalog(snapshot, cursorsRef, false);
    } catch (caughtError) {
      setActionError(
        caughtError instanceof Error
          ? caughtError.message
          : "Unable to load the climb catalog for this room."
      );
    }
  }, [fetchCatalog, setActionError, setCatalog, snapshot]);

  useEffect(() => {
    refreshRoomStateRef.current = refreshRoomState;
  }, [refreshRoomState]);

  const refreshRoomOnly = useCallback(async () => {
    await fetchSnapshot(false);
  }, [fetchSnapshot]);

  const refreshRoomAndCatalog = useCallback(async () => {
    await refreshRoomStateRef.current();
  }, []);

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

    void (async () => {
      try {
        await fetchCatalog(snapshot, cursorsRef, true);
      } catch (caughtError) {
        setActionError(
          caughtError instanceof Error
            ? caughtError.message
            : "Unable to load the climb catalog for this room."
        );
      }
    })();
  }, [currentPage, deferredSearch, fetchCatalog, setActionError, setCatalog, slug, snapshot, sort]);

  useEffect(() => {
    if (
      !slug ||
      !snapshot?.permissions.manage_surface ||
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
    setActionError,
    showSurfaceEditor,
    slug,
    snapshot?.permissions.manage_surface,
    snapshot?.connection.connected,
    snapshot?.provider_id,
    snapshot?.surface?.id,
  ]);

  useEffect(() => {
    if (
      !slug ||
      !snapshot?.provider_id ||
      !usesNestedSurfaceHierarchy(snapshot.provider_id, capabilities) ||
      !snapshot.permissions.manage_surface ||
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
          getApiErrorMessage(caughtError, "Unable to load walls for the selected gym.")
        );
      } finally {
        setSurfaceLoading(false);
      }
    };

    void loadWalls();
  }, [
    capabilities,
    hasSurface,
    selectedGymSlug,
    setActionError,
    showSurfaceEditor,
    slug,
    snapshot?.permissions.manage_surface,
    snapshot?.connection.connected,
    snapshot?.provider_id,
    snapshot?.surface?.id,
  ]);

  useRoomEvents({
    slug,
    roomStatus,
    refreshRoom: refreshRoomOnly,
    refreshCatalog: refreshCatalogOnly,
    refreshRoomAndCatalog,
  });

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
        if (snapshot.provider_id === "crux") {
          savedPrefsRef.current = rememberCruxToken(token, rememberCredentials.crux);
        }
      }
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

  const handleDiscardSoloSeed = () => {
    const nextPrefs = clearPendingSoloRoomSeed();
    savedPrefsRef.current = nextPrefs;
    setPrefs(nextPrefs);
    setPendingRoomSeed(undefined);
  };

  const handleImportSoloSeed = async () => {
    if (!slug || !pendingRoomSeed) {
      return;
    }

    const pendingClimbs = pendingRoomSeed.climbs.filter(
      (climb) => !queuedClimbIds.has(climb.id)
    );

    if (pendingClimbs.length === 0) {
      handleDiscardSoloSeed();
      return;
    }

    setImportingSoloSeed(true);
    setActionError("");

    try {
      for (const climb of pendingClimbs) {
        await api.addRoomQueueEntry(slug, climb.id);
      }
      handleDiscardSoloSeed();
      await refreshRoomState();
    } catch (caughtError) {
      console.error("Import room seed failed", caughtError);
      setActionError("Unable to import the saved plan into this room queue.");
    } finally {
      setImportingSoloSeed(false);
    }
  };

  const handleFistBumpsToggle = async (enabled: boolean) => {
    if (!slug || !snapshot?.permissions.edit_room_settings) {
      return;
    }

    setFistBumpsSaving(true);
    setActionError("");

    try {
      const updatedSnapshot = await api.setRoomFistBumpsEnabled(slug, enabled);
      setSnapshot(updatedSnapshot);
      rememberRoomVisit(updatedSnapshot);
    } catch (caughtError) {
      console.error("Update fist bumps failed", caughtError);
      setActionError(
        getApiErrorMessage(caughtError, "Unable to update fist bumps for this room.")
      );
    } finally {
      setFistBumpsSaving(false);
    }
  };

  const handleFistBumpToggle = async (climbId: string) => {
    if (!slug || !snapshot?.fist_bumps_enabled) {
      if (!snapshot?.fist_bumps_enabled) {
        setActionError("The host has disabled fist bumps for this room.");
      }
      return;
    }

    setPendingFistBumpClimbId(climbId);
    setActionError("");

    try {
      await api.toggleRoomVote(slug, climbId);
      await refreshRoomState();
    } catch (caughtError) {
      console.error("Toggle fist bump failed", caughtError);
      setActionError(
        getApiErrorMessage(caughtError, "Unable to update the fist bump for this climb.")
      );
    } finally {
      setPendingFistBumpClimbId("");
    }
  };

  const handleQueueAdd = async (climbId: string) => {
    if (!slug) {
      return;
    }

    try {
      await api.addRoomQueueEntry(slug, climbId);
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

  const handleMoveFinalist = async (entryId: number, direction: "up" | "down") => {
    const currentIndex = snapshot?.finalists.findIndex((entry) => entry.id === entryId) ?? -1;
    if (!snapshot || currentIndex < 0) {
      return;
    }

    const targetIndex = direction === "up" ? currentIndex - 1 : currentIndex + 1;
    const targetEntry = snapshot.finalists[targetIndex];
    if (!targetEntry) {
      return;
    }

    await handleReorderFinalists(entryId, targetEntry.id);
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

  const handleMoveQueueEntry = async (entryId: number, direction: "up" | "down") => {
    const currentIndex = snapshot?.queue.findIndex((entry) => entry.id === entryId) ?? -1;
    if (!snapshot || currentIndex < 0) {
      return;
    }

    const targetIndex = direction === "up" ? currentIndex - 1 : currentIndex + 1;
    const targetEntry = snapshot.queue[targetIndex];
    if (!targetEntry) {
      return;
    }

    await handleReorderQueueEntry(entryId, targetEntry.id);
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
      setActionError("Unable to clear fist bumps for this room.");
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

  const handleParticipantRoleUpdate = async (
    participantId: number,
    role: "participant" | "co_host"
  ) => {
    if (!slug) {
      return;
    }

    try {
      await api.updateRoomParticipantRole(slug, participantId, role);
      await refreshRoomState();
    } catch (caughtError) {
      console.error("Update participant role failed", caughtError);
      setActionError("Unable to update this participant role.");
    }
  };

  const copyInviteLink = async () => {
    try {
      if (isMobile && typeof navigator !== "undefined" && typeof navigator.share === "function") {
        try {
          await navigator.share({
            title: snapshot?.room_name || "Join climbing room",
            url: inviteLink,
          });
          trackProductEvent("room.share", {
            roomSlug: slug,
            viewerRole: canManageSession ? "host" : "guest",
            properties: {
              method: "navigator_share",
            },
          });
          return;
        } catch (caughtError) {
          if (isShareAbortError(caughtError)) {
            return;
          }
        }
      }

      const method = await copyTextToClipboard(inviteLink);
      setCopiedInvite(true);
      trackProductEvent("room.share", {
        roomSlug: slug,
        viewerRole: canManageSession ? "host" : "guest",
        properties: {
          method,
        },
      });
    } catch (caughtError) {
      console.error("Copy invite failed", caughtError);
      setActionError("Unable to copy the invite link from this browser.");
    }
  };

  const handleUpdateRoomName = async () => {
    if (!slug || !snapshot?.permissions.edit_room_settings) {
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

  useEffect(() => {
    if (!snapshot) {
      return;
    }

    const branch = snapshot.permissions.manage_session ? "host" : "guest";
    const branchCompleted =
      branch === "host" ? prefs.guidedTour.hostCompleted : prefs.guidedTour.guestCompleted;

    if (
      isMobile &&
      prefs.settings.autoGuidesEnabled &&
      prefs.guidedTour.activeBranch === branch &&
      !branchCompleted
    ) {
      setShowGuide(true);
    }
  }, [
    isMobile,
    prefs.guidedTour.activeBranch,
    prefs.guidedTour.guestCompleted,
    prefs.guidedTour.hostCompleted,
    prefs.settings.autoGuidesEnabled,
    snapshot,
  ]);

  useEffect(() => {
    if (
      !snapshot ||
      snapshot.status !== "closed" ||
      !snapshot.permissions.close_room ||
      !shouldShowFeedbackPrompt("room-close")
    ) {
      return;
    }

    setShowCloseFeedback(true);
  }, [snapshot]);

  useEffect(() => {
    if (
      !isMobile ||
      snapshot?.status !== "open" ||
      typeof window === "undefined" ||
      typeof document === "undefined"
    ) {
      return;
    }

    const navigatorWithWakeLock = navigator as Navigator & {
      wakeLock?: {
        request: (
          type: "screen"
        ) => Promise<{ release?: () => Promise<void>; addEventListener?: (name: string, listener: () => void) => void }>;
      };
    };

    if (!navigatorWithWakeLock.wakeLock?.request) {
      return;
    }

    let active = true;

    const requestWakeLock = async () => {
      try {
        const lock = await navigatorWithWakeLock.wakeLock?.request("screen");
        if (!active) {
          await lock?.release?.();
          return;
        }
        wakeLockRef.current = lock ?? null;
      } catch {
        wakeLockRef.current = null;
      }
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible" && !wakeLockRef.current) {
        void requestWakeLock();
      }
    };

    void requestWakeLock();
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      active = false;
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      const lock = wakeLockRef.current;
      wakeLockRef.current = null;
      void lock?.release?.();
    };
  }, [isMobile, snapshot?.status]);

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

  const permissions = snapshot.permissions;
  const canManageSession = permissions.manage_session;
  const canManageSurface = permissions.manage_surface;
  const canManageQueue = permissions.manage_queue;
  const canManageFinalists = permissions.manage_finalists;
  const canEditRoomSettings = permissions.edit_room_settings;
  const canManageParticipants = permissions.manage_participants;
  const canAssignCoHosts = permissions.assign_co_hosts;
  const canCloseRoom = permissions.close_room;

  const selectedFistBumpCount =
    (selectedClimb ? catalog?.vote_counts[selectedClimb.id] : undefined) ??
    (selectedClimb ? snapshot.vote_counts[selectedClimb.id] : 0) ??
    0;
  const myFistBumps = catalog?.my_votes ?? snapshot.my_votes;
  const queuedClimbIds = new Set(snapshot.queue.map((entry) => entry.climb.id));
  const pendingRoomSeedHasClimbs = (pendingRoomSeed?.climbs.length ?? 0) > 0;
  const pendingRoomSeedMatchesSurface = pendingSeedMatchesSurface(snapshot, pendingRoomSeed);
  const pendingRoomSeedQueuedClimbs =
    pendingRoomSeed?.climbs.filter((climb) => !queuedClimbIds.has(climb.id)) ?? [];
  const selectedHasMyFistBump = selectedClimb ? myFistBumps.includes(selectedClimb.id) : false;
  const selectedIsQueued = selectedClimb ? queuedClimbIds.has(selectedClimb.id) : false;
  const selectedQueueEntry = selectedClimb
    ? snapshot.queue.find((entry) => entry.climb.id === selectedClimb.id)
    : undefined;
  const selectedIsFinalist = selectedClimb
    ? snapshot.finalists.some((entry) => entry.climb.id === selectedClimb.id)
    : false;
  const inviteLink = buildInviteLink(slug);
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
  const providerLabel = getProviderLabel(snapshot.provider_id, capabilities);
  const nestedSurfaceProvider = usesNestedSurfaceHierarchy(
    snapshot.provider_id,
    capabilities
  );
  const showSurfaceCard = snapshot.connection.connected && (canManageSurface || !snapshot.surface);
  const surfaceEditorOpen =
    canManageSurface && snapshot.connection.connected && (!snapshot.surface || showSurfaceEditor);
  const currentGymLabel =
    nestedSurfaceProvider
      ? cruxGyms.find(
          (surface) =>
            surface.id === (snapshot.surface?.meta?.gym_slug || snapshot.surface?.parent_id || "")
        )?.name ||
        snapshot.surface?.meta?.gym_slug ||
        snapshot.surface?.parent_id ||
        "Choose a gym"
      : null;
  const surfaceSummaryItems: DetailGridItem[] = [
    {
      label: "Provider",
      value: providerLabel,
    },
    {
      label: nestedSurfaceProvider ? "Wall" : "Board",
      value: snapshot.surface?.name ?? "Not selected yet",
    },
    ...(nestedSurfaceProvider
      ? [
          {
            label: "Gym",
            value: currentGymLabel ?? "Choose a gym",
          },
        ]
      : [
          {
            label: "Angle",
            value: snapshot.surface?.meta?.angle
              ? `${snapshot.surface.meta.angle}\u00b0`
              : "Choose an angle",
          },
        ]),
  ];

  const roomReadyToShare =
    canManageSession && snapshot.connection.connected && Boolean(snapshot.surface);
  const canShareInvite =
    typeof navigator !== "undefined" && typeof navigator.share === "function";
  const invitePath = `/join/${slug}`;
  const signedInAs = snapshot.display_name || "guest";
  const sharedSurfaceLabel =
    snapshot.surface?.name ?? (canManageSurface ? "Not selected yet" : "Waiting for host");
  const currentClimbLabel = snapshot.current_climb?.name ?? "Nothing live yet";
  const guideSteps = canManageSession ? HOST_ROOM_GUIDE_STEPS : GUEST_ROOM_GUIDE_STEPS;
  const roomNavItems = [
    {
      label: "Help",
      icon: CircleHelp,
      onClick: () => {
        const nextPrefs = resetGuides();
        savedPrefsRef.current = nextPrefs;
        setPrefs(nextPrefs);
        setShowGuide(true);
      },
      dataGuide: "room-help",
    },
    { label: "About", icon: Info, to: "/about" },
    { label: "Settings", icon: Settings2, to: "/settings" },
  ] satisfies Parameters<typeof HeaderNavRail>[0]["items"];
  const roomActionRail = canManageSession
    ? [
        { label: "Share", target: "room-share" },
        { label: "Current", target: "room-current" },
        { label: "Queue", target: "room-queue" },
        { label: "People", target: "room-people" },
      ]
    : [
        { label: "Current", target: "room-current" },
        { label: "Vote", target: "room-vote" },
        { label: "Queue", target: "room-queue" },
        { label: "People", target: "room-people" },
      ];

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,_rgba(250,250,249,1),_rgba(240,249,255,0.8))] px-4 py-5 sm:px-6">
      <CoachMarkOverlay
        open={showGuide}
        steps={guideSteps}
        onClose={() => {
          setShowGuide(false);
          trackProductEvent("onboarding.skipped", {
            roomSlug: slug,
            viewerRole: canManageSession ? "host" : "guest",
            properties: {
              branch: canManageSession ? "host" : "guest",
            },
          });
        }}
        onComplete={() => {
          const branch = canManageSession ? "host" : "guest";
          const nextPrefs = completeGuideBranch(branch);
          savedPrefsRef.current = nextPrefs;
          setPrefs(nextPrefs);
          trackProductEvent("onboarding.completed", {
            roomSlug: slug,
            viewerRole: branch,
            properties: { branch },
          });
        }}
      />
      <FeedbackPrompt
        open={showCloseFeedback}
        title="How did this session wrap feel?"
        description="A quick signal here helps tune the host close flow and the recap that comes after it."
        onClose={() => {
          const nextPrefs = markFeedbackPromptSeen("room-close");
          savedPrefsRef.current = nextPrefs;
          setPrefs(nextPrefs);
          setShowCloseFeedback(false);
        }}
        onSubmit={async ({ sentiment, message }) => {
          await api.submitFeedback({
            roomSlug: slug,
            promptFamily: "room-close",
            sentiment,
            message,
            metadata: {
              provider_id: snapshot.provider_id,
              role: canManageSession ? "host" : "guest",
            },
          });
          const nextPrefs = markFeedbackPromptSeen("room-close");
          savedPrefsRef.current = nextPrefs;
          setPrefs(nextPrefs);
          setShowCloseFeedback(false);
        }}
      />
      <div className="mx-auto flex max-w-7xl flex-col gap-5">
        <MobilePageHeader
          title={roomTitle}
          backTo="/"
          backLabel="Community mode"
          menuGuideId="room-help"
          onHelp={() => {
            const nextPrefs = resetGuides();
            savedPrefsRef.current = nextPrefs;
            setPrefs(nextPrefs);
            setShowGuide(true);
          }}
          primaryAction={
            roomReadyToShare
              ? {
                  label: copiedInvite ? "Copied" : isMobile && canShareInvite ? "Share" : "Copy",
                  icon:
                    isMobile && canShareInvite ? (
                      <Share2 className="h-4 w-4" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    ),
                  onSelect: () => {
                    void copyInviteLink();
                  },
                }
              : undefined
          }
        />
        <header className="rounded-3xl border bg-card/95 px-5 py-5 shadow-sm">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-start xl:justify-between">
            <div className="min-w-0 flex-1 space-y-4">
              <div className="hidden flex-wrap items-center gap-2 md:flex">
                <Button asChild variant="ghost" className="-ml-3">
                  <Link to="/">
                    <ArrowLeft className="mr-2 h-4 w-4" />
                    Back
                  </Link>
                </Button>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-3xl font-semibold tracking-tight">{roomTitle}</h1>
                <Badge variant="secondary">{providerLabel}</Badge>
                <Badge variant={snapshot.status === "open" ? "default" : "secondary"}>
                  {snapshot.status}
                </Badge>
                {snapshot.surface ? <Badge variant="outline">{snapshot.surface.name}</Badge> : null}
                <Badge variant={snapshot.assistant.mode === "assist" ? "default" : "outline"}>
                  Assistant {snapshot.assistant.mode}
                </Badge>
              </div>
              <div className="rounded-2xl border bg-white/75 px-4 py-4">
                <div className="flex flex-col gap-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-1">
                      <p className="text-[11px] uppercase tracking-[0.24em] text-muted-foreground">
                        Room overview
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {roomReadyToShare
                          ? "Ready to share with guests."
                          : canManageSurface
                            ? "Connect the provider and choose a surface to finish setup."
                            : "Waiting for the host to finish room setup."}
                      </p>
                    </div>
                    {roomReadyToShare ? (
                      <Badge
                        variant="outline"
                        className="rounded-full border-emerald-200 bg-emerald-50 px-3 py-1 text-emerald-800"
                      >
                        Ready to share
                      </Badge>
                    ) : null}
                  </div>

                  <div className="grid gap-x-6 gap-y-4 sm:grid-cols-2 xl:grid-cols-4">
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground">Signed in as</p>
                      <p className="text-sm font-medium">{signedInAs}</p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground">Shared surface</p>
                      <p className="text-sm font-medium">{sharedSurfaceLabel}</p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground">Current climb</p>
                      <p className="text-sm font-medium">{currentClimbLabel}</p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground">Room slug</p>
                      <p className="break-all font-mono text-sm font-medium">{snapshot.slug}</p>
                    </div>
                  </div>

                  <div className="space-y-3 border-t pt-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-[11px] uppercase tracking-[0.24em] text-muted-foreground">
                        Room pulse
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {liveParticipants.length > 0
                          ? `${liveParticipants.length} online now`
                          : "No one online yet"}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Badge variant="outline" className="rounded-full px-3 py-1">
                        {readinessCounts.ready} ready
                      </Badge>
                      <Badge variant="outline" className="rounded-full px-3 py-1">
                        {readinessCounts.resting} resting
                      </Badge>
                      <Badge variant="outline" className="rounded-full px-3 py-1">
                        {readinessCounts.away} away
                      </Badge>
                      <Badge variant="outline" className="rounded-full px-3 py-1">
                        {readinessCounts.watching} watching
                      </Badge>
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
                {canEditRoomSettings ? (
                  <Button
                    type="button"
                    variant={showRoomSettings ? "secondary" : "outline"}
                    onClick={() => setShowRoomSettings((currentValue) => !currentValue)}
                  >
                    {showRoomSettings ? "Hide room details" : "Edit room details"}
                  </Button>
                ) : null}
              </div>
              {canEditRoomSettings && showRoomSettings ? (
                <div className="rounded-2xl border bg-muted/20 p-4">
                  <div className="mb-3 space-y-1">
                    <p className="text-sm font-medium text-foreground">Room details</p>
                    <p className="text-sm text-muted-foreground">
                      Keep optional room settings tucked away until you need them.
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
                    <div className="mt-3 rounded-2xl border bg-white/80 p-3">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="space-y-1">
                          <p className="text-sm font-medium text-foreground">Fist bumps</p>
                          <p className="text-sm text-muted-foreground">
                            {snapshot.fist_bumps_enabled
                              ? "Guests can fist bump climbs from the room cards."
                              : "Fist bumps are hidden and no one can add them right now."}
                          </p>
                        </div>
                        <Button
                          type="button"
                          variant={snapshot.fist_bumps_enabled ? "outline" : "secondary"}
                          disabled={fistBumpsSaving || snapshot.status === "closed"}
                          onClick={() =>
                            void handleFistBumpsToggle(!snapshot.fist_bumps_enabled)
                          }
                        >
                          {fistBumpsSaving
                            ? "Saving..."
                            : snapshot.fist_bumps_enabled
                              ? "Disable fist bumps"
                              : "Enable fist bumps"}
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>
              ) : null}
            </div>

            <div className="grid w-full min-w-0 gap-3 xl:w-[26rem] xl:shrink-0">
              <HeaderNavRail items={roomNavItems} className="hidden self-start md:flex xl:self-end" />
              <div
                className="min-w-0"
                data-guide="room-share"
              >
                <Card className="gap-0 py-0 shadow-none">
                  <CardContent className="grid gap-4 p-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
                    <div className="min-w-0 space-y-3">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="space-y-1">
                          <p className="text-sm font-medium">Invite guests</p>
                          <p className="text-sm text-muted-foreground">
                            Share the link or let them scan the QR code.
                          </p>
                        </div>
                        <Button size="sm" variant="outline" onClick={copyInviteLink}>
                          {isMobile && canShareInvite ? (
                            <Share2 className="mr-2 h-4 w-4" />
                          ) : (
                            <Copy className="mr-2 h-4 w-4" />
                          )}
                          {copiedInvite
                            ? "Copied"
                            : isMobile && canShareInvite
                              ? "Share invite"
                              : "Copy invite"}
                        </Button>
                      </div>
                      <div className="grid gap-2 sm:grid-cols-2">
                        <div className="min-w-0 rounded-xl border bg-muted/20 px-3 py-2.5">
                          <p className="text-[11px] uppercase tracking-[0.22em] text-muted-foreground">
                            Join path
                          </p>
                          <p className="mt-1 break-all font-mono text-sm font-medium sm:truncate">
                            {invitePath}
                          </p>
                          <p className="mt-1 break-all text-xs text-muted-foreground sm:truncate">
                            {inviteLink}
                          </p>
                        </div>
                        <div className="min-w-0 rounded-xl border bg-muted/20 px-3 py-2.5">
                          <p className="text-[11px] uppercase tracking-[0.22em] text-muted-foreground">
                            Room slug
                          </p>
                          <p className="mt-1 break-all text-sm font-medium">{snapshot.slug}</p>
                        </div>
                      </div>
                    </div>
                    <InviteQRCodeCard
                      slug={slug}
                      size={isMobile ? "mobile" : "compact"}
                      embedded
                      className="sm:items-end"
                    />
                  </CardContent>
                </Card>
              </div>
              {canManageSession ? (
                <Card className="border-dashed bg-white/80 shadow-none">
                  <CardContent className="grid gap-3 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium">Session assistant</p>
                        <p className="text-sm text-muted-foreground">
                          {snapshot.assistant.message ||
                            "Assist mode suggests the next climb, but the host still confirms it."}
                        </p>
                      </div>
                      <Button
                        type="button"
                        size="sm"
                        variant={snapshot.assistant.mode === "assist" ? "default" : "outline"}
                        onClick={async () => {
                          const nextMode =
                            snapshot.assistant.mode === "assist" ? "manual" : "assist";
                          try {
                            const updatedSnapshot = await api.updateRoomAssistantMode(slug, nextMode);
                            setSnapshot(updatedSnapshot);
                            rememberRoomVisit(updatedSnapshot);
                            trackProductEvent("room.assistant_mode_changed", {
                              roomSlug: slug,
                              viewerRole: "host",
                              properties: { mode: nextMode },
                            });
                          } catch (caughtError) {
                            console.error("Update assistant mode failed", caughtError);
                            setActionError("Unable to update the room assistant mode.");
                          }
                        }}
                        disabled={snapshot.status === "closed"}
                      >
                        <Sparkles className="mr-2 h-4 w-4" />
                        {snapshot.assistant.mode === "assist" ? "Assist on" : "Manual"}
                      </Button>
                    </div>
                    {snapshot.assistant.suggestion ? (
                      <div className="rounded-2xl border bg-muted/30 p-3">
                        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                          Suggested next
                        </p>
                        <p className="mt-2 font-medium">
                          {snapshot.assistant.suggestion.climb.name}
                        </p>
                        <p className="mt-1 text-sm text-muted-foreground">
                          Source: {snapshot.assistant.suggestion.source.replace("_", " ")} ·{" "}
                          {snapshot.assistant.suggestion.ready_count} ready
                        </p>
                        <div className="mt-3 flex flex-wrap gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() =>
                              handlePromoteClimb(
                                snapshot.assistant.suggestion!.climb.id,
                                "next"
                              )
                            }
                            disabled={snapshot.status === "closed"}
                          >
                            Make next
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() =>
                              handlePromoteClimb(
                                snapshot.assistant.suggestion!.climb.id,
                                "current"
                              )
                            }
                            disabled={snapshot.status === "closed"}
                          >
                            Make current
                          </Button>
                        </div>
                      </div>
                    ) : null}
                  </CardContent>
                </Card>
              ) : null}
            </div>
          </div>
        </header>

        <div className="sticky top-2 z-20 -mt-2 flex gap-2 overflow-x-auto rounded-2xl border bg-white/90 px-2 py-2 shadow-sm backdrop-blur sm:top-3 sm:rounded-full">
          {roomActionRail.map((item) => (
            <Button
              key={item.target}
              type="button"
              variant="ghost"
              className="h-9 rounded-full px-3 text-sm"
              onClick={() => {
                document
                  .querySelector(`[data-section="${item.target}"]`)
                  ?.scrollIntoView({ behavior: "smooth", block: "start" });
              }}
            >
              {item.label}
            </Button>
          ))}
        </div>

        {!snapshot.connection.connected ? (
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <CardTitle>Connect the host account</CardTitle>
                  <CardDescription>
                    {canEditRoomSettings
                      ? snapshot.provider_id === "kilter"
                        ? "Authenticate one Kilter account so the room can browse a shared board."
                        : `Enter one ${providerLabel} token so the room can browse a shared gym and wall.`
                      : "Waiting for the host to connect the provider account before guests can browse climbs."}
                  </CardDescription>
                </div>
                {canEditRoomSettings && isMobile ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setShowConnectionEditor((currentValue) => !currentValue)}
                  >
                    {showConnectionEditor ? "Hide form" : "Show form"}
                  </Button>
                ) : null}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {canEditRoomSettings && (!isMobile || showConnectionEditor) ? (
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
                      <SecretInput
                        ref={kilterPasswordInputRef}
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
                      {snapshot.provider_id === "test" ? (
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
                          placeholder="Test provider token"
                        />
                      ) : (
                        <SecretInput
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
                      )}
                      <p className="text-sm text-muted-foreground">
                        {snapshot.provider_id === "test" ? (
                          "Use any non-empty token while the test provider flag is enabled."
                        ) : (
                          <>
                            Paste either the raw Crux token or the full <code>Bearer ...</code> value.
                          </>
                        )}
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
                        {snapshot.provider_id === "test"
                          ? "Remember this test provider auth preference on this browser"
                          : "Remember this Crux auth preference on this browser"}
                      </label>
                      <p className="text-xs text-muted-foreground">
                        {snapshot.provider_id === "test"
                          ? "Stores this preference locally for test-only room setup."
                          : "Stores this preference locally. You still enter the Crux token each time."}
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
          <Card data-section="room-current" data-guide="room-current">
            <CardHeader>
              <CardTitle>
                {snapshot.surface ? "Shared climbing surface" : "Choose the shared climbing surface"}
              </CardTitle>
              <CardDescription>
                {canManageSurface
                  ? snapshot.surface
                    ? "Everyone in the room is browsing this board or wall. Open edit when you need to switch it."
                    : "This becomes the shared board or wall for everyone in the room."
                  : "Waiting for the host to choose the shared board or wall."}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {pendingRoomSeed ? (
                <div className="rounded-2xl border border-teal-200 bg-teal-50/80 px-4 py-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-1">
                      <p className="text-sm font-medium text-teal-900">
                        {pendingRoomSeedHasClimbs
                          ? "Saved plan seed is ready"
                          : "Saved surface context is ready"}
                      </p>
                      <p className="text-sm text-teal-900/80">
                        {pendingRoomSeedHasClimbs
                          ? pendingRoomSeedMatchesSurface
                            ? pendingRoomSeedQueuedClimbs.length > 0
                              ? `Import ${pendingRoomSeedQueuedClimbs.length} saved climb${
                                  pendingRoomSeedQueuedClimbs.length === 1 ? "" : "s"
                                } into this room queue.`
                              : "Every saved climb is already in the room queue."
                            : `Choose ${pendingRoomSeed.surface.name} to import ${pendingRoomSeed.climbs.length} saved climb${
                                pendingRoomSeed.climbs.length === 1 ? "" : "s"
                              }.`
                          : pendingRoomSeedMatchesSurface
                            ? "This room is already set to the saved plan context."
                            : `Choose ${pendingRoomSeed.surface.name} to use the saved plan context in this room.`}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {canManageQueue &&
                      pendingRoomSeedMatchesSurface &&
                      pendingRoomSeedHasClimbs ? (
                        <Button
                          type="button"
                          variant="secondary"
                          onClick={() => void handleImportSoloSeed()}
                          disabled={importingSoloSeed}
                        >
                          {importingSoloSeed
                            ? "Importing..."
                            : pendingRoomSeedQueuedClimbs.length > 0
                              ? "Import plan to queue"
                              : "Clear imported seed"}
                        </Button>
                      ) : null}
                      <Button
                        type="button"
                        variant="outline"
                        className="border-teal-200 bg-white/80"
                        onClick={handleDiscardSoloSeed}
                      >
                        Discard seed
                      </Button>
                    </div>
                  </div>
                </div>
              ) : null}
              <DetailGrid items={surfaceSummaryItems} className="lg:grid-cols-3" />
              {canManageSurface && snapshot.surface ? (
                <Button
                  type="button"
                  variant={surfaceEditorOpen ? "secondary" : "outline"}
                  onClick={() => setShowSurfaceEditor((currentValue) => !currentValue)}
                >
                  {surfaceEditorOpen ? "Hide surface editor" : "Edit surface"}
                </Button>
              ) : null}
              {canManageSurface && surfaceEditorOpen ? (
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
                          <SelectValue
                            placeholder={
                              snapshot.provider_id === "test"
                                ? "Select a test gym"
                                : "Select a Crux gym"
                            }
                          />
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
                          <SelectValue
                            placeholder={
                              snapshot.provider_id === "test"
                                ? "Select a test wall"
                                : "Select a wall"
                            }
                          />
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
              <Card className="order-2 gap-4 lg:order-none">
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
                        const isQueued = queuedClimbIds.has(climb.id);
                        const finalistEntry = snapshot.finalists.find(
                          (entry) => entry.climb.id === climb.id
                        );
                        const queueEntry = snapshot.queue.find(
                          (entry) => entry.climb.id === climb.id
                        );
                        const providerMetaLine = formatProviderCatalogMeta(climb);

                        return (
                          <div
                            key={climb.id}
                            className={`w-full rounded-2xl border p-3 text-left transition-colors ${
                              selectedClimb?.id === climb.id
                                ? "border-primary bg-primary/5"
                                : "bg-card hover:bg-muted/40"
                            }`}
                          >
                            <button
                              type="button"
                              onClick={() => selectClimb(climb)}
                              className="w-full text-left"
                            >
                              <div className="flex items-start justify-between gap-3">
                                <div>
                                  <p className="font-medium">{climb.name}</p>
                                  <p className="mt-1 text-xs text-muted-foreground">
                                    {climb.setter_name || "Unknown setter"}
                                  </p>
                                  {providerMetaLine ? (
                                    <p className="mt-1 text-[11px] uppercase tracking-[0.2em] text-muted-foreground/80">
                                      {providerMetaLine}
                                    </p>
                                  ) : null}
                                </div>
                                <div className="flex flex-col items-end gap-1">
                                  <Badge variant="secondary">
                                    {climb.primary_grade || "Unknown"}
                                  </Badge>
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
                          </div>
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

              <div className="order-1 grid gap-4 lg:order-none">
                <Card className="gap-4" data-section="room-vote" data-guide="room-vote">
                  <CardHeader className="flex flex-row items-center justify-between gap-4 space-y-0">
                    <div>
                      <CardTitle>Climb detail</CardTitle>
                      <CardDescription>
                        Fist bumps and queue actions affect the shared room state.
                      </CardDescription>
                    </div>
                    {selectedClimb ? (
                      <div className="flex flex-wrap items-center gap-2">
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
                        {snapshot.fist_bumps_enabled && selectedIsQueued ? (
                          <RoomFistBumpButton
                            active={selectedHasMyFistBump}
                            climbName={selectedClimb.name}
                            count={selectedFistBumpCount}
                            disabled={
                              fistBumpsBlocked ||
                              pendingFistBumpClimbId === selectedClimb.id
                            }
                            onClick={() => void handleFistBumpToggle(selectedClimb.id)}
                          />
                        ) : null}
                        <Button
                          variant="outline"
                          onClick={() => handleQueueAdd(selectedClimb.id)}
                          disabled={selectedIsQueued || snapshot.status === "closed"}
                        >
                          {selectedIsQueued ? "Already queued" : "Add to queue"}
                        </Button>
                        {canManageQueue ? (
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
                    />
                  </CardContent>
                </Card>

                <Card className="gap-4">
                  <CardHeader>
                    <CardTitle>Leaderboard</CardTitle>
                    <CardDescription>
                      Most fist-bumped climbs visible in this room snapshot.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {!snapshot.fist_bumps_enabled ? (
                      <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
                        Fist bumps are disabled for this room.
                      </div>
                    ) : leaderboard.length === 0 ? (
                      <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
                        Fist bumps will surface the leaderboard once the group starts choosing climbs.
                      </div>
                    ) : (
                      <>
                        {topVoteCount > 0 && topVoteTieCount > 1 ? (
                          <div className="rounded-2xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-950">
                            There is currently a tie for first place across {topVoteTieCount} climbs.
                          </div>
                        ) : null}
                        {leaderboard.map((climb, index) => (
                          <div
                            key={climb.id}
                            className="rounded-2xl border p-3 transition-colors hover:bg-muted/30"
                          >
                            <button
                              type="button"
                              onClick={() => selectClimb(climb)}
                              className="w-full text-left"
                            >
                              <p className="font-medium">
                                #{index + 1} {climb.name}
                              </p>
                              <p className="mt-1 text-xs text-muted-foreground">
                                {climb.setter_name || "Unknown setter"}
                              </p>
                            </button>
                            {snapshot.fist_bumps_enabled && queuedClimbIds.has(climb.id) ? (
                              <div className="mt-3">
                                <RoomFistBumpButton
                                  active={myFistBumps.includes(climb.id)}
                                  climbName={climb.name}
                                  count={snapshot.vote_counts[climb.id] ?? 0}
                                  disabled={
                                    fistBumpsBlocked ||
                                    pendingFistBumpClimbId === climb.id
                                  }
                                  onClick={() => void handleFistBumpToggle(climb.id)}
                                />
                              </div>
                            ) : null}
                          </div>
                        ))}
                        {canManageQueue ? (
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
                              Pick random top fist bump
                            </Button>
                          </div>
                        ) : null}
                      </>
                    )}
                  </CardContent>
                </Card>
              </div>

              <div className="order-3 grid gap-4 lg:order-none">
                <Card className="gap-4">
                  <CardHeader>
                    <CardTitle>Finalists</CardTitle>
                    <CardDescription>
                      Manager-controlled shortlist for narrowing down the field.
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
                            {canManageFinalists ? (
                              isMobile ? (
                                <div className="flex flex-col gap-1">
                                  <Button
                                    type="button"
                                    size="icon"
                                    variant="ghost"
                                    aria-label={`Move ${entry.climb.name} up in finalists`}
                                    onClick={() => void handleMoveFinalist(entry.id, "up")}
                                  >
                                    <ChevronUp className="h-4 w-4" />
                                  </Button>
                                  <Button
                                    type="button"
                                    size="icon"
                                    variant="ghost"
                                    aria-label={`Move ${entry.climb.name} down in finalists`}
                                    onClick={() => void handleMoveFinalist(entry.id, "down")}
                                  >
                                    <ChevronDown className="h-4 w-4" />
                                  </Button>
                                </div>
                              ) : (
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
                              )
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
                              </div>
                            </button>
                          </div>
                          <div className="mt-3 flex flex-wrap gap-2">
                            {snapshot.fist_bumps_enabled && queuedClimbIds.has(entry.climb.id) ? (
                              <RoomFistBumpButton
                                active={myFistBumps.includes(entry.climb.id)}
                                climbName={entry.climb.name}
                                count={snapshot.vote_counts[entry.climb.id] ?? 0}
                                disabled={
                                  fistBumpsBlocked ||
                                  pendingFistBumpClimbId === entry.climb.id
                                }
                                onClick={() => void handleFistBumpToggle(entry.climb.id)}
                              />
                            ) : null}
                            {canManageFinalists ? (
                              <>
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
                              </>
                            ) : null}
                          </div>
                        </div>
                      ))
                    )}
                  </CardContent>
                </Card>

                <Card className="gap-4" data-section="room-queue" data-guide="room-queue">
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
                            {canManageQueue ? (
                              isMobile ? (
                                <div className="flex flex-col gap-1">
                                  <Button
                                    type="button"
                                    size="icon"
                                    variant="ghost"
                                    aria-label={`Move ${entry.climb.name} up in queue`}
                                    onClick={() => void handleMoveQueueEntry(entry.id, "up")}
                                  >
                                    <ChevronUp className="h-4 w-4" />
                                  </Button>
                                  <Button
                                    type="button"
                                    size="icon"
                                    variant="ghost"
                                    aria-label={`Move ${entry.climb.name} down in queue`}
                                    onClick={() => void handleMoveQueueEntry(entry.id, "down")}
                                  >
                                    <ChevronDown className="h-4 w-4" />
                                  </Button>
                                </div>
                              ) : (
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
                              )
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
                          <div className="mt-3 flex flex-wrap gap-2">
                            {snapshot.fist_bumps_enabled ? (
                              <RoomFistBumpButton
                                active={myFistBumps.includes(entry.climb.id)}
                                climbName={entry.climb.name}
                                count={snapshot.vote_counts[entry.climb.id] ?? 0}
                                disabled={
                                  fistBumpsBlocked ||
                                  pendingFistBumpClimbId === entry.climb.id
                                }
                                onClick={() => void handleFistBumpToggle(entry.climb.id)}
                              />
                            ) : null}
                            {canManageQueue ? (
                              <>
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
                              </>
                            ) : null}
                          </div>
                        </div>
                      ))
                    )}
                  </CardContent>
                </Card>

                <Card className="gap-4" data-section="room-people" data-guide="room-people">
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
                                {formatParticipantRole(participant.role)} ·{" "}
                                {participant.is_online ? "online" : "idle"}
                              </span>
                              <Badge variant="outline">{participant.status}</Badge>
                            </div>
                          </div>
                          <div className="flex flex-wrap items-center justify-end gap-2">
                            {canAssignCoHosts && participant.role !== "host" ? (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() =>
                                  handleParticipantRoleUpdate(
                                    participant.id,
                                    participant.role === "co_host" ? "participant" : "co_host"
                                  )
                                }
                              >
                                {participant.role === "co_host"
                                  ? "Remove co-host"
                                  : "Make co-host"}
                              </Button>
                            ) : null}
                            {canManageParticipants && participant.role !== "host" ? (
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
                      </div>
                    ))}

                    {canManageQueue || canCloseRoom ? (
                      <div className="flex flex-wrap gap-2 pt-2">
                        {canManageQueue ? (
                          <Button variant="outline" onClick={handleClearVotes}>
                            Clear fist bumps
                          </Button>
                        ) : null}
                        {canCloseRoom ? (
                          <Button variant="destructive" onClick={handleCloseRoom}>
                            Close room
                          </Button>
                        ) : null}
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
