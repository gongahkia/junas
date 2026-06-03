import Link from "next/link";
import {
  getBenchmarkLeaderboard,
  listBenchmarkEvaluators,
  listBenchmarkTasks,
} from "../../lib/api-server";

type TaskInfo = { name: string };
type EvaluatorInfo = { name: string; strength: "strong" | "weak" };
type LeaderboardEntry = {
  run_id: string;
  workflow: string;
  dataset: string;
  finished_at: string;
  total_cases: number;
  per_evaluator_mean: Record<string, number>;
  strict: boolean;
};
type LeaderboardResponse = {
  entries: LeaderboardEntry[];
  aggregated_per_workflow: Record<string, Record<string, number>>;
};

type TaskSpec = {
  id: string;
  workflow: string;
  name: string;
  source: string;
  format: string;
  metric: string;
  n: string;
  status: "spec" | "dataset" | "baseline" | "published";
  description: string;
};

const TASKS: TaskSpec[] = [
  { id: "SGLB-01", workflow: "sglb_01", name: "PDPA-Outcome", source: "PDPC enforcement decisions", format: "facts → obligation breached + penalty band", metric: "macro-F1, MAE", n: "~210", status: "spec", description: "Predict the PDPA obligation breached and a penalty log-band from a redacted enforcement decision summary." },
  { id: "SGLB-02", workflow: "sglb_02", name: "Statute-QA", source: "SSO statutes", format: "question grounded in section → answer + citation", metric: "exact-match (citation), ROUGE-L", n: "~500", status: "spec", description: "Answer a question about a SG statute and cite the correct section." },
  { id: "SGLB-03", workflow: "sglb_03", name: "Case-Holding", source: "eLitigation public judgments (TOS-gated)", format: "facts + question → holding (MCQ)", metric: "exact-match", n: "~300", status: "spec", description: "Select the correct holding for an SG case among distractors. Requires eLitigation TOS pass." },
  { id: "SGLB-04", workflow: "sglb_04", name: "Citation-Verify", source: "SAL Style Guide grammar + perturbations", format: "input string → valid SAL citation?", metric: "multi-label F1, per-error breakdown", n: "30 (smoke)", status: "dataset", description: "Verify whether an SG legal citation conforms to the SAL Style Guide. v0.1 smoke dataset shipped; production dataset coming." },
  { id: "SGLB-05", workflow: "sglb_05", name: "Employment-Issue", source: "MOM published guidance + Employment Act", format: "scenario → list of EA issues", metric: "multi-label F1", n: "~150", status: "spec", description: "Multi-label classification of which Employment Act issues a scenario triggers." },
  { id: "SGLB-06", workflow: "sglb_06", name: "Rules-of-Court-2021", source: "Rules of Court 2021 (SSO)", format: "scenario → applicable Order + Rule", metric: "exact-match (order:rule), top-3 acc", n: "~200", status: "spec", description: "Identify the ROC 2021 Order and Rule that govern a procedural scenario." },
  { id: "SGLB-07", workflow: "sglb_07", name: "Jurisdiction-Routing", source: "Curated SG cases citing UK/AU/HK precedent", format: "question → SG / UK persuasive / AU persuasive / N/A", metric: "accuracy", n: "~250", status: "spec", description: "Classify the source-jurisdiction of the controlling authority for an SG legal question." },
  { id: "SGLB-08", workflow: "sglb_08", name: "Clause-Tone", source: "Junas SG clause library + LLM-judge augmentation", format: "clause text → standard / aggressive / balanced / protective", metric: "macro-F1", n: "~400", status: "spec", description: "Classify the negotiation tone of a contractual clause." },
  { id: "SGLB-09", workflow: "sglb_09", name: "Summary-Faithfulness", source: "SG judgments + PDPC + MOM", format: "summary → atomic facts → source-grounded support", metric: "FActScore, hallucination rate", n: "~160 sources", status: "spec", description: "Atomic-fact precision of summaries against the source document." },
  { id: "SGLB-10", workflow: "sglb_10", name: "Citation-Generation", source: "SG judgments w/ explicit controlling-authority", format: "fact pattern → controlling SG citation", metric: "top-1, top-3 hit rate", n: "~300", status: "spec", description: "Predict the controlling SG authority for a fact pattern." },
  { id: "SGLB-11", workflow: "sglb_11", name: "Citation-Hallucination", source: "Synthesised passages w/ injected fake citations", format: "passage → list of fabricated citations", metric: "per-perturbation P/R/F1", n: "~500 passages", status: "spec", description: "Detect fabricated SG citations among real ones." },
  { id: "SGLB-12", workflow: "sglb_12", name: "Multi-Issue-Spotting", source: "Composed PDPA + EA + ROC scenarios", format: "fact pattern → set of issue labels", metric: "macro-F1, exact-set-match", n: "~150", status: "spec", description: "Multi-source issue spotting across PDPA + EA + ROC 2021." },
  { id: "SGLB-13", workflow: "sglb_13", name: "Counterfactual-Outcome", source: "PDPC decisions w/ minimal-pair fact perturbations", format: "pair (A, B) → same / different outcome", metric: "paired accuracy", n: "~150 pairs", status: "spec", description: "Counterfactual reasoning over PDPC outcomes." },
  { id: "SGLB-14", workflow: "sglb_14", name: "Statutory-Entailment", source: "PDPC + MOM regulator-stated worked examples", format: "(scenario, clause) → entails / contradicts / neutral", metric: "3-class accuracy", n: "~250", status: "spec", description: "Statutory entailment grounded in regulator worked examples." },
  { id: "SGLB-15", workflow: "sglb_15", name: "Draft-Constraint-Sat", source: "SG drafting briefs + verifiable constraints", format: "drafted document scored against IFEval-style constraints", metric: "per-constraint pass rate, all-pass", n: "~300 briefs", status: "spec", description: "Verifiable constraint satisfaction on SG-context drafting." },
  { id: "SGLB-16", workflow: "sglb_16", name: "Review-Redflag-Recall", source: "SG-context contracts w/ planted defects", format: "contract → list of (excerpt, defect_class)", metric: "per-class recall, IoU localisation", n: "~80 contracts", status: "spec", description: "Planted-defect detection on SG contracts." },
];

