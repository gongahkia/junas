export type ProviderDescriptor = {
  key: string
  name: string
  status: "ok" | "experimental" | "unavailable"
  requires_credentials: boolean
}

export type CreateSessionResp = {
  code: string
  host_participant_id: string
  host_secret: string
}

export type JoinSessionResp = {
  participant_id: string
  ws_token: string
}

export type SessionSummary = {
  code: string
  provider: string
  participant_count: number
  queue_length: number
  created_at: string
  ended_at: string | null
}

export type ClimbOut = {
  id: string
  provider: string
  name: string
  setter: string | null
  grade: string | null
  angle: number | null
  ascents: number | null
}

export type Participant = {
  id: string
  display_name: string
  role: "host" | "cohost" | "participant"
  joined_at: string
}

export type QueuedClimb = {
  id: string
  provider: string
  climb_id: string
  name: string
  added_by: string
  votes: string[]
  added_at: string
}

export type CompletedClimb = {
  climb_id: string
  provider: string
  name: string
  completed_by: string
  result: string
  completed_at: string
}

export type SessionState = {
  code: string
  host_id: string
  provider: string
  participants: Record<string, Participant>
  queue: QueuedClimb[]
  finalists: string[]
  history: CompletedClimb[]
}

export type WsMessage =
  | { type: "roomStateUpdate"; payload: SessionState }
  | { type: "queueUpdate"; payload: { queue: QueuedClimb[] } }
  | { type: "participantsUpdate"; payload: { participants: Participant[] } }
  | { type: "finalistsUpdate"; payload: { finalists: string[] } }
  | { type: "historyUpdate"; payload: { history: CompletedClimb[] } }
  | { type: "sessionEnded"; payload: Record<string, never> }
  | { type: "participantKicked"; payload: { participant_id: string } }
  | { type: "error"; payload: { error: string; detail?: string } }
