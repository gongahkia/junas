// live research harness: real headed Chromium, real model, isolated profile, stdin commands.
import { chromium } from "playwright";
import { mkdir, writeFile, appendFile } from "node:fs/promises";
import { resolve } from "node:path";
import { createInterface } from "node:readline";

const output = process.env.JUNAS_LIVE_OUTPUT;
if (!output) throw Error("Set JUNAS_LIVE_OUTPUT to a private, task-owned evidence directory.");
if (process.platform !== "linux") throw Error("This live harness uses Linux X11/Vulkan flags; use the normal extension on other platforms.");
await mkdir(output, { recursive: true });
const browser = await chromium.launchPersistentContext(resolve(output, "profile"), {
  executablePath: process.env.JUNAS_CHROMIUM || undefined,
  headless: false,
  viewport: null,
  args: [
    `--disable-extensions-except=${resolve("dist")}`, `--load-extension=${resolve("dist")}`,
    "--ozone-platform=x11", "--enable-unsafe-webgpu",
    "--enable-features=Vulkan,VulkanFromANGLE,DefaultANGLEVulkan", "--use-angle=vulkan",
  ],
});
const started = Date.now();
let bytes = 0, requests = 0;
browser.on("requestfinished", async request => {
  if (!/^https?:/.test(request.url())) return;
  const url = new URL(request.url());
  try {
    const sizes = await request.sizes();
    bytes += sizes.responseBodySize + sizes.responseHeadersSize;
    requests++;
    await appendFile(resolve(output, "requests.jsonl"), JSON.stringify({
      time: Date.now(), method: request.method(), origin: url.origin, path: url.pathname,
      response_bytes: sizes.responseBodySize, total_observed_bytes: bytes,
    }) + "\n");
  } catch {}
});
browser.on("page", page => {
  page.on("pageerror", error => appendFile(resolve(output, "errors.jsonl"), JSON.stringify({ time: Date.now(), message: error.message.slice(0, 1000) }) + "\n"));
});
const background = browser.serviceWorkers()[0] ?? await browser.waitForEvent("serviceworker");
const base = background.url().replace("background.js", "");
let page = await browser.newPage();
await page.goto(base + "process.html");
const gpu = await page.evaluate(async () => {
  const adapter = await navigator.gpu?.requestAdapter();
  return { webgpu: !!navigator.gpu, adapter: !!adapter, features: adapter ? [...adapter.features] : [],
    info: adapter?.info ? { vendor: adapter.info.vendor, architecture: adapter.info.architecture } : null,
    user_agent: navigator.userAgent };
});
await writeFile(resolve(output, "gpu.json"), JSON.stringify(gpu, null, 2));
console.log(JSON.stringify({ ready: true, base, gpu }));
const lines = createInterface({ input: process.stdin });
browser.on("close", () => lines.close());
try {
  for await (const line of lines) {
    try {
      const command = JSON.parse(line);
      if (command.action === "close") break;
      if (command.action === "goto") {
        if (page.isClosed()) page = await browser.newPage();
        await page.goto(command.url.startsWith("/") ? base + command.url.slice(1) : command.url);
      }
      if (command.action === "click") await page.locator(command.selector).click(command.options ?? {});
      if (command.action === "fill") await page.locator(command.selector).fill(command.text);
      if (command.action === "press") await page.keyboard.press(command.key);
      if (command.action === "mouse") {
        if (command.event === "move") await page.mouse.move(command.x, command.y, { steps: command.steps ?? 1 });
        if (command.event === "down") await page.mouse.down({ button: command.button ?? "left" });
        if (command.event === "up") await page.mouse.up({ button: command.button ?? "left" });
        if (command.event === "click") await page.mouse.click(command.x, command.y, { button: command.button ?? "left" });
      }
      if (command.action === "upload") await page.locator(command.selector).setInputFiles(command.path);
      if (command.action === "newest") page = browser.pages().filter(candidate => !candidate.isClosed()).at(-1) ?? await browser.newPage();
      if (command.action === "evaluate") {
        const value = await page.evaluate(command.expression);
        if (command.save) await writeFile(resolve(output, command.save), JSON.stringify(value, null, 2));
        console.log(JSON.stringify({ action: command.action, value }));
        continue;
      }
      if (command.action === "screenshot") await page.screenshot({ path: resolve(output, command.name), fullPage: true });
      if (command.action === "download") {
        const download = page.waitForEvent("download");
        await page.locator(command.selector).click();
        await (await download).saveAs(resolve(output, command.name));
      }
      if (command.action === "offline") await browser.setOffline(command.enabled);
      if (command.action === "snapshot") {
        console.log(JSON.stringify({ url: page.url(), pages: browser.pages().map(p => p.url()),
          state: await page.evaluate(() => {
            const raw = document.getElementById("report")?.textContent;
            const report = raw ? JSON.parse(raw) : null;
            return { status: document.getElementById("status")?.textContent,
              resultsVisible: document.getElementById("results")?.hidden === false,
              report: report ? { documents: report.documents, received: report.received, failed: report.failed, completed: report.completed } : null };
          }),
          elapsed_ms: Date.now() - started, response_bytes: bytes, requests }));
        continue;
      }
      console.log(JSON.stringify({ action: command.action, done: true }));
    } catch (error) { console.log(JSON.stringify({ error: error.message.slice(0, 1500) })); }
  }
} finally { await browser.close(); }
