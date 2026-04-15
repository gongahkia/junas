import { useEffect, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { api, ApiError } from "../api/client"
import type { ProviderDescriptor } from "../api/types"
import { Button, Card, Input, Label, Pill } from "../components/ui"
import { storage, type SessionMembership } from "../lib/storage"
import DynamicBackground from "../components/DynamicBackground"
import { FIELDS_BY_PROVIDER } from "../components/CredentialsModal"
import { PROVIDER_LINKS } from "../lib/providerLinks"

export function Home() {
  const navigate = useNavigate()
  const [providers, setProviders] = useState<ProviderDescriptor[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [creds, setCreds] = useState<Record<string, string>>({})
  const [name, setName] = useState("")

  const selectedDescriptor = providers.find((p) => p.key === selected) ?? null
  const needsCreds = !!selectedDescriptor?.requires_credentials
  const credFields = selected ? (FIELDS_BY_PROVIDER[selected] ?? [
    { key: "username", label: "Username" },
    { key: "password", label: "Password", type: "password" },
  ]) : []
  const credsComplete = !needsCreds || credFields.every((f) => (creds[f.key] ?? "").trim().length > 0)
  const [joinCode, setJoinCode] = useState("")
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [scrolled, setScrolled] = useState(false)
  const [recent, setRecent] = useState<SessionMembership[]>([])
  const appSectionRef = useRef<HTMLElement>(null)

  useEffect(() => {
    api.listProviders().then(setProviders).catch((e) => setErr(String(e)))
  }, [])

  useEffect(() => {
    let cancelled = false
    const probe = async () => {
      const all = storage.list()
      const checks = await Promise.all(all.map(async (m) => {
        try { await api.getSession(m.code); return m } // still open
        catch (e) {
          if (e instanceof ApiError && e.status === 404) { storage.remove(m.code); return null }
          return m // network/other error: keep entry
        }
      }))
      if (!cancelled) setRecent(checks.filter((x): x is SessionMembership => x !== null).slice(0, 5))
    }
    probe()
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    let ticking = false
    const onScroll = () => {
      if (ticking) return
      ticking = true
      requestAnimationFrame(() => {
        setScrolled((prev) => {
          const next = window.scrollY > 50
          return prev === next ? prev : next
        })
        ticking = false
      })
    }
    window.addEventListener("scroll", onScroll, { passive: true })
    return () => window.removeEventListener("scroll", onScroll)
  }, [])

  async function create() {
    if (!name.trim()) { setErr("display name required"); return }
    if (!selected) { setErr("pick a board"); return }
    if (needsCreds && !credsComplete) { setErr("credentials required for this board"); return }
    setBusy(true); setErr(null)
    let created: { code: string; host_participant_id: string; host_secret: string } | null = null
    try {
      created = await api.createSession(name.trim(), selected)
      if (needsCreds) {
        await api.attachCredentials(created.code, selected, creds, created.host_secret)
      }
      storage.save({
        code: created.code,
        participant_id: created.host_participant_id,
        ws_token: "",
        display_name: name.trim(),
        is_host: true,
        host_secret: created.host_secret,
        joined_at: new Date().toISOString(),
      })
      navigate(`/s/${created.code}`)
    } catch (e) {
      setErr(String(e))
      if (created && needsCreds) { // attach failed — tear down to let user retry cleanly
        try { await api.endSession(created.code, created.host_secret) } catch { /* best effort */ }
      }
    } finally { setBusy(false) }
  }

  const scrollToApp = () => appSectionRef.current?.scrollIntoView({ behavior: "smooth" })

  return (
    <div className="relative min-h-screen">
      <div className="fixed inset-0 z-0">
        <DynamicBackground />
        <div className="absolute inset-0 bg-white/60" />
      </div>

      <header
        className={`fixed top-0 left-0 right-0 z-20 transition-all duration-300 ${
          scrolled ? "bg-white/80 backdrop-blur border-b border-[var(--color-border)] py-2" : "bg-transparent py-4"
        }`}
      >
        <div className="container mx-auto px-6 flex items-center justify-between">
          <h1 className="text-xl font-bold text-[var(--color-text)] tracking-tight">Kilter Together</h1>
        </div>
      </header>

      <main className="relative z-10">
        <section className="min-h-screen flex flex-col items-center justify-center text-[var(--color-text)] px-4">
          <h2 className="text-5xl md:text-7xl font-bold text-center mb-4 tracking-tight">Climb together.</h2>
          <p className="text-lg md:text-2xl text-center mb-10 max-w-2xl text-[var(--color-text-muted)]">
            Start a session, queue climbs from any supported board, vote with friends, and run the wall together — in real time.
          </p>
          <button
            onClick={scrollToApp}
            className="animate-bounce rounded-full border border-[var(--color-border)] bg-white/70 backdrop-blur px-5 py-2 text-sm text-[var(--color-text)] hover:bg-white transition"
            aria-label="Scroll to app"
          >
            ↓ get climbing
          </button>
        </section>

        <section ref={appSectionRef} className="py-20 px-4">
          <div className="max-w-5xl mx-auto">
            <div className="grid md:grid-cols-2 gap-6">
              <Card className="p-6 backdrop-blur bg-[var(--color-surface)]/85">
                <h2 className="text-lg font-semibold mb-1">Start a new session</h2>
                <p className="text-sm text-[var(--color-text-muted)] mb-5">As host you control providers, queue, and finalists.</p>
                <Label>Your display name</Label>
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Alex" />

                <div className="mt-5">
                  <Label>Pick a board</Label>
                  <div role="radiogroup" className="flex gap-2 overflow-x-auto pb-2 -mx-1 px-1 snap-x">
                    {providers.map((p) => {
                      const dotClass =
                        p.status === "ok" ? "bg-[var(--color-success)]"
                        : p.status === "experimental" ? "bg-[var(--color-accent-2)]"
                        : "bg-[var(--color-danger)]"
                      const isSel = selected === p.key
                      const link = PROVIDER_LINKS[p.key]
                      return (
                        <div
                          key={p.key}
                          className={`shrink-0 snap-start inline-flex items-center gap-1.5 rounded-full border text-sm transition ${
                            isSel
                              ? "border-[var(--color-accent)] bg-[var(--color-accent)]/15"
                              : "border-[var(--color-border)] bg-[var(--color-surface-2)] hover:bg-[var(--color-surface)]"
                          }`}
                        >
                          <button
                            type="button"
                            role="radio"
                            aria-checked={isSel}
                            onClick={() => { setSelected(p.key); setCreds({}); setErr(null) }}
                            className="inline-flex items-center gap-2 pl-3 pr-1 py-2 text-[var(--color-text)]"
                            title={`${p.status}${p.requires_credentials ? " · needs credentials" : ""}`}
                          >
                            <span className={`inline-block w-2 h-2 rounded-full ${dotClass}`} aria-hidden />
                            <span className="font-medium whitespace-nowrap">{p.name}</span>
                            {p.requires_credentials && (
                              <span className="text-[10px] uppercase tracking-wide text-[var(--color-text-muted)]">creds</span>
                            )}
                          </button>
                          {link && (
                            <a
                              href={link.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              title={`Open ${link.label}`}
                              aria-label={`Open ${p.name} site in new tab`}
                              className="pr-2.5 py-2 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                            >↗</a>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>

                {needsCreds && credFields.length > 0 && (
                  <div className="mt-5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)]/50 p-4">
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <Label>Credentials for {selectedDescriptor?.name}</Label>
                      {selected && PROVIDER_LINKS[selected] && (
                        <a
                          href={PROVIDER_LINKS[selected].url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-[var(--color-accent)] hover:underline shrink-0"
                        >{PROVIDER_LINKS[selected].label} ↗</a>
                      )}
                    </div>
                    <p className="text-xs text-[var(--color-text-muted)] mb-3">
                      Needed to fetch climbs. Encrypted at rest, deleted when the session ends.
                    </p>
                    <div className="space-y-3">
                      {credFields.map((f) => (
                        <div key={f.key}>
                          <Label>{f.label}</Label>
                          <Input
                            type={f.type ?? "text"}
                            placeholder={f.placeholder}
                            value={creds[f.key] ?? ""}
                            onChange={(e) => setCreds({ ...creds, [f.key]: e.target.value })}
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <Button
                  className="mt-6 w-full"
                  onClick={create}
                  disabled={busy || !selected || !name.trim() || (needsCreds && !credsComplete)}
                >
                  {busy ? (needsCreds ? "validating..." : "creating...") : "Create session →"}
                </Button>
              </Card>

              <Card className="p-6 backdrop-blur bg-[var(--color-surface)]/85">
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
          </div>
        </section>
      </main>

      <footer className="relative z-10 bg-white/80 backdrop-blur border-t border-[var(--color-border)] py-4">
        <div className="container mx-auto px-4 text-center">
          <p className="text-xs text-[var(--color-text-muted)]">© {new Date().getFullYear()} Kilter Together</p>
        </div>
      </footer>
    </div>
  )
}
