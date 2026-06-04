import Link from "next/link";

type TaskStatus = "shipped" | "code-shipped" | "in-progress" | "queued" | "deferred";

interface TaskRow {
  id: string;
  name: string;
  source: string;
  n: string;
  metric: string;
  status: TaskStatus;
  note?: string;
}

const TASKS: TaskRow[] = [
  { id: "SGLB-01", name: "PDPA-Outcome", source: "PDPC enforcement decisions", metric: "multi-label F1 (obligation) + ordinal MAE (penalty band)", n: "211", status: "shipped" },
  { id: "SGLB-02", name: "Statute-QA", source: "SSO statutes (PDPA seed)", metric: "exact-match (citation) + ROUGE-L (answer)", n: "78", status: "shipped", note: "PDPA-only v0.1; expansion to EmA/PC/ROC pending live ingest" },
  { id: "SGLB-03", name: "Case-Holding", source: "eLitigation public judgments", metric: "exact-match on MCQ holding", n: "—", status: "deferred", note: "TOS-deferred; will reopen with CommonLII fallback in v0.2" },
  { id: "SGLB-04", name: "Citation-Verify", source: "SAL Style Guide + perturbations", metric: "multi-label F1 (valid/invalid)", n: "30 (smoke)", status: "shipped", note: "Smoke level; ~1000-case production set pending" },
  { id: "SGLB-05", name: "Employment-Issue", source: "MOM guidance + Employment Act", metric: "multi-label F1", n: "—", status: "code-shipped", note: "Builder + scorer + runner ready; data pending MOM scraper (#59)" },
  { id: "SGLB-06", name: "Rules-of-Court-2021", source: "Rules of Court 2021 (SSO)", metric: "label F1 + top-3 accuracy", n: "—", status: "code-shipped", note: "Builder + scorers ready; data pending make ingest-sso SSO_CODE=ROC2021" },
  { id: "SGLB-07", name: "Jurisdiction-Routing", source: "CommonLII SG judgments", metric: "accuracy", n: "—", status: "code-shipped", note: "Builder + scorer + runner ready; data pending CommonLII ingester (#34)" },
  { id: "SGLB-08", name: "Clause-Tone", source: "SG clause library + LLM-judge augmentation", metric: "macro-F1", n: "400 (gen)", status: "in-progress", note: "Synthetic candidates generating; human review gate before promote" },
];

const STATUS_STYLES: Record<TaskStatus, { label: string; bg: string; fg: string }> = {
  "shipped":      { label: "shipped",      bg: "#dcfce7", fg: "#166534" },
  "code-shipped": { label: "code shipped", bg: "#dbeafe", fg: "#1e40af" },
  "in-progress":  { label: "in progress",  bg: "#fef3c7", fg: "#92400e" },
  "queued":       { label: "queued",       bg: "#f1f5f9", fg: "#475569" },
  "deferred":     { label: "deferred",     bg: "#fce7f3", fg: "#9d174d" },
};

