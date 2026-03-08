import {
  useCallback,
  startTransition,
  useDeferredValue,
  useEffect,
  useRef,
  useState,
} from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowUp,
  Copy,
  RefreshCw,
  Trash2,
  UserMinus,
} from "lucide-react";
import { api } from "@/api";
import type {
  ProviderSurface,
  QueueEntry,
  QueueStatus,
  RoomCatalogClimbsResponse,
  RoomSnapshot,
} from "@/types";
import { DEFAULT_ANGLE, normalizeSort } from "@/lib/climbs";
import RoomProblemView from "@/components/RoomProblemView";
import AngleSelector from "@/components/AngleSelector";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const PAGE_SIZE = 12;

export default function RoomView() {
  const { slug = "" } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const [snapshot, setSnapshot] = useState<RoomSnapshot | null>(null);
  const [catalog, setCatalog] = useState<RoomCatalogClimbsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [surfaceLoading, setSurfaceLoading] = useState(false);
  const [actionError, setActionError] = useState("");
  const [connectionFields, setConnectionFields] = useState({
    username: "",
    password: "",
    token: "",
  });
  const [boardSurfaces, setBoardSurfaces] = useState<ProviderSurface[]>([]);
  const [cruxGyms, setCruxGyms] = useState<ProviderSurface[]>([]);
  const [cruxWalls, setCruxWalls] = useState<ProviderSurface[]>([]);
  const [selectedBoardId, setSelectedBoardId] = useState("");
  const [selectedAngle, setSelectedAngle] = useState(DEFAULT_ANGLE);
  const [selectedGymSlug, setSelectedGymSlug] = useState("");
  const [selectedWallId, setSelectedWallId] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [copiedInvite, setCopiedInvite] = useState(false);
  const cursorsRef = useRef<Record<number, string>>({});
  const lastFilterKeyRef = useRef("");

  const search = searchParams.get("q") ?? "";
  const sort = normalizeSort(searchParams.get("sort"));
  const selectedClimbId = searchParams.get("climb") ?? "";
  const deferredSearch = useDeferredValue(search);

  const selectedClimb =
    catalog?.climbs.find((climb) => climb.id === selectedClimbId) ||
    catalog?.climbs[0] ||
    null;

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

        if (nextSnapshot.provider_id === "kilter") {
          setSelectedBoardId(
            nextSnapshot.surface?.meta?.board_id || nextSnapshot.surface?.id || ""
          );
          setSelectedAngle(
            Number(nextSnapshot.surface?.meta?.angle ?? DEFAULT_ANGLE)
          );
        }

        if (nextSnapshot.provider_id === "crux") {
          const gymSlug =
            nextSnapshot.surface?.meta?.gym_slug || nextSnapshot.surface?.parent_id || "";
          setSelectedGymSlug(gymSlug);
          setSelectedWallId(nextSnapshot.surface?.id || "");
        }

        return nextSnapshot;
      } catch (caughtError) {
        console.error("Load room failed", caughtError);
        setSnapshot(null);
        setCatalog(null);
        setActionError(
          "Unable to load this room. Join the invite first, or check whether the host has closed it."
        );
        return null;
      } finally {
        if (showLoader) {
          setLoading(false);
        }
      }
    },
    [slug]
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

        const nextSelectedClimb =
          nextCatalog.climbs.find((climb) => climb.id === selectedClimbId) ||
          nextCatalog.climbs[0] ||
          null;
        if (nextSelectedClimb?.id !== selectedClimbId) {
          const nextSearchParams = new URLSearchParams(searchParams);
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
        setActionError("Unable to load the climb catalog for this room.");
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
      searchParams,
      selectedClimbId,
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
  }, [currentPage, deferredSearch, fetchCatalog, searchParams, selectedClimbId, setSearchParams, slug, snapshot, sort]);

  useEffect(() => {
    if (!slug || !snapshot?.can_manage || !snapshot.connection.connected || snapshot.surface) {
      return;
    }

    const loadSurfaces = async () => {
      setSurfaceLoading(true);
      setActionError("");

      try {
        if (snapshot.provider_id === "kilter") {
          const nextBoards = await api.getRoomCatalogSurfaces(slug);
          setBoardSurfaces(nextBoards);
          setSelectedBoardId((currentValue) => currentValue || nextBoards[0]?.id || "");
          return;
        }

        const nextGyms = await api.getRoomCatalogSurfaces(slug);
        setCruxGyms(nextGyms);
        setSelectedGymSlug((currentValue) => currentValue || nextGyms[0]?.id || "");
      } catch (caughtError) {
        console.error("Load room surfaces failed", caughtError);
        setActionError("Unable to load provider surfaces for this room.");
      } finally {
        setSurfaceLoading(false);
      }
    };

    void loadSurfaces();
  }, [slug, snapshot]);

  useEffect(() => {
    if (
      !slug ||
      snapshot?.provider_id !== "crux" ||
      !snapshot.can_manage ||
      !snapshot.connection.connected ||
      snapshot.surface ||
      !selectedGymSlug
    ) {
      return;
    }

    const loadWalls = async () => {
      setSurfaceLoading(true);

      try {
        const nextWalls = await api.getRoomCatalogSurfaces(slug, selectedGymSlug);
        setCruxWalls(nextWalls);
        setSelectedWallId((currentValue) => currentValue || nextWalls[0]?.id || "");
      } catch (caughtError) {
        console.error("Load room walls failed", caughtError);
        setActionError("Unable to load Crux walls for the selected gym.");
      } finally {
        setSurfaceLoading(false);
      }
    };

    void loadWalls();
  }, [selectedGymSlug, slug, snapshot]);

  useEffect(() => {
    if (!slug || !snapshot || snapshot.status === "closed" || typeof EventSource === "undefined") {
      return;
    }

    const eventSource = new EventSource(api.getRoomEventsUrl(slug), {
      withCredentials: true,
    });
    const handleRoomEvent = () => {
      void refreshRoomState();
    };

    eventSource.addEventListener("room", handleRoomEvent);
    eventSource.onerror = () => {
      eventSource.close();
    };

    return () => {
      eventSource.removeEventListener("room", handleRoomEvent);
      eventSource.close();
    };
  }, [refreshRoomState, slug, snapshot]);

  useEffect(() => {
    if (!copiedInvite) {
      return;
    }

    const timeoutID = window.setTimeout(() => setCopiedInvite(false), 1800);
    return () => window.clearTimeout(timeoutID);
  }, [copiedInvite]);

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
      setSearchParams(nextSearchParams);
    });
  };

  const handleConnectProvider = async () => {
    if (!slug || !snapshot) {
      return;
    }

    setSurfaceLoading(true);
    setActionError("");

    try {
      if (snapshot.provider_id === "kilter") {
        await api.connectRoomProvider(slug, {
          username: connectionFields.username,
          password: connectionFields.password,
        });
      } else {
        await api.connectRoomProvider(slug, {
          token: connectionFields.token,
        });
      }
      await refreshRoomState();
    } catch (caughtError) {
      console.error("Connect provider failed", caughtError);
      setActionError("Unable to validate the provider credentials for this room.");
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
          },
        });
      } else {
        await api.setRoomSurface(slug, {
          surfaceId: selectedWallId,
          context: {
            gym_slug: selectedGymSlug,
          },
        });
      }

      cursorsRef.current = {};
      setCurrentPage(1);
      await refreshRoomState();
    } catch (caughtError) {
      console.error("Set room surface failed", caughtError);
      setActionError("Unable to save the provider surface for this room.");
    } finally {
      setSurfaceLoading(false);
    }
  };

  const handleCatalogRefresh = async () => {
    await refreshRoomState();
  };

  const handleVoteToggle = async (climbId: string) => {
    if (!slug) {
      return;
    }

    try {
      await api.toggleRoomVote(slug, climbId);
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
      await refreshRoomState();
    } catch (caughtError) {
      console.error("Add queue entry failed", caughtError);
      setActionError("Unable to add this climb to the room queue.");
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

  const handleMoveQueueEntry = async (entry: QueueEntry, direction: -1 | 1) => {
    if (!slug || !snapshot) {
      return;
    }

    const entryIDs = snapshot.queue.map((queueEntry) => queueEntry.id);
    const currentIndex = entryIDs.indexOf(entry.id);
    const nextIndex = currentIndex + direction;
    if (currentIndex < 0 || nextIndex < 0 || nextIndex >= entryIDs.length) {
      return;
    }

    const reordered = [...entryIDs];
    [reordered[currentIndex], reordered[nextIndex]] = [
      reordered[nextIndex],
      reordered[currentIndex],
    ];

    try {
      await api.reorderRoomQueue(slug, reordered);
      await refreshRoomState();
    } catch (caughtError) {
      console.error("Reorder queue failed", caughtError);
      setActionError("Unable to reorder the queue.");
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

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-lg text-muted-foreground">Loading room...</div>
      </div>
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
              <CardDescription>{actionError || "This room could not be loaded."}</CardDescription>
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
  const inviteLink =
    typeof window === "undefined" ? `/join/${slug}` : `${window.location.origin}/join/${slug}`;

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,_rgba(250,250,249,1),_rgba(240,249,255,0.8))] px-4 py-5 sm:px-6">
      <div className="mx-auto flex max-w-7xl flex-col gap-5">
        <header className="rounded-3xl border bg-card/95 px-5 py-5 shadow-sm">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-2">
              <Button asChild variant="ghost" className="-ml-3">
                <Link to="/">
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  Back
                </Link>
              </Button>
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-3xl font-semibold tracking-tight">Room {snapshot.slug}</h1>
                <Badge variant="secondary">{snapshot.provider_id}</Badge>
                <Badge variant={snapshot.status === "open" ? "default" : "secondary"}>
                  {snapshot.status}
                </Badge>
                {snapshot.surface ? <Badge variant="outline">{snapshot.surface.name}</Badge> : null}
              </div>
              <p className="text-sm text-muted-foreground">
                Signed in as {snapshot.display_name || "guest"}.
              </p>
              {snapshot.current_climb ? (
                <p className="text-sm text-muted-foreground">
                  Current climb:{" "}
                  <span className="font-medium text-foreground">
                    {snapshot.current_climb.name}
                  </span>
                </p>
              ) : null}
            </div>

            <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
              <div className="rounded-2xl border bg-muted/30 px-4 py-3">
                <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
                  Invite link
                </p>
                <p className="mt-1 break-all text-sm">{inviteLink}</p>
              </div>
              <Button variant="outline" onClick={copyInviteLink}>
                <Copy className="mr-2 h-4 w-4" />
                {copiedInvite ? "Copied" : "Copy invite"}
              </Button>
            </div>
          </div>
        </header>

        {actionError ? (
          <div className="rounded-2xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            {actionError}
          </div>
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
                        value={connectionFields.username}
                        onChange={(event) =>
                          setConnectionFields((previousState) => ({
                            ...previousState,
                            username: event.target.value,
                          }))
                        }
                        placeholder="Kilter username"
                      />
                      <Input
                        type="password"
                        value={connectionFields.password}
                        onChange={(event) =>
                          setConnectionFields((previousState) => ({
                            ...previousState,
                            password: event.target.value,
                          }))
                        }
                        placeholder="Kilter password"
                      />
                    </div>
                  ) : (
                    <Input
                      value={connectionFields.token}
                      onChange={(event) =>
                        setConnectionFields((previousState) => ({
                          ...previousState,
                          token: event.target.value,
                        }))
                      }
                      placeholder="Crux bearer token"
                    />
                  )}
                  <Button onClick={handleConnectProvider} disabled={surfaceLoading}>
                    {surfaceLoading ? "Connecting..." : "Connect provider"}
                  </Button>
                </>
              ) : null}
            </CardContent>
          </Card>
        ) : null}

        {snapshot.connection.connected && !snapshot.surface ? (
          <Card>
            <CardHeader>
              <CardTitle>Choose the shared climbing surface</CardTitle>
              <CardDescription>
                {snapshot.can_manage
                  ? "This becomes the shared board or wall for everyone in the room."
                  : "Waiting for the host to choose the shared board or wall."}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {snapshot.can_manage ? (
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
                      {surfaceLoading ? "Saving..." : "Save board"}
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
                      {surfaceLoading ? "Saving..." : "Save wall"}
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

                        return (
                          <button
                            key={climb.id}
                            type="button"
                            onClick={() => {
                              const nextSearchParams = new URLSearchParams(searchParams);
                              nextSearchParams.set("climb", climb.id);
                              setSearchParams(nextSearchParams, { replace: true });
                            }}
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
                      </div>
                    ) : null}
                    <RoomProblemView
                      climb={selectedClimb}
                      providerId={snapshot.provider_id}
                      hasResults={(catalog?.climbs.length ?? 0) > 0}
                    />
                  </CardContent>
                </Card>
              </div>

              <div className="grid gap-4">
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
                      snapshot.queue.map((entry, index) => (
                        <div key={entry.id} className="rounded-2xl border p-3">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="font-medium">{entry.climb.name}</p>
                              <p className="text-xs text-muted-foreground">
                                Added by {entry.added_by}
                              </p>
                            </div>
                            <Badge variant="outline">{entry.status}</Badge>
                          </div>
                          {snapshot.can_manage ? (
                            <div className="mt-3 flex flex-wrap gap-2">
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleMoveQueueEntry(entry, -1)}
                                disabled={index === 0}
                              >
                                <ArrowUp className="mr-1 h-3.5 w-3.5" />
                                Up
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleMoveQueueEntry(entry, 1)}
                                disabled={index === snapshot.queue.length - 1}
                              >
                                Down
                              </Button>
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
                          <p className="text-xs text-muted-foreground">
                            {participant.role} · {participant.is_online ? "online" : "idle"}
                          </p>
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
