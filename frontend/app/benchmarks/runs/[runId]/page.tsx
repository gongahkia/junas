import Link from "next/link";
import { headers } from "next/headers";

type EvaluatorScore = {
  score: number;
  error?: string | null;
  metadata?: Record<string, unknown>;
};

type CaseDetail = {
  case_name: string;
  input: Record<string, unknown>;
  expected: Record<string, unknown> | null;
  actual: unknown;
  evaluator_scores: Record<string, EvaluatorScore>;
};

type RunDetail = {
  run_id: string;
  workflow: string;
  dataset: string;
  evaluators: string[];
  total_cases: number;
  per_evaluator_mean: Record<string, number>;
  started_at: string;
  finished_at: string;
  strict: boolean;
  weak_evaluators_used: string[];
  data_tier?: string;
  provenance?: Record<string, unknown>;
  cases: CaseDetail[];
};

type SortDir = "asc" | "desc";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

async function getRun(runId: string, apiKey: string): Promise<RunDetail | null> {
  const requestHeaders = apiKey.trim() ? { "X-API-Key": apiKey.trim() } : undefined;
  try {
    const resp = await fetch(
      `${API_BASE}/api/v1/benchmarks/runs/${encodeURIComponent(runId)}`,
      { cache: "no-store", headers: requestHeaders },
    );
    if (!resp.ok) return null;
    return (await resp.json()) as RunDetail;
  } catch {
    return null;
  }
}

function paramValue(value: string | string[] | undefined): string {
  if (Array.isArray(value)) return value[0] ?? "";
  return value ?? "";
}

function formatDate(iso: string): string {
  if (!iso) return "-";
  try {
    return new Date(iso).toISOString().replace("T", " ").slice(0, 19) + " UTC";
  } catch {
    return iso;
  }
}

function formatScore(value: number | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "-";
  return value.toFixed(3);
}

