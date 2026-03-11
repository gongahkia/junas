import {
  startTransition,
  useDeferredValue,
  useEffect,
  useRef,
  useState,
} from "react";
import { Heart, Layers3, ListChecks } from "lucide-react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ChevronLeft } from "lucide-react";
import { api } from "../api";
import type { Board, Climb } from "../types";
import Sidebar from "./Sidebar";
import MobileDropdown from "./MobileDropdown";
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
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { useErrorToast } from "@/hooks/use-toast";

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
  const selectedUuid = searchParams.get("climb") ?? "";
  const deferredNameQuery = useDeferredValue(nameQuery);
  const deferredSetterQuery = useDeferredValue(setterQuery);

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
      sort,
      climb: selectedClimb?.uuid,
    });
  }, [angle, boardId, nameQuery, selectedClimb?.uuid, setterQuery, sort]);

  useEffect(() => {
    setSavedFilterID("");
  }, [angle, boardId, nameQuery, setterQuery, sort]);

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
      className="bg-[radial-gradient(circle_at_top_left,_rgba(15,118,110,0.18),_transparent_35%),linear-gradient(135deg,_rgba(255,255,255,0.98),_rgba(240,253,250,0.92))]"
    >
      <div className="flex min-h-screen w-full">
        <Sidebar
          boardName={boardName}
          climbs={climbs}
          selectedClimb={selectedClimb}
          onClimbSelect={handleClimbSelect}
          onBackClick={() => navigate(backPath)}
          angle={angle}
          onAngleChange={(nextAngle) =>
            updateSearchState({ angle: String(nextAngle), sort })
          }
          sort={sort}
          onSortChange={(nextSort) =>
            updateSearchState({ angle: String(angle), sort: nextSort })
          }
          nameQuery={nameQuery}
          setterQuery={setterQuery}
          onNameChange={(value) =>
            updateSearchState({ angle: String(angle), sort, q: value, setter: setterQuery })
          }
          onSetterChange={(value) =>
            updateSearchState({ angle: String(angle), sort, q: nameQuery, setter: value })
          }
          currentPage={currentPage}
          hasNextPage={hasNextPage}
          onNextPage={goToNextPage}
          onPreviousPage={goToPreviousPage}
          pageLoading={pageLoading}
        />

        <SidebarInset className="bg-transparent">
          <div className="flex min-h-screen flex-col px-4 py-5 sm:px-6">
            <div className="md:hidden">
              <Card className="border-0 bg-white/85 shadow-xl shadow-teal-950/10 backdrop-blur">
                <CardHeader className="gap-3">
                  <div className="flex items-center gap-2">
                    <SidebarTrigger className="md:hidden" />
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
                    <div className="flex flex-wrap gap-2">
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
                <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0">
                  <div className="flex items-start gap-3">
                    <SidebarTrigger className="mt-1" />
                    <div>
                      <p className="text-sm uppercase tracking-[0.35em] text-muted-foreground">
                        Solo Kilter Browse
                      </p>
                      <CardTitle className="mt-3 text-4xl tracking-tight">{boardName}</CardTitle>
                      <CardDescription className="mt-3 max-w-2xl text-base leading-7">
                        Read-only climb scouting with the same local catalog used by rooms. Filter in the sidebar, then inspect the overlay and metadata here.
                      </CardDescription>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
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
                    <Button asChild variant="ghost">
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
              <MobileDropdown
                climbs={climbs}
                selectedClimb={selectedClimb}
                onClimbSelect={handleClimbSelect}
                angle={angle}
                onAngleChange={(nextAngle) =>
                  updateSearchState({ angle: String(nextAngle), sort })
                }
                sort={sort}
                onSortChange={(nextSort) =>
                  updateSearchState({ angle: String(angle), sort: nextSort })
                }
                nameQuery={nameQuery}
                setterQuery={setterQuery}
                onNameChange={(value) =>
                  updateSearchState({ angle: String(angle), sort, q: value, setter: setterQuery })
                }
                onSetterChange={(value) =>
                  updateSearchState({ angle: String(angle), sort, q: nameQuery, setter: value })
                }
              />

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

            <div className="order-1 mt-4 min-w-0 flex-1 overflow-auto md:order-none">
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
