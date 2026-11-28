import { test } from "node:test";
import assert from "node:assert/strict";
import { runValidation } from "../research/run-validation.js";

test("bounded research worker lifetimes preserve checkpoints and release each worker", async () => {
  const original = globalThis.Worker, workers = [], checkpoints = [];
  globalThis.Worker = class {
    posts = 0;
    terminated = false;
    constructor(url) { this.url = url; workers.push(this); }
    postMessage({ text }) {
      this.posts++;
      queueMicrotask(() => this.onmessage({ data: { type: "result", proposal: { document: { text }, complete: true,
        sensitivity: { pii: { state: "not_detected", evidence: [] }, mnpi: { state: "not_detected", evidence: [] } } }, timing: { inference_ms: 1, load_ms: 1 } } }));
    }
    terminate() { this.terminated = true; }
  };
  try {
    const cases = Array.from({ length: 5 }, (_, i) => ({ id: String(i), text: `Passage ${i}.` }));
    const result = await runValidation(cases, "model", progress => { if (progress.rows) checkpoints.push(progress.rows.length); }, { workerUrl: "candidate.js", maxCasesPerWorker: 2 });
    assert.equal(result.completed, true);
    assert.deepEqual(checkpoints, [1, 2, 3, 4, 5]);
    assert.deepEqual(workers.map(w => w.posts), [2, 2, 1]);
    assert.ok(workers.every(w => w.terminated && w.url === "candidate.js"));
  } finally { globalThis.Worker = original; }
});
