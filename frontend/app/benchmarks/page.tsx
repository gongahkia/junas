import Link from "next/link";

type Task = {
  id: string;
  name: string;
  source: string;
  format: string;
  metric: string;
  n: string;
  status: "spec" | "data" | "baseline" | "published";
  description: string;
};

const TASKS: Task[] = [
  { id: "SGLB-01", name: "PDPA-Outcome", source: "PDPC enforcement decisions", format: "facts → obligation breached + penalty band", metric: "macro-F1, MAE", n: "~210", status: "spec", description: "Predict the PDPA obligation breached and a penalty log-band from a redacted enforcement decision summary." },
  { id: "SGLB-02", name: "Statute-QA", source: "SSO statutes", format: "question grounded in section → answer + citation", metric: "exact-match (citation), ROUGE-L", n: "~500", status: "spec", description: "Answer a question about a SG statute and cite the correct section." },
  { id: "SGLB-03", name: "Case-Holding", source: "eLitigation public judgments (TOS-gated)", format: "facts + question → holding (MCQ)", metric: "exact-match", n: "~300", status: "spec", description: "Select the correct holding for a SG case among distractors. Requires eLitigation TOS pass." },
  { id: "SGLB-04", name: "Citation-Verify", source: "SAL Style Guide grammar + perturbations", format: "input string → valid SAL citation?", metric: "accuracy + per-error breakdown", n: "~1000", status: "spec", description: "Verify whether an SG legal citation conforms to the SAL Style Guide." },
  { id: "SGLB-05", name: "Employment-Issue", source: "MOM published guidance + Employment Act", format: "scenario → list of EA issues", metric: "multi-label F1", n: "~150", status: "spec", description: "Multi-label classification of which Employment Act issues a scenario triggers." },
  { id: "SGLB-06", name: "Rules-of-Court-2021", source: "Rules of Court 2021 (SSO)", format: "scenario → applicable Order + Rule", metric: "exact-match (order:rule), top-3 acc", n: "~200", status: "spec", description: "Identify the ROC 2021 Order and Rule that govern a procedural scenario." },
  { id: "SGLB-07", name: "Jurisdiction-Routing", source: "Curated SG cases citing UK/AU/HK precedent", format: "question → SG / UK persuasive / AU persuasive / N/A", metric: "accuracy", n: "~250", status: "spec", description: "Classify the source-jurisdiction of the controlling authority for an SG legal question." },
  { id: "SGLB-08", name: "Clause-Tone", source: "Junas SG clause library + LLM-judge augmentation", format: "clause text → standard / aggressive / balanced / protective", metric: "macro-F1", n: "~400", status: "spec", description: "Classify the negotiation tone of a contractual clause." },
];

const STATUS_LABELS: Record<Task["status"], string> = {
  spec: "Spec only",
  data: "Dataset drafted",
  baseline: "Baselines running",
  published: "Published",
};

const STATUS_COLORS: Record<Task["status"], string> = {
  spec: "#fef3c7",
  data: "#dbeafe",
  baseline: "#fae8ff",
  published: "#d1fae5",
};

export default function BenchmarksLanding() {
  return (
    <main style={{ maxWidth: "920px", margin: "0 auto", padding: "2rem 1.25rem", fontFamily: "system-ui, -apple-system, sans-serif" }}>
      <Link href="/" style={{ fontSize: "0.8rem", color: "#64748b", textDecoration: "none" }}>&larr; Back</Link>
      <h1 style={{ fontSize: "1.5rem", margin: "0.6rem 0 0.5rem 0", fontWeight: 600 }}>SG-LegalBench Tasks</h1>
      <p style={{ color: "#475569", fontSize: "0.9rem", margin: "0 0 1.5rem 0" }}>
        Eight tasks in v0.1. All grounded in public-domain SG regulator and court outputs.
        Labels are mechanically extracted, not authored.
      </p>

      <div style={{ display: "grid", gap: "0.75rem" }}>
        {TASKS.map(t => (
          <div key={t.id} style={{ border: "1px solid #e2e8f0", borderRadius: "0.5rem", padding: "0.85rem 1rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: "0.6rem", flexWrap: "wrap" }}>
              <div>
                <code style={{ fontSize: "0.78rem", color: "#64748b" }}>{t.id}</code>
                <span style={{ marginLeft: "0.5rem", fontWeight: 600 }}>{t.name}</span>
              </div>
              <span style={{ fontSize: "0.7rem", padding: "0.15rem 0.45rem", borderRadius: "0.25rem", background: STATUS_COLORS[t.status], color: "#0f172a" }}>{STATUS_LABELS[t.status]}</span>
            </div>
            <p style={{ color: "#334155", fontSize: "0.85rem", margin: "0.4rem 0 0.5rem 0" }}>{t.description}</p>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "0.5rem", fontSize: "0.75rem", color: "#475569" }}>
              <div><strong>Source:</strong> {t.source}</div>
              <div><strong>Format:</strong> {t.format}</div>
              <div><strong>Metric:</strong> {t.metric}</div>
              <div><strong>N:</strong> {t.n}</div>
            </div>
          </div>
        ))}
      </div>

      <section style={{ marginTop: "2rem" }}>
        <h2 style={{ fontSize: "1rem", fontWeight: 600, margin: "0 0 0.5rem 0" }}>Leaderboard</h2>
        <p style={{ color: "#64748b", fontSize: "0.85rem", margin: 0 }}>
          Coming with v0.1 baseline run (GPT-5, Claude 4.x, Gemini 2.x, open-weight baseline). See <a href="https://github.com/gongahkia/junas/issues/36" style={{ color: "#1d4ed8" }}>issue #36</a>.
        </p>
      </section>
    </main>
  );
}
