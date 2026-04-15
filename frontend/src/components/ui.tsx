import type { ComponentPropsWithoutRef, ReactNode } from "react"

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger"

export function Button({
  variant = "primary",
  className = "",
  ...rest
}: ComponentPropsWithoutRef<"button"> & { variant?: ButtonVariant }) {
  const base = "inline-flex items-center justify-center rounded-lg px-4 py-2 font-medium transition disabled:opacity-50 disabled:cursor-not-allowed"
  const variants: Record<ButtonVariant, string> = {
    primary: "bg-[var(--color-accent)] text-black hover:bg-[var(--color-accent-2)]",
    secondary: "bg-[var(--color-surface-2)] text-[var(--color-text)] border border-[var(--color-border)] hover:bg-[var(--color-surface)]",
    ghost: "text-[var(--color-text-muted)] hover:text-[var(--color-text)]",
    danger: "bg-[var(--color-danger)] text-white hover:opacity-90",
  }
  return <button {...rest} className={`${base} ${variants[variant]} ${className}`} />
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`bg-[var(--color-surface)] border border-[var(--color-border)] rounded-2xl ${className}`}>
      {children}
    </div>
  )
}

export function Input(props: ComponentPropsWithoutRef<"input">) {
  return (
    <input
      {...props}
      className={`w-full bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-lg px-3 py-2 text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)] ${props.className ?? ""}`}
    />
  )
}

export function Label({ children, htmlFor }: { children: ReactNode; htmlFor?: string }) {
  return <label htmlFor={htmlFor} className="block text-xs uppercase tracking-wider text-[var(--color-text-muted)] mb-1.5">{children}</label>
}

export function Pill({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "ok" | "warn" | "bad" }) {
  const tones = {
    neutral: "bg-[var(--color-surface-2)] text-[var(--color-text-muted)]",
    ok: "bg-[var(--color-success)]/15 text-[var(--color-success)]",
    warn: "bg-[var(--color-accent-2)]/15 text-[var(--color-accent-2)]",
    bad: "bg-[var(--color-danger)]/15 text-[var(--color-danger)]",
  }
  return <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${tones[tone]}`}>{children}</span>
}

export function Modal({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm" onClick={onClose}>
      <Card className="w-full max-w-lg max-h-[90vh] overflow-auto" >
        <div className="p-6" onClick={(e) => e.stopPropagation()}>
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold text-[var(--color-text)]">{title}</h2>
            <Button variant="ghost" onClick={onClose}>✕</Button>
          </div>
          {children}
        </div>
      </Card>
    </div>
  )
}

export function PageShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-full">
      <header className="border-b border-[var(--color-border)] px-6 py-4 flex items-center justify-between">
        <a href="/" className="text-lg font-semibold tracking-tight">Kilter Together</a>
      </header>
      <main className="max-w-5xl mx-auto p-6">{children}</main>
    </div>
  )
}
