import type { ClimbSort, ProviderId, RoomSnapshot, SoloSavedClimb } from "@/types";
import { DEFAULT_ANGLE, DEFAULT_SORT } from "@/lib/climbs";

const USER_PREFS_STORAGE_KEY = "kilter-together:user-prefs:v1";
export const USER_PREFS_CHANGE_EVENT = "kilter-together:prefs-changed";
const MAX_RECENT_ROOMS = 9;
const MAX_SOLO_SAVED_CLIMBS = 24;

export interface RecentRoom {
  slug: string;
  roomName?: string;
  providerId: ProviderId;
  displayName?: string;
  surfaceName?: string;
  lastVisitedAt: string;
  pinned?: boolean;
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
  hostConnectedProvider: boolean;
  hostSelectedSurface: boolean;
  guestJoinedRoom: boolean;
  guestParticipated: boolean;
}

export interface IntroProgress {
  version: number;
  landingDismissed: boolean;
  soloDismissed: boolean;
}

export interface SavedCredentials {
  kilter: {
    username: string;
    remember: boolean;
  };
  crux: {
    remember: boolean;
  };
}

export interface HostDefaults {
  roomNameTemplate: string;
  defaultFistBumpsEnabled: boolean;
}

export interface AppSettings {
  clickCheersEnabled: boolean;
  playfulMotionEnabled: boolean;
  autoGuidesEnabled: boolean;
  recentRoomsEnabled: boolean;
  soloDefaultSort: ClimbSort;
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
  hostDefaults: HostDefaults;
  savedCredentials: SavedCredentials;
  recentRooms: RecentRoom[];
  soloFavorites: SoloSavedClimb[];
  soloShortlist: SoloSavedClimb[];
  soloResume?: SoloResumeState;
  intro: IntroProgress;
  onboarding: OnboardingProgress;
  settings: AppSettings;
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
    hostDefaults: {
      roomNameTemplate: "",
      defaultFistBumpsEnabled: true,
    },
    savedCredentials: {
      kilter: {
        username: "",
        remember: false,
      },
      crux: {
        remember: false,
      },
    },
    recentRooms: [],
    soloFavorites: [],
    soloShortlist: [],
    intro: {
      version: 1,
      landingDismissed: false,
      soloDismissed: false,
    },
    onboarding: {
      version: 1,
      dismissed: false,
      hostCompleted: false,
      guestCompleted: false,
      hostConnectedProvider: false,
      hostSelectedSurface: false,
      guestJoinedRoom: false,
      guestParticipated: false,
    },
    settings: {
      clickCheersEnabled: true,
      playfulMotionEnabled: true,
      autoGuidesEnabled: true,
      recentRoomsEnabled: true,
      soloDefaultSort: DEFAULT_SORT,
    },
  };
}

