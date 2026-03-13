import axios from "axios";
import { config } from "./config";
import type { paths } from "@/generated/api";
import type {
  AssistantMode,
  ApiResponse,
  Board,
  PaginatedClimbsParams,
  PaginatedClimbsResponse,
  ParticipantStatus,
  ProviderCapability,
  ProviderConnectionState,
  ProviderClimb,
  ProviderId,
  ProviderSurface,
  RandomPickSource,
  RoomCatalogClimbsResponse,
  RoomCatalogClimbResponse,
  ProviderCatalogClimbResponse,
  ProviderCatalogClimbsResponse,
  RoomSnapshot,
  ClimbSort,
  QueueStatus,
  RoomRecap,
  RoomPermissions,
  SessionSummary,
  SoloPlanSnapshot,
  ProductMetrics,
  RuntimeStatus,
} from "./types";
import { reportApiFailure } from "@/lib/observability";

const BASE_URL = config.api.baseUrl;
const IMAGES_BASE_URL = `${BASE_URL}/images`;

const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 10000,
  withCredentials: true,
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const requestUrl =
      typeof error?.config?.url === "string" ? error.config.url : "unknown";
    reportApiFailure(error, requestUrl);
    return Promise.reject(error);
  }
);

type JsonContent<T> = T extends { content: { "application/json": infer U } } ? U : never;
type CreateRoomPayload =
  paths["/rooms"]["post"]["requestBody"]["content"]["application/json"];
type CreateRoomResponse = JsonContent<paths["/rooms"]["post"]["responses"][201]>;
type JoinRoomPayload =
  paths["/rooms/{slug}/join"]["post"]["requestBody"]["content"]["application/json"];
type JoinRoomResponse = JsonContent<paths["/rooms/{slug}/join"]["post"]["responses"][201]>;
type GetRoomResponse = JsonContent<paths["/rooms/{slug}"]["get"]["responses"][200]>;
type UpdateRoomPayload =
  paths["/rooms/{slug}"]["patch"]["requestBody"]["content"]["application/json"];
type UpdateRoomResponse = JsonContent<paths["/rooms/{slug}"]["patch"]["responses"][200]>;
type SetFistBumpsPayload =
  paths["/rooms/{slug}/fist-bumps/settings"]["put"]["requestBody"]["content"]["application/json"];
type SetFistBumpsResponse =
  JsonContent<paths["/rooms/{slug}/fist-bumps/settings"]["put"]["responses"][200]>;
type ConnectProviderPayload =
  paths["/rooms/{slug}/provider/connect"]["post"]["requestBody"]["content"]["application/json"];
type ConnectProviderResponse =
  JsonContent<paths["/rooms/{slug}/provider/connect"]["post"]["responses"][200]>;
type RoomSurfacesResponse =
  JsonContent<paths["/rooms/{slug}/catalog/surfaces"]["get"]["responses"][200]>;
type SetSurfacePayload =
  paths["/rooms/{slug}/surface"]["post"]["requestBody"]["content"]["application/json"];
type SetSurfaceResponse =
  JsonContent<paths["/rooms/{slug}/surface"]["post"]["responses"][200]>;
type RoomCatalogClimbsResponseDTO =
  JsonContent<paths["/rooms/{slug}/catalog/climbs"]["get"]["responses"][200]>;
type RoomCatalogClimbResponseDTO =
  JsonContent<paths["/rooms/{slug}/catalog/climbs/{climbId}"]["get"]["responses"][200]>;
type RandomPickPayload =
  NonNullable<
    paths["/rooms/{slug}/pick-random"]["post"]["requestBody"]
  >["content"]["application/json"];
type RandomPickResponse =
  JsonContent<paths["/rooms/{slug}/pick-random"]["post"]["responses"][200]>;

function defaultRoomPermissions(canManage: boolean): RoomPermissions {
  return {
    manage_session: canManage,
    manage_surface: canManage,
    manage_queue: canManage,
    manage_finalists: canManage,
    edit_room_settings: canManage,
    manage_participants: canManage,
    assign_co_hosts: canManage,
    close_room: canManage,
  };
}

function normalizeRoomSnapshot(snapshot: RoomSnapshot): RoomSnapshot {
  const canManage = snapshot.can_manage ?? false;
  return {
    ...snapshot,
    assistant: snapshot.assistant ?? { mode: "manual" as AssistantMode },
    fist_bumps_enabled: snapshot.fist_bumps_enabled ?? true,
    can_manage: canManage,
    permissions: snapshot.permissions ?? defaultRoomPermissions(canManage),
  };
}

