import { useState } from "react"
import { api } from "../api/client"
import { Button, Input, Label, Modal } from "./ui"
import { PROVIDER_LINKS } from "../lib/providerLinks"

export type CredField = { key: string; label: string; type?: string; placeholder?: string }

export const FIELDS_BY_PROVIDER: Record<string, CredField[]> = {
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
  provider,
  hostSecret,
  onClose,
}: {
  code: string
  provider: string
  hostSecret: string
  onClose: () => void
}) {
  const [values, setValues] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ type: "ok" | "bad"; text: string } | null>(null)

  const fields: CredField[] = FIELDS_BY_PROVIDER[provider] ?? [
    { key: "username", label: "Username" },
    { key: "password", label: "Password", type: "password" },
  ]

  async function attach() {
    setBusy(true); setMsg(null)
    try {
      await api.attachCredentials(code, provider, values, hostSecret)
      setMsg({ type: "ok", text: `${provider}: attached & validated` })
      setValues({})
    } catch (e) { setMsg({ type: "bad", text: String(e) }) } finally { setBusy(false) }
  }

  return (
    <Modal open onClose={onClose} title={`Credentials — ${provider}`}>
      <p className="text-sm text-[var(--color-text-muted)] mb-2">
        Credentials are encrypted at rest and deleted when the session ends. Only you (the host) can attach.
      </p>
      {PROVIDER_LINKS[provider] && (
        <p className="text-sm mb-4">
          <a
            href={PROVIDER_LINKS[provider].url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[var(--color-accent)] hover:underline"
          >{PROVIDER_LINKS[provider].label} ↗</a>
        </p>
      )}

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
        {fields.length > 0 && (
          <Button onClick={attach} disabled={busy} className="w-full">
            {busy ? "validating..." : `Attach ${provider}`}
          </Button>
        )}
      </div>

      {msg && (
        <div className={`mt-4 p-3 rounded-lg text-sm ${msg.type === "ok" ? "bg-[var(--color-success)]/15 text-[var(--color-success)]" : "bg-[var(--color-danger)]/15 text-[var(--color-danger)]"}`}>
          {msg.text}
        </div>
      )}
    </Modal>
  )
}