function stringify(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

function sortValue(row: CaseDetail, sort: string): string | number {
  if (sort === "case") return row.case_name;
  if (sort === "input") return stringify(row.input);
  if (sort === "expected") return stringify(row.expected);
  if (sort === "actual") return stringify(row.actual);
  if (sort.startsWith("score:")) {
    const evaluator = sort.slice("score:".length);
    const score = row.evaluator_scores[evaluator]?.score;
    return typeof score === "number" ? score : Number.NaN;
  }
  return row.case_name;
}

function sortedCases(cases: CaseDetail[], sort: string, dir: SortDir): CaseDetail[] {
  const direction = dir === "asc" ? 1 : -1;
  return [...cases].sort((a, b) => {
    const av = sortValue(a, sort);
    const bv = sortValue(b, sort);
    if (typeof av === "number" || typeof bv === "number") {
      const an = typeof av === "number" && Number.isFinite(av) ? av : -Infinity;
      const bn = typeof bv === "number" && Number.isFinite(bv) ? bv : -Infinity;
      return (an - bn) * direction;
    }
    return String(av).localeCompare(String(bv)) * direction;
  });
}

function sortHref(runId: string, key: string, current: string, dir: SortDir): string {
  const nextDir: SortDir = current === key && dir === "asc" ? "desc" : "asc";
  return `/benchmarks/runs/${encodeURIComponent(runId)}?sort=${encodeURIComponent(key)}&dir=${nextDir}`;
}

function SortHeader({
  label,
  sortKey,
  runId,
  current,
  dir,
}: {
  label: string;
  sortKey: string;
  runId: string;
  current: string;
  dir: SortDir;
}) {
  const active = current === sortKey;
  return (
    <th style={th}>
      <Link href={sortHref(runId, sortKey, current, dir)} style={sortLink}>
        {label}
        {active ? <span style={sortState}> {dir}</span> : null}
      </Link>
    </th>
  );
}

function ScoreCell({ score }: { score?: EvaluatorScore }) {
  const value = score?.score;
  const bg = typeof value === "number" && value >= 0.8 ? "#dcfce7" : "#fef3c7";
  const fg = typeof value === "number" && value >= 0.8 ? "#166534" : "#92400e";
  return (
    <td style={td}>
      <span style={{ ...scorePill, background: bg, color: fg }}>{formatScore(value)}</span>
      {score?.error ? <div style={errorText}>{score.error}</div> : null}
    </td>
  );
}

export default async function BenchmarkRunPage({
  params,
  searchParams,
}: {
  params: { runId: string };
  searchParams?: Record<string, string | string[] | undefined>;
}) {
  const runId = decodeURIComponent(params.runId);
  const apiKey = headers().get("X-API-Key") ?? "";
  const run = await getRun(runId, apiKey);
  const requestedSort = paramValue(searchParams?.sort);
  const dir = paramValue(searchParams?.dir) === "desc" ? "desc" : "asc";

  if (!run) {
    return (
      <main style={page}>
        <Link href="/benchmarks" style={backLink}>Back to benchmarks</Link>
        <h1 style={title}>Run not found</h1>
        <p style={muted}><code>{runId}</code></p>
      </main>
    );
  }

  const evaluators = run.evaluators.length > 0
    ? run.evaluators
    : Array.from(new Set(run.cases.flatMap((c) => Object.keys(c.evaluator_scores)))).sort();
  const allowedSorts = new Set(["case", "input", "expected", "actual", ...evaluators.map((e) => `score:${e}`)]);
  const sort = allowedSorts.has(requestedSort) ? requestedSort : "case";
  const rows = sortedCases(run.cases, sort, dir);

  return (
    <main style={page}>
      <Link href="/benchmarks" style={backLink}>Back to benchmarks</Link>
      <header style={header}>
        <div>
          <p style={eyebrow}>Benchmark run</p>
          <h1 style={title}><code>{run.run_id}</code></h1>
        </div>
        <div style={summaryGrid}>
          <Metric label="Workflow" value={run.workflow} />
          <Metric label="Cases" value={String(run.total_cases)} />
          <Metric label="Strict" value={run.strict ? "yes" : "no"} />
          <Metric label="Tier" value={run.data_tier ?? "regulator"} />
        </div>
      </header>

      <section style={metaBand}>
        <div><strong>Dataset:</strong> <code>{run.dataset}</code></div>
        <div><strong>Started:</strong> {formatDate(run.started_at)}</div>
        <div><strong>Finished:</strong> {formatDate(run.finished_at)}</div>
        {run.weak_evaluators_used.length > 0 ? (
          <div><strong>Weak evaluators:</strong> {run.weak_evaluators_used.join(", ")}</div>
        ) : null}
      </section>

      <section style={scoreBand}>
        {evaluators.map((evaluator) => (
          <div key={evaluator} style={meanItem}>
            <span style={meanLabel}>{evaluator}</span>
            <span style={meanValue}>{formatScore(run.per_evaluator_mean[evaluator])}</span>
          </div>
        ))}
      </section>

      <section>
        <div style={tableHeader}>
          <h2 style={sectionTitle}>Per-case results</h2>
          <span style={muted}>{rows.length} rows, sorted by {sort} {dir}</span>
        </div>
        <div style={tableWrap}>
          <table style={table}>
            <thead>
              <tr>
                <SortHeader label="Case" sortKey="case" runId={run.run_id} current={sort} dir={dir} />
                <SortHeader label="Input" sortKey="input" runId={run.run_id} current={sort} dir={dir} />
                <SortHeader label="Expected" sortKey="expected" runId={run.run_id} current={sort} dir={dir} />
                <SortHeader label="Actual" sortKey="actual" runId={run.run_id} current={sort} dir={dir} />
                {evaluators.map((evaluator) => (
                  <SortHeader
                    key={evaluator}
                    label={evaluator}
                    sortKey={`score:${evaluator}`}
                    runId={run.run_id}
                    current={sort}
                    dir={dir}
                  />
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.case_name}>
                  <td style={td}><code>{row.case_name}</code></td>
                  <td style={td}><pre style={pre}>{stringify(row.input)}</pre></td>
                  <td style={td}><pre style={pre}>{stringify(row.expected)}</pre></td>
                  <td style={td}><pre style={pre}>{stringify(row.actual)}</pre></td>
                  {evaluators.map((evaluator) => (
                    <ScoreCell key={evaluator} score={row.evaluator_scores[evaluator]} />
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div style={metric}>
      <span style={metricLabel}>{label}</span>
      <span style={metricValue}>{value}</span>
    </div>
  );
}

const page: React.CSSProperties = {
  maxWidth: "1180px",
  margin: "0 auto",
  padding: "2rem 1.25rem",
  fontFamily: "system-ui, -apple-system, sans-serif",
  color: "#1c1917",
};
const backLink: React.CSSProperties = { color: "#2563eb", fontSize: "0.82rem", textDecoration: "none" };
const header: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "minmax(0, 1fr) minmax(280px, 420px)",
  gap: "1rem",
  alignItems: "end",
  marginTop: "0.75rem",
  marginBottom: "1rem",
};
const eyebrow: React.CSSProperties = {
  margin: 0,
  color: "#78716c",
  fontSize: "0.76rem",
  fontWeight: 700,
  textTransform: "uppercase",
  letterSpacing: "0.06em",
};
const title: React.CSSProperties = { margin: "0.15rem 0 0", fontSize: "1.35rem", fontWeight: 650, lineHeight: 1.25 };
const summaryGrid: React.CSSProperties = { display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: "0.5rem" };
const metric: React.CSSProperties = { border: "1px solid #e7e5e4", borderRadius: "0.45rem", padding: "0.55rem 0.65rem", background: "#ffffff" };
const metricLabel: React.CSSProperties = { display: "block", color: "#78716c", fontSize: "0.68rem", textTransform: "uppercase", letterSpacing: "0.04em" };
const metricValue: React.CSSProperties = { display: "block", marginTop: "0.15rem", fontSize: "0.9rem", fontWeight: 650, overflowWrap: "anywhere" };
const metaBand: React.CSSProperties = {
  display: "grid",
  gap: "0.35rem",
  padding: "0.85rem 1rem",
  borderTop: "1px solid #e7e5e4",
  borderBottom: "1px solid #e7e5e4",
  background: "#fafafa",
  fontSize: "0.82rem",
  color: "#44403c",
  overflowWrap: "anywhere",
};
const scoreBand: React.CSSProperties = { display: "flex", flexWrap: "wrap", gap: "0.5rem", margin: "1rem 0 1.25rem" };
const meanItem: React.CSSProperties = { display: "flex", alignItems: "center", gap: "0.45rem", border: "1px solid #d6d3d1", borderRadius: "0.4rem", padding: "0.35rem 0.55rem", background: "#fff" };
const meanLabel: React.CSSProperties = { fontSize: "0.78rem", color: "#57534e" };
const meanValue: React.CSSProperties = { fontSize: "0.84rem", fontWeight: 700, color: "#166534" };
const tableHeader: React.CSSProperties = { display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: "1rem", marginBottom: "0.5rem", flexWrap: "wrap" };
const sectionTitle: React.CSSProperties = { margin: 0, fontSize: "1rem", fontWeight: 650 };
const muted: React.CSSProperties = { color: "#78716c", fontSize: "0.8rem", margin: 0 };
const tableWrap: React.CSSProperties = { overflowX: "auto", border: "1px solid #d6d3d1", borderRadius: "0.45rem", background: "#fff" };
const table: React.CSSProperties = { width: "100%", borderCollapse: "collapse", fontSize: "0.78rem" };
const th: React.CSSProperties = { background: "#f5f5f4", borderBottom: "1px solid #d6d3d1", padding: "0.5rem 0.6rem", textAlign: "left", verticalAlign: "bottom", whiteSpace: "nowrap" };
const td: React.CSSProperties = { borderTop: "1px solid #e7e5e4", padding: "0.5rem 0.6rem", verticalAlign: "top", maxWidth: "22rem" };
const sortLink: React.CSSProperties = { color: "#1c1917", textDecoration: "none", fontWeight: 650 };
const sortState: React.CSSProperties = { color: "#2563eb", fontWeight: 700 };
const pre: React.CSSProperties = { margin: 0, maxHeight: "12rem", overflow: "auto", whiteSpace: "pre-wrap", overflowWrap: "anywhere", fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", fontSize: "0.72rem", lineHeight: 1.45 };
const scorePill: React.CSSProperties = { display: "inline-flex", minWidth: "3.4rem", justifyContent: "center", borderRadius: "0.25rem", padding: "0.12rem 0.35rem", fontWeight: 700 };
const errorText: React.CSSProperties = { marginTop: "0.3rem", color: "#b91c1c", fontSize: "0.72rem", overflowWrap: "anywhere" };
