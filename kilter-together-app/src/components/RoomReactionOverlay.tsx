import { useEffect, useMemo, useState } from "react";
import { ROOM_REACTION_META, ROOM_REACTION_TTL_MS } from "@/lib/room-reactions";
import { cn } from "@/lib/utils";
import type { RoomReaction } from "@/types";

function hashString(value: string) {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
  }
  return hash;
}

interface RoomReactionOverlayProps {
  reactions: RoomReaction[];
  motionEnabled: boolean;
}

export default function RoomReactionOverlay({
  reactions,
  motionEnabled,
}: RoomReactionOverlayProps) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    setNow(Date.now());
  }, [reactions]);

  useEffect(() => {
    if (!motionEnabled || reactions.length === 0 || typeof window === "undefined") {
      return undefined;
    }

    const intervalID = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(intervalID);
  }, [motionEnabled, reactions.length]);

  const activeReactions = useMemo(
    () =>
      reactions
        .map((reaction) => ({
          reaction,
          createdAtMs: Date.parse(reaction.created_at),
        }))
        .filter(
          ({ createdAtMs }) =>
            Number.isFinite(createdAtMs) && now-createdAtMs < ROOM_REACTION_TTL_MS
        ),
    [now, reactions]
  );

  if (!motionEnabled || activeReactions.length === 0) {
    return null;
  }

  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
      {activeReactions.map(({ reaction, createdAtMs }) => {
        const meta = ROOM_REACTION_META[reaction.emoji_code];
        const ageMs = Math.max(0, now - createdAtMs);
        const seed = hashString(reaction.id);
        const lane = seed % 4;
        const left = 10 + (seed % 68);
        const drift = (seed % 2 === 0 ? 1 : -1) * (18 + (seed % 28));

        return (
          <div
            key={reaction.id}
            className={cn(
              "room-reaction-burst absolute flex items-center gap-2 rounded-full border px-3 py-2 shadow-sm backdrop-blur-sm",
              meta.accentClassName
            )}
            style={{
              left: `${left}%`,
              top: `${60 + lane * 9}%`,
              animationDelay: `-${Math.min(ageMs, ROOM_REACTION_TTL_MS - 120)}ms`,
              animationDuration: `${ROOM_REACTION_TTL_MS}ms`,
              ["--room-reaction-drift" as string]: `${drift}px`,
            }}
          >
            <span className="text-lg leading-none">{meta.emoji}</span>
            <span className="text-xs font-medium">{reaction.display_name}</span>
          </div>
        );
      })}
    </div>
  );
}
