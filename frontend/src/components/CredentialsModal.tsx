import { useEffect, useState } from "react"
import { api } from "../api/client"
import type { ProviderDescriptor } from "../api/types"
import { Button, Input, Label, Modal, Pill } from "./ui"

type Field = { key: string; label: string; type?: string; placeholder?: string }

const FIELDS_BY_PROVIDER: Record<string, Field[]> = {
  tension: [
    { key: "username", label: "Username" },
    { key: "password", label: "Password", type: "password" },
  ],
  grasshopper: [
    { key: "username", label: "Username" },
    { key: "password", label: "Password", type: "password" },
  ],
  decoy: [
    { key: "username", label: "Username" },
    { key: "password", label: "Password", type: "password" },
  ],
  soill: [
    { key: "username", label: "Username" },
    { key: "password", label: "Password", type: "password" },
  ],
  touchstone: [
    { key: "username", label: "Username" },
    { key: "password", label: "Password", type: "password" },
  ],
  aurora: [
    { key: "username", label: "Username" },
    { key: "password", label: "Password", type: "password" },
  ],
  moonboard: [
    { key: "username", label: "MoonBoard username" },
    { key: "password", label: "Password", type: "password" },
  ],
  kilter: [
    { key: "username", label: "Username" },
    { key: "password", label: "Password", type: "password" },
    { key: "client_id", label: "Mobile app client_id (advanced)", placeholder: "leave blank if you don't have it" },
  ],
  crux: [
    { key: "token", label: "API token (Bearer)", placeholder: "from cruxapp.ca → settings → API Authentication" },
    { key: "gym_slug", label: "Default gym slug" },
  ],
  moonboard_catalog: [],
}

export function CredentialsModal({
  code,
  hostSecret,
  onClose,
}: {
  code: string
  hostSecret: string
  onClose: () => void
}) {
  const [providers, setProviders] = useState<ProviderDescriptor[]>([])
  const [chosen, setChosen] = useState<string>("")
  const [values, setValues] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ type: "ok" | "bad"; text: string } | null>(null)

  useEffect(() => { api.listProviders().then(setProviders).catch(() => {}) }, [])

  const fields = FIELDS_BY_PROVIDER[chosen] ?? [
    { key: "username", label: "Username" },
    { key: "password", label: "Password", type: "password" },
  ]

  async function attach() {
    setBusy(true); setMsg(null)
    try {
      await api.attachCredentials(code, chosen, values, hostSecret)
      setMsg({ type: "ok", text: `${chosen}: attached & validated` })
      setValues({})
    } catch (e) { setMsg({ type: "bad", text: String(e) }) } finally { setBusy(false) }
  }

  return (
    <Modal open onClose={onClose} title="Provider credentials">
      <p className="text-sm text-[var(--color-text-muted)] mb-4">
        Credentials are encrypted at rest and deleted when the session ends. Only you (the host) can attach.
      </p>

      <Label>Pick a provider</Label>
      <div className="flex flex-wrap gap-1.5 mb-4">
        {providers.map((p) => (
          <button
            key={p.key}
            onClick={() => { setChosen(p.key); setValues({}); setMsg(null) }}
            className={`px-2.5 py-1 rounded-lg text-sm border ${
              chosen === p.key
                ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10"
                : "border-[var(--color-border)] bg-[var(--color-surface-2)]"
            }`}
          >
            {p.name}{!p.requires_credentials && " ·"} {!p.requires_credentials && <Pill tone="ok">no creds</Pill>}
          </button>
        ))}
      </div>

      {chosen && (
        <div className="space-y-3">
          {fields.length === 0 && <p className="text-sm text-[var(--color-text-muted)]">No credentials needed for this provider.</p>}
          {fields.map((f) => (
            <div key={f.key}>
              <Label>{f.label}</Label>
              <Input
                type={f.type ?? "text"}
                placeholder={f.placeholder}
                value={values[f.key] ?? ""}
                onChange={(e) => setValues({ ...values, [f.key]: e.target.value })}
              />
            </div>
          ))}
          <Button onClick={attach} disabled={busy} className="w-full">
            {busy ? "validating..." : `Attach ${chosen}`}
          </Button>
        </div>
      )}

      {msg && (
        <div className={`mt-4 p-3 rounded-lg text-sm ${msg.type === "ok" ? "bg-[var(--color-success)]/15 text-[var(--color-success)]" : "bg-[var(--color-danger)]/15 text-[var(--color-danger)]"}`}>
          {msg.text}
        </div>
      )}
    </Modal>
  )
}
