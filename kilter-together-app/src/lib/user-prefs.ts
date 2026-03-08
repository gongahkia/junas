import type { ClimbSort, ProviderId, RoomSnapshot } from "@/types";
import { DEFAULT_ANGLE, DEFAULT_SORT } from "@/lib/climbs";

const USER_PREFS_STORAGE_KEY = "kilter-together:user-prefs:v1";
const MAX_RECENT_ROOMS = 6;

export interface RecentRoom {
  slug: string;
  providerId: ProviderId;
  displayName?: string;
  surfaceName?: string;
  lastVisitedAt: string;
}

export interface SoloResumeState {
  boardId: string;
  angle: number;
  q?: string;
  setter?: string;
  sort: ClimbSort;
  climb?: string;
}

export interface OnboardingProgress {
  version: number;
  dismissed: boolean;
  hostCompleted: boolean;
  guestCompleted: boolean;
}

export interface UserPrefs {
  savedDisplayName: string;
  lastProviderId: ProviderId;
  lastKilter: {
    boardId: string;
    angle: number;
  };
  lastCrux: {
    gymSlug: string;
    wallId: string;
  };
  recentRooms: RecentRoom[];
  soloResume?: SoloResumeState;
  onboarding: OnboardingProgress;
}

function getDefaultUserPrefs(): UserPrefs {
  return {
    savedDisplayName: "",
    lastProviderId: "kilter",
    lastKilter: {
      boardId: "",
      angle: DEFAULT_ANGLE,
    },
    lastCrux: {
      gymSlug: "",
      wallId: "",
    },
    recentRooms: [],
    onboarding: {
      version: 1,
      dismissed: false,
      hostCompleted: false,
      guestCompleted: false,
    },
  };
}

export function loadUserPrefs(): UserPrefs {
  if (typeof window === "undefined") {
    return getDefaultUserPrefs();
  }

  const rawValue = window.localStorage.getItem(USER_PREFS_STORAGE_KEY);
  if (!rawValue) {
    return getDefaultUserPrefs();
  }

  try {
    const parsedValue = JSON.parse(rawValue) as Partial<UserPrefs>;
    const defaults = getDefaultUserPrefs();
    return {
      ...defaults,
      ...parsedValue,
      lastKilter: {
        ...defaults.lastKilter,
        ...parsedValue.lastKilter,
      },
      lastCrux: {
        ...defaults.lastCrux,
        ...parsedValue.lastCrux,
      },
      recentRooms: Array.isArray(parsedValue.recentRooms)
        ? parsedValue.recentRooms.slice(0, MAX_RECENT_ROOMS)
        : defaults.recentRooms,
      onboarding: {
        ...defaults.onboarding,
        ...parsedValue.onboarding,
      },
    };
  } catch {
    return getDefaultUserPrefs();
  }
}

export function saveUserPrefs(prefs: UserPrefs): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(USER_PREFS_STORAGE_KEY, JSON.stringify(prefs));
}

export function updateUserPrefs(
  updater: (currentPrefs: UserPrefs) => UserPrefs
): UserPrefs {
  const nextPrefs = updater(loadUserPrefs());
  saveUserPrefs(nextPrefs);
  return nextPrefs;
}

export function rememberDisplayName(displayName: string): UserPrefs {
  const normalizedValue = displayName.trim();
  if (!normalizedValue) {
    return loadUserPrefs();
  }

  return updateUserPrefs((currentPrefs) => ({
    ...currentPrefs,
    savedDisplayName: normalizedValue,
  }));
}

export function rememberLastProvider(providerId: ProviderId): UserPrefs {
  return updateUserPrefs((currentPrefs) => ({
    ...currentPrefs,
    lastProviderId: providerId,
  }));
}

export function rememberLastKilterSurface(boardId: string, angle: number): UserPrefs {
  return updateUserPrefs((currentPrefs) => ({
    ...currentPrefs,
    lastKilter: {
      boardId,
      angle,
    },
  }));
}

export function rememberLastCruxSurface(gymSlug: string, wallId: string): UserPrefs {
  return updateUserPrefs((currentPrefs) => ({
    ...currentPrefs,
    lastCrux: {
      gymSlug,
      wallId,
    },
  }));
}

export function rememberRoomVisit(snapshot: RoomSnapshot): UserPrefs {
  return updateUserPrefs((currentPrefs) => {
    const recentRoom: RecentRoom = {
      slug: snapshot.slug,
      providerId: snapshot.provider_id,
      displayName: snapshot.display_name,
      surfaceName: snapshot.surface?.name,
      lastVisitedAt: new Date().toISOString(),
    };

    const nextRecentRooms = [
      recentRoom,
      ...currentPrefs.recentRooms.filter((room) => room.slug !== snapshot.slug),
    ].slice(0, MAX_RECENT_ROOMS);

    return {
      ...currentPrefs,
      recentRooms: nextRecentRooms,
    };
  });
}

export function rememberSoloResume(state: SoloResumeState): UserPrefs {
  return updateUserPrefs((currentPrefs) => ({
    ...currentPrefs,
    soloResume: state,
    lastKilter: {
      boardId: state.boardId,
      angle: state.angle,
    },
  }));
}

export function buildSoloResumePath(state?: SoloResumeState): string | null {
  if (!state?.boardId) {
    return null;
  }

  const searchParams = new URLSearchParams({
    angle: String(state.angle || DEFAULT_ANGLE),
    sort: state.sort || DEFAULT_SORT,
  });
  if (state.q) {
    searchParams.set("q", state.q);
  }
  if (state.setter) {
    searchParams.set("setter", state.setter);
  }
  if (state.climb) {
    searchParams.set("climb", state.climb);
  }

  return `/solo/boards/${encodeURIComponent(state.boardId)}?${searchParams.toString()}`;
}

export function resetOnboardingPrefs(): UserPrefs {
  return updateUserPrefs((currentPrefs) => ({
    ...currentPrefs,
    onboarding: {
      ...currentPrefs.onboarding,
      dismissed: false,
      hostCompleted: false,
      guestCompleted: false,
    },
  }));
}
