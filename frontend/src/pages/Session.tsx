import { useEffect, useRef, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { api } from "../api/client"
import { SessionSocket } from "../api/ws"
import type { QueuedClimb, CompletedClimb, SessionState } from "../api/types"
import { Button, Card, PageShell, Pill } from "../components/ui"
import { storage, type SessionMembership } from "../lib/storage"
import { ClimbBrowser } from "../components/ClimbBrowser"
import { CredentialsModal } from "../components/CredentialsModal"

type ConnState = "idle" | "connecting" | "open" | "closed"

export function Session() {
  const { code = "" } = useParams()
  const navigate = useNavigate()
  const [me, setMe] = useState<SessionMembership | undefined>(() => storage.get(code))
  const [state, setState] = useState<SessionState | null>(null)
  const [conn, setConn] = useState<ConnState>("idle")
  const [showBrowser, setShowBrowser] = useState(false)
  const [showCreds, setShowCreds] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const sockRef = useRef<SessionSocket | null>(null)

  useEffect(() => {
    if (!me) { navigate(`/join/${code}`); return }

    let ws_token = me.ws_token
    const setup = async () => {
      // Host needs a ws_token too — get one via join with their existing display name.
      if (!ws_token) {
        try {
          const j = await api.joinSession(code, me.display_name + (me.is_host ? " (host)" : ""))
          // Note: this creates a fresh participant id for ws; we keep the host's saved id for credential ops
          ws_token = j.ws_token
          storage.save({ ...me, ws_token, participant_id: j.participant_id })
          setMe({ ...me, ws_token, participant_id: j.participant_id })
        } catch (e) { setErr(String(e)); return }
      }

      setConn("connecting")
      const sock = new SessionSocket(code, ws_token)
      sockRef.current = sock
      sock.connect({
        onOpen: () => setConn("open"),
        onClose: () => setConn("closed"),
        onError: (e) => console.error("ws error", e),
        onMessage: (msg) => {
          if (msg.type === "roomStateUpdate") setState(msg.payload)
          else if (msg.type === "error") setErr(msg.payload.detail || msg.payload.error)
          else if (msg.type === "sessionEnded") { setConn("closed"); setErr("session ended by host") }
          else if (msg.type === "participantKicked" && msg.payload?.participant_id === me.participant_id) {
            sockRef.current?.close()
            storage.remove(code)
            setConn("closed")
            setErr("you were removed from the session")
            setTimeout(() => navigate("/"), 1200)
          }
        },
      })
    }
    setup()

    return () => { sockRef.current?.close(); sockRef.current = null }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code])

  if (!me) return null

  const meId = me.participant_id
  const myRole = state?.host_id === meId ? "host" : (state?.participants[meId]?.role ?? "participant")
  const isHost = myRole === "host"
  const isCoOrHost = myRole === "host" || myRole === "cohost"

  function action(type: string, payload: Record<string, unknown> = {}) {
    sockRef.current?.send(type, payload)
  }

  async function endSession() {
    if (!me?.host_secret) return
    if (!confirm("End session for everyone?")) return
    try {
      await api.endSession(code, me.host_secret)
      storage.remove(code)
      navigate("/")
    } catch (e) { setErr(String(e)) }
  }

  return (
    <PageShell>
      <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold tracking-tight">
              <span className="font-mono text-[var(--color-accent)]">{code}</span>
            </h1>
            <Pill tone={conn === "open" ? "ok" : conn === "connecting" ? "warn" : "bad"}>
              {conn}
            </Pill>
            <Pill tone={isHost ? "warn" : "neutral"}>{myRole}</Pill>
          </div>
          <p className="text-sm text-[var(--color-text-muted)] mt-1">
            {state ? `${Object.keys(state.participants).length} climbers · ${state.queue.length} queued · ${state.history.length} done` : "loading…"}
          </p>
        </div>
        <div className="flex gap-2">
          {isCoOrHost && (
            <Button variant="secondary" onClick={() => setShowBrowser(true)}>+ Add climb</Button>
          )}
          {!isCoOrHost && (
            <Button variant="secondary" onClick={() => setShowBrowser(true)}>+ Suggest climb</Button>
          )}
          {isHost && (
            <Button variant="secondary" onClick={() => setShowCreds(true)}>Credentials</Button>
          )}
          {isHost && (
            <Button variant="danger" onClick={endSession}>End session</Button>
          )}
        </div>
      </div>

      {err && (
        <div className="mb-4 p-3 rounded-lg bg-[var(--color-danger)]/15 text-[var(--color-danger)] text-sm flex justify-between">
          <span>{err}</span>
          <button onClick={() => setErr(null)} className="text-[var(--color-danger)]">✕</button>
        </div>
      )}

      {!state ? (
        <Card className="p-12 text-center text-[var(--color-text-muted)]">connecting…</Card>
      ) : (
        <div className="grid lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 space-y-4">
            <Card className="p-5">
              <div className="flex justify-between items-baseline mb-3">
                <h2 className="text-lg font-semibold">Up next</h2>
                <span className="text-xs text-[var(--color-text-muted)]">{state.queue.length} climbs</span>
              </div>
              {state.queue.length === 0 && (
                <p className="text-sm text-[var(--color-text-muted)] py-4 text-center">queue is empty — add a climb to get started</p>
              )}
              <ul className="space-y-2">
                {state.queue.map((q: QueuedClimb) => {
                  const isFinalist = state.finalists.includes(q.id)
                  const myVote = q.votes.includes(meId)
                  return (
                    <li key={q.id}
                        className={`p-3 rounded-lg border flex items-center gap-3 ${
                          isFinalist
                            ? "border-[var(--color-accent-2)] bg-[var(--color-accent-2)]/10"
                            : "border-[var(--color-border)] bg-[var(--color-surface-2)]"
                        }`}>
                      <button
                        onClick={() => action("voteClimb", { queue_id: q.id, value: !myVote })}
                        className={`flex flex-col items-center justify-center px-2 min-w-12 rounded-lg ${
                          myVote ? "bg-[var(--color-accent)] text-black" : "bg-[var(--color-surface)] text-[var(--color-text-muted)]"
                        }`}
                        title={myVote ? "Remove vote" : "Vote"}
                      >
                        <span className="text-xs">▲</span>
                        <span className="text-sm font-bold">{q.votes.length}</span>
                      </button>
                      <div className="flex-1 min-w-0">
                        <div className="font-medium truncate">{q.name || q.climb_id}</div>
                        <div className="text-xs text-[var(--color-text-muted)] flex gap-2 items-center">
                          <Pill tone="neutral">{q.provider}</Pill>
                          <span>by {state.participants[q.added_by]?.display_name ?? "—"}</span>
                          {isFinalist && <Pill tone="warn">finalist</Pill>}
                        </div>
                      </div>
                      <div className="flex gap-1.5">
                        {isCoOrHost && !isFinalist && (
                          <Button variant="ghost" onClick={() => action("markFinalist", { queue_id: q.id })}>★</Button>
                        )}
                        <Button variant="ghost" onClick={() => action("markCompleted", { queue_id: q.id, result: "sent" })}>
                          ✓ sent
                        </Button>
                        {(isCoOrHost || q.added_by === meId) && (
                          <Button variant="ghost" onClick={() => action("removeFromQueue", { queue_id: q.id })}>✕</Button>
                        )}
                      </div>
                    </li>
                  )
                })}
              </ul>
            </Card>

            <Card className="p-5">
              <h2 className="text-lg font-semibold mb-3">History</h2>
              {state.history.length === 0 ? (
                <p className="text-sm text-[var(--color-text-muted)]">no climbs done yet</p>
              ) : (
                <ul className="space-y-1.5">
                  {state.history.slice().reverse().map((h: CompletedClimb, i: number) => (
                    <li key={i} className="flex items-center justify-between text-sm py-1.5 border-b border-[var(--color-border)] last:border-0">
                      <span>
                        <Pill tone="neutral">{h.provider}</Pill>{" "}
                        <span className="font-medium">{h.name || h.climb_id}</span>
                      </span>
                      <span className="text-xs text-[var(--color-text-muted)]">
                        {state.participants[h.completed_by]?.display_name ?? "—"} · {h.result}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>

          <div className="space-y-4">
            <Card className="p-5">
              <h2 className="text-lg font-semibold mb-3">Climbers</h2>
              <ul className="space-y-2">
                {Object.values(state.participants).map((p) => {
                  const canManage = isHost && p.id !== state.host_id // host can't manage themselves
                  return (
                    <li key={p.id} className="flex items-center justify-between text-sm gap-2">
                      <span className="truncate">{p.display_name}{p.id === meId && " (you)"}</span>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <Pill tone={p.role === "host" ? "warn" : "neutral"}>{p.role}</Pill>
                        {canManage && p.role === "participant" && (
                          <button
                            onClick={() => action("setRole", { participant_id: p.id, role: "cohost" })}
                            className="text-xs px-2 py-0.5 rounded border border-[var(--color-border)] hover:bg-[var(--color-surface-2)]"
                            title="Promote to cohost"
                          >↑ cohost</button>
                        )}
                        {canManage && p.role === "cohost" && (
                          <button
                            onClick={() => action("setRole", { participant_id: p.id, role: "participant" })}
                            className="text-xs px-2 py-0.5 rounded border border-[var(--color-border)] hover:bg-[var(--color-surface-2)]"
                            title="Demote to participant"
                          >↓ participant</button>
                        )}
                        {canManage && (
                          <button
                            onClick={() => {
                              if (confirm(`Remove ${p.display_name} from the session?`))
                                action("kickParticipant", { participant_id: p.id })
                            }}
                            className="text-xs px-2 py-0.5 rounded border border-[var(--color-danger)]/30 text-[var(--color-danger)] hover:bg-[var(--color-danger)]/10"
                            title="Remove from session"
                          >✕</button>
                        )}
                      </div>
                    </li>
                  )
                })}
              </ul>
            </Card>

            <Card className="p-5">
              <h2 className="text-lg font-semibold mb-3">Board</h2>
              {state.provider
                ? <Pill tone="ok">{state.provider}</Pill>
                : <p className="text-sm text-[var(--color-text-muted)]">No board set.</p>}
            </Card>
          </div>
        </div>
      )}

      {showBrowser && state?.provider && (
        <ClimbBrowser
          code={code}
          provider={state.provider}
          onClose={() => setShowBrowser(false)}
          onAdd={(climb_id, name) => {
            action("addToQueue", { climb_id, name })
            setShowBrowser(false)
          }}
        />
      )}

      {showCreds && me?.host_secret && state?.provider && (
        <CredentialsModal
          code={code}
          provider={state.provider}
          hostSecret={me.host_secret}
          onClose={() => setShowCreds(false)}
        />
      )}
    </PageShell>
  )
}
