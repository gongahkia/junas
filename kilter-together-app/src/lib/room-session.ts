import type { RoomSession } from "@/types";

function sessionStorageKey(slug: string): string {
  return `kilter-together:room-session:${slug.trim()}`;
}

export function readRoomSession(slug: string): RoomSession | null {
  if (typeof window === "undefined") {
    return null;
  }

  const normalizedSlug = slug.trim();
  if (!normalizedSlug) {
    return null;
  }

  const rawValue = window.localStorage.getItem(sessionStorageKey(normalizedSlug));
  if (!rawValue) {
    return null;
  }

  try {
    const parsedValue = JSON.parse(rawValue) as Partial<RoomSession> | null;
    if (!parsedValue?.token?.trim()) {
      return null;
    }

    return {
      token: parsedValue.token.trim(),
      role: parsedValue.role?.trim(),
      expires_at: parsedValue.expires_at,
    };
  } catch {
    return null;
  }
}

export function saveRoomSession(slug: string, session: RoomSession): void {
  if (typeof window === "undefined") {
    return;
  }

  const normalizedSlug = slug.trim();
  if (!normalizedSlug || !session.token.trim()) {
    return;
  }

  window.localStorage.setItem(
    sessionStorageKey(normalizedSlug),
    JSON.stringify({
      token: session.token.trim(),
      role: session.role?.trim(),
      expires_at: session.expires_at,
    })
  );
}

export function clearRoomSession(slug: string): void {
  if (typeof window === "undefined") {
    return;
  }

  const normalizedSlug = slug.trim();
  if (!normalizedSlug) {
    return;
  }

  window.localStorage.removeItem(sessionStorageKey(normalizedSlug));
}