function getRecentRoomTimestamp(lastVisitedAt: string): number {
  const timestamp = Date.parse(lastVisitedAt);
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

function sortRecentRooms(recentRooms: RecentRoom[]): RecentRoom[] {
  return [...recentRooms].sort((left, right) => {
    if (Boolean(left.pinned) !== Boolean(right.pinned)) {
      return left.pinned ? -1 : 1;
    }

    return getRecentRoomTimestamp(right.lastVisitedAt) - getRecentRoomTimestamp(left.lastVisitedAt);
  });
}

function normalizeRecentRooms(recentRooms: RecentRoom[]): RecentRoom[] {
  const dedupedRooms = recentRooms.reduce<RecentRoom[]>((rooms, room) => {
    const slug = room.slug?.trim();
    if (!slug) {
      return rooms;
    }

    rooms.push({
      ...room,
      slug,
      pinned: Boolean(room.pinned),
    });
    return rooms;
  }, []);

  return sortRecentRooms(dedupedRooms).slice(0, MAX_RECENT_ROOMS);
}

export function soloSavedClimbKey(climb: Pick<SoloSavedClimb, "product_size_id" | "uuid">): string {
  return `${climb.product_size_id}:${climb.uuid}`;
}

function normalizeSoloSavedClimbs(climbs: SoloSavedClimb[]): SoloSavedClimb[] {
  const deduped = new Map<string, SoloSavedClimb>();

  for (const climb of climbs) {
    if (!climb?.uuid || !climb?.product_size_id || !climb?.board_id) {
      continue;
    }

    deduped.set(soloSavedClimbKey(climb), {
      ...climb,
      climb_name: climb.climb_name?.trim() || climb.uuid,
      setter_name: climb.setter_name?.trim() || "Unknown setter",
      board_name: climb.board_name?.trim() || `Board ${climb.board_id}`,
      saved_at: climb.saved_at || new Date().toISOString(),
    });
  }

  return [...deduped.values()]
    .sort((left, right) => Date.parse(right.saved_at) - Date.parse(left.saved_at))
    .slice(0, MAX_SOLO_SAVED_CLIMBS);
}

export function buildSoloSavedClimb(
  input: Omit<SoloSavedClimb, "saved_at">
): SoloSavedClimb {
  return {
    ...input,
    saved_at: new Date().toISOString(),
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
      hostDefaults: {
        ...defaults.hostDefaults,
        ...parsedValue.hostDefaults,
      },
      savedCredentials: {
        kilter: {
          username:
            typeof parsedValue.savedCredentials?.kilter?.username === "string"
              ? parsedValue.savedCredentials.kilter.username
              : defaults.savedCredentials.kilter.username,
          remember:
            typeof parsedValue.savedCredentials?.kilter?.remember === "boolean"
              ? parsedValue.savedCredentials.kilter.remember
              : defaults.savedCredentials.kilter.remember,
        },
        crux: {
          remember:
            typeof parsedValue.savedCredentials?.crux?.remember === "boolean"
              ? parsedValue.savedCredentials.crux.remember
              : defaults.savedCredentials.crux.remember,
        },
      },
      recentRooms: Array.isArray(parsedValue.recentRooms)
        ? normalizeRecentRooms(parsedValue.recentRooms as RecentRoom[])
        : defaults.recentRooms,
      soloFavorites: Array.isArray(parsedValue.soloFavorites)
        ? normalizeSoloSavedClimbs(parsedValue.soloFavorites as SoloSavedClimb[])
        : defaults.soloFavorites,
      soloShortlist: Array.isArray(parsedValue.soloShortlist)
        ? normalizeSoloSavedClimbs(parsedValue.soloShortlist as SoloSavedClimb[])
        : defaults.soloShortlist,
      intro: {
        ...defaults.intro,
        ...parsedValue.intro,
      },
      onboarding: {
        ...defaults.onboarding,
        ...parsedValue.onboarding,
      },
      settings: {
        ...defaults.settings,
        ...parsedValue.settings,
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
  window.dispatchEvent(new Event(USER_PREFS_CHANGE_EVENT));
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

export function updateHostDefaults(partialDefaults: Partial<HostDefaults>): UserPrefs {
  return updateUserPrefs((currentPrefs) => ({
    ...currentPrefs,
    hostDefaults: {
      ...currentPrefs.hostDefaults,
      ...partialDefaults,
    },
  }));
}

export function resolveHostRoomNameTemplate(
  template: string,
  now = new Date()
): string {
  const normalizedTemplate = template.trim();
  if (!normalizedTemplate) {
    return "";
  }

  return normalizedTemplate
    .replace(
      /\{weekday\}/g,
      now.toLocaleDateString(undefined, { weekday: "long" })
    )
    .replace(
      /\{date\}/g,
      now.toLocaleDateString(undefined, { month: "short", day: "numeric" })
    )
    .replace(/\{iso_date\}/g, now.toISOString().slice(0, 10))
    .trim();
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

export function rememberKilterCredentials(
  username: string,
  _password: string,
  remember: boolean
): UserPrefs {
  return updateUserPrefs((currentPrefs) => ({
    ...currentPrefs,
    savedCredentials: {
      ...currentPrefs.savedCredentials,
      kilter: remember
        ? {
            username,
            remember: true,
          }
        : {
            username: "",
            remember: false,
          },
    },
  }));
}

export function rememberCruxToken(_token: string, remember: boolean): UserPrefs {
  return updateUserPrefs((currentPrefs) => ({
    ...currentPrefs,
    savedCredentials: {
      ...currentPrefs.savedCredentials,
      crux: remember
        ? {
            remember: true,
          }
        : {
            remember: false,
          },
    },
  }));
}

export function rememberRoomVisit(snapshot: RoomSnapshot): UserPrefs {
  return updateUserPrefs((currentPrefs) => {
    if (!currentPrefs.settings.recentRoomsEnabled) {
      return currentPrefs;
    }

    const existingRoom = currentPrefs.recentRooms.find((room) => room.slug === snapshot.slug);
    const recentRoom: RecentRoom = {
      slug: snapshot.slug,
      roomName: snapshot.room_name,
      providerId: snapshot.provider_id,
      displayName: snapshot.display_name,
      surfaceName: snapshot.surface?.name,
      lastVisitedAt: new Date().toISOString(),
      pinned: existingRoom?.pinned ?? false,
    };

    return {
      ...currentPrefs,
      recentRooms: normalizeRecentRooms([
        recentRoom,
        ...currentPrefs.recentRooms.filter((room) => room.slug !== snapshot.slug),
      ]),
    };
  });
}

export function togglePinnedRecentRoom(slug: string): UserPrefs {
  return updateUserPrefs((currentPrefs) => ({
    ...currentPrefs,
    recentRooms: normalizeRecentRooms(
      currentPrefs.recentRooms.map((room) =>
        room.slug === slug ? { ...room, pinned: !room.pinned } : room
      )
    ),
  }));
}

export function removeRecentRoom(slug: string): UserPrefs {
  return updateUserPrefs((currentPrefs) => ({
    ...currentPrefs,
    recentRooms: currentPrefs.recentRooms.filter((room) => room.slug !== slug),
  }));
}

function toggleSoloSavedClimbCollection(
  collectionKey: "soloFavorites" | "soloShortlist",
  climb: SoloSavedClimb
): UserPrefs {
  return updateUserPrefs((currentPrefs) => {
    const existing = currentPrefs[collectionKey];
    const climbKey = soloSavedClimbKey(climb);
    const alreadySaved = existing.some(
      (candidate) => soloSavedClimbKey(candidate) === climbKey
    );

    return {
      ...currentPrefs,
      [collectionKey]: alreadySaved
        ? existing.filter((candidate) => soloSavedClimbKey(candidate) !== climbKey)
        : normalizeSoloSavedClimbs([climb, ...existing]),
    };
  });
}

export function toggleSoloFavorite(climb: SoloSavedClimb): UserPrefs {
  return toggleSoloSavedClimbCollection("soloFavorites", climb);
}

export function toggleSoloShortlist(climb: SoloSavedClimb): UserPrefs {
  return toggleSoloSavedClimbCollection("soloShortlist", climb);
}

export function removeSoloFavorite(climbKey: string): UserPrefs {
  return updateUserPrefs((currentPrefs) => ({
    ...currentPrefs,
    soloFavorites: currentPrefs.soloFavorites.filter(
      (climb) => soloSavedClimbKey(climb) !== climbKey
    ),
  }));
}

export function removeSoloShortlist(climbKey: string): UserPrefs {
  return updateUserPrefs((currentPrefs) => ({
    ...currentPrefs,
    soloShortlist: currentPrefs.soloShortlist.filter(
      (climb) => soloSavedClimbKey(climb) !== climbKey
    ),
  }));
}

export function buildSoloSavedClimbPath(climb: SoloSavedClimb): string {
  const searchParams = new URLSearchParams({
    angle: String(climb.angle || DEFAULT_ANGLE),
    sort: DEFAULT_SORT,
    climb: climb.uuid,
  });

  return `/solo/boards/${encodeURIComponent(climb.board_id)}?${searchParams.toString()}`;
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

export function dismissLandingIntro(): UserPrefs {
  return updateUserPrefs((currentPrefs) => ({
    ...currentPrefs,
    intro: {
      ...currentPrefs.intro,
      landingDismissed: true,
    },
  }));
}

export function dismissSoloIntro(): UserPrefs {
  return updateUserPrefs((currentPrefs) => ({
    ...currentPrefs,
    intro: {
      ...currentPrefs.intro,
      soloDismissed: true,
    },
  }));
}

export function reopenSoloIntro(): UserPrefs {
  return updateUserPrefs((currentPrefs) => ({
    ...currentPrefs,
    intro: {
      ...currentPrefs.intro,
      soloDismissed: false,
    },
  }));
}

export function resetOnboardingPrefs(): UserPrefs {
  return updateUserPrefs((currentPrefs) => ({
    ...currentPrefs,
    onboarding: {
      ...currentPrefs.onboarding,
      dismissed: false,
      hostCompleted: false,
      guestCompleted: false,
      hostConnectedProvider: false,
      hostSelectedSurface: false,
      guestJoinedRoom: false,
      guestParticipated: false,
    },
  }));
}

export function dismissOnboarding(): UserPrefs {
  return updateUserPrefs((currentPrefs) => ({
    ...currentPrefs,
    onboarding: {
      ...currentPrefs.onboarding,
      dismissed: true,
    },
  }));
}

export function markHostProviderConnected(): UserPrefs {
  return updateUserPrefs((currentPrefs) => {
    const onboarding = {
      ...currentPrefs.onboarding,
      hostConnectedProvider: true,
    };

    return {
      ...currentPrefs,
      onboarding: {
        ...onboarding,
        hostCompleted: onboarding.hostConnectedProvider && onboarding.hostSelectedSurface,
      },
    };
  });
}

export function markHostSurfaceSelected(): UserPrefs {
  return updateUserPrefs((currentPrefs) => {
    const onboarding = {
      ...currentPrefs.onboarding,
      hostSelectedSurface: true,
    };

    return {
      ...currentPrefs,
      onboarding: {
        ...onboarding,
        hostCompleted: onboarding.hostConnectedProvider && onboarding.hostSelectedSurface,
      },
    };
  });
}

export function markGuestJoinedRoom(): UserPrefs {
  return updateUserPrefs((currentPrefs) => {
    const onboarding = {
      ...currentPrefs.onboarding,
      guestJoinedRoom: true,
    };

    return {
      ...currentPrefs,
      onboarding: {
        ...onboarding,
        guestCompleted: onboarding.guestJoinedRoom && onboarding.guestParticipated,
      },
    };
  });
}

export function markGuestParticipated(): UserPrefs {
  return updateUserPrefs((currentPrefs) => {
    const onboarding = {
      ...currentPrefs.onboarding,
      guestParticipated: true,
    };

    return {
      ...currentPrefs,
      onboarding: {
        ...onboarding,
        guestCompleted: onboarding.guestJoinedRoom && onboarding.guestParticipated,
      },
    };
  });
}

export function updateAppSettings(partialSettings: Partial<AppSettings>): UserPrefs {
  return updateUserPrefs((currentPrefs) => {
    const nextSettings = {
      ...currentPrefs.settings,
      ...partialSettings,
    };

    return {
      ...currentPrefs,
      settings: nextSettings,
      recentRooms: nextSettings.recentRoomsEnabled ? currentPrefs.recentRooms : [],
      savedCredentials: currentPrefs.savedCredentials,
    };
  });
}

export function clearRecentRooms(): UserPrefs {
  return updateUserPrefs((currentPrefs) => ({
    ...currentPrefs,
    recentRooms: [],
  }));
}

export function clearSavedCredentials(): UserPrefs {
  return updateUserPrefs((currentPrefs) => ({
    ...currentPrefs,
    savedCredentials: {
      kilter: {
        username: "",
        remember: false,
      },
      crux: {
        remember: false,
      },
    },
  }));
}

export function clearSoloResume(): UserPrefs {
  return updateUserPrefs((currentPrefs) => ({
    ...currentPrefs,
    soloResume: undefined,
  }));
}

export function resetGuides(): UserPrefs {
  return updateUserPrefs((currentPrefs) => ({
    ...currentPrefs,
    intro: {
      ...currentPrefs.intro,
      landingDismissed: false,
      soloDismissed: false,
    },
    onboarding: {
      ...currentPrefs.onboarding,
      dismissed: false,
      hostCompleted: false,
      guestCompleted: false,
      hostConnectedProvider: false,
      hostSelectedSurface: false,
      guestJoinedRoom: false,
      guestParticipated: false,
    },
  }));
}
