import { makeCases } from "../eval/cases.js";
import { scoreResults, validateCases } from "./evaluation.js";
import { MODEL } from "./contract.js";
import screeningIds from "../eval/screening-ids.json" with { type: "json" };
const allCases = validateCases(makeCases());
let cases = allCases;
const $ = id => document.getElementById(id);
let worker, timer, rejectPending, stopped = false, rows = [], report, attempts = 0;
function stopWorker() { worker?.terminate(); worker = undefined; clearTimeout(timer); }
function processCase(item) {
  return new Promise((resolve, reject) => {
    rejectPending = reject;
    worker ??= new Worker(new URL("worker.js", import.meta.url), { type: "module" });
    timer = setTimeout(() => { stopWorker(); reject(Error("timeout")); }, attempts++ ? 120_000 : 600_000);
    worker.onerror = () => { stopWorker(); reject(Error("worker failure")); };
    worker.onmessage = ({ data }) => {
      if (data.type === "progress") $("status").textContent = data.message;
      if (data.type === "error") {
        clearTimeout(timer);
        if (data.phase !== "validation") stopWorker();
        const error = Error(data.message || "invalid or failed processing");
        error.phase = data.phase;
        error.code = data.code;
        reject(error);
      }
      if (data.type === "result") { clearTimeout(timer); resolve(data); }
    };
    worker.postMessage({ text: item.text, model_id: $("model").value || MODEL });
  });
}
$("stop").onclick = () => { stopped = true; stopWorker(); rejectPending?.(Error("cancelled")); };
$("run").onclick = async () => {
  rows = globalThis.junasResumeRows ?? []; globalThis.junasResumeRows = undefined;
  attempts = 0; stopped = false; report = undefined;
  cases = $("suite").value === "screening" ? allCases.filter(c => screeningIds.includes(c.id)) : allCases;
  scoreResults(cases, rows);
  const resumedReceived = rows.length;
  $("run").disabled = $("model").disabled = $("suite").disabled = true; $("stop").hidden = false; $("download").disabled = true;
  let errors = 0;
  const started = performance.now();
  let identity;
  try {
    const adapter = await navigator.gpu?.requestAdapter();
    if (!adapter?.features.has("shader-f16")) throw Error("A usable WebGPU adapter with shader-f16 is required; no model downloaded.");
    for (const item of cases) {
      if (rows.some(row => row.id === item.id)) continue;
      if (stopped || performance.now() - started > 3_600_000) break;
      $("status").textContent = `Processing ${rows.length + 1} / ${cases.length}: ${item.id}`;
      const attemptStarted = performance.now();
      try {
        const data = await processCase(item);
        identity = data.model_identity;
        rows.push({ id: item.id, text: item.text, states: Object.fromEntries(["pii", "mnpi"].map(c => [c, data.proposal.sensitivity[c].state])),
          pii_evidence: data.proposal.sensitivity.pii.evidence, inference_ms: data.timing.inference_ms,
          load_ms: data.timing.load_ms, wall_ms: performance.now() - attemptStarted, usage: data.usage, proposal: data.proposal });
        errors = 0;
      } catch (error) {
        rows.push({ id: item.id, text: item.text, error: error.message, phase: error.phase ?? "infrastructure", code: error.code ?? null, wall_ms: performance.now() - attemptStarted });
        // rejected proposals remain failures without preventing coverage of other families.
        if (error.phase === "validation") errors = 0;
        else if (++errors >= 3) break;
      }
      dispatchEvent(new CustomEvent("junas-research-row", { detail: { model: $("model").value, suite: $("suite").value, rows: structuredClone(rows) } }));
    }
    report = { ...scoreResults(cases, rows), selected_suite: $("suite").value, selected_model: $("model").value, model_identity: identity ?? null, elapsed_ms: performance.now() - started,
      completed: rows.length === cases.length && !stopped, resumed_received: resumedReceived,
      resume_limit: resumedReceived ? "Earlier row timings retained; earlier rows lack individual build identities. Run spans a browser/server restart." : null, rows };
    // research automation reads the same complete report offered by the download button.
    globalThis.junasBenchmarkReport = structuredClone(report);
    $("report").textContent = JSON.stringify({ ...report, rows: undefined }, null, 2);
    $("status").textContent = `Recorded ${rows.length} / ${cases.length} cases. Missing and failed cases are included as errors. Results are development agreement only.`;
    $("download").disabled = false;
  } catch (error) { $("status").textContent = error.message; }
  finally { stopWorker(); rejectPending = undefined; $("run").disabled = $("model").disabled = $("suite").disabled = false; $("stop").hidden = true; }
};
$("download").onclick = () => {
  const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }));
  const link = document.createElement("a"); link.href = url; link.download = "junas-browser-development.json"; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
