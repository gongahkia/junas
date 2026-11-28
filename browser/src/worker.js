import { CreateMLCEngine } from "@mlc-ai/web-llm";
import { MODEL, REQUEST_VERSION, admitText, inferenceRequest, decodeProposal } from "./contract.js";
import { modelConfig, WEIGHTS_REVISIONS, LIBRARY_REVISION } from "./model.js";

let engine;
let loadedModel;
const assetFetch = globalThis.fetch.bind(globalThis);
let busy = false;
self.onmessage = async ({ data }) => {
  if (busy) { self.postMessage({ type: "error", message: "A local request is already running." }); return; }
  busy = true;
  let phase = "input";
  try {
    const text = admitText(data.text);
    const model = data.model_id ?? MODEL;
    const config = modelConfig(model);
    const request = inferenceRequest(text);
    const started = performance.now();
    phase = "model_loading";
    if (engine && loadedModel !== model) { await engine.unload(); engine = undefined; }
    if (!engine) {
      globalThis.fetch = assetFetch;
      engine = await CreateMLCEngine(model, {
      appConfig: config,
      initProgressCallback: progress => self.postMessage({ type: "progress", message: progress.text }),
    }, { context_window_size: 4096 });
      loadedModel = model;
    }
    const loaded = performance.now();
    // after initialization there is no network fallback, including on errors.
    globalThis.fetch = async () => { throw Error("Network access is disabled during classification."); };
    phase = "inference";
    const reply = await engine.chat.completions.create(request);
    const choice = reply.choices?.[0];
    phase = "validation";
    const proposal = decodeProposal(text, choice);
    proposal.model = model;
    self.postMessage({ type: "result", proposal, model_identity: { model, request_version: REQUEST_VERSION, build_sha256: __JUNAS_BUILD_ID__, weights_revision: WEIGHTS_REVISIONS[model], library_revision: LIBRARY_REVISION, runtime: "@mlc-ai/web-llm@0.2.89" }, timing: {
      load_ms: loaded - started, inference_ms: performance.now() - loaded,
      total_ms: performance.now() - started,
    }, usage: reply.usage ?? null });
  } catch (error) {
    // only our static validation messages are exposed; runtime errors can include private data.
    const detail = phase === "validation" && error?.name !== "SyntaxError" ? error.message : "";
    const code = String(error?.constructor?.name ?? "Error").replace(/[^A-Za-z0-9_]/g, "").slice(0, 80);
    self.postMessage({ type: "error", phase, code, message: `Local ${phase.replaceAll("_", " ")} failed (${code}). ${detail} No clean result is available.` });
  } finally { busy = false; }
};
