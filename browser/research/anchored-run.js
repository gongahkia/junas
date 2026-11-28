import { makeCases } from "../eval/cases.js";
import screeningIds from "../eval/screening-ids.json" with { type: "json" };
import { MODEL_IDS } from "../src/contract.js";
import { scoreResults } from "../src/evaluation.js";
import { runValidation } from "./run-validation.js";
import { redactorMetrics } from "./redactor-metrics.js";
import { shadowFindings } from "./shadow-policy.js";
import { ANCHORED_REQUEST_VERSION } from "./anchored-request.js";

const development = makeCases(), screen = screeningIds.map(id => development.find(c => c.id === id));
const policy = { pii: true, mnpi: true, threshold: .85, mnpiExtent: "evidence" };
const status = message => { document.getElementById("status").textContent = message; };
const prefix = "anchored-v1";
async function save(name, data) {
  const response = await fetch("/checkpoint", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, data }) });
  if (!response.ok) throw Error("Checkpoint failed; stop rather than discard evidence.");
}
async function saved(name) {
  const response = await fetch(`/saved/${name}`);
  if (response.status === 404) return null;
  if (!response.ok) throw Error("Checkpoint read failed.");
  return response.json();
}
function summary(cases, rows, split = "development") {
  const sweeps = [];
  for (const mnpiExtent of ["evidence", "sentences"]) for (const threshold of [0, .5, .7, .85, .95, 1]) for (const pii of [false, true]) for (const mnpi of [false, true]) {
    const { examples, ...metrics } = redactorMetrics(cases, rows, { threshold, pii, mnpi, mnpiExtent });
    sweeps.push(metrics);
  }
  return { classification: scoreResults(cases, rows, { split }), default_policy: redactorMetrics(cases, rows, policy),
    shadow_policy: redactorMetrics(cases, rows, policy, shadowFindings), sweeps };
}
async function runBatch(cases, model, stage, initial = []) {
  const key = `${prefix}-${stage}-${model}`;
  const checkpoint = await saved(key);
  if (checkpoint && (checkpoint.request_version !== ANCHORED_REQUEST_VERSION || checkpoint.artifact_sha256 !== __JUNAS_BUILD_ID__)) throw Error("Checkpoint configuration mismatch.");
  if (checkpoint?.completed) return checkpoint;
  const result = await runValidation(cases, model, async progress => {
    status(`${stage}: ${model}, ${progress.completed} / ${progress.total}, ${progress.id}`);
    if (progress.rows) await save(key, { rows: progress.rows, completed: false, request_version: ANCHORED_REQUEST_VERSION, artifact_sha256: __JUNAS_BUILD_ID__ });
  }, { confidence: true, workerUrl: "anchored-worker.js", rows: checkpoint?.rows ?? initial.filter(r => cases.some(c => c.id === r.id && c.text === r.text)) });
  const report = { ...result, ...summary(cases, result.rows, stage === "validation" ? "validation" : "development"), request_version: ANCHORED_REQUEST_VERSION,
    artifact_sha256: __JUNAS_BUILD_ID__, reference_kind: `authored_synthetic_${stage === "validation" ? "validation" : "development"}_expectation` };
  await save(key, report);
  if (!result.completed) throw Error(`Incomplete ${stage}; preserved partial evidence and stopped.`);
  return report;
}

export async function run() {
  const mode = new URLSearchParams(location.search).get("mode") ?? "smoke";
  if (!["smoke", "all"].includes(mode)) throw Error("Use smoke or all mode.");
  const smokeIds = ["acquisition-0-nn", "acquisition-0-nm", "acquisition-0-pn", "acquisition-0-pm", "edge-conflicting_disclosure-true", "edge-mixed_issuers-false", "edge-document_instructions-true", "edge-missing_materiality-false"];
  const smoke = await runBatch(development.filter(c => smokeIds.includes(c.id)), MODEL_IDS[0], "smoke");
  if (mode === "smoke") { status("Eight-case candidate smoke recorded. Inspect the saved outputs before comparison."); return; }
  const screens = [];
  for (const model of MODEL_IDS) screens.push(await runBatch(screen, model, "screen", model === MODEL_IDS[0] ? smoke.rows : []));
  // select on fixed development evidence only; validation cannot affect this order or policy.
  const usable = screens.filter(r => r.rows.some(row => row.proposal?.complete));
  const weakest = r => Math.min(r.default_policy.pii_char_recall ?? 0, r.default_policy.mnpi_documents_redacted / r.default_policy.mnpi_positive_documents);
  usable.sort((a, b) => weakest(b) - weakest(a) || a.default_policy.negative_documents_changed - b.default_policy.negative_documents_changed || a.classification.failed - b.classification.failed || MODEL_IDS.indexOf(a.model) - MODEL_IDS.indexOf(b.model));
  if (!usable.length) throw Error("No complete candidate. Validation remains untouched.");
  const selected = usable[0];
  const all = await runBatch(development, selected.model, "development", selected.rows);
  const freeze = { model: selected.model, artifact_sha256: __JUNAS_BUILD_ID__, validation_sha256: __JUNAS_VALIDATION_SHA256__, request_version: ANCHORED_REQUEST_VERSION, policy,
    screening_order: usable.map(r => r.model), development_gates_passed: all.classification.passed,
    status: all.classification.passed ? "candidate_for_authored_validation" : "exploratory_candidate_with_failed_development_gates",
    classification_applied: false, paid_api_calls: 0, interpretation: "Frozen authored-development selection; no independent accuracy or calibrated-confidence claim." };
  await save(`${prefix}-freeze`, freeze);
  const response = await fetch("frozen-validation.json");
  if (!response.ok) throw Error("Frozen validation artifact unavailable.");
  const bytes = await response.arrayBuffer();
  const digest = [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))].map(b => b.toString(16).padStart(2, "0")).join("");
  if (digest !== __JUNAS_VALIDATION_SHA256__) throw Error("Frozen validation hash mismatch.");
  const validation = JSON.parse(new TextDecoder().decode(bytes));
  if (validation.length !== 48) throw Error("Expected the frozen 48-case validation set.");
  await runBatch(validation, selected.model, "validation");
  await save(`${prefix}-complete`, { ...freeze, completed: true });
  status("Development and frozen authored validation recorded. No candidate was deployed automatically.");
}
