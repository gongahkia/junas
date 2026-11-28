import { makeCases } from "../eval/cases.js";
import { scoreResults, validateCases } from "./evaluation.js";
const cases = validateCases(makeCases());
const $ = id => document.getElementById(id);
let worker, timer, rejectPending, stopped = false, rows = [], report;
function stopWorker() { worker?.terminate(); worker = undefined; clearTimeout(timer); }
function processCase(item) {
  return new Promise((resolve, reject) => {
    rejectPending = reject;
    worker ??= new Worker(new URL("worker.js", import.meta.url), { type: "module" });
    timer = setTimeout(() => { stopWorker(); reject(Error("timeout")); }, rows.length ? 120_000 : 600_000);
    worker.onerror = () => { stopWorker(); reject(Error("worker failure")); };
    worker.onmessage = ({ data }) => {
      if (data.type === "progress") $("status").textContent = data.message;
      if (data.type === "error") { stopWorker(); reject(Error("invalid or failed processing")); }
      if (data.type === "result") { clearTimeout(timer); resolve(data); }
    };
    worker.postMessage({ text: item.text });
  });
}
$("stop").onclick = () => { stopped = true; stopWorker(); rejectPending?.(Error("cancelled")); };
$("run").onclick = async () => {
  rows = []; stopped = false; report = undefined;
  $("run").disabled = true; $("stop").hidden = false; $("download").disabled = true;
  let errors = 0;
  const started = performance.now();
  let identity;
  try {
    const adapter = await navigator.gpu?.requestAdapter();
    if (!adapter?.features.has("shader-f16")) throw Error("A usable WebGPU adapter with shader-f16 is required; no model downloaded.");
    for (const item of cases) {
      if (stopped || performance.now() - started > 1_200_000) break;
      $("status").textContent = `Processing ${rows.length + 1} / ${cases.length}: ${item.id}`;
      try {
        const data = await processCase(item);
        identity = data.model_identity;
        rows.push({ id: item.id, text: item.text, states: Object.fromEntries(["pii", "mnpi"].map(c => [c, data.proposal.sensitivity[c].state])),
          pii_evidence: data.proposal.sensitivity.pii.evidence, inference_ms: data.timing.inference_ms,
          load_ms: data.timing.load_ms, proposal: data.proposal });
        errors = 0;
      } catch (error) {
        rows.push({ id: item.id, text: item.text, error: error.message });
        if (++errors >= 3) break;
      }
    }
    report = { ...scoreResults(cases, rows), model_identity: identity ?? null, elapsed_ms: performance.now() - started,
      completed: rows.length === cases.length && !stopped, rows };
    $("report").textContent = JSON.stringify({ ...report, rows: undefined }, null, 2);
    $("status").textContent = `Recorded ${rows.length} / ${cases.length} cases. Missing and failed cases are included as errors. Results are development agreement only.`;
    $("download").disabled = false;
  } catch (error) { $("status").textContent = error.message; }
  finally { stopWorker(); rejectPending = undefined; $("run").disabled = false; $("stop").hidden = true; }
};
$("download").onclick = () => {
  const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }));
  const link = document.createElement("a"); link.href = url; link.download = "junas-browser-development.json"; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
