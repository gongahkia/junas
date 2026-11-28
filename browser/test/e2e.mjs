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
  await unsupported.addInitScript(() => Object.defineProperty(navigator, "gpu", { value: undefined, configurable: true }));
  await unsupported.goto(base + "process.html");
  await unsupported.locator("#source").fill("Contact alice.tan@example.com.");
  await unsupported.locator("#process").click();
  await unsupported.getByRole("status").filter({ hasText: "WebGPU is unavailable" }).waitFor();
  assert.equal(await unsupported.locator("#results").isVisible(), false);
  await unsupported.close();

  const source = "🙂 Contact alice.tan@example.com.";
  await background.evaluate(async text => chrome.storage.session.set({ "selection:test-capture": { text, created: Date.now() } }), source);
  await context.addInitScript(() => {
    Object.defineProperty(navigator, "gpu", { value: { requestAdapter: async () => ({ features: new Set(["shader-f16"]) }) }, configurable: true });
    class MockWorker {
      terminated = false;
      constructor() { globalThis.workerCount = (globalThis.workerCount ?? 0) + 1; }
      postMessage({ text }) {
        setTimeout(() => {
          if (this.terminated) return;
          const quote = "alice.tan@example.com";
          const start = Array.from(text.slice(0, text.indexOf(quote))).length;
          this.onmessage?.({ data: { type: "result", timing: { load_ms: 1, inference_ms: 2 },
            proposal: { document: { text }, complete: true, sensitivity: {
              pii: { state: "present", evidence: [{ label: "EMAIL", matched_text: quote, start_char: start, end_char: start + quote.length }] },
              mnpi: { state: "not_detected", evidence: [] }, absence_verified: false,
            } } } });
        }, 20);
      }
      terminate() { this.terminated = true; }
    }
    globalThis.Worker = MockWorker;
  });
  const page = await context.newPage();
  page.on("pageerror", error => errors.push(error.message));
  await page.goto(base + "process.html?selection=test-capture");
  await page.locator("#results").waitFor();
  assert.equal(await page.locator("#source").inputValue(), source);
  assert.deepEqual(await background.evaluate(() => chrome.storage.session.get(null)), {});
  await page.locator("#evidence input").check();
  await page.locator("#preview").click();
  assert.equal(await page.locator("#redacted").inputValue(), "🙂 Contact [REDACTED].");
  assert.equal(await page.locator("#source").inputValue(), source);
  await page.locator("#copy").click();
  await page.getByRole("status").filter({ hasText: "Redacted text copied" }).waitFor();
  await page.locator("#source").fill("Changed source.");
  assert.equal(await page.locator("#results").isVisible(), false);
  await page.locator("#clear").click();
  assert.equal(await page.locator("#source").inputValue(), "");
  assert.equal(await page.locator("#redacted").inputValue(), "");
  assert.equal(await page.locator("#json").textContent(), "");
  await page.evaluate(() => {
    navigator.gpu.requestAdapter = () => new Promise(resolve => { globalThis.resolveAdapter = resolve; });
  });
  await page.locator("#source").fill(source);
  const workerCount = await page.evaluate(() => globalThis.workerCount);
  await page.locator("#process").click();
  await page.locator("#clear").click();
  await page.evaluate(() => globalThis.resolveAdapter({ features: new Set(["shader-f16"]) }));
  assert.equal(await page.evaluate(() => globalThis.workerCount), workerCount);
  assert.equal(await page.locator("#source").inputValue(), "");
  await page.setViewportSize({ width: 375, height: 812 });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  assert.deepEqual(errors, []);
  assert.deepEqual(requests, []);
  console.log("PASS: unpacked extension loads; selection handoff, unsupported-device failure, mocked processing, redaction preview/copy, invalidation, clearing and narrow layout; no remote requests.");
} finally {
  await context?.close();
  await rm(profile, { recursive: true, force: true });
}
