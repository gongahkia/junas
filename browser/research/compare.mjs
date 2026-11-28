// attach to an explicitly supplied existing browser; never launch or close it.
import { chromium } from "playwright";
import { parseArgs } from "node:util";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { createHash } from "node:crypto";
import { MODEL_IDS } from "../src/contract.js";
import { scoreResults } from "../src/evaluation.js";

const { values } = parseArgs({ options: { endpoint: { type: "string" }, extension: { type: "string" }, output: { type: "string" } } });
if (!values.endpoint || !/^[a-p]{32}$/.test(values.extension ?? "") || !values.output) throw Error("Usage: node research/compare.mjs --endpoint http://127.0.0.1:PORT --extension INSTALLED_ID --output PRIVATE_DIRECTORY");
const endpoint = new URL(values.endpoint);
if (endpoint.protocol !== "http:" || !["127.0.0.1", "localhost", "[::1]"].includes(endpoint.hostname) || endpoint.username || endpoint.password) throw Error("Use an explicitly enabled loopback browser endpoint, without credentials.");
const output = resolve(values.output);
await mkdir(output, { recursive: true });
const source = await readFile(new URL("../eval/cases.json", import.meta.url));
const cases = JSON.parse(source);
const plan = { models: MODEL_IDS, dataset_sha256: createHash("sha256").update(source).digest("hex"), documents_per_model: cases.length,
  interpretation: "Authored development agreement, not independent accuracy. No automatic classifier promotion.",
  paid_api_calls: 0, new_paid_api_spend_usd: "0", per_model_deadline_minutes: 60 };
await writeFile(resolve(output, "plan.json"), JSON.stringify(plan, null, 2) + "\n", { flag: "wx" });
const browser = await chromium.connectOverCDP(values.endpoint, { timeout: 10_000 });
const context = browser.contexts()[0];
if (!context) throw Error("The connected browser exposes no usable context.");
const page = await context.newPage();
const base = `chrome-extension://${values.extension}/`;
let current = null;
const reports = [];
// do not inspect or export the user's other tabs or request bodies.
page.on("requestfinished", async request => {
  if (!current || !/^https?:/.test(request.url())) return;
  try {
    const sizes = await request.sizes();
    current.asset_response_bytes += sizes.responseBodySize + sizes.responseHeadersSize;
    current.asset_response_requests++;
  } catch {}
});
try {
  for (const model of MODEL_IDS) {
    await page.goto(base + "benchmark.html");
    await page.locator("#model").selectOption(model);
    current = { model, asset_response_bytes: 0, asset_response_requests: 0 };
    await page.locator("#run").click();
    await page.waitForFunction(() => !document.getElementById("download").disabled, undefined, { timeout: 3_750_000 });
    const [download] = await Promise.all([page.waitForEvent("download"), page.locator("#download").click()]);
    const path = resolve(output, `${model}.json`);
    await writeFile(path, await readFile(await download.path()), { flag: "wx" });
    const report = JSON.parse(await readFile(path, "utf8"));
    const rescored = scoreResults(cases, report.rows);
    for (const [key, value] of Object.entries(rescored)) if (JSON.stringify(report[key]) !== JSON.stringify(value)) throw Error(`Saved score mismatch: ${key}`);
    reports.push({ ...current, received: report.received, failed: report.failed, completed: report.completed,
      measurements: report.measurements, targets: report.targets, passed: report.passed,
      model_identity: report.model_identity, elapsed_ms: report.elapsed_ms,
      inference_ms: report.inference_ms, complete_proposals: report.rows.filter(r => r.proposal?.complete).length,
      wall_ms: report.rows.map(r => r.wall_ms), report_sha256: createHash("sha256").update(await readFile(path)).digest("hex") });
    console.log(JSON.stringify({ model, received: report.received, failed: report.failed, passed: report.passed }));
    current = null;
  }
  await writeFile(resolve(output, "comparison.json"), JSON.stringify({ ...plan, reports }, null, 2) + "\n", { flag: "wx" });
  await page.goto(base + "popup.html");
  console.log("Saved comparison. Existing browser remains open; no other tabs were inspected.");
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
} finally {
  // ending this client drops its CDP connection without sending Browser.close.
  setImmediate(() => process.exit(process.exitCode ?? 0));
}
