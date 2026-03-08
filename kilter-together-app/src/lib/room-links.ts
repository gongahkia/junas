export function buildInviteLink(slug: string): string {
  if (typeof window === "undefined") {
    return `/join/${slug}`;
  }

  return `${window.location.origin}/join/${slug}`;
}

export function extractRoomSlugFromValue(value: string): string | null {
  const trimmedValue = value.trim();
  if (!trimmedValue) {
    return null;
  }

  try {
    const parsedUrl = new URL(trimmedValue);
    const matchedPath = parsedUrl.pathname.match(/^\/(?:join|rooms)\/([^/?#]+)/i);
    if (!matchedPath) {
      return null;
    }
    return decodeURIComponent(matchedPath[1]);
  } catch {
    const matchedValue = trimmedValue.match(/^(?:join\/|rooms\/)?([^/?#]+)$/i);
    return matchedValue ? decodeURIComponent(matchedValue[1]) : null;
  }
}
