import AngleSelector from "./AngleSelector";
import type { Climb } from "../types";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getGradeForAngle } from "../types";

interface MobileDropdownProps {
  climbs: Climb[];
  selectedClimb: Climb | null;
  onClimbSelect: (climb: Climb) => void;
  angle: number;
  onAngleChange: (angle: number) => void;
}

export default function MobileDropdown({
  climbs,
  selectedClimb,
  onClimbSelect,
  angle,
  onAngleChange,
}: MobileDropdownProps) {
  return (
    <div className="md:hidden p-4 border-b bg-card">
      <Card>
        <CardContent className="p-4">
          <div className="flex gap-3">
            <AngleSelector
              angle={angle}
              onAngleChange={onAngleChange}
              className="flex-shrink-0"
            />
            <Select
              value={selectedClimb?.uuid || ""}
              onValueChange={(value) => {
                const selected = climbs.find((c) => c.uuid === value);
                if (selected) {
                  onClimbSelect(selected);
                }
              }}
            >
              <SelectTrigger className="flex-1">
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
