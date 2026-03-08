export type ClimbSort = "popular" | "newest";
export type ProviderId = "kilter" | "crux";
export type RoomStatus = "open" | "closed";
export type QueueStatus = "queued" | "next" | "current" | "done";

export interface Board {
  id: number;
  name: string;
  kilter_name: string;
}

export interface GradeInfo {
  boulder: string;
  route: string;
}

export interface Climb {
  uuid: string;
  climb_name: string;
  description?: string;
  frames: string;
  grades?: Record<string, GradeInfo>;
  setter_name: string;
  image_filenames?: string[];
  product_size_id: number;
  ascends: number;
  created_at: string;
}

export interface PaginatedClimbsResponse {
  climbs: Climb[];
  has_more: boolean;
  next_cursor?: string;
  page_size: number;
}

export interface ApiResponse {
  boards?: Board[];
  climbs?: Climb[];
}

export interface PaginatedClimbsParams {
  boardId: string;
  angle: number;
  cursor?: string;
  pageSize?: number;
  name?: string;
  setter?: string;
  sort?: ClimbSort;
}

export interface ProviderConnectionState {
  provider_id: ProviderId;
  metadata?: Record<string, string>;
  connected: boolean;
}

export interface ProviderSurface {
  id: string;
  kind: string;
  name: string;
  description?: string;
  parent_id?: string;
  meta?: Record<string, string>;
}

export interface ProviderClimbMedia {
  url: string;
  kind: string;
}

export interface ProviderClimb {
  id: string;
  external_id: string;
  provider_id: ProviderId;
  surface_id: string;
  name: string;
  description?: string;
  setter_name?: string;
  primary_grade?: string;
  secondary_grade?: string;
  created_at?: string;
  popularity?: number;
  media?: ProviderClimbMedia[];
  meta?: Record<string, string>;
}

export interface Participant {
  id: number;
  display_name: string;
  role: string;
  is_online: boolean;
}

export interface QueueEntry {
  id: number;
  status: QueueStatus;
  position: number;
  added_by: string;
  climb: ProviderClimb;
}

export interface RoomSnapshot {
  slug: string;
  status: RoomStatus;
  provider_id: ProviderId;
  version: number;
  surface?: ProviderSurface;
  connection: ProviderConnectionState;
  current_climb?: ProviderClimb;
  participants: Participant[];
  queue: QueueEntry[];
  vote_counts: Record<string, number>;
  my_votes: string[];
  can_manage: boolean;
  display_name?: string;
}

export interface RoomCatalogClimbsResponse {
  climbs: ProviderClimb[];
  has_more: boolean;
  next_cursor?: string;
  page_size: number;
  vote_counts: Record<string, number>;
  my_votes: string[];
}

export interface RoomCatalogClimbResponse {
  climb: ProviderClimb;
  vote_count: number;
  my_vote: boolean;
  is_queued: boolean;
}

export interface RoomEventPayload {
  type: string;
  room_slug: string;
  version: number;
}
