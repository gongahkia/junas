import { useEffect, useState } from "react";
import type { ProviderClimb, ProviderId } from "@/types";
import { config } from "@/config";
import { formatClimbDate } from "@/lib/climbs";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useErrorToast } from "@/hooks/use-toast";
import KilterBoardImage from "@/components/KilterBoardImage";

interface RoomProblemViewProps {
  climb: ProviderClimb | null;
  providerId: ProviderId;
  hasResults: boolean;
}

export default function RoomProblemView({
  climb,
  providerId,
  hasResults,
}: RoomProblemViewProps) {
  const showErrorToast = useErrorToast();
  const [failedImages, setFailedImages] = useState<Record<string, true>>({});
  const [notifiedClimbId, setNotifiedClimbId] = useState("");

  useEffect(() => {
    setFailedImages({});
    setNotifiedClimbId("");
  }, [climb?.id]);

  const allImageMedia = (climb?.media ?? []).filter((media) => media.kind === "image");
  const imageMedia = allImageMedia.filter((media) => !failedImages[media.url]);

  useEffect(() => {
    if (!climb || allImageMedia.length === 0 || imageMedia.length > 0) {
      return;
    }
    if (notifiedClimbId === climb.id) {
      return;
    }

    showErrorToast("Climb images failed to load for this room entry.");
    setNotifiedClimbId(climb.id);
  }, [allImageMedia.length, climb, imageMedia.length, notifiedClimbId, showErrorToast]);

  if (!climb) {
    return (
      <Card className="h-full">
        <CardContent className="flex h-full min-h-[18rem] items-center justify-center text-muted-foreground">
          {hasResults
            ? "Select a climb to inspect it."
            : "No climbs match the current room filters."}
        </CardContent>
      </Card>
    );
  }

  const fallbackMetadata = climb.meta ?? {};

  return (
    <Card className="h-full gap-4">
      <CardHeader>
        <CardTitle className="text-3xl">{climb.name}</CardTitle>
        {climb.description ? (
          <CardDescription className="text-sm leading-7">
            {climb.description}
          </CardDescription>
        ) : null}
      </CardHeader>
      <CardContent className="grid gap-6">
        <div className="grid gap-3 text-sm text-muted-foreground sm:grid-cols-2">
          <span>Primary grade: {climb.primary_grade || "Unknown"}</span>
          <span>
            {providerId === "kilter" ? "Route grade" : "Secondary info"}:{" "}
            {climb.secondary_grade || "Unknown"}
          </span>
          <span>Setter: {climb.setter_name || "Unknown"}</span>
          <span>
            {providerId === "kilter" ? "Ascends" : "Sends"}:{" "}
            {climb.popularity ?? 0}
          </span>
          <span>Created: {formatClimbDate(climb.created_at)}</span>
          <span>
            Surface:{" "}
            {fallbackMetadata.gym_name ||
              fallbackMetadata.board_id ||
              climb.surface_id}
          </span>
        </div>

        <div className="flex min-h-[20rem] items-center justify-center rounded-2xl border bg-muted/20 p-4">
          {imageMedia.length === 0 ? (
            <p className="text-center text-sm text-muted-foreground">
              {allImageMedia.length > 0
                ? "Preview unavailable for this provider entry."
                : "No climb images are available for this provider entry."}
            </p>
          ) : (
            <KilterBoardImage
              layers={imageMedia.map((media, index) => ({
                key: media.url,
                src: resolveMediaUrl(media.url),
                alt: `${climb.name} layer ${index + 1}`,
              }))}
              highlightedHolds={
                providerId === "kilter" ? climb.highlighted_holds : undefined
              }
              onLayerError={(url) =>
                setFailedImages((previousState) => ({
                  ...previousState,
                  [url]: true,
                }))
              }
            />
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function resolveMediaUrl(url: string): string {
  if (/^(https?:)?\/\//i.test(url) || url.startsWith("data:")) {
    return url;
  }

  if (url.startsWith("/")) {
    return url;
  }

  const baseUrl = config.api.baseUrl.replace(/\/+$/, "");
  return `${baseUrl}/${url.replace(/^\/+/, "")}`;
}
