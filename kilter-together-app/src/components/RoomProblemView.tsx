import { useEffect, useState } from "react";
import type {
  ProviderClimb,
  ProviderId,
  RoomReaction,
  RoomReactionCode,
  RoomStatus,
} from "@/types";
import { config } from "@/config";
import { formatClimbDate } from "@/lib/climbs";
import { cn } from "@/lib/utils";
import {
  ROOM_REACTION_OPTIONS,
  type RoomReactionMeta,
} from "@/lib/room-reactions";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useErrorToast } from "@/hooks/use-toast";
import KilterBoardImage from "@/components/KilterBoardImage";
import RoomReactionOverlay from "@/components/RoomReactionOverlay";

interface RoomProblemViewProps {
  climb: ProviderClimb | null;
  providerId: ProviderId;
  hasResults: boolean;
  reactionsEnabled: boolean;
  canManage: boolean;
  roomStatus: RoomStatus;
  recentReactions: RoomReaction[];
  motionEnabled: boolean;
  emojiReactionsSaving: boolean;
  reactionSendingCode: RoomReactionCode | null;
  onSendReaction: (emojiCode: RoomReactionCode) => void;
  onToggleReactions: (enabled: boolean) => void;
}

export default function RoomProblemView({
  climb,
  providerId,
  hasResults,
  reactionsEnabled,
  canManage,
  roomStatus,
  recentReactions,
  motionEnabled,
  emojiReactionsSaving,
  reactionSendingCode,
  onSendReaction,
  onToggleReactions,
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

        <div className="grid gap-4 rounded-2xl border bg-muted/20 p-4">
          <div className="flex min-h-[16rem] items-center justify-center">
            {imageMedia.length === 0 ? (
              <p className="text-center text-sm text-muted-foreground">
                {allImageMedia.length > 0
                  ? "Preview unavailable for this provider entry."
                  : "No climb images are available for this provider entry."}
              </p>
            ) : (
              <div className="relative inline-block max-w-full">
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
                <RoomReactionOverlay
                  reactions={recentReactions}
                  motionEnabled={motionEnabled}
                />
              </div>
            )}
          </div>

          <div className="rounded-2xl border bg-white/85 p-3">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="space-y-1">
                <p className="text-[11px] uppercase tracking-[0.24em] text-muted-foreground">
                  Emoji reactions
                </p>
                <p className="text-sm text-muted-foreground">
                  {reactionsEnabled
                    ? imageMedia.length > 0
                      ? "Reactions float over the current board preview."
                      : "Reactions are on. They will float over the preview once imagery is available."
                    : canManage
                      ? "Guests cannot react until you turn this back on."
                      : "The host paused emoji reactions for now."}
                </p>
              </div>
              {canManage ? (
                <Button
                  type="button"
                  size="sm"
                  variant={reactionsEnabled ? "secondary" : "outline"}
                  disabled={emojiReactionsSaving || roomStatus === "closed"}
                  onClick={() => onToggleReactions(!reactionsEnabled)}
                >
                  {reactionsEnabled ? "Pause reactions" : "Allow reactions"}
                </Button>
              ) : null}
            </div>

            <div className="mt-3 flex flex-wrap gap-2">
              {ROOM_REACTION_OPTIONS.map((reaction) => (
                <ReactionButton
                  key={reaction.code}
                  reaction={reaction}
                  disabled={
                    roomStatus === "closed" ||
                    !reactionsEnabled ||
                    reactionSendingCode !== null
                  }
                  onClick={() => onSendReaction(reaction.code)}
                />
              ))}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function ReactionButton({
  reaction,
  disabled,
  onClick,
}: {
  reaction: RoomReactionMeta;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <Button
      type="button"
      size="sm"
      variant="outline"
      className={cn("h-10 rounded-full px-3 text-sm", reaction.accentClassName)}
      aria-label={`${reaction.label} reaction`}
      disabled={disabled}
      onClick={onClick}
    >
      <span className="text-base leading-none">{reaction.emoji}</span>
      <span>{reaction.label}</span>
    </Button>
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
