import type { Participant } from "../api/types"

const KEY = "kt.sessions"

export type SessionMembership = {
  code: string
  participant_id: string
  ws_token: string
  display_name: string
  is_host: boolean
  host_secret?: string
  joined_at: string
}

type Store = Record<string, SessionMembership>

function read(): Store {
  try { return JSON.parse(localStorage.getItem(KEY) || "{}") } catch { return {} }
}

function write(s: Store): void {
  localStorage.setItem(KEY, JSON.stringify(s))
}

export const storage = {
  save(m: SessionMembership) {
    const s = read()
    s[m.code] = m
    write(s)
  },
  get(code: string): SessionMembership | undefined {
    return read()[code]
  },
  remove(code: string) {
    const s = read()
    delete s[code]
    write(s)
  },
  list(): SessionMembership[] {
    return Object.values(read()).sort((a, b) => b.joined_at.localeCompare(a.joined_at))
  },
}

export function roleOf(meId: string, hostId: string, participants: Record<string, Participant>): "host" | "cohost" | "participant" | "unknown" {
  if (meId === hostId) return "host"
  return participants[meId]?.role ?? "unknown"
}
