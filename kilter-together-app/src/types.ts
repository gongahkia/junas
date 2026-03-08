export type ClimbSort = "popular" | "newest";

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
