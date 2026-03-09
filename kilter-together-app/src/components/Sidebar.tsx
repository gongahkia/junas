import AngleSelector from "./AngleSelector";
import SortSelector from "./SortSelector";
import type { Climb, ClimbSort } from "../types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { getGradeForAngle } from "@/lib/climbs";
import { ChevronLeft, Compass } from "lucide-react";
import {
  Sidebar as SidebarPrimitive,
  SidebarContent,
  SidebarHeader,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
} from "@/components/ui/sidebar";

interface SidebarProps {
  boardName: string;
  climbs: Climb[];
  selectedClimb: Climb | null;
  onClimbSelect: (climb: Climb) => void;
  onBackClick: () => void;
  angle: number;
  onAngleChange: (angle: number) => void;
  sort: ClimbSort;
  onSortChange: (sort: ClimbSort) => void;
  nameQuery: string;
  setterQuery: string;
  onNameChange: (value: string) => void;
  onSetterChange: (value: string) => void;
  currentPage: number;
  hasNextPage: boolean;
  onNextPage: () => void;
  onPreviousPage: () => void;
  pageLoading: boolean;
}

export default function Sidebar({
  boardName,
  climbs,
  selectedClimb,
  onClimbSelect,
  onBackClick,
  angle,
  onAngleChange,
  sort,
  onSortChange,
  nameQuery,
  setterQuery,
  onNameChange,
  onSetterChange,
  currentPage,
  hasNextPage,
  onNextPage,
  onPreviousPage,
  pageLoading,
}: SidebarProps) {
  return (
    <SidebarPrimitive
      variant="floating"
      collapsible="icon"
      className="md:top-4 md:bottom-4 md:left-4"
    >
      <SidebarHeader className="gap-3 border-b border-white/70 bg-white/90 p-4 backdrop-blur">
        <Button variant="ghost" onClick={onBackClick} className="justify-start rounded-xl">
          <ChevronLeft className="w-4 h-4 mr-2" />
          <span>Back to boards</span>
        </Button>
        <div className="rounded-2xl border bg-[radial-gradient(circle_at_top_left,_rgba(15,118,110,0.16),_transparent_55%),linear-gradient(135deg,_rgba(255,255,255,0.98),_rgba(240,253,250,0.9))] p-4 shadow-sm">
          <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
            Solo browse
          </p>
          <h2 className="mt-2 text-xl font-semibold truncate">{boardName}</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Scan the catalog fast and keep the detail panel focused on one climb at a time.
          </p>
        </div>
      </SidebarHeader>

      <SidebarContent className="gap-4 bg-white/75 px-2 pb-4">
        <SidebarGroup className="rounded-2xl border bg-white/80 p-0 shadow-sm">
          <SidebarGroupLabel className="h-auto px-4 pt-4 text-[11px] font-semibold uppercase tracking-[0.24em] text-muted-foreground">
            Controls
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <div className="space-y-3 p-4">
              <AngleSelector angle={angle} onAngleChange={onAngleChange} />
              <SortSelector sort={sort} onSortChange={onSortChange} />
              <Input
                value={nameQuery}
                onChange={(event) => onNameChange(event.target.value)}
                placeholder="Search climbs"
              />
              <Input
                value={setterQuery}
                onChange={(event) => onSetterChange(event.target.value)}
                placeholder="Filter by setter"
              />
              <div className="rounded-2xl border bg-muted/20 p-3 text-xs leading-6 text-muted-foreground">
                Local filters update only this device. The solo browser stays independent from room votes and queue state.
              </div>
            </div>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup className="rounded-2xl border bg-white/80 p-0 shadow-sm">
          <SidebarGroupLabel className="flex h-auto items-center gap-2 px-4 pt-4 text-[11px] font-semibold uppercase tracking-[0.24em] text-muted-foreground">
            <Compass className="h-3.5 w-3.5" />
            Problems
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <div className="space-y-2 p-4">
              {climbs.length === 0 ? (
                <div className="rounded-2xl border border-dashed bg-muted/20 p-4 text-sm text-muted-foreground">
                  No climbs match the current filters.
                </div>
              ) : (
                climbs.map((climb) => (
                  <button
                    key={climb.uuid}
                    type="button"
                    className={`w-full rounded-2xl border p-4 text-left transition-all ${
                      selectedClimb?.uuid === climb.uuid
                        ? "border-primary bg-primary/5 shadow-sm"
                        : "bg-white/70 hover:-translate-y-0.5 hover:bg-white hover:shadow-md"
                    }`}
                    onClick={() => onClimbSelect(climb)}
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{climb.climb_name}</p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {climb.setter_name} • {climb.ascends} ascends
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Badge variant="secondary" className="text-xs">
                          {getGradeForAngle(climb, angle)}
                        </Badge>
                        <Badge variant="outline" className="text-xs">
                          ID {climb.uuid.slice(0, 6)}
                        </Badge>
                      </div>
                    </div>
                  </button>
                ))
              )}

              <div className="flex items-center justify-between gap-2 border-t pt-3">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onPreviousPage}
                  disabled={currentPage === 1 || pageLoading}
                  className="flex-1 rounded-xl"
                >
                  Previous
                </Button>
                <span className="text-sm text-muted-foreground px-2">
                  {pageLoading ? "Loading..." : `Page ${currentPage}`}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onNextPage}
                  disabled={!hasNextPage || pageLoading}
                  className="flex-1 rounded-xl"
                >
                  Next
                </Button>
              </div>
            </div>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </SidebarPrimitive>
  );
}
