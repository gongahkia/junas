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
  const [failedImages, setFailedImages] = useState<Record<string, true>>({});

  useEffect(() => {
    setFailedImages({});
  }, [climb?.id]);

  if (!climb) {
    return (
      <Card className="h-full">
        <CardContent className="flex h-full min-h-[18rem] items-center justify-center text-muted-foreground">
          {hasResults ? "Select a climb to inspect it." : "No climbs match the current room filters."}
        </CardContent>
      </Card>
    );
  }

  const imageMedia = (climb.media ?? []).filter(
    (media) => media.kind === "image" && !failedImages[media.url]
  );
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
            Surface: {fallbackMetadata.gym_name || fallbackMetadata.board_id || climb.surface_id}
          </span>
        </div>

        <div className="flex min-h-[20rem] items-center justify-center rounded-2xl border bg-muted/20 p-4">
          {imageMedia.length === 0 ? (
            <p className="text-center text-sm text-muted-foreground">
              No climb images are available for this provider entry.
            </p>
          ) : (
            <div className="relative max-w-full">
              {imageMedia.map((media, index) => (
                <img
                  key={media.url}
                  src={resolveMediaUrl(media.url)}
                  alt={`${climb.name} layer ${index + 1}`}
                  className={`max-h-[70vh] max-w-full object-contain ${
                    index === 0 ? "relative" : "absolute left-0 top-0"
                  }`}
                  style={{
                    mixBlendMode: index > 0 ? "multiply" : "normal",
                  }}
                  onError={() =>
                    setFailedImages((previousState) => ({
                      ...previousState,
                      [media.url]: true,
                    }))
                  }
                />
              ))}
            </div>
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