const STATUS_LABELS: Record<TaskSpec["status"], string> = {
  spec: "Spec only",
  dataset: "Dataset drafted",
  baseline: "Baselines running",
  published: "Published",
};

const STATUS_COLORS: Record<TaskSpec["status"], string> = {
  spec: "#fef3c7",
  dataset: "#dbeafe",
  baseline: "#fae8ff",
  published: "#d1fae5",
};

function formatScore(value: number): string {
  if (!Number.isFinite(value)) return "—";
  return value.toFixed(3);
}

function formatDate(iso: string): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toISOString().replace("T", " ").slice(0, 19) + " UTC";
  } catch {
    return iso;
  }
}

export const dynamic = "force-dynamic";

export default async function BenchmarksLanding() {
  const [tasks, evaluators, leaderboard]: [
    TaskInfo[],
    EvaluatorInfo[],
    LeaderboardResponse,
  ] = await Promise.all([
    listBenchmarkTasks(),
    listBenchmarkEvaluators(),
    getBenchmarkLeaderboard(),
  ]);

  const registeredWorkflows = new Set(tasks.map((t) => t.name));
  const evaluatorNames = Array.from(
    new Set(leaderboard.entries.flatMap((e) => Object.keys(e.per_evaluator_mean))),
  ).sort();

  return (
    <main style={{ maxWidth: "960px", margin: "0 auto", padding: "2rem 1.25rem", fontFamily: "system-ui, -apple-system, sans-serif" }}>
      <Link href="/" style={{ fontSize: "0.8rem", color: "#64748b", textDecoration: "none" }}>&larr; Back</Link>
      <h1 style={{ fontSize: "1.5rem", margin: "0.6rem 0 0.5rem 0", fontWeight: 600 }}>SG-LegalBench Tasks &amp; Leaderboard</h1>
      <p style={{ color: "#475569", fontSize: "0.9rem", margin: "0 0 1.5rem 0" }}>
        Sixteen tasks across nine capability surfaces (see <a href="https://github.com/gongahkia/junas/blob/main/docs/coverage-matrix.md" style={{ color: "#1d4ed8" }}>coverage matrix</a>).
        Labels are mechanically extracted from public-domain regulator and court outputs.
      </p>

      <section style={{ marginBottom: "2rem" }}>
        <h2 style={{ fontSize: "1.05rem", fontWeight: 600, margin: "0 0 0.5rem 0" }}>Leaderboard</h2>
        {leaderboard.entries.length === 0 ? (
          <p style={{ color: "#64748b", fontSize: "0.85rem", margin: 0 }}>
            No runs yet. Start one with <code>make eval WORKFLOW=sglb_04 DATASET=benchmark/datasets/sglb_04_citation_verify.yaml EVALUATORS=&quot;multi_label_f1&quot;</code> or <code>POST /api/v1/benchmarks/run</code>.
          </p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem" }}>
              <thead>
                <tr style={{ background: "#f1f5f9" }}>
                  <th style={th}>Run</th>
                  <th style={th}>Workflow</th>
                  <th style={th}>Cases</th>
                  <th style={th}>Strict</th>
                  {evaluatorNames.map((ev) => (
                    <th key={ev} style={th}>{ev}</th>
                  ))}
                  <th style={th}>Finished</th>
                </tr>
              </thead>
              <tbody>
                {leaderboard.entries.map((entry) => (
                  <tr key={entry.run_id}>
                    <td style={td}><code>{entry.run_id}</code></td>
                    <td style={td}>{entry.workflow}</td>
                    <td style={td}>{entry.total_cases}</td>
                    <td style={td}>{entry.strict ? "yes" : "no"}</td>
                    {evaluatorNames.map((ev) => (
                      <td key={ev} style={td}>{formatScore(entry.per_evaluator_mean[ev] ?? Number.NaN)}</td>
                    ))}
                    <td style={td}>{formatDate(entry.finished_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {Object.keys(leaderboard.aggregated_per_workflow).length > 0 && (
          <details style={{ marginTop: "0.75rem" }}>
            <summary style={{ fontSize: "0.8rem", color: "#475569", cursor: "pointer" }}>Per-workflow mean across all runs</summary>
            <pre style={{ fontSize: "0.75rem", background: "#f8fafc", padding: "0.5rem", borderRadius: "0.25rem", overflowX: "auto" }}>
              {JSON.stringify(leaderboard.aggregated_per_workflow, null, 2)}
            </pre>
          </details>
        )}
      </section>

      <section style={{ marginBottom: "2rem" }}>
        <h2 style={{ fontSize: "1.05rem", fontWeight: 600, margin: "0 0 0.5rem 0" }}>Tasks</h2>
        <p style={{ color: "#64748b", fontSize: "0.8rem", margin: "0 0 0.75rem 0" }}>
          {tasks.length} task(s) registered with the harness; {evaluators.length} evaluator(s) available.
        </p>
        <div style={{ display: "grid", gap: "0.75rem" }}>
          {TASKS.map((t) => {
            const registered = registeredWorkflows.has(t.workflow);
            return (
              <div key={t.id} style={{ border: "1px solid #e2e8f0", borderRadius: "0.5rem", padding: "0.85rem 1rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: "0.6rem", flexWrap: "wrap" }}>
                  <div>
                    <code style={{ fontSize: "0.78rem", color: "#64748b" }}>{t.id}</code>
                    <span style={{ marginLeft: "0.5rem", fontWeight: 600 }}>{t.name}</span>
                    {registered && (
                      <span style={{ marginLeft: "0.5rem", fontSize: "0.7rem", padding: "0.1rem 0.35rem", borderRadius: "0.25rem", background: "#dcfce7", color: "#166534" }}>
                        registered
                      </span>
                    )}
                  </div>
                  <span style={{ fontSize: "0.7rem", padding: "0.15rem 0.45rem", borderRadius: "0.25rem", background: STATUS_COLORS[t.status], color: "#0f172a" }}>{STATUS_LABELS[t.status]}</span>
                </div>
                <p style={{ color: "#334155", fontSize: "0.85rem", margin: "0.4rem 0 0.5rem 0" }}>{t.description}</p>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "0.4rem", fontSize: "0.75rem", color: "#475569" }}>
                  <div><strong>Source:</strong> {t.source}</div>
                  <div><strong>Format:</strong> {t.format}</div>
                  <div><strong>Metric:</strong> {t.metric}</div>
                  <div><strong>N:</strong> {t.n}</div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section style={{ marginBottom: "1rem" }}>
        <h2 style={{ fontSize: "1.05rem", fontWeight: 600, margin: "0 0 0.5rem 0" }}>Available evaluators</h2>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
          {evaluators.map((e) => (
            <span key={e.name} style={{ fontSize: "0.72rem", padding: "0.2rem 0.5rem", borderRadius: "0.25rem", background: e.strength === "strong" ? "#dcfce7" : "#fee2e2", color: "#0f172a" }}>
              {e.name} [{e.strength}]
            </span>
          ))}
        </div>
        <p style={{ color: "#64748b", fontSize: "0.75rem", margin: "0.6rem 0 0 0" }}>
          Weak evaluators are rejected in publication mode (<code>strict: true</code>); see <a href="https://github.com/gongahkia/junas/blob/main/docs/coverage-matrix.md" style={{ color: "#1d4ed8" }}>coverage matrix §4.2</a>.
        </p>
      </section>
    </main>
  );
}

const th: React.CSSProperties = { border: "1px solid #cbd5e1", padding: "0.45rem 0.6rem", textAlign: "left", fontWeight: 600 };
const td: React.CSSProperties = { border: "1px solid #e2e8f0", padding: "0.45rem 0.6rem", verticalAlign: "top" };
