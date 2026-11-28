// consumes a frozen authored set only after candidate selection; no reference labels enter the worker.
export async function runValidation(cases, model, onProgress = () => {}, options = {}) {
  let worker, consecutiveInfrastructureErrors = 0;
  const rows = structuredClone(options.rows ?? []), started = performance.now();
  if (new Set(rows.map(r => r.id)).size !== rows.length || rows.some(r => !cases.some(c => c.id === r.id && c.text === r.text))) throw Error("Checkpoint identity/source mismatch.");
  let attempts = 0;
  let identity;
  try {
    for (const item of cases) {
      if (rows.some(r => r.id === item.id)) continue;
      if (performance.now() - started > 3_600_000 || consecutiveInfrastructureErrors >= 3) break;
      onProgress({ completed: rows.length, total: cases.length, id: item.id });
      const attemptStarted = performance.now();
      try {
        worker ??= new Worker(options.workerUrl ?? "worker.js", { type: "module" });
        const data = await new Promise((resolve, reject) => {
          const timer = setTimeout(() => { worker?.terminate(); worker = undefined; reject(Error("timeout")); }, attempts++ ? 120_000 : 600_000);
          worker.onerror = () => { clearTimeout(timer); reject(Error("worker failure")); };
          worker.onmessage = ({ data }) => {
            if (data.type === "result") { clearTimeout(timer); resolve(data); }
            if (data.type === "error") { clearTimeout(timer); reject(Object.assign(Error(data.message), { phase: data.phase, code: data.code })); }
          };
          worker.postMessage({ text: item.text, model_id: model, confidence: options.confidence === true });
        });
        identity = data.model_identity;
        rows.push({ id: item.id, text: item.text, states: Object.fromEntries(["pii", "mnpi"].map(c => [c, data.proposal.sensitivity[c].state])),
          pii_evidence: data.proposal.sensitivity.pii.evidence, inference_ms: data.timing.inference_ms, load_ms: data.timing.load_ms,
          wall_ms: performance.now() - attemptStarted, proposal: data.proposal, model_identity: data.model_identity, usage: data.usage });
        consecutiveInfrastructureErrors = 0;
      } catch (error) {
        rows.push({ id: item.id, text: item.text, error: error.message, phase: error.phase ?? "infrastructure", code: error.code ?? null, wall_ms: performance.now() - attemptStarted });
        if (error.phase === "validation") consecutiveInfrastructureErrors = 0;
        else { worker?.terminate(); worker = undefined; consecutiveInfrastructureErrors++; }
      }
      await onProgress({ completed: rows.length, total: cases.length, id: item.id, rows: structuredClone(rows) });
    }
    return { rows, model_identity: identity ?? null, model, completed: rows.length === cases.length, elapsed_ms: performance.now() - started,
      reference_kind: "authored_synthetic_validation_expectation", interpretation: "Untouched authored validation agreement; not independent accuracy." };
  } finally { worker?.terminate(); }
}
