import type {
  ClimbOut,
  CreateSessionResp,
  JoinSessionResp,
  ProviderDescriptor,
  SessionSummary,
} from "./types"

export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(status: number, detail: unknown) {
    super(`HTTP ${status}: ${JSON.stringify(detail)}`)
    this.status = status
    this.detail = detail
  }
}

async function jfetch<T>(input: string, init?: RequestInit): Promise<T> {
  const r = await fetch(input, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
  })
  if (!r.ok) {
    let detail: unknown
    try { detail = await r.json() } catch { detail = await r.text() }
    throw new ApiError(r.status, detail)
  }
  if (r.status === 204) return undefined as T
  return r.json() as Promise<T>
}

export const api = {
  health: () => jfetch<{ status: string }>("/healthz"),

  listProviders: () => jfetch<ProviderDescriptor[]>("/api/providers"),

  createSession: (host_display_name: string, enabled_providers: string[]) =>
    jfetch<CreateSessionResp>("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ host_display_name, enabled_providers }),
    }),

  getSession: (code: string) =>
    jfetch<SessionSummary>(`/api/sessions/${encodeURIComponent(code)}`),

  joinSession: (code: string, display_name: string) =>
    jfetch<JoinSessionResp>(`/api/sessions/${encodeURIComponent(code)}/join`, {
      method: "POST",
      body: JSON.stringify({ display_name }),
    }),

  endSession: (code: string, host_secret: string) =>
    jfetch<{ ended: boolean }>(
      `/api/sessions/${encodeURIComponent(code)}?host_secret=${encodeURIComponent(host_secret)}`,
      { method: "DELETE" },
    ),

  attachCredentials: (
    code: string,
    provider: string,
    credentials: Record<string, unknown>,
    host_secret: string,
  ) =>
    jfetch<{ provider: string; ok: boolean }>(
      `/api/sessions/${encodeURIComponent(code)}/credentials`,
      {
        method: "POST",
        body: JSON.stringify({ provider, credentials, host_secret }),
      },
    ),

  searchClimbs: (
    code: string,
    params: {
      provider: string
      text?: string
      angle?: number
      layout_id?: string
      holds_required?: string[]
      holds_forbidden?: string[]
      limit?: number
      offset?: number
    },
  ) => {
    const q = new URLSearchParams()
    q.set("provider", params.provider)
    if (params.text) q.set("text", params.text)
    if (params.angle != null) q.set("angle", String(params.angle))
    if (params.layout_id) q.set("layout_id", params.layout_id)
    for (const h of params.holds_required ?? []) q.append("holds_required", h)
    for (const h of params.holds_forbidden ?? []) q.append("holds_forbidden", h)
    if (params.limit != null) q.set("limit", String(params.limit))
    if (params.offset != null) q.set("offset", String(params.offset))
    return jfetch<{ climbs: ClimbOut[] }>(
      `/api/sessions/${encodeURIComponent(code)}/climbs?${q}`,
    )
  },
}
