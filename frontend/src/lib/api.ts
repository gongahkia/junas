import type {
  ApiErrorPayload,
  SearchResult,
  SourceId,
  SpoilerLevel,
  SummaryPayload,
  TargetsPayload,
} from "@/lib/contracts";

class ApiError extends Error {
  code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.code = code;
  }
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ??
  "http://localhost:4000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const errorPayload = (await response
      .json()
      .catch(() => null)) as ApiErrorPayload | null;

    throw new ApiError(
      errorPayload?.errors?.code ?? "request_failed",
      errorPayload?.errors?.detail ?? "The request could not be completed.",
    );
  }

  return response.json() as Promise<T>;
}

export async function searchTitles(source: SourceId, query: string) {
  const params = new URLSearchParams({
    source,
    query,
  });

  const response = await request<{ data: { results: SearchResult[] } }>(
    `/api/v1/search?${params.toString()}`,
  );

  return response.data.results;
}

export async function fetchTargets(source: SourceId, mediaId: string) {
  const response = await request<{ data: TargetsPayload }>(
    `/api/v1/media/${source}/${mediaId}/targets`,
  );

  return response.data;
}

export async function createSummary(input: {
  source: SourceId;
  mediaId: string;
  targetType: "title" | "episode";
  targetId?: string;
  spoilerLevel: SpoilerLevel;
}) {
  const response = await request<{ data: SummaryPayload }>(`/api/v1/summarize`, {
    method: "POST",
    body: JSON.stringify({
      source: input.source,
      media_id: input.mediaId,
      target_type: input.targetType,
      target_id: input.targetId,
      spoiler_level: input.spoilerLevel,
    }),
  });

  return response.data;
}

export function getApiErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Something went wrong while talking to the API.";
}

export function getApiErrorCode(error: unknown) {
  if (error instanceof ApiError) {
    return error.code;
  }

  return "unknown";
}
