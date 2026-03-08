import axios from "axios";
import { config } from "./config";
import type {
  Board,
  Climb,
  ApiResponse,
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

  getClimbs: async (boardId: string, angle?: number): Promise<Climb[]> => {
    try {
      let url = `/climbs?board_id=${boardId}`;
      if (angle !== undefined) {
        url += `&angle=${angle}`;
      }
      const response = await apiClient.get<ApiResponse>(url);
      return response.data.climbs || [];
    } catch (error) {
      console.error("Error fetching climbs:", error);
      throw error;
    }
  },

  getPaginatedClimbs: async (
    boardId: string,
    angle?: number,
    cursor?: string,
    pageSize: number = 10
  ): Promise<PaginatedClimbsResponse> => {
    try {
      let url = `/climbs?board_id=${boardId}&page_size=${pageSize}`;
      if (angle !== undefined) {
        url += `&angle=${angle}`;
      }
      if (cursor) {
        url += `&cursor=${encodeURIComponent(cursor)}`;
      }
      const response = await apiClient.get<PaginatedClimbsResponse>(url);
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

  getImageUrls: (imageFilenames: string): string[] => {
    if (!imageFilenames) return [];
    const filenames = imageFilenames.includes("/")
      ? imageFilenames.split("/").slice(1)
      : [imageFilenames];
    return filenames.map((filename) => api.getImageUrl(filename));
  },
};

export { BASE_URL, IMAGES_BASE_URL };
