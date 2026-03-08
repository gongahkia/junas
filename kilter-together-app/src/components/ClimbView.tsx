import {
  startTransition,
  useDeferredValue,
  useEffect,
  useRef,
  useState,
} from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ChevronLeft } from "lucide-react";
import { api } from "../api";
import type { Board, Climb } from "../types";
import Sidebar from "./Sidebar";
import MobileDropdown from "./MobileDropdown";
import ProblemView from "./ProblemView";
import { normalizeAngle, normalizeSort } from "@/lib/climbs";
import { rememberSoloResume } from "@/lib/user-prefs";
import { Button } from "@/components/ui/button";
import {
  SidebarProvider,
  SidebarInset,
  SidebarTrigger,
} from "@/components/ui/sidebar";

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
  const [climbs, setClimbs] = useState<Climb[]>([]);
  const [loading, setLoading] = useState(true);
  const [pageLoading, setPageLoading] = useState(false);
  const [selectedClimb, setSelectedClimb] = useState<Climb | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [hasNextPage, setHasNextPage] = useState(false);
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
      } finally {
        setLoading(false);
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

  if (loading && currentPage === 1) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg text-muted-foreground">Loading climbs...</div>
      </div>
    );
  }

  return (
    <SidebarProvider defaultOpen={true}>
      <div className="min-h-screen bg-background flex">
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

        <SidebarInset>
          <div className="flex flex-col h-screen">
            <div className="md:hidden bg-card shadow-sm border-b">
              <div className="px-4 py-3">
                <div className="flex items-center gap-2 mb-2">
                  <SidebarTrigger className="md:hidden" />
                  <Button
                    variant="ghost"
                    onClick={() => navigate(backPath)}
                    className="flex items-center gap-2"
                  >
                    <ChevronLeft className="h-4 w-4" />
                    Back
                  </Button>
                </div>
                <div className="flex items-center justify-between">
                  <h2 className="text-xl">{boardName}</h2>
                </div>
              </div>
            </div>

            <div className="hidden md:flex items-center gap-2 p-4 border-b bg-card">
              <SidebarTrigger />
              <h2 className="text-xl">{boardName}</h2>
            </div>

            <div className="md:hidden">
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
                <div className="flex items-center justify-between gap-2">
                  <Button
                    variant="outline"
                    onClick={goToPreviousPage}
                    disabled={currentPage === 1 || pageLoading}
                    className="flex-1"
                  >
                    Previous
                  </Button>
                  <span className="text-sm text-muted-foreground px-3">
                    {pageLoading ? "Loading..." : `Page ${currentPage}`}
                  </span>
                  <Button
                    variant="outline"
                    onClick={goToNextPage}
                    disabled={!hasNextPage || pageLoading}
                    className="flex-1"
                  >
                    Next
                  </Button>
                </div>
              </div>
            </div>

            <div className="flex-1 p-4 md:p-6 overflow-auto">
              <ProblemView
                selectedClimb={selectedClimb}
                angle={angle}
                hasResults={climbs.length > 0}
              />
            </div>
          </div>
        </SidebarInset>
      </div>
    </SidebarProvider>
  );
}
