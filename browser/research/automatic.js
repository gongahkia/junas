import { MODEL_IDS } from "../src/contract.js";
import { scoreResults } from "../src/evaluation.js";
import { rankCandidates } from "./selection.mjs";
import { makeValidationCases } from "./validation-cases.mjs";
import { runValidation } from "./run-validation.js";

const validation = makeValidationCases();
let stage = "screening", saving = Promise.resolve();
function save(name, data) {
  saving = saving.then(async () => {
    const response = await fetch("/checkpoint", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, data }) });
    if (!response.ok) throw Error("Research checkpoint failed; stop rather than discard evidence.");
  });
  return saving;
}
addEventListener("junas-research-row", event => { save(`${stage}-${event.detail.model}-partial`, event.detail).catch(() => document.getElementById("stop").click()); });
async function run(model, suite) {
  document.getElementById("model").value = model;
  document.getElementById("suite").value = suite;
  globalThis.junasBenchmarkReport = null;
  document.getElementById("run").click();
  const deadline = Date.now() + 3_750_000;
  while (document.getElementById("download").disabled) {
    if (Date.now() > deadline) throw Error("Research deadline exceeded.");
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  const report = globalThis.junasBenchmarkReport;
  if (!report) throw Error("No completed research report.");
  await save(`${stage}-${model}`, report);
  return report;
}
export async function runResearch() {
  await save("research-plan", { models: MODEL_IDS, screening_documents: 32, full_documents: 144, validation_documents: 48,
    paid_api_calls: 0, interpretation: "Authored development and untouched authored validation; no independent accuracy or promotion claim." });
  const screens = [];
  for (const model of MODEL_IDS) screens.push(await run(model, "screening"));
  const candidate = rankCandidates(screens);
  await save("candidate-freeze", candidate);
  stage = "development";
  await run(candidate.model, "full");
  stage = "validation";
  const result = await runValidation(validation, candidate.model, progress => {
    document.getElementById("status").textContent = `Frozen validation ${Math.min(progress.completed + 1, progress.total)} / ${progress.total}: ${progress.id}`;
    if (progress.rows) return save("validation-partial", { model: candidate.model, rows: progress.rows });
  });
  await save("validation-result", { ...scoreResults(validation, result.rows, { split: "validation" }), ...result });
  await save("research-complete", { candidate, completed: true, classification_applied: false, paid_api_calls: 0 });
  document.getElementById("status").textContent = "Research finished. Saved all reports; no model automatically promoted.";
}
