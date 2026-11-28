import { readFile, writeFile } from "node:fs/promises";
import { parseArgs } from "node:util";
import { resolve } from "node:path";
import { createHash } from "node:crypto";
import { makeCases } from "../eval/cases.js";
import screenIds from "../eval/screening-ids.json" with { type: "json" };
import { MODEL_IDS } from "../src/contract.js";
import { scoreResults } from "../src/evaluation.js";
import { redactorMetrics, redactionPolicyScore } from "./redactor-metrics.js";
import { shadowFindings } from "./shadow-policy.js";

const { values } = parseArgs({ options: { evidence: { type: "string" }, validation: { type: "string" }, output: { type: "string" }, candidate: { type: "string", default: "anchored-v3" }, "allow-partial": { type: "boolean", default: false } } });
if (!values.evidence || !values.validation || !values.output) throw Error("Use --evidence PRIVATE_DIR --validation FROZEN_JSON --output NEW_JSON [--allow-partial].");
if (!/^anchored-v\d+$/.test(values.candidate)) throw Error("Invalid candidate version.");
const prefix = values.candidate;
const root = resolve(values.evidence), development = makeCases(), files = {};
async function read(name) {
  try {
    const bytes = await readFile(resolve(root, name));
    files[name] = createHash("sha256").update(bytes).digest("hex");
    return JSON.parse(bytes);
  } catch (error) { if (values["allow-partial"] && error.code === "ENOENT") return null; throw error; }
}
const shadowFreeze = await read("local-pattern-v4-freeze.json");
if (shadowFreeze) for (const [file, expected] of Object.entries(shadowFreeze.source_sha256)) {
  if (createHash("sha256").update(await readFile(file)).digest("hex") !== expected) throw Error("Separately frozen shadow candidate changed.");
}
function percentile(list, p) {
  const ordered = list.filter(Number.isFinite).sort((a, b) => a - b);
  return ordered.length ? ordered[Math.ceil(ordered.length * p) - 1] : null;
}
const policy = { pii: true, mnpi: true, threshold: .85, mnpiExtent: "evidence" };
function score(cases, report, split = "development", documentedStop = null) {
  if (!report) return null;
  if (!values["allow-partial"] && !documentedStop && (!report.completed || report.rows.length !== cases.length)) throw Error("Cannot finalize an incomplete run.");
  const rows = report.rows;
  return { model: report.model ?? MODEL_IDS[0], completed: report.completed, received: rows.length, documents: cases.length,
    documented_stop: documentedStop, request_version: report.request_version, artifact_sha256: report.artifact_sha256 ?? report.model_identity?.build_sha256 ?? null,
    classification: scoreResults(cases, rows, { split }), policy_decisions: redactionPolicyScore(cases, rows, policy, split), default_policy: redactorMetrics(cases, rows, policy),
    separately_frozen_shadow_policy: shadowFreeze ? redactorMetrics(cases, rows, policy, shadowFindings) : null,
    attempt_wall_ms: { samples: rows.length, p50: percentile(rows.map(r => r.wall_ms), .5), p95: percentile(rows.map(r => r.wall_ms), .95) },
    successful_inference_ms: { samples: rows.filter(r => Number.isFinite(r.inference_ms)).length, p50: percentile(rows.map(r => r.inference_ms), .5), p95: percentile(rows.map(r => r.inference_ms), .95) },
    rows };
}
const baselineRows = await read("redactor-baseline-v1.json"), baselineStop = await read("baseline-futility-stop.json");
if (baselineStop) {
  if (baselineStop.received !== baselineRows.rows.length) throw Error("Baseline changed after its documented stop.");
  for (const [category, minimum] of [["pii", .9], ["mnpi", .8]]) {
    const positives = development.filter(c => c.expected[category] === "present");
    const byId = new Map(baselineRows.rows.map(r => [r.id, r]));
    const upper = positives.filter(c => !byId.has(c.id) || byId.get(c.id).states?.[category] === "present").length / positives.length;
    if (upper >= minimum || upper !== baselineStop.bounds[category].maximum_possible_final_detection) throw Error("Baseline futility claim does not match saved evidence.");
  }
}
const baseline = score(development, baselineRows, "development", baselineStop);
const screens = [];
for (const model of MODEL_IDS) {
  const name = `${prefix}-screen-${model}`.replace(/[^a-zA-Z0-9_-]/g, "_") + ".json";
  screens.push(score(screenIds.map(id => development.find(c => c.id === id)), await read(name)));
}
const freeze = await read(`${prefix}-freeze.json`);
let selectedDevelopment = null, validation = null;
if (freeze) {
  const manifest = await read(`${prefix}-manifest.json`);
  if (freeze.artifact_sha256 !== manifest?.artifact_sha256) throw Error("Freeze/manifest identity mismatch.");
  const key = stage => `${prefix}-${stage}-${freeze.model}`.replace(/[^a-zA-Z0-9_-]/g, "_") + ".json";
  selectedDevelopment = score(development, await read(key("development")));
  const bytes = await readFile(values.validation);
  if (createHash("sha256").update(bytes).digest("hex") !== freeze.validation_sha256) throw Error("Validation reference hash mismatch.");
  validation = score(JSON.parse(bytes), await read(key("validation")), "validation");
  for (const report of [selectedDevelopment, validation].filter(Boolean)) if (report.artifact_sha256 !== freeze.artifact_sha256 || report.rows.some(r => r.model_identity && r.model_identity.build_sha256 !== freeze.artifact_sha256)) throw Error("Evaluated artifact differs from the freeze.");
}
const output = { generated_at: new Date().toISOString(), status: values["allow-partial"] ? "partial_snapshot_not_final" : "completed",
  reference_kind: "authored_synthetic_development_and_validation_expectations", interpretation: "Authored agreement, not independent accuracy or calibrated confidence. MNPI paragraph allowance cannot establish minimal-span correctness.",
  paid_api_calls: 0, new_paid_api_spend_usd: 0, production_candidate_enabled: false, policy, source_files_sha256: files,
  baseline, screens, freeze, shadow_candidate_freeze: shadowFreeze, selected_development: selectedDevelopment, validation };
await writeFile(values.output, JSON.stringify(output, null, 2) + "\n", { flag: "wx" });
console.log(JSON.stringify({ status: output.status, baseline_received: baseline?.received, screening_received: screens.map(r => r?.received ?? 0), validation_received: validation?.received ?? 0 }));
