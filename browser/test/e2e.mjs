// browser-flow checks use a fake worker; they do not measure model quality.
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const profile = await mkdtemp(join(tmpdir(), "junas-extension-test-"));
let context;
try {
  const extension = resolve("dist");
  context = await chromium.launchPersistentContext(profile, {
    executablePath: process.env.JUNAS_CHROMIUM || undefined,
    headless: true,
    args: [`--disable-extensions-except=${extension}`, `--load-extension=${extension}`],
  });
  const background = context.serviceWorkers()[0] ?? await context.waitForEvent("serviceworker");
  const base = background.url().replace("background.js", "");
  const requests = [], errors = [];
  context.on("request", request => { if (/^https?:/.test(request.url())) requests.push(request.url()); });
  await context.route(/^https?:/, route => route.abort());
  const unsupported = await context.newPage();
  await unsupported.goto(base + "process.html");
  await unsupported.evaluate(() => chrome.runtime.sendMessage({ target: "session", kind: "get" }));
  const inspector = await context.newCDPSession(unsupported);
  async function offscreenEvaluate(expression) {
    const targets = (await inspector.send("Target.getTargets")).targetInfos;
    const target = targets.find(t => t.url === base + "offscreen.html");
    assert.ok(target, "offscreen document exists");
    const { sessionId } = await inspector.send("Target.attachToTarget", { targetId: target.targetId, flatten: false });
    try {
      return await new Promise((resolve, reject) => {
        const timeout = setTimeout(() => { inspector.off("Target.receivedMessageFromTarget", handler); reject(Error("offscreen inspector timeout")); }, 5000);
        function handler(event) {
          if (event.sessionId !== sessionId) return;
          const response = JSON.parse(event.message);
          if (response.id !== 1) return;
          clearTimeout(timeout); inspector.off("Target.receivedMessageFromTarget", handler);
          if (response.error || response.result?.exceptionDetails) reject(Error(JSON.stringify(response)));
          else resolve(response.result?.result?.value);
        }
        inspector.on("Target.receivedMessageFromTarget", handler);
        inspector.send("Target.sendMessageToTarget", { sessionId, message: JSON.stringify({ id: 1, method: "Runtime.evaluate", params: { expression, returnByValue: true, awaitPromise: true } }) }).catch(reject);
      });
    } finally { await inspector.send("Target.detachFromTarget", { sessionId }); }
  }
  await offscreenEvaluate('Object.defineProperty(navigator,"gpu",{value:undefined,configurable:true})');
  await unsupported.locator("#source").fill("Contact alice.tan@example.com.");
  await unsupported.locator("#process").click();
  await unsupported.getByRole("status").filter({ hasText: "WebGPU adapter" }).waitFor();
  assert.equal(await unsupported.locator("#results").isVisible(), false);
  await offscreenEvaluate(`(${() => {
    Object.defineProperty(navigator, "gpu", { value: { requestAdapter: async () => ({ features: new Set(["shader-f16"]) }) }, configurable: true });
    globalThis.workerCount = 0;
    globalThis.Worker = class {
      terminated = false;
      constructor() { globalThis.workerCount++; }
      postMessage({ text }) {
        setTimeout(() => {
          if (this.terminated) return;
          const quote = "alice.tan@example.com";
          const start = Array.from(text.slice(0, text.indexOf(quote))).length;
          this.onmessage?.({ data: { type: "result", timing: { load_ms: 1, inference_ms: 2 }, proposal: {
            document: { text }, complete: true, sensitivity: {
              pii: { state: "present", evidence: [{ label: "EMAIL", matched_text: quote, start_char: start, end_char: start + quote.length }] },
              mnpi: { state: "not_detected", evidence: [] }, absence_verified: false,
            }
          } } });
        }, 800);
      }
      terminate() { this.terminated = true; }
    };
  }})()`);
  const source = "🙂 Contact alice.tan@example.com.";
  await background.evaluate(async text => chrome.storage.session.set({ "selection:test-capture": { text, created: Date.now() } }), source);
  await context.addInitScript(() => Object.defineProperty(navigator, "gpu", { value: { requestAdapter: async () => ({ features: new Set(["shader-f16"]) }) }, configurable: true }));
  const firstView = await context.newPage();
  await firstView.goto(base + "process.html?selection=test-capture");
  await firstView.waitForFunction(() => !document.getElementById("cancel").hidden);
  await firstView.close();
  const page = await context.newPage();
  page.on("pageerror", error => errors.push(error.message));
  await page.goto(base + "popup.html");
  await page.locator("#results").waitFor();
  assert.equal(await page.locator("#source").inputValue(), source);
  assert.deepEqual(await background.evaluate(() => chrome.storage.session.get(null)), {});
  assert.equal(await offscreenEvaluate("globalThis.workerCount"), 1);
  await page.locator("#evidence input").check();
  await page.locator("#preview").click();
  assert.equal(await page.locator("#redacted").inputValue(), "🙂 Contact [REDACTED].");
  assert.equal(await page.locator("#source").inputValue(), source);
  await page.locator("#copy").click();
  await page.getByRole("status").filter({ hasText: "saved to clipboard" }).waitFor();
  await page.locator("#source").fill("Changed source.");
  assert.equal(await page.locator("#results").isVisible(), false);
  await page.locator("#clear").click();
  await page.waitForFunction(() => document.getElementById("source").value === "");
  assert.equal(await page.locator("#redacted").inputValue(), "");
  assert.equal(await page.locator("#json").textContent(), "");
  await page.locator("#source").fill(source);
  await page.locator("#process").click();
  await page.locator("#cancel").waitFor();
  await page.locator("#cancel").click();
  await page.getByRole("status").filter({ hasText: "Cancelled" }).waitFor();
  await page.waitForTimeout(1000);
  assert.equal(await page.locator("#results").isVisible(), false);
  await page.setViewportSize({ width: 375, height: 812 });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  const benchmark = await context.newPage();
  await benchmark.addInitScript(() => {
    globalThis.benchmarkWorkers = 0;
    globalThis.Worker = class {
      calls = 0;
      constructor() { globalThis.benchmarkWorkers++; }
      terminate() {}
      postMessage() {
        const first = ++this.calls === 1;
        queueMicrotask(() => this.onmessage?.({ data: first
          ? { type: "error", phase: "validation", code: "Error", message: "Rejected fabricated evidence." }
          : { type: "result", timing: { load_ms: 0, inference_ms: 1 }, proposal: {
            sensitivity: { pii: { state: "unknown", evidence: [] }, mnpi: { state: "unknown", evidence: [] } },
          } } }));
      }
    };
  });
  await benchmark.goto(base + "benchmark.html");
  await benchmark.locator("#run").click();
  await benchmark.locator("#download").waitFor({ state: "visible" });
  await benchmark.waitForFunction(() => !document.getElementById("download").disabled);
  const coverage = await benchmark.locator("#report").textContent().then(JSON.parse);
  assert.equal(coverage.received, 144);
  assert.equal(coverage.failed, 1);
  assert.equal(coverage.passed, false);
  assert.equal(await benchmark.evaluate(() => globalThis.benchmarkWorkers), 1);
  await benchmark.close();
  const infrastructure = await context.newPage();
  await infrastructure.addInitScript(() => {
    globalThis.Worker = class {
      terminate() {}
      postMessage() { queueMicrotask(() => this.onmessage?.({ data: {
        type: "error", phase: "inference", code: "Error", message: "Runtime unavailable.",
      } })); }
    };
  });
  await infrastructure.goto(base + "benchmark.html");
  await infrastructure.locator("#run").click();
  await infrastructure.waitForFunction(() => !document.getElementById("download").disabled);
  const interrupted = await infrastructure.locator("#report").textContent().then(JSON.parse);
  assert.equal(interrupted.received, 3);
  assert.equal(interrupted.failed, 144);
  assert.equal(interrupted.completed, false);
  await infrastructure.close();
  assert.deepEqual(errors, []);
  assert.deepEqual(requests, []);
  console.log("PASS: popup/offscreen processing survives closing/reopening the view; selection handoff, unsupported-device failure, mocked processing, redaction preview/copy, invalidation, clearing and narrow layout; no remote requests.");
} finally {
  await context?.close();
  await rm(profile, { recursive: true, force: true });
}