// wrap in api namespace
export const api = {
  getProviderCapabilities: async (): Promise<ProviderCapability[]> => {
    const response = await apiClient.get<{ providers?: ProviderCapability[] }>(
      "/providers/capabilities"
    );
    return response.data.providers ?? [];
  },

  getRecentSessions: async (limit = 6): Promise<SessionSummary[]> => {
    const response = await apiClient.get<{ sessions?: SessionSummary[] }>(
      "/sessions/recent",
      {
        params: { limit },
      }
    );
    return response.data.sessions ?? [];
  },

  getRuntimeStatus: async (): Promise<RuntimeStatus> => {
    const response = await apiClient.get<RuntimeStatus>("/runtime/status");
    return response.data;
  },

  recordAnalyticsEvent: async (payload: {
    roomSlug?: string;
    eventName: string;
    source?: string;
    viewerRole?: string;
    route?: string;
    properties?: Record<string, unknown>;
  }): Promise<void> => {
    await apiClient.post("/analytics/events", {
      room_slug: payload.roomSlug,
      event_name: payload.eventName,
      source: payload.source ?? "client",
      viewer_role: payload.viewerRole,
      route: payload.route,
      properties: payload.properties ?? {},
    });
  },

  submitFeedback: async (payload: {
    roomSlug?: string;
    shareId?: string;
    promptFamily: string;
    sentiment: "up" | "down";
    message?: string;
    route?: string;
    metadata?: Record<string, unknown>;
  }): Promise<void> => {
    await apiClient.post("/feedback", {
      room_slug: payload.roomSlug,
      share_id: payload.shareId,
      prompt_family: payload.promptFamily,
      sentiment: payload.sentiment,
      message: payload.message,
      route: payload.route,
      metadata: payload.metadata ?? {},
    });
  },

  getRoomRecap: async (shareId: string): Promise<RoomRecap> => {
    const response = await apiClient.get<RoomRecap>(`/recaps/${encodeURIComponent(shareId)}`);
    return response.data;
  },

  createSoloPlan: async (payload: {
    providerId: ProviderId;
    title: string;
    notes?: string;
    surface: ProviderSurface;
    context?: Record<string, string>;
    filters?: Record<string, string>;
    climbs: ProviderClimb[];
    openPath?: string;
    createdBy?: string;
  }): Promise<SoloPlanSnapshot> => {
    const response = await apiClient.post<SoloPlanSnapshot>("/solo/plans", {
      provider_id: payload.providerId,
      title: payload.title,
      notes: payload.notes,
      surface: payload.surface,
      context: payload.context ?? {},
      filters: payload.filters ?? {},
      climbs: payload.climbs,
      open_path: payload.openPath,
      created_by: payload.createdBy,
    });
    return response.data;
  },

  getSoloPlan: async (shareId: string): Promise<SoloPlanSnapshot> => {
    const response = await apiClient.get<SoloPlanSnapshot>(
      `/solo/plans/${encodeURIComponent(shareId)}`
    );
    return response.data;
  },

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
          grade: params.grade,
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
    fistBumpsEnabled: boolean;
  }): Promise<RoomSnapshot> => {
    const requestBody: CreateRoomPayload & { fist_bumps_enabled: boolean } = {
      provider_id: payload.providerId,
      room_name: payload.roomName,
      display_name: payload.displayName,
      secret: payload.secret,
      fist_bumps_enabled: payload.fistBumpsEnabled,
    };
    const response = await apiClient.post<CreateRoomResponse>(
      "/rooms",
      requestBody as CreateRoomPayload
    );
    return normalizeRoomSnapshot(response.data as RoomSnapshot);
  },

  joinRoom: async (slug: string, displayName: string): Promise<RoomSnapshot> => {
    const requestBody: JoinRoomPayload = {
      display_name: displayName,
    };
    const response = await apiClient.post<JoinRoomResponse>(`/rooms/${slug}/join`, requestBody);
    return normalizeRoomSnapshot(response.data as RoomSnapshot);
  },

  getRoom: async (slug: string): Promise<RoomSnapshot> => {
    const response = await apiClient.get<GetRoomResponse>(`/rooms/${slug}`);
    return normalizeRoomSnapshot(response.data as RoomSnapshot);
  },

  updateRoom: async (
    slug: string,
    payload: { roomName: string }
  ): Promise<RoomSnapshot> => {
    const requestBody: UpdateRoomPayload = {
      room_name: payload.roomName,
    };
    const response = await apiClient.patch<UpdateRoomResponse>(`/rooms/${slug}`, requestBody);
    return normalizeRoomSnapshot(response.data as RoomSnapshot);
  },

  setRoomFistBumpsEnabled: async (
    slug: string,
    enabled: boolean
  ): Promise<RoomSnapshot> => {
    const requestBody: SetFistBumpsPayload = {
      enabled,
    };
    const response = await apiClient.put<SetFistBumpsResponse>(
      `/rooms/${slug}/fist-bumps/settings`,
      requestBody
    );
    return normalizeRoomSnapshot(response.data as RoomSnapshot);
  },

  updateRoomAssistantMode: async (
    slug: string,
    mode: AssistantMode
  ): Promise<RoomSnapshot> => {
    const response = await apiClient.put<RoomSnapshot>(
      `/rooms/${slug}/assistant/settings`,
      { mode }
    );
    return normalizeRoomSnapshot(response.data);
  },

  getRoomEventsUrl: (slug: string): string => `${BASE_URL}/rooms/${slug}/events`,

  connectRoomProvider: async (
    slug: string,
    secret: Record<string, string>
  ): Promise<ProviderConnectionState> => {
    const requestBody: ConnectProviderPayload = { secret };
    const response = await apiClient.post<ConnectProviderResponse>(
      `/rooms/${slug}/provider/connect`,
      requestBody
    );
    return response.data as ProviderConnectionState;
  },

  getRoomCatalogSurfaces: async (
    slug: string,
    parentId?: string
  ): Promise<ProviderSurface[]> => {
    const response = await apiClient.get<RoomSurfacesResponse>(
      `/rooms/${slug}/catalog/surfaces`,
      {
        params: {
          parent_id: parentId,
        },
      }
    );
    return (response.data.surfaces ?? []) as ProviderSurface[];
  },

  getSoloProviderSurfaces: async (
    providerId: ProviderId,
    payload: {
      secret: Record<string, string>;
      parentId?: string;
    }
  ): Promise<ProviderSurface[]> => {
    const response = await apiClient.post<{ surfaces?: ProviderSurface[] }>(
      `/solo/providers/${providerId}/surfaces`,
      {
        secret: payload.secret,
        parent_id: payload.parentId,
      }
    );
    return response.data.surfaces ?? [];
  },

  getSoloProviderClimbs: async (
    providerId: ProviderId,
    payload: {
      secret: Record<string, string>;
      surfaceId?: string;
      context?: Record<string, string>;
      q?: string;
      sort?: ClimbSort;
      cursor?: string;
      pageSize?: number;
    }
  ): Promise<ProviderCatalogClimbsResponse> => {
    const response = await apiClient.post<ProviderCatalogClimbsResponse>(
      `/solo/providers/${providerId}/climbs`,
      {
        secret: payload.secret,
        surface_id: payload.surfaceId,
        context: payload.context ?? {},
        q: payload.q,
        sort: payload.sort,
        cursor: payload.cursor,
        page_size: payload.pageSize ?? 10,
      }
    );
    return response.data;
  },

  getSoloProviderClimb: async (
    providerId: ProviderId,
    climbId: string,
    payload: {
      secret: Record<string, string>;
      surfaceId?: string;
      context?: Record<string, string>;
    }
  ): Promise<ProviderCatalogClimbResponse> => {
    const response = await apiClient.post<ProviderCatalogClimbResponse>(
      `/solo/providers/${providerId}/climbs/${encodeURIComponent(climbId)}`,
      {
        secret: payload.secret,
        surface_id: payload.surfaceId,
        context: payload.context ?? {},
      }
    );
    return response.data;
  },

  setRoomSurface: async (
    slug: string,
    payload: { surfaceId: string; context?: Record<string, string> }
  ): Promise<ProviderSurface> => {
    const requestBody: SetSurfacePayload = {
      surface_id: payload.surfaceId,
      context: payload.context ?? {},
    };
    const response = await apiClient.post<SetSurfaceResponse>(`/rooms/${slug}/surface`, requestBody);
    return response.data as ProviderSurface;
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
    const response = await apiClient.get<RoomCatalogClimbsResponseDTO>(
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
    return response.data as RoomCatalogClimbsResponse;
  },

  getRoomCatalogClimb: async (
    slug: string,
    climbId: string
  ): Promise<RoomCatalogClimbResponse> => {
    const response = await apiClient.get<RoomCatalogClimbResponseDTO>(
      `/rooms/${slug}/catalog/climbs/${encodeURIComponent(climbId)}`
    );
    return response.data as RoomCatalogClimbResponse;
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
    const requestBody: RandomPickPayload = { source };
    const response = await apiClient.post<RandomPickResponse>(
      `/rooms/${slug}/pick-random`,
      requestBody
    );
    return response.data.climb as ProviderClimb;
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

  updateRoomParticipantRole: async (
    slug: string,
    participantId: number,
    role: "participant" | "co_host"
  ): Promise<void> => {
    await apiClient.patch(`/rooms/${slug}/participants/${participantId}/role`, { role });
  },

  updateMyParticipantStatus: async (
    slug: string,
    status: ParticipantStatus
  ): Promise<void> => {
    await apiClient.put(`/rooms/${slug}/participants/me/status`, { status });
  },

  getOperatorProductMetrics: async (token: string): Promise<ProductMetrics> => {
    const response = await apiClient.get<ProductMetrics>("/operator/product", {
      headers: {
        "X-Operator-Token": token,
      },
    });
    return response.data;
  },
};

export { BASE_URL, IMAGES_BASE_URL };
