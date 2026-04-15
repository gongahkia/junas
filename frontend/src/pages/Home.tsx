import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { api } from "../api/client"
import type { ProviderDescriptor } from "../api/types"
import { Button, Card, Input, Label, PageShell, Pill } from "../components/ui"
import { storage } from "../lib/storage"

export function Home() {
  const navigate = useNavigate()
  const [providers, setProviders] = useState<ProviderDescriptor[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [name, setName] = useState("")
  const [joinCode, setJoinCode] = useState("")
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    api.listProviders().then(setProviders).catch((e) => setErr(String(e)))
  }, [])

  const recent = storage.list().slice(0, 5)

  async function create() {
    if (!name.trim()) { setErr("display name required"); return }
    setBusy(true); setErr(null)
    try {
      const r = await api.createSession(name.trim(), [...selected])
      storage.save({
        code: r.code,
        participant_id: r.host_participant_id,
        ws_token: "",
        display_name: name.trim(),
        is_host: true,
        host_secret: r.host_secret,
        joined_at: new Date().toISOString(),
      })
      navigate(`/s/${r.code}`)
    } catch (e) { setErr(String(e)) } finally { setBusy(false) }
  }

  function toggle(key: string) {
    const s = new Set(selected)
    s.has(key) ? s.delete(key) : s.add(key)
    setSelected(s)
  }

  return (
    <PageShell>
      <h1 className="text-4xl font-bold tracking-tight mb-2">Climb together.</h1>
      <p className="text-[var(--color-text-muted)] mb-10 max-w-lg">
        Start a session, queue climbs from any supported board, vote with friends, and run the wall together — in real time.
      </p>

      <div className="grid md:grid-cols-2 gap-6">
        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-1">Start a new session</h2>
          <p className="text-sm text-[var(--color-text-muted)] mb-5">As host you control providers, queue, and finalists.</p>
          <Label>Your display name</Label>
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Alex" />

          <div className="mt-5">
            <Label>Enable boards</Label>
            <div className="flex flex-wrap gap-2">
              {providers.map((p) => (
                <button
                  key={p.key}
                  type="button"
                  onClick={() => toggle(p.key)}
                  className={`text-left px-3 py-2 rounded-lg border transition ${
                    selected.has(p.key)
                      ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10"
                      : "border-[var(--color-border)] bg-[var(--color-surface-2)]"
                  }`}
                  title={p.requires_credentials ? "Will need credentials" : "No credentials needed"}
                >
                  <div className="text-sm font-medium">{p.name}</div>
                  <div className="mt-1 flex items-center gap-1.5">
                    <Pill tone={p.status === "ok" ? "ok" : p.status === "experimental" ? "warn" : "bad"}>
                      {p.status}
                    </Pill>
                    {p.requires_credentials && <Pill tone="neutral">creds</Pill>}
                  </div>
                </button>
              ))}
            </div>
          </div>

          <Button className="mt-6 w-full" onClick={create} disabled={busy}>
            {busy ? "creating..." : "Create session →"}
          </Button>
        </Card>

        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-1">Join a session</h2>
          <p className="text-sm text-[var(--color-text-muted)] mb-5">Enter a 6-character session code from the host.</p>
          <Label>Session code</Label>
          <Input
            value={joinCode}
            onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
            placeholder="ABCDEF"
            maxLength={6}
            className="font-mono tracking-widest text-center text-lg"
          />
          <Button
            variant="secondary"
            className="mt-4 w-full"
            onClick={() => joinCode.length === 6 && navigate(`/join/${joinCode}`)}
            disabled={joinCode.length !== 6}
          >
            Join →
          </Button>

          {recent.length > 0 && (
            <div className="mt-6 pt-6 border-t border-[var(--color-border)]">
              <Label>Recent sessions</Label>
              <ul className="space-y-1.5">
                {recent.map((m) => (
                  <li key={m.code}>
                    <button
                      onClick={() => navigate(`/s/${m.code}`)}
                      className="w-full text-left px-3 py-2 rounded-lg hover:bg-[var(--color-surface-2)] flex justify-between text-sm"
                    >
                      <span><span className="font-mono">{m.code}</span> — {m.display_name}</span>
                      {m.is_host && <Pill tone="warn">host</Pill>}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      </div>

      {err && <div className="mt-6 p-3 rounded-lg bg-[var(--color-danger)]/15 text-[var(--color-danger)] text-sm">{err}</div>}
    </PageShell>
  )
}
