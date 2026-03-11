export type ClimbSort = "popular" | "newest";
export type ProviderId = "kilter" | "crux" | "test" | "moonboard" | "tension" | "grasshopper";
export type RoomStatus = "open" | "closed";
export type QueueStatus = "queued" | "next" | "current" | "done";
export type ParticipantStatus = "watching" | "ready" | "resting" | "away";
export type RandomPickSource = "auto" | "finalists" | "top_voted";
export type ApiErrorCode =
  | "bad_request"
  | "display_name_required"
  | "display_name_taken"
  | "fist_bumps_disabled"
  | "forbidden"
  | "internal_error"
  | "invalid_request"
  | "operator_auth_required"
  | "provider_auth_failed"
  | "provider_not_connected"
  | "rate_limited"
  | "room_closed"
  | "room_not_found"
  | "runtime_unavailable"
  | "session_cookie_failed"
  | "session_expired"
  | "session_invalid"
  | "session_required"
  | "unauthorized"
  | "unsupported_provider";
export type RoomEventResource =
  | "room"
  | "participants"
  | "queue"
  | "finalists"
  | "votes"
  | "catalog"
  | "connection"
  | "surface"
  | "current_climb";

export interface Board {
  id: number;
  name: string;
  kilter_name: string;
  preview_image_filename?: string;
  climb_count?: number;
}

export interface GradeInfo {
  boulder: string;
  route: string;
}

export interface HighlightedHold {
  position: number;
  x: number;
  y: number;
  role: string;
  color: string;
}

export interface Climb {
  uuid: string;
  climb_name: string;
  description?: string;
  frames: string;
  grades?: Record<string, GradeInfo>;
  setter_name: string;
  image_filenames?: string[];
  highlighted_holds?: HighlightedHold[];
  product_size_id: number;
  ascends: number;
  created_at: string;
}

export interface SoloSavedClimb {
  uuid: string;
  product_size_id: number;
  climb_name: string;
  setter_name: string;
  board_id: string;
  board_name: string;
  angle: number;
  grade?: string;
  image_filename?: string;
  ascends: number;
  saved_at: string;
}

export interface SoloFilterPreset {
  id: string;
  label: string;
  board_id: string;
  board_name: string;
  angle: number;
  sort: ClimbSort;
  q?: string;
  setter?: string;
  saved_at: string;
}

export interface PendingSoloRoomSeed {
  board_id: string;
  board_name: string;
  angle: number;
  climbs: SoloSavedClimb[];
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

export interface ApiErrorPayload {
  error?: string;
  status?: string;
  code?: ApiErrorCode | string;
  request_id?: string;
  trace_id?: string;
}

export interface ProviderAuthField {
  key: string;
  label: string;
  type: string;
  placeholder?: string;
  autocomplete?: string;
}

export interface ProviderCapability {
  id: ProviderId;
  label: string;
  room_supported: boolean;
  solo_supported: boolean;
  surface_hierarchy: "board" | "nested" | string;
  auth_fields: ProviderAuthField[];
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
  highlighted_holds?: HighlightedHold[];
  meta?: Record<string, string>;
}

export interface Participant {
  id: number;
  display_name: string;
  role: string;
  status: ParticipantStatus;
  is_online: boolean;
}

export interface RoomPermissions {
  manage_session: boolean;
  manage_surface: boolean;
  manage_queue: boolean;
  manage_finalists: boolean;
  edit_room_settings: boolean;
  manage_participants: boolean;
  assign_co_hosts: boolean;
  close_room: boolean;
}

export interface QueueEntry {
  id: number;
  status: QueueStatus;
  position: number;
  added_by: string;
  climb: ProviderClimb;
}

export interface FinalistEntry {
  id: number;
  position: number;
  added_by: string;
  climb: ProviderClimb;
}

export interface SessionSummaryClimb {
  position?: number;
  status?: string;
  added_by?: string;
  vote_count?: number;
  climb: ProviderClimb;
}

export interface SessionSummary {
  room_slug: string;
  room_name?: string;
  provider_id: ProviderId;
  surface_name?: string;
  surface_kind?: string;
  participant_count: number;
  closed_at: string;
  top_voted: SessionSummaryClimb[];
  final_queue: SessionSummaryClimb[];
  finalists: SessionSummaryClimb[];
}

export interface RoomSnapshot {
  slug: string;
  room_name?: string;
  status: RoomStatus;
  provider_id: ProviderId;
  version: number;
  surface?: ProviderSurface;
  connection: ProviderConnectionState;
  current_climb?: ProviderClimb;
  participants: Participant[];
  finalists: FinalistEntry[];
  queue: QueueEntry[];
  vote_counts: Record<string, number>;
  my_votes: string[];
  fist_bumps_enabled: boolean;
  can_manage: boolean;
  permissions: RoomPermissions;
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
  resources?: RoomEventResource[];
}
