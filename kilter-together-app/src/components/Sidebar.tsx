import AngleSelector from "./AngleSelector";
import SortSelector from "./SortSelector";
import type { Climb, ClimbSort } from "../types";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { getGradeForAngle } from "@/lib/climbs";
import { ChevronLeft } from "lucide-react";
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
    <SidebarPrimitive variant="sidebar" collapsible="icon">
      <SidebarHeader>
        <Button variant="ghost" onClick={onBackClick} className="justify-start">
          <ChevronLeft className="w-4 h-4 mr-2" />
          <span>Back to Boards</span>
        </Button>
        <div className="px-2">
          <h2 className="text-xl truncate">{boardName}</h2>
        </div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Controls</SidebarGroupLabel>
          <SidebarGroupContent>
            <div className="space-y-3 p-2">
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
            </div>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel>Problems</SidebarGroupLabel>
          <SidebarGroupContent>
            <div className="space-y-1 p-1">
              {climbs.length === 0 ? (
                <div className="rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
                  No climbs match the current filters.
                </div>
              ) : (
                climbs.map((climb) => (
                  <Card
                    key={climb.uuid}
                    className={`p-2 cursor-pointer transition-colors ${
                      selectedClimb?.uuid === climb.uuid
                        ? "border-primary bg-primary/5"
                        : "hover:bg-muted/50"
                    }`}
                    onClick={() => onClimbSelect(climb)}
                  >
                    <CardContent className="p-3 space-y-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-medium truncate">
                          {climb.climb_name}
                        </span>
                        <Badge
                          variant="secondary"
                          className="text-xs flex-shrink-0"
                        >
                          {getGradeForAngle(climb, angle)}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {climb.setter_name} • {climb.ascends} ascends
                      </p>
                    </CardContent>
                  </Card>
                ))
              )}

              <div className="flex items-center justify-between gap-2 pt-3 border-t">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onPreviousPage}
                  disabled={currentPage === 1 || pageLoading}
                  className="flex-1"
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
                  className="flex-1"
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
