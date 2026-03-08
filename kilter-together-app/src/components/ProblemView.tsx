import { api } from "../api";
import type { Climb } from "../types";
import { getGradeForAngle } from "../types";

interface ProblemViewProps {
  selectedClimb: Climb | null;
  angle: number;
}

export default function ProblemView({
  selectedClimb,
  angle,
}: ProblemViewProps) {
  const getImageFilenames = (climb: Climb): string[] =>
    climb.image_filenames || [];

  if (!selectedClimb) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-muted-foreground text-lg">
          Select a problem to view images
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="mb-4">
        <h3 className="text-2xl mb-2">{selectedClimb.climb_name}</h3>
        <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
          <span>Grade: {getGradeForAngle(selectedClimb, angle)}</span>
          <span>Setter: {selectedClimb.setter_name}</span>
          <span>Ascends: {selectedClimb.ascends}</span>
        </div>
      </div>
      {/* Overlapped Images Container */}
      <div className="flex-1 flex items-center justify-center">
        <div className="relative max-w-full max-h-full">
          {getImageFilenames(selectedClimb).map((filename, index) => (
            <img
              key={index}
              src={api.getImageUrl(filename)}
              alt={`Hold position ${index + 1}`}
              className={`max-w-full max-h-[70vh] object-contain ${
                index === 0 ? "relative" : "absolute top-0 left-0"
              }`}
              style={{
                mixBlendMode: index > 0 ? "multiply" : "normal",
              }}
              crossOrigin="anonymous"
            />
          ))}
        </div>
      </div>
    </div>
  );
}
