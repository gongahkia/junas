import { makeCases } from "../eval/cases.js";
import { MODEL } from "../src/contract.js";
import { runValidation } from "./run-validation.js";
import { redactorMetrics } from "./redactor-metrics.js";
const cases = makeCases();
const key = "redactor-baseline-v1";
async function save(data) {
  const r = await fetch("/checkpoint", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: key, data }) });
  if (!r.ok) throw Error("Checkpoint failed; stop evaluation.");
}
export async function run() {
  const stopped = await fetch("/saved/baseline-futility-stop");
  if (stopped.ok) { document.getElementById("status").textContent = "Original baseline intentionally stopped: its locked detection targets are unreachable. Partial evidence is preserved."; return; }
  if (stopped.status !== 404) throw Error("Cannot verify baseline stop status.");
  const previous = await fetch(`/saved/${key}`);
  const checkpoint = previous.ok ? await previous.json() : {};
  if (checkpoint.completed) { document.getElementById("status").textContent = "Saved baseline already complete."; return; }
  const result = await runValidation(cases, MODEL, async progress => {
    document.getElementById("status").textContent = `Actual redactor ${Math.min(progress.completed + 1, progress.total)} / ${progress.total}: ${progress.id}`;
    if (progress.rows) await save({ rows: progress.rows, completed: false, request_version: "redaction-estimates-v1" });
  }, { confidence: true, rows: checkpoint.rows ?? [] });
  const sweeps = [];
  for (const threshold of [0, .5, .7, .85, .95, 1]) for (const pii of [false, true]) for (const mnpi of [false, true]) {
    const { examples, ...summary } = redactorMetrics(cases, result.rows, { threshold, pii, mnpi });
    sweeps.push(summary);
  }
  await save({ ...result, reference_kind: "authored_synthetic_development_expectation", request_version: "redaction-estimates-v1", sweeps,
    default_policy: redactorMetrics(cases, result.rows, { threshold: .85, pii: true, mnpi: true }) });
  document.getElementById("status").textContent = `Baseline recorded: ${result.rows.length} / ${cases.length}. Inspect saved errors and outputs before tuning.`;
}
