import { useEffect, useState } from "react";
import { api } from "../api";
import type { Climb } from "../types";
import {
  formatClimbDate,
  getGradeForAngle,
  getRouteGradeForAngle,
} from "@/lib/climbs";

interface ProblemViewProps {
  selectedClimb: Climb | null;
  angle: number;
  hasResults: boolean;
}

export default function ProblemView({
  selectedClimb,
  angle,
  hasResults,
}: ProblemViewProps) {
  const [failedImages, setFailedImages] = useState<Record<string, true>>({});

  useEffect(() => {
    setFailedImages({});
  }, [selectedClimb?.uuid]);

  const imageFilenames = selectedClimb?.image_filenames || [];
  const visibleImages = imageFilenames.filter((filename) => !failedImages[filename]);

  if (!selectedClimb) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-muted-foreground text-lg">
          {hasResults
            ? "Select a problem to view details."
            : "No climbs match the current filters."}
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full gap-6">
      <div className="space-y-3">
        <div>
          <h3 className="text-3xl">{selectedClimb.climb_name}</h3>
          {selectedClimb.description ? (
            <p className="mt-2 text-muted-foreground">
              {selectedClimb.description}
            </p>
          ) : null}
        </div>

        <div className="grid gap-3 text-sm text-muted-foreground sm:grid-cols-2 xl:grid-cols-3">
          <span>Boulder grade: {getGradeForAngle(selectedClimb, angle)}</span>
          <span>Route grade: {getRouteGradeForAngle(selectedClimb, angle)}</span>
          <span>Setter: {selectedClimb.setter_name}</span>
          <span>Ascends: {selectedClimb.ascends}</span>
          <span>Created: {formatClimbDate(selectedClimb.created_at)}</span>
          <span>Board size ID: {selectedClimb.product_size_id}</span>
        </div>
      </div>

      <div className="flex-1 flex items-center justify-center rounded-2xl border bg-card/30 p-4">
        {imageFilenames.length === 0 ? (
          <p className="text-muted-foreground">No board images are available for this climb.</p>
        ) : visibleImages.length === 0 ? (
          <p className="text-muted-foreground">Board images failed to load for this climb.</p>
        ) : (
          <div className="relative max-w-full max-h-full">
            {visibleImages.map((filename, index) => (
              <img
                key={filename}
                src={api.getImageUrl(filename)}
                alt={`${selectedClimb.climb_name} board layer ${index + 1}`}
                className={`max-w-full max-h-[70vh] object-contain ${
                  index === 0 ? "relative" : "absolute top-0 left-0"
                }`}
                style={{
                  mixBlendMode: index > 0 ? "multiply" : "normal",
                }}
                onError={() =>
                  setFailedImages((previousState) => ({
                    ...previousState,
                    [filename]: true,
                  }))
                }
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