export default function LandingPage() {
  return (
    <main style={{ maxWidth: "920px", margin: "0 auto", padding: "2rem 1.25rem", fontFamily: "system-ui, -apple-system, sans-serif" }}>
      <header style={{ marginBottom: "2rem" }}>
        <div style={{ display: "inline-block", fontSize: "0.7rem", letterSpacing: "0.12em", textTransform: "uppercase", color: "#64748b", marginBottom: "0.5rem" }}>SG-LegalBench v0.1 (pre-release)</div>
        <h1 style={{ fontSize: "1.75rem", lineHeight: 1.25, margin: "0 0 0.6rem 0", fontWeight: 600 }}>The first open benchmark for Singapore legal reasoning in LLMs, with a reproducible reference implementation.</h1>
        <p style={{ color: "#475569", fontSize: "0.95rem", margin: 0 }}>
          Eight tasks grounded in public-domain SG sources (PDPC, SSO, MOM, Rules of Court 2021). Mechanical label extraction from regulator outputs. Baselines across frontier and open-weight LLMs. AGPL/MIT licensing; CC-BY data.
        </p>
        <div style={{ display: "flex", gap: "0.6rem", marginTop: "1.1rem", flexWrap: "wrap" }}>
          <Link href="/benchmarks" style={{ background: "#0f172a", color: "#f8fafc", padding: "0.55rem 0.9rem", borderRadius: "0.4rem", textDecoration: "none", fontSize: "0.85rem" }}>View tasks &amp; leaderboard</Link>
          <Link href="/chat" style={{ border: "1px solid #cbd5e1", color: "#0f172a", padding: "0.55rem 0.9rem", borderRadius: "0.4rem", textDecoration: "none", fontSize: "0.85rem" }}>Try the reference copilot</Link>
          <a href="https://github.com/gongahkia/junas" style={{ border: "1px solid #cbd5e1", color: "#0f172a", padding: "0.55rem 0.9rem", borderRadius: "0.4rem", textDecoration: "none", fontSize: "0.85rem" }}>GitHub</a>
        </div>
      </header>

      <section style={{ marginBottom: "2rem" }}>
        <h2 style={{ fontSize: "1.05rem", margin: "0 0 0.6rem 0", fontWeight: 600 }}>Why this exists</h2>
        <p style={{ color: "#475569", fontSize: "0.9rem", margin: "0 0 0.4rem 0" }}>
          LegalBench (Stanford) is US-focused. LexGLUE covers US/EU. LawBench targets Chinese law. No public benchmark exists for Singapore legal reasoning despite a distinctive common-law system (PDPA, Rules of Court 2021, SAL citation, SG corpus).
        </p>
        <p style={{ color: "#475569", fontSize: "0.9rem", margin: 0 }}>
          We make no legal interpretive claims. We mechanically reformulate published regulator and court outputs as evaluation tasks.
        </p>
      </section>

      <section style={{ marginBottom: "2rem" }}>
        <h2 style={{ fontSize: "1.05rem", margin: "0 0 0.6rem 0", fontWeight: 600 }}>Tasks (v0.1 spec)</h2>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
            <thead>
              <tr style={{ background: "#f1f5f9" }}>
                <th style={th}>ID</th>
                <th style={th}>Task</th>
                <th style={th}>Source</th>
                <th style={th}>N</th>
                <th style={th}>Metric</th>
                <th style={th}>Status</th>
              </tr>
            </thead>
            <tbody>
              {TASKS.map(t => {
                const s = STATUS_STYLES[t.status];
                return (
                  <tr key={t.id}>
                    <td style={td}><code>{t.id}</code></td>
                    <td style={td}>
                      <div>{t.name}</div>
                      {t.note && <div style={noteStyle}>{t.note}</div>}
                    </td>
                    <td style={td}>{t.source}</td>
                    <td style={td}>{t.n}</td>
                    <td style={td}>{t.metric}</td>
                    <td style={td}>
                      <span style={{ background: s.bg, color: s.fg, padding: "0.15rem 0.45rem", borderRadius: "0.3rem", fontSize: "0.7rem", fontWeight: 600, whiteSpace: "nowrap" }}>{s.label}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section style={{ marginBottom: "1rem" }}>
        <h2 style={{ fontSize: "1.05rem", margin: "0 0 0.6rem 0", fontWeight: 600 }}>Status</h2>
        <p style={{ color: "#475569", fontSize: "0.9rem", margin: 0 }}>
          Pre-release. 3 of 8 v0.1 tasks shipped with data (SGLB-01/02/04); 3 code-shipped pending data ingest (SGLB-05/06/07); 1 generating synthetic candidates (SGLB-08); 1 TOS-deferred to v0.2 (SGLB-03). Track issues on <a href="https://github.com/gongahkia/junas/issues" style={{ color: "#1d4ed8" }}>GitHub</a>.
        </p>
      </section>
    </main>
  );
}

const th: React.CSSProperties = { border: "1px solid #cbd5e1", padding: "0.45rem 0.6rem", textAlign: "left", fontWeight: 600 };
const td: React.CSSProperties = { border: "1px solid #e2e8f0", padding: "0.45rem 0.6rem", verticalAlign: "top" };
const noteStyle: React.CSSProperties = { color: "#94a3b8", fontSize: "0.72rem", marginTop: "0.15rem", fontStyle: "italic" };
