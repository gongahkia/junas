import { useEffect, useState, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ChevronLeft } from "lucide-react";
import { api } from "../api";
import type { Climb, LocationState } from "../types";
import Sidebar from "./Sidebar";
import MobileDropdown from "./MobileDropdown";
import ProblemView from "./ProblemView";
import { Button } from "@/components/ui/button";
import {
  SidebarProvider,
  SidebarInset,
  SidebarTrigger,
} from "@/components/ui/sidebar";

interface ClimbViewProps {
  angle: number;
  onAngleChange: (angle: number) => void;
}

export default function ClimbView({ angle, onAngleChange }: ClimbViewProps) {
  const [climbs, setClimbs] = useState<Climb[]>([]);
  const [loading, setLoading] = useState(true);
  const [pageLoading, setPageLoading] = useState(false);
  const [selectedClimb, setSelectedClimb] = useState<Climb | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [hasNextPage, setHasNextPage] = useState(false);
  const [isInitialized, setIsInitialized] = useState(false);
  const cursorsRef = useRef<Record<number, string>>({});
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state as LocationState;
  const boardId = state?.boardId;
  const boardName = state?.boardName;
  const PAGE_SIZE = 10;

  useEffect(() => {
    if (!boardId) {
      navigate("/");
      return;
    }

    const fetchPage = async (page: number) => {
      try {
        // Only show full loading screen for the very first load
        const isFirstLoad = !isInitialized;
        if (isFirstLoad) {
          setLoading(true);
        } else {
          setPageLoading(true);
        }

        const cursor = page > 1 ? cursorsRef.current[page] : undefined;
        const paginatedData = await api.getPaginatedClimbs(
          boardId,
          angle,
          cursor,
          PAGE_SIZE
        );
        setClimbs(paginatedData.climbs);
        setHasNextPage(paginatedData.has_more);

        // Store cursor for next page if it exists
        if (paginatedData.next_cursor) {
          cursorsRef.current = {
            ...cursorsRef.current,
            [page + 1]: paginatedData.next_cursor,
          };
        }

        // Always set first problem as selected when loading a page
        if (paginatedData.climbs.length > 0) {
          setSelectedClimb(paginatedData.climbs[0]);
        }

        if (isFirstLoad) {
          setLoading(false);
          setIsInitialized(true);
        } else {
          setPageLoading(false);
        }
      } catch (error) {
        console.error("API Error:", error);
        setClimbs([]);
        setLoading(false);
        setPageLoading(false);
      }
    };

    fetchPage(currentPage);
  }, [boardId, angle, currentPage, navigate, isInitialized]);

  const goToNextPage = () => {
    if (hasNextPage) {
      setCurrentPage((prev) => prev + 1);
    }
  };

  const goToPreviousPage = () => {
    if (currentPage > 1) {
      setCurrentPage((prev) => prev - 1);
    }
  };

  const handleClimbSelect = (climb: Climb) => {
    setSelectedClimb(climb);
  };

  const handleAngleChange = (newAngle: number) => {
    setLoading(true);
    setSelectedClimb(null); // Clear selected climb when angle changes
    setClimbs([]); // Clear existing climbs
    setCurrentPage(1); // Reset to first page
    setHasNextPage(false); // Reset pagination
    setIsInitialized(false); // Reset initialization state
    cursorsRef.current = {}; // Reset cursors
    onAngleChange(newAngle);
  };

  const handleBackClick = () => {
    navigate("/");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg text-muted-foreground">Loading climbs...</div>
      </div>
    );
  }

  return (
    <SidebarProvider defaultOpen={true}>
      <div className="min-h-screen bg-background flex">
        {/* Sidebar */}
        <Sidebar
          boardName={boardName}
          climbs={climbs}
          selectedClimb={selectedClimb}
          onClimbSelect={handleClimbSelect}
          onBackClick={handleBackClick}
          angle={angle}
          onAngleChange={handleAngleChange}
          currentPage={currentPage}
          hasNextPage={hasNextPage}
          onNextPage={goToNextPage}
          onPreviousPage={goToPreviousPage}
          pageLoading={pageLoading}
        />

        {/* Main Content */}
        <SidebarInset>
          <div className="flex flex-col h-screen">
            {/* Mobile Header */}
            <div className="md:hidden bg-card shadow-sm border-b">
              <div className="px-4 py-3">
                <div className="flex items-center gap-2 mb-2">
                  <SidebarTrigger className="md:hidden" />
                  <Button
                    variant="ghost"
                    onClick={() => navigate("/")}
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

            {/* Desktop Header */}
            <div className="hidden md:flex items-center gap-2 p-4 border-b bg-card">
              <SidebarTrigger />
              <h2 className="text-xl">{boardName}</h2>
            </div>

            {/* Mobile Dropdown - only show when sidebar is hidden */}
            <div className="md:hidden">
              <MobileDropdown
                climbs={climbs}
                selectedClimb={selectedClimb}
                onClimbSelect={handleClimbSelect}
                angle={angle}
                onAngleChange={handleAngleChange}
              />
              {/* Mobile Pagination */}
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

            {/* Problem View */}
            <div className="flex-1 p-4 md:p-6 overflow-auto">
              <ProblemView selectedClimb={selectedClimb} angle={angle} />
            </div>
          </div>
        </SidebarInset>
      </div>
    </SidebarProvider>
  );
}
