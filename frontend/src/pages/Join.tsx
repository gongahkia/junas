import { useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { api } from "../api/client"
import { Button, Card, Input, Label, PageShell } from "../components/ui"
import { storage } from "../lib/storage"

export function Join() {
  const { code } = useParams()
  const navigate = useNavigate()
  const [name, setName] = useState("")
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function go() {
    if (!code) return
    if (!name.trim()) { setErr("display name required"); return }
    setBusy(true); setErr(null)
    try {
      const r = await api.joinSession(code, name.trim())
      storage.save({
        code,
        participant_id: r.participant_id,
        ws_token: r.ws_token,
        display_name: name.trim(),
        is_host: false,
        joined_at: new Date().toISOString(),
      })
      navigate(`/s/${code}`)
    } catch (e) { setErr(String(e)) } finally { setBusy(false) }
  }

  return (
    <PageShell>
      <Card className="p-6 max-w-md mx-auto">
        <h1 className="text-2xl font-semibold mb-1">Joining session</h1>
        <p className="text-sm text-[var(--color-text-muted)] mb-6">
          Code: <span className="font-mono text-[var(--color-accent)]">{code}</span>
        </p>
        <Label>Your display name</Label>
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Sam" />
        <Button className="mt-5 w-full" onClick={go} disabled={busy}>
          {busy ? "joining..." : "Join →"}
        </Button>
        {err && <div className="mt-4 p-3 rounded-lg bg-[var(--color-danger)]/15 text-[var(--color-danger)] text-sm">{err}</div>}
      </Card>
    </PageShell>
  )
}
