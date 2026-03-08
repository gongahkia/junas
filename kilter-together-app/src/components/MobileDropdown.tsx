import AngleSelector from "./AngleSelector";
import SortSelector from "./SortSelector";
import type { Climb, ClimbSort } from "../types";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getGradeForAngle } from "@/lib/climbs";

interface MobileDropdownProps {
  climbs: Climb[];
  selectedClimb: Climb | null;
  onClimbSelect: (climb: Climb) => void;
  angle: number;
  onAngleChange: (angle: number) => void;
  sort: ClimbSort;
  onSortChange: (sort: ClimbSort) => void;
  nameQuery: string;
  setterQuery: string;
  onNameChange: (value: string) => void;
  onSetterChange: (value: string) => void;
}

export default function MobileDropdown({
  climbs,
  selectedClimb,
  onClimbSelect,
  angle,
  onAngleChange,
  sort,
  onSortChange,
  nameQuery,
  setterQuery,
  onNameChange,
  onSetterChange,
}: MobileDropdownProps) {
  return (
    <div className="md:hidden p-4 border-b bg-card">
      <Card>
        <CardContent className="p-4 space-y-3">
          <div className="flex flex-col gap-3">
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
            <Select
              value={selectedClimb?.uuid || ""}
              onValueChange={(value) => {
                const selected = climbs.find((climb) => climb.uuid === value);
                if (selected) {
                  onClimbSelect(selected);
                }
              }}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select a problem" />
              </SelectTrigger>
              <SelectContent>
                {climbs.map((climb) => (
                  <SelectItem key={climb.uuid} value={climb.uuid}>
                    {climb.climb_name} ({getGradeForAngle(climb, angle)})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
