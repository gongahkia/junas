import {
  startTransition,
  useDeferredValue,
  useEffect,
  useRef,
  useState,
} from "react";
import { Heart, Layers3, ListChecks, Share2 } from "lucide-react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ChevronLeft } from "lucide-react";
import { api } from "../api";
import type { Board, Climb, ProviderClimb } from "../types";
import Sidebar from "./Sidebar";
import ProblemView from "./ProblemView";
import LoadingSlideshow from "./LoadingSlideshow";
import { getGradeForAngle, normalizeAngle, normalizeSort } from "@/lib/climbs";
import {
  beginSoloRoomSeed,
  buildSoloFilterPreset,
  buildSoloSavedClimb,
  loadUserPrefs,
  rememberSoloResume,
  saveSoloFilterPreset,
  soloSavedClimbKey,
  toggleSoloFavorite,
  toggleSoloShortlist,
} from "@/lib/user-prefs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { useErrorToast } from "@/hooks/use-toast";
import { trackProductEvent } from "@/lib/product-analytics";

const PAGE_SIZE = 10;

interface ClimbViewProps {
  boards: Board[];
  boardsLoading: boolean;
  backPath?: string;
}

export default function ClimbView({
  boards,
  boardsLoading,
  backPath = "/",
}: ClimbViewProps) {
  const showErrorToast = useErrorToast();
  const [climbs, setClimbs] = useState<Climb[]>([]);
  const [loading, setLoading] = useState(true);
  const [initialLoad, setInitialLoad] = useState(true);
  const [pageLoading, setPageLoading] = useState(false);
  const [selectedClimb, setSelectedClimb] = useState<Climb | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [hasNextPage, setHasNextPage] = useState(false);
  const [savedFilterID, setSavedFilterID] = useState("");
  const [prefs, setPrefs] = useState(() => loadUserPrefs());
  const [planTitle, setPlanTitle] = useState("");
  const [planNotes, setPlanNotes] = useState("");
  const [sharingPlan, setSharingPlan] = useState(false);
  const cursorsRef = useRef<Record<number, string>>({});
  const lastFilterKeyRef = useRef("");
  const { boardId = "" } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const rawAngle = searchParams.get("angle");
  const rawSort = searchParams.get("sort");
  const angle = normalizeAngle(rawAngle);
  const sort = normalizeSort(rawSort);
  const nameQuery = searchParams.get("q") ?? "";
  const setterQuery = searchParams.get("setter") ?? "";
  const gradeQuery = searchParams.get("grade") ?? "";
  const selectedUuid = searchParams.get("climb") ?? "";
  const deferredNameQuery = useDeferredValue(nameQuery);
  const deferredSetterQuery = useDeferredValue(setterQuery);
  const deferredGradeQuery = useDeferredValue(gradeQuery);

  const board = boards.find((candidate) => String(candidate.id) === boardId);
  const boardName = board?.name || (boardsLoading ? "Loading board..." : `Board ${boardId}`);
  const selectedClimbKey = selectedClimb
    ? soloSavedClimbKey({
        uuid: selectedClimb.uuid,
        product_size_id: selectedClimb.product_size_id,
      })
    : "";
  const isFavorite = prefs.soloFavorites.some(
    (climb) => soloSavedClimbKey(climb) === selectedClimbKey
  );
  const isShortlisted = prefs.soloShortlist.some(
    (climb) => soloSavedClimbKey(climb) === selectedClimbKey
  );
  const shortlistForCurrentView = prefs.soloShortlist.filter(
    (climb) => climb.board_id === boardId && climb.angle === angle
  );

  useEffect(() => {
    if (!planTitle.trim() && boardName && !boardsLoading) {
      setPlanTitle(`${boardName} plan`);
    }
  }, [boardName, boardsLoading, planTitle]);

  useEffect(() => {
    if (!boardId) {
      navigate("/", { replace: true });
      return;
    }

    const nextSearchParams = new URLSearchParams(searchParams);
    let changed = false;

    if (rawAngle !== String(angle)) {
      nextSearchParams.set("angle", String(angle));
      changed = true;
    }

    if (rawSort !== sort) {
      nextSearchParams.set("sort", sort);
      changed = true;
    }

    if (changed) {
      setSearchParams(nextSearchParams, { replace: true });
    }
  }, [angle, boardId, navigate, rawAngle, rawSort, searchParams, setSearchParams, sort]);

  useEffect(() => {
    if (!boardId) {
      return;
    }

    const filterKey = JSON.stringify({
      boardId,
      angle,
      name: deferredNameQuery,
      setter: deferredSetterQuery,
      grade: deferredGradeQuery,
      sort,
    });
    const filtersChanged = lastFilterKeyRef.current !== filterKey;
    if (filtersChanged) {
      lastFilterKeyRef.current = filterKey;
      cursorsRef.current = {};
      setHasNextPage(false);
      if (currentPage !== 1) {
        setCurrentPage(1);
        return;
      }
    }

    const fetchPage = async () => {
      try {
        if (currentPage === 1) {
          setLoading(true);
        } else {
          setPageLoading(true);
        }

        const paginatedData = await api.getPaginatedClimbs({
          boardId,
          angle,
          cursor: currentPage > 1 ? cursorsRef.current[currentPage] : undefined,
          pageSize: PAGE_SIZE,
          name: deferredNameQuery || undefined,
          setter: deferredSetterQuery || undefined,
          grade: deferredGradeQuery || undefined,
          sort,
        });

        setClimbs(paginatedData.climbs);
        setHasNextPage(paginatedData.has_more);

        if (paginatedData.next_cursor) {
          cursorsRef.current = {
            ...cursorsRef.current,
            [currentPage + 1]: paginatedData.next_cursor,
          };
        }

        const nextSelectedClimb =
          paginatedData.climbs.find((climb) => climb.uuid === selectedUuid) ||
          paginatedData.climbs[0] ||
          null;
        setSelectedClimb(nextSelectedClimb);

        if (nextSelectedClimb?.uuid !== selectedUuid) {
          const nextSearchParams = new URLSearchParams(searchParams);
          if (nextSelectedClimb) {
            nextSearchParams.set("climb", nextSelectedClimb.uuid);
          } else {
            nextSearchParams.delete("climb");
          }
          setSearchParams(nextSearchParams, { replace: true });
        }
      } catch (error) {
        console.error("API Error:", error);
        setClimbs([]);
        setSelectedClimb(null);
        setHasNextPage(false);
        showErrorToast("Unable to load climbs for this board. Try refreshing the page.");
      } finally {
        setLoading(false);
        setInitialLoad(false);
        setPageLoading(false);
      }
    };

    void fetchPage();
  }, [
    angle,
    boardId,
    currentPage,
    deferredNameQuery,
    deferredSetterQuery,
    deferredGradeQuery,
    searchParams,
    selectedUuid,
    setSearchParams,
    showErrorToast,
    sort,
  ]);

  useEffect(() => {
    if (!boardId) {
      return;
    }

    rememberSoloResume({
      boardId,
      angle,
      q: nameQuery || undefined,
      setter: setterQuery || undefined,
      grade: gradeQuery || undefined,
      sort,
      climb: selectedClimb?.uuid,
    });
  }, [angle, boardId, gradeQuery, nameQuery, selectedClimb?.uuid, setterQuery, sort]);

  useEffect(() => {
    setSavedFilterID("");
  }, [angle, boardId, gradeQuery, nameQuery, setterQuery, sort]);

  const updateSearchState = (updates: Record<string, string | undefined>) => {
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
      setHasNextPage(false);
      setSearchParams(nextSearchParams);
    });
  };

  const handleClimbSelect = (climb: Climb) => {
    setSelectedClimb(climb);
    const nextSearchParams = new URLSearchParams(searchParams);
    nextSearchParams.set("climb", climb.uuid);
    setSearchParams(nextSearchParams, { replace: true });
  };

  const goToNextPage = () => {
    if (hasNextPage) {
      setCurrentPage((previousPage) => previousPage + 1);
    }
  };

  const goToPreviousPage = () => {
    if (currentPage > 1) {
      setCurrentPage((previousPage) => previousPage - 1);
    }
  };

  const buildSavedClimb = () => {
    if (!selectedClimb || !boardId) {
      return null;
    }

    return buildSoloSavedClimb({
      uuid: selectedClimb.uuid,
      product_size_id: selectedClimb.product_size_id,
      climb_name: selectedClimb.climb_name,
      setter_name: selectedClimb.setter_name,
      board_id: boardId,
      board_name: boardName,
      angle,
      grade: getGradeForAngle(selectedClimb, angle),
      image_filename: selectedClimb.image_filenames?.[0],
      ascends: selectedClimb.ascends,
    });
  };

  const handleToggleFavorite = () => {
    const savedClimb = buildSavedClimb();
    if (!savedClimb) {
      return;
    }
    setPrefs(toggleSoloFavorite(savedClimb));
  };

  const handleToggleShortlist = () => {
    const savedClimb = buildSavedClimb();
    if (!savedClimb) {
      return;
    }
    setPrefs(toggleSoloShortlist(savedClimb));
  };

  const handleSaveFilterPreset = () => {
    if (!boardId) {
      return;
    }

    const preset = buildSoloFilterPreset({
      board_id: boardId,
      board_name: boardName,
      angle,
      sort,
      q: nameQuery || undefined,
      setter: setterQuery || undefined,
      grade: gradeQuery || undefined,
    });
    setSavedFilterID(preset.id);
    setPrefs(saveSoloFilterPreset(preset));
  };

  const handleSeedRoomFromShortlist = () => {
    if (!boardId || shortlistForCurrentView.length === 0) {
      return;
    }

    setPrefs(
      beginSoloRoomSeed({
        boardId,
        boardName,
        angle,
        climbs: shortlistForCurrentView,
      })
    );
    navigate("/rooms/new");
  };

  const handleSeedRoomFromBoard = () => {
    if (!boardId) {
      return;
    }

    setPrefs(
      beginSoloRoomSeed({
        boardId,
        boardName,
        angle,
        climbs: [],
      })
    );
    navigate("/rooms/new");
  };

  const buildPlanClimbs = (): ProviderClimb[] =>
    shortlistForCurrentView.map((climb) => ({
      id: `kilter:${climb.product_size_id}:${climb.uuid}`,
      external_id: climb.uuid,
      provider_id: "kilter",
      surface_id: boardId,
      name: climb.climb_name,
      setter_name: climb.setter_name,
      primary_grade: climb.grade,
      popularity: climb.ascends,
      meta: {
        board_id: climb.board_id,
        board_name: climb.board_name,
        angle: String(climb.angle),
      },
      media: climb.image_filename
        ? [
            {
              kind: "image",
              url: api.getImageUrl(climb.image_filename),
            },
          ]
        : undefined,
    }));

  const handleSharePlan = async () => {
    if (!boardId || shortlistForCurrentView.length === 0) {
      showErrorToast("Add at least one shortlisted climb before creating a shareable plan.");
      return;
    }

    setSharingPlan(true);
    try {
      const plan = await api.createSoloPlan({
        providerId: "kilter",
        title: planTitle.trim() || `${boardName} plan`,
        notes: planNotes.trim() || undefined,
        surface: {
          id: boardId,
          kind: "board",
          name: boardName,
          meta: {
            board_id: boardId,
            angle: String(angle),
          },
        },
        filters: {
          angle: String(angle),
          sort,
          q: nameQuery || "",
          setter: setterQuery || "",
          grade: gradeQuery || "",
        },
        climbs: buildPlanClimbs(),
        openPath:
          typeof window !== "undefined"
            ? `${window.location.pathname}${window.location.search}`
            : undefined,
        createdBy: prefs.savedDisplayName || undefined,
      });
      trackProductEvent("solo_plan.create", {
        properties: {
          provider_id: "kilter",
          climb_count: shortlistForCurrentView.length,
        },
      });
      navigate(`/plans/${plan.share_id}`);
    } catch (error) {
      console.error("Create solo plan failed", error);
      showErrorToast("Unable to create a shareable solo plan from this shortlist.");
    } finally {
      setSharingPlan(false);
    }
  };

  if (initialLoad && loading) {
    return (
      <LoadingSlideshow
        title="Loading solo browse"
        description={`Pulling climbs for ${boardsLoading ? "the selected board" : boardName}.`}
        detail="Preparing the board image, hold overlay, and filter state for the current solo session."
      />
    );
  }

  return (
    <SidebarProvider
      defaultOpen={true}
      className="bg-[radial-gradient(circle_at_top_left,_rgba(15,118,110,0.18),_transparent_35%),linear-gradient(135deg,_rgba(255,255,255,0.98),_rgba(240,253,250,0.92))] md:h-[calc(100dvh-5rem)] md:min-h-0"
    >
      <div className="flex min-h-screen w-full md:h-full md:min-h-0">
        <Sidebar
          boardName={boardName}
          climbs={climbs}
          selectedClimb={selectedClimb}
          onClimbSelect={handleClimbSelect}
          onBackClick={() => navigate(backPath)}
          angle={angle}
          onAngleChange={(nextAngle) =>
            updateSearchState({ angle: String(nextAngle), sort, q: nameQuery, setter: setterQuery, grade: gradeQuery })
          }
          sort={sort}
          onSortChange={(nextSort) =>
            updateSearchState({ angle: String(angle), sort: nextSort, q: nameQuery, setter: setterQuery, grade: gradeQuery })
          }
          nameQuery={nameQuery}
          setterQuery={setterQuery}
          gradeQuery={gradeQuery}
          onNameChange={(value) =>
            updateSearchState({ angle: String(angle), sort, q: value, setter: setterQuery, grade: gradeQuery })
          }
          onSetterChange={(value) =>
            updateSearchState({ angle: String(angle), sort, q: nameQuery, setter: value, grade: gradeQuery })
          }
          onGradeChange={(value) =>
            updateSearchState({ angle: String(angle), sort, q: nameQuery, setter: setterQuery, grade: value })
          }
          currentPage={currentPage}
          hasNextPage={hasNextPage}
          onNextPage={goToNextPage}
          onPreviousPage={goToPreviousPage}
          pageLoading={pageLoading}
        />

        <SidebarInset className="bg-transparent md:h-full md:min-h-0 md:overflow-hidden">
          <div className="flex min-h-screen flex-col px-4 py-5 sm:px-6 md:h-full md:min-h-0 md:overflow-hidden">
            <div className="md:hidden">
              <Card className="border-0 bg-white/85 shadow-xl shadow-teal-950/10 backdrop-blur">
                <CardHeader className="gap-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <SidebarTrigger className="md:hidden">
                      <span>Filters & climbs</span>
                    </SidebarTrigger>
                    <Button
                      variant="ghost"
                      onClick={() => navigate(backPath)}
                      className="flex items-center gap-2 rounded-xl"
                    >
                      <ChevronLeft className="h-4 w-4" />
                      Back
                    </Button>
                  </div>
                  <div className="space-y-2">
                    <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
                      Solo Kilter Browse
                    </p>
                    <h2 className="text-2xl font-semibold">{boardName}</h2>
                    <p className="text-sm text-muted-foreground">
                      Open the catalog sheet to filter the board and jump between climbs on this device.
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        type="button"
                        variant="secondary"
                        onClick={handleSeedRoomFromBoard}
                      >
                        Start room on this board
                      </Button>
                      {shortlistForCurrentView.length > 0 ? (
                        <Button
                          type="button"
                          variant="secondary"
                          onClick={handleSeedRoomFromShortlist}
                        >
                          Start room from shortlist
                        </Button>
                      ) : null}
                      <Button
                        type="button"
                        variant={savedFilterID ? "secondary" : "outline"}
                        onClick={handleSaveFilterPreset}
                      >
                        {savedFilterID ? "Filter saved" : "Save filter preset"}
                      </Button>
                    </div>
                  </div>
                </CardHeader>
              </Card>
            </div>

            <div className="hidden md:block">
              <Card className="border-0 bg-white/85 shadow-xl shadow-teal-950/10 backdrop-blur">
                <CardHeader className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-start">
                  <div className="flex items-start gap-3">
                    <SidebarTrigger className="mt-1" />
                    <div>
                      <p className="text-sm uppercase tracking-[0.35em] text-muted-foreground">
                        Solo Kilter Browse
                      </p>
                      <CardTitle className="mt-2 text-3xl tracking-tight">{boardName}</CardTitle>
                      <CardDescription className="mt-2 max-w-2xl text-sm leading-6">
                        Read-only climb scouting with the same local catalog used by rooms. Filter in the sidebar, then inspect the overlay and metadata here.
                      </CardDescription>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 lg:justify-end">
                    <Badge variant="secondary">{angle}°</Badge>
                    <Badge variant="outline">{sort}</Badge>
                    <Badge variant="outline">
                      <Layers3 className="mr-1 h-3.5 w-3.5" />
                      {climbs.length} visible
                    </Badge>
                    {prefs.soloFavorites.length > 0 ? (
                      <Badge variant="outline">
                        <Heart className="mr-1 h-3.5 w-3.5" />
                        {prefs.soloFavorites.length} favorites
                      </Badge>
                    ) : null}
                    {prefs.soloShortlist.length > 0 ? (
                      <Badge variant="outline">
                        <ListChecks className="mr-1 h-3.5 w-3.5" />
                        {prefs.soloShortlist.length} shortlisted
                      </Badge>
                    ) : null}
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      onClick={handleSeedRoomFromBoard}
                    >
                      Start room on this board
                    </Button>
                    {shortlistForCurrentView.length > 0 ? (
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        onClick={handleSeedRoomFromShortlist}
                      >
                        Start room from shortlist
                      </Button>
                    ) : null}
                    <Button
                      type="button"
                      variant={savedFilterID ? "secondary" : "outline"}
                      size="sm"
                      onClick={handleSaveFilterPreset}
                    >
                      {savedFilterID ? "Filter saved" : "Save filter preset"}
                    </Button>
                    <Button asChild variant="ghost" size="sm">
                      <Link to={backPath}>
                        <ChevronLeft className="mr-2 h-4 w-4" />
                        Back
                      </Link>
                    </Button>
                  </div>
                </CardHeader>
              </Card>
            </div>

            <div className="order-2 mt-4 md:hidden md:order-none">
              <Card className="mx-4 mb-4 border-0 bg-white/88 shadow-lg shadow-teal-950/10 backdrop-blur">
                <CardHeader className="space-y-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <CardTitle className="text-xl">Shareable solo plan</CardTitle>
                      <CardDescription>
                        Turn this shortlist into an immutable plan link.
                      </CardDescription>
                    </div>
                    <Badge variant="outline">{shortlistForCurrentView.length} climbs</Badge>
                  </div>
                  <Input
                    value={planTitle}
                    onChange={(event) => setPlanTitle(event.target.value)}
                    placeholder="Plan title"
                  />
                  <textarea
                    value={planNotes}
                    onChange={(event) => setPlanNotes(event.target.value)}
                    placeholder="Optional planning notes"
                    className="min-h-24 rounded-xl border border-input bg-background px-3 py-2 text-sm shadow-sm outline-none ring-offset-background placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    disabled={sharingPlan || shortlistForCurrentView.length === 0}
                    onClick={() => void handleSharePlan()}
                  >
                    <Share2 className="mr-2 h-4 w-4" />
                    {sharingPlan ? "Creating plan..." : "Create shareable plan"}
                  </Button>
                </CardHeader>
              </Card>
              <div className="px-4 pb-4">
                <Card className="border-0 bg-white/85 shadow-lg shadow-teal-950/10 backdrop-blur">
                  <CardHeader className="flex flex-row items-center justify-between gap-2 space-y-0">
                    <Button
                      variant="outline"
                      onClick={goToPreviousPage}
                      disabled={currentPage === 1 || pageLoading}
                      className="flex-1 rounded-xl"
                    >
                      Previous
                    </Button>
                    <span className="px-3 text-sm text-muted-foreground">
                      {pageLoading ? "Loading..." : `Page ${currentPage}`}
                    </span>
                    <Button
                      variant="outline"
                      onClick={goToNextPage}
                      disabled={!hasNextPage || pageLoading}
                      className="flex-1 rounded-xl"
                    >
                      Next
                    </Button>
                  </CardHeader>
                </Card>
              </div>
            </div>

            <div className="order-1 mt-4 min-w-0 flex-1 overflow-auto md:order-none md:min-h-0">
              <Card className="mb-3 hidden border-0 bg-white/88 shadow-lg shadow-teal-950/10 backdrop-blur md:block">
                <CardHeader className="grid gap-3 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)_auto] lg:items-start">
                  <div>
                    <CardTitle className="text-xl">Shareable solo plan</CardTitle>
                    <CardDescription className="mt-1 text-sm leading-6">
                      Package the current shortlist, board context, and filters into an immutable public plan.
                    </CardDescription>
                  </div>
                  <div className="grid gap-3">
                    <Input
                      value={planTitle}
                      onChange={(event) => setPlanTitle(event.target.value)}
                      placeholder="Plan title"
                    />
                    <textarea
                      value={planNotes}
                      onChange={(event) => setPlanNotes(event.target.value)}
                      placeholder="Optional planning notes"
                      className="min-h-16 rounded-xl border border-input bg-background px-3 py-2 text-sm shadow-sm outline-none ring-offset-background placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
                    />
                  </div>
                  <div className="flex flex-col items-stretch gap-2.5 lg:w-52">
                    <Badge variant="outline" className="justify-center">
                      {shortlistForCurrentView.length} climbs in plan
                    </Badge>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={sharingPlan || shortlistForCurrentView.length === 0}
                      onClick={() => void handleSharePlan()}
                    >
                      <Share2 className="mr-2 h-4 w-4" />
                      {sharingPlan ? "Creating..." : "Create shareable plan"}
                    </Button>
                  </div>
                </CardHeader>
              </Card>
              <ProblemView
                selectedClimb={selectedClimb}
                angle={angle}
                hasResults={climbs.length > 0}
                isFavorite={isFavorite}
                isShortlisted={isShortlisted}
                onToggleFavorite={handleToggleFavorite}
                onToggleShortlist={handleToggleShortlist}
              />
            </div>
          </div>
        </SidebarInset>
      </div>
    </SidebarProvider>
  );
}
