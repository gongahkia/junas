import Link from "next/link";
import {
  getBenchmarkLeaderboard,
  listBenchmarkEvaluators,
  listBenchmarkTasks,
} from "../../lib/api-server";

type TaskInfo = { name: string };
type EvaluatorInfo = { name: string; strength: "strong" | "weak" };
type DataTier = "regulator" | "synthetic" | "mixed";
type LeaderboardEntry = {
  run_id: string;
  workflow: string;
  dataset: string;
  finished_at: string;
  total_cases: number;
  per_evaluator_mean: Record<string, number>;
  strict: boolean;
  data_tier?: DataTier;
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
  tier: DataTier;
  description: string;
};

const TASKS: TaskSpec[] = [
  { id: "SGLB-01", workflow: "sglb_01", name: "PDPA-Outcome", source: "PDPC enforcement decisions", format: "facts → obligation breached + penalty band", metric: "macro-F1, MAE", n: "~210", status: "spec", tier: "regulator", description: "Predict the PDPA obligation breached and a penalty log-band from a redacted enforcement decision summary." },
  { id: "SGLB-02", workflow: "sglb_02", name: "Statute-QA", source: "SSO statutes", format: "question grounded in section → answer + citation", metric: "exact-match (citation), ROUGE-L", n: "~500", status: "spec", tier: "regulator", description: "Answer a question about a SG statute and cite the correct section." },
  { id: "SGLB-03", workflow: "sglb_03", name: "Case-Holding", source: "eLitigation public judgments (TOS-gated)", format: "facts + question → holding (MCQ)", metric: "exact-match", n: "~300", status: "spec", tier: "regulator", description: "Select the correct holding for an SG case among distractors. Requires eLitigation TOS pass." },
  { id: "SGLB-04", workflow: "sglb_04", name: "Citation-Verify", source: "SAL Style Guide grammar + perturbations", format: "input string → valid SAL citation?", metric: "multi-label F1, per-error breakdown", n: "30 (smoke)", status: "dataset", tier: "regulator", description: "Verify whether an SG legal citation conforms to the SAL Style Guide. v0.1 smoke dataset shipped; production dataset coming." },
  { id: "SGLB-05", workflow: "sglb_05", name: "Employment-Issue", source: "MOM published guidance + Employment Act", format: "scenario → list of EA issues", metric: "multi-label F1", n: "~150", status: "spec", tier: "regulator", description: "Multi-label classification of which Employment Act issues a scenario triggers." },
  { id: "SGLB-06", workflow: "sglb_06", name: "Rules-of-Court-2021", source: "Rules of Court 2021 (SSO)", format: "scenario → applicable Order + Rule", metric: "exact-match (order:rule), top-3 acc", n: "~200", status: "spec", tier: "regulator", description: "Identify the ROC 2021 Order and Rule that govern a procedural scenario." },
  { id: "SGLB-07", workflow: "sglb_07", name: "Jurisdiction-Routing", source: "Curated SG cases citing UK/AU/HK precedent", format: "question → SG / UK persuasive / AU persuasive / N/A", metric: "accuracy", n: "~250", status: "spec", tier: "regulator", description: "Classify the source-jurisdiction of the controlling authority for an SG legal question." },
  { id: "SGLB-08", workflow: "sglb_08", name: "Clause-Tone", source: "Synthetic — SG clause library + tone taxonomy", format: "clause text → standard / aggressive / balanced / protective", metric: "multi-label F1", n: "synthesis-ready", status: "dataset", tier: "synthetic", description: "Classify the negotiation tone of a contractual clause. Labels fixed by the generation instruction; human-review-gated, multi-provider rotation." },
  { id: "SGLB-09", workflow: "sglb_09", name: "Summary-Faithfulness", source: "SG judgments + PDPC + MOM", format: "summary → atomic facts → source-grounded support", metric: "FActScore, hallucination rate", n: "~160 sources", status: "spec", tier: "regulator", description: "Atomic-fact precision of summaries against the source document." },
  { id: "SGLB-10", workflow: "sglb_10", name: "Citation-Generation", source: "SG judgments w/ explicit controlling-authority", format: "fact pattern → controlling SG citation", metric: "top-1, top-3 hit rate", n: "~300", status: "spec", tier: "regulator", description: "Predict the controlling SG authority for a fact pattern." },
  { id: "SGLB-11", workflow: "sglb_11", name: "Citation-Hallucination", source: "Synthesised passages w/ injected fake citations", format: "passage → list of fabricated citations", metric: "per-perturbation P/R/F1", n: "40 (smoke)", status: "dataset", tier: "regulator", description: "Detect fabricated SG citations among real ones. Perturbations are mechanical, real-pool is hand-curated SG case citations; rule-based generation, not LLM-tier." },
  { id: "SGLB-12", workflow: "sglb_12", name: "Multi-Issue-Spotting", source: "Synthetic — composed PDPA + EA + ROC scenarios", format: "fact pattern → set of issue labels", metric: "macro-F1, exact-set-match", n: "synthesis-ready", status: "dataset", tier: "synthetic", description: "Multi-source issue spotting across PDPA + EA + ROC 2021. Compound scenarios synthesised under fixed-label composition; human-review-gated." },
  { id: "SGLB-13", workflow: "sglb_13", name: "Counterfactual-Outcome", source: "PDPC decisions w/ minimal-pair fact perturbations", format: "pair (A, B) → same / different outcome", metric: "paired accuracy", n: "~150 pairs", status: "spec", tier: "regulator", description: "Counterfactual reasoning over PDPC outcomes." },
  { id: "SGLB-14", workflow: "sglb_14", name: "Statutory-Entailment", source: "PDPC + MOM regulator-stated worked examples", format: "(scenario, clause) → entails / contradicts / neutral", metric: "3-class accuracy", n: "~250", status: "spec", tier: "regulator", description: "Statutory entailment grounded in regulator worked examples." },
  { id: "SGLB-15", workflow: "sglb_15", name: "Draft-Constraint-Sat", source: "Synthetic — SG drafting briefs + verifiable constraints", format: "drafted document scored against IFEval-style constraints", metric: "per-constraint pass rate, all-pass", n: "synthesis-ready", status: "dataset", tier: "synthetic", description: "Verifiable constraint satisfaction on SG-context drafting. No LLM-judge in scoring pipeline; every constraint is a Python function." },
  { id: "SGLB-16", workflow: "sglb_16", name: "Review-Redflag-Recall", source: "SG-context contracts w/ planted defects", format: "contract → list of (excerpt, defect_class)", metric: "per-class recall, IoU localisation", n: "~80 contracts", status: "spec", tier: "regulator", description: "Planted-defect detection on SG contracts." },
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

const TIER_LABELS: Record<DataTier, string> = {
  regulator: "Regulator-tier",
  synthetic: "Synthetic-tier",
  mixed: "Mixed-tier",
};

const TIER_COLORS: Record<DataTier, { bg: string; fg: string; border: string }> = {
  regulator: { bg: "#ecfdf5", fg: "#065f46", border: "#34d399" },
  synthetic: { bg: "#fff7ed", fg: "#9a3412", border: "#fb923c" },
  mixed: { bg: "#f3e8ff", fg: "#6b21a8", border: "#c084fc" },
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

function entryTier(entry: LeaderboardEntry): DataTier {
  const value = entry.data_tier ?? "regulator";
  if (value === "synthetic" || value === "mixed") return value;
  return "regulator";
}

function TierBadge({ tier }: { tier: DataTier }) {
  const c = TIER_COLORS[tier];
  return (
    <span
      style={{
        fontSize: "0.7rem",
        padding: "0.15rem 0.45rem",
        borderRadius: "0.25rem",
        background: c.bg,
        color: c.fg,
        border: `1px solid ${c.border}`,
        fontWeight: 500,
      }}
    >
      {TIER_LABELS[tier]}
    </span>
  );
}

function LeaderboardTable({
  entries,
  evaluatorNames,
}: {
  entries: LeaderboardEntry[];
  evaluatorNames: string[];
}) {
  if (entries.length === 0) {
    return (
      <p style={{ color: "#94a3b8", fontSize: "0.8rem", margin: "0.5rem 0 0 0", fontStyle: "italic" }}>
        No runs in this tier yet.
      </p>
    );
  }
  return (
    <div style={{ overflowX: "auto", marginTop: "0.5rem" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem" }}>
        <thead>
          <tr style={{ background: "#f1f5f9" }}>
            <th style={th}>Run</th>
            <th style={th}>Workflow</th>
            <th style={th}>Cases</th>
            <th style={th}>Strict</th>
            {evaluatorNames.map((ev) => (
              <th key={ev} style={th}>
                {ev}
              </th>
            ))}
            <th style={th}>Finished</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr key={entry.run_id}>
              <td style={td}>
                <code>{entry.run_id}</code>
              </td>
              <td style={td}>{entry.workflow}</td>
              <td style={td}>{entry.total_cases}</td>
              <td style={td}>{entry.strict ? "yes" : "no"}</td>
              {evaluatorNames.map((ev) => (
                <td key={ev} style={td}>
                  {formatScore(entry.per_evaluator_mean[ev] ?? Number.NaN)}
                </td>
              ))}
              <td style={td}>{formatDate(entry.finished_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
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

  // Partition leaderboard entries by tier so the two cannot be compared by eye.
  // Per docs/coverage-matrix.md §4.1: regulator-tier and synthetic-tier scores
  // are not directly comparable. Mechanical-extraction labels (regulator) carry
  // a stronger defensibility claim than instruction-derived labels (synthetic).
  const regulatorEntries = leaderboard.entries.filter((e) => entryTier(e) === "regulator");
  const syntheticEntries = leaderboard.entries.filter((e) => entryTier(e) === "synthetic");
  const mixedEntries = leaderboard.entries.filter((e) => entryTier(e) === "mixed");

  const regulatorTasks = TASKS.filter((t) => t.tier === "regulator");
  const syntheticTasks = TASKS.filter((t) => t.tier === "synthetic");

  return (
    <main style={{ maxWidth: "960px", margin: "0 auto", padding: "2rem 1.25rem", fontFamily: "system-ui, -apple-system, sans-serif" }}>
      <Link href="/" style={{ fontSize: "0.8rem", color: "#64748b", textDecoration: "none" }}>&larr; Back</Link>
      <h1 style={{ fontSize: "1.5rem", margin: "0.6rem 0 0.5rem 0", fontWeight: 600 }}>SG-LegalBench Tasks &amp; Leaderboard</h1>
      <p style={{ color: "#475569", fontSize: "0.9rem", margin: "0 0 1rem 0" }}>
        Sixteen tasks across nine capability surfaces (see <a href="https://github.com/gongahkia/junas/blob/main/docs/coverage-matrix.md" style={{ color: "#1d4ed8" }}>coverage matrix</a>).
      </p>

      <section style={{ marginBottom: "1.5rem", padding: "0.85rem 1rem", background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "0.5rem", fontSize: "0.82rem", color: "#475569" }}>
        <strong style={{ color: "#0f172a" }}>Two tiers, scored separately.</strong>{" "}
        <TierBadge tier="regulator" /> tasks use labels mechanically extracted from public-domain regulator and court outputs. <TierBadge tier="synthetic" /> tasks (SGLB-08, -12, -15) use labels fixed by the generation instruction, with human-review-gated fixtures and multi-provider rotation. Scores are not directly comparable across tiers — see <a href="https://github.com/gongahkia/junas/blob/main/docs/coverage-matrix.md" style={{ color: "#1d4ed8" }}>coverage matrix §4.1</a>.
      </section>

      <section style={{ marginBottom: "2rem" }}>
        <h2 style={{ fontSize: "1.05rem", fontWeight: 600, margin: "0 0 0.5rem 0" }}>Leaderboard</h2>
        {leaderboard.entries.length === 0 ? (
          <p style={{ color: "#64748b", fontSize: "0.85rem", margin: 0 }}>
            No runs yet. Start one with <code>make eval WORKFLOW=sglb_04 DATASET=benchmark/datasets/sglb_04_citation_verify.yaml EVALUATORS=&quot;multi_label_f1&quot;</code> or <code>POST /api/v1/benchmarks/run</code>.
          </p>
        ) : (
          <>
            <div style={{ marginBottom: "1.25rem" }}>
              <h3 style={{ fontSize: "0.9rem", fontWeight: 600, margin: "0 0 0.25rem 0", display: "flex", alignItems: "center", gap: "0.4rem" }}>
                <TierBadge tier="regulator" /> ({regulatorEntries.length})
              </h3>
              <LeaderboardTable entries={regulatorEntries} evaluatorNames={evaluatorNames} />
            </div>

            <div style={{ marginBottom: "1.25rem" }}>
              <h3 style={{ fontSize: "0.9rem", fontWeight: 600, margin: "0 0 0.25rem 0", display: "flex", alignItems: "center", gap: "0.4rem" }}>
                <TierBadge tier="synthetic" /> ({syntheticEntries.length})
              </h3>
              <LeaderboardTable entries={syntheticEntries} evaluatorNames={evaluatorNames} />
            </div>

            {mixedEntries.length > 0 && (
              <div style={{ marginBottom: "1.25rem" }}>
                <h3 style={{ fontSize: "0.9rem", fontWeight: 600, margin: "0 0 0.25rem 0", display: "flex", alignItems: "center", gap: "0.4rem" }}>
                  <TierBadge tier="mixed" /> ({mixedEntries.length})
                </h3>
                <LeaderboardTable entries={mixedEntries} evaluatorNames={evaluatorNames} />
              </div>
            )}
          </>
        )}

        {Object.keys(leaderboard.aggregated_per_workflow).length > 0 && (
          <details style={{ marginTop: "0.75rem" }}>
            <summary style={{ fontSize: "0.8rem", color: "#475569", cursor: "pointer" }}>Per-workflow mean across all runs (raw)</summary>
            <pre style={{ fontSize: "0.75rem", background: "#f8fafc", padding: "0.5rem", borderRadius: "0.25rem", overflowX: "auto" }}>
              {JSON.stringify(leaderboard.aggregated_per_workflow, null, 2)}
            </pre>
            <p style={{ fontSize: "0.7rem", color: "#94a3b8", margin: "0.4rem 0 0 0", fontStyle: "italic" }}>
              The aggregated values above collapse across tiers and should be read with the per-tier tables above.
            </p>
          </details>
        )}
      </section>

      <TaskSection
        title="Regulator-tier tasks"
        tier="regulator"
        tasks={regulatorTasks}
        registeredWorkflows={registeredWorkflows}
        intro="Labels mechanically extracted from public regulator or court outputs. The benchmark's load-bearing defensibility commitment."
      />

      <TaskSection
        title="Synthetic-tier tasks"
        tier="synthetic"
        tasks={syntheticTasks}
        registeredWorkflows={registeredWorkflows}
        intro="Labels fixed by the generation instruction itself; human-review-gated; multi-provider rotation. Used only where regulator material is structurally unavailable for the capability."
      />

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

function TaskSection({
  title,
  tier,
  tasks,
  registeredWorkflows,
  intro,
}: {
  title: string;
  tier: DataTier;
  tasks: TaskSpec[];
  registeredWorkflows: Set<string>;
  intro: string;
}) {
  return (
    <section style={{ marginBottom: "2rem" }}>
      <h2 style={{ fontSize: "1.05rem", fontWeight: 600, margin: "0 0 0.25rem 0", display: "flex", alignItems: "center", gap: "0.5rem" }}>
        {title} <TierBadge tier={tier} /> <span style={{ fontSize: "0.78rem", color: "#94a3b8", fontWeight: 400 }}>({tasks.length})</span>
      </h2>
      <p style={{ color: "#64748b", fontSize: "0.8rem", margin: "0 0 0.75rem 0" }}>{intro}</p>
      <div style={{ display: "grid", gap: "0.75rem" }}>
        {tasks.map((t) => {
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
  );
}

const th: React.CSSProperties = { border: "1px solid #cbd5e1", padding: "0.45rem 0.6rem", textAlign: "left", fontWeight: 600 };
const td: React.CSSProperties = { border: "1px solid #e2e8f0", padding: "0.45rem 0.6rem", verticalAlign: "top" };
