import axios from "axios";
import { config } from "./config";
import type {
  Board,
  ApiResponse,
  PaginatedClimbsParams,
  PaginatedClimbsResponse,
} from "./types";

const BASE_URL = config.api.baseUrl;
const IMAGES_BASE_URL = `${BASE_URL}/images`;

const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 10000,
});

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
};

export { BASE_URL, IMAGES_BASE_URL };
