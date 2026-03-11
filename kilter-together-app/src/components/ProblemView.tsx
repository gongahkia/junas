import { useEffect, useState } from "react";
import { Heart, ListChecks } from "lucide-react";
import { api } from "../api";
import type { Climb } from "../types";
import {
  formatClimbDate,
  getGradeForAngle,
  getRouteGradeForAngle,
} from "@/lib/climbs";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import { useErrorToast } from "@/hooks/use-toast";
import KilterBoardImage from "@/components/KilterBoardImage";

interface ProblemViewProps {
  selectedClimb: Climb | null;
  angle: number;
  hasResults: boolean;
  isFavorite?: boolean;
  isShortlisted?: boolean;
  onToggleFavorite?: () => void;
  onToggleShortlist?: () => void;
}

export default function ProblemView({
  selectedClimb,
  angle,
  hasResults,
  isFavorite = false,
  isShortlisted = false,
  onToggleFavorite,
  onToggleShortlist,
}: ProblemViewProps) {
  const showErrorToast = useErrorToast();
  const [failedImages, setFailedImages] = useState<Record<string, true>>({});
  const [notifiedClimbId, setNotifiedClimbId] = useState("");

  useEffect(() => {
    setFailedImages({});
    setNotifiedClimbId("");
  }, [selectedClimb?.uuid]);

  const imageFilenames = selectedClimb?.image_filenames || [];
  const visibleImages = imageFilenames.filter(
    (filename) => !failedImages[filename],
  );

  useEffect(() => {
    if (!selectedClimb || imageFilenames.length === 0 || visibleImages.length > 0) {
      return;
    }
    if (notifiedClimbId === selectedClimb.uuid) {
      return;
    }

    showErrorToast("Board images failed to load for this climb.");
    setNotifiedClimbId(selectedClimb.uuid);
  }, [
    imageFilenames.length,
    notifiedClimbId,
    selectedClimb,
    showErrorToast,
    visibleImages.length,
  ]);

  if (!selectedClimb) {
    return (
      <Card className="h-full border-0 bg-white/85 shadow-xl shadow-teal-950/10 backdrop-blur">
        <CardContent className="flex h-full min-h-[24rem] items-center justify-center text-center text-muted-foreground">
          <p className="max-w-md text-lg">
            {hasResults
              ? "Select a problem to view details."
              : "No climbs match the current filters."}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="h-full border-0 bg-white/85 shadow-xl shadow-teal-950/10 backdrop-blur">
      <CardHeader className="gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary">
            {getGradeForAngle(selectedClimb, angle)}
          </Badge>
          <Badge variant="outline">{selectedClimb.ascends} ascends</Badge>
          <Badge variant="outline">{selectedClimb.setter_name}</Badge>
        </div>
        <div>
          <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            {selectedClimb.climb_name}
          </h2>
          {selectedClimb.description ? (
            <CardDescription className="mt-3 max-w-3xl text-base leading-7">
              {selectedClimb.description}
            </CardDescription>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={onToggleFavorite}
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-sm transition-colors ${
              isFavorite
                ? "border-rose-200 bg-rose-50 text-rose-700"
                : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
            }`}
          >
            <Heart className={`h-4 w-4 ${isFavorite ? "fill-current" : ""}`} />
            {isFavorite ? "Saved to favorites" : "Add to favorites"}
          </button>
          <button
            type="button"
            onClick={onToggleShortlist}
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-sm transition-colors ${
              isShortlisted
                ? "border-teal-200 bg-teal-50 text-teal-700"
                : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
            }`}
          >
            <ListChecks className="h-4 w-4" />
            {isShortlisted ? "In shortlist" : "Add to shortlist"}
          </button>
        </div>
      </CardHeader>

      <CardContent className="grid gap-6">
        <div className="grid gap-3 text-sm text-muted-foreground sm:grid-cols-2 xl:grid-cols-3">
          <span>Boulder grade: {getGradeForAngle(selectedClimb, angle)}</span>
          <span>
            Route grade: {getRouteGradeForAngle(selectedClimb, angle)}
          </span>
          <span>Setter: {selectedClimb.setter_name}</span>
          <span>Ascends: {selectedClimb.ascends}</span>
          <span>Created: {formatClimbDate(selectedClimb.created_at)}</span>
          <span>Board size ID: {selectedClimb.product_size_id}</span>
        </div>

        <div className="flex flex-1 items-center justify-center rounded-3xl border bg-[radial-gradient(circle_at_top_left,_rgba(15,118,110,0.12),_transparent_45%),linear-gradient(180deg,_rgba(255,255,255,0.88),_rgba(240,249,255,0.65))] p-4">
          {imageFilenames.length === 0 ? (
            <p className="text-muted-foreground">
              No board images are available for this climb.
            </p>
          ) : visibleImages.length === 0 ? (
            <p className="text-muted-foreground">
              Preview unavailable for this climb.
            </p>
          ) : (
            <KilterBoardImage
              layers={visibleImages.map((filename, index) => ({
                key: filename,
                src: api.getImageUrl(filename),
                alt: `${selectedClimb.climb_name} board layer ${index + 1}`,
              }))}
              highlightedHolds={selectedClimb.highlighted_holds}
              onLayerError={(filename) =>
                setFailedImages((previousState) => ({
                  ...previousState,
                  [filename]: true,
                }))
              }
            />
          )}
        </div>
      </CardContent>
    </Card>
  );
}
