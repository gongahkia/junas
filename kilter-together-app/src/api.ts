import axios from "axios";
import { config } from "./config";
import type {
  ApiResponse,
  Board,
  PaginatedClimbsParams,
  PaginatedClimbsResponse,
  ParticipantStatus,
  ProviderConnectionState,
  ProviderClimb,
  ProviderId,
  ProviderSurface,
  RandomPickSource,
  RoomCatalogClimbsResponse,
  RoomCatalogClimbResponse,
  RoomSnapshot,
  ClimbSort,
  QueueStatus,
} from "./types";

const BASE_URL = config.api.baseUrl;
const IMAGES_BASE_URL = `${BASE_URL}/images`;

const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 10000,
  withCredentials: true,
});

function normalizeRoomSnapshot(snapshot: RoomSnapshot): RoomSnapshot {
  return {
    ...snapshot,
    fist_bumps_enabled: snapshot.fist_bumps_enabled ?? true,
  };
}

// wrap in api namespace
export const api = {
  getBoards: async (): Promise<Board[]> => {
    try {
      const response = await apiClient.get<ApiResponse>("/boards");
      return response.data.boards || [];
    } catch (error) {
      console.error("Error fetching boards:", error);
      throw error;
    }
  },

  getPaginatedClimbs: async (
    params: PaginatedClimbsParams
  ): Promise<PaginatedClimbsResponse> => {
    try {
      const response = await apiClient.get<PaginatedClimbsResponse>("/climbs", {
        params: {
          board_id: params.boardId,
          angle: params.angle,
          page_size: params.pageSize ?? 10,
          cursor: params.cursor,
          name: params.name,
          setter: params.setter,
          sort: params.sort,
        },
      });
      return response.data;
    } catch (error) {
      console.error("Error fetching paginated climbs:", error);
      throw error;
    }
  },

  getImageUrl: (filename: string): string => {
    const baseName = filename.includes("/")
      ? filename.split("/").pop()!
      : filename;
    return `${IMAGES_BASE_URL}/${baseName}`;
  },

  createRoom: async (payload: {
    providerId: ProviderId;
    roomName: string;
    displayName: string;
    secret: Record<string, string>;
  }): Promise<RoomSnapshot> => {
    const response = await apiClient.post<RoomSnapshot>("/rooms", {
      provider_id: payload.providerId,
      room_name: payload.roomName,
      display_name: payload.displayName,
      secret: payload.secret,
    });
    return normalizeRoomSnapshot(response.data);
  },

  joinRoom: async (slug: string, displayName: string): Promise<RoomSnapshot> => {
    const response = await apiClient.post<RoomSnapshot>(`/rooms/${slug}/join`, {
      display_name: displayName,
    });
    return normalizeRoomSnapshot(response.data);
  },

  getRoom: async (slug: string): Promise<RoomSnapshot> => {
    const response = await apiClient.get<RoomSnapshot>(`/rooms/${slug}`);
    return normalizeRoomSnapshot(response.data);
  },

  updateRoom: async (
    slug: string,
    payload: { roomName: string }
  ): Promise<RoomSnapshot> => {
    const response = await apiClient.patch<RoomSnapshot>(`/rooms/${slug}`, {
      room_name: payload.roomName,
    });
    return normalizeRoomSnapshot(response.data);
  },

  setRoomFistBumpsEnabled: async (
    slug: string,
    enabled: boolean
  ): Promise<RoomSnapshot> => {
    const response = await apiClient.put<RoomSnapshot>(`/rooms/${slug}/fist-bumps/settings`, {
      enabled,
    });
    return normalizeRoomSnapshot(response.data);
  },

  getRoomEventsUrl: (slug: string): string => `${BASE_URL}/rooms/${slug}/events`,

  connectRoomProvider: async (
    slug: string,
    secret: Record<string, string>
  ): Promise<ProviderConnectionState> => {
    const response = await apiClient.post<ProviderConnectionState>(
      `/rooms/${slug}/provider/connect`,
      { secret }
    );
    return response.data;
  },

  getRoomCatalogSurfaces: async (
    slug: string,
    parentId?: string
  ): Promise<ProviderSurface[]> => {
    const response = await apiClient.get<{ surfaces: ProviderSurface[] }>(
      `/rooms/${slug}/catalog/surfaces`,
      {
        params: {
          parent_id: parentId,
        },
      }
    );
    return response.data.surfaces ?? [];
  },

  setRoomSurface: async (
    slug: string,
    payload: { surfaceId: string; context?: Record<string, string> }
  ): Promise<ProviderSurface> => {
    const response = await apiClient.post<ProviderSurface>(`/rooms/${slug}/surface`, {
      surface_id: payload.surfaceId,
      context: payload.context ?? {},
    });
    return response.data;
  },

  getRoomCatalogClimbs: async (
    slug: string,
    params: {
      q?: string;
      sort?: ClimbSort;
      cursor?: string;
      pageSize?: number;
    }
  ): Promise<RoomCatalogClimbsResponse> => {
    const response = await apiClient.get<RoomCatalogClimbsResponse>(
      `/rooms/${slug}/catalog/climbs`,
      {
        params: {
          q: params.q,
          sort: params.sort,
          cursor: params.cursor,
          page_size: params.pageSize ?? 10,
        },
      }
    );
    return response.data;
  },

  getRoomCatalogClimb: async (
    slug: string,
    climbId: string
  ): Promise<RoomCatalogClimbResponse> => {
    const response = await apiClient.get<RoomCatalogClimbResponse>(
      `/rooms/${slug}/catalog/climbs/${encodeURIComponent(climbId)}`
    );
    return response.data;
  },

  toggleRoomVote: async (slug: string, climbId: string): Promise<void> => {
    await apiClient.put(`/rooms/${slug}/votes/${encodeURIComponent(climbId)}`);
  },

  addRoomQueueEntry: async (slug: string, climbId: string): Promise<void> => {
    await apiClient.post(`/rooms/${slug}/queue`, { climb_id: climbId });
  },

  addRoomFinalist: async (slug: string, climbId: string): Promise<void> => {
    await apiClient.post(`/rooms/${slug}/finalists`, { climb_id: climbId });
  },

  reorderRoomFinalists: async (slug: string, entryIds: number[]): Promise<void> => {
    await apiClient.patch(`/rooms/${slug}/finalists/reorder`, { entry_ids: entryIds });
  },

  deleteRoomFinalist: async (slug: string, entryId: number): Promise<void> => {
    await apiClient.delete(`/rooms/${slug}/finalists/${entryId}`);
  },

  pickRandomRoomClimb: async (
    slug: string,
    source: RandomPickSource
  ): Promise<ProviderClimb> => {
    const response = await apiClient.post<{ climb: ProviderClimb }>(
      `/rooms/${slug}/pick-random`,
      { source }
    );
    return response.data.climb;
  },

  reorderRoomQueue: async (slug: string, entryIds: number[]): Promise<void> => {
    await apiClient.patch(`/rooms/${slug}/queue/reorder`, { entry_ids: entryIds });
  },

  promoteRoomQueueClimb: async (
    slug: string,
    climbId: string,
    status: "current" | "next"
  ): Promise<void> => {
    await apiClient.post(`/rooms/${slug}/queue/promote`, {
      climb_id: climbId,
      status,
    });
  },

  updateRoomQueueEntry: async (
    slug: string,
    entryId: number,
    status: QueueStatus
  ): Promise<void> => {
    await apiClient.patch(`/rooms/${slug}/queue/${entryId}`, { status });
  },

  deleteRoomQueueEntry: async (slug: string, entryId: number): Promise<void> => {
    await apiClient.delete(`/rooms/${slug}/queue/${entryId}`);
  },

  clearRoomVotes: async (slug: string): Promise<void> => {
    await apiClient.post(`/rooms/${slug}/clear-votes`);
  },

  closeRoom: async (slug: string): Promise<void> => {
    await apiClient.post(`/rooms/${slug}/close`);
  },

  removeRoomParticipant: async (
    slug: string,
    participantId: number
  ): Promise<void> => {
    await apiClient.delete(`/rooms/${slug}/participants/${participantId}`);
  },

  updateMyParticipantStatus: async (
    slug: string,
    status: ParticipantStatus
  ): Promise<void> => {
    await apiClient.put(`/rooms/${slug}/participants/me/status`, { status });
  },
};

export { BASE_URL, IMAGES_BASE_URL };
