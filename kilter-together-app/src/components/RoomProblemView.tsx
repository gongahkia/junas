import { useEffect, useState } from "react";
import type { ProviderClimb, ProviderId } from "@/types";
import { config } from "@/config";
import { formatClimbDate } from "@/lib/climbs";
import DetailGrid, { type DetailGridItem } from "@/components/DetailGrid";
import { Badge } from "@/components/ui/badge";
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
  const metadataBadges = [
    fallbackMetadata.source_label,
    fallbackMetadata.color,
    fallbackMetadata.foot_rules,
  ].filter((value): value is string => Boolean(value?.trim()));
  const detailItems: DetailGridItem[] = [
    {
      label: "Primary grade",
      value: climb.primary_grade || "Unknown",
    },
    {
      label:
        providerId === "kilter"
          ? "Route grade"
          : providerId === "crux"
            ? "Angle"
            : "Secondary info",
      value: climb.secondary_grade || "Unknown",
    },
    {
      label: "Setter",
      value: climb.setter_name || "Unknown",
    },
    {
      label: providerId === "kilter" ? "Ascends" : "Sends",
      value: (climb.popularity ?? 0).toLocaleString(),
    },
    {
      label: "Created",
      value: formatClimbDate(climb.created_at),
    },
    {
      label: providerId === "crux" ? "Gym" : "Surface",
      value: fallbackMetadata.gym_name || fallbackMetadata.board_id || climb.surface_id,
    },
  ];
  if (providerId === "crux" && fallbackMetadata.source_label) {
    detailItems.push({
      label: "Catalog source",
      value: fallbackMetadata.source_label,
    });
  }
  if (providerId === "crux" && fallbackMetadata.color) {
    detailItems.push({
      label: "Color",
      value: fallbackMetadata.color,
    });
  }
  if (providerId === "crux" && fallbackMetadata.foot_rules) {
    detailItems.push({
      label: "Foot rules",
      value: fallbackMetadata.foot_rules,
    });
  }

  return (
    <Card className="h-full gap-4">
      <CardHeader>
        <CardTitle className="text-3xl">{climb.name}</CardTitle>
        {climb.description ? (
          <CardDescription className="text-sm leading-7">
            {climb.description}
          </CardDescription>
        ) : null}
        {metadataBadges.length > 0 ? (
          <div className="flex flex-wrap gap-2 pt-2">
            {metadataBadges.map((badge) => (
              <Badge key={badge} variant="secondary">
                {badge}
              </Badge>
            ))}
          </div>
        ) : null}
      </CardHeader>
      <CardContent className="grid gap-6">
        <DetailGrid items={detailItems} />

        <div className="grid gap-4 rounded-2xl border bg-muted/20 p-4">
          <div className="flex min-h-[16rem] items-center justify-center">
            {imageMedia.length === 0 ? (
              <p className="text-center text-sm text-muted-foreground">
                {allImageMedia.length > 0
                  ? "Preview unavailable for this provider entry."
                  : "No climb images are available for this provider entry."}
              </p>
            ) : (
              <div className="inline-block max-w-full">
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
              </div>
            )}
          </div>
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
