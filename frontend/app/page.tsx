import Link from "next/link";

const TASKS = [
  { id: "SGLB-01", name: "PDPA-Outcome", source: "PDPC enforcement decisions", metric: "macro-F1 (obligation), MAE (penalty band)", n: "~210" },
  { id: "SGLB-02", name: "Statute-QA", source: "SSO statutes", metric: "exact-match (citation), ROUGE-L (answer)", n: "~500" },
  { id: "SGLB-03", name: "Case-Holding", source: "eLitigation public judgments", metric: "exact-match on multiple-choice holding", n: "~300" },
  { id: "SGLB-04", name: "Citation-Verify", source: "SAL Style Guide + perturbations", metric: "accuracy + per-error-class breakdown", n: "~1000" },
  { id: "SGLB-05", name: "Employment-Issue", source: "MOM guidance + Employment Act", metric: "multi-label F1", n: "~150" },
  { id: "SGLB-06", name: "Rules-of-Court-2021", source: "Rules of Court 2021 (SSO)", metric: "exact-match (order:rule), top-3 accuracy", n: "~200" },
  { id: "SGLB-07", name: "Jurisdiction-Routing", source: "Curated SG cases citing UK/AU/HK precedent", metric: "accuracy", n: "~250" },
  { id: "SGLB-08", name: "Clause-Tone", source: "SG clause library + LLM-judge augmentation", metric: "macro-F1", n: "~400" },
];

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
              </tr>
            </thead>
            <tbody>
              {TASKS.map(t => (
                <tr key={t.id}>
                  <td style={td}><code>{t.id}</code></td>
                  <td style={td}>{t.name}</td>
                  <td style={td}>{t.source}</td>
                  <td style={td}>{t.n}</td>
                  <td style={td}>{t.metric}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section style={{ marginBottom: "1rem" }}>
        <h2 style={{ fontSize: "1.05rem", margin: "0 0 0.6rem 0", fontWeight: 600 }}>Status</h2>
        <p style={{ color: "#475569", fontSize: "0.9rem", margin: 0 }}>
          Pre-release. P0 pivot cleanup landed. Dataset ingestion (PDPC, SSO) and eval CLI in progress.
          Track issues on <a href="https://github.com/gongahkia/junas/issues" style={{ color: "#1d4ed8" }}>GitHub</a>.
        </p>
      </section>
    </main>
  );
}

const th: React.CSSProperties = { border: "1px solid #cbd5e1", padding: "0.45rem 0.6rem", textAlign: "left", fontWeight: 600 };
const td: React.CSSProperties = { border: "1px solid #e2e8f0", padding: "0.45rem 0.6rem", verticalAlign: "top" };
