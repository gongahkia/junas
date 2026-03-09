import type { RoomReactionCode } from "@/types";

export interface RoomReactionMeta {
  code: RoomReactionCode;
  emoji: string;
  label: string;
  accentClassName: string;
}

export const ROOM_REACTION_TTL_MS = 12000;

export const ROOM_REACTION_OPTIONS: RoomReactionMeta[] = [
  {
    code: "thumbs_up",
    emoji: "👍",
    label: "Thumbs up",
    accentClassName: "border-sky-200 bg-sky-50 text-sky-700",
  },
  {
    code: "heart",
    emoji: "❤️",
    label: "Heart",
    accentClassName: "border-rose-200 bg-rose-50 text-rose-700",
  },
  {
    code: "clap",
    emoji: "👏",
    label: "Clap",
    accentClassName: "border-amber-200 bg-amber-50 text-amber-700",
  },
  {
    code: "fire",
    emoji: "🔥",
    label: "Fire",
    accentClassName: "border-orange-200 bg-orange-50 text-orange-700",
  },
  {
    code: "mind_blown",
    emoji: "😮",
    label: "Mind blown",
    accentClassName: "border-violet-200 bg-violet-50 text-violet-700",
  },
  {
    code: "party",
    emoji: "🎉",
    label: "Party",
    accentClassName: "border-emerald-200 bg-emerald-50 text-emerald-700",
  },
];

export const ROOM_REACTION_META: Record<RoomReactionCode, RoomReactionMeta> =
  ROOM_REACTION_OPTIONS.reduce(
    (metaByCode, option) => ({
      ...metaByCode,
      [option.code]: option,
    }),
    {} as Record<RoomReactionCode, RoomReactionMeta>
  );
