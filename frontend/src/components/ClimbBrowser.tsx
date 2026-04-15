import { useState } from "react"
import { api } from "../api/client"
import type { ClimbOut } from "../api/types"
import { Button, Input, Label, Modal, Pill } from "./ui"

export function ClimbBrowser({
  code,
  provider,
  onClose,
  onAdd,
}: {
  code: string
  provider: string
  onClose: () => void
  onAdd: (climb_id: string, name: string) => void
}) {
  const [text, setText] = useState("")
  const [layoutId, setLayoutId] = useState("")
  const [angle, setAngle] = useState("")
  const [holdsRequired, setHoldsRequired] = useState("")
  const [results, setResults] = useState<ClimbOut[]>([])
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function search() {
    setBusy(true); setErr(null)
    try {
      const r = await api.searchClimbs(code, {
        text: text || undefined,
        layout_id: layoutId || undefined,
        angle: angle ? Number(angle) : undefined,
        holds_required: holdsRequired ? holdsRequired.split(/[,\s]+/).filter(Boolean) : undefined,
        limit: 30,
      })
      setResults(r.climbs)
    } catch (e) { setErr(String(e)); setResults([]) } finally { setBusy(false) }
  }

  return (
    <Modal open onClose={onClose} title={`Browse climbs — ${provider}`}>
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label>Layout / Gym slug</Label>
            <Input value={layoutId} onChange={(e) => setLayoutId(e.target.value)} placeholder="e.g. benchmarks, 2019" />
          </div>
          <div>
            <Label>Angle</Label>
            <Input value={angle} onChange={(e) => setAngle(e.target.value)} placeholder="e.g. 40" />
          </div>
        </div>
        <div>
          <Label>Search text</Label>
          <Input value={text} onChange={(e) => setText(e.target.value)} placeholder="name, setter…" />
        </div>
        <div>
          <Label>Holds required (comma separated)</Label>
          <Input value={holdsRequired} onChange={(e) => setHoldsRequired(e.target.value)} placeholder="e.g. C5, K10" />
        </div>
        <Button onClick={search} disabled={busy} className="w-full">{busy ? "searching..." : "Search"}</Button>
        {err && <div className="p-2 rounded bg-[var(--color-danger)]/15 text-[var(--color-danger)] text-sm">{err}</div>}

        {results.length > 0 && (
          <ul className="mt-2 space-y-1.5 max-h-72 overflow-auto">
            {results.map((c) => (
              <li key={`${c.provider}:${c.id}`} className="flex items-center justify-between p-2 rounded-lg bg-[var(--color-surface-2)] border border-[var(--color-border)]">
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium truncate">{c.name || c.id}</div>
                  <div className="text-xs text-[var(--color-text-muted)] flex gap-1.5 items-center">
                    {c.grade && <Pill tone="neutral">{c.grade}</Pill>}
                    {c.angle != null && <span>{c.angle}°</span>}
                    {c.ascents != null && <span>· {c.ascents} sends</span>}
                  </div>
                </div>
                <Button onClick={() => onAdd(c.id, c.name || c.id)}>Add</Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Modal>
  )
}
