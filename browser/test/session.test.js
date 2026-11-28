import assert from "node:assert/strict";
import { test } from "node:test";
import { ProcessingSession } from "../src/session.js";

function fixture(getAdapter = async () => ({ features: new Set(["shader-f16"]) })) {
  const worker = { terminated: false, postMessage(data) { this.sent = data; }, terminate() { this.terminated = true; } };
  let now = 0, created = 0;
  const session = new ProcessingSession({ createWorker: () => { created++; return worker; }, getAdapter, now: () => now });
  return { worker, session, advance: ms => { now += ms; }, created: () => created };
}
const result = text => ({ type: "result", timing: { load_ms: 1, inference_ms: 2 }, proposal: { document: { text }, complete: true, sensitivity: { pii: { state: "not_detected", evidence: [] }, mnpi: { state: "not_detected", evidence: [] } } } });
test("a reopened client sees a result completed without a connected view", async () => {
  const { session, worker } = fixture();
  try {
    await session.start("Nothing personal.");
    const closedClientSnapshot = session.snapshot();
    assert.equal(closedClientSnapshot.busy, true);
    worker.onmessage({ data: result("Nothing personal.") });
    const reopened = session.snapshot();
    assert.equal(reopened.busy, false);
    assert.equal(reopened.result.proposal.complete, true);
    reopened.result.proposal.complete = false;
    assert.equal(session.snapshot().result.proposal.complete, true);
  } finally { session.clear(); }
});
test("cancel rejects late worker messages and permits a new assessment", async () => {
  const { session, worker } = fixture();
  try {
    await session.start("First passage.");
    const late = worker.onmessage;
    session.cancel();
    late({ data: result("First passage.") });
    assert.equal(session.snapshot().result, null);
    assert.match(session.snapshot().status, /Cancelled/);
    await session.start("Second passage.");
    late({ data: result("First passage.") });
    assert.equal(session.snapshot().text, "Second passage.");
    assert.equal(session.snapshot().result, null);
  } finally { session.clear(); }
});
test("clear during adapter discovery cannot resurrect processing", async () => {
  let resolve;
  const { session, created } = fixture(() => new Promise(r => { resolve = r; }));
  const pending = session.start("Pending discovery.");
  session.clear();
  resolve({ features: new Set(["shader-f16"]) }); await pending;
  assert.equal(created(), 0); assert.equal(session.snapshot().text, "");
});
test("busy edits, unsupported models, bad input and mismatched results fail explicitly", async () => {
  const { session, worker } = fixture();
  try {
    await assert.rejects(session.start(" "), /nonblank/);
    await assert.rejects(session.start("ok", "untrusted-model"), /Unsupported/);
    await session.start("Original.");
    assert.throws(() => session.draft("Changed."), /Cancel/);
    await assert.rejects(session.start("Other."), /already running/);
    worker.onmessage({ data: result("Different.") });
    assert.equal(session.snapshot().result, null);
    assert.match(session.snapshot().status, /mismatch/);
  } finally { session.clear(); }
});
test("idle expiry erases passage/results and unavailable GPU creates no worker", async () => {
  const { session, advance } = fixture();
  session.draft("Private ephemeral draft."); advance(900_001); session.expire();
  assert.equal(session.snapshot().text, "");
  const unsupported = fixture(async () => null);
  await unsupported.session.start("A passage.");
  assert.equal(unsupported.created(), 0);
  assert.match(unsupported.session.snapshot().status, /WebGPU/);
  unsupported.session.clear(); session.clear();
});
