import type { RoomEventPayload } from "@/types";

const ROOM_ONLY_RESOURCES = new Set([
  "room",
  "participants",
  "queue",
  "finalists",
  "votes",
  "current_climb",
]);

export function parseRoomEventPayload(raw: string): RoomEventPayload | null {
  try {
    return JSON.parse(raw) as RoomEventPayload;
  } catch {
    return null;
  }
}

export function shouldRefreshCatalogOnly(payload: RoomEventPayload | null): boolean {
  if (!payload?.resources?.length) {
    return false;
  }

  return payload.resources.every((resource) => resource === "catalog");
}

export function shouldRefreshRoomAndCatalog(payload: RoomEventPayload | null): boolean {
  if (!payload?.resources?.length) {
    return true
  }

  return payload.resources.some(
    (resource) => resource === "surface" || resource === "connection" || resource === "catalog"
  )
}

export function shouldRefreshRoomOnly(payload: RoomEventPayload | null): boolean {
  if (!payload?.resources?.length) {
    return false;
  }

  return payload.resources.some((resource) => ROOM_ONLY_RESOURCES.has(resource));
}
